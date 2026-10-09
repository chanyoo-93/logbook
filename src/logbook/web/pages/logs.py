"""기록 페이지: 목록·필터(GET /logs), 행 조각, 인라인 수정(PATCH), 삭제(DELETE).

수정·삭제는 화면이 본 기록 버전(worklog_version)이 지금 기록과 같을 때만 한다.
DB 없이 끝나는 검증을 먼저 하고, 나머지는 세션 하나 안에서 한다. 중간에 오류가 나면
모두 롤백되어 DB가 바뀌지 않는다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import HTMLResponse

from logbook.core import services
from logbook.core.duration import parse_duration
from logbook.core.errors import InvalidInputError, LogbookError
from logbook.core.ids import parse_id
from logbook.core.weeks import Week, parse_date, parse_week
from logbook.web.context import WebContext, get_context
from logbook.web.errors import RECORD_CHANGED, ConflictError
from logbook.web.htmx import is_htmx
from logbook.web.pages.forms import FormText, QueryText
from logbook.web.pages.panels import RESULT_MARK
from logbook.web.pages.templating import render, render_error
from logbook.web.pages.views import (
    LogEditValues,
    LogFilter,
    edit_values,
    log_edit_view,
    log_filter_view,
    log_row,
    log_table_view,
    record_text,
    worklog_version,
)

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

    from logbook.core.models import WorkLog

router = APIRouter()

PAGE_TEMPLATE = "logs.html"
TABLE_TEMPLATE = "partials/log_table_response.html"
ROW_TEMPLATE = "partials/log_row.html"
EDIT_TEMPLATE = "partials/log_edit_row.html"
DEFAULT_WEEK = "this"
NO_CHANGE = "바뀐 내용이 없습니다."
UPDATED = f"{RESULT_MARK} 수정했습니다: {{record}}"
DELETED = f"{RESULT_MARK} 삭제했습니다: {{record}}"
LOG_LABEL = "기록"
TASK_LABEL = "태스크"

Ctx = Annotated[WebContext, Depends(get_context)]


def _filter(week: str, project: str, category: str) -> LogFilter:
    """빈 값과 공백뿐인 값은 생략한 것으로 본다."""
    return LogFilter(week.strip(), project.strip(), category.strip())


def _parse_week(ctx: WebContext, values: LogFilter) -> Week:
    return parse_week(values.week or DEFAULT_WEEK, today=ctx.today(), week_start=ctx.cfg.week_start)


def _table_page(
    s: Session,
    ctx: WebContext,
    week: Week,
    values: LogFilter,
    *,
    message: str = "",
) -> dict[str, Any]:
    """필터에 맞는 표와 필터 폼의 템플릿 값. 없는 프로젝트 필터는 NotFoundError다."""
    logs = services.list_worklogs(
        s,
        week=week,
        project_slug=values.project or None,
        category=values.category or None,
    )
    return {
        "table": log_table_view(week, logs, message=message),
        "filters": log_filter_view(s, ctx.cfg, week, values),
    }


def _load_checked(s: Session, number: int, values: LogFilter, version: str) -> WorkLog:
    """세션 안의 앞부분 검증: 필터 프로젝트 확인 -> 기록 조회 -> 버전 확인(다르면 409)."""
    if values.project:
        services.get_project(s, values.project)
    log = services.get_worklog(s, number)
    if worklog_version(log) != version:
        raise ConflictError(RECORD_CHANGED.format(id=log.id))
    return log


@router.get("/logs", response_class=HTMLResponse)
def logs_page(
    request: Request,
    ctx: Ctx,
    week: QueryText = "",
    project: QueryText = "",
    category: QueryText = "",
) -> HTMLResponse:
    values = _filter(week, project, category)
    try:
        parsed = _parse_week(ctx, values)
        with ctx.session() as s:
            page = _table_page(s, ctx, parsed, values)
    except InvalidInputError as error:
        if is_htmx(request):
            raise  # 알림 영역에 쓴다 (공통 오류 처리)
        with ctx.session() as s:
            filters = log_filter_view(s, ctx.cfg, None, values)
        context = {"active": "logs", "filters": filters, "table": None, "error": str(error)}
        return render_error(request, error, PAGE_TEMPLATE, context)
    if is_htmx(request):
        return render(request, TABLE_TEMPLATE, {**page, "oob": True})
    return render(request, PAGE_TEMPLATE, {"active": "logs", **page})


@router.get("/logs/{log_id}/row", response_class=HTMLResponse)
def log_row_fragment(request: Request, ctx: Ctx, log_id: str) -> HTMLResponse:
    number = parse_id(log_id, LOG_LABEL)
    with ctx.session() as s:
        row = log_row(services.get_worklog(s, number))
    return render(request, ROW_TEMPLATE, {"row": row})


@router.get("/logs/{log_id}/edit", response_class=HTMLResponse)
def log_edit_fragment(request: Request, ctx: Ctx, log_id: str) -> HTMLResponse:
    number = parse_id(log_id, LOG_LABEL)
    with ctx.session() as s:
        log = services.get_worklog(s, number)
        edit = log_edit_view(s, ctx.cfg, log, edit_values(log))
    return render(request, EDIT_TEMPLATE, {"edit": edit})


def _changes(
    log: WorkLog, form: LogEditValues, minutes: int, work_date: date, task_id: int | None
) -> dict[str, Any]:
    """폼 값 중 기록과 다른 것만 update_worklog 인자로 고른다(CLI lb log edit처럼)."""
    changes: dict[str, Any] = {}
    if minutes != log.minutes:
        changes["minutes"] = minutes
    if form.note.strip() != log.note:
        changes["note"] = form.note
    if work_date != log.date:
        changes["work_date"] = work_date
    if form.log_project.strip() != log.project.slug:
        changes["project_slug"] = form.log_project.strip()
    if form.log_category.strip() != log.category:
        changes["category"] = form.log_category.strip()
    if task_id is None:
        if log.task_id is not None:
            changes["clear_task"] = True
    elif task_id != log.task_id:
        changes["task_id"] = task_id
    return changes


def _apply_edit(
    ctx: WebContext, log_id: str, form: LogEditValues, values: LogFilter
) -> dict[str, Any]:
    number = parse_id(log_id, LOG_LABEL)
    week = _parse_week(ctx, values)
    minutes = parse_duration(form.duration)
    work_date = parse_date(form.log_date, today=ctx.today(), week_start=ctx.cfg.week_start)
    task_id = parse_id(form.log_task, TASK_LABEL) if form.log_task.strip() else None
    with ctx.session() as s:
        log = _load_checked(s, number, values, form.version)
        changes = _changes(log, form, minutes, work_date, task_id)
        message = NO_CHANGE
        if changes:
            log = services.update_worklog(
                s, number, **changes, allowed_categories=tuple(ctx.cfg.categories)
            )
            message = UPDATED.format(record=record_text(log, with_date=True))
        return _table_page(s, ctx, week, values, message=message)


def _edit_error(
    request: Request, ctx: WebContext, log_id: str, form: LogEditValues, error: LogbookError
) -> HTMLResponse:
    """입력 문제나 버전 충돌은 편집 행에 오류 줄을 달아 그 자리에 다시 그린다."""
    number = parse_id(log_id, LOG_LABEL)
    with ctx.session() as s:
        log = services.get_worklog(s, number)
        edit = log_edit_view(s, ctx.cfg, log, form, error=str(error))
    headers = {"HX-Retarget": f"#log-{number}", "HX-Reswap": "outerHTML", "HX-Push-Url": "false"}
    return render_error(request, error, EDIT_TEMPLATE, {"edit": edit}, headers=headers)


@router.patch("/logs/{log_id}", response_class=HTMLResponse)
def patch_log(
    request: Request,
    ctx: Ctx,
    log_id: str,
    duration: FormText = "",
    note: FormText = "",
    log_date: FormText = "",
    log_project: FormText = "",
    log_category: FormText = "",
    log_task: FormText = "",
    version: FormText = "",
    week: FormText = "",
    project: FormText = "",
    category: FormText = "",
) -> HTMLResponse:
    form = LogEditValues(duration, note, log_date, log_project, log_category, log_task, version)
    try:
        page = _apply_edit(ctx, log_id, form, _filter(week, project, category))
    except (InvalidInputError, ConflictError) as error:
        return _edit_error(request, ctx, log_id, form, error)
    return render(request, TABLE_TEMPLATE, {**page, "oob": True})


@router.delete("/logs/{log_id}", response_class=HTMLResponse)
def delete_log(
    request: Request,
    ctx: Ctx,
    log_id: str,
    version: QueryText = "",
    week: QueryText = "",
    project: QueryText = "",
    category: QueryText = "",
) -> HTMLResponse:
    values = _filter(week, project, category)
    number = parse_id(log_id, LOG_LABEL)
    parsed = _parse_week(ctx, values)
    with ctx.session() as s:
        log = _load_checked(s, number, values, version)
        record = record_text(log, with_date=True)
        services.delete_worklog(s, number)
        page = _table_page(s, ctx, parsed, values, message=DELETED.format(record=record))
    return render(request, TABLE_TEMPLATE, {**page, "oob": True})
