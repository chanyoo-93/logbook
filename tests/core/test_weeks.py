"""logbook.core.weeks 단위 테스트."""

from datetime import date, datetime, timedelta

import pytest

from logbook.core.errors import InvalidInputError
from logbook.core.weeks import (
    Week,
    WeekStart,
    clock_label,
    day_label,
    full_day,
    parse_date,
    parse_week,
    total_label,
    week_heading,
    week_of,
)


def test_label_is_zero_padded() -> None:
    assert Week(2026, 1).label == "2026-W01"
    assert Week(2026, 40).label == "2026-W40"


def test_start_and_end_monday_mode() -> None:
    week = Week(2026, 40)
    assert week.start == date(2026, 9, 28)
    assert week.end == date(2026, 10, 4)


def test_start_and_end_sunday_mode() -> None:
    week = Week(2026, 40, "sunday")
    assert week.start == date(2026, 9, 27)
    assert week.end == date(2026, 10, 3)
    assert week.label == "2026-W40"


@pytest.mark.parametrize(
    ("day", "label"),
    [
        (date(2026, 12, 31), "2026-W53"),
        (date(2027, 1, 1), "2026-W53"),
        (date(2025, 12, 29), "2026-W01"),
        (date(2021, 1, 3), "2020-W53"),
        (date(2026, 10, 1), "2026-W40"),
    ],
)
def test_week_of_year_boundaries(day: date, label: str) -> None:
    assert week_of(day).label == label


def test_week_of_sunday_mode_assigns_sunday_to_next_iso_week() -> None:
    assert week_of(date(2026, 9, 27), "sunday") == Week(2026, 40, "sunday")
    assert week_of(date(2026, 10, 3), "sunday") == Week(2026, 40, "sunday")
    assert week_of(date(2026, 10, 4), "sunday") == Week(2026, 41, "sunday")


def test_week_of_monday_mode_keeps_sunday_in_iso_week() -> None:
    assert week_of(date(2026, 10, 4)) == Week(2026, 40)


def test_week_of_sunday_mode_crosses_year() -> None:
    # 2026-12-27(일)은 sunday 모드에서 2026-W53의 첫날, 2027-01-03(일)은 2027-W01의 첫날
    assert week_of(date(2026, 12, 27), "sunday") == Week(2026, 53, "sunday")
    assert week_of(date(2027, 1, 3), "sunday") == Week(2027, 1, "sunday")


def test_week_of_rejects_invalid_week_start() -> None:
    with pytest.raises(InvalidInputError, match="friday"):
        week_of(date(2026, 10, 1), "friday")  # type: ignore[arg-type]


def test_next_and_prev_cross_year_boundary() -> None:
    assert Week(2026, 53).next() == Week(2027, 1)
    assert Week(2026, 1).prev() == Week(2025, 52)
    assert Week(2026, 40).next() == Week(2026, 41)
    assert Week(2026, 40).prev() == Week(2026, 39)


def test_next_and_prev_keep_sunday_mode() -> None:
    assert Week(2026, 53, "sunday").next() == Week(2027, 1, "sunday")
    assert Week(2026, 1, "sunday").prev() == Week(2025, 52, "sunday")
    assert Week(2026, 40, "sunday").next().start == date(2026, 10, 4)


def test_contains_includes_both_ends() -> None:
    week = Week(2026, 40)
    assert week.contains(date(2026, 9, 28))
    assert week.contains(date(2026, 10, 4))
    assert not week.contains(date(2026, 9, 27))
    assert not week.contains(date(2026, 10, 5))


def test_contains_sunday_mode() -> None:
    week = Week(2026, 40, "sunday")
    assert week.contains(date(2026, 9, 27))
    assert week.contains(date(2026, 10, 3))
    assert not week.contains(date(2026, 10, 4))
    assert not week.contains(date(2026, 9, 26))


def test_days_returns_seven_consecutive_dates() -> None:
    week = Week(2026, 40)
    days = week.days()
    assert len(days) == 7
    assert days[0] == week.start
    assert days[-1] == week.end
    assert days == [
        date(2026, 9, 28),
        date(2026, 9, 29),
        date(2026, 9, 30),
        date(2026, 10, 1),
        date(2026, 10, 2),
        date(2026, 10, 3),
        date(2026, 10, 4),
    ]


def test_days_returns_new_list() -> None:
    week = Week(2026, 40)
    week.days().clear()
    assert len(week.days()) == 7


def test_week_53_exists_only_in_long_years() -> None:
    assert Week(2026, 53).start == date(2026, 12, 28)
    with pytest.raises(InvalidInputError, match="2025-W53"):
        Week(2025, 53)


