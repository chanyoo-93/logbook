"""화면 뷰 데이터(pages/views.py, pages/summary.py) 테스트."""

import re
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from logbook.core.config import DEFAULT_CATEGORIES
from logbook.core.models import ActiveTimer, Project, WorkLog
from logbook.web.pages.views import (
    RECENT_LIMIT,
    category_color_map,
    content_version,
    log_row,
    project_color,
    record_text,
    timer_version,
    timer_view,
    worklog_version,
)
from tests.helpers import FIXED_NOW

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


def test_project_color_uses_explicit_color() -> None:
    assert project_color(Project(id=3, slug="a", name="a", color="#123456")) == "#123456"


@pytest.mark.parametrize(
    ("project_id", "expected"),
    [
        (1, "#495057"),
        (2, "#a61e4d"),
        (3, "#5c940d"),
        (10, "#2f6fde"),
        (11, "#495057"),
    ],
)
def test_project_color_falls_back_to_palette_from_the_end(project_id: int, expected: str) -> None:
    assert project_color(Project(id=project_id, slug="a", name="a")) == expected


@pytest.mark.parametrize("color", ["red", "#12345", "#12345g"])
def test_project_color_ignores_invalid_color(color: str) -> None:
    assert project_color(Project(id=2, slug="a", name="a", color=color)) == "#a61e4d"


def test_first_project_color_differs_from_every_default_category_color() -> None:
    colors = category_color_map(tuple(DEFAULT_CATEGORIES), {}).values()

    assert project_color(Project(id=1, slug="common", name="공통")) not in colors


def test_log_row_has_project_color() -> None:
    assert log_row(_log()).project_color == "#495057"


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


def test_content_version_matches_worklog_version() -> None:
    log = _log(task_id=7)
    expected = content_version(
        log.id,
        log.date.isoformat(),
        log.minutes,
        log.note,
        log.project_id,
        log.category,
        log.task_id,
        log.created_at.isoformat(),
    )

    assert expected == worklog_version(log)


def test_content_version_treats_none_as_empty_and_separates_fields() -> None:
    assert content_version("a", None) == content_version("a", "")
    assert content_version("a", "bc") != content_version("ab", "c")


def test_timer_version_changes_with_started_at_and_note() -> None:
    base = timer_version(_timer())

    assert timer_version(_timer()) == base
    assert timer_version(_timer(note="다른 메모")) != base
    assert timer_version(_timer(started_at=datetime(2026, 9, 30, 13, 11, tzinfo=UTC))) != base


def test_timer_view_has_version_and_cancel_confirm() -> None:
    now = FIXED_NOW + timedelta(minutes=85)
    started = datetime(2026, 10, 1, 0, 30, tzinfo=UTC)
    timer = _timer(started_at=started, note="설계")

    view = timer_view(timer, now)

    assert view.version == timer_version(timer)
    assert view.cancel_confirm == (
        "버릴 타이머: payment/design — 설계 (시작 09:30 · 경과 1h 25m)\n"
        "버릴까요? 기록은 남지 않습니다."
    )
