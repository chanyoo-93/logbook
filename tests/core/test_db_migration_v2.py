"""스키마 2 마이그레이션(week_notes)과 마이그레이션 전 자동 백업."""

import datetime as dt
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text

from logbook.core import db
from logbook.core.errors import LogbookError
from tests.helpers import make_v1_database

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 13, 15, 30, tzinfo=KST)
BACKUP_NAME = "logbook.db.v1-20261013-153000.bak"
COUNT_TABLES = ("projects", "tasks", "worklogs", "active_timer")

MakeEngine = Callable[[Path], Engine]


@pytest.fixture
def make_engine() -> Iterator[MakeEngine]:
    engines: list[Engine] = []

    def make(path: Path) -> Engine:
        engine = db.create_engine_for(path)
        engines.append(engine)
        return engine

    yield make
    for engine in engines:
        engine.dispose()


def seed_v1(path: Path) -> None:
    """v1 DB에 프로젝트·태스크·기록·타이머를 한 건씩 넣는다."""
    make_v1_database(path)
    engine = db.create_engine_for(path)
    stamp = "2026-10-01 00:00:00"
    try:
        # v1 스키마에는 최신 모델의 컬럼이 없으므로 ORM 대신 고정 SQL로 넣는다.
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO projects (slug, name, archived, created_at) "
                f"VALUES ('payment', '결제 시스템', 0, '{stamp}')"
            )
            conn.exec_driver_sql(
                "INSERT INTO tasks (project_id, title, status, created_at, updated_at) "
                f"VALUES (1, '환불 API 설계', 'todo', '{stamp}', '{stamp}')"
            )
            conn.exec_driver_sql(
                "INSERT INTO worklogs (project_id, task_id, category, date, minutes, note, "
                f"created_at) VALUES (1, 1, 'dev', '2026-10-01', 30, '구현', '{stamp}')"
            )
            conn.exec_driver_sql(
                "INSERT INTO active_timer (id, project_id, category, note, started_at) "
                f"VALUES (1, 1, 'dev', '진행', '{stamp}')"
            )
    finally:
        engine.dispose()


def row_counts(path: Path) -> dict[str, int]:
    """sqlite3로 직접 읽은 테이블별 행 수(연결은 닫는다)."""
    conn = sqlite3.connect(path)
    try:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
            for table in COUNT_TABLES
        }
    finally:
        conn.close()


