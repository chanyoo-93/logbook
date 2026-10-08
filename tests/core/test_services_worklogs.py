"""logbook.core.services.worklogs 단위 테스트."""

from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.config import DEFAULT_CATEGORIES
from logbook.core.db import session_scope
from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.models import Task, TaskStatus, WorkLog
from logbook.core.services import worklogs
from logbook.core.weeks import Week

# 2026-W40: 월요일 9/28 ~ 일요일 10/4 (sunday 모드는 일요일 9/27 ~ 토요일 10/3)
MON = date(2026, 9, 28)
THU = date(2026, 10, 1)
SUN = date(2026, 10, 4)


def _seed_projects(s: Session) -> None:
    services.ensure_common_project(s)
    services.create_project(s, "payment", "결제 서버")
    services.create_project(s, "search", "검색")


@pytest.fixture
def seeded(session: Session) -> Session:
    """common, payment, search 프로젝트가 있는 세션."""
    _seed_projects(session)
    return session


def _add(s: Session, **overrides: Any) -> WorkLog:
    params: dict[str, Any] = {"minutes": 60, "note": "작업", "category": "dev", "today": THU}
    return services.add_worklog(s, **{**params, **overrides})


def _make_task(
    s: Session,
    project_slug: str = "payment",
    *,
    category: str | None = "dev",
    status: TaskStatus = TaskStatus.TODO,
) -> Task:
    # 태스크 서비스는 Task 1-8에서 생기므로 모델로 직접 만든다.
    task = Task(
        project=services.get_project(s, project_slug),
        title="결제 재시도",
        category=category,
        status=status,
    )
    s.add(task)
    s.flush()
    return task


def _count_logs(s: Session) -> int:
    return s.scalars(select(func.count()).select_from(WorkLog)).one()


def _dates(logs: list[WorkLog]) -> list[date]:
    return [log.date for log in logs]


# --- add_worklog ---


def test_add_stores_fields_and_returns_id(seeded: Session, today: date) -> None:
    log = services.add_worklog(
        seeded,
        minutes=120,
        note="결제 재시도 로직 구현",
        project_slug="payment",
        category="dev",
        today=today,
    )

    assert log.id is not None
    assert log.project.slug == "payment"
    assert log.category == "dev"
    assert log.date == today
    assert log.minutes == 120
    assert log.note == "결제 재시도 로직 구현"
    assert log.task is None
    assert log.created_at.tzinfo is not None
    stored = seeded.get(WorkLog, log.id)
    assert stored is not None
    assert (stored.project_id, stored.minutes) == (log.project.id, 120)


def test_add_explicit_work_date_wins_over_today(seeded: Session, today: date) -> None:
    log = _add(seeded, work_date=date(2026, 9, 30), today=today)

    assert log.date == date(2026, 9, 30)


def test_add_without_today_uses_system_date(seeded: Session) -> None:
    before = date.today()
    log = _add(seeded, today=None)

    assert log.date in {before, date.today()}


def test_add_without_project_uses_default_project(seeded: Session) -> None:
    log = _add(seeded)

    assert log.project.slug == "common"


def test_add_uses_given_default_project(seeded: Session) -> None:
    log = _add(seeded, default_project="search")

    assert log.project.slug == "search"


def test_add_unknown_project_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        _add(seeded, project_slug="paymnt")

    assert str(excinfo.value) == (
        "프로젝트를 찾을 수 없습니다: 'paymnt'. 'lb project list'로 확인하거나, "
        "새 프로젝트라면 'lb project add paymnt <이름>'으로 만드세요."
    )
    assert _count_logs(seeded) == 0


def test_add_missing_default_project_raises_not_found(session: Session) -> None:
    with pytest.raises(NotFoundError, match="'common'"):
        _add(session)


def test_add_to_archived_project_raises(seeded: Session) -> None:
    services.archive_project(seeded, "search")

    with pytest.raises(InvalidInputError) as excinfo:
        _add(seeded, project_slug="search")

    assert str(excinfo.value) == (
        "보관된 프로젝트에는 새 기록이나 태스크를 추가할 수 없습니다: 'search'. "
        "다른 프로젝트를 지정하세요."
    )
    assert _count_logs(seeded) == 0


