"""logbook.core.services.tasks 단위 테스트."""

from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.models import Task, TaskStatus
from logbook.core.weeks import Week

W40 = Week(2026, 40)
W41 = Week(2026, 41)
W42 = Week(2026, 42)
THU = date(2026, 10, 1)
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def seeded(session: Session) -> Session:
    """common, payment, search 프로젝트가 있는 세션."""
    services.ensure_common_project(session)
    services.create_project(session, "payment", "결제 서버")
    services.create_project(session, "search", "검색")
    return session


def _create(s: Session, **overrides: Any) -> Task:
    params: dict[str, Any] = {"title": "환불 API 설계", "project_slug": "payment"}
    return services.create_task(s, **{**params, **overrides})


def _ids(tasks: list[Task]) -> list[int]:
    return [task.id for task in tasks]


# --- create_task ---


def test_create_defaults_to_todo_and_stores_week_label(seeded: Session) -> None:
    task = services.create_task(
        seeded,
        title="  환불 API 설계  ",
        project_slug="payment",
        category="design",
        estimate_minutes=240,
        planned_week=W41,
        due_date=date(2026, 10, 9),
        external_ref=" #43 ",
        description="  부분 환불 포함  ",
    )

    assert task.id is not None
    assert task.status is TaskStatus.TODO
    assert task.title == "환불 API 설계"
    assert task.project.slug == "payment"
    assert task.category == "design"
    assert task.estimate_minutes == 240
    assert task.planned_week == "2026-W41"
    assert task.due_date == date(2026, 10, 9)
    assert task.external_ref == "#43"
    assert task.description == "부분 환불 포함"
    assert task.done_at is None
    assert task.created_at.tzinfo is not None


def test_create_optional_fields_default_to_none(seeded: Session) -> None:
    task = _create(seeded, external_ref="   ", description="")

    assert task.category is None
    assert task.estimate_minutes is None
    assert task.planned_week is None
    assert task.due_date is None
    assert task.external_ref is None
    assert task.description is None


def test_create_unknown_project_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError, match="'paymnt'"):
        _create(seeded, project_slug="paymnt")


def test_create_archived_project_rejected(seeded: Session) -> None:
    services.archive_project(seeded, "search")

    with pytest.raises(InvalidInputError, match="보관된 프로젝트"):
        _create(seeded, project_slug="search")


@pytest.mark.parametrize("title", ["", "   ", "\t\n"])
def test_create_blank_title_rejected(seeded: Session, title: str) -> None:
    with pytest.raises(InvalidInputError, match="제목"):
        _create(seeded, title=title)


@pytest.mark.parametrize("estimate", [0, -30, True, False, 1.5, "4h"])
def test_create_invalid_estimate_rejected(seeded: Session, estimate: object) -> None:
    with pytest.raises(InvalidInputError, match="예상 공수"):
        _create(seeded, estimate_minutes=estimate)


def test_create_estimate_has_no_upper_limit(seeded: Session) -> None:
    assert _create(seeded, estimate_minutes=3 * 1440).estimate_minutes == 3 * 1440


def test_create_category_checked_against_allowed(seeded: Session) -> None:
    with pytest.raises(InvalidInputError, match="사용할 수 있는 카테고리: design, dev"):
        _create(seeded, category="legacy", allowed_categories=["dev", "design"])


def test_create_blank_category_rejected(seeded: Session) -> None:
    with pytest.raises(InvalidInputError, match="카테고리를 지정하세요"):
        _create(seeded, category="  ")


def test_create_without_category_skips_allowed_check(seeded: Session) -> None:
    task = _create(seeded, allowed_categories=["dev"])

    assert task.category is None


def test_worklog_for_created_task_uses_task_project_and_category(seeded: Session) -> None:
    task = _create(seeded, category="design")

    log = services.add_worklog(seeded, minutes=90, note="API 초안", task_id=task.id, today=THU)

    assert log.task is task
    assert log.project.slug == "payment"
    assert log.category == "design"


INVALID_DUE_DATES = ["2026-10-09", datetime(2026, 10, 9, tzinfo=UTC), 20261009]
INVALID_WEEKS = ["2026-W41", "next", 41]


@pytest.mark.parametrize("due_date", INVALID_DUE_DATES)
def test_create_invalid_due_date_rejected(seeded: Session, due_date: object) -> None:
    with pytest.raises(InvalidInputError, match="마감일"):
        _create(seeded, due_date=due_date)


