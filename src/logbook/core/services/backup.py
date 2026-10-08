"""전체 데이터 JSONL 내보내기.

형식(버전 1)은 공개 계약이다. 필드 목록은 모델 컬럼에서 만들지 않고 아래 튜플로 고정한다.
컬럼이 늘면 형식을 의도적으로 바꾸고 FORMAT_VERSION을 올린다.
"""

import datetime as dt
import enum
import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from logbook.core import db
from logbook.core.models import ActiveTimer, Project, Task, WorkLog

FORMAT_VERSION = 1
EXPORT_TYPE = "logbook-export"
TABLE_ORDER = ("projects", "tasks", "worklogs", "active_timer")

PROJECT_FIELDS = ("id", "slug", "name", "description", "color", "archived", "created_at")
TASK_FIELDS = (
    "id",
    "project_id",
    "title",
    "description",
    "status",
    "category",
    "estimate_minutes",
    "planned_week",
    "due_date",
    "external_ref",
    "created_at",
    "updated_at",
    "done_at",
)
WORKLOG_FIELDS = (
    "id",
    "project_id",
    "task_id",
    "category",
    "date",
    "minutes",
    "note",
    "started_at",
    "ended_at",
    "created_at",
)
TIMER_FIELDS = ("id", "project_id", "task_id", "category", "note", "started_at")

FIELDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "projects": PROJECT_FIELDS,
        "tasks": TASK_FIELDS,
        "worklogs": WORKLOG_FIELDS,
        "active_timer": TIMER_FIELDS,
    }
)

# 테이블 이름 → 모델. 순서는 TABLE_ORDER와 같다.
MODELS: Mapping[str, type[Any]] = MappingProxyType(
    {
        "projects": Project,
        "tasks": Task,
        "worklogs": WorkLog,
        "active_timer": ActiveTimer,
    }
)

# ensure_ascii=False는 이 세 문자를 원문자로 남기고, str.splitlines()와 일부 편집기는
# 이를 줄 끝으로 본다. 문자열 안에서만 나오므로 JSON 이스케이프로 바꿔도 값은 같다.
SEPARATOR_ESCAPES: Mapping[int, str] = MappingProxyType(
    {cp: json.dumps(chr(cp))[1:-1] for cp in (0x2028, 0x2029, 0x85)}
)


@dataclass(frozen=True)
class BackupCounts:
    projects: int
    tasks: int
    worklogs: int
    timers: int


def _encode_value(value: object) -> object:
    """DB 값을 JSON 값으로 바꾼다(시각은 UTC, 날짜는 YYYY-MM-DD, 상태는 값 문자열)."""
    if isinstance(value, dt.datetime):
        return value.astimezone(dt.UTC).isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    return value


def _dump(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True).translate(SEPARATOR_ESCAPES)


def _row_line(table: str, record: object) -> str:
    row = {name: _encode_value(getattr(record, name)) for name in FIELDS[table]}
    return _dump({"table": table, "row": row})


def export_records(s: Session, *, now: dt.datetime) -> tuple[list[str], BackupCounts]:
    """JSONL 줄 목록(줄바꿈 없음)과 개수. now는 머리글 exported_at(aware)."""
    if now.utcoffset() is None:
        raise ValueError(f"now must be timezone-aware: {now!r}")
    header: dict[str, Any] = {
        "type": EXPORT_TYPE,
        "format": FORMAT_VERSION,
        "schema_version": db.SCHEMA_VERSION,
        "exported_at": _encode_value(now),
    }
    lines = [_dump(header)]
    counts: dict[str, int] = {}
    for table in TABLE_ORDER:
        model = MODELS[table]
        records = s.scalars(select(model).order_by(model.id)).all()
        lines.extend(_row_line(table, record) for record in records)
        counts[table] = len(records)
    return lines, BackupCounts(
        projects=counts["projects"],
        tasks=counts["tasks"],
        worklogs=counts["worklogs"],
        timers=counts["active_timer"],
    )
