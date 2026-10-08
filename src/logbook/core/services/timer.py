"""타이머 시작·조회·종료·취소 유스케이스.

시각은 직접 만들지 않고 now(aware datetime)를 인자로 받는다. 기록 날짜와 표시 시각은
now의 시간대 기준으로 계산한다.
"""

from collections.abc import Collection
from datetime import datetime, timedelta
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from logbook.core.duration import MAX_MINUTES
from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.models import ActiveTimer, Task, TaskStatus, WorkLog
from logbook.core.services._resolve import (
    clean_note,
    pick_slug,
    resolve_category,
    target_project,
)
from logbook.core.services._shared import load_task
from logbook.core.services.projects import COMMON_SLUG
from logbook.core.services.tasks import set_task_status

MAX_ROUND_MINUTES = 60

_TIMER_ID = 1
_ONE_SECOND = timedelta(seconds=1)
NO_TIMER_MESSAGE = "진행 중인 타이머가 없습니다. 'lb start \"메모\"'로 시작하세요."


class StartedTimer(NamedTuple):
    timer: ActiveTimer
    task_started: bool  # 연결한 태스크를 todo → doing으로 바꿨는지


class TimerStopped(NamedTuple):
    log: WorkLog
    elapsed_minutes: int  # 반올림 전 경과(분, 30초 반올림)


def start_timer(
    s: Session,
    *,
    now: datetime,
    note: str | None,
    project_slug: str | None = None,
    category: str | None = None,
    task_id: int | None = None,
    allowed_categories: Collection[str] | None = None,
    default_project: str = COMMON_SLUG,
) -> StartedTimer:
    """타이머를 시작한다. 프로젝트·카테고리는 add_worklog와 같은 순서로 정한다.

    메모를 생략하면 태스크 제목을 쓰고, todo 태스크는 doing으로 바꾼다.
    """
    _check_aware(now)
    running = get_timer(s)
    if running is not None:
        raise InvalidInputError(
            f"이미 진행 중인 타이머가 있습니다: {running.project.slug}/{running.category} "
            f"'{running.note}' ({_time_label(running.started_at, now)} 시작). "
            "'lb stop'으로 저장하거나 'lb cancel'로 버리세요."
        )
    task = load_task(s, task_id) if task_id is not None else None
    checked_note = task.title if note is None and task is not None else clean_note(note or "")
    slug = pick_slug(project_slug, task, default_project)
    project = target_project(s, slug, task, current=None)
    resolved_category = resolve_category(category, task, allowed_categories)
    task_started = task is not None and task.status == TaskStatus.TODO
    if task is not None and task_started:
        set_task_status(s, task.id, TaskStatus.DOING)
    timer = ActiveTimer(
        id=_TIMER_ID,
        project=project,
        task=task,
        category=resolved_category,
        note=checked_note,
        started_at=now,
    )
    s.add(timer)
    s.flush()
    return StartedTimer(timer, task_started)


def get_timer(s: Session) -> ActiveTimer | None:
    """진행 중인 타이머 (project, task 함께 로드). 없으면 None."""
    query = (
        select(ActiveTimer)
        .where(ActiveTimer.id == _TIMER_ID)
        .options(
            joinedload(ActiveTimer.project),
            joinedload(ActiveTimer.task).joinedload(Task.project),
        )
    )
    return s.scalars(query).one_or_none()


def elapsed_minutes(started_at: datetime, now: datetime) -> int:
    """경과 분(30초 이상 올림). now가 더 이르면 0."""
    return _round_to_minute(_elapsed_seconds(started_at, now))


