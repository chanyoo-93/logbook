"""ISO 8601 주차(YYYY-Www) 계산과 날짜·주차 입력 파싱.

주차 라벨은 항상 ISO 주차를 따른다. sunday 모드는 범위만 하루 앞당긴다(일~토).
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, get_args

from logbook.core.errors import InvalidInputError

WeekStart = Literal["monday", "sunday"]

_DAYS_PER_WEEK = 7
_ONE_DAY = timedelta(days=1)
_ONE_WEEK = timedelta(days=_DAYS_PER_WEEK)
_SUNDAY = 6  # date.weekday() 기준

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

# 소문자로 바꾼 뒤 적용한다. re.ASCII로 전각 숫자 등 비ASCII 숫자는 받지 않는다.
_WEEK_PATTERN = re.compile(r"(?P<year>[0-9]{4})-?w(?P<number>[0-9]{1,2})", re.ASCII)
_FULL_DATE_PATTERN = re.compile(
    r"(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})", re.ASCII
)
_MONTH_DAY_PATTERN = re.compile(r"(?P<month>[0-9]{2})-(?P<day>[0-9]{2})", re.ASCII)


def _check_week_start(week_start: str) -> None:
    if week_start not in get_args(WeekStart):
        raise InvalidInputError(
            f"주 시작 요일이 올바르지 않습니다: '{week_start}'. "
            "'monday' 또는 'sunday'로 설정하세요."
        )


@dataclass(frozen=True, order=True)
class Week:
    """ISO 주차 하나. week_start는 범위(start~end)를 정할 때만 쓰인다."""

    year: int
    number: int
    week_start: WeekStart = "monday"

    def __post_init__(self) -> None:
        _check_week_start(self.week_start)
        try:
            # 범위 끝(end)까지 계산해 date 범위(0001-01-01~9999-12-31) 안인지도 확인한다.
            _ = self.end
        except (ValueError, OverflowError):
            raise InvalidInputError(
                f"존재하지 않거나 지원 범위를 벗어난 주차입니다: '{self.label}'. "
                "주차는 연도에 따라 W01~W52 또는 W53까지 있습니다."
            ) from None

    @property
    def label(self) -> str:
        return f"{self.year:04d}-W{self.number:02d}"

    @property
    def _iso_monday(self) -> date:
        return date.fromisocalendar(self.year, self.number, 1)

    @property
    def start(self) -> date:
        """주의 첫날. ISO 월요일이며, sunday 모드에서는 하루 앞선 일요일."""
        monday = self._iso_monday
        return monday - _ONE_DAY if self.week_start == "sunday" else monday

    @property
    def end(self) -> date:
        """주의 마지막 날(start + 6일). sunday 모드에서는 토요일."""
        return self.start + timedelta(days=_DAYS_PER_WEEK - 1)

    def contains(self, d: date) -> bool:
        return self.start <= d <= self.end

    def next(self) -> "Week":
        return self._shift(_ONE_WEEK)

    def prev(self) -> "Week":
        return self._shift(-_ONE_WEEK)

    def days(self) -> list[date]:
        start = self.start
        return [start + timedelta(days=offset) for offset in range(_DAYS_PER_WEEK)]

    def _shift(self, delta: timedelta) -> "Week":
        try:
            iso = (self._iso_monday + delta).isocalendar()
        except OverflowError:
            raise InvalidInputError(
                f"지원 범위를 벗어난 주차입니다: '{self.label}'의 이전·다음 주차는 "
                "계산할 수 없습니다. 다른 주차를 지정하세요."
            ) from None
        return Week(iso.year, iso.week, self.week_start)


def week_of(d: date, week_start: WeekStart = "monday") -> Week:
    """d가 속한 주차. sunday 모드에서 일요일은 다음 ISO 주차에 속한다."""
    _check_week_start(week_start)
    if week_start == "sunday" and d.weekday() == _SUNDAY:
        d += _ONE_DAY
    iso = d.isocalendar()
    return Week(iso.year, iso.week, week_start)


def parse_week(text: str, *, today: date | None = None, week_start: WeekStart = "monday") -> Week:
    """'this', 'last', 'next', '2026-W41'(대소문자·'-' 생략 허용)을 Week로 바꾼다."""
    current = week_of(today if today is not None else date.today(), week_start)
    normalized = text.strip().lower()
    if normalized == "this":
        return current
    if normalized == "last":
        return current.prev()
    if normalized == "next":
        return current.next()

    error = InvalidInputError(
        f"주차 형식이 올바르지 않습니다: '{text}'. 예: this, last, next, 2026-W41"
    )
    match = _WEEK_PATTERN.fullmatch(normalized)
    if match is None:
        raise error
    try:
        return Week(int(match["year"]), int(match["number"]), week_start)
    except InvalidInputError:
        raise error from None


def parse_date(text: str, *, today: date | None = None, week_start: WeekStart = "monday") -> date:
    """'today', 'yesterday', 'mon'~'sun', 'YYYY-MM-DD', 'MM-DD'를 date로 바꾼다.

    요일은 오늘을 포함한 최근 7일 중 해당 요일이며 week_start와 무관하다(week_start는 검증만 한다).
    """
    _check_week_start(week_start)
    base = today if today is not None else date.today()
    normalized = text.strip().lower()
    if normalized == "today":
        return base
    if normalized == "yesterday":
        return base - _ONE_DAY
    if normalized in _WEEKDAYS:
        week_first_day = week_of(base, week_start).start
        offset = (_WEEKDAYS[normalized] - week_first_day.weekday()) % _DAYS_PER_WEEK
        day = week_first_day + timedelta(days=offset)
        return day - _ONE_WEEK if day > base else day

    error = InvalidInputError(
        f"날짜 형식이 올바르지 않습니다: '{text}'. 예: today, yesterday, mon~sun, 2026-10-01, 10-01"
    )
    full = _FULL_DATE_PATTERN.fullmatch(normalized)
    month_day = _MONTH_DAY_PATTERN.fullmatch(normalized)
    try:
        if full is not None:
            return date(int(full["year"]), int(full["month"]), int(full["day"]))
        if month_day is not None:
            return date(base.year, int(month_day["month"]), int(month_day["day"]))
    except ValueError:
        raise error from None
    raise error
