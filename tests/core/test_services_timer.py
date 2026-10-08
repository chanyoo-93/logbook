"""logbook.core.services.timer 단위 테스트."""

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.duration import MAX_MINUTES
from logbook.core.errors import InvalidInputError, LogbookError, NotFoundError
from logbook.core.models import ActiveTimer, Task, TaskStatus, WorkLog

KST = timezone(timedelta(hours=9))
# 목요일 09:30 (KST)
T0 = datetime(2026, 10, 1, 9, 30, tzinfo=KST)

NO_TIMER_MESSAGE = "진행 중인 타이머가 없습니다. 'lb start \"메모\"'로 시작하세요."
TOO_SHORT_MESSAGE = "1분이 지나지 않아 기록하지 않았습니다. 버리려면 'lb cancel'을 실행하세요."
BLANK_EXTRA_MESSAGE = "덧붙일 메모가 비어 있습니다. 메모를 덧붙이지 않으려면 --note를 빼세요."


@pytest.fixture
def seeded(session: Session) -> Session:
    """common, payment, search 프로젝트가 있는 세션."""
    services.ensure_common_project(session)
    services.create_project(session, "payment", "결제 서버")
    services.create_project(session, "search", "검색")
    return session


def _start(s: Session, **overrides: Any) -> services.StartedTimer:
    params: dict[str, Any] = {
        "now": T0,
        "note": "설계",
        "project_slug": "payment",
        "category": "design",
    }
    return services.start_timer(s, **{**params, **overrides})


def _make_task(
    s: Session,
    project_slug: str = "payment",
    *,
    category: str | None = "design",
    status: TaskStatus = TaskStatus.TODO,
) -> Task:
    task = services.create_task(
        s, title="환불 API 설계", project_slug=project_slug, category=category
    )
    if status != TaskStatus.TODO:
        services.set_task_status(s, task.id, status)
    return task


def _count(s: Session, model: type[ActiveTimer] | type[WorkLog]) -> int:
    return s.scalars(select(func.count()).select_from(model)).one()


def _error_of(call: Any) -> LogbookError:
    with pytest.raises(LogbookError) as excinfo:
        call()
    return excinfo.value


# --- start_timer ---


def test_start_stores_timer(seeded: Session) -> None:
    started = _start(seeded)

    assert started.task_started is False
    seeded.expire_all()
    timer = seeded.get(ActiveTimer, 1)
    assert timer is not None
    assert _count(seeded, ActiveTimer) == 1
    assert timer.project.slug == "payment"
    assert timer.category == "design"
    assert timer.note == "설계"
    assert timer.task is None
    # UTC로 저장하고, 읽으면 같은 순간이다.
    assert timer.started_at == T0
    assert timer.started_at.tzinfo == UTC


def test_start_with_todo_task_uses_task_values_and_starts_task(seeded: Session) -> None:
    task = _make_task(seeded, "payment", category="design")

    started = services.start_timer(seeded, now=T0, note=None, task_id=task.id)

    assert started.task_started is True
    assert started.timer.note == "환불 API 설계"
    assert started.timer.category == "design"
    assert started.timer.project.slug == "payment"
    assert started.timer.task is task
    assert task.status == TaskStatus.DOING


def test_start_with_task_and_note_uses_note(seeded: Session) -> None:
    task = _make_task(seeded)

    started = services.start_timer(seeded, now=T0, note="  리뷰 반영 ", task_id=task.id)

    assert started.timer.note == "리뷰 반영"


@pytest.mark.parametrize("status", [TaskStatus.DOING, TaskStatus.DONE])
def test_start_with_non_todo_task_keeps_status(seeded: Session, status: TaskStatus) -> None:
    task = _make_task(seeded, status=status)

    started = services.start_timer(seeded, now=T0, note=None, task_id=task.id)

    assert started.task_started is False
    assert task.status == status


def test_start_without_project_uses_default_project(seeded: Session) -> None:
    started = services.start_timer(seeded, now=T0, note="회의", category="meeting")

    assert started.timer.project.slug == "common"


def test_start_uses_given_default_project(seeded: Session) -> None:
    started = services.start_timer(
        seeded, now=T0, note="회의", category="meeting", default_project="search"
    )

    assert started.timer.project.slug == "search"


def _add_kwargs(start_kwargs: dict[str, Any]) -> dict[str, Any]:
    params = {k: v for k, v in start_kwargs.items() if k != "now"}
    return {"minutes": 60, "today": date(2026, 10, 1), **params}


def _setup_archived(s: Session) -> dict[str, Any]:
    services.archive_project(s, "search")
    return {"note": "설계", "project_slug": "search", "category": "design"}


