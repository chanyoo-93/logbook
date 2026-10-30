"""대시보드(GET /)와 빠른 기록(POST /logs)."""

from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse

from logbook.core import services
from logbook.core.duration import parse_duration
from logbook.core.errors import InvalidInputError, LogbookError
from logbook.core.ids import parse_id
from logbook.core.weeks import week_of
from logbook.web.context import TASK_LABEL, Ctx, WebContext
from logbook.web.pages.forms import FormText
from logbook.web.pages.panels import (
    CATEGORY_REQUIRED,
    quick_form_context,
    refreshed_panels,
    result_line,
    timer_panel_context,
)
from logbook.web.pages.summary import build_summary
from logbook.web.pages.templating import render, render_error
from logbook.web.pages.views import RECENT_LIMIT, QuickFormValues, log_row

router = APIRouter()

QUICK_FORM_TEMPLATE = "partials/quick_form_response.html"
DURATION_REQUIRED = "시간을 입력하세요. 예: 2h, 90m, 1:30. 시간을 재려면 타이머 시작을 누르세요."


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, ctx: Ctx) -> HTMLResponse:
    now = ctx.now()
    week = week_of(now.date(), ctx.cfg.week_start)
    with ctx.session() as s:
        summary = build_summary(s, ctx, week, now)
        timer_panel = timer_panel_context(s, now)
        rows = [log_row(log) for log in services.recent_worklogs(s, limit=RECENT_LIMIT)]
        form = quick_form_context(s, ctx, QuickFormValues())
    return render(
        request,
        "dashboard.html",
        {
            "active": "dashboard",
            "summary": summary,
            **timer_panel,
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
        message = result_line(s, log, today)
        kept = QuickFormValues(project=values.project, category=values.category, task=values.task)
        return {
            **refreshed_panels(s, ctx, now),
            **quick_form_context(s, ctx, kept, message=message),
        }


@router.post("/logs", response_class=HTMLResponse)
def add_log(
    request: Request,
    ctx: Ctx,
    duration: FormText = "",
    note: FormText = "",
    project: FormText = "",
    category: FormText = "",
    task: FormText = "",
) -> HTMLResponse:
    values = QuickFormValues(duration, note, project, category, task)
    try:
        page = _add_log(ctx, values)
    except LogbookError as error:
        with ctx.session() as s:
            form = quick_form_context(s, ctx, values, message=str(error), is_error=True)
        return render_error(request, error, QUICK_FORM_TEMPLATE, form)
    return render(request, QUICK_FORM_TEMPLATE, page)
