"""타이머 패널: 표시(GET /timer), 경과 갱신(GET /timer/elapsed), 시작·정지·취소(POST)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse

from logbook.core import services
from logbook.core.errors import InvalidInputError, LogbookError, NotFoundError
from logbook.core.ids import parse_id
from logbook.web.context import TASK_LABEL, Ctx, WebContext
from logbook.web.errors import TIMER_CHANGED, ConflictError
from logbook.web.pages.forms import FormText
from logbook.web.pages.panels import (
    CATEGORY_REQUIRED,
    NOTE_REQUIRED,
    RESULT_MARK,
    refreshed_panels,
    result_line,
    timer_panel_context,
)
from logbook.web.pages.templating import render, render_error
from logbook.web.pages.views import TimerStartValues, timer_version, timer_view

router = APIRouter()

PANEL_TEMPLATE = "partials/timer.html"
STOP_TEMPLATE = "partials/timer_stop_response.html"
ELAPSED_TEMPLATE = "partials/timer_elapsed.html"
# 경과 갱신 중 타이머가 사라졌을 때(CLI에서 정지 등) 요소 대신 패널 전체를 바꾼다.
PANEL_RETARGET = {"HX-Retarget": "#timer", "HX-Reswap": "outerHTML"}
TIMER_STARTED = f"{RESULT_MARK} 타이머 시작: {{scope}} — {{note}} ({{started}})"
TASK_STARTED = " (태스크 #{id}: 할 일 → 진행)"
TIMER_CANCELED = f"{RESULT_MARK} 타이머를 버렸습니다: {{scope}} — {{note}} (경과 {{elapsed}})"


def _panel(
    ctx: WebContext,
    *,
    values: TimerStartValues | None = None,
    message: str = "",
    is_error: bool = False,
) -> dict[str, Any]:
    """지금 DB 상태로 패널 값을 만든다(오류 응답에서 패널을 다시 그릴 때 쓴다)."""
    with ctx.session() as s:
        return timer_panel_context(
            s, ctx, ctx.now(), values=values, message=message, is_error=is_error
        )


@router.get("/timer", response_class=HTMLResponse)
def timer_panel(request: Request, ctx: Ctx) -> HTMLResponse:
    # 지금 화면은 /timer/elapsed만 폴링한다. 타이머 패널 전체를 다시 그릴 때 쓰는 조각이다.
    return render(request, PANEL_TEMPLATE, _panel(ctx))


@router.get("/timer/elapsed", response_class=HTMLResponse)
def timer_elapsed(request: Request, ctx: Ctx) -> HTMLResponse:
    panel = _panel(ctx)
    if panel["timer"] is None:
        return render(request, PANEL_TEMPLATE, panel, headers=PANEL_RETARGET)
    return render(request, ELAPSED_TEMPLATE, {"timer": panel["timer"]})


def _start(ctx: WebContext, values: TimerStartValues) -> dict[str, Any]:
    """폼 값을 검증해 타이머를 시작하고, 성공 응답의 패널 값을 돌려준다."""
    task_text = values.task.strip()
    note = values.note.strip()
    if not task_text and not note:
        raise InvalidInputError(NOTE_REQUIRED)
    if not task_text and not values.category:
        raise InvalidInputError(CATEGORY_REQUIRED)
    task_id = parse_id(task_text, TASK_LABEL) if task_text else None
    now = ctx.now()
    with ctx.session() as s:
        started = services.start_timer(
            s,
            now=now,
            note=note or None,
            project_slug=values.project or None,
            category=values.category or None,
            task_id=task_id,
            allowed_categories=tuple(ctx.cfg.categories),
            default_project=ctx.cfg.default_project,
        )
        view = timer_view(started.timer, now)
        message = TIMER_STARTED.format(scope=view.scope, note=view.note, started=view.started)
        if started.task_started:
            message += TASK_STARTED.format(id=started.timer.task_id)
        return timer_panel_context(s, ctx, now, message=message)


@router.post("/timer/start", response_class=HTMLResponse)
def start_timer(
    request: Request,
    ctx: Ctx,
    note: FormText = "",
    project: FormText = "",
    category: FormText = "",
    task: FormText = "",
) -> HTMLResponse:
    values = TimerStartValues(note, project, category, task)
    try:
        panel = _start(ctx, values)
    except LogbookError as error:
        # 실패해도 DB는 그대로다. 그사이 CLI가 시작했다면 진행 중 패널이,
        # 아니면 입력값을 채운 폼이 나온다.
        context = _panel(ctx, values=values, message=str(error), is_error=True)
        return render_error(request, error, PANEL_TEMPLATE, context)
    return render(request, PANEL_TEMPLATE, panel)


@router.post("/timer/stop", response_class=HTMLResponse)
def stop_timer(request: Request, ctx: Ctx) -> HTMLResponse:
    now = ctx.now()
    try:
        with ctx.session() as s:
            stopped = services.stop_timer(s, now=now)
            message = result_line(s, stopped.log, now.date())
            page = {
                **refreshed_panels(s, ctx, now),
                **timer_panel_context(s, ctx, now, message=message),
            }
    except LogbookError as error:
        # 실패해도 DB는 그대로이므로 현재 상태로 패널을 다시 그린다.
        context = _panel(ctx, message=str(error), is_error=True)
        return render_error(request, error, PANEL_TEMPLATE, context)
    return render(request, STOP_TEMPLATE, page)


def _cancel(ctx: WebContext, version: str) -> dict[str, Any]:
    """화면이 본 타이머가 그대로일 때만 기록 없이 버린다."""
    now = ctx.now()
    with ctx.session() as s:
        timer = services.get_timer(s)
        if timer is None:
            raise NotFoundError(services.NO_TIMER_MESSAGE)
        if timer_version(timer) != version:
            raise ConflictError(TIMER_CHANGED)
        view = timer_view(timer, now)
        services.cancel_timer(s)
        message = TIMER_CANCELED.format(scope=view.scope, note=view.note, elapsed=view.elapsed)
        return timer_panel_context(s, ctx, now, message=message)


@router.post("/timer/cancel", response_class=HTMLResponse)
def cancel_timer(request: Request, ctx: Ctx, version: FormText = "") -> HTMLResponse:
    try:
        panel = _cancel(ctx, version)
    except LogbookError as error:
        context = _panel(ctx, message=str(error), is_error=True)
        return render_error(request, error, PANEL_TEMPLATE, context)
    return render(request, PANEL_TEMPLATE, panel)