@pytest.mark.parametrize("week", INVALID_WEEKS)
def test_create_invalid_planned_week_rejected(seeded: Session, week: object) -> None:
    with pytest.raises(InvalidInputError, match="계획 주차"):
        _create(seeded, planned_week=week)


# --- get_task ---


def test_get_task_returns_task_with_project(seeded: Session) -> None:
    task_id = _create(seeded).id
    seeded.expunge_all()

    task = services.get_task(seeded, task_id)
    seeded.expunge_all()

    # 세션에서 떨어져도 project를 읽을 수 있어야 한다 (CLI는 세션을 닫고 출력한다).
    assert task.project.slug == "payment"


def test_get_task_unknown_id_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError, match="태스크 #999가 없습니다.*'lb task list'"):
        services.get_task(seeded, 999)


# --- list_tasks ---


def test_list_orders_by_week_then_id_with_null_weeks_last(seeded: Session) -> None:
    no_week = _create(seeded, title="언젠가")
    w42 = _create(seeded, title="다다음 주", planned_week=W42)
    w40_a = _create(seeded, title="이번 주 A", planned_week=W40)
    w41 = _create(seeded, title="다음 주", planned_week=W41)
    w40_b = _create(seeded, title="이번 주 B", planned_week=W40)

    tasks = services.list_tasks(seeded)

    assert _ids(tasks) == [w40_a.id, w40_b.id, w41.id, w42.id, no_week.id]


def test_list_filters_by_multiple_statuses(seeded: Session) -> None:
    todo = _create(seeded)
    doing = _create(seeded)
    done = _create(seeded)
    services.set_task_status(seeded, doing.id, TaskStatus.DOING)
    services.set_task_status(seeded, done.id, TaskStatus.DONE)

    tasks = services.list_tasks(seeded, statuses={TaskStatus.TODO, TaskStatus.DOING})

    assert _ids(tasks) == [todo.id, doing.id]


def test_list_empty_statuses_returns_empty(seeded: Session) -> None:
    _create(seeded)

    assert services.list_tasks(seeded, statuses=[]) == []


def test_list_filters_by_week(seeded: Session) -> None:
    _create(seeded, planned_week=W40)
    w41 = _create(seeded, planned_week=W41)
    _create(seeded)

    assert _ids(services.list_tasks(seeded, week=W41)) == [w41.id]


def test_list_filters_by_project(seeded: Session) -> None:
    payment = _create(seeded)
    _create(seeded, project_slug="search")

    tasks = services.list_tasks(seeded, project_slug="payment")

    assert _ids(tasks) == [payment.id]
    assert tasks[0].project.slug == "payment"


def test_list_combines_filters_with_and(seeded: Session) -> None:
    match = _create(seeded, planned_week=W41)
    _create(seeded, planned_week=W40)
    _create(seeded, project_slug="search", planned_week=W41)
    done = _create(seeded, planned_week=W41)
    services.set_task_status(seeded, done.id, TaskStatus.DONE)

    tasks = services.list_tasks(
        seeded, project_slug="payment", statuses=[TaskStatus.TODO], week=W41
    )

    assert _ids(tasks) == [match.id]


def test_list_unknown_project_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError, match="'paymnt'"):
        services.list_tasks(seeded, project_slug="paymnt")


def test_list_includes_archived_project_tasks(seeded: Session) -> None:
    task = _create(seeded, project_slug="search")
    services.archive_project(seeded, "search")

    assert _ids(services.list_tasks(seeded, project_slug="search")) == [task.id]


def test_list_loads_project_for_detached_use(seeded: Session) -> None:
    _create(seeded)
    seeded.expunge_all()

    tasks = services.list_tasks(seeded)
    seeded.expunge_all()

    assert tasks[0].project.slug == "payment"


def test_list_rejects_plain_string_statuses(seeded: Session) -> None:
    _create(seeded)

    with pytest.raises(TypeError, match="statuses"):
        services.list_tasks(seeded, statuses="todo")  # type: ignore[arg-type]


# --- update_task ---


def test_update_changes_planned_week(seeded: Session) -> None:
    task = _create(seeded, planned_week=W40)

    updated = services.update_task(seeded, task.id, planned_week=W41)

    assert updated.planned_week == "2026-W41"
    assert services.list_tasks(seeded, week=W41) == [updated]


