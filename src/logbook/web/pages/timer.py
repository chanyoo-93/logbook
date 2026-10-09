"""타이머 패널: 표시(GET /timer), 경과 갱신(GET /timer/elapsed), 정지(POST /timer/stop)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import HTMLResponse

from logbook.core import services
from logbook.core.duration import format_duration
from logbook.core.errors import LogbookError
from logbook.core.weeks import total_label
from logbook.web.context import WebContext, get_context
from logbook.web.errors import classify
from logbook.web.pages.panels import refreshed_panels
from logbook.web.pages.templating import render
from logbook.web.pages.views import TimerView, record_text, timer_view

router = APIRouter()

PANEL_TEMPLATE = "partials/timer.html"
STOP_TEMPLATE = "partials/timer_stop_response.html"
ELAPSED_TEMPLATE = "partials/timer_elapsed.html"
RESULT_MARK = "✔"
# 경과 갱신 중 타이머가 사라졌을 때(CLI에서 정지 등) 요소 대신 패널 전체를 바꾼다.
PANEL_RETARGET = {"HX-Retarget": "#timer", "HX-Reswap": "outerHTML"}

Ctx = Annotated[WebContext, Depends(get_context)]


def _current_timer(ctx: WebContext) -> TimerView | None:
    now = ctx.now()
    with ctx.session() as s:
        timer = services.get_timer(s)
        return timer_view(timer, now) if timer is not None else None


@router.get("/timer", response_class=HTMLResponse)
def timer_panel(request: Request, ctx: Ctx) -> HTMLResponse:
    return render(request, PANEL_TEMPLATE, {"timer": _current_timer(ctx)})


@router.get("/timer/elapsed", response_class=HTMLResponse)
def timer_elapsed(request: Request, ctx: Ctx) -> HTMLResponse:
    timer = _current_timer(ctx)
    if timer is None:
        return render(request, PANEL_TEMPLATE, {"timer": None}, headers=PANEL_RETARGET)
    return render(request, ELAPSED_TEMPLATE, {"timer": timer})


@router.post("/timer/stop", response_class=HTMLResponse)
def stop_timer(request: Request, ctx: Ctx) -> HTMLResponse:
    now = ctx.now()
    try:
        with ctx.session() as s:
            stopped = services.stop_timer(s, now=now)
            day_total = services.day_total_minutes(s, stopped.log.date)
            message = (
                f"{RESULT_MARK} {record_text(stopped.log, with_date=False)} "
                f"({total_label(stopped.log.date, now.date())} 누적 {format_duration(day_total)})"
            )
            page = {
                **refreshed_panels(s, ctx, now),
                "timer": None,
                "timer_message": message,
                "timer_error": False,
            }
    except LogbookError as error:
        # 실패해도 DB는 그대로이므로 현재 상태로 패널을 다시 그린다.
        context = {
            "timer": _current_timer(ctx),
            "timer_message": str(error),
            "timer_error": True,
        }
        return render(request, PANEL_TEMPLATE, context, status_code=classify(error).status)
    return render(request, STOP_TEMPLATE, page)
