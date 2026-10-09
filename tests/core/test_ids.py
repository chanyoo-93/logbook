"""logbook.core.ids 단위 테스트."""

import pytest

from logbook.core.errors import InvalidInputError
from logbook.core.ids import MAX_ID, check_id, parse_id


@pytest.mark.parametrize(
    ("text", "expected"),
    [("128", 128), ("#128", 128), (" 7 ", 7), (str(MAX_ID), MAX_ID)],
)
def test_parse_id_accepts_valid_ids(text: str, expected: int) -> None:
    assert parse_id(text) == expected


@pytest.mark.parametrize(
    "text",
    ["0", "-1", "12a", "١٢", str(MAX_ID + 1), "1" * 20],
    ids=["zero", "negative", "letters", "arabic-digits", "over-max", "twenty-digits"],
)
def test_parse_id_rejects_invalid_ids(text: str) -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        parse_id(text)

    assert str(exc_info.value) == (
        f"기록 ID가 올바르지 않습니다: '{text}'. 숫자로 입력하세요 (예: 128 또는 #128)."
    )


def test_parse_id_names_the_target() -> None:
    with pytest.raises(InvalidInputError, match="태스크 ID가 올바르지 않습니다"):
        parse_id("x", "태스크")


@pytest.mark.parametrize("value", [1, MAX_ID])
def test_check_id_accepts_valid_ids(value: int) -> None:
    assert check_id(value) == value


@pytest.mark.parametrize("value", [0, -1, MAX_ID + 1, True])
def test_check_id_rejects_invalid_ids(value: int) -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        check_id(value)

    assert str(exc_info.value) == (
        f"기록 ID가 올바르지 않습니다: {value}. 1 이상의 정수로 입력하세요."
    )


def test_check_id_names_the_target() -> None:
    with pytest.raises(InvalidInputError, match="태스크 ID가 올바르지 않습니다"):
        check_id(0, "태스크")
