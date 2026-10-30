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
from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.web.context import Ctx, WebContext
from logbook.web.errors import CATEGORY_CHANGED, PROJECT_CHANGED, ConflictError, user_message
from logbook.web.pages.forms import FormText
from logbook.web.pages.panels import NO_CHANGE, RESULT_MARK
from logbook.web.pages.templating import render, render_error
from logbook.web.pages.views import (
    CHART_PALETTE,
    category_color_map,
    content_version,
    project_color,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from logbook.core.models import Project

router = APIRouter()

PAGE_TEMPLATE = "settings.html"
SECTION_TEMPLATE = "partials/project_section.html"
CATEGORY_TEMPLATE = "partials/category_section.html"
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
    "카테고리 추가와 이름은 설정 파일 [categories]에서 바꿉니다. "
    "저장한 뒤 화면을 새로 고치면 반영됩니다."
)
CATEGORY_SAVED = f"{RESULT_MARK} {{key}} 색을 저장했습니다."
CATEGORY_RESET = f"{RESULT_MARK} {{key}} 색을 자동으로 되돌렸습니다."
CATEGORY_UNKNOWN = "설정에 없는 카테고리입니다: {key}. 설정 파일 [categories]를 확인하세요."
FONT_NOTE = (
    "글꼴은 이 PC에 설치된 글꼴 이름으로 정합니다"
    "(설정 [web]의 heading_font·document_font·body_font). "
    "설치되지 않은 글꼴이면 기본 글꼴로 보입니다."
)
DEFAULT_FONT_LABEL = "기본 글꼴"
AUTO_LABEL = "자동"
AUTO_ON = "1"  # 자동 체크가 켜졌을 때 폼이 보내는 값(꺼지면 키가 오지 않는다)


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
    color: str  # 견본 색: 지정한 색, 없거나 형식이 틀리면 자동 팔레트 색(항상 #rrggbb)
    color_text: str  # 표에 보여 줄 글자: 지정한 색의 원래 값, 자동이면 '자동'
    description: str  # 또는 ''
    archived: bool
    is_common: bool  # 보관 버튼을 두지 않는다
    version: str
    archive_confirm: str


@dataclass(frozen=True)
class ProjectAddValues:
    slug: str = ""
    name: str = ""
    color: str = CHART_PALETTE[0]
    is_auto: bool = True


@dataclass(frozen=True)
class ProjectEditValues:
    name: str
    color: str  # 색 고르기 칸의 값
    description: str
    version: str
    is_auto: bool = False  # '자동' 체크


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
class CategoryRowView:
    key: str
    label: str
    color: str  # 색 칸의 값: 저장한 색, 없으면 자동 팔레트 색
    is_auto: bool  # 저장한 색이 없다
    version: str


@dataclass(frozen=True)
class CategorySectionView:
    rows: tuple[CategoryRowView, ...]  # 설정 순서
    note: str = CATEGORY_NOTE
    message: str = ""


@dataclass(frozen=True)
class FontRowView:
    label: str
    name: str  # 설정 값. 비어 있으면 '기본 글꼴'
    preview_class: str


@dataclass(frozen=True)
class SettingsInfoView:
    config_file: str  # str(Path) 그대로(Windows 역슬래시)
    db_path: str  # 실제로 연 DB. 설정의 db_path는 다시 시작하기 전에는 다를 수 있다
    default_project: str
    week_start: str
    daily_target: str
    fonts: tuple[FontRowView, ...]


def category_version(key: str, stored_color: str | None) -> str:
    """화면이 본 카테고리 색이 그사이 바뀌었는지 가리는 값."""
    return content_version(key, stored_color or "")


def category_section_view(ctx: WebContext, s: Session, *, message: str = "") -> CategorySectionView:
    stored = services.category_colors(s)
    colors = category_color_map(tuple(ctx.cfg.categories), stored)
    rows = tuple(
        CategoryRowView(
            key=key,
            label=label,
            color=colors[key],
            is_auto=key not in stored,
            version=category_version(key, stored.get(key)),
        )
        for key, label in ctx.cfg.categories.items()
    )
    return CategorySectionView(rows, message=message)


def _chosen_color(project: Project) -> str:
    """지정한 색(검증된 #rrggbb). 없거나 형식이 틀리면 ''(자동)."""
    color = project.color or ""
    return color if services.is_valid_color(color) else ""


