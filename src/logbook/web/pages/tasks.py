"""태스크 화면: 칸반 보드(GET /tasks), 상태 변경(POST /tasks/{id}/status),
등록 화면(GET /tasks/new)과 저장(POST /tasks), 수정 화면(GET /tasks/{id}/edit)과 저장
(PATCH /tasks/{id}), 이월(POST /tasks/carry).

등록·수정 화면은 전체 페이지의 폼이다. 저장에 성공하면 HX-Redirect로 보드(필터 유지)로 보낸다.
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
from logbook.core.weeks import parse_date, parse_week, week_of
from logbook.web.context import TASK_LABEL, Ctx, WebContext
from logbook.web.errors import TASK_CHANGED, ConflictError
from logbook.web.htmx import is_htmx
from logbook.web.pages.forms import FormText, QueryText
from logbook.web.pages.panels import NO_CHANGE, RESULT_MARK
from logbook.web.pages.task_views import (
    CARRY_CONFIRM,
    DROP_CONFIRM,
    STATUS_LABELS,
    TaskFormValues,
    board_url,
    edit_url,
    edit_values,
    plan_panel,
    task_board,
    task_filter_view,
    task_form_view,
    task_version,
)
from logbook.web.pages.templating import render, render_error

if TYPE_CHECKING:
    from datetime import date

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
FORM_TEMPLATE = "partials/task_form.html"
NEW_TEMPLATE = "task_new.html"
EDIT_TEMPLATE = "task_edit.html"
PLAN_TEMPLATE = "partials/task_plan_response.html"
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
def tasks_page(
    request: Request,
    ctx: Ctx,
    project: QueryText = "",
    added: QueryText = "",
    updated: QueryText = "",
) -> HTMLResponse:
    selected = project.strip()
    try:
        with ctx.session() as s:
            message = _saved_message(s, added, updated)
            board = task_board(s, ctx, selected, message=message)
            plan = plan_panel(s, ctx, selected)
            filters = task_filter_view(s, selected)
    except NotFoundError as error:
        if is_htmx(request):
            raise  # 알림 영역에 쓴다 (공통 오류 처리)
        with ctx.session() as s:
            filters = task_filter_view(s, selected)
        context = {
            "active": "tasks",
            "filters": filters,
            "board": None,
            "plan": None,
            "error": str(error),
        }
        return render_error(request, error, PAGE_TEMPLATE, context)
    if is_htmx(request):
        return render(request, BOARD_TEMPLATE, {"board": board, "plan": plan})
    context = {"active": "tasks", "filters": filters, "board": board, "plan": plan}
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


def _saved_task(s: Session, raw: str) -> Task | None:
    """?added=·?updated= 값이 가리키는 태스크. 숫자가 아니거나 없는 ID면 None(오류 아님)."""
    if not raw.strip():
        return None
    try:
        return services.get_task(s, parse_id(raw, TASK_LABEL))
    except (InvalidInputError, NotFoundError):
        return None


def _saved_message(s: Session, added: str, updated: str) -> str:
    """저장 뒤 보드로 돌아왔을 때 보여 줄 결과 줄. 없으면 ''."""
    task = _saved_task(s, added)
    if task is not None:
        details = _added_details(task.estimate_minutes, task.planned_week)
        return TASK_ADDED.format(
            id=task.id, project=task.project.slug, title=task.title, details=details
        )
    task = _saved_task(s, updated)
    if task is None:
        return ""
    return TASK_UPDATED.format(id=task.id, project=task.project.slug, title=task.title)


def _redirect(url: str) -> HTMLResponse:
    """저장에 성공하면 htmx가 보드로 옮겨 가게 한다(전체 페이지 이동)."""
    return HTMLResponse("", headers={"HX-Redirect": url})


def _parsed_inputs(
    ctx: WebContext, values: TaskFormValues
) -> tuple[int | None, Week | None, date | None]:
    """예상·계획 주차·마감일 입력을 core 파서로 읽는다. 비었으면 None."""
    today, week_start = ctx.today(), ctx.cfg.week_start
    estimate = (
        parse_duration(values.estimate, max_minutes=None) if values.estimate.strip() else None
    )
    planned = (
        parse_week(values.week, today=today, week_start=week_start) if values.week.strip() else None
    )
    due = parse_date(values.due, today=today, week_start=week_start) if values.due.strip() else None
    return estimate, planned, due


def _add_task(ctx: WebContext, values: TaskFormValues) -> int:
    """폼 값을 검증해 태스크를 저장하고 ID를 돌려준다."""
    estimate, planned, due = _parsed_inputs(ctx, values)
    with ctx.session() as s:
        task = services.create_task(
            s,
            title=values.title,
            project_slug=values.task_project.strip() or ctx.cfg.default_project,
            category=values.task_category.strip() or None,
            estimate_minutes=estimate,
            planned_week=planned,
            due_date=due,
            external_ref=values.external_ref,
            description=values.description,
            allowed_categories=tuple(ctx.cfg.categories),
        )
        return task.id


def _form_error(
    request: Request,
    ctx: WebContext,
    error: LogbookError,
    values: TaskFormValues,
    filter_project: str,
    task_id: int | None = None,
) -> HTMLResponse:
    """입력 문제나 버전 충돌은 폼을 입력값 그대로 다시 그린다. 문구는 폼 아래와 #flash에 둔다."""
    with ctx.session() as s:
        task = None if task_id is None else services.get_task(s, task_id)
        reopen = ""
        if isinstance(error, ConflictError) and task is not None:
            reopen = edit_url(task.id, filter_project)
        form = task_form_view(
            s,
            ctx,
            values,
            filter_project=filter_project,
            task=task,
            message=str(error),
            is_error=True,
            reopen_url=reopen,
        )
    return render_error(request, error, FORM_TEMPLATE, {"form": form})


