"""화면이 쓰는 뷰 데이터: 기록 행, 타이머, 기록 한 줄 문구, 기록 버전.

서비스가 돌려준 ORM 객체는 세션 안에서 이 모듈의 불변 값으로 바꾼다. 템플릿은 세션을 닫은 뒤 그린다.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from logbook.core import services
from logbook.core.duration import format_duration
from logbook.core.errors import InvalidInputError
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import clock_label, day_label, full_day, week_heading

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from logbook.core.config import Config
    from logbook.core.models import ActiveTimer, Project, WorkLog
    from logbook.core.weeks import Week

RECENT_LIMIT = 10
NO_TASK = "-"
ARCHIVED_MARK = " (보관)"
DELETE_CONFIRM = "삭제할 기록: {record}\n삭제할까요?"
CANCEL_CONFIRM = (
    "버릴 타이머: {scope} — {note} (시작 {started} · 경과 {elapsed})\n"
    "버릴까요? 기록은 남지 않습니다."
)
LOGS_PATH = "/logs"
# 색을 정하지 않은 프로젝트와 카테고리에 돌려 쓰는 색. 모두 흰 배경에서 구분된다.
CHART_PALETTE = (
    "#2f6fde",
    "#e8590c",
    "#2b8a3e",
    "#c2255c",
    "#7048e8",
    "#0b7285",
    "#e67700",
    "#5c940d",
    "#a61e4d",
    "#495057",
)
# 버전 문자열에서 필드를 가르는 구분자(필드 값에 나올 수 없는 제어 문자)
_FIELD_SEPARATOR = "\x1f"
_VERSION_LENGTH = 16


def project_color(project: Project) -> str:
    """지정한 색(검증된 #rrggbb)이 있으면 그 색, 없으면 프로젝트 ID로 고른 CHART_PALETTE 색.

    자동 색은 팔레트를 끝에서부터 거꾸로 쓴다. 카테고리는 앞에서부터 쓰므로
    기본 프로젝트(common)와 기본 카테고리가 같은 색이 되지 않는다.
    ID는 바뀌지 않으므로 같은 프로젝트는 어느 화면·어느 주에서도 같은 색이다.
    """
    color = project.color or ""
    if services.is_valid_color(color):
        return color
    count = len(CHART_PALETTE)
    return CHART_PALETTE[(count - 1 - (project.id - 1)) % count]


def _palette_color(position: int) -> str:
    return CHART_PALETTE[position % len(CHART_PALETTE)]


def category_color_map(
    configured: Sequence[str], stored: Mapping[str, str], present: Sequence[str] = ()
) -> dict[str, str]:
    """카테고리 색: 저장한 색이 있으면 그 색, 없으면 설정 순서 위치의 팔레트 색.

    대상은 설정 카테고리 전부와 present 중 설정에 없는 key다. 설정에 없는 key는
    설정 개수 뒤의 위치를 이름 순으로 받는다. 같은 카테고리는 주마다 같은 색이다.
    """
    position = {key: i for i, key in enumerate(configured)}
    unknown = sorted(key for key in present if key not in position)
    position.update({key: len(configured) + i for i, key in enumerate(unknown)})
    return {key: stored.get(key) or _palette_color(i) for key, i in position.items()}


@dataclass(frozen=True)
class LogRowView:
    id: int
    day: str  # '10-01 (목)'
    full_day: str  # '2026-10-01 (목)' (삭제 확인 문구)
    iso_date: str  # '2026-10-01' (편집 행의 date 입력)
    project: str
    project_color: str  # '#rrggbb' (색 점)
    category: str
    duration: str
    note: str
    task: str  # '#42' 또는 '-'
    version: str  # worklog_version
    confirm: str  # 삭제 확인 창 문구 (연도를 붙인 기록 한 줄)


@dataclass(frozen=True)
class TimerView:
    scope: str  # 'payment/design'
    note: str
    task: str | None  # '#43'
    started: str  # 오늘이면 '09:30', 아니면 '09-30 (수) 22:10'
    elapsed: str  # '1h 25m'
    version: str  # timer_version
    cancel_confirm: str  # 취소 확인 창 문구


@dataclass(frozen=True)
class TimerStartValues:
    """타이머 시작 요청(빠른 기록 폼의 `타이머 시작`) 입력값. 문자열 그대로, 비면 '자동'."""

    note: str = ""
    project: str = ""
    category: str = ""
    task: str = ""


def content_version(*fields: object) -> str:
    """화면이 본 값이 그사이 바뀌었는지 가리는 값: 필드를 구분자로 이어 sha256한 앞 16자.

    None은 빈 문자열로 본다. 구분자 덕분에 ('a', 'bc')와 ('ab', 'c')는 다른 값이다.
    """
    text = _FIELD_SEPARATOR.join("" if value is None else str(value) for value in fields)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_VERSION_LENGTH]


def worklog_version(log: WorkLog) -> str:
    """화면이 본 기록이 그사이 바뀌었는지 가리는 값.

    id·date·minutes·note·project_id·category·task_id·created_at로 만든다.
    SQLite가 id를 다시 쓰는 경우에도 created_at이 달라서 다른 기록으로 가려진다.
    """
    return content_version(
        log.id,
        log.date.isoformat(),
        log.minutes,
        log.note,
        log.project_id,
        log.category,
        log.task_id,
        log.created_at.isoformat(),
    )


def timer_version(timer: ActiveTimer) -> str:
    """화면이 본 타이머가 그사이 바뀌었는지 가리는 값(취소 요청이 확인한다).

    시작 시각은 UTC로 맞춰 쓴다. 같은 순간이 현지 시간대(시작 응답)와 UTC(DB에서 읽은 값)로
    다르게 적혀도 같은 버전이어야 한다.
    """
    return content_version(
        timer.started_at.astimezone(UTC).isoformat(),
        timer.project_id,
        timer.category,
        timer.note,
        timer.task_id,
    )


def record_text(log: WorkLog, *, with_date: bool) -> str:
    """기록 한 줄: '#128 payment/dev 2h — 메모'. with_date면 날짜가 id 뒤에 붙는다.

    예: '#128 2026-10-01 (목) payment/dev 2h — 메모'
    """
    date_part = f"{full_day(log.date)} " if with_date else ""
    scope = f"{log.project.slug}/{log.category}"
    return f"#{log.id} {date_part}{scope} {format_duration(log.minutes)} — {log.note}"


def log_row(log: WorkLog) -> LogRowView:
    return LogRowView(
        id=log.id,
        day=day_label(log.date),
        full_day=full_day(log.date),
        iso_date=log.date.isoformat(),
        project=log.project.slug,
        project_color=project_color(log.project),
        category=log.category,
        duration=format_duration(log.minutes),
        note=log.note,
        task=f"#{log.task_id}" if log.task_id is not None else NO_TASK,
        version=worklog_version(log),
        confirm=DELETE_CONFIRM.format(record=record_text(log, with_date=True)),
    )


def timer_view(timer: ActiveTimer, now: datetime) -> TimerView:
    """진행 중인 타이머. DB의 시각은 UTC라서 now의 시간대로 바꿔 표기한다."""
    scope = f"{timer.project.slug}/{timer.category}"
    started = clock_label(timer.started_at.astimezone(now.tzinfo), now.date())
    elapsed = format_duration(services.elapsed_minutes(timer.started_at, now))
    return TimerView(
        scope=scope,
        note=timer.note,
        task=f"#{timer.task_id}" if timer.task_id is not None else None,
        started=started,
        elapsed=elapsed,
        version=timer_version(timer),
        cancel_confirm=CANCEL_CONFIRM.format(
            scope=scope, note=timer.note, started=started, elapsed=elapsed
        ),
    )


@dataclass(frozen=True)
class Choice:
    value: str
    label: str


@dataclass(frozen=True)
class QuickFormOptions:
    projects: tuple[Choice, ...]  # 보관하지 않은 프로젝트: Choice('payment', 'payment — 결제 서버')
    categories: tuple[Choice, ...]  # 설정 순서: Choice('dev', 'dev — 개발')
    # 보관하지 않은 프로젝트의 todo·doing: Choice('42', '#42 payment · 제목')
    tasks: tuple[Choice, ...]


@dataclass(frozen=True)
class QuickFormValues:
    """빠른 기록 폼에 채워 둘 값. 모두 입력 문자열 그대로이고 비어 있으면 '자동'이다."""

    duration: str = ""
    note: str = ""
    project: str = ""
    category: str = ""
    task: str = ""


def quick_form_options(s: Session, cfg: Config) -> QuickFormOptions:
    """빠른 기록 폼의 선택지. 세션 안에서 불러 일반 값으로 바꾼다."""
    projects = tuple(Choice(p.slug, f"{p.slug} — {p.name}") for p in services.list_projects(s))
    categories = tuple(Choice(key, f"{key} — {label}") for key, label in cfg.categories.items())
    open_tasks = services.list_tasks(s, statuses=(TaskStatus.TODO, TaskStatus.DOING))
    tasks = tuple(Choice(str(t.id), f"#{t.id} {t.project.slug} · {t.title}") for t in open_tasks)
    return QuickFormOptions(projects=projects, categories=categories, tasks=tasks)


@dataclass(frozen=True)
class LogFilter:
    """기록 페이지 필터. 입력 문자열 그대로이고 비어 있으면 week는 이번 주, 나머지는 전체다."""

    week: str = ""
    project: str = ""
    category: str = ""


@dataclass(frozen=True)
class LogFilterView:
    week: str  # 주차 입력 칸 값 ('2026-W40'. 잘못 입력한 주차는 입력 그대로)
    prev_url: str | None  # 이전 주 링크 (표시할 주를 알 수 없거나 범위 밖이면 None)
    next_url: str | None
    project: str  # 선택된 프로젝트 slug ('' = 전체)
    category: str
    projects: tuple[Choice, ...]
    categories: tuple[Choice, ...]


@dataclass(frozen=True)
class LogTableView:
    heading: str  # week_heading
    rows: tuple[LogRowView, ...]
    total: str  # format_duration
    count: int
    message: str = ""  # 결과 줄
    is_error: bool = False


@dataclass(frozen=True)
class LogEditValues:
    """편집 행에 채워 둘 값. 모두 입력 문자열 그대로다(오류 뒤에도 입력을 유지한다)."""

    duration: str
    note: str
    log_date: str
    log_project: str
    log_category: str
    log_task: str
    version: str


@dataclass(frozen=True)
class LogEditView:
    id: int
    values: LogEditValues
    projects: tuple[Choice, ...]
    categories: tuple[Choice, ...]
    tasks: tuple[Choice, ...]
    error: str = ""


def week_url(week: Week, values: LogFilter) -> str:
    """주 이동 링크. 현재 프로젝트·카테고리 필터를 유지한다."""
    query = {"week": week.label}
    if values.project:
        query["project"] = values.project
    if values.category:
        query["category"] = values.category
    return f"{LOGS_PATH}?{urlencode(query)}"


def _neighbor_url(week: Week, values: LogFilter, *, forward: bool) -> str | None:
    try:
        return week_url(week.next() if forward else week.prev(), values)
    except InvalidInputError:  # 지원 범위의 끝
        return None


def project_choices(s: Session, *, keep: str = "", archived: bool = True) -> tuple[Choice, ...]:
    """프로젝트 선택지. archived=False면 보관 프로젝트는 keep(현재 값)만 남긴다."""
    return tuple(
        Choice(p.slug, f"{p.slug} — {p.name}{ARCHIVED_MARK if p.archived else ''}")
        for p in services.list_projects(s, include_archived=True)
        if archived or not p.archived or p.slug == keep
    )


def category_choices(cfg: Config, current: str) -> tuple[Choice, ...]:
    """설정 카테고리에 현재 값(설정에서 빠졌을 수 있다)을 더한다."""
    choices = [Choice(key, f"{key} — {label}") for key, label in cfg.categories.items()]
    if current and current not in cfg.categories:
        choices.append(Choice(current, current))
    return tuple(choices)


def log_filter_view(s: Session, cfg: Config, week: Week | None, values: LogFilter) -> LogFilterView:
    """week가 None이면(주차 입력이 틀림) 입력을 그대로 두고 이동 링크는 뺀다."""
    return LogFilterView(
        week=values.week if week is None else week.label,
        prev_url=None if week is None else _neighbor_url(week, values, forward=False),
        next_url=None if week is None else _neighbor_url(week, values, forward=True),
        project=values.project,
        category=values.category,
        projects=project_choices(s),
        categories=category_choices(cfg, values.category),
    )


def log_table_view(
    week: Week, logs: Sequence[WorkLog], *, message: str = "", is_error: bool = False
) -> LogTableView:
    return LogTableView(
        heading=week_heading(week),
        rows=tuple(log_row(log) for log in logs),
        total=format_duration(sum(log.minutes for log in logs)),
        count=len(logs),
        message=message,
        is_error=is_error,
    )


def edit_values(log: WorkLog) -> LogEditValues:
    """기록의 현재 값으로 채운 편집 폼 값."""
    return LogEditValues(
        duration=format_duration(log.minutes),
        note=log.note,
        log_date=log.date.isoformat(),
        log_project=log.project.slug,
        log_category=log.category,
        log_task="" if log.task_id is None else str(log.task_id),
        version=worklog_version(log),
    )


def log_edit_view(
    s: Session, cfg: Config, log: WorkLog, values: LogEditValues, *, error: str = ""
) -> LogEditView:
    """편집 행. 선택지는 지금 고를 수 있는 값에 기록의 현재 값을 더한 것이다."""
    open_tasks = services.list_tasks(s, statuses=(TaskStatus.TODO, TaskStatus.DOING))
    tasks = [Choice(str(t.id), f"#{t.id} {t.project.slug} · {t.title}") for t in open_tasks]
    if log.task is not None and all(choice.value != str(log.task.id) for choice in tasks):
        current = log.task
        label = f"#{current.id} {current.project.slug} · {current.title}"
        tasks.append(Choice(str(current.id), label))
    return LogEditView(
        id=log.id,
        values=values,
        projects=project_choices(s, keep=log.project.slug, archived=False),
        categories=category_choices(cfg, log.category),
        tasks=tuple(tasks),
        error=error,
    )