def test_add_with_task_uses_task_project_and_category(seeded: Session) -> None:
    task = _make_task(seeded, "payment", category="review")

    log = services.add_worklog(seeded, minutes=30, note="리뷰 반영", task_id=task.id, today=THU)

    assert log.task is task
    assert log.project.slug == "payment"
    assert log.category == "review"


def test_add_explicit_category_overrides_task_category(seeded: Session) -> None:
    task = _make_task(seeded, "payment", category="review")

    log = _add(seeded, task_id=task.id, category="dev")

    assert log.category == "dev"
    assert log.project.slug == "payment"


def test_add_explicit_project_matching_task_is_accepted(seeded: Session) -> None:
    task = _make_task(seeded, "payment")

    log = _add(seeded, task_id=task.id, project_slug="payment")

    assert log.project.slug == "payment"
    assert log.task is task


def test_add_explicit_project_different_from_task_raises(seeded: Session) -> None:
    task = _make_task(seeded, "payment")

    with pytest.raises(InvalidInputError) as excinfo:
        _add(seeded, task_id=task.id, project_slug="search")

    assert str(excinfo.value) == (
        f"'payment' 프로젝트에 속한 태스크입니다 (#{task.id}). "
        "프로젝트를 빼거나 같은 프로젝트(-p payment)를 지정하세요."
    )
    assert _count_logs(seeded) == 0


def test_add_unknown_task_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        _add(seeded, task_id=999)

    assert str(excinfo.value) == "태스크를 찾을 수 없습니다: #999. 'lb task list'로 확인하세요."


def test_add_task_in_archived_project_raises(seeded: Session) -> None:
    task = _make_task(seeded, "search")
    services.archive_project(seeded, "search")

    with pytest.raises(InvalidInputError, match="보관된 프로젝트"):
        _add(seeded, task_id=task.id)


@pytest.mark.parametrize("status", [TaskStatus.DONE, TaskStatus.DROPPED])
def test_add_to_finished_task_is_allowed(seeded: Session, status: TaskStatus) -> None:
    task = _make_task(seeded, status=status)

    log = _add(seeded, task_id=task.id)

    assert log.task is task


def test_add_without_category_raises(seeded: Session) -> None:
    with pytest.raises(InvalidInputError, match="카테고리를 지정하세요") as excinfo:
        _add(seeded, category=None)

    assert "-c dev" in str(excinfo.value)
    assert _count_logs(seeded) == 0


def test_add_task_without_category_and_no_category_raises(seeded: Session) -> None:
    task = _make_task(seeded, category=None)

    with pytest.raises(InvalidInputError, match="카테고리를 지정하세요"):
        _add(seeded, task_id=task.id, category=None)


@pytest.mark.parametrize("category", ["", "   "])
def test_add_blank_category_raises(seeded: Session, category: str) -> None:
    with pytest.raises(InvalidInputError, match="카테고리를 지정하세요"):
        _add(seeded, category=category)


def test_add_category_not_allowed_raises_with_sorted_list(seeded: Session) -> None:
    with pytest.raises(InvalidInputError) as excinfo:
        _add(seeded, category="xyz", allowed_categories={"dev", "admin"})

    assert str(excinfo.value) == (
        "쓸 수 없는 카테고리입니다: 'xyz'. 사용할 수 있는 카테고리: admin, dev"
    )
    assert _count_logs(seeded) == 0


def test_add_category_allowed_by_config_mapping(seeded: Session) -> None:
    log = _add(seeded, category="meeting", allowed_categories=DEFAULT_CATEGORIES)

    assert log.category == "meeting"


def test_add_task_category_is_checked_against_allowed(seeded: Session) -> None:
    task = _make_task(seeded, category="legacy")

    with pytest.raises(InvalidInputError, match="'legacy'"):
        _add(seeded, task_id=task.id, category=None, allowed_categories={"dev"})


def test_add_without_allowed_categories_skips_check(seeded: Session) -> None:
    log = _add(seeded, category="xyz", allowed_categories=None)

    assert log.category == "xyz"


