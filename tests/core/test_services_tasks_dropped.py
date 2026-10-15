"""중단 시각(dropped_at), dropped_tasks_in_week, 설명 줄바꿈 정규화."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.errors import NotFoundError
from logbook.core.models import Task, TaskStatus
from logbook.core.weeks import Week

KST = timezone(timedelta(hours=9))
W40 = Week(2026, 40)
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def seeded(session: Session) -> Session:
    services.ensure_common_project(session)
    services.create_project(session, "payment", "결제 서버")
    services.create_project(session, "search", "검색")
    return session


def _create(s: Session, **overrides: Any) -> Task:
    params: dict[str, Any] = {"title": "환불 API 설계", "project_slug": "payment"}
    return services.create_task(s, **{**params, **overrides})


def _dropped(s: Session, dropped_at: datetime | None, project: str = "payment") -> Task:
    task = Task(
        project=services.get_project(s, project),
        title="중단 태스크",
        status=TaskStatus.DROPPED,
        dropped_at=dropped_at,
    )
    s.add(task)
    s.flush()
    return task


def _ids(tasks: list[Task]) -> list[int]:
    return [task.id for task in tasks]


# --- set_task_status ---


def test_new_task_has_no_dropped_at(seeded: Session) -> None:
    assert _create(seeded).dropped_at is None


def test_set_dropped_records_dropped_at(seeded: Session) -> None:
    task = _create(seeded)

    services.set_task_status(seeded, task.id, TaskStatus.DROPPED)

    assert task.dropped_at is not None
    assert task.dropped_at.tzinfo is not None


def test_set_dropped_then_todo_clears_dropped_at(seeded: Session) -> None:
    task = _create(seeded)
    services.set_task_status(seeded, task.id, TaskStatus.DROPPED)

    services.set_task_status(seeded, task.id, TaskStatus.TODO)

    assert task.status is TaskStatus.TODO
    assert task.dropped_at is None


def test_set_dropped_twice_keeps_first_dropped_at(seeded: Session) -> None:
    task = _create(seeded)
    services.set_task_status(seeded, task.id, TaskStatus.DROPPED)
    task.dropped_at = LONG_AGO
    seeded.flush()

    services.set_task_status(seeded, task.id, TaskStatus.DROPPED)

    assert task.dropped_at == LONG_AGO


def test_set_dropped_fills_missing_dropped_at(seeded: Session) -> None:
    task = _dropped(seeded, None)

    services.set_task_status(seeded, task.id, TaskStatus.DROPPED)

    assert task.dropped_at is not None


def test_done_to_dropped_clears_done_at_and_records_dropped_at(seeded: Session) -> None:
    task = _create(seeded)
    services.set_task_status(seeded, task.id, TaskStatus.DONE)

    services.set_task_status(seeded, task.id, TaskStatus.DROPPED)

    assert task.done_at is None
    assert task.dropped_at is not None


def test_dropped_to_done_clears_dropped_at_and_records_done_at(seeded: Session) -> None:
    task = _create(seeded)
    services.set_task_status(seeded, task.id, TaskStatus.DROPPED)

    services.set_task_status(seeded, task.id, TaskStatus.DONE)

    assert task.dropped_at is None
    assert task.done_at is not None


# --- dropped_tasks_in_week ---


def test_dropped_tasks_in_week_lists_week_dropped_latest_first(seeded: Session) -> None:
    early = _dropped(seeded, datetime(2026, 9, 29, 3, tzinfo=UTC))
    late = _dropped(seeded, datetime(2026, 10, 3, 3, tzinfo=UTC))
    _dropped(seeded, datetime(2026, 9, 21, 3, tzinfo=UTC))  # 앞 주
    _create(seeded)  # 중단이 아님
    services.archive_project(seeded, "search")
    _dropped(seeded, datetime(2026, 10, 1, 3, tzinfo=UTC), project="search")  # 보관 프로젝트

    tasks = services.dropped_tasks_in_week(seeded, W40, tz=UTC)

    assert _ids(tasks) == [late.id, early.id]


def test_dropped_tasks_in_week_same_time_orders_by_id(seeded: Session) -> None:
    at = datetime(2026, 9, 30, 3, tzinfo=UTC)
    first = _dropped(seeded, at)
    second = _dropped(seeded, at)

    assert _ids(services.dropped_tasks_in_week(seeded, W40, tz=UTC)) == [first.id, second.id]


def test_dropped_tasks_in_week_ignores_non_dropped_status_with_dropped_at(
    seeded: Session,
) -> None:
    task = _create(seeded)
    task.dropped_at = datetime(2026, 9, 30, 3, tzinfo=UTC)
    seeded.flush()

    assert services.dropped_tasks_in_week(seeded, W40, tz=UTC) == []


def test_dropped_tasks_in_week_project_slug_includes_archived(seeded: Session) -> None:
    services.archive_project(seeded, "search")
    task = _dropped(seeded, datetime(2026, 10, 1, 3, tzinfo=UTC), project="search")
    _dropped(seeded, datetime(2026, 10, 1, 3, tzinfo=UTC), project="payment")

    tasks = services.dropped_tasks_in_week(seeded, W40, tz=UTC, project_slug="search")

    assert _ids(tasks) == [task.id]


def test_dropped_tasks_in_week_unknown_project_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError):
        services.dropped_tasks_in_week(seeded, W40, tz=UTC, project_slug="nope")


def test_dropped_tasks_in_week_uses_local_date_of_tz(seeded: Session) -> None:
    task = _dropped(seeded, datetime(2026, 9, 27, 15, 30, tzinfo=UTC))  # KST로 월요일 00:30

    assert _ids(services.dropped_tasks_in_week(seeded, W40, tz=KST)) == [task.id]
    assert services.dropped_tasks_in_week(seeded, W40, tz=UTC) == []


def test_dropped_tasks_in_week_loads_project(seeded: Session) -> None:
    _dropped(seeded, datetime(2026, 9, 29, 3, tzinfo=UTC))
    seeded.expunge_all()

    tasks = services.dropped_tasks_in_week(seeded, W40, tz=UTC)
    seeded.expunge_all()

    assert tasks[0].project.slug == "payment"


def test_dropped_tasks_in_week_first_week_with_tz_ahead_of_utc_does_not_overflow(
    seeded: Session,
) -> None:
    _dropped(seeded, datetime(2026, 9, 30, 3, tzinfo=UTC))

    assert services.dropped_tasks_in_week(seeded, Week(1, 1), tz=KST) == []


# --- 설명 줄바꿈 ---


@pytest.mark.parametrize("raw", ["가\r\n나\r\n다", "가\r나\r다", "가\n나\n다"])
def test_create_normalizes_description_line_breaks_to_lf(seeded: Session, raw: str) -> None:
    task = _create(seeded, description=raw)

    assert task.description == "가\n나\n다"


def test_update_normalizes_description_and_resending_crlf_changes_nothing(
    seeded: Session,
) -> None:
    task = _create(seeded)

    services.update_task(seeded, task.id, description="가\r\n나")
    first = task.description
    services.update_task(seeded, task.id, description="가\r\n나")

    assert first == "가\n나"
    assert task.description == first


def test_blank_description_after_normalizing_becomes_none(seeded: Session) -> None:
    task = _create(seeded, description=" \r\n ")

    assert task.description is None