def _setup_unknown_project(s: Session) -> dict[str, Any]:
    return {"note": "설계", "project_slug": "paymnt", "category": "design"}


def _setup_no_category(s: Session) -> dict[str, Any]:
    return {"note": "설계", "project_slug": "payment"}


def _setup_disallowed_category(s: Session) -> dict[str, Any]:
    return {
        "note": "설계",
        "project_slug": "payment",
        "category": "xyz",
        "allowed_categories": {"dev", "design"},
    }


def _setup_blank_note(s: Session) -> dict[str, Any]:
    return {"note": "   ", "project_slug": "payment", "category": "design"}


def _setup_task_other_project(s: Session) -> dict[str, Any]:
    task = _make_task(s, "payment")
    return {"note": None, "task_id": task.id, "project_slug": "search"}


def _setup_task_archived_project(s: Session) -> dict[str, Any]:
    task = _make_task(s, "search")
    services.archive_project(s, "search")
    return {"note": None, "task_id": task.id}


def _setup_unknown_task(s: Session) -> dict[str, Any]:
    return {"note": None, "task_id": 999}


def _setup_task_disallowed_category(s: Session) -> dict[str, Any]:
    task = _make_task(s, "payment", category="legacy")
    return {"note": None, "task_id": task.id, "allowed_categories": {"dev"}}


@pytest.mark.parametrize(
    "setup",
    [
        _setup_archived,
        _setup_unknown_project,
        _setup_no_category,
        _setup_disallowed_category,
        _setup_blank_note,
        _setup_task_other_project,
        _setup_task_archived_project,
        _setup_unknown_task,
        _setup_task_disallowed_category,
    ],
)
def test_start_rejects_like_add_worklog(seeded: Session, setup: Any) -> None:
    kwargs = setup(seeded)
    # add_worklog의 note는 str이므로 None이면 생략한다 (태스크 제목은 add에 쓰이지 않음).
    add_kwargs = _add_kwargs({k: v for k, v in kwargs.items() if v is not None})
    add_kwargs.setdefault("note", "작업")
    expected = _error_of(lambda: services.add_worklog(seeded, **add_kwargs))

    actual = _error_of(lambda: services.start_timer(seeded, now=T0, **kwargs))

    assert type(actual) is type(expected)
    assert str(actual) == str(expected)
    assert _count(seeded, ActiveTimer) == 0


def test_start_rejection_keeps_todo_task(seeded: Session) -> None:
    task = _make_task(seeded, "payment")

    with pytest.raises(InvalidInputError):
        services.start_timer(seeded, now=T0, note=None, task_id=task.id, project_slug="search")

    assert task.status == TaskStatus.TODO


def test_start_when_timer_running_raises_and_keeps_timer(seeded: Session) -> None:
    _start(seeded)

    with pytest.raises(InvalidInputError) as excinfo:
        _start(seeded, now=T0 + timedelta(minutes=5), note="다른 일", category="dev")

    assert str(excinfo.value) == (
        "이미 진행 중인 타이머가 있습니다: payment/design '설계' (09:30 시작). "
        "'lb stop'으로 저장하거나 'lb cancel'로 버리세요."
    )
    timer = services.get_timer(seeded)
    assert timer is not None
    assert timer.note == "설계"
    assert _count(seeded, ActiveTimer) == 1


def test_start_when_yesterdays_timer_running_shows_date(seeded: Session) -> None:
    _start(seeded, now=datetime(2026, 9, 30, 22, 10, tzinfo=KST))

    with pytest.raises(InvalidInputError) as excinfo:
        _start(seeded)

    assert "(09-30 22:10 시작)" in str(excinfo.value)


def test_start_with_running_timer_does_not_start_task(seeded: Session) -> None:
    _start(seeded)
    task = _make_task(seeded)

    with pytest.raises(InvalidInputError):
        services.start_timer(seeded, now=T0, note=None, task_id=task.id)

    assert task.status == TaskStatus.TODO


def test_start_with_naive_now_raises_value_error(seeded: Session) -> None:
    with pytest.raises(ValueError) as excinfo:
        _start(seeded, now=datetime(2026, 10, 1, 9, 30))

    assert not isinstance(excinfo.value, LogbookError)
    assert _count(seeded, ActiveTimer) == 0


# --- elapsed_minutes ---


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(seconds=29), 0),
        (timedelta(seconds=30), 1),
        (timedelta(seconds=89), 1),
        (timedelta(seconds=90), 2),
        (timedelta(minutes=90), 90),
        (timedelta(minutes=-5), 0),
    ],
)
def test_elapsed_minutes(delta: timedelta, expected: int) -> None:
    assert services.elapsed_minutes(T0, T0 + delta) == expected