def test_add_stores_stripped_category(seeded: Session) -> None:
    log = _add(seeded, category=" dev ", allowed_categories=None)

    assert log.category == "dev"
    assert services.list_worklogs(seeded, category="dev") == [log]


@pytest.mark.parametrize("minutes", [1, 1440])
def test_add_minutes_bounds_accepted(seeded: Session, minutes: int) -> None:
    assert _add(seeded, minutes=minutes).minutes == minutes


@pytest.mark.parametrize(
    ("minutes", "message"),
    [
        (0, "소요 시간은 1분 이상이어야 합니다."),
        (-30, "소요 시간은 1분 이상이어야 합니다."),
        (1441, "소요 시간은 24시간 이하여야 합니다."),
    ],
)
def test_add_minutes_out_of_range_raises(seeded: Session, minutes: int, message: str) -> None:
    with pytest.raises(InvalidInputError) as excinfo:
        _add(seeded, minutes=minutes)

    assert str(excinfo.value).startswith(message)
    assert _count_logs(seeded) == 0


@pytest.mark.parametrize("minutes", [True, False, 1.5, "60"])
def test_add_non_int_minutes_raises(seeded: Session, minutes: object) -> None:
    with pytest.raises(InvalidInputError, match="소요 시간"):
        _add(seeded, minutes=minutes)

    assert _count_logs(seeded) == 0


INVALID_WORK_DATES = [datetime(2026, 10, 1, 9, 30, tzinfo=UTC), "2026-10-01"]


@pytest.mark.parametrize("work_date", INVALID_WORK_DATES)
def test_add_invalid_work_date_raises(seeded: Session, work_date: object) -> None:
    with pytest.raises(InvalidInputError, match="작업 날짜는 날짜로 입력하세요"):
        _add(seeded, work_date=work_date)

    assert _count_logs(seeded) == 0


@pytest.mark.parametrize("note", ["", "   ", "\t\n"])
def test_add_blank_note_raises(seeded: Session, note: str) -> None:
    with pytest.raises(InvalidInputError) as excinfo:
        _add(seeded, note=note)

    assert str(excinfo.value) == "메모를 입력하세요. 무엇을 했는지 한 줄로 적어 주세요."
    assert _count_logs(seeded) == 0


def test_add_stores_stripped_note(seeded: Session) -> None:
    log = _add(seeded, note="  결제 재시도 로직 구현 \n")

    assert log.note == "결제 재시도 로직 구현"


def test_add_result_is_readable_after_session_closes(engine: Engine) -> None:
    with session_scope(engine) as s:
        _seed_projects(s)
        task = _make_task(s, "payment")
        task_id = task.id
    with session_scope(engine) as s:
        log = _add(s, task_id=task_id)

    assert log.project.slug == "payment"
    assert log.task is not None
    assert log.task.id == task_id


# --- get_worklog / delete_worklog ---


def test_get_returns_log(seeded: Session) -> None:
    created = _add(seeded, note="회의록 정리")

    found = services.get_worklog(seeded, created.id)

    assert found.id == created.id
    assert found.note == "회의록 정리"


def test_get_missing_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        services.get_worklog(seeded, 128)

    assert str(excinfo.value) == "기록을 찾을 수 없습니다: #128. 'lb log'로 확인하세요."


def test_get_result_is_readable_after_session_closes(engine: Engine) -> None:
    with session_scope(engine) as s:
        _seed_projects(s)
        task = _make_task(s, "payment")
        log_id = _add(s, task_id=task.id).id
    with session_scope(engine) as s:
        log = services.get_worklog(s, log_id)

    assert log.project.slug == "payment"
    assert log.task is not None
    assert log.task.title == "결제 재시도"
    assert log.task.project.slug == "payment"


def test_delete_then_get_raises_not_found(seeded: Session) -> None:
    log = _add(seeded)
    log_id = log.id

    services.delete_worklog(seeded, log_id)

    with pytest.raises(NotFoundError, match=f"기록을 찾을 수 없습니다: #{log_id}"):
        services.get_worklog(seeded, log_id)
    assert _count_logs(seeded) == 0


