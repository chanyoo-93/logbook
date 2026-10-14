"""태스크 화면: 칸반 보드(GET /tasks), 상태 변경(POST /tasks/{id}/status), 추가(POST /tasks),
카드 수정(GET /tasks/{id}/edit·card, PATCH /tasks/{id}), 이월(POST /tasks/carry).

상태 변경·수정은 화면이 본 태스크 버전(task_version)이 지금 태스크와 같을 때만 한다.
DB 없이 끝나는 검증을 먼저 하고, 나머지는 세션 하나 안에서 한다. 중간에 오류가 나면
모두 롤백되어 DB가 바뀌지 않는다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse

from logbook.core import services
from logbook.core.duration import format_duration, parse_duration
from logbook.core.errors import InvalidInputError, LogbookError, NotFoundError
from logbook.core.ids import parse_id
from logbook.core.taskstatus import TaskStatus, parse_status
from logbook.core.weeks import parse_week, week_of
from logbook.web.context import TASK_LABEL, Ctx, WebContext
from logbook.web.errors import TASK_CHANGED, ConflictError
from logbook.web.htmx import is_htmx
from logbook.web.pages.forms import FormText, QueryText
from logbook.web.pages.panels import NO_CHANGE, RESULT_MARK
from logbook.web.pages.task_views import (
    CARRY_CONFIRM,
    DROP_CONFIRM,
    STATUS_LABELS,
    TaskEditValues,
    TaskFormValues,
    edit_values,
    plan_panel,
    task_board,
    task_card,
    task_edit_view,
    task_filter_view,
    task_form_view,
    task_version,
)
from logbook.web.pages.templating import render, render_error

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from logbook.core.models import Task
    from logbook.core.weeks import Week

__all__ = [
    "CARRIED",
    "CARRY_CONFIRM",
    "CARRY_EMPTY",
    "CARRY_NONE",
    "CARRY_SKIPPED",
    "DROP_CONFIRM",
    "STATUS_CHANGED",
    "TASK_ADDED",
    "TASK_UPDATED",
    "router",
]

router = APIRouter()

PAGE_TEMPLATE = "tasks.html"
BOARD_TEMPLATE = "partials/task_board_response.html"
FORM_TEMPLATE = "partials/task_form_response.html"
PLAN_TEMPLATE = "partials/task_plan_response.html"
CARD_TEMPLATE = "partials/task_card.html"
EDIT_TEMPLATE = "partials/task_edit_card.html"
TASK_ADDED = f"{RESULT_MARK} 태스크 추가: #{{id}} {{project}} · {{title}}{{details}}"
STATUS_CHANGED = f"{RESULT_MARK} #{{id}} {{old}} → {{new}}: {{project}} · {{title}}{{tail}}"
TASK_UPDATED = f"{RESULT_MARK} 수정했습니다: #{{id}} {{project}} · {{title}}"
CARRIED = f"{RESULT_MARK} {{count}}건을 옮겼습니다: {{this}} → {{next}}"
CARRY_SKIPPED = " {count}건은 그사이 바뀌어 옮기지 않았습니다."
CARRY_EMPTY = "옮길 태스크가 없습니다."
CARRY_NONE = (
    "옮긴 태스크가 없습니다. 그사이 상태나 계획 주차가 바뀌었습니다. "
    "패널을 지금 상태로 다시 표시했습니다."
)


@router.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request, ctx: Ctx, project: QueryText = "") -> HTMLResponse:
    selected = project.strip()
    try:
        with ctx.session() as s:
            board = task_board(s, ctx, selected)
            plan = plan_panel(s, ctx, selected)
            filters = task_filter_view(s, selected)
            form = task_form_view(s, ctx, TaskFormValues())
    except NotFoundError as error:
        if is_htmx(request):
            raise  # 알림 영역에 쓴다 (공통 오류 처리)
        with ctx.session() as s:
            filters = task_filter_view(s, selected)
            form = task_form_view(s, ctx, TaskFormValues())
        context = {
            "active": "tasks",
            "form": form,
            "filters": filters,
            "board": None,
            "plan": None,
            "error": str(error),
        }
        return render_error(request, error, PAGE_TEMPLATE, context)
    if is_htmx(request):
        return render(request, BOARD_TEMPLATE, {"board": board, "plan": plan})
    context = {"active": "tasks", "form": form, "filters": filters, "board": board, "plan": plan}
    return render(request, PAGE_TEMPLATE, context)


def _status_message(s: Session, task: Task, old: TaskStatus) -> str:
    """상태 변경 결과 줄. 완료로 바꿨으면 꼬리에 실적(과 예상)을 붙인다."""
    tail = ""
    if task.status == TaskStatus.DONE:
        actual = format_duration(services.task_actual_minutes(s, task.id))
        estimate = task.estimate_minutes
        tail = (
            f" (실적 {actual}"
            + ("" if estimate is None else f" / 예상 {format_duration(estimate)}")
            + ")"
        )
    return STATUS_CHANGED.format(
        id=task.id,
        old=STATUS_LABELS[old],
        new=STATUS_LABELS[task.status],
        project=task.project.slug,
        title=task.title,
        tail=tail,
    )


@router.post("/tasks/{task_id}/status", response_class=HTMLResponse)
def set_status(
    request: Request,
    ctx: Ctx,
    task_id: str,
    status: FormText = "",
    version: FormText = "",
    project: FormText = "",
) -> HTMLResponse:
    number = parse_id(task_id, TASK_LABEL)
    new_status = parse_status(status)
    with ctx.session() as s:
        task = services.get_task(s, number)
        if task_version(task) != version:
            raise ConflictError(TASK_CHANGED.format(id=task.id))
        old = task.status
        task = services.set_task_status(s, number, new_status)
        message = _status_message(s, task, old)
        board = task_board(s, ctx, project.strip(), message=message)
        plan = plan_panel(s, ctx, project.strip())
    return render(request, BOARD_TEMPLATE, {"board": board, "plan": plan})


def _added_details(estimate: int | None, week: str | None) -> str:
    parts = []
    if estimate is not None:
        parts.append(f"예상 {format_duration(estimate)}")
    if week is not None:
        parts.append(week)
    return f" ({', '.join(parts)})" if parts else ""


def _add_task(ctx: WebContext, values: TaskFormValues, filter_project: str) -> dict[str, Any]:
    """폼 값을 검증해 태스크를 저장하고, 성공 응답에 필요한 템플릿 값을 돌려준다."""
    today, week_start = ctx.today(), ctx.cfg.week_start
    estimate = (
        parse_duration(values.estimate, max_minutes=None) if values.estimate.strip() else None
    )
    planned = (
        parse_week(values.week, today=today, week_start=week_start) if values.week.strip() else None
    )
    with ctx.session() as s:
        task = services.create_task(
            s,
            title=values.title,
            project_slug=values.task_project.strip() or ctx.cfg.default_project,
            category=values.task_category.strip() or None,
            estimate_minutes=estimate,
            planned_week=planned,
            allowed_categories=tuple(ctx.cfg.categories),
        )
        details = _added_details(task.estimate_minutes, task.planned_week)
        message = TASK_ADDED.format(
            id=task.id, project=task.project.slug, title=task.title, details=details
        )
        kept = TaskFormValues(
            task_project=values.task_project,
            task_category=values.task_category,
            week=values.week,
        )
        return {
            "form": task_form_view(s, ctx, kept, message=message),
            "board": task_board(s, ctx, filter_project),
            "plan": plan_panel(s, ctx, filter_project),
        }


@router.post("/tasks", response_class=HTMLResponse)
def add_task(
    request: Request,
    ctx: Ctx,
    title: FormText = "",
    task_project: FormText = "",
    task_category: FormText = "",
    estimate: FormText = "",
    week: FormText = "",
    project: FormText = "",
) -> HTMLResponse:
    values = TaskFormValues(title, task_project, task_category, estimate, week)
    try:
        page = _add_task(ctx, values, project.strip())
    except LogbookError as error:
        with ctx.session() as s:
            form = task_form_view(s, ctx, values, message=str(error), is_error=True)
        return render_error(
            request, error, FORM_TEMPLATE, {"form": form, "board": None, "plan": None}
        )
    return render(request, FORM_TEMPLATE, page)


@router.get("/tasks/{task_id}/edit", response_class=HTMLResponse)
def task_edit_fragment(request: Request, ctx: Ctx, task_id: str) -> HTMLResponse:
    number = parse_id(task_id, TASK_LABEL)
    with ctx.session() as s:
        task = services.get_task(s, number)
        edit = task_edit_view(ctx, task, edit_values(task))
    return render(request, EDIT_TEMPLATE, {"edit": edit})


@router.get("/tasks/{task_id}/card", response_class=HTMLResponse)
def task_card_fragment(request: Request, ctx: Ctx, task_id: str) -> HTMLResponse:
    number = parse_id(task_id, TASK_LABEL)
    this_week = week_of(ctx.today(), ctx.cfg.week_start)
    with ctx.session() as s:
        task = services.get_task(s, number)
        card = task_card(task, services.task_actual_minutes(s, number), this_week)
    return render(request, CARD_TEMPLATE, {"card": card})


def _changes(
    task: Task, form: TaskEditValues, estimate: int | None, week: Week | None
) -> dict[str, Any]:
    """폼 값 중 태스크와 다른 것만 update_task 인자로 고른다."""
    changes: dict[str, Any] = {}
    if form.title.strip() != task.title:
        changes["title"] = form.title
    category = form.task_category.strip() or None
    if category != task.category:
        changes["category"] = category
    if estimate != task.estimate_minutes:
        changes["estimate_minutes"] = estimate
    if (None if week is None else week.label) != task.planned_week:
        changes["planned_week"] = week
    return changes


def _apply_update(
    ctx: WebContext, task_id: str, form: TaskEditValues, filter_project: str
) -> dict[str, Any]:
    number = parse_id(task_id, TASK_LABEL)
    estimate = parse_duration(form.estimate, max_minutes=None) if form.estimate.strip() else None
    week = (
        parse_week(form.week, today=ctx.today(), week_start=ctx.cfg.week_start)
        if form.week.strip()
        else None
    )
    with ctx.session() as s:
        task = services.get_task(s, number)
        if task_version(task) != form.version:
            raise ConflictError(TASK_CHANGED.format(id=task.id))
        changes = _changes(task, form, estimate, week)
        message = NO_CHANGE
        if changes:
            task = services.update_task(
                s, number, **changes, allowed_categories=tuple(ctx.cfg.categories)
            )
            message = TASK_UPDATED.format(id=task.id, project=task.project.slug, title=task.title)
        return {
            "board": task_board(s, ctx, filter_project, message=message),
            "plan": plan_panel(s, ctx, filter_project),
        }


def _edit_error(
    request: Request, ctx: WebContext, task_id: str, form: TaskEditValues, error: LogbookError
) -> HTMLResponse:
    """입력 문제나 버전 충돌은 편집 카드를 입력값 그대로 다시 그린다. 문구는 #flash에 넣는다."""
    number = parse_id(task_id, TASK_LABEL)
    with ctx.session() as s:
        task = services.get_task(s, number)
        edit = task_edit_view(ctx, task, form, error=str(error))
    headers = {"HX-Retarget": f"#task-{number}", "HX-Reswap": "outerHTML", "HX-Push-Url": "false"}
    return render_error(request, error, EDIT_TEMPLATE, {"edit": edit}, headers=headers)