def stop_timer(
    s: Session,
    *,
    now: datetime,
    extra_note: str | None = None,
    round_to: int | None = None,
) -> TimerStopped:
    """타이머를 업무 기록으로 저장하고 지운다. 기록 날짜는 시작한 날(now 시간대 기준)이다.

    프로젝트 보관 여부와 카테고리 허용 목록은 다시 검사하지 않는다 (시작할 때 검사했다).
    분 계산이 거부되면 타이머는 그대로 남는다.
    """
    _check_aware(now)
    timer = _require_timer(s)
    note = timer.note if extra_note is None else f"{timer.note} — {_clean_extra(extra_note)}"
    step = _checked_round_to(round_to)
    seconds = _elapsed_seconds(timer.started_at, now)
    elapsed = _round_to_minute(seconds)
    if elapsed == 0:
        raise InvalidInputError(
            "1분이 지나지 않아 기록하지 않았습니다. 버리려면 'lb cancel'을 실행하세요."
        )
    minutes = elapsed if step is None else _rounded_minutes(seconds, step)
    if minutes > MAX_MINUTES:
        raise InvalidInputError(
            f"타이머가 24시간을 넘었습니다 (시작 {_time_label(timer.started_at, now)}). "
            "'lb cancel'로 버린 뒤 'lb add'로 날짜별로 나눠 기록하세요."
        )
    log = WorkLog(
        project=timer.project,
        task=timer.task,
        category=timer.category,
        date=timer.started_at.astimezone(now.tzinfo).date(),
        minutes=minutes,
        note=note,
        started_at=timer.started_at,
        ended_at=now,
    )
    s.add(log)
    s.delete(timer)
    s.flush()
    return TimerStopped(log, elapsed)


def cancel_timer(s: Session) -> ActiveTimer:
    """타이머를 기록 없이 지운다. 지운 타이머(관계 로드됨)를 반환한다. 없으면 NotFoundError."""
    timer = _require_timer(s)
    s.delete(timer)
    s.flush()
    return timer


def _require_timer(s: Session) -> ActiveTimer:
    timer = get_timer(s)
    if timer is None:
        raise NotFoundError(NO_TIMER_MESSAGE)
    return timer


def _check_aware(now: datetime) -> None:
    # 시간대를 추측하지 않는다. naive 값은 호출 쪽 프로그래밍 오류다.
    if now.utcoffset() is None:
        raise ValueError(f"now must be timezone-aware: {now!r}")


def _elapsed_seconds(started_at: datetime, now: datetime) -> int:
    """경과 초(내림). now가 더 이르면 0."""
    return max(0, (now - started_at) // _ONE_SECOND)


def _round_to_minute(seconds: int) -> int:
    """초를 분으로 바꾼다(30초 이상 올림)."""
    return (seconds + 30) // 60


def _rounded_minutes(seconds: int, step: int) -> int:
    """step분 단위 반올림. 0이 되면 최소 한 단위로 올린다 (seconds가 30초 이상일 때만 호출)."""
    minutes = ((seconds + step * 30) // (step * 60)) * step
    return minutes or step


def _checked_round_to(round_to: object) -> int | None:
    if round_to is None:
        return None
    # bool은 int의 하위 타입이지만 단위로 받지 않는다.
    if (
        isinstance(round_to, bool)
        or not isinstance(round_to, int)
        or not 1 <= round_to <= MAX_ROUND_MINUTES
    ):
        raise InvalidInputError(f"반올림 단위는 1~60분 사이의 정수여야 합니다: {round_to!r}")
    return round_to


def _clean_extra(extra_note: str) -> str:
    extra = extra_note.strip()
    if not extra:
        raise InvalidInputError(
            "덧붙일 메모가 비어 있습니다. 메모를 덧붙이지 않으려면 --note를 빼세요."
        )
    return extra


def _time_label(at: datetime, now: datetime) -> str:
    """now 시간대 기준 HH:MM. now와 날짜가 다르면 MM-DD HH:MM."""
    local = at.astimezone(now.tzinfo)
    label = f"{local.hour:02d}:{local.minute:02d}"
    if local.date() == now.date():
        return label
    return f"{local.month:02d}-{local.day:02d} {label}"
