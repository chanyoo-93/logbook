"""여러 서비스 모듈이 함께 쓰는 조회·검증 도우미.

worklogs와 tasks가 서로 import하지 않도록 공통 부분을 여기에 둔다.
"""

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.models import Task

MISSING_CATEGORY_MESSAGE = "카테고리를 지정하세요. 예: -c dev"


def load_task(s: Session, task_id: int) -> Task:
    """id로 태스크를 찾는다 (project를 함께 로드). 없으면 NotFoundError."""
    query = select(Task).where(Task.id == task_id).options(joinedload(Task.project))
    task = s.scalars(query).one_or_none()
    if task is None:
        raise NotFoundError(f"태스크 #{task_id}가 없습니다. 'lb task list'로 확인하세요.")
    return task


def check_category(category: str, allowed: Collection[str] | None) -> str:
    """앞뒤 공백을 지운 카테고리를 반환한다. 비었거나 allowed에 없으면 InvalidInputError."""
    category = category.strip()
    if not category:
        raise InvalidInputError(MISSING_CATEGORY_MESSAGE)
    if allowed is not None and category not in allowed:
        listed = ", ".join(sorted(allowed))
        raise InvalidInputError(
            f"카테고리 '{category}'는 쓸 수 없습니다. 사용할 수 있는 카테고리: {listed}"
        )
    return category
