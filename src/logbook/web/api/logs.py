"""/api/logs: 기록 조회·추가·수정·삭제."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette.responses import JSONResponse

from logbook.core import services
from logbook.core.duration import parse_duration
from logbook.core.errors import InvalidInputError
from logbook.core.ids import check_id, parse_id
from logbook.core.weeks import parse_date, parse_week
from logbook.web.api.envelope import ok
from logbook.web.api.schemas import LogCreate, LogPatch, changed_fields, optional_text
from logbook.web.api.serialize import week_meta, worklog_json
from logbook.web.context import WebContext, get_context

router = APIRouter()

Ctx = Annotated[WebContext, Depends(get_context)]
TASK_LABEL = "태스크"
NOTHING_TO_CHANGE = (
    "바꿀 항목을 하나 이상 지정하세요: duration, note, category, project, date, task_id"
)


@router.get("/logs")
def list_logs(
    ctx: Ctx,
    week: Annotated[str | None, Query()] = None,
    project: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    the_week = parse_week(
        optional_text(week) or "this", today=ctx.today(), week_start=ctx.cfg.week_start
    )
    with ctx.session() as s:
        logs = services.list_worklogs(
            s,
            week=the_week,
            project_slug=optional_text(project),
            category=optional_text(category),
        )
        data = [worklog_json(log) for log in logs]
    total = sum(int(str(item["minutes"])) for item in data)
    meta = {**week_meta(the_week), "count": len(data), "total_minutes": total}
    return ok(data, meta=meta)


@router.post("/logs")
def create_log(body: LogCreate, ctx: Ctx) -> JSONResponse:
    minutes = parse_duration(body.duration)
    task_id = check_id(body.task_id, TASK_LABEL) if body.task_id is not None else None
    work_date = parse_date(
        body.date if body.date is not None else "today",
        today=ctx.today(),
        week_start=ctx.cfg.week_start,
    )
    with ctx.session() as s:
        log = services.add_worklog(
            s,
            minutes=minutes,
            note=body.note,
            project_slug=body.project,
            category=body.category,
            work_date=work_date,
            task_id=task_id,
            allowed_categories=tuple(ctx.cfg.categories),
            default_project=ctx.cfg.default_project,
            today=ctx.today(),
        )
        data = {
            "log": worklog_json(log),
            "day_total_minutes": services.day_total_minutes(s, log.date),
        }
    return ok(data, status_code=201)


@router.patch("/logs/{log_id}")
def update_log(log_id: str, body: LogPatch, ctx: Ctx) -> JSONResponse:
    the_id = parse_id(log_id)
    fields = changed_fields(body, nullable=frozenset({"task_id"}))
    if not fields:
        raise InvalidInputError(NOTHING_TO_CHANGE)
    duration = fields.get("duration")
    work_date = fields.get("date")
    task_id = fields.get("task_id")
    with ctx.session() as s:
        log = services.update_worklog(
            s,
            the_id,
            minutes=parse_duration(str(duration)) if duration is not None else None,
            note=_text(fields, "note"),
            category=_text(fields, "category"),
            project_slug=_text(fields, "project"),
            work_date=(
                parse_date(str(work_date), today=ctx.today(), week_start=ctx.cfg.week_start)
                if work_date is not None
                else None
            ),
            task_id=check_id(int(str(task_id)), TASK_LABEL) if task_id is not None else None,
            clear_task="task_id" in fields and task_id is None,
            allowed_categories=tuple(ctx.cfg.categories),
        )
        data = {"log": worklog_json(log)}
    return ok(data)


@router.delete("/logs/{log_id}")
def delete_log(log_id: str, ctx: Ctx) -> JSONResponse:
    the_id = parse_id(log_id)
    with ctx.session() as s:
        services.delete_worklog(s, the_id)
    return ok({"id": the_id})


def _text(fields: dict[str, object], name: str) -> str | None:
    value = fields.get(name)
    return None if value is None else str(value)
