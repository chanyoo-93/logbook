"""형식 4(tasks.dropped_at) 가져오기와 형식 1~3 파일의 변환."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.models import Task
from logbook.core.taskstatus import TaskStatus

from .backup_helpers import (
    COMMON,
    HEADER,
    HEADER_V2,
    HEADER_V3,
    HEADER_V4,
    PAY,
    STAMP,
    TASK,
    TASK_V4,
    TIME_EXPECT,
    dumps,
    line,
    rejects,
)

DROPPED = "(status가 dropped이면 시각, 아니면 null이어야 합니다)."
LATER = "2026-09-10T00:00:00+00:00"
PREFIX_V4 = [HEADER_V4, COMMON, PAY]


def _tasks(s: Session) -> list[Task]:
    s.flush()
    return list(s.scalars(select(Task).order_by(Task.id)))


def test_imports_format_4_file_with_dropped_at(fresh: Session) -> None:
    dropped = line("tasks", id=2, status="dropped", updated_at=LATER, dropped_at=LATER)

    counts = services.import_records(fresh, [*PREFIX_V4, TASK_V4, dropped])

    assert counts.tasks == 2
    todo, gone = _tasks(fresh)
    assert todo.dropped_at is None
    assert gone.status is TaskStatus.DROPPED
    assert gone.dropped_at == datetime(2026, 9, 10, tzinfo=UTC)


def test_dropped_at_may_differ_from_updated_at_in_format_4(fresh: Session) -> None:
    dropped = line("tasks", status="dropped", updated_at=LATER, dropped_at=STAMP)

    services.import_records(fresh, [*PREFIX_V4, dropped])

    assert _tasks(fresh)[0].dropped_at == datetime(2026, 9, 1, tzinfo=UTC)


@pytest.mark.parametrize("header", [HEADER, HEADER_V2, HEADER_V3], ids=["v1", "v2", "v3"])
def test_older_formats_fill_dropped_at_from_updated_at(fresh: Session, header: str) -> None:
    lines = [
        header,
        COMMON,
        PAY,
        TASK,
        line("tasks", id=2, status="dropped", updated_at=LATER),
        line("tasks", id=3, status="done", done_at=STAMP, updated_at=LATER),
    ]

    services.import_records(fresh, lines)

    todo, dropped, done = _tasks(fresh)
    assert todo.dropped_at is None
    assert dropped.dropped_at == datetime(2026, 9, 10, tzinfo=UTC)
    assert done.dropped_at is None


@pytest.mark.parametrize("header", [HEADER, HEADER_V2, HEADER_V3], ids=["v1", "v2", "v3"])
def test_older_format_rejects_dropped_at_key(fresh: Session, header: str) -> None:
    lines = [header, COMMON, PAY, TASK_V4]

    rejects(
        fresh, lines, f"{len(lines)}번째 줄: tasks 행에 알 수 없는 필드가 있습니다: dropped_at."
    )


def test_format_4_rejects_missing_dropped_at(fresh: Session) -> None:
    lines = [*PREFIX_V4, TASK]

    rejects(fresh, lines, f"{len(lines)}번째 줄: tasks 행에 빠진 필드가 있습니다: dropped_at.")


@pytest.mark.parametrize("bad", ["2026-10-08T03:00:00", "2026-10-08", 5])
def test_format_4_rejects_bad_dropped_at_value(fresh: Session, bad: Any) -> None:
    lines = [*PREFIX_V4, line("tasks", status="dropped", dropped_at=bad)]

    rejects(
        fresh,
        lines,
        f"{len(lines)}번째 줄: tasks.dropped_at 값이 올바르지 않습니다: {dumps(bad)} "
        f"(null 또는 {TIME_EXPECT}).",
    )


def test_format_4_rejects_dropped_without_dropped_at(fresh: Session) -> None:
    lines = [*PREFIX_V4, line("tasks", status="dropped", dropped_at=None)]

    rejects(
        fresh,
        lines,
        f"{len(lines)}번째 줄: tasks.dropped_at 값이 올바르지 않습니다: null {DROPPED}",
    )


def test_format_4_rejects_dropped_at_on_non_dropped_task(fresh: Session) -> None:
    lines = [*PREFIX_V4, line("tasks", status="doing", dropped_at=STAMP)]

    rejects(
        fresh,
        lines,
        f'{len(lines)}번째 줄: tasks.dropped_at 값이 올바르지 않습니다: "{STAMP}" {DROPPED}',
    )
