"""프로젝트 생성·조회·목록·보관 유스케이스."""

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.models import Project

COMMON_SLUG = "common"
SLUG_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,31}$"

_SLUG_RE = re.compile(SLUG_PATTERN, re.ASCII)
_COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}", re.ASCII)
_COMMON_NAME = "공통"
_COMMON_DESCRIPTION = "프로젝트와 무관한 업무 (회의, 교육, 행정 등)"


def create_project(
    s: Session,
    slug: str,
    name: str,
    *,
    description: str | None = None,
    color: str | None = None,
) -> Project:
    """새 프로젝트를 만든다. 입력이 잘못되었거나 slug가 이미 있으면 InvalidInputError."""
    _validate_slug(slug)
    clean_name = name.strip()
    if not clean_name:
        raise InvalidInputError("프로젝트 이름이 비어 있습니다. 이름을 입력하세요.")
    _validate_color(color)
    if _find_project(s, slug) is not None:
        raise InvalidInputError(_duplicate_message(slug))
    project = Project(
        slug=slug,
        name=clean_name,
        description=_strip_or_none(description),
        color=color,
    )
    s.add(project)
    try:
        s.flush()
    except IntegrityError as error:
        # 확인과 삽입 사이에 다른 프로세스가 같은 slug를 넣은 경우.
        raise InvalidInputError(_duplicate_message(slug)) from error
    return project


def get_project(s: Session, slug: str) -> Project:
    """slug로 프로젝트를 찾는다 (보관된 프로젝트 포함). 없으면 NotFoundError."""
    project = _find_project(s, slug)
    if project is None:
        raise NotFoundError(f"프로젝트 '{slug}'가 없습니다. 'lb project list'로 확인하세요.")
    return project


def get_active_project(s: Session, slug: str) -> Project:
    """새 기록·태스크를 추가할 프로젝트를 찾는다. 보관된 프로젝트면 InvalidInputError."""
    project = get_project(s, slug)
    if project.archived:
        raise InvalidInputError(
            f"보관된 프로젝트 '{slug}'에는 새 기록이나 태스크를 추가할 수 없습니다. "
            "다른 프로젝트를 지정하세요."
        )
    return project


def list_projects(s: Session, *, include_archived: bool = False) -> list[Project]:
    """slug 순 프로젝트 목록. 기본은 보관된 프로젝트를 제외한다."""
    query = select(Project).order_by(Project.slug)
    if not include_archived:
        query = query.where(Project.archived.is_(False))
    return list(s.scalars(query))


def archive_project(s: Session, slug: str) -> Project:
    """프로젝트를 보관 처리한다. 이미 보관되어 있어도 그대로 반환한다."""
    if slug == COMMON_SLUG:
        raise InvalidInputError(
            "common 프로젝트는 보관할 수 없습니다. "
            "프로젝트와 무관한 업무를 기록하는 기본 프로젝트입니다."
        )
    project = get_project(s, slug)
    if not project.archived:
        project.archived = True
        s.flush()
    return project


def ensure_common_project(s: Session) -> Project:
    """common 프로젝트가 없으면 만들고, 있으면 그대로 반환한다.

    조회와 삽입 사이에 다른 프로세스가 common을 먼저 만들면 create_project의 중복
    InvalidInputError가 그대로 올라가고 세션 트랜잭션은 롤백된다 (단일 사용자 도구라 허용).
    """
    project = _find_project(s, COMMON_SLUG)
    if project is not None:
        return project
    return create_project(s, COMMON_SLUG, _COMMON_NAME, description=_COMMON_DESCRIPTION)


def _find_project(s: Session, slug: str) -> Project | None:
    return s.scalars(select(Project).where(Project.slug == slug)).one_or_none()


def _validate_slug(slug: str) -> None:
    # fullmatch: '$'가 끝의 줄바꿈 앞에서도 맞는 것을 막는다.
    if _SLUG_RE.fullmatch(slug) is None:
        raise InvalidInputError(
            f"프로젝트 slug가 올바르지 않습니다: '{slug}'. 영문 소문자나 숫자로 시작하고 "
            "영문 소문자·숫자·'-'·'_'만 쓸 수 있습니다 (최대 32자)."
        )


def _validate_color(color: str | None) -> None:
    if color is not None and _COLOR_RE.fullmatch(color) is None:
        raise InvalidInputError(
            f"색상이 올바르지 않습니다: '{color}'. '#4f46e5'처럼 '#'과 16진수 6자리로 입력하세요."
        )


def _duplicate_message(slug: str) -> str:
    return f"프로젝트 '{slug}'가 이미 존재합니다. 'lb project list'로 확인하세요."


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None