def table_names(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


def stored_version(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("SELECT version FROM schema_version").fetchone()[0])
    finally:
        conn.close()


def week_notes_shape(engine: Engine) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    with engine.connect() as conn:
        columns = [tuple(row) for row in conn.execute(text("PRAGMA table_info(week_notes)"))]
        indexes = [tuple(row) for row in conn.execute(text("PRAGMA index_list(week_notes)"))]
    return columns, indexes


def test_schema_version_includes_week_notes_step() -> None:
    assert db.SCHEMA_VERSION >= 2
    assert 2 in db.MIGRATIONS


def test_upgrade_from_v1_keeps_rows_and_adds_week_notes(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    path = tmp_path / "logbook.db"
    seed_v1(path)
    before = row_counts(path)
    assert before == {"projects": 1, "tasks": 1, "worklogs": 1, "active_timer": 1}
    engine = make_engine(path)

    result = db.init_db(engine, now=NOW)

    assert result == db.InitResult(1, db.SCHEMA_VERSION, tmp_path / BACKUP_NAME)
    assert row_counts(path) == before
    assert "week_notes" in table_names(path)
    assert stored_version(path) == db.SCHEMA_VERSION


def test_upgraded_and_new_databases_have_same_week_notes_table(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    upgraded_path = tmp_path / "upgraded" / "logbook.db"
    upgraded_path.parent.mkdir()
    make_v1_database(upgraded_path)
    upgraded = make_engine(upgraded_path)
    db.init_db(upgraded, now=NOW)
    created = make_engine(tmp_path / "new.db")
    db.init_db(created)

    assert week_notes_shape(upgraded) == week_notes_shape(created)
    assert week_notes_shape(created)[0]  # 열이 비어 있지 않다(테이블이 실제로 있다)


def test_backup_holds_the_previous_version(tmp_path: Path, make_engine: MakeEngine) -> None:
    path = tmp_path / "logbook.db"
    seed_v1(path)
    before = row_counts(path)
    result = db.init_db(make_engine(path), now=NOW)

    assert result.backup_path is not None
    assert stored_version(result.backup_path) == 1
    assert "week_notes" not in table_names(result.backup_path)
    assert row_counts(result.backup_path) == before


def test_backup_name_gets_suffix_when_taken(tmp_path: Path, make_engine: MakeEngine) -> None:
    path = tmp_path / "logbook.db"
    make_v1_database(path)
    taken = tmp_path / BACKUP_NAME
    taken.write_text("이전 백업", encoding="utf-8")

    result = db.init_db(make_engine(path), now=NOW)

    assert result.backup_path == tmp_path / "logbook.db.v1-20261013-153000-2.bak"
    assert result.backup_path.is_file()
    assert taken.read_text(encoding="utf-8") == "이전 백업"


def test_backup_path_for_counts_up_over_existing_files(tmp_path: Path) -> None:
    db_file = tmp_path / "logbook.db"
    for name in (BACKUP_NAME, "logbook.db.v1-20261013-153000-2.bak"):
        (tmp_path / name).write_text("x", encoding="utf-8")

    chosen = db.backup_path_for(db_file, 1, NOW)

    assert chosen == tmp_path / "logbook.db.v1-20261013-153000-3.bak"


def test_backup_path_for_uses_windows_safe_name(tmp_path: Path) -> None:
    name = db.backup_path_for(tmp_path / "logbook.db", 7, NOW).name

    assert name == "logbook.db.v7-20261013-153000.bak"
    assert not set(':*?"<>|') & set(name)


@pytest.mark.parametrize("fresh", [True, False])
def test_no_backup_for_new_or_current_database(
    tmp_path: Path, make_engine: MakeEngine, fresh: bool
) -> None:
    path = tmp_path / "logbook.db"
    engine = make_engine(path)
    if not fresh:
        db.init_db(engine, now=NOW)

    result = db.init_db(engine, now=NOW)

    assert result.backup_path is None
    assert result.previous_version == (None if fresh else db.SCHEMA_VERSION)
    assert result.version == db.SCHEMA_VERSION
    assert list(tmp_path.glob("*.bak")) == []


def test_backup_failure_aborts_migration_and_removes_partial_file(
    tmp_path: Path, make_engine: MakeEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "logbook.db"
    seed_v1(path)
    before = row_counts(path)

    def failing_copy(source: Path, target: Path) -> None:
        target.write_text("만들다 만 파일", encoding="utf-8")
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(db, "_copy_database", failing_copy)
    engine = make_engine(path)

    with pytest.raises(LogbookError) as excinfo:
        db.init_db(engine, now=NOW)

    target = tmp_path / BACKUP_NAME
    assert str(excinfo.value) == db.BACKUP_FAILED.format(target=target, detail="disk I/O error")
    assert db.current_version(engine) == 1
    assert "week_notes" not in table_names(path)
    assert row_counts(path) == before
    assert list(tmp_path.glob("*.bak")) == []


def test_backup_is_skipped_when_version_is_already_current_under_lock(
    tmp_path: Path, make_engine: MakeEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 다른 프로세스가 먼저 올린 상황: 잠금 전 읽기는 v1, 잠금 안에서는 이미 최신.
    path = tmp_path / "logbook.db"
    engine = make_engine(path)
    db.init_db(engine, now=NOW)
    monkeypatch.setattr(db, "current_version", lambda _engine: 1)

    result = db.init_db(engine, now=NOW)

    assert result == db.InitResult(db.SCHEMA_VERSION, db.SCHEMA_VERSION)
    assert list(tmp_path.glob("*.bak")) == []


def test_backup_is_made_once_for_multiple_steps(
    tmp_path: Path, make_engine: MakeEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "logbook.db"
    make_v1_database(path)
    next_version = db.SCHEMA_VERSION + 1
    monkeypatch.setattr(db, "SCHEMA_VERSION", next_version)
    monkeypatch.setitem(db.MIGRATIONS, next_version, lambda conn: None)

    result = db.init_db(make_engine(path), now=NOW)

    assert result == db.InitResult(1, next_version, tmp_path / BACKUP_NAME)
    assert [p.name for p in tmp_path.glob("*.bak")] == [BACKUP_NAME]


def test_open_database_reports_upgrade_once(tmp_path: Path) -> None:
    path = tmp_path / "logbook.db"
    make_v1_database(path)
    reports: list[db.InitResult] = []

    first = db.open_database(path, now=NOW, on_upgrade=reports.append)
    first.dispose()
    second = db.open_database(path, now=NOW, on_upgrade=reports.append)
    second.dispose()

    assert reports == [db.InitResult(1, db.SCHEMA_VERSION, tmp_path / BACKUP_NAME)]


def test_initialize_database_returns_backup_path(tmp_path: Path) -> None:
    path = tmp_path / "logbook.db"
    make_v1_database(path)

    result = db.initialize_database(path, now=NOW)

    assert result == db.InitResult(1, db.SCHEMA_VERSION, tmp_path / BACKUP_NAME)


def test_init_result_backup_path_defaults_to_none() -> None:
    assert db.InitResult(None, db.SCHEMA_VERSION).backup_path is None


def test_backup_is_skipped_for_in_memory_database() -> None:
    engine = create_engine("sqlite://")
    try:
        assert db._backup_database(engine, 1, NOW) is None
    finally:
        engine.dispose()
