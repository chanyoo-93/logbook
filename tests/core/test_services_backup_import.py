"""JSONL 가져오기(import_records) 테스트."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, event, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from logbook.core import db, services
from logbook.core.errors import DatabaseBusyError, InvalidInputError
from logbook.core.models import ActiveTimer, Project, Task, WorkLog
from logbook.core.services import backup, backup_import
from logbook.core.taskstatus import TaskStatus

from .backup_helpers import (
    COMMON,
    HEADER,
    LS,
    NEL,
    NON_EMPTY_MESSAGE,
    NOW,
    PAY,
    PS,
    TASK,
    add_exotic_rows,
    line,
    populate,
    valid,
)

# --- 성공 경로와 왕복 ---


def test_imports_valid_file_and_returns_counts(fresh: Session) -> None:
    counts = services.import_records(fresh, valid())

    assert counts == services.BackupCounts(projects=2, tasks=1, worklogs=1, timers=1)
    fresh.flush()
    assert [(p.id, p.slug) for p in fresh.scalars(select(Project).order_by(Project.id))] == [
        (1, "common"),
        (2, "pay"),
    ]
    task = fresh.scalars(select(Task)).one()
    assert (task.id, task.project_id, task.status) == (1, 2, TaskStatus.TODO)
    worklog = fresh.scalars(select(WorkLog)).one()
    assert (worklog.date, worklog.minutes, worklog.note) == (date(2026, 10, 7), 30, "메모")
    assert fresh.scalars(select(ActiveTimer)).one().note == "타이머"


def test_allows_db_with_only_common_or_no_projects(session: Session) -> None:
    counts = services.import_records(session, [HEADER, COMMON])

    assert counts == services.BackupCounts(projects=1, tasks=0, worklogs=0, timers=0)


def test_allows_trailing_newlines_and_crlf(fresh: Session) -> None:
    lines = [line + "\r\n" for line in valid()]

    counts = services.import_records(fresh, lines)

    assert counts.projects == 2


def test_imports_lines_with_unescaped_line_separators(fresh: Session) -> None:
    note = f"앞{LS}가운데{PS}가운데{NEL}뒤"
    lines = [HEADER, COMMON, PAY, TASK, line("worklogs", note=note)]
    assert note in lines[-1]

    services.import_records(fresh, lines)
    fresh.flush()

    assert fresh.scalars(select(WorkLog)).one().note == note


def _new_engine(path: Path) -> Engine:
    engine = db.create_engine_for(path)
    db.init_db(engine)
    return engine


def test_export_import_export_is_byte_identical_except_header_time(
    session: Session, tmp_path: Path
) -> None:
    populate(session)
    add_exotic_rows(session)
    first, counts = services.export_records(session, now=NOW)
    other = _new_engine(tmp_path / "other.db")
    try:
        with Session(other, expire_on_commit=False) as target:
            services.ensure_common_project(target)
            target.flush()
            imported = services.import_records(target, first)
            target.flush()
            second, _ = services.export_records(
                target, now=datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC)
            )
            micro = target.scalars(select(WorkLog).order_by(WorkLog.id.desc())).first()
            assert micro is not None
            assert micro.started_at == datetime(2026, 10, 8, 3, 0, 0, 123456, tzinfo=UTC)
            assert micro.created_at.microsecond == 123456
    finally:
        other.dispose()

    assert imported == counts
    assert second[1:] == first[1:]
    assert json.loads(second[0])["exported_at"] != json.loads(first[0])["exported_at"]
    assert {k: v for k, v in json.loads(second[0]).items() if k != "exported_at"} == {
        k: v for k, v in json.loads(first[0]).items() if k != "exported_at"
    }


def test_imports_common_with_id_3_and_new_ids_follow_max(fresh: Session) -> None:
    lines = [
        HEADER,
        line("projects", id=3),
        line("projects", id=4, slug="pay"),
        line("worklogs", id=7, project_id=3, task_id=None),
    ]

    services.import_records(fresh, lines)
    fresh.flush()

    assert fresh.scalars(select(Project).where(Project.slug == "common")).one().id == 3
    project = Project(slug="new", name="새", created_at=NOW)
    worklog = WorkLog(
        project_id=3, category="dev", date=date(2026, 10, 8), minutes=5, note="", created_at=NOW
    )
    fresh.add_all([project, worklog])
    fresh.flush()
    assert project.id == 5
    assert worklog.id == 8


# --- 빈 DB 확인 ---


def _add_task(s: Session) -> None:
    common = services.ensure_common_project(s)
    s.add(Task(project_id=common.id, title="t", created_at=NOW, updated_at=NOW))


def _add_worklog(s: Session) -> None:
    common = services.ensure_common_project(s)
    s.add(
        WorkLog(
            project_id=common.id,
            category="dev",
            date=date(2026, 10, 8),
            minutes=5,
            note="",
            created_at=NOW,
        )
    )


def _add_timer(s: Session) -> None:
    common = services.ensure_common_project(s)
    s.add(ActiveTimer(project_id=common.id, category="dev", note="", started_at=NOW))


def _add_project(s: Session) -> None:
    s.add(Project(slug="extra", name="추가", created_at=NOW))


@pytest.mark.parametrize("add", [_add_task, _add_worklog, _add_timer, _add_project])
def test_rejects_db_with_data_and_changes_nothing(fresh: Session, add: Any) -> None:
    add(fresh)
    fresh.flush()
    before = [p.slug for p in fresh.scalars(select(Project).order_by(Project.id))]

    with pytest.raises(InvalidInputError) as excinfo:
        services.import_records(fresh, valid())

    assert str(excinfo.value) == NON_EMPTY_MESSAGE
    assert [p.slug for p in fresh.scalars(select(Project).order_by(Project.id))] == before


# --- 쓰기 단계 오류 ---


class FakeSqliteError(Exception):
    def __init__(self, errorname: str) -> None:
        super().__init__("fake")
        self.sqlite_errorname = errorname


def _fail_inserts(engine: Engine, error: Exception) -> None:
    def raise_on_insert(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
    ) -> None:
        if statement.lstrip().upper().startswith("INSERT"):
            raise error

    event.listen(engine, "before_cursor_execute", raise_on_insert)


def test_flush_integrity_error_becomes_import_error(fresh: Session, engine: Engine) -> None:
    error = IntegrityError("INSERT ...", None, Exception("UNIQUE constraint failed: x"))
    _fail_inserts(engine, error)

    with pytest.raises(InvalidInputError) as excinfo:
        services.import_records(fresh, valid())

    assert str(excinfo.value) == (
        "가져온 데이터가 데이터베이스 규칙에 맞지 않습니다: UNIQUE constraint failed: x. "
        "'lb export'로 만든 파일인지 확인하세요."
    )


def test_flush_operational_error_is_not_translated(
    engine: Engine,
) -> None:
    with db.session_scope(engine) as setup:
        services.ensure_common_project(setup)
    error = OperationalError("INSERT ...", None, FakeSqliteError("SQLITE_BUSY"))
    _fail_inserts(engine, error)

    with pytest.raises(DatabaseBusyError) as excinfo, db.session_scope(engine) as session:
        services.import_records(session, valid())

    assert not isinstance(excinfo.value, InvalidInputError)
    assert excinfo.value.__cause__ is error
    with Session(engine) as check:
        assert [p.slug for p in check.scalars(select(Project))] == ["common"]


def test_validation_kind_tables_are_consistent() -> None:
    assert tuple(backup_import._KINDS) == backup.TABLE_ORDER
    assert set(backup_import._REFERENCES) == set(backup.TABLE_ORDER)
    used_kinds = set()
    for table, fields in backup.FIELDS.items():
        assert tuple(backup_import._KINDS[table]) == fields, table
        used_kinds.update(backup_import._KINDS[table].values())
    base_kinds = {kind.removeprefix("opt_") for kind in used_kinds}
    # 모든 종류에 변환기와 기대 문구가 있다(opt_ 접두 종류는 접두 없는 변환기를 쓴다).
    assert base_kinds <= set(backup_import._CONVERTERS)
    # 쓰이지 않는 변환기·문구가 남아 있지 않다.
    assert set(backup_import._CONVERTERS) == base_kinds
    assert set(backup_import._EXPECTED) == used_kinds
