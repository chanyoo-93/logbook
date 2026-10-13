"""태스크 화면: 칸반 보드(GET /tasks), 상태 변경(POST /tasks/{id}/status), 추가(POST /tasks).

상태 변경은 화면이 본 태스크 버전(task_version)이 지금 태스크와 같을 때만 한다.
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
from logbook.core.errors import LogbookError, NotFoundError
from logbook.core.ids import parse_id
from logbook.core.taskstatus import TaskStatus, parse_status
from logbook.core.weeks import parse_week
from logbook.web.context import TASK_LABEL, Ctx, WebContext
from logbook.web.errors import TASK_CHANGED, ConflictError
from logbook.web.htmx import is_htmx
from logbook.web.pages.forms import FormText, QueryText
from logbook.web.pages.panels import RESULT_MARK
from logbook.web.pages.task_views import (
    DROP_CONFIRM,
    STATUS_LABELS,
    TaskFormValues,
    task_board,
    task_filter_view,
    task_form_view,
    task_version,
)
from logbook.web.pages.templating import render, render_error

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from logbook.core.models import Task

__all__ = ["DROP_CONFIRM", "STATUS_CHANGED", "TASK_ADDED", "router"]

router = APIRouter()

PAGE_TEMPLATE = "tasks.html"
BOARD_TEMPLATE = "partials/task_board_response.html"
FORM_TEMPLATE = "partials/task_form_response.html"
TASK_ADDED = f"{RESULT_MARK} 태스크 추가: #{{id}} {{project}} · {{title}}{{details}}"
STATUS_CHANGED = f"{RESULT_MARK} #{{id}} {{old}} → {{new}}: {{project}} · {{title}}{{tail}}"


@router.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request, ctx: Ctx, project: QueryText = "") -> HTMLResponse:
    selected = project.strip()
    try:
        with ctx.session() as s:
            board = task_board(s, ctx, selected)
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
            "error": str(error),
        }
        return render_error(request, error, PAGE_TEMPLATE, context)
    if is_htmx(request):
        return render(request, BOARD_TEMPLATE, {"board": board})
    context = {"active": "tasks", "form": form, "filters": filters, "board": board}
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
    return render(request, BOARD_TEMPLATE, {"board": board})


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
        return render_error(request, error, FORM_TEMPLATE, {"form": form, "board": None})
    return render(request, FORM_TEMPLATE, page)