@router.patch("/tasks/{task_id}", response_class=HTMLResponse)
def patch_task(
    request: Request,
    ctx: Ctx,
    task_id: str,
    title: FormText = "",
    task_category: FormText = "",
    estimate: FormText = "",
    week: FormText = "",
    version: FormText = "",
    project: FormText = "",
) -> HTMLResponse:
    form = TaskEditValues(title, task_category, estimate, week, version)
    try:
        page = _apply_update(ctx, task_id, form, project.strip())
    except (InvalidInputError, ConflictError) as error:
        return _edit_error(request, ctx, task_id, form, error)
    return render(request, BOARD_TEMPLATE, page)


def _carry_ids(text: str) -> list[int]:
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts:
        raise InvalidInputError(CARRY_EMPTY)
    return [parse_id(part, TASK_LABEL) for part in parts]


def _carry(ctx: WebContext, ids: list[int], filter_project: str) -> dict[str, Any]:
    this_week = week_of(ctx.today(), ctx.cfg.week_start)
    with ctx.session() as s:
        moved = services.carry_tasks(s, this_week, ids)
        if not moved:
            raise ConflictError(CARRY_NONE)
        message = CARRIED.format(
            count=len(moved), this=this_week.label, next=this_week.next().label
        )
        skipped = len(set(ids)) - len(moved)
        if skipped:
            message += CARRY_SKIPPED.format(count=skipped)
        return {
            "plan": plan_panel(s, ctx, filter_project, message=message),
            "board": task_board(s, ctx, filter_project),
        }


@router.post("/tasks/carry", response_class=HTMLResponse)
def carry(request: Request, ctx: Ctx, ids: FormText = "", project: FormText = "") -> HTMLResponse:
    wanted = _carry_ids(ids)
    selected = project.strip()
    try:
        page = _carry(ctx, wanted, selected)
    except ConflictError as error:
        with ctx.session() as s:
            page = {
                "plan": plan_panel(s, ctx, selected, message=str(error), is_error=True),
                "board": task_board(s, ctx, selected),
            }
        return render_error(request, error, PLAN_TEMPLATE, page, headers={"HX-Push-Url": "false"})
    return render(request, PLAN_TEMPLATE, page)