def test_delete_missing_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError, match="'lb log'"):
        services.delete_worklog(seeded, 128)


def test_delete_keeps_other_logs(seeded: Session) -> None:
    first = _add(seeded)
    second = _add(seeded)

    services.delete_worklog(seeded, first.id)

    assert [log.id for log in services.list_worklogs(seeded)] == [second.id]


# --- list_worklogs ---


def test_list_without_filters_orders_by_date_then_id(seeded: Session) -> None:
    late = _add(seeded, work_date=date(2026, 10, 2))
    early_a = _add(seeded, work_date=date(2026, 9, 29))
    early_b = _add(seeded, work_date=date(2026, 9, 29))
    middle = _add(seeded, work_date=THU)

    result = services.list_worklogs(seeded)

    assert [log.id for log in result] == [early_a.id, early_b.id, middle.id, late.id]


def test_list_empty_returns_empty_list(seeded: Session) -> None:
    assert services.list_worklogs(seeded) == []


def test_list_week_includes_boundaries_and_excludes_outside(seeded: Session) -> None:
    for day in [date(2026, 9, 27), MON, THU, SUN, date(2026, 10, 5)]:
        _add(seeded, work_date=day)

    result = services.list_worklogs(seeded, week=Week(2026, 40))

    assert _dates(result) == [MON, THU, SUN]


def test_list_sunday_mode_week_includes_preceding_sunday(seeded: Session) -> None:
    for day in [date(2026, 9, 26), date(2026, 9, 27), date(2026, 10, 3), SUN]:
        _add(seeded, work_date=day)

    result = services.list_worklogs(seeded, week=Week(2026, 40, "sunday"))

    assert _dates(result) == [date(2026, 9, 27), date(2026, 10, 3)]


def test_list_on_filters_exact_date(seeded: Session) -> None:
    for day in [date(2026, 9, 30), THU, THU, date(2026, 10, 2)]:
        _add(seeded, work_date=day)

    result = services.list_worklogs(seeded, on=THU)

    assert _dates(result) == [THU, THU]


def test_list_project_filter(seeded: Session) -> None:
    _add(seeded, project_slug="payment")
    _add(seeded, project_slug="search")
    _add(seeded)

    result = services.list_worklogs(seeded, project_slug="payment")

    assert [log.project.slug for log in result] == ["payment"]


def test_list_category_filter(seeded: Session) -> None:
    _add(seeded, category="dev")
    _add(seeded, category="meeting")
    _add(seeded, category="dev")

    result = services.list_worklogs(seeded, category="meeting")

    assert [log.category for log in result] == ["meeting"]


def test_list_filters_combine_with_and(seeded: Session) -> None:
    match = _add(seeded, project_slug="payment", category="dev", work_date=THU)
    _add(seeded, project_slug="payment", category="dev", work_date=date(2026, 10, 5))
    _add(seeded, project_slug="payment", category="review", work_date=THU)
    _add(seeded, project_slug="search", category="dev", work_date=THU)

    result = services.list_worklogs(
        seeded, week=Week(2026, 40), on=THU, project_slug="payment", category="dev"
    )

    assert [log.id for log in result] == [match.id]


def test_list_unknown_project_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError, match="'paymnt'"):
        services.list_worklogs(seeded, project_slug="paymnt")


def test_list_archived_project_is_allowed(seeded: Session) -> None:
    log = _add(seeded, project_slug="search")
    services.archive_project(seeded, "search")

    result = services.list_worklogs(seeded, project_slug="search")

    assert [item.id for item in result] == [log.id]


def test_list_results_are_readable_after_session_closes(engine: Engine) -> None:
    with session_scope(engine) as s:
        _seed_projects(s)
        task = _make_task(s, "payment")
        _add(s, task_id=task.id)
        _add(s, project_slug="search")
    with session_scope(engine) as s:
        result = services.list_worklogs(s)

    assert [log.project.slug for log in result] == ["payment", "search"]
    assert result[0].task is not None
    assert result[0].task.title == "결제 재시도"
    assert result[0].task.project.slug == "payment"
    assert result[1].task is None