@pytest.mark.parametrize(("year", "number"), [(2026, 54), (2026, 0), (2026, -1)])
def test_week_rejects_nonexistent_week(year: int, number: int) -> None:
    with pytest.raises(InvalidInputError):
        Week(year, number)


# date 범위(0001-01-01~9999-12-31)를 벗어나는 주차는 계산 중 OverflowError 대신 거부한다.
@pytest.mark.parametrize(
    ("year", "number", "week_start"),
    [(9999, 52, "monday"), (9999, 52, "sunday"), (1, 1, "sunday")],
)
def test_week_rejects_week_outside_supported_range(
    year: int, number: int, week_start: WeekStart
) -> None:
    with pytest.raises(InvalidInputError, match=f"{year:04d}-W{number:02d}"):
        Week(year, number, week_start)


def test_week_at_end_of_supported_range_still_works() -> None:
    week = Week(9999, 51)
    assert week.end == date(9999, 12, 26)
    assert week.days()[-1] == date(9999, 12, 26)
    assert Week(1, 1).start == date(1, 1, 1)


@pytest.mark.parametrize("week", [Week(1, 1), Week(1, 2, "sunday")], ids=["monday", "sunday"])
def test_prev_outside_supported_range_raises_invalid_input(week: Week) -> None:
    with pytest.raises(InvalidInputError):
        week.prev()


def test_next_outside_supported_range_raises_invalid_input() -> None:
    with pytest.raises(InvalidInputError):
        Week(9999, 51).next()


def test_week_of_last_supported_date_raises_invalid_input() -> None:
    with pytest.raises(InvalidInputError):
        week_of(date(9999, 12, 31))


def test_parse_week_rejects_week_outside_supported_range(today: date) -> None:
    with pytest.raises(InvalidInputError, match="9999-W52"):
        parse_week("9999-W52", today=today)


def test_week_rejects_invalid_week_start() -> None:
    with pytest.raises(InvalidInputError, match="friday"):
        Week(2026, 40, "friday")  # type: ignore[arg-type]


def test_weeks_are_ordered_chronologically() -> None:
    assert Week(2026, 40) < Week(2026, 41) < Week(2027, 1)


def test_week_is_immutable() -> None:
    week = Week(2026, 40)
    with pytest.raises(AttributeError):
        week.number = 41  # type: ignore[misc]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("this", Week(2026, 40)),
        ("last", Week(2026, 39)),
        ("next", Week(2026, 41)),
        (" THIS ", Week(2026, 40)),
        ("2026-W41", Week(2026, 41)),
        ("2026-w41", Week(2026, 41)),
        ("2026W41", Week(2026, 41)),
        ("2026-W5", Week(2026, 5)),
        ("2026-W05", Week(2026, 5)),
        ("2026-W53", Week(2026, 53)),
    ],
)
def test_parse_week_valid(text: str, expected: Week, today: date) -> None:
    assert parse_week(text, today=today) == expected


def test_parse_week_sunday_mode(today: date) -> None:
    assert parse_week("this", today=today, week_start="sunday") == Week(2026, 40, "sunday")
    assert parse_week("2026-W41", today=today, week_start="sunday") == Week(2026, 41, "sunday")


def test_parse_week_relative_follows_week_start_on_sunday() -> None:
    # 일요일 2026-10-04는 sunday 모드에서 W41, monday 모드에서 W40에 속한다
    sunday = date(2026, 10, 4)
    assert parse_week("this", today=sunday, week_start="sunday") == Week(2026, 41, "sunday")
    assert parse_week("this", today=sunday) == Week(2026, 40)


def test_parse_week_defaults_today_to_current_date() -> None:
    # 자정을 넘기는 경우를 대비해 호출 전후 날짜를 모두 허용한다
    before = date.today()
    result = parse_week("this")
    after = date.today()
    assert result in {week_of(before), week_of(after)}


@pytest.mark.parametrize(
    "text", ["2026-W54", "2026-W00", "2025-W53", "W41", "abc", "", "2026-W041", "26-W41"]
)
def test_parse_week_invalid(text: str, today: date) -> None:
    with pytest.raises(InvalidInputError, match="2026-W41"):
        parse_week(text, today=today)


