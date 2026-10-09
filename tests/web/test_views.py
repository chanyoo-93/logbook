"""화면 뷰 데이터(pages/views.py, pages/summary.py) 테스트."""

import re
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from logbook.core.models import ActiveTimer, Project, WorkLog
from logbook.web.pages.summary import CHART_PALETTE, project_colors
from logbook.web.pages.views import (
    RECENT_LIMIT,
    log_row,
    record_text,
    timer_view,
    worklog_version,
)
from tests.cli.helpers import FIXED_NOW

CREATED_AT = datetime(2026, 10, 1, 0, 30, tzinfo=UTC)


def _log(**overrides: object) -> WorkLog:
    fields: dict[str, object] = {
        "id": 1,
        "project_id": 1,
        "task_id": None,
        "category": "dev",
        "date": date(2026, 10, 1),
        "minutes": 120,
        "note": "메모",
        "created_at": CREATED_AT,
        "project": Project(id=1, slug="payment", name="결제"),
    }
    fields.update(overrides)
    return WorkLog(**fields)


def _timer(**overrides: object) -> ActiveTimer:
    fields: dict[str, object] = {
        "id": 1,
        "project_id": 1,
        "task_id": 43,
        "category": "design",
        "note": "환불 API 설계",
        "started_at": datetime(2026, 9, 30, 13, 10, tzinfo=UTC),
        "project": Project(id=1, slug="payment", name="결제"),
    }
    fields.update(overrides)
    return ActiveTimer(**fields)


def test_recent_limit_is_ten() -> None:
    assert RECENT_LIMIT == 10


def test_worklog_version_is_sixteen_lowercase_hex() -> None:
    assert re.fullmatch(r"[0-9a-f]{16}", worklog_version(_log()))


def test_worklog_version_is_stable_for_the_same_record() -> None:
    assert worklog_version(_log()) == worklog_version(_log())


@pytest.mark.parametrize(
    "change",
    [
        {"id": 2},
        {"date": date(2026, 10, 2)},
        {"minutes": 121},
        {"note": "다른 메모"},
        {"project_id": 2},
        {"category": "docs"},
        {"task_id": 7},
        {"created_at": CREATED_AT + timedelta(seconds=1)},
    ],
    ids=["id", "date", "minutes", "note", "project_id", "category", "task_id", "created_at"],
)
def test_worklog_version_changes_with_each_field(change: dict[str, object]) -> None:
    assert worklog_version(_log(**change)) != worklog_version(_log())


def test_worklog_version_separates_fields() -> None:
    # 필드 경계가 없으면 ('a', 'bc')와 ('ab', 'c')가 같아진다.
    assert worklog_version(_log(note="a", category="bc")) != worklog_version(
        _log(note="ab", category="c")
    )


def test_project_colors_uses_explicit_color_or_palette_position() -> None:
    colors = project_colors(["a", "b", "c"], {"a": None, "b": "#123456", "c": None})

    assert colors == {"a": CHART_PALETTE[0], "b": "#123456", "c": CHART_PALETTE[2]}


def test_project_colors_cycles_through_the_palette() -> None:
    slugs = [f"p{i}" for i in range(len(CHART_PALETTE) + 1)]

    colors = project_colors(slugs, {})

    assert colors[slugs[-1]] == CHART_PALETTE[0]


def test_project_colors_ignores_unknown_explicit_slugs() -> None:
    assert project_colors(["a"], {"zzz": "#111111"}) == {"a": CHART_PALETTE[0]}


def test_timer_view_converts_started_at_to_local_time() -> None:
    view = timer_view(_timer(), FIXED_NOW)

    assert view.started == "09-30 (수) 22:10"


def test_timer_view_shows_only_the_time_for_today() -> None:
    today_start = datetime(2026, 10, 1, 0, 30, tzinfo=UTC)  # 로컬(+09:00) 09:30

    view = timer_view(_timer(started_at=today_start), FIXED_NOW)

    assert view.started == "09:30"


def test_timer_view_fields() -> None:
    now = FIXED_NOW + timedelta(minutes=85)
    started = datetime(2026, 10, 1, 0, 30, tzinfo=UTC)

    view = timer_view(_timer(started_at=started), now)

    assert view.scope == "payment/design"
    assert view.note == "환불 API 설계"
    assert view.task == "#43"
    assert view.elapsed == "1h 25m"


def test_timer_view_without_task() -> None:
    assert timer_view(_timer(task_id=None), FIXED_NOW).task is None


def test_timer_view_uses_the_offset_of_now() -> None:
    now = datetime(2026, 10, 1, 9, 30, tzinfo=timezone(timedelta(hours=-5)))
    started = datetime(2026, 10, 1, 13, 0, tzinfo=UTC)  # 로컬(-05:00) 08:00

    assert timer_view(_timer(started_at=started), now).started == "08:00"


def test_record_text_without_date() -> None:
    assert record_text(_log(), with_date=False) == "#1 payment/dev 2h — 메모"


def test_record_text_with_date() -> None:
    assert record_text(_log(), with_date=True) == "#1 2026-10-01 (목) payment/dev 2h — 메모"


def test_log_row_fields() -> None:
    log = _log(id=128, task_id=42, minutes=90)

    row = log_row(log)

    assert row.id == 128
    assert row.day == "10-01 (목)"
    assert row.full_day == "2026-10-01 (목)"
    assert row.iso_date == "2026-10-01"
    assert row.project == "payment"
    assert row.category == "dev"
    assert row.duration == "1h 30m"
    assert row.note == "메모"
    assert row.task == "#42"
    assert row.version == worklog_version(log)


def test_log_row_without_task_shows_dash() -> None:
    assert log_row(_log()).task == "-"
