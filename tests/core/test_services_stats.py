"""logbook.core.services.stats 단위 테스트."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.errors import InvalidInputError
from logbook.core.services import MatrixResult, StatsResult, StatsRow
from logbook.core.weeks import Week

# 2026-W40: 월요일 9/28 ~ 일요일 10/4 (sunday 모드는 일요일 9/27 ~ 토요일 10/3)
W40 = Week(2026, 40)
W40_SUNDAY = Week(2026, 40, "sunday")
SUN_BEFORE = date(2026, 9, 27)
MON = date(2026, 9, 28)
TUE = date(2026, 9, 29)
THU = date(2026, 10, 1)
SAT = date(2026, 10, 3)
SUN = date(2026, 10, 4)
NEXT_MON = date(2026, 10, 5)


@pytest.fixture
def seeded(session: Session) -> Session:
    """common, payment, search 프로젝트가 있는 세션."""
    services.ensure_common_project(session)
    services.create_project(session, "payment", "결제 서버")
    services.create_project(session, "search", "검색")
    return session


def _log(s: Session, project: str, category: str, minutes: int, work_date: date = THU) -> None:
    services.add_worklog(
        s,
        minutes=minutes,
        note="작업",
        project_slug=project,
        category=category,
        work_date=work_date,
    )


def _summary(rows: tuple[StatsRow, ...]) -> list[tuple[str, int, int]]:
    return [(row.key, row.minutes, row.count) for row in rows]


# --- stats_by: 공통 ---


@pytest.mark.parametrize("by", ["project", "category"])
def test_empty_week_has_no_rows(seeded: Session, by: services.StatsBy) -> None:
    result = services.stats_by(seeded, W40, by)

    assert result == StatsResult(week=W40, by=by, total_minutes=0, count=0, rows=())


def test_empty_week_by_day_has_seven_zero_rows(seeded: Session) -> None:
    result = services.stats_by(seeded, W40, "day")

    assert (result.total_minutes, result.count) == (0, 0)
    assert [row.key for row in result.rows] == [day.isoformat() for day in W40.days()]
    assert all(row.minutes == 0 and row.count == 0 for row in result.rows)


def test_invalid_by_raises(seeded: Session) -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        services.stats_by(seeded, W40, "week")  # type: ignore[arg-type]

    assert str(exc_info.value) == (
        "집계 기준이 올바르지 않습니다: 'week'. project, category, day 중 하나를 쓰세요."
    )


# --- stats_by: project ---


def test_by_project_sums_minutes_and_counts_logs(seeded: Session) -> None:
    _log(seeded, "search", "dev", 90, MON)
    _log(seeded, "payment", "dev", 120, MON)
    _log(seeded, "payment", "meeting", 60, SUN)

    result = services.stats_by(seeded, W40, "project")

    assert result.rows == (
        StatsRow(key="payment", label="결제 서버", minutes=180, count=2),
        StatsRow(key="search", label="검색", minutes=90, count=1),
    )
    assert (result.week, result.by) == (W40, "project")
    assert (result.total_minutes, result.count) == (270, 3)


def test_count_is_number_of_worklogs_not_minutes(seeded: Session) -> None:
    for _ in range(3):
        _log(seeded, "payment", "dev", 30)

    result = services.stats_by(seeded, W40, "project")

    assert _summary(result.rows) == [("payment", 90, 3)]
    assert result.count == 3


def test_by_project_ties_are_ordered_by_key(seeded: Session) -> None:
    _log(seeded, "search", "dev", 60)
    _log(seeded, "payment", "dev", 60)
    _log(seeded, "common", "meeting", 30)

    result = services.stats_by(seeded, W40, "project")

    assert [row.key for row in result.rows] == ["payment", "search", "common"]


def test_by_project_includes_archived_project(seeded: Session) -> None:
    _log(seeded, "search", "dev", 45)
    services.archive_project(seeded, "search")

    result = services.stats_by(seeded, W40, "project")

    assert _summary(result.rows) == [("search", 45, 1)]
    assert result.rows[0].label == "검색"


def test_logs_outside_week_are_excluded(seeded: Session) -> None:
    _log(seeded, "payment", "dev", 60, SUN_BEFORE)
    _log(seeded, "payment", "dev", 30, MON)
    _log(seeded, "payment", "dev", 20, SUN)
    _log(seeded, "payment", "dev", 90, NEXT_MON)

    result = services.stats_by(seeded, W40, "project")

    assert _summary(result.rows) == [("payment", 50, 2)]


# --- stats_by: category ---


def test_by_category_uses_labels_and_falls_back_to_key(seeded: Session) -> None:
    _log(seeded, "payment", "dev", 120)
    _log(seeded, "search", "dev", 60)
    _log(seeded, "common", "meeting", 30)

    result = services.stats_by(seeded, W40, "category", category_labels={"dev": "개발"})

    assert result.rows == (
        StatsRow(key="dev", label="개발", minutes=180, count=2),
        StatsRow(key="meeting", label="meeting", minutes=30, count=1),
    )
    assert (result.total_minutes, result.count) == (210, 3)


def test_by_category_without_labels_uses_key(seeded: Session) -> None:
    _log(seeded, "payment", "review", 30)
    _log(seeded, "payment", "dev", 30)

    result = services.stats_by(seeded, W40, "category")

    assert [(row.key, row.label) for row in result.rows] == [
        ("dev", "dev"),
        ("review", "review"),
    ]


# --- stats_by: day ---


def test_by_day_has_seven_rows_in_date_order(seeded: Session) -> None:
    _log(seeded, "payment", "dev", 60, TUE)
    _log(seeded, "search", "dev", 30, TUE)
    _log(seeded, "payment", "dev", 45, SUN)
    _log(seeded, "payment", "dev", 999, NEXT_MON)

    result = services.stats_by(seeded, W40, "day")

    assert _summary(result.rows) == [
        ("2026-09-28", 0, 0),
        ("2026-09-29", 90, 2),
        ("2026-09-30", 0, 0),
        ("2026-10-01", 0, 0),
        ("2026-10-02", 0, 0),
        ("2026-10-03", 0, 0),
        ("2026-10-04", 45, 1),
    ]
    assert (result.total_minutes, result.count) == (135, 3)


def test_by_day_labels_have_month_day_and_weekday(seeded: Session) -> None:
    result = services.stats_by(seeded, W40, "day")

    assert [row.label for row in result.rows] == [
        "09-28 (월)",
        "09-29 (화)",
        "09-30 (수)",
        "10-01 (목)",
        "10-02 (금)",
        "10-03 (토)",
        "10-04 (일)",
    ]


def test_sunday_mode_week_includes_previous_sunday(seeded: Session) -> None:
    _log(seeded, "payment", "dev", 60, SUN_BEFORE)
    _log(seeded, "payment", "dev", 30, SAT)
    _log(seeded, "payment", "dev", 90, SUN)

    result = services.stats_by(seeded, W40_SUNDAY, "day")

    assert result.rows[0] == StatsRow(key="2026-09-27", label="09-27 (일)", minutes=60, count=1)
    assert result.rows[-1] == StatsRow(key="2026-10-03", label="10-03 (토)", minutes=30, count=1)
    assert (result.total_minutes, result.count) == (90, 2)


def test_sunday_mode_project_stats_use_shifted_range(seeded: Session) -> None:
    _log(seeded, "payment", "dev", 60, SUN_BEFORE)
    _log(seeded, "payment", "dev", 90, SUN)

    result = services.stats_by(seeded, W40_SUNDAY, "project")

    assert _summary(result.rows) == [("payment", 60, 1)]


# --- stats_matrix ---


def _seed_matrix(s: Session) -> None:
    _log(s, "payment", "dev", 120, MON)
    _log(s, "payment", "dev", 60, TUE)
    _log(s, "payment", "meeting", 30, THU)
    _log(s, "search", "review", 60, THU)
    _log(s, "common", "meeting", 90, SUN)
    _log(s, "common", "admin", 30, SUN)
    _log(s, "payment", "dev", 600, NEXT_MON)


def test_matrix_cells_and_totals(seeded: Session) -> None:
    _seed_matrix(seeded)

    result = services.stats_matrix(seeded, W40)

    assert result.week == W40
    assert result.projects == ("payment", "common", "search")
    assert result.categories == ("admin", "dev", "meeting", "review")
    assert dict(result.cells) == {
        ("payment", "dev"): 180,
        ("payment", "meeting"): 30,
        ("search", "review"): 60,
        ("common", "meeting"): 90,
        ("common", "admin"): 30,
    }
    assert dict(result.row_totals) == {"payment": 210, "common": 120, "search": 60}
    assert dict(result.col_totals) == {"dev": 180, "meeting": 120, "review": 60, "admin": 30}
    assert (result.total_minutes, result.count) == (390, 6)


def test_matrix_keeps_category_order_and_drops_empty_categories(seeded: Session) -> None:
    _seed_matrix(seeded)

    result = services.stats_matrix(
        seeded, W40, category_order=["dev", "review", "meeting", "docs", "admin"]
    )

    assert result.categories == ("dev", "review", "meeting", "admin")


def test_matrix_appends_categories_missing_from_order_alphabetically(seeded: Session) -> None:
    _seed_matrix(seeded)
    _log(seeded, "search", "ops", 15, THU)

    result = services.stats_matrix(seeded, W40, category_order=["meeting", "dev"])

    assert result.categories == ("meeting", "dev", "admin", "ops", "review")


def test_matrix_project_ties_are_ordered_by_slug(seeded: Session) -> None:
    _log(seeded, "search", "dev", 60)
    _log(seeded, "payment", "dev", 60)

    result = services.stats_matrix(seeded, W40)

    assert result.projects == ("payment", "search")


def test_matrix_includes_archived_project(seeded: Session) -> None:
    _log(seeded, "search", "dev", 45)
    services.archive_project(seeded, "search")

    result = services.stats_matrix(seeded, W40)

    assert result.projects == ("search",)
    assert dict(result.cells) == {("search", "dev"): 45}


def test_matrix_of_empty_week(seeded: Session) -> None:
    result = services.stats_matrix(seeded, W40, category_order=["dev"])

    assert result == MatrixResult(
        week=W40,
        projects=(),
        categories=(),
        cells={},
        row_totals={},
        col_totals={},
        total_minutes=0,
        count=0,
    )


def test_matrix_uses_sunday_mode_range(seeded: Session) -> None:
    _log(seeded, "payment", "dev", 60, SUN_BEFORE)
    _log(seeded, "payment", "dev", 90, SUN)

    result = services.stats_matrix(seeded, W40_SUNDAY)

    assert dict(result.cells) == {("payment", "dev"): 60}
    assert (result.total_minutes, result.count) == (60, 1)


def test_matrix_mappings_are_read_only(seeded: Session) -> None:
    _log(seeded, "payment", "dev", 60)

    result = services.stats_matrix(seeded, W40)

    with pytest.raises(TypeError):
        result.cells[("payment", "dev")] = 0  # type: ignore[index]
    with pytest.raises(TypeError):
        result.row_totals["payment"] = 0  # type: ignore[index]
    with pytest.raises(TypeError):
        result.col_totals["dev"] = 0  # type: ignore[index]


# --- daily_project_minutes ---


def test_daily_project_minutes_builds_day_by_project_grid(seeded: Session) -> None:
    _log(seeded, "payment", "dev", 60, MON)
    _log(seeded, "common", "meeting", 30, MON)
    _log(seeded, "payment", "dev", 120, THU)
    _log(seeded, "payment", "dev", 999, SUN_BEFORE)

    result = services.daily_project_minutes(seeded, W40)

    assert isinstance(result, services.DailyProjectResult)
    assert result.week == W40
    assert result.days == tuple(W40.days())
    assert len(result.days) == 7
    assert result.projects == ("payment", "common")
    assert dict(result.cells) == {(MON, "payment"): 60, (MON, "common"): 30, (THU, "payment"): 120}
    assert result.day_totals[TUE] == 0
    assert result.day_totals[MON] == 90
    assert set(result.day_totals) == set(W40.days())
    assert result.total_minutes == 210


def test_daily_project_minutes_orders_ties_by_slug(seeded: Session) -> None:
    _log(seeded, "search", "dev", 60, MON)
    _log(seeded, "payment", "dev", 60, TUE)

    result = services.daily_project_minutes(seeded, W40)

    assert result.projects == ("payment", "search")


def test_daily_project_minutes_empty_week(seeded: Session) -> None:
    result = services.daily_project_minutes(seeded, W40)

    assert result.projects == ()
    assert dict(result.cells) == {}
    assert result.total_minutes == 0
    assert list(result.day_totals.values()) == [0] * 7


def test_daily_project_minutes_respects_sunday_week(seeded: Session) -> None:
    _log(seeded, "payment", "dev", 60, SUN_BEFORE)
    _log(seeded, "payment", "dev", 30, SAT)
    _log(seeded, "payment", "dev", 999, SUN)

    result = services.daily_project_minutes(seeded, W40_SUNDAY)

    assert result.days[0] == SUN_BEFORE
    assert result.days[-1] == SAT
    assert result.total_minutes == 90


def test_daily_project_minutes_includes_archived_project(seeded: Session) -> None:
    _log(seeded, "search", "dev", 45, MON)
    services.archive_project(seeded, "search")

    result = services.daily_project_minutes(seeded, W40)

    assert result.projects == ("search",)
    assert result.total_minutes == 45
