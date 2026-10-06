"""소요 시간 문자열("1h30m", "1.5h", "90m", "1:30" 등)과 정수 분 사이의 변환."""

import re
from decimal import MAX_EMAX, MIN_EMIN, ROUND_HALF_UP, Context, Decimal

from logbook.core.errors import InvalidInputError

MAX_MINUTES = 24 * 60
MINUTES_PER_HOUR = 60
_ECHO_LIMIT = 40  # 에러 메시지에 되돌려 보여줄 입력의 최대 글자 수

# 소문자로 바꾼 뒤 적용한다. re.ASCII로 전각 숫자 등 비ASCII 숫자는 받지 않는다.
_PATTERNS = tuple(
    re.compile(pattern, re.ASCII)
    for pattern in (
        r"(?P<minutes>[0-9]+)m?",  # 45, 90m
        r"(?P<hours>[0-9]+(?:\.[0-9]+)?)h",  # 2h, 1.5h
        r"(?P<hours>[0-9]+)h\s*(?P<minutes>[0-9]+)m?",  # 1h30m, 1h 30m, 1h30
        r"(?P<hours>[0-9]+):(?P<minutes>[0-9]{2})",  # 1:30
    )
)


def _echo(text: str) -> str:
    """에러 메시지용 입력 표시. 너무 긴 입력은 앞부분만 남긴다."""
    return text if len(text) <= _ECHO_LIMIT else text[:_ECHO_LIMIT] + "..."


def _format_error(text: str) -> InvalidInputError:
    return InvalidInputError(
        f"시간 형식이 올바르지 않습니다: '{_echo(text)}'. 예: 2h, 1.5h, 90m, 1h30m, 1:30"
    )


def _to_minutes(hours: str | None, minutes: str | None) -> Decimal:
    """정규식 그룹을 정확한 분(Decimal)으로 바꾼다."""
    minute_value = Decimal(minutes) if minutes is not None else Decimal(0)
    if hours is None:
        return minute_value
    # 곱셈(최대 len(hours)+2자리)과 59 이하 분 덧셈(+1자리)이 모두 정확하도록 정밀도를 잡는다.
    # 지수 범위도 최대로 넓혀 아주 긴 입력에서 Overflow 없이 범위 검사로 넘긴다.
    context = Context(prec=len(hours) + 3, Emax=MAX_EMAX, Emin=MIN_EMIN)
    product = context.multiply(Decimal(hours), Decimal(MINUTES_PER_HOUR))
    return context.add(product, minute_value)


def parse_duration(text: str) -> int:
    """소요 시간 문자열을 정수 분으로 바꾼다. 형식이 틀리거나 범위를 벗어나면 InvalidInputError."""
    normalized = text.strip().lower()
    for pattern in _PATTERNS:
        match = pattern.fullmatch(normalized)
        if match is None:
            continue
        groups = match.groupdict()
        hours, minutes = groups.get("hours"), groups.get("minutes")
        # 시·분 조합(1h30m, 1:30)에서 분은 0~59만 허용한다.
        if hours is not None and minutes is not None and Decimal(minutes) >= MINUTES_PER_HOUR:
            raise _format_error(text)
        exact = _to_minutes(hours, minutes)
        rounded = exact.to_integral_value(rounding=ROUND_HALF_UP)
        if rounded < 1:
            raise InvalidInputError(f"소요 시간은 1분 이상이어야 합니다: '{_echo(text)}'")
        if rounded > MAX_MINUTES:
            raise InvalidInputError(f"소요 시간은 24시간 이하여야 합니다: '{_echo(text)}'")
        return int(rounded)
    raise _format_error(text)


def format_duration(minutes: int) -> str:
    """정수 분을 "1h 30m", "1h", "30m", "0m" 형태로 표시한다. 음수는 ValueError."""
    if minutes < 0:
        raise ValueError(f"minutes must not be negative: {minutes}")
    hours, rest = divmod(minutes, MINUTES_PER_HOUR)
    if hours == 0:
        return f"{rest}m"
    if rest == 0:
        return f"{hours}h"
    return f"{hours}h {rest}m"