# --- update_worklog ---


def test_update_minutes_only_keeps_other_fields(seeded: Session) -> None:
    task = _make_task(seeded, "payment", category="review")
    log = _add(seeded, task_id=task.id, category=None, note="리뷰", work_date=date(2026, 9, 30))

    updated = services.update_worklog(seeded, log.id, minutes=90)

    assert updated.id == log.id
    assert updated.minutes == 90
    assert (updated.note, updated.category, updated.date) == ("리뷰", "review", date(2026, 9, 30))
    assert updated.project.slug == "payment"
    assert updated.task is task
    stored = seeded.scalar(select(WorkLog.minutes).where(WorkLog.id == log.id))
    assert stored == 90


def test_update_note_category_and_date(seeded: Session) -> None:
    log = _add(seeded)

    updated = services.update_worklog(
        seeded, log.id, note="  회의록 정리 ", category="docs", work_date=date(2026, 9, 29)
    )

    assert (updated.note, updated.category, updated.date) == (
        "회의록 정리",
        "docs",
        date(2026, 9, 29),
    )


def test_update_missing_raises_not_found(seeded: Session) -> None:
    with pytest.raises(NotFoundError, match="기록을 찾을 수 없습니다: #128"):
        services.update_worklog(seeded, 128, minutes=90)


@pytest.mark.parametrize("minutes", [0, 1441, True])
def test_update_invalid_minutes_raises(seeded: Session, minutes: int) -> None:
    log = _add(seeded, minutes=60)

    with pytest.raises(InvalidInputError, match="소요 시간"):
        services.update_worklog(seeded, log.id, minutes=minutes)

    assert log.minutes == 60


def test_update_blank_note_raises(seeded: Session) -> None:
    log = _add(seeded)

    with pytest.raises(InvalidInputError, match="메모를 입력하세요"):
        services.update_worklog(seeded, log.id, note="  ")


@pytest.mark.parametrize("work_date", INVALID_WORK_DATES)
def test_update_invalid_work_date_raises(seeded: Session, work_date: object) -> None:
    log = _add(seeded, note="작업", work_date=THU)

    with pytest.raises(InvalidInputError, match="작업 날짜는 날짜로 입력하세요"):
        services.update_worklog(seeded, log.id, note="새 메모", work_date=work_date)

    assert (log.note, log.date) == ("작업", THU)
    seeded.expire_all()
    stored = seeded.execute(select(WorkLog.note, WorkLog.date).where(WorkLog.id == log.id)).one()
    assert tuple(stored) == ("작업", THU)


def test_update_category_not_allowed_raises(seeded: Session) -> None:
    log = _add(seeded, category="dev")

    with pytest.raises(InvalidInputError, match="사용할 수 있는 카테고리: dev, review"):
        services.update_worklog(
            seeded, log.id, category="xyz", allowed_categories={"review", "dev"}
        )

    assert log.category == "dev"


def test_update_unchanged_category_skips_allowed_check(seeded: Session) -> None:
    log = _add(seeded, category="legacy")

    updated = services.update_worklog(
        seeded, log.id, minutes=30, category="legacy", allowed_categories={"dev"}
    )

    assert (updated.category, updated.minutes) == ("legacy", 30)


def test_update_stores_stripped_category(seeded: Session) -> None:
    log = _add(seeded, category="dev")

    updated = services.update_worklog(seeded, log.id, category=" docs ")

    assert updated.category == "docs"


def test_update_project_to_active_project(seeded: Session) -> None:
    log = _add(seeded, project_slug="payment")

    updated = services.update_worklog(seeded, log.id, project_slug="search")

    assert updated.project.slug == "search"
    assert seeded.scalar(select(WorkLog.project_id).where(WorkLog.id == log.id)) == (
        services.get_project(seeded, "search").id
    )


