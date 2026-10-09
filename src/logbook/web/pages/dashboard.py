"""대시보드(GET /)와 빠른 기록(POST /logs)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form
from starlette.requests import Request
from starlette.responses import HTMLResponse

from logbook.core import services
from logbook.core.duration import format_duration, parse_duration
from logbook.core.errors import InvalidInputError, LogbookError
from logbook.core.ids import parse_id
from logbook.core.weeks import total_label, week_of
from logbook.web.context import WebContext, get_context
from logbook.web.errors import classify
from logbook.web.pages.panels import quick_form_context, refreshed_panels
from logbook.web.pages.summary import build_summary
from logbook.web.pages.templating import render
from logbook.web.pages.views import (
    RECENT_LIMIT,
    QuickFormValues,
    log_row,
    record_text,
    timer_view,
)

router = APIRouter()

QUICK_FORM_TEMPLATE = "partials/quick_form_response.html"
DURATION_REQUIRED = "시간을 입력하세요. 예: 2h, 90m, 1:30"
CATEGORY_REQUIRED = "카테고리를 고르세요. 태스크를 고르면 태스크의 카테고리를 씁니다."
TASK_LABEL = "태스크"
RESULT_MARK = "✔"

Field = Annotated[str, Form()]


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, ctx: Annotated[WebContext, Depends(get_context)]) -> HTMLResponse:
    now = ctx.now()
    week = week_of(now.date(), ctx.cfg.week_start)
    with ctx.session() as s:
        summary = build_summary(s, ctx, week, now)
        timer = services.get_timer(s)
        timer_data = timer_view(timer, now) if timer is not None else None
        rows = [log_row(log) for log in services.recent_worklogs(s, limit=RECENT_LIMIT)]
        form = quick_form_context(s, ctx, QuickFormValues())
    return render(
        request,
        "dashboard.html",
        {
            "active": "dashboard",
            "summary": summary,
            "timer": timer_data,
            "rows": rows,
            **form,
        },
    )


def _add_log(ctx: WebContext, values: QuickFormValues) -> dict[str, object]:
    """폼 값을 검증해 기록을 저장하고, 성공 응답에 필요한 템플릿 값을 돌려준다."""
    if not values.duration.strip():
        raise InvalidInputError(DURATION_REQUIRED)
    if not values.category and not values.task:
        raise InvalidInputError(CATEGORY_REQUIRED)
    minutes = parse_duration(values.duration)
    task_id = parse_id(values.task, TASK_LABEL) if values.task else None
    now = ctx.now()
    today = now.date()
    with ctx.session() as s:
        log = services.add_worklog(
            s,
            minutes=minutes,
            note=values.note,
            project_slug=values.project or None,
            category=values.category or None,
            task_id=task_id,
            default_project=ctx.cfg.default_project,
            today=today,
            allowed_categories=tuple(ctx.cfg.categories),
        )
        s.flush()
        day_total = services.day_total_minutes(s, log.date)
        message = (
            f"{RESULT_MARK} {record_text(log, with_date=False)} "
            f"({total_label(log.date, today)} 누적 {format_duration(day_total)})"
        )
        kept = QuickFormValues(project=values.project, category=values.category, task=values.task)
        return {
            **refreshed_panels(s, ctx, now),
            **quick_form_context(s, ctx, kept, message=message),
        }


@router.post("/logs", response_class=HTMLResponse)
def add_log(
    request: Request,
    ctx: Annotated[WebContext, Depends(get_context)],
    duration: Field = "",
    note: Field = "",
    project: Field = "",
    category: Field = "",
    task: Field = "",
) -> HTMLResponse:
    values = QuickFormValues(duration, note, project, category, task)
    try:
        page = _add_log(ctx, values)
    except LogbookError as error:
        with ctx.session() as s:
            form = quick_form_context(s, ctx, values, message=str(error), is_error=True)
        return render(request, QUICK_FORM_TEMPLATE, form, status_code=classify(error).status)
    return render(request, QUICK_FORM_TEMPLATE, page)