def project_row(project: Project) -> ProjectRowView:
    return ProjectRowView(
        slug=project.slug,
        name=project.name,
        color=project_color(project),
        color_text=_chosen_color(project) or AUTO_LABEL,
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
        default_project=cfg.default_project,
        week_start=cfg.week_start,
        daily_target=format_duration(cfg.daily_target_minutes),
        fonts=(
            FontRowView(
                "제목 글꼴", cfg.web.heading_font or DEFAULT_FONT_LABEL, "font-preview--heading"
            ),
            FontRowView(
                "문서 글꼴", cfg.web.document_font or DEFAULT_FONT_LABEL, "font-preview--document"
            ),
            FontRowView("본문 글꼴", cfg.web.body_font or DEFAULT_FONT_LABEL, "font-preview--body"),
        ),
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
        categories = category_section_view(ctx, s)
    context = {
        "active": "settings",
        "section": section,
        "categories": categories,
        "info": info_view(ctx),
        "font_note": FONT_NOTE,
    }
    return render(request, PAGE_TEMPLATE, context)


@router.post("/settings/projects", response_class=HTMLResponse)
def add_project(
    request: Request,
    ctx: Ctx,
    slug: FormText = "",
    name: FormText = "",
    color: FormText = "",
    color_auto: FormText = "",
) -> HTMLResponse:
    is_auto = color_auto == AUTO_ON
    values = ProjectAddValues(slug, name, color, is_auto)
    try:
        with ctx.session() as s:
            chosen = None if is_auto else color.strip() or None
            project = services.create_project(s, slug.strip(), name, color=chosen)
            message = PROJECT_ADDED.format(slug=project.slug, name=project.name)
            section = section_view(s, message=message)
    except InvalidInputError as error:
        with ctx.session() as s:
            section = section_view(s, values, message=user_message(error), is_error=True)
        return _section_response(request, section, error=error)
    return _section_response(request, section)


def _edit_values(project: Project) -> ProjectEditValues:
    chosen = _chosen_color(project)
    return ProjectEditValues(
        project.name,
        chosen or project_color(project),
        project.description or "",
        project_version(project),
        is_auto=not chosen,
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


def _same_color(new: str | None, stored: str | None) -> bool:
    """색 비교는 대소문자를 무시한다(색 고르기 칸은 소문자로 보낸다)."""
    if new is None or stored is None:
        return new is stored
    return new.lower() == stored.lower()


def _changes(project: Project, form: ProjectEditValues) -> dict[str, Any]:
    """폼 값 중 프로젝트와 다른 것만 update_project 인자로 고른다."""
    changes: dict[str, Any] = {}
    if form.name.strip() != project.name:
        changes["name"] = form.name
    color = None if form.is_auto else form.color.strip() or None
    if not _same_color(color, project.color):
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
    edit = ProjectEditView(slug, form, error=user_message(error))
    headers = {"HX-Retarget": f"#project-{slug}", "HX-Reswap": "outerHTML", "HX-Push-Url": "false"}
    return render_error(request, error, EDIT_TEMPLATE, {"edit": edit}, headers=headers)


@router.patch("/settings/projects/{slug}", response_class=HTMLResponse)
def patch_project(
    request: Request,
    ctx: Ctx,
    slug: str,
    name: FormText = "",
    color: FormText = "",
    color_auto: FormText = "",
    description: FormText = "",
    version: FormText = "",
) -> HTMLResponse:
    form = ProjectEditValues(name, color, description, version, is_auto=color_auto == AUTO_ON)
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


def _set_category_color(
    ctx: WebContext, key: str, color: str, auto: str, version: str
) -> CategorySectionView:
    with ctx.session() as s:
        if key not in ctx.cfg.categories:
            raise NotFoundError(CATEGORY_UNKNOWN.format(key=key))
        stored = services.category_colors(s).get(key)
        if category_version(key, stored) != version:
            raise ConflictError(CATEGORY_CHANGED.format(key=key))
        message = NO_CHANGE
        new_color = color.strip()
        if auto:
            if services.clear_category_color(s, key):
                message = CATEGORY_RESET.format(key=key)
        elif stored is None or stored.lower() != new_color.lower():
            services.set_category_color(s, key, new_color)
            message = CATEGORY_SAVED.format(key=key)
        return category_section_view(ctx, s, message=message)


@router.post("/settings/categories/{key}/color", response_class=HTMLResponse)
def set_category_color(
    request: Request,
    ctx: Ctx,
    key: str,
    color: FormText = "",
    auto: FormText = "",
    version: FormText = "",
) -> HTMLResponse:
    """오류(404, 409, 400)는 잡지 않는다. 전역 처리기가 #flash로 보내고 표는 그대로 남는다."""
    section = _set_category_color(ctx, key, color, auto, version)
    return render(request, CATEGORY_TEMPLATE, {"categories": section})
