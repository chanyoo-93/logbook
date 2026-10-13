"""설정 화면: 프로젝트 표(추가·수정·보관·보관 해제)와 읽기 전용 설정 정보.

수정·보관·해제는 화면이 본 프로젝트 버전(project_version)이 지금 프로젝트와 같을 때만 한다.
카테고리와 기본값은 설정 파일에서 바꾸므로 여기서는 보여 주기만 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse

from logbook.core import services
from logbook.core.duration import format_duration
from logbook.core.errors import InvalidInputError
from logbook.web.context import Ctx, WebContext
from logbook.web.errors import PROJECT_CHANGED, ConflictError
from logbook.web.pages.forms import FormText
from logbook.web.pages.panels import NO_CHANGE, RESULT_MARK
from logbook.web.pages.templating import render, render_error
from logbook.web.pages.views import Choice, content_version

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from logbook.core.models import Project

router = APIRouter()

PAGE_TEMPLATE = "settings.html"
SECTION_TEMPLATE = "partials/project_section.html"
ROW_TEMPLATE = "partials/project_row.html"
EDIT_TEMPLATE = "partials/project_edit_row.html"
PROJECT_ADDED = f"{RESULT_MARK} 프로젝트 추가: {{slug}} ({{name}})"
PROJECT_UPDATED = f"{RESULT_MARK} 프로젝트 수정: {{slug}} ({{name}})"
PROJECT_ARCHIVED = f"{RESULT_MARK} 프로젝트 보관: {{slug}} (과거 기록은 집계에 계속 포함됩니다)"
PROJECT_UNARCHIVED = f"{RESULT_MARK} 프로젝트 보관 해제: {{slug}}"
DEFAULT_ARCHIVED = (
    " 보관한 프로젝트가 설정의 default_project입니다. 설정 파일의 default_project를 바꾸세요."
)
ARCHIVE_CONFIRM = (
    "보관할 프로젝트: {slug} ({name})\n"
    "보관할까요? 과거 기록은 집계에 계속 포함되고, 새 기록과 태스크는 추가할 수 없습니다."
)
CATEGORY_NOTE = (
    "카테고리와 기본값은 설정 파일에서 바꿉니다. 저장한 뒤 화면을 새로 고치면 반영됩니다."
)


def project_version(project: Project) -> str:
    """화면이 본 프로젝트가 그사이 바뀌었는지 가리는 값."""
    return content_version(
        project.id,
        project.slug,
        project.name,
        project.description,
        project.color,
        project.archived,
        project.created_at.isoformat(),
    )


@dataclass(frozen=True)
class ProjectRowView:
    slug: str
    name: str
    color: str  # 견본에 쓸 색: #[0-9a-fA-F]{6}에 맞을 때만 값, 아니면 ''
    color_text: str  # 표에 글자로 보여 줄 원래 값(없으면 '')
    description: str  # 또는 ''
    archived: bool
    is_common: bool  # 보관 버튼을 두지 않는다
    version: str
    archive_confirm: str


@dataclass(frozen=True)
class ProjectAddValues:
    slug: str = ""
    name: str = ""
    color: str = ""


@dataclass(frozen=True)
class ProjectEditValues:
    name: str
    color: str
    description: str
    version: str


@dataclass(frozen=True)
class ProjectEditView:
    slug: str
    values: ProjectEditValues
    error: str = ""


@dataclass(frozen=True)
class ProjectSectionView:
    rows: tuple[ProjectRowView, ...]  # 보관 포함, slug 순
    add_values: ProjectAddValues
    message: str = ""
    is_error: bool = False


@dataclass(frozen=True)
class SettingsInfoView:
    config_file: str  # str(Path) 그대로(Windows 역슬래시)
    db_path: str  # 실제로 연 DB. 설정의 db_path는 다시 시작하기 전에는 다를 수 있다
    categories: tuple[Choice, ...]  # (key, 라벨), 설정 순서
    default_project: str
    week_start: str
    daily_target: str


def project_row(project: Project) -> ProjectRowView:
    color = project.color or ""
    return ProjectRowView(
        slug=project.slug,
        name=project.name,
        color=color if services.is_valid_color(color) else "",
        color_text=color,
        description=project.description or "",
        archived=project.archived,
        is_common=project.slug == services.COMMON_SLUG,
        version=project_version(project),
        archive_confirm=ARCHIVE_CONFIRM.format(slug=project.slug, name=project.name),
    )


def section_view(
    s: Session,
    add_values: ProjectAddValues | None = None,
    *,
    message: str = "",
    is_error: bool = False,
) -> ProjectSectionView:
    rows = tuple(project_row(p) for p in services.list_projects(s, include_archived=True))
    return ProjectSectionView(rows, add_values or ProjectAddValues(), message, is_error)


def info_view(ctx: WebContext) -> SettingsInfoView:
    cfg = ctx.cfg
    return SettingsInfoView(
        config_file=str(ctx.config_file),
        db_path=str(ctx.engine.url.database),
        categories=tuple(Choice(key, label) for key, label in cfg.categories.items()),
        default_project=cfg.default_project,
        week_start=cfg.week_start,
        daily_target=format_duration(cfg.daily_target_minutes),
    )


def _section_response(
    request: Request, section: ProjectSectionView, *, error: InvalidInputError | None = None
) -> HTMLResponse:
    if error is not None:
        return render_error(request, error, SECTION_TEMPLATE, {"section": section})
    return render(request, SECTION_TEMPLATE, {"section": section})


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, ctx: Ctx) -> HTMLResponse:
    with ctx.session() as s:
        section = section_view(s)
    context = {
        "active": "settings",
        "section": section,
        "info": info_view(ctx),
        "category_note": CATEGORY_NOTE,
    }
    return render(request, PAGE_TEMPLATE, context)


@router.post("/settings/projects", response_class=HTMLResponse)
def add_project(
    request: Request,
    ctx: Ctx,
    slug: FormText = "",
    name: FormText = "",
    color: FormText = "",
) -> HTMLResponse:
    values = ProjectAddValues(slug, name, color)
    try:
        with ctx.session() as s:
            project = services.create_project(s, slug.strip(), name, color=color.strip() or None)
            message = PROJECT_ADDED.format(slug=project.slug, name=project.name)
            section = section_view(s, message=message)
    except InvalidInputError as error:
        with ctx.session() as s:
            section = section_view(s, values, message=str(error), is_error=True)
        return _section_response(request, section, error=error)
    return _section_response(request, section)


def _edit_values(project: Project) -> ProjectEditValues:
    return ProjectEditValues(
        project.name, project.color or "", project.description or "", project_version(project)
    )


@router.get("/settings/projects/{slug}/edit", response_class=HTMLResponse)
def edit_row(request: Request, ctx: Ctx, slug: str) -> HTMLResponse:
    with ctx.session() as s:
        project = services.get_project(s, slug)
        edit = ProjectEditView(project.slug, _edit_values(project))
    return render(request, EDIT_TEMPLATE, {"edit": edit})


@router.get("/settings/projects/{slug}/row", response_class=HTMLResponse)
def view_row(request: Request, ctx: Ctx, slug: str) -> HTMLResponse:
    with ctx.session() as s:
        row = project_row(services.get_project(s, slug))
    return render(request, ROW_TEMPLATE, {"row": row})


def _changes(project: Project, form: ProjectEditValues) -> dict[str, Any]:
    """폼 값 중 프로젝트와 다른 것만 update_project 인자로 고른다."""
    changes: dict[str, Any] = {}
    if form.name.strip() != project.name:
        changes["name"] = form.name
    color = form.color.strip() or None
    if color != project.color:
        changes["color"] = color
    description = form.description.strip() or None
    if description != project.description:
        changes["description"] = description
    return changes


def _checked_project(s: Session, slug: str, version: str) -> Project:
    project = services.get_project(s, slug)
    if project_version(project) != version:
        raise ConflictError(PROJECT_CHANGED.format(slug=slug))
    return project


def _apply_update(ctx: WebContext, slug: str, form: ProjectEditValues) -> ProjectSectionView:
    with ctx.session() as s:
        project = _checked_project(s, slug, form.version)
        changes = _changes(project, form)
        message = NO_CHANGE
        if changes:
            project = services.update_project(s, slug, **changes)
            message = PROJECT_UPDATED.format(slug=project.slug, name=project.name)
        return section_view(s, message=message)


def _edit_error(
    request: Request,
    ctx: WebContext,
    slug: str,
    form: ProjectEditValues,
    error: InvalidInputError | ConflictError,
) -> HTMLResponse:
    """입력 문제나 버전 충돌은 편집 행을 입력값 그대로 다시 그린다. 문구는 #flash에 넣는다."""
    edit = ProjectEditView(slug, form, error=str(error))
    headers = {"HX-Retarget": f"#project-{slug}", "HX-Reswap": "outerHTML", "HX-Push-Url": "false"}
    return render_error(request, error, EDIT_TEMPLATE, {"edit": edit}, headers=headers)