def test_update_none_clears_nullable_fields(seeded: Session) -> None:
    task = _create(
        seeded,
        category="dev",
        estimate_minutes=60,
        planned_week=W41,
        due_date=date(2026, 10, 9),
        external_ref="#43",
        description="설명",
    )

    services.update_task(
        seeded,
        task.id,
        category=None,
        estimate_minutes=None,
        planned_week=None,
        due_date=None,
        external_ref=None,
        description=None,
    )

    assert task.category is None
    assert task.estimate_minutes is None
    assert task.planned_week is None
    assert task.due_date is None
    assert task.external_ref is None
    assert task.description is None


def test_update_sets_fields_with_create_rules(seeded: Session) -> None:
    task = _create(seeded)

    services.update_task(
        seeded,
        task.id,
        title="  부분 환불 API  ",
        category=" review ",
        estimate_minutes=90,
        due_date=date(2026, 10, 16),
        external_ref="  #44 ",
        description="   ",
    )

    assert task.title == "부분 환불 API"
    assert task.category == "review"
    assert task.estimate_minutes == 90
    assert task.due_date == date(2026, 10, 16)
    assert task.external_ref == "#44"
    assert task.description is None


def test_update_without_fields_keeps_values(seeded: Session) -> None:
    task = _create(seeded, category="dev", planned_week=W41)

    services.update_task(seeded, task.id)

    assert (task.title, task.category, task.planned_week) == ("환불 API 설계", "dev", "2026-W41")


def test_update_unknown_field_raises_type_error(seeded: Session) -> None:
    task = _create(seeded)

    with pytest.raises(TypeError, match="status"):
        services.update_task(seeded, task.id, title="새 제목", status=TaskStatus.DONE)

    assert task.title == "환불 API 설계"


@pytest.mark.parametrize("title", [None, "", "   "])
def test_update_blank_title_rejected(seeded: Session, title: str | None) -> None:
    task = _create(seeded)

    with pytest.raises(InvalidInputError, match="제목"):
        services.update_task(seeded, task.id, title=title)

    assert task.title == "환불 API 설계"


@pytest.mark.parametrize("estimate", [0, True])
def test_update_invalid_estimate_rejected(seeded: Session, estimate: object) -> None:
    task = _create(seeded, estimate_minutes=60)

    with pytest.raises(InvalidInputError, match="예상 공수"):
        services.update_task(seeded, task.id, estimate_minutes=estimate)

    assert task.estimate_minutes == 60


def test_update_invalid_value_leaves_other_fields_unchanged(seeded: Session) -> None:
    task = _create(seeded)

    with pytest.raises(InvalidInputError):
        services.update_task(seeded, task.id, title="새 제목", estimate_minutes=0)

    assert task.title == "환불 API 설계"


def test_update_category_checked_against_allowed(seeded: Session) -> None:
    task = _create(seeded)

    with pytest.raises(InvalidInputError, match="사용할 수 있는 카테고리: dev"):
        services.update_task(seeded, task.id, category="legacy", allowed_categories=["dev"])


def test_update_rechecks_unchanged_category_against_allowed(seeded: Session) -> None:
    # create_task와 같은 검증: 기존 값과 같아도 넘긴 카테고리는 allowed로 검사한다.
    task = _create(seeded, category="legacy")

    with pytest.raises(InvalidInputError, match="사용할 수 있는 카테고리: dev"):
        services.update_task(
            seeded, task.id, title="새 제목", category="legacy", allowed_categories=["dev"]
        )

    assert (task.title, task.category) == ("환불 API 설계", "legacy")


def test_update_without_category_keeps_category_outside_allowed(seeded: Session) -> None:
    # 카테고리를 넘기지 않으면 설정에서 빠진 카테고리를 가진 태스크도 고칠 수 있다.
    task = _create(seeded, category="legacy")

    services.update_task(seeded, task.id, title="새 제목", allowed_categories=["dev"])

    assert (task.title, task.category) == ("새 제목", "legacy")


@pytest.mark.parametrize("due_date", INVALID_DUE_DATES)
def test_update_invalid_due_date_rejected(seeded: Session, due_date: object) -> None:
    task = _create(seeded, due_date=date(2026, 10, 9))

    with pytest.raises(InvalidInputError, match="마감일"):
        services.update_task(seeded, task.id, due_date=due_date)

    assert task.due_date == date(2026, 10, 9)


