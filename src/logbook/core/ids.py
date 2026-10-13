"""ID 입력 파싱과 검증. CLI 문자열 입력(parse_id)과 JSON 정수 입력(check_id)이 함께 쓴다.

SQLAlchemy를 import하지 않는다.
"""

import re

from logbook.core.errors import InvalidInputError

# SQLite INTEGER 최댓값. 넘는 값은 서비스에서 OverflowError(traceback)가 난다.
MAX_ID = 2**63 - 1
MAX_ID_DIGITS = 19
# 자릿수를 먼저 제한해 int()의 자릿수 한도(4300자리) ValueError도 피한다.
_ID_PATTERN = re.compile(rf"#?([0-9]{{1,{MAX_ID_DIGITS}}})")


def parse_id(text: str, what: str = "기록") -> int:
    """'128', '#128' 형식의 ID. 1 이상 MAX_ID 이하의 ASCII 숫자만 받는다."""
    match = _ID_PATTERN.fullmatch(text.strip())
    value = int(match.group(1)) if match else 0
    if not 1 <= value <= MAX_ID:
        raise InvalidInputError(
            f"{what} ID가 올바르지 않습니다: '{text}'. 숫자로 입력하세요 (예: 128 또는 #128)."
        )
    return value


def check_id(value: int, what: str = "기록") -> int:
    """JSON 정수 ID. bool이거나 1 이상 MAX_ID 이하가 아니면 InvalidInputError."""
    # bool은 int의 하위 타입이라 따로 막는다.
    if isinstance(value, bool) or not 1 <= value <= MAX_ID:
        raise InvalidInputError(
            f"{what} ID가 올바르지 않습니다: {value}. 1 이상의 정수로 입력하세요."
        )
    return value