def test_elapsed_minutes_across_timezones() -> None:
    assert services.elapsed_minutes(T0.astimezone(UTC), T0 + timedelta(minutes=10)) == 10


# --- get_timer ---


def test_get_timer_without_timer_returns_none(seeded: Session) -> None:
    assert services.get_timer(seeded) is None


def test_get_timer_returns_timer_with_relations(seeded: Session) -> None:
    task = _make_task(seeded)
    services.start_timer(seeded, now=T0, note=None, task_id=task.id)
    seeded.commit()
    seeded.expire_all()

    timer = services.get_timer(seeded)
    seeded.expunge_all()

    assert timer is not None
    assert timer.project.slug == "payment"
    assert timer.task is not None
    assert timer.task.title == "환불 API 설계"
    assert timer.task.project.slug == "payment"


# --- stop_timer ---


def test_stop_saves_worklog_and_removes_timer(seeded: Session) -> None:
    _start(seeded)
    now = T0 + timedelta(hours=1, minutes=25)

    stopped = services.stop_timer(seeded, now=now)

    log = stopped.log
    assert stopped.elapsed_minutes == 85
    assert log.id is not None
    assert log.minutes == 85
    assert log.date == date(2026, 10, 1)
    assert log.started_at == T0
    assert log.ended_at == now
    assert log.project.slug == "payment"
    assert log.category == "design"
    assert log.note == "설계"
    assert log.task is None
    assert _count(seeded, ActiveTimer) == 0
    assert _count(seeded, WorkLog) == 1


def test_stop_keeps_task_link(seeded: Session) -> None:
    task = _make_task(seeded)
    services.start_timer(seeded, now=T0, note=None, task_id=task.id)

    stopped = services.stop_timer(seeded, now=T0 + timedelta(minutes=10))

    assert stopped.log.task is task


@pytest.mark.parametrize(
    ("delta", "round_to", "expected"),
    [
        (timedelta(hours=1, minutes=25), 15, 90),
        (timedelta(minutes=7), 15, 15),
        (timedelta(minutes=22, seconds=29), 15, 15),
        (timedelta(minutes=22, seconds=30), 15, 30),
        (timedelta(seconds=30), 15, 15),
        (timedelta(minutes=10), 1, 10),
        (timedelta(minutes=29), 60, 60),
        (timedelta(minutes=90), 60, 120),
        (timedelta(hours=23, minutes=50), 60, MAX_MINUTES),
    ],
)
def test_stop_round_to(seeded: Session, delta: timedelta, round_to: int, expected: int) -> None:
    _start(seeded)

    stopped = services.stop_timer(seeded, now=T0 + delta, round_to=round_to)

    assert stopped.log.minutes == expected
    assert stopped.elapsed_minutes == services.elapsed_minutes(T0, T0 + delta)


@pytest.mark.parametrize("round_to", [None, 15])
def test_stop_before_one_minute_raises_and_keeps_timer(
    seeded: Session, round_to: int | None
) -> None:
    _start(seeded)

    with pytest.raises(InvalidInputError) as excinfo:
        services.stop_timer(seeded, now=T0 + timedelta(seconds=20), round_to=round_to)

    assert str(excinfo.value) == TOO_SHORT_MESSAGE
    assert _count(seeded, ActiveTimer) == 1
    assert _count(seeded, WorkLog) == 0


def test_stop_over_24_hours_raises_and_keeps_timer(seeded: Session) -> None:
    _start(seeded)

    with pytest.raises(InvalidInputError) as excinfo:
        services.stop_timer(seeded, now=T0 + timedelta(hours=24, minutes=1))

    assert str(excinfo.value) == (
        "타이머가 24시간을 넘었습니다 (시작 10-01 09:30). "
        "'lb cancel'로 버린 뒤 'lb add'로 날짜별로 나눠 기록하세요."
    )
    assert _count(seeded, ActiveTimer) == 1
    assert _count(seeded, WorkLog) == 0


def test_stop_exactly_24_hours_is_allowed(seeded: Session) -> None:
    _start(seeded)

    stopped = services.stop_timer(seeded, now=T0 + timedelta(hours=24))

    assert stopped.log.minutes == MAX_MINUTES


def test_stop_round_up_over_24_hours_raises(seeded: Session) -> None:
    _start(seeded)

    # 경과 1430분은 상한 안이지만 50분 단위로 반올림하면 1450분이다.
    with pytest.raises(InvalidInputError, match="24시간을 넘었습니다"):
        services.stop_timer(seeded, now=T0 + timedelta(hours=23, minutes=50), round_to=50)

    assert _count(seeded, ActiveTimer) == 1