def test_parse_week_error_shows_input(today: date) -> None:
    with pytest.raises(InvalidInputError, match="abc"):
        parse_week("abc", today=today)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("today", date(2026, 10, 1)),
        ("TODAY", date(2026, 10, 1)),
        ("yesterday", date(2026, 9, 30)),
        ("mon", date(2026, 9, 28)),
        (" Mon ", date(2026, 9, 28)),
        ("tue", date(2026, 9, 29)),
        ("wed", date(2026, 9, 30)),
        ("thu", date(2026, 10, 1)),
        ("fri", date(2026, 9, 25)),
        ("sat", date(2026, 9, 26)),
        ("sun", date(2026, 9, 27)),
        ("2026-10-01", date(2026, 10, 1)),
        ("10-01", date(2026, 10, 1)),
        ("2028-02-29", date(2028, 2, 29)),
        ("2025-12-31", date(2025, 12, 31)),
    ],
)
def test_parse_date_valid(text: str, expected: date, today: date) -> None:
    assert parse_date(text, today=today) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("sun", date(2026, 9, 27)),
        ("sat", date(2026, 9, 26)),
        ("mon", date(2026, 9, 28)),
        ("thu", date(2026, 10, 1)),
    ],
)
def test_parse_date_sunday_mode(text: str, expected: date, today: date) -> None:
    assert parse_date(text, today=today, week_start="sunday") == expected


def test_parse_date_weekday_is_most_recent_within_seven_days_regardless_of_week_start() -> None:
    # 요일 별칭은 week_start와 무관하게 오늘을 포함한 최근 7일 안의 해당 요일이다.
    for offset in range(7):
        base = date(2026, 9, 27) + timedelta(days=offset)
        for alias, weekday in [
            ("mon", 0),
            ("tue", 1),
            ("wed", 2),
            ("thu", 3),
            ("fri", 4),
            ("sat", 5),
            ("sun", 6),
        ]:
            result = parse_date(alias, today=base)
            assert parse_date(alias, today=base, week_start="sunday") == result
            assert base - timedelta(days=6) <= result <= base
            assert result.weekday() == weekday


def test_parse_date_yesterday_crosses_year() -> None:
    assert parse_date("yesterday", today=date(2027, 1, 1)) == date(2026, 12, 31)


def test_parse_date_mm_dd_uses_year_of_today() -> None:
    assert parse_date("12-31", today=date(2027, 1, 2)) == date(2027, 12, 31)


def test_parse_date_defaults_today_to_current_date() -> None:
    before = date.today()
    result = parse_date("today")
    after = date.today()
    assert result in {before, after}


@pytest.mark.parametrize(
    "text",
    [
        "02-30",
        "2026-13-01",
        "foo",
        "2026-02-29",
        "02-29",
        "",
        "2026-1-1",
        "1-1",
        "monday",
        "2026/10/01",
        "0000-01-01",
    ],
)
def test_parse_date_invalid(text: str, today: date) -> None:
    with pytest.raises(InvalidInputError, match="2026-10-01"):
        parse_date(text, today=today)


def test_parse_date_error_shows_input(today: date) -> None:
    with pytest.raises(InvalidInputError, match="foo"):
        parse_date("foo", today=today)


def test_parse_date_rejects_invalid_week_start(today: date) -> None:
    with pytest.raises(InvalidInputError, match="friday"):
        parse_date("mon", today=today, week_start="friday")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 9, 28), "09-28 (월)"),
        (date(2026, 10, 4), "10-04 (일)"),
        (date(2027, 1, 1), "01-01 (금)"),
    ],
)
def test_day_label_has_zero_padded_month_day_and_weekday(day: date, expected: str) -> None:
    assert day_label(day) == expected


@pytest.mark.parametrize(
    ("week", "expected"),
    [
        (Week(2026, 40), "2026-W40 (09-28 ~ 10-04)"),
        (Week(2026, 40, "sunday"), "2026-W40 (09-27 ~ 10-03)"),
        (Week(2026, 53), "2026-W53 (12-28 ~ 01-03)"),
        (Week(2020, 53, "sunday"), "2020-W53 (12-27 ~ 01-02)"),
    ],
)
def test_week_heading_shows_label_and_range(week: Week, expected: str) -> None:
    assert week_heading(week) == expected


# --- 표기: clock_label, total_label, full_day ---


def test_clock_label_shows_time_only_for_today() -> None:
    today = date(2026, 10, 1)

    assert clock_label(datetime(2026, 10, 1, 9, 30), today) == "09:30"


def test_clock_label_adds_date_for_other_days() -> None:
    today = date(2026, 10, 1)

    assert clock_label(datetime(2026, 9, 30, 22, 10), today) == "09-30 (수) 22:10"


def test_total_label_says_today_or_month_day() -> None:
    today = date(2026, 10, 1)

    assert total_label(today, today) == "오늘"
    assert total_label(date(2026, 9, 30), today) == "09-30"


def test_full_day_includes_year_and_weekday() -> None:
    assert full_day(date(2026, 10, 1)) == "2026-10-01 (목)"
