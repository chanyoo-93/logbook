"""cli.render: 시각 표기, 태스크·계획·타이머 줄과 표."""

import io
from datetime import date, datetime, timedelta, timezone

import pytest
from rich.console import Console
from rich.table import Table

from logbook.cli import console, render
from logbook.core.models import ActiveTimer, Project, Task, TaskStatus
from tests.cli.helpers import FIXED_NOW, assert_fits, tokens

KST = timezone(timedelta(hours=9))
TODAY = date(2026, 10, 1)


def make_task(
    task_id: int = 43,
    *,
    slug: str = "payment",
    title: str = "환불 API 설계",
    status: TaskStatus = TaskStatus.DOING,
    category: str | None = "design",
    estimate: int | None = 240,
    week: str | None = "2026-W42",
    ref: str | None = "#43",
    due: date | None = date(2026, 10, 15),
) -> Task:
    """세션 없이 만든(transient) 태스크. 표기 함수는 속성만 읽는다."""
    return Task(
        id=task_id,
        project=Project(slug=slug, name=slug),
        title=title,
        status=status,
        category=category,
        estimate_minutes=estimate,
        planned_week=week,
        external_ref=ref,
        due_date=due,
    )


def bare_task() -> Task:
    return make_task(
        44,
        slug="admin",
        title="권한 정리",
        category=None,
        estimate=None,
        week=None,
        ref=None,
        due=None,
    )


# 표 행 내용을 확인할 때 쓰는 넉넉한 폭 (제목이 접히지 않는다)
WIDE = 200
# 기본 두 태스크 표의 필요 폭: no_wrap 열의 가장 넓은 칸 + fold 열 min_width + 열 간격
TASK_TABLE_WIDTH = 2 + 5 + 8 + 8 + 10 + 4 + 6 + 8 + 6 + 2 * 8
PLAN_TABLE_WIDTH = 2 + 5 + 8 + 10 + 4 + 6 + 2 * 5


def render_table(table: Table, width: int = WIDE) -> str:
    """width 폭의 콘솔에 표를 그린 문자열."""
    buffer = io.StringIO()
    Console(file=buffer, width=width, color_system=None, legacy_windows=False).print(table)
    return buffer.getvalue()


# --- clock_label ---


def test_clock_label_today_shows_time_only() -> None:
    assert render.clock_label(FIXED_NOW, TODAY) == "09:30"


def test_clock_label_other_day_adds_date() -> None:
    moment = datetime(2026, 9, 30, 22, 10, tzinfo=KST)

    assert render.clock_label(moment, TODAY) == "09-30 (수) 22:10"


def test_clock_label_pads_single_digits() -> None:
    moment = datetime(2026, 10, 1, 7, 5, tzinfo=KST)

    assert render.clock_label(moment, TODAY) == "07:05"


# --- task_line / task_details ---


def test_task_line_with_category() -> None:
    assert render.task_line(make_task()).plain == "#43 payment/design 환불 API 설계"


def test_task_line_without_category() -> None:
    assert render.task_line(bare_task()).plain == "#44 admin 권한 정리"


def test_task_details_with_all_values() -> None:
    assert render.task_details(make_task()).plain == " (예상 4h · 2026-W42 · 참조 #43 · 마감 10-15)"


def test_task_details_without_values_is_empty() -> None:
    assert render.task_details(bare_task()).plain == ""


def test_task_details_keeps_markup_in_ref_literal() -> None:
    task = make_task(estimate=None, week=None, due=None, ref="[bold]x[/bold]")

    assert render.task_details(task).plain == " (참조 [bold]x[/bold])"


def test_task_line_keeps_markup_in_title_literal() -> None:
    task = make_task(title="[bold]x[/bold]", category=None)

    assert render.task_line(task).plain == "#43 payment [bold]x[/bold]"


# --- task_table / task_lines ---


def test_task_table_rows() -> None:
    tasks = [make_task(), bare_task()]

    output = render_table(render.task_table(tasks, {43: 150}))

    rows = [tokens(line) for line in output.splitlines()]
    assert rows == [
        ["ID", "상태", "프로젝트", "카테고리", "제목", "예상", "실적", "주차", "참조"],
        ["43", "doing", "payment", "design", "환불 API 설계", "4h", "2h 30m", "2026-W42", "#43"],
        ["44", "doing", "admin", "-", "권한 정리", "-", "-", "-", "-"],
    ]


def test_task_table_fits_required_width() -> None:
    table = render.task_table([make_task(), bare_task()], {43: 150})

    width = console.required_width(table)
    output = render_table(table, width)

    assert width == TASK_TABLE_WIDTH
    assert_fits(output, width)
    assert "…" not in output


def test_task_table_zero_actual_is_dash() -> None:
    output = render_table(render.task_table([make_task()], {43: 0}))

    assert tokens(output.splitlines()[1])[6] == "-"


def test_task_lines() -> None:
    lines = render.task_lines([make_task(), bare_task()], {43: 150})

    assert [line.plain for line in lines] == [
        "#43 doing payment/design 환불 API 설계 · 예상 4h · 실적 2h 30m · 2026-W42 · 참조 #43",
        "#44 doing admin 권한 정리",
    ]


# --- plan_table / plan_lines ---


def test_plan_table_rows() -> None:
    tasks = [make_task(), bare_task()]

    output = render_table(render.plan_table(tasks, {43: 150}))

    rows = [tokens(line) for line in output.splitlines()]
    assert rows == [
        ["ID", "상태", "프로젝트", "제목", "예상", "실적"],
        ["43", "doing", "payment", "환불 API 설계", "4h", "2h 30m"],
        ["44", "doing", "admin", "권한 정리", "-", "-"],
    ]


def test_plan_table_fits_required_width() -> None:
    table = render.plan_table([make_task(), bare_task()], {43: 150})

    width = console.required_width(table)
    output = render_table(table, width)

    assert width == PLAN_TABLE_WIDTH
    assert_fits(output, width)
    assert "…" not in output


def test_plan_lines() -> None:
    lines = render.plan_lines([make_task(), bare_task()], {43: 150})

    assert [line.plain for line in lines] == [
        "#43 doing payment 환불 API 설계 · 예상 4h · 실적 2h 30m",
        "#44 doing admin 권한 정리",
    ]


# --- timer_line ---


def make_timer(task_id: int | None) -> ActiveTimer:
    return ActiveTimer(
        project=Project(slug="payment", name="결제"),
        task_id=task_id,
        category="design",
        note="환불 API 설계",
        started_at=FIXED_NOW,
    )


@pytest.mark.parametrize(
    ("task_id", "expected"),
    [
        (43, "payment/design — 환불 API 설계 [#43]"),
        (None, "payment/design — 환불 API 설계"),
    ],
)
def test_timer_line(task_id: int | None, expected: str) -> None:
    assert render.timer_line(make_timer(task_id)).plain == expected


def test_timer_line_keeps_markup_literal() -> None:
    timer = make_timer(None)
    timer.note = "[/api] fix"

    assert render.timer_line(timer).plain == "payment/design — [/api] fix"
