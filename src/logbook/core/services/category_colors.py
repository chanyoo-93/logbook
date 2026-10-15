"""카테고리 색 저장과 조회. 카테고리 정의(키·이름)는 설정 파일에 있고, 여기는 고른 색만 둔다."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from logbook.core.config import CATEGORY_KEY
from logbook.core.errors import InvalidInputError
from logbook.core.models import CategoryColor
from logbook.core.services.projects import validate_color


def category_colors(s: Session) -> dict[str, str]:
    """저장된 색 전부를 {카테고리 키: 색}으로 돌려준다."""
    rows = s.scalars(select(CategoryColor).order_by(CategoryColor.category)).all()
    return {row.category: row.color for row in rows}


def set_category_color(s: Session, category: str, color: str) -> None:
    """카테고리 색을 저장한다(있으면 바꾼다). 키는 설정 파일의 키 형식, 색은 '#rrggbb'다.

    키가 설정에 있는지는 확인하지 않는다(호출자 몫). 커밋은 호출자의 session_scope가 한다.
    """
    _validate_key(category)
    validate_color(color)
    row = s.get(CategoryColor, category)
    if row is None:
        s.add(CategoryColor(category=category, color=color))
    else:
        row.color = color
    s.flush()


def clear_category_color(s: Session, category: str) -> bool:
    """색을 지워 자동으로 되돌린다. 지운 행이 있으면 True."""
    row = s.get(CategoryColor, category)
    if row is None:
        return False
    s.delete(row)
    s.flush()
    return True


def _validate_key(category: str) -> None:
    if CATEGORY_KEY.fullmatch(category) is None:
        raise InvalidInputError(
            f"카테고리 키가 올바르지 않습니다: '{category}'. "
            "영문 소문자로 시작하고 영문 소문자·숫자·'_'·'-'만 쓰세요."
        )