@router.patch("/settings/projects/{slug}", response_class=HTMLResponse)
def patch_project(
    request: Request,
    ctx: Ctx,
    slug: str,
    name: FormText = "",
    color: FormText = "",
    description: FormText = "",
    version: FormText = "",
) -> HTMLResponse:
    form = ProjectEditValues(name, color, description, version)
    try:
        section = _apply_update(ctx, slug, form)
    except (InvalidInputError, ConflictError) as error:
        return _edit_error(request, ctx, slug, form, error)
    return render(request, SECTION_TEMPLATE, {"section": section})


def _set_archived(ctx: WebContext, slug: str, version: str, *, archive: bool) -> ProjectSectionView:
    with ctx.session() as s:
        _checked_project(s, slug, version)
        if archive:
            services.archive_project(s, slug)
            message = PROJECT_ARCHIVED.format(slug=slug)
            if slug == ctx.cfg.default_project:
                message += DEFAULT_ARCHIVED
        else:
            services.unarchive_project(s, slug)
            message = PROJECT_UNARCHIVED.format(slug=slug)
        return section_view(s, message=message)


@router.post("/settings/projects/{slug}/archive", response_class=HTMLResponse)
def archive(request: Request, ctx: Ctx, slug: str, version: FormText = "") -> HTMLResponse:
    return render(
        request, SECTION_TEMPLATE, {"section": _set_archived(ctx, slug, version, archive=True)}
    )


@router.post("/settings/projects/{slug}/unarchive", response_class=HTMLResponse)
def unarchive(request: Request, ctx: Ctx, slug: str, version: FormText = "") -> HTMLResponse:
    return render(
        request, SECTION_TEMPLATE, {"section": _set_archived(ctx, slug, version, archive=False)}
    )