@router.get("/tasks/new", response_class=HTMLResponse)
def task_new_page(request: Request, ctx: Ctx, project: QueryText = "") -> HTMLResponse:
    selected = project.strip()
    with ctx.session() as s:
        form = task_form_view(s, ctx, TaskFormValues(), filter_project=selected)
    return render(request, NEW_TEMPLATE, {"active": "tasks", "form": form})


@router.post("/tasks", response_class=HTMLResponse)
def add_task(
    request: Request,
    ctx: Ctx,
    title: FormText = "",
    task_project: FormText = "",
    task_category: FormText = "",
    estimate: FormText = "",
    week: FormText = "",
    due: FormText = "",
    external_ref: FormText = "",
    description: FormText = "",
    project: FormText = "",
) -> HTMLResponse:
    values = TaskFormValues(
        title=title,
        task_project=task_project,
        task_category=task_category,
        estimate=estimate,
        week=week,
        due=due,
        external_ref=external_ref,
        description=description,
    )
    selected = project.strip()
    try:
        task_id = _add_task(ctx, values)
    except LogbookError as error:
        return _form_error(request, ctx, error, values, selected)
    return _redirect(board_url(selected, added=task_id))


@router.get("/tasks/{task_id}/edit", response_class=HTMLResponse)
def task_edit_page(
    request: Request, ctx: Ctx, task_id: str, project: QueryText = ""
) -> HTMLResponse:
    number = parse_id(task_id, TASK_LABEL)
    selected = project.strip()
    with ctx.session() as s:
        task = services.get_task(s, number)
        form = task_form_view(s, ctx, edit_values(task), filter_project=selected, task=task)
    return render(request, EDIT_TEMPLATE, {"active": "tasks", "form": form})


def _clean(text: str) -> str | None:
    """core의 정리 규칙과 같다: 줄바꿈을 LF로 바꾸고 앞뒤 공백을 지운다. 비면 None."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip() or None


def _changes(
    task: Task, form: TaskFormValues, estimate: int | None, week: Week | None, due: date | None
) -> dict[str, Any]:
    """폼 값 중 태스크와 다른 것만 update_task 인자로 고른다."""
    changes: dict[str, Any] = {}
    category = form.task_category.strip() or None
    if form.title.strip() != task.title:
        changes["title"] = form.title
    if category != task.category:
        changes["category"] = category
    if estimate != task.estimate_minutes:
        changes["estimate_minutes"] = estimate
    if (None if week is None else week.label) != task.planned_week:
        changes["planned_week"] = week
    if due != task.due_date:
        changes["due_date"] = due
    if _clean(form.external_ref) != task.external_ref:
        changes["external_ref"] = form.external_ref
    if _clean(form.description) != task.description:
        changes["description"] = form.description
    return changes


def _apply_update(ctx: WebContext, number: int, form: TaskFormValues) -> bool:
    """버전을 확인하고 바뀐 값과 상태를 저장한다. 바뀐 것이 있으면 True."""
    estimate, week, due = _parsed_inputs(ctx, form)
    new_status = parse_status(form.status) if form.status.strip() else None
    with ctx.session() as s:
        task = services.get_task(s, number)
        if task_version(task) != form.version:
            raise ConflictError(TASK_CHANGED.format(id=task.id))
        changes = _changes(task, form, estimate, week, due)
        if changes:
            task = services.update_task(
                s, number, **changes, allowed_categories=tuple(ctx.cfg.categories)
            )
        status_changed = new_status is not None and new_status != task.status
        if new_status is not None and status_changed:
            services.set_task_status(s, number, new_status)
        return bool(changes) or status_changed


@router.patch("/tasks/{task_id}", response_class=HTMLResponse)
def patch_task(
    request: Request,
    ctx: Ctx,
    task_id: str,
    title: FormText = "",
    task_category: FormText = "",
    estimate: FormText = "",
    week: FormText = "",
    due: FormText = "",
    external_ref: FormText = "",
    description: FormText = "",
    status: FormText = "",
    version: FormText = "",
    project: FormText = "",
) -> HTMLResponse:
    number = parse_id(task_id, TASK_LABEL)
    selected = project.strip()
    form = TaskFormValues(
        title=title,
        task_category=task_category,
        estimate=estimate,
        week=week,
        due=due,
        external_ref=external_ref,
        description=description,
        status=status,
        version=version,
    )
    try:
        changed = _apply_update(ctx, number, form)
    except (InvalidInputError, ConflictError) as error:
        return _form_error(request, ctx, error, form, selected, number)
    if changed:
        return _redirect(board_url(selected, updated=number))
    with ctx.session() as s:  # 바뀐 것이 없으면 화면에 머물며 알린다
        task = services.get_task(s, number)
        view = task_form_view(
            s, ctx, edit_values(task), filter_project=selected, task=task, message=NO_CHANGE
        )
    return render(request, FORM_TEMPLATE, {"form": view})


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