@pytest.mark.parametrize("week", INVALID_WEEKS)
def test_update_invalid_planned_week_rejected(seeded: Session, week: object) -> None:
    task = _create(seeded, planned_week=W41)

    with pytest.raises(InvalidInputError, match="계획 주차"):
        services.update_task(seeded, task.id, planned_week=week)

    assert task.planned_week == "2026-W41"


def test_update_without_allowed_categories_accepts_any_category(seeded: Session) -> None:
    task = _create(seeded, category="dev")

    services.update_task(seeded, task.id, category="  anything  ")

    assert task.category == "anything"


def test_update_bumps_updated_at(seeded: Session) -> None:
    task = _create(seeded)
    task.updated_at = LONG_AGO
    seeded.flush()

    services.update_task(seeded, task.id, title="새 제목")

    assert task.updated_at > LONG_AGO


def test_update_unknown_task_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError, match="'lb task list'"):
        services.update_task(seeded, 999, title="새 제목")


# --- set_task_status ---


def test_set_done_sets_done_at(seeded: Session) -> None:
    task = _create(seeded)

    updated = services.set_task_status(seeded, task.id, TaskStatus.DONE)

    assert updated.status is TaskStatus.DONE
    assert updated.done_at is not None
    assert updated.done_at.tzinfo is not None


def test_set_done_then_doing_clears_done_at(seeded: Session) -> None:
    task = _create(seeded)
    services.set_task_status(seeded, task.id, TaskStatus.DONE)

    services.set_task_status(seeded, task.id, TaskStatus.DOING)

    assert task.status is TaskStatus.DOING
    assert task.done_at is None


def test_set_dropped_has_no_done_at(seeded: Session) -> None:
    task = _create(seeded)
    services.set_task_status(seeded, task.id, TaskStatus.DONE)

    services.set_task_status(seeded, task.id, TaskStatus.DROPPED)

    assert task.status is TaskStatus.DROPPED
    assert task.done_at is None


def test_set_done_twice_keeps_first_done_at(seeded: Session) -> None:
    task = _create(seeded)
    services.set_task_status(seeded, task.id, TaskStatus.DONE)
    task.done_at = LONG_AGO  # 첫 완료 시각을 구분할 수 있게 과거로 둔다.
    seeded.flush()

    services.set_task_status(seeded, task.id, TaskStatus.DONE)

    assert task.done_at == LONG_AGO


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (TaskStatus.TODO, TaskStatus.DOING),
        (TaskStatus.DONE, TaskStatus.DONE),
        (TaskStatus.TODO, TaskStatus.TODO),
    ],
)
def test_set_status_bumps_updated_at(
    seeded: Session, before: TaskStatus, after: TaskStatus
) -> None:
    task = _create(seeded)
    services.set_task_status(seeded, task.id, before)
    task.updated_at = LONG_AGO
    seeded.flush()

    services.set_task_status(seeded, task.id, after)

    assert task.updated_at > LONG_AGO


def test_set_status_persists(seeded: Session) -> None:
    task_id = _create(seeded).id
    services.set_task_status(seeded, task_id, TaskStatus.DONE)
    seeded.expunge_all()

    task = services.get_task(seeded, task_id)

    assert task.status is TaskStatus.DONE
    assert task.done_at is not None


def test_set_status_unknown_task_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError, match="태스크 #999가 없습니다"):
        services.set_task_status(seeded, 999, TaskStatus.DONE)


# --- task_actual_minutes ---


def test_actual_minutes_sums_linked_logs_only(seeded: Session) -> None:
    task = _create(seeded, category="dev")
    other = _create(seeded, category="dev")
    services.add_worklog(seeded, minutes=90, note="구현", task_id=task.id, today=THU)
    services.add_worklog(seeded, minutes=45, note="리뷰 반영", task_id=task.id, today=THU)
    services.add_worklog(seeded, minutes=30, note="다른 태스크", task_id=other.id, today=THU)
    services.add_worklog(
        seeded, minutes=60, note="연결 없음", project_slug="payment", category="dev", today=THU
    )

    assert services.task_actual_minutes(seeded, task.id) == 135


def test_actual_minutes_zero_without_logs(seeded: Session) -> None:
    task = _create(seeded)

    assert services.task_actual_minutes(seeded, task.id) == 0


def test_actual_minutes_unknown_task_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError, match="'lb task list'"):
        services.task_actual_minutes(seeded, 999)
