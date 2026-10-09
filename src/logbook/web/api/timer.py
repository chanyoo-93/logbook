"""/api/timer: 타이머 시작·정지."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from logbook.core import services
from logbook.core.ids import check_id
from logbook.web.api.envelope import ok
from logbook.web.api.schemas import TimerStart, TimerStop
from logbook.web.api.serialize import timer_json, worklog_json
from logbook.web.context import WebContext, get_context

router = APIRouter()

Ctx = Annotated[WebContext, Depends(get_context)]
TASK_LABEL = "태스크"


@router.post("/timer/start")
def start_timer(ctx: Ctx, body: TimerStart | None = None) -> JSONResponse:
    request = body or TimerStart()
    now = ctx.now()
    task_id = check_id(request.task_id, TASK_LABEL) if request.task_id is not None else None
    with ctx.session() as s:
        started = services.start_timer(
            s,
            now=now,
            note=request.note,
            project_slug=request.project,
            category=request.category,
            task_id=task_id,
            allowed_categories=tuple(ctx.cfg.categories),
            default_project=ctx.cfg.default_project,
        )
        data = {"timer": timer_json(started.timer, now), "task_started": started.task_started}
    return ok(data, status_code=201)


@router.post("/timer/stop")
def stop_timer(ctx: Ctx, body: TimerStop | None = None) -> JSONResponse:
    request = body or TimerStop()
    now = ctx.now()
    with ctx.session() as s:
        stopped = services.stop_timer(s, now=now, extra_note=request.note, round_to=request.round)
        data = {
            "log": worklog_json(stopped.log),
            "elapsed_minutes": stopped.elapsed_minutes,
            "day_total_minutes": services.day_total_minutes(s, stopped.log.date),
        }
    return ok(data)