def test_update_project_to_archived_project_raises(seeded: Session) -> None:
    log = _add(seeded, project_slug="payment", minutes=60)
    services.archive_project(seeded, "search")

    with pytest.raises(InvalidInputError) as excinfo:
        services.update_worklog(seeded, log.id, minutes=90, project_slug="search")

    assert str(excinfo.value) == (
        "보관된 프로젝트로는 기록을 옮길 수 없습니다: 'search'. 다른 프로젝트를 지정하세요."
    )
    assert log.minutes == 60
    assert log.project.slug == "payment"


def test_update_unknown_project_raises_not_found(seeded: Session) -> None:
    log = _add(seeded)

    with pytest.raises(NotFoundError, match="'paymnt'"):
        services.update_worklog(seeded, log.id, project_slug="paymnt")


def test_update_minutes_of_log_in_archived_project_is_allowed(seeded: Session) -> None:
    log = _add(seeded, project_slug="search")
    services.archive_project(seeded, "search")

    updated = services.update_worklog(
        seeded, log.id, minutes=45, note="정리", project_slug="search"
    )

    assert (updated.minutes, updated.note, updated.project.slug) == (45, "정리", "search")


def test_update_task_moves_project(seeded: Session) -> None:
    log = _add(seeded)
    task = _make_task(seeded, "search")

    updated = services.update_worklog(seeded, log.id, task_id=task.id)

    assert updated.task is task
    assert updated.project.slug == "search"
    assert updated.category == "dev"
    stored = seeded.execute(
        select(WorkLog.project_id, WorkLog.task_id).where(WorkLog.id == log.id)
    ).one()
    assert tuple(stored) == (task.project_id, task.id)


def test_update_task_in_archived_project_raises(seeded: Session) -> None:
    log = _add(seeded)
    task = _make_task(seeded, "search")
    services.archive_project(seeded, "search")

    with pytest.raises(InvalidInputError) as excinfo:
        services.update_worklog(seeded, log.id, task_id=task.id)

    assert str(excinfo.value) == (
        "보관된 프로젝트로는 기록을 옮길 수 없습니다: 'search'. 다른 프로젝트를 지정하세요."
    )
    assert log.task is None
    assert log.project.slug == "common"


def test_update_unknown_task_raises_not_found(seeded: Session) -> None:
    log = _add(seeded)

    with pytest.raises(NotFoundError, match="태스크를 찾을 수 없습니다: #999"):
        services.update_worklog(seeded, log.id, task_id=999)


def test_update_explicit_project_inconsistent_with_new_task_raises(seeded: Session) -> None:
    log = _add(seeded)
    task = _make_task(seeded, "payment")

    with pytest.raises(InvalidInputError) as excinfo:
        services.update_worklog(seeded, log.id, task_id=task.id, project_slug="search")

    assert str(excinfo.value) == (
        f"'payment' 프로젝트에 속한 태스크입니다 (#{task.id}). "
        "프로젝트를 빼거나 같은 프로젝트(-p payment)를 지정하세요."
    )
    assert log.task is None


def test_update_project_away_from_linked_task_raises(seeded: Session) -> None:
    task = _make_task(seeded, "payment")
    log = _add(seeded, task_id=task.id)

    with pytest.raises(InvalidInputError) as excinfo:
        services.update_worklog(seeded, log.id, project_slug="search")

    assert str(excinfo.value) == (
        f"연결된 태스크(#{task.id})와 다른 프로젝트로 옮길 수 없습니다 "
        "(태스크의 프로젝트: 'payment'). "
        "태스크 연결을 해제하거나 같은 프로젝트를 지정하세요."
    )
    assert log.project.slug == "payment"
    assert log.task is task


def test_update_clear_task_unlinks_and_keeps_other_fields(seeded: Session) -> None:
    task = _make_task(seeded, "payment", category="review")
    log = _add(seeded, task_id=task.id, minutes=45, note="리뷰 반영", work_date=MON)

    updated = services.update_worklog(seeded, log.id, clear_task=True)

    assert updated.task is None
    assert (updated.project.slug, updated.category, updated.minutes) == ("payment", "dev", 45)
    assert (updated.note, updated.date) == ("리뷰 반영", MON)
    assert seeded.scalar(select(WorkLog.task_id).where(WorkLog.id == log.id)) is None


