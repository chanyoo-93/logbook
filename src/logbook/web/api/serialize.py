"""ORM·결과 객체를 JSON용 dict로 바꾼다. 세션이 열려 있는 동안 호출한다."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from logbook.core.duration import format_duration

if TYPE_CHECKING:
    from logbook.core.models import WorkLog
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
