"""/api/tasks: 태스크 조회·추가·수정(상태 변경 포함)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Query
from starlette.responses import JSONResponse

from logbook.core import services
from logbook.core.duration import echo_input, parse_duration
from logbook.core.errors import InvalidInputError
from logbook.core.ids import parse_id
from logbook.core.taskstatus import OPEN_STATUSES, TaskStatus, parse_statuses
from logbook.core.weeks import parse_date, parse_week
from logbook.web.api.deps import TASK_LABEL, Ctx
from logbook.web.api.envelope import ok
from logbook.web.api.schemas import TaskCreate, TaskPatch, changed_fields, optional_text
from logbook.web.api.serialize import task_json
from logbook.web.context import WebContext

if TYPE_CHECKING:
    from logbook.core.weeks import Week, WeekStart

router = APIRouter()

DEFAULT_STATUSES = ",".join(status.value for status in OPEN_STATUSES)
NOTHING_TO_CHANGE = (
    "바꿀 항목을 하나 이상 지정하세요: title, category, estimate, week, due, ref, "
    "description, status"
)
STATUS_INVALID = (
    "태스크 상태가 올바르지 않습니다: '{value}'. todo, doing, done, dropped 중 하나를 쓰세요."
)
NULLABLE_FIELDS = frozenset({"category", "estimate", "week", "due", "ref", "description"})


@router.get("/tasks")
def list_tasks(
    ctx: Ctx,
    status: Annotated[str | None, Query()] = None,
    week: Annotated[str | None, Query()] = None,
    project: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    statuses = parse_statuses(optional_text(status) or DEFAULT_STATUSES)
    the_week = _week(optional_text(week), ctx.today(), ctx.cfg.week_start)
    with ctx.session() as s:
        tasks = services.list_tasks(
            s, project_slug=optional_text(project), statuses=statuses, week=the_week
        )
        actual = services.actual_minutes_by_task(s, [task.id for task in tasks])
        data = [task_json(task, actual.get(task.id, 0)) for task in tasks]
    return ok(data, meta={"count": len(data)})


@router.post("/tasks")
def create_task(body: TaskCreate, ctx: Ctx) -> JSONResponse:
    today, week_start = ctx.today(), ctx.cfg.week_start
    estimate = (
        parse_duration(body.estimate, max_minutes=None) if body.estimate is not None else None
    )
    the_week = _week(body.week, today, week_start)
    due = _date(body.due, today, week_start)
    with ctx.session() as s:
        task = services.create_task(
            s,
            title=body.title,
            project_slug=body.project if body.project is not None else ctx.cfg.default_project,
            category=body.category,
            estimate_minutes=estimate,
            planned_week=the_week,
            due_date=due,
            external_ref=body.ref,
            description=body.description,
            allowed_categories=tuple(ctx.cfg.categories),
        )
        data = task_json(task, 0)
    return ok(data, status_code=201)


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, body: TaskPatch, ctx: Ctx) -> JSONResponse:
    the_id = parse_id(task_id, TASK_LABEL)
    sent = changed_fields(body, nullable=NULLABLE_FIELDS)
    if not sent:
        raise InvalidInputError(NOTHING_TO_CHANGE)
    # 값 해석 오류는 세션을 열기 전에 모두 낸다.
    fields = _task_fields(body, sent, ctx)
    status = _status(body.status) if body.status is not None else None
    with ctx.session() as s:
        if fields:
            services.update_task(s, the_id, allowed_categories=tuple(ctx.cfg.categories), **fields)
        task = (
            services.set_task_status(s, the_id, status)
            if status is not None
            else services.get_task(s, the_id)
        )
        data = task_json(task, services.task_actual_minutes(s, the_id))
    return ok(data)


def _task_fields(body: TaskPatch, sent: frozenset[str], ctx: WebContext) -> dict[str, object]:
    """보낸 키를 update_task의 필드 이름과 값으로 바꾼다. 값은 모델 속성에서 읽는다."""
    today, week_start = ctx.today(), ctx.cfg.week_start
    fields: dict[str, object] = {}
    if "title" in sent:
        fields["title"] = body.title
    if "category" in sent:
        fields["category"] = body.category
    if "estimate" in sent:
        fields["estimate_minutes"] = (
            parse_duration(body.estimate, max_minutes=None) if body.estimate is not None else None
        )
    if "week" in sent:
        fields["planned_week"] = _week(body.week, today, week_start)
    if "due" in sent:
        fields["due_date"] = _date(body.due, today, week_start)
    if "ref" in sent:
        fields["external_ref"] = body.ref
    if "description" in sent:
        fields["description"] = body.description
    return fields


def _week(text: str | None, today: date, week_start: WeekStart) -> Week | None:
    return None if text is None else parse_week(text, today=today, week_start=week_start)


def _date(text: str | None, today: date, week_start: WeekStart) -> date | None:
    return None if text is None else parse_date(text, today=today, week_start=week_start)


def _status(text: str) -> TaskStatus:
    try:
        return TaskStatus(text.strip().lower())
    except ValueError:
        raise InvalidInputError(STATUS_INVALID.format(value=echo_input(text))) from None
