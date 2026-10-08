"""logbook.core.errors 단위 테스트."""

import pytest

from logbook.core.errors import (
    DatabaseBusyError,
    DatabaseNotInitializedError,
    InvalidInputError,
    LogbookError,
    NotFoundError,
)

KOREAN_MESSAGE = "프로젝트 'x'가 없습니다. 'lb project list'로 확인하세요."


def test_errors_are_subclasses() -> None:
    assert issubclass(InvalidInputError, LogbookError)
    assert issubclass(InvalidInputError, ValueError)
    assert issubclass(NotFoundError, LogbookError)
    assert issubclass(NotFoundError, LookupError)

    assert not issubclass(InvalidInputError, NotFoundError)
    assert not issubclass(NotFoundError, InvalidInputError)
    assert not issubclass(InvalidInputError, LookupError)
    assert not issubclass(NotFoundError, ValueError)


def test_database_errors_are_logbook_errors_and_unrelated() -> None:
    assert issubclass(DatabaseNotInitializedError, LogbookError)
    assert issubclass(DatabaseBusyError, LogbookError)

    assert not issubclass(DatabaseNotInitializedError, DatabaseBusyError)
    assert not issubclass(DatabaseBusyError, DatabaseNotInitializedError)


@pytest.mark.parametrize(
    ("error_type", "builtin_base"),
    [(InvalidInputError, ValueError), (NotFoundError, LookupError)],
)
def test_errors_can_be_caught_by_both_bases(
    error_type: type[LogbookError], builtin_base: type[Exception]
) -> None:
    with pytest.raises(LogbookError):
        raise error_type(KOREAN_MESSAGE)
    with pytest.raises(builtin_base):
        raise error_type(KOREAN_MESSAGE)


@pytest.mark.parametrize(
    "error_type",
    [
        LogbookError,
        InvalidInputError,
        NotFoundError,
        DatabaseNotInitializedError,
        DatabaseBusyError,
    ],
)
def test_message_is_korean_roundtrip(error_type: type[LogbookError]) -> None:
    err = error_type(KOREAN_MESSAGE)

    assert str(err) == KOREAN_MESSAGE
    assert err.args == (KOREAN_MESSAGE,)
