"""대시보드(GET /). 빠른 기록(POST /logs)은 Task 5-7에서 더한다."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import HTMLResponse

from logbook.core import services
from logbook.core.weeks import week_of
from logbook.web.context import WebContext, get_context
from logbook.web.pages.summary import build_summary
from logbook.web.pages.templating import render
from logbook.web.pages.views import RECENT_LIMIT, log_row, timer_view

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, ctx: Annotated[WebContext, Depends(get_context)]) -> HTMLResponse:
    now = ctx.now()
    week = week_of(now.date(), ctx.cfg.week_start)
    with ctx.session() as s:
        summary = build_summary(s, ctx, week, now)
        timer = services.get_timer(s)
        timer_data = timer_view(timer, now) if timer is not None else None
        rows = [log_row(log) for log in services.recent_worklogs(s, limit=RECENT_LIMIT)]
    return render(
        request,
        "dashboard.html",
        {"active": "dashboard", "summary": summary, "timer": timer_data, "rows": rows},
    )
