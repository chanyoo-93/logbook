"""logbook.core.duration 단위 테스트."""

import pytest

from logbook.core.duration import MAX_MINUTES, format_duration, parse_duration
from logbook.core.errors import InvalidInputError

FULLWIDTH_TWO = "２"  # 전각 숫자 '２'


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2h", 120),
        ("1.5h", 90),
        ("90m", 90),
        ("1h30m", 90),
        ("1h 30m", 90),
        ("45", 45),
        ("1:30", 90),
        ("0.25h", 15),
        (" 2H ", 120),
        ("24h", 1440),
        ("1h30", 90),
        ("1h 30", 90),
        ("0:45", 45),
        ("24:00", 1440),
        ("90M", 90),
        ("1H30M", 90),
        ("0.1h", 6),
        ("0.075h", 5),
        ("1h0m", 60),
        ("1:59", 119),
    ],
)
def test_parse_duration_valid(text: str, expected: int) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["0", "0m", "0h", "0:00", "0.001h"])
def test_parse_duration_rejects_below_one_minute(text: str) -> None:
    with pytest.raises(InvalidInputError, match="1분 이상") as exc_info:
        parse_duration(text)
    assert f"'{text}'" in str(exc_info.value)


@pytest.mark.parametrize("text", ["25h", "1441", "24:01", "24h 1m", "9" * 5000, "9" * 5000 + "h"])
def test_parse_duration_rejects_over_24_hours(text: str) -> None:
    with pytest.raises(InvalidInputError, match="24시간 이하"):
        parse_duration(text)


@pytest.mark.parametrize(
    "text",
    [
        "-1h",
        "abc",
        "",
        "   ",
        "1.5",
        "1.5m",
        "1:75",
        "h",
        "1hh",
        "1.5h30m",
        "1h75m",
        "1h60m",
        "1h 60",
        "1:60",
        "0:60",
        "1:5",
        ":30",
        ".5h",
        "2.h",
        "1 h",
        "30m1h",
        "1h2h",
        "+2h",
        "2d",
        f"{FULLWIDTH_TWO}h",
    ],
)
def test_parse_duration_rejects_bad_format(text: str) -> None:
    with pytest.raises(InvalidInputError, match="형식") as exc_info:
        parse_duration(text)
    assert f"'{text}'" in str(exc_info.value)
    assert "예: 2h, 1.5h, 90m, 1h30m, 1:30" in str(exc_info.value)


# 유효 자릿수가 기본 Decimal 정밀도(28)를 넘어도 정확한 값을 한 번만 반올림해야 한다.
NEAR_HALF_MINUTE_BELOW = "0.00833333333333333333333333333333333h"  # 0.4999...98분
NEAR_HALF_MINUTE_ABOVE = "0.00833333333333333333333333333333334h"  # 0.5000...04분
NEAR_MAX_BELOW_HALF = "24.0083333333333333333333333333333h"  # 1440.4999...98분


def test_parse_duration_rounds_exact_value_of_long_decimal_below_half() -> None:
    with pytest.raises(InvalidInputError, match="1분 이상"):
        parse_duration(NEAR_HALF_MINUTE_BELOW)


def test_parse_duration_rounds_exact_value_of_long_decimal_above_half() -> None:
    assert parse_duration(NEAR_HALF_MINUTE_ABOVE) == 1


def test_parse_duration_rounds_exact_value_of_long_decimal_near_max() -> None:
    assert parse_duration(NEAR_MAX_BELOW_HALF) == MAX_MINUTES


# 기본 Decimal 지수 한계(Emax=999999)를 넘는 자릿수에서도 Overflow 대신 범위 에러여야 한다.
HUGE_DIGITS = "9" * 1_000_001


@pytest.mark.parametrize(
    "text",
    [HUGE_DIGITS, HUGE_DIGITS + "m", HUGE_DIGITS + "h", HUGE_DIGITS + "h30m", HUGE_DIGITS + ":00"],
    ids=["minutes", "minutes-unit", "hours", "hours-minutes", "clock"],
)
def test_parse_duration_rejects_huge_input_as_too_large(text: str) -> None:
    with pytest.raises(InvalidInputError, match="24시간 이하"):
        parse_duration(text)


def test_parse_duration_rejects_tiny_input_as_too_small() -> None:
    with pytest.raises(InvalidInputError, match="1분 이상"):
        parse_duration("0." + "0" * 1_000_001 + "1h")


# 시·분 사이의 "선택적 공백"은 \s(공백·탭·개행)로 정의한다. 앞뒤 공백은 strip()으로 제거된다.
@pytest.mark.parametrize("text", ["1h\t30m", "1h\n30", "1h  30m"])
def test_parse_duration_accepts_any_ascii_whitespace_between_hours_and_minutes(text: str) -> None:
    assert parse_duration(text) == 90


@pytest.mark.parametrize(
    ("text", "keyword"),
    [("x" * 1000, "형식"), ("9" * 1000, "24시간 이하"), ("0" * 1000, "1분 이상")],
)
def test_parse_duration_error_truncates_long_input(text: str, keyword: str) -> None:
    with pytest.raises(InvalidInputError, match=keyword) as exc_info:
        parse_duration(text)
    message = str(exc_info.value)
    assert f"'{text[:40]}...'" in message
    assert len(message) < 200


def test_parse_duration_error_echoes_input_when_too_large() -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        parse_duration("25h")
    assert str(exc_info.value) == (
        "소요 시간은 24시간 이하여야 합니다: '25h'. 하루를 넘는 작업은 날짜별로 나눠 기록하세요."
    )


def test_parse_duration_error_echoes_input_with_example_when_too_small() -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        parse_duration("0m")
    assert str(exc_info.value) == "소요 시간은 1분 이상이어야 합니다: '0m'. 예: 30m, 1h"


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (90, "1h 30m"),
        (60, "1h"),
        (30, "30m"),
        (0, "0m"),
        (1, "1m"),
        (1440, "24h"),
        (1500, "25h"),
        (1501, "25h 1m"),
    ],
)
def test_format_duration(minutes: int, expected: str) -> None:
    assert format_duration(minutes) == expected


@pytest.mark.parametrize("minutes", [-1, -90])
def test_format_duration_rejects_negative(minutes: int) -> None:
    with pytest.raises(ValueError) as exc_info:
        format_duration(minutes)
    assert not isinstance(exc_info.value, InvalidInputError)


def test_format_then_parse_round_trips_every_valid_minute() -> None:
    for minutes in range(1, MAX_MINUTES + 1):
        assert parse_duration(format_duration(minutes)) == minutes
