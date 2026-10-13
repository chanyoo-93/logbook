"""ORM·결과 객체를 JSON용 dict로 바꾼다. 세션이 열려 있는 동안 호출한다."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from logbook.core import services
from logbook.core.duration import format_duration

if TYPE_CHECKING:
    from logbook.core.models import ActiveTimer, Task, WorkLog
    from logbook.core.services import StatsResult
    from logbook.core.weeks import Week


def iso_utc(moment: dt.datetime | None) -> str | None:
    """UTC ISO 8601(백업과 같은 isoformat). None은 None."""
    if moment is None:
        return None
    return moment.astimezone(dt.UTC).isoformat()


def week_meta(week: Week) -> dict[str, str]:
    return {"week": week.label, "start": week.start.isoformat(), "end": week.end.isoformat()}


def worklog_json(log: WorkLog) -> dict[str, object]:
    return {
        "id": log.id,
        "date": log.date.isoformat(),
        "minutes": log.minutes,
        "duration": format_duration(log.minutes),
        "note": log.note,
        "project": log.project.slug,
        "category": log.category,
        "task_id": log.task_id,
        "started_at": iso_utc(log.started_at),
        "ended_at": iso_utc(log.ended_at),
        "created_at": iso_utc(log.created_at),
    }


def task_json(task: Task, actual_minutes: int) -> dict[str, object]:
    return {
        "id": task.id,
        "project": task.project.slug,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "category": task.category,
        "estimate_minutes": task.estimate_minutes,
        "planned_week": task.planned_week,
        "due_date": task.due_date.isoformat() if task.due_date is not None else None,
        "external_ref": task.external_ref,
        "created_at": iso_utc(task.created_at),
        "updated_at": iso_utc(task.updated_at),
        "done_at": iso_utc(task.done_at),
        "actual_minutes": actual_minutes,
    }


def timer_json(timer: ActiveTimer, now: dt.datetime) -> dict[str, object]:
    return {
        "project": timer.project.slug,
        "category": timer.category,
        "note": timer.note,
        "task_id": timer.task_id,
        "started_at": iso_utc(timer.started_at),
        "elapsed_minutes": services.elapsed_minutes(timer.started_at, now),
    }


def stats_json(result: StatsResult) -> dict[str, object]:
    return {
        **week_meta(result.week),
        "by": result.by,
        "total_minutes": result.total_minutes,
        "count": result.count,
        "rows": [
            {"key": row.key, "label": row.label, "minutes": row.minutes, "count": row.count}
            for row in result.rows
        ],
    }