def test_update_clear_task_with_project_moves_project(seeded: Session) -> None:
    task = _make_task(seeded, "payment")
    log = _add(seeded, task_id=task.id)

    updated = services.update_worklog(seeded, log.id, clear_task=True, project_slug="search")

    assert updated.task is None
    assert updated.project.slug == "search"


def test_update_clear_task_without_link_is_noop(seeded: Session) -> None:
    log = _add(seeded, project_slug="payment", minutes=60)

    updated = services.update_worklog(seeded, log.id, clear_task=True)

    assert updated.task is None
    assert (updated.project.slug, updated.minutes, updated.note) == ("payment", 60, "작업")


def test_update_clear_task_with_task_id_raises_before_any_change(seeded: Session) -> None:
    task = _make_task(seeded, "payment")
    other = _make_task(seeded, "payment")
    log = _add(seeded, task_id=task.id, minutes=60)

    with pytest.raises(InvalidInputError) as excinfo:
        services.update_worklog(seeded, log.id, minutes=90, clear_task=True, task_id=other.id)

    assert str(excinfo.value) == (
        "태스크를 지정하면서 연결을 해제할 수는 없습니다. 둘 중 하나만 지정하세요."
    )
    assert log.task is task
    assert log.minutes == 60


def test_update_clear_task_conflict_is_checked_before_loading_log(seeded: Session) -> None:
    with pytest.raises(InvalidInputError) as excinfo:
        services.update_worklog(seeded, 999, task_id=1, clear_task=True)

    assert str(excinfo.value) == (
        "태스크를 지정하면서 연결을 해제할 수는 없습니다. 둘 중 하나만 지정하세요."
    )


def test_update_clear_task_to_archived_project_raises(seeded: Session) -> None:
    task = _make_task(seeded, "payment")
    log = _add(seeded, task_id=task.id)
    services.archive_project(seeded, "search")

    with pytest.raises(InvalidInputError) as excinfo:
        services.update_worklog(seeded, log.id, clear_task=True, project_slug="search")

    assert str(excinfo.value) == (
        "보관된 프로젝트로는 기록을 옮길 수 없습니다: 'search'. 다른 프로젝트를 지정하세요."
    )
    assert log.task is task
    assert log.project.slug == "payment"


def test_update_result_is_readable_after_session_closes(engine: Engine) -> None:
    with session_scope(engine) as s:
        _seed_projects(s)
        log_id = _add(s).id
        task_id = _make_task(s, "search").id
    with session_scope(engine) as s:
        updated = services.update_worklog(s, log_id, task_id=task_id)

    assert updated.project.slug == "search"
    assert updated.task is not None
    assert updated.task.id == task_id


# --- day_total_minutes ---


def test_day_total_sums_all_projects_on_that_date(seeded: Session) -> None:
    _add(seeded, minutes=30, project_slug="payment", work_date=THU)
    _add(seeded, minutes=45, project_slug="search", work_date=THU)
    _add(seeded, minutes=90, work_date=THU)
    _add(seeded, minutes=600, work_date=date(2026, 9, 30))
    _add(seeded, minutes=600, work_date=date(2026, 10, 2))
    services.archive_project(seeded, "search")

    assert services.day_total_minutes(seeded, THU) == 165


def test_day_total_without_logs_is_zero(seeded: Session) -> None:
    _add(seeded, work_date=date(2026, 9, 30))

    assert services.day_total_minutes(seeded, THU) == 0


# --- 패키지 재노출 ---


def test_package_reexports_worklog_services() -> None:
    assert services.add_worklog is worklogs.add_worklog
    assert services.get_worklog is worklogs.get_worklog
    assert services.list_worklogs is worklogs.list_worklogs
    assert services.update_worklog is worklogs.update_worklog
    assert services.delete_worklog is worklogs.delete_worklog
    assert services.day_total_minutes is worklogs.day_total_minutes
    assert set(services.__all__) >= {
        "add_worklog",
        "day_total_minutes",
        "delete_worklog",
        "get_worklog",
        "list_worklogs",
        "update_worklog",
    }