def test_stop_after_midnight_uses_start_date(seeded: Session) -> None:
    start = datetime(2026, 10, 1, 23, 50, tzinfo=KST)
    _start(seeded, now=start)

    stopped = services.stop_timer(seeded, now=datetime(2026, 10, 2, 0, 40, tzinfo=KST))

    assert stopped.log.date == date(2026, 10, 1)
    assert stopped.log.minutes == 50


def test_stop_date_uses_now_timezone(seeded: Session) -> None:
    # 시작 시각을 UTC로 주어도 기록 날짜는 now의 시간대(KST) 기준이다.
    start = datetime(2026, 9, 30, 15, 10, tzinfo=UTC)  # KST 10-01 00:10
    _start(seeded, now=start)

    stopped = services.stop_timer(seeded, now=datetime(2026, 10, 1, 1, 0, tzinfo=KST))

    assert stopped.log.date == date(2026, 10, 1)


def test_stop_appends_extra_note(seeded: Session) -> None:
    _start(seeded)

    stopped = services.stop_timer(
        seeded, now=T0 + timedelta(minutes=30), extra_note="  예외 케이스 정리 "
    )

    assert stopped.log.note == "설계 — 예외 케이스 정리"


@pytest.mark.parametrize("extra_note", ["", "   "])
def test_stop_blank_extra_note_raises_and_keeps_timer(seeded: Session, extra_note: str) -> None:
    _start(seeded)

    with pytest.raises(InvalidInputError) as excinfo:
        services.stop_timer(seeded, now=T0 + timedelta(minutes=30), extra_note=extra_note)

    assert str(excinfo.value) == BLANK_EXTRA_MESSAGE
    assert _count(seeded, ActiveTimer) == 1


@pytest.mark.parametrize("round_to", [0, 61, -15, True, 1.5, "15"])
def test_stop_invalid_round_to_raises_and_keeps_timer(seeded: Session, round_to: object) -> None:
    _start(seeded)

    with pytest.raises(InvalidInputError) as excinfo:
        services.stop_timer(seeded, now=T0 + timedelta(minutes=30), round_to=round_to)  # type: ignore[arg-type]

    assert str(excinfo.value) == f"반올림 단위는 1~60분 사이의 정수여야 합니다: {round_to!r}"
    assert _count(seeded, ActiveTimer) == 1


def test_stop_after_task_deleted_saves_without_task(seeded: Session) -> None:
    task = _make_task(seeded)
    services.start_timer(seeded, now=T0, note=None, task_id=task.id)
    seeded.execute(delete(Task).where(Task.id == task.id))
    # 실제로는 다른 세션(다른 명령)에서 stop하므로 캐시된 상태를 버린다.
    seeded.expire_all()

    stopped = services.stop_timer(seeded, now=T0 + timedelta(minutes=30))

    assert stopped.log.task is None
    assert stopped.log.note == "환불 API 설계"


def test_stop_after_archive_and_category_change_is_allowed(seeded: Session) -> None:
    _start(seeded, project_slug="search", allowed_categories={"design"})
    services.archive_project(seeded, "search")

    stopped = services.stop_timer(seeded, now=T0 + timedelta(minutes=30))

    assert stopped.log.project.slug == "search"
    assert stopped.log.category == "design"


def test_stop_without_timer_raises(seeded: Session) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        services.stop_timer(seeded, now=T0)

    assert str(excinfo.value) == NO_TIMER_MESSAGE


def test_stop_with_naive_now_raises_value_error(seeded: Session) -> None:
    _start(seeded)

    with pytest.raises(ValueError) as excinfo:
        services.stop_timer(seeded, now=datetime(2026, 10, 1, 10, 0))

    assert not isinstance(excinfo.value, LogbookError)
    assert _count(seeded, ActiveTimer) == 1


# --- cancel_timer ---


def test_cancel_removes_timer_and_returns_it(seeded: Session) -> None:
    task = _make_task(seeded)
    services.start_timer(seeded, now=T0, note=None, task_id=task.id)
    seeded.commit()
    seeded.expire_all()

    timer = services.cancel_timer(seeded)
    seeded.commit()
    seeded.expunge_all()

    assert timer.note == "환불 API 설계"
    assert timer.project.slug == "payment"
    assert timer.task is not None
    assert timer.task.id == task.id
    assert _count(seeded, ActiveTimer) == 0
    assert _count(seeded, WorkLog) == 0


def test_cancel_without_timer_raises(seeded: Session) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        services.cancel_timer(seeded)

    assert str(excinfo.value) == NO_TIMER_MESSAGE
