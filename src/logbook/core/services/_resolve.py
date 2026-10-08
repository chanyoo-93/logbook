"""기록과 타이머가 함께 쓰는 메모·카테고리·프로젝트 해석 규칙.

_shared에 두지 않는 이유: projects가 _shared를 import하므로 _shared가 projects를
import하면 순환이 생긴다. 이 모듈은 _shared와 projects를 import하고, worklogs와
timer가 이 모듈을 import한다.
"""

from collections.abc import Collection

from sqlalchemy.orm import Session

from logbook.core.errors import InvalidInputError
from logbook.core.models import Project, Task
from logbook.core.services._shared import MISSING_CATEGORY_MESSAGE, check_category
from logbook.core.services.projects import get_active_project, get_project


def clean_note(note: str) -> str:
    """앞뒤 공백을 지운 메모. 비면 InvalidInputError."""
    clean = note.strip()
    if not clean:
        raise InvalidInputError("메모를 입력하세요. 무엇을 했는지 한 줄로 적어 주세요.")
    return clean


def resolve_category(
    category: str | None, task: Task | None, allowed: Collection[str] | None
) -> str:
    """명시한 카테고리 > 태스크의 카테고리. 둘 다 없으면 InvalidInputError."""
    resolved = task.category if category is None and task is not None else category
    if resolved is None:
        raise InvalidInputError(MISSING_CATEGORY_MESSAGE)
    return check_category(resolved, allowed)


def pick_slug(explicit: str | None, task: Task | None, fallback: str) -> str:
    """명시한 slug > 태스크의 프로젝트 > fallback."""
    if explicit is not None:
        return explicit
    return task.project.slug if task is not None else fallback


def target_project(
    s: Session,
    slug: str,
    task: Task | None,
    *,
    current: Project | None,
    task_is_new: bool = True,
) -> Project:
    """기록이 속할 프로젝트. 연결된 태스크와 프로젝트가 같아야 한다.

    current가 None이면 추가 경로, 아니면 수정 경로다. task_is_new는 task가 이번에 새로
    지정한 태스크인지(False면 기록에 이미 연결된 태스크) 나타낸다.
    프로젝트가 current와 같으면 보관 여부를 다시 확인하지 않는다 (보관된 프로젝트의
    옛 기록도 시간·메모는 고칠 수 있다).
    """
    if task is not None and task.project.slug != slug:
        owner = task.project.slug
        if not task_is_new:
            raise InvalidInputError(
                f"연결된 태스크 #{task.id}의 프로젝트('{owner}')와 다른 프로젝트로 옮길 수 "
                "없습니다. 태스크 연결을 해제하거나 같은 프로젝트를 지정하세요."
            )
        raise InvalidInputError(
            f"태스크 #{task.id}는 '{owner}' 프로젝트에 속합니다. "
            f"프로젝트를 빼거나 '{owner}'로 지정하세요."
        )
    if current is None:
        return get_active_project(s, slug)
    if current.slug == slug:
        return current
    project = get_project(s, slug)
    if project.archived:
        raise InvalidInputError(
            f"보관된 프로젝트로는 기록을 옮길 수 없습니다: '{slug}'. 다른 프로젝트를 지정하세요."
        )
    return project
