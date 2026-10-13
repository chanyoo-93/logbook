"""타이머 패널: 표시(GET /timer), 경과 갱신(GET /timer/elapsed), 정지(POST /timer/stop)."""

from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse

from logbook.core import services
from logbook.core.errors import LogbookError
from logbook.web.context import Ctx, WebContext
from logbook.web.pages.panels import refreshed_panels, result_line
from logbook.web.pages.templating import render, render_error
from logbook.web.pages.views import TimerView, timer_view

router = APIRouter()

PANEL_TEMPLATE = "partials/timer.html"
STOP_TEMPLATE = "partials/timer_stop_response.html"
ELAPSED_TEMPLATE = "partials/timer_elapsed.html"
# 경과 갱신 중 타이머가 사라졌을 때(CLI에서 정지 등) 요소 대신 패널 전체를 바꾼다.
PANEL_RETARGET = {"HX-Retarget": "#timer", "HX-Reswap": "outerHTML"}


def _current_timer(ctx: WebContext) -> TimerView | None:
    now = ctx.now()
    with ctx.session() as s:
        timer = services.get_timer(s)
        return timer_view(timer, now) if timer is not None else None


@router.get("/timer", response_class=HTMLResponse)
def timer_panel(request: Request, ctx: Ctx) -> HTMLResponse:
    # 지금 화면은 /timer/elapsed만 폴링한다. 타이머 패널 전체를 다시 그릴 때 쓰는 조각이다.
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
            message = result_line(s, stopped.log, now.date())
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
        return render_error(request, error, PANEL_TEMPLATE, context)
    return render(request, STOP_TEMPLATE, page)
