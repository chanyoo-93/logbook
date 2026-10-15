"""logbook.core.services.category_colors 단위 테스트."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.errors import InvalidInputError
from logbook.core.models import CategoryColor


def _row_count(s: Session) -> int:
    return s.scalar(select(func.count()).select_from(CategoryColor)) or 0


def test_starts_empty(session: Session) -> None:
    assert services.category_colors(session) == {}


def test_set_change_list_and_clear(session: Session) -> None:
    services.set_category_color(session, "dev", "#4f46e5")
    services.set_category_color(session, "meeting", "#0F7A3D")
    assert services.category_colors(session) == {"dev": "#4f46e5", "meeting": "#0F7A3D"}

    services.set_category_color(session, "dev", "#112233")
    assert services.category_colors(session) == {"dev": "#112233", "meeting": "#0F7A3D"}
    assert _row_count(session) == 2

    assert services.clear_category_color(session, "dev") is True
    assert services.clear_category_color(session, "dev") is False
    assert services.category_colors(session) == {"meeting": "#0F7A3D"}


@pytest.mark.parametrize("color", ["red", "#12345", "#1234567", "4f46e5", "#4f46eg", "#4f46e5\n"])
def test_invalid_color_is_rejected(session: Session, color: str) -> None:
    with pytest.raises(InvalidInputError) as excinfo:
        services.set_category_color(session, "dev", color)

    assert str(excinfo.value) == (
        f"색상이 올바르지 않습니다: '{color}'. '#4f46e5'처럼 '#'과 16진수 6자리로 입력하세요."
    )
    assert _row_count(session) == 0


@pytest.mark.parametrize("key", ["Dev", "1x", "a b", "", "-a", "한글"])
def test_invalid_key_is_rejected(session: Session, key: str) -> None:
    with pytest.raises(InvalidInputError) as excinfo:
        services.set_category_color(session, key, "#4f46e5")

    assert str(excinfo.value) == (
        f"카테고리 키가 올바르지 않습니다: '{key}'. "
        "영문 소문자로 시작하고 영문 소문자·숫자·'_'·'-'만 쓰세요."
    )
    assert _row_count(session) == 0


@pytest.mark.parametrize("name", ["category_colors", "set_category_color", "clear_category_color"])
def test_public_names_are_exported_from_services(name: str) -> None:
    assert name in services.__all__
    assert hasattr(services, name)
