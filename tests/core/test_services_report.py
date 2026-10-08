"""logbook.core.services.report(weekly_report)와 core.report 데이터 클래스 단위 테스트."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.errors import InvalidInputError
from logbook.core.models import Task, TaskStatus
from logbook.core.report import (
    MatrixRow,
    PlanGroup,
    PlanItem,
    ProjectSection,
    ReportData,
    TaskLine,
    percent_text,
)
from logbook.core.weeks import Week

FIXED = Week(2026, 40)  # 2026-09-28 ~ 2026-10-04
KST = timezone(timedelta(hours=9))
WED = date(2026, 9, 30)  # FIXED 안의 날짜
LAST_WEEK_DAY = date(2026, 9, 23)  # W39
# W40 안, KST 정오 부근이라 날짜 경계와 멀다.
DONE_IN_WEEK = datetime(2026, 9, 30, 3, 0, tzinfo=UTC)
LABELS = {
    "dev": "개발",
    "review": "코드리뷰",
    "meeting": "회의",
    "admin": "행정/기타",
    "ops": "운영/배포/장애",
}
TITLE_FORMAT = "주간업무보고 ({start} ~ {end})"


@pytest.fixture
def seeded(session: Session) -> Session:
    services.ensure_common_project(session)
    services.create_project(session, "payment", "결제 서버")
    services.create_project(session, "admin", "관리자")
    return session


def _report(s: Session, week: Week = FIXED, **overrides: Any) -> ReportData:
    params: dict[str, Any] = {
        "tz": KST,
        "title_format": TITLE_FORMAT,
        "author": "홍길동",
        "category_labels": LABELS,
    }
    return services.weekly_report(s, week, **{**params, **overrides})


def _log(
    s: Session,
    minutes: int,
    category: str = "dev",
    *,
    project: str = "payment",
    task: Task | None = None,
    day: date = WED,
) -> None:
    services.add_worklog(
        s,
        minutes=minutes,
        note="작업",
        project_slug=project,
        category=category,
        work_date=day,
        task_id=task.id if task is not None else None,
    )


def _task(s: Session, title: str = "작업", project: str = "payment", **overrides: Any) -> Task:
    return services.create_task(s, title=title, project_slug=project, **overrides)


def _finish(s: Session, task: Task, done_at: datetime = DONE_IN_WEEK) -> Task:
    """set_task_status는 실제 현재 시각을 쓰므로 고정 완료 시각을 직접 넣는다."""
    task.status = TaskStatus.DONE
    task.done_at = done_at
    s.flush()
    return task


def _plan_pairs(data: ReportData) -> list[tuple[str, list[tuple[int, bool]]]]:
    return [(g.project, [(i.task_id, i.carried) for i in g.items]) for g in data.plan]


# --- percent_text ---


@pytest.mark.parametrize(
    ("part", "total", "expected"),
    [(0, 100, "-"), (1, 0, "-"), (0, 0, "-"), (1, 8, "13%"), (1, 2, "50%"), (35, 35, "100%")],
)
def test_percent_text_rounds_half_up(part: int, total: int, expected: str) -> None:
    assert percent_text(part, total) == expected


# --- 빈 주와 제목 ---


def test_empty_week(seeded: Session) -> None:
    data = _report(seeded)

    assert data.total == "0m"
    assert data.log_count == 0
    assert data.done_task_count == 0
    assert data.categories == ()
    assert data.matrix == ()
    assert data.sections == ()
    assert data.plan == ()
    assert data.week_label == "2026-W40"
    assert (data.start, data.end) == ("2026-09-28", "2026-10-04")
    assert data.author == "홍길동"
    assert data.title == "주간업무보고 (2026-09-28 ~ 2026-10-04)"


def test_title_uses_custom_format(seeded: Session) -> None:
    data = _report(seeded, title_format="보고 {start}~{end}")

    assert data.title == "보고 2026-09-28~2026-10-04"


@pytest.mark.parametrize(
    "title_format",
    [
        "보고 {foo}",
        "{0}",
        "보고 {",
        "}",
        "보고 ({start} ~ {end)",
        "{start:%m/%d}",
        "{start!x}",
        "{start.year}",
        "{start[a]}",
    ],
)
def test_invalid_title_format_is_input_error(seeded: Session, title_format: str) -> None:
    with pytest.raises(InvalidInputError) as caught:
        _report(seeded, title_format=title_format)

    assert str(caught.value) == (
        f"보고서 제목 형식이 올바르지 않습니다: '{title_format}'. "
        "사용할 수 있는 이름: {start}, {end}"
    )


# --- 기본 템플릿 예시와 같은 구성 ---


def test_example_report_from_services(seeded: Session) -> None:
    retry = _task(seeded, "결제 재시도 로직 구현", estimate_minutes=360)
    design = _task(seeded, "환불 API 설계", estimate_minutes=240, planned_week=FIXED)
    perms = _task(seeded, "권한 정리", "admin", estimate_minutes=600, planned_week=FIXED)
    refund = _task(seeded, "환불 API 구현", estimate_minutes=480, planned_week=FIXED.next())
    services.set_task_status(seeded, design.id, TaskStatus.DOING)
    services.set_task_status(seeded, perms.id, TaskStatus.DOING)
    _finish(seeded, retry)
    _log(seeded, 480, "dev", task=retry)
    _log(seeded, 180, "dev", task=design)
    _log(seeded, 180, "dev")
    _log(seeded, 180, "review")
    _log(seeded, 120, "meeting")
    _log(seeded, 360, "dev", project="admin", task=perms)
    _log(seeded, 60, "review", project="admin")
    _log(seeded, 60, "meeting", project="admin")
    _log(seeded, 300, "meeting", project="common")
    _log(seeded, 180, "admin", project="common")

    data = _report(seeded)

    assert data.total == "35h"
    assert data.log_count == 10
    assert data.done_task_count == 1
    assert data.categories == ("개발", "코드리뷰", "회의", "행정/기타")
    assert data.matrix == (
        MatrixRow("payment", ("14h", "3h", "2h", "-"), "19h", "54%"),
        MatrixRow("admin", ("6h", "1h", "1h", "-"), "8h", "23%"),
        MatrixRow("common", ("-", "-", "5h", "3h"), "8h", "23%"),
    )
    assert data.sections == (
        ProjectSection(
            "payment",
            "19h",
            (
                TaskLine("완료", "결제 재시도 로직 구현", retry.id, "8h", "6h", "실제"),
                TaskLine("진행", "환불 API 설계", design.id, "3h", "4h", "누적"),
            ),
            (("개발", "3h"), ("코드리뷰", "3h"), ("회의", "2h")),
        ),
        ProjectSection(
            "admin",
            "8h",
            (TaskLine("진행", "권한 정리", perms.id, "6h", "10h", "누적"),),
            (("코드리뷰", "1h"), ("회의", "1h")),
        ),
        ProjectSection("common", "8h", (), (("회의", "5h"), ("행정/기타", "3h"))),
    )
    assert data.plan == (
        PlanGroup("admin", "10h", (PlanItem("권한 정리", perms.id, "10h", True),)),
        PlanGroup(
            "payment",
            "12h",
            (
                PlanItem("환불 API 구현", refund.id, "8h", False),
                PlanItem("환불 API 설계", design.id, "4h", True),
            ),
        ),
    )


# --- 태스크 줄 ---


def test_task_actual_is_cumulative_including_earlier_weeks(seeded: Session) -> None:
    task = _task(seeded, estimate_minutes=600)
    _log(seeded, 60, task=task)
    _log(seeded, 30, task=task, day=date(2026, 10, 1))
    _log(seeded, 120, task=task, day=LAST_WEEK_DAY)

    lines = _report(seeded).sections[0].tasks

    assert len(lines) == 1
    assert lines[0].actual == "3h 30m"
    assert lines[0].estimate == "10h"


def test_last_week_report_ignores_later_logs_and_completion(seeded: Session) -> None:
    task = _task(seeded, "환불 API 설계")
    _log(seeded, 120, task=task, day=LAST_WEEK_DAY)
    _log(seeded, 60, task=task, day=WED)
    _finish(seeded, task)

    data = _report(seeded, FIXED.prev())

    line = data.sections[0].tasks[0]
    assert (line.status, line.actual, line.actual_label) == ("진행", "2h", "누적")
    assert data.done_task_count == 0


def test_done_task_lines_sort_before_open_ones_by_id(seeded: Session) -> None:
    tasks = [_task(seeded, f"작업{n}") for n in range(1, 6)]
    services.set_task_status(seeded, tasks[0].id, TaskStatus.DOING)
    _finish(seeded, tasks[1])
    services.set_task_status(seeded, tasks[2].id, TaskStatus.DROPPED)
    _finish(seeded, tasks[4])
    for task in tasks:
        _log(seeded, 60, task=task)

    lines = _report(seeded).sections[0].tasks

    assert [(t.task_id, t.status) for t in lines] == [
        (2, "완료"),
        (5, "완료"),
        (1, "진행"),
        (4, "할 일"),
        (3, "중단"),
    ]


def test_done_task_without_estimate(seeded: Session) -> None:
    task = _finish(seeded, _task(seeded))
    _log(seeded, 60, task=task)

    line = _report(seeded).sections[0].tasks[0]

    assert line.actual_label == "실제"
    assert line.estimate is None


def test_task_done_in_earlier_week_with_logs_this_week_stays_done(seeded: Session) -> None:
    task = _finish(seeded, _task(seeded), datetime(2026, 9, 23, 3, 0, tzinfo=UTC))
    _log(seeded, 60, task=task)

    data = _report(seeded)

    line = data.sections[0].tasks[0]
    assert (line.status, line.actual_label) == ("완료", "실제")
    assert data.done_task_count == 0


def test_week_boundary_includes_sunday_and_excludes_next_monday(seeded: Session) -> None:
    _log(seeded, 60, day=FIXED.end)
    _log(seeded, 30, day=FIXED.end + timedelta(days=1))

    data = _report(seeded)

    assert (data.total, data.log_count) == ("1h", 1)


def test_titles_and_labels_are_single_line(seeded: Session) -> None:
    task = _task(seeded, "첫 줄\n# 둘째\t끝")
    _log(seeded, 60, "dev", task=task)
    _log(seeded, 60, "review")

    data = _report(seeded, category_labels={"dev": "개 발\n하기", "review": "코드 리뷰"})

    assert data.sections[0].tasks[0].title == "첫 줄 # 둘째 끝"
    assert data.categories == ("개 발 하기", "코드 리뷰")
    assert data.sections[0].others == (("코드 리뷰", "1h"),)


# --- 기타 줄 ---


def test_others_sorted_by_minutes_descending(seeded: Session) -> None:
    _log(seeded, 30, "ops")
    _log(seeded, 180, "review")

    assert _report(seeded).sections[0].others == (("코드리뷰", "3h"), ("운영/배포/장애", "30m"))


def test_others_merge_same_label_and_break_ties_by_column_order(seeded: Session) -> None:
    labels = {"dev": "개발", "dev2": "개발"}
    for category, minutes in (("dev", 30), ("dev2", 30), ("zeta", 60), ("alpha", 60)):
        _log(seeded, minutes, category)

    data = _report(seeded, category_labels=labels)

    assert data.sections[0].others == (("개발", "1h"), ("alpha", "1h"), ("zeta", "1h"))


def test_unregistered_category_uses_key(seeded: Session) -> None:
    _log(seeded, 60, "unknown")

    data = _report(seeded)

    assert data.categories == ("unknown",)
    assert data.sections[0].others == (("unknown", "1h"),)


def test_linked_logs_are_not_in_others(seeded: Session) -> None:
    _log(seeded, 60, task=_task(seeded))

    assert _report(seeded).sections[0].others == ()


# --- 완료 태스크 수 ---


def test_done_count_uses_local_date(seeded: Session) -> None:
    # UTC로는 전 주 일요일 23:30, KST로는 월요일 08:30
    _finish(seeded, _task(seeded), datetime(2026, 9, 27, 23, 30, tzinfo=UTC))

    assert _report(seeded).done_task_count == 1
    assert _report(seeded, tz=UTC).done_task_count == 0


def test_task_done_this_week_without_logs_counts_but_has_no_section(seeded: Session) -> None:
    task = _task(seeded)
    _log(seeded, 120, task=task, day=LAST_WEEK_DAY)
    _finish(seeded, task)

    data = _report(seeded)

    assert data.done_task_count == 1
    assert data.matrix == ()
    assert data.sections == ()


def test_done_count_includes_archived_projects(seeded: Session) -> None:
    _finish(seeded, _task(seeded))
    services.archive_project(seeded, "payment")

    assert _report(seeded).done_task_count == 1


def test_done_after_week_end_is_reported_as_open(seeded: Session) -> None:
    task = _finish(seeded, _task(seeded), datetime(2026, 10, 4, 15, 30, tzinfo=UTC))  # KST 월요일
    _log(seeded, 60, task=task)

    line = _report(seeded).sections[0].tasks[0]

    assert (line.status, line.actual_label) == ("진행", "누적")


# --- 다음 주 계획 ---


def test_plan_includes_next_week_open_and_carried_tasks(seeded: Session) -> None:
    next_todo = _task(seeded, "다음 할 일", planned_week=FIXED.next())
    _finish(seeded, _task(seeded, "다음 완료", planned_week=FIXED.next()))
    carried = _task(seeded, "이월", planned_week=FIXED)
    services.set_task_status(seeded, carried.id, TaskStatus.DOING)
    _finish(seeded, _task(seeded, "이번 완료", planned_week=FIXED))
    _task(seeded, "보관됨", "admin", planned_week=FIXED.next())
    services.archive_project(seeded, "admin")

    data = _report(seeded)

    assert _plan_pairs(data) == [("payment", [(next_todo.id, False), (carried.id, True)])]


def test_plan_groups_by_slug_with_next_week_before_carried(seeded: Session) -> None:
    t3 = _task(seeded, "p-W40-doing", planned_week=FIXED)
    services.set_task_status(seeded, t3.id, TaskStatus.DOING)
    t4 = _task(seeded, "p-W41-todo-b", planned_week=FIXED.next())
    t5 = _task(seeded, "p-W41-doing", planned_week=FIXED.next())
    services.set_task_status(seeded, t5.id, TaskStatus.DOING)
    t6 = _task(seeded, "a-W40-todo", "admin", planned_week=FIXED)

    data = _report(seeded)

    assert _plan_pairs(data) == [
        ("admin", [(t6.id, True)]),
        ("payment", [(t4.id, False), (t5.id, False), (t3.id, True)]),
    ]


def test_plan_estimate_total(seeded: Session) -> None:
    _task(seeded, "a", planned_week=FIXED.next(), estimate_minutes=240)
    _task(seeded, "b", planned_week=FIXED.next(), estimate_minutes=480)
    _task(seeded, "c", "admin", planned_week=FIXED.next())

    totals = {group.project: group.estimate_total for group in _report(seeded).plan}

    assert totals == {"payment": "12h", "admin": "0m"}


def test_plan_item_estimate_and_title(seeded: Session) -> None:
    task = _task(seeded, "환불\nAPI", planned_week=FIXED.next(), estimate_minutes=90)
    bare = _task(seeded, "예상 없음", planned_week=FIXED.next())

    items = _report(seeded).plan[0].items

    assert items == (
        PlanItem("환불 API", task.id, "1h 30m", False),
        PlanItem("예상 없음", bare.id, None, False),
    )


# --- 쿼리 수 ---


def _record_queries(engine: Engine, action: Callable[[], object]) -> int:
    statements: list[str] = []

    def record(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        action()
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return len(statements)


def test_query_count_does_not_grow_with_log_count(seeded: Session, engine: Engine) -> None:
    first = _task(seeded, "첫 태스크", estimate_minutes=60, planned_week=FIXED.next())
    _log(seeded, 30, task=first)
    seeded.expire_all()
    single = _record_queries(engine, lambda: _report(seeded))

    tasks = [_task(seeded, f"작업{n}", ["payment", "admin"][n % 2]) for n in range(10)]
    for n in range(119):
        task = tasks[n % len(tasks)] if n % 3 else None
        project = task.project.slug if task is not None else "common"
        _log(seeded, 10 + n % 5, "dev" if n % 2 else "review", project=project, task=task)
        if n % 7 == 0:
            _task(seeded, f"계획{n}", planned_week=FIXED.next() if n % 2 else FIXED)
    seeded.expire_all()
    many = _record_queries(engine, lambda: _report(seeded))

    assert many == single
