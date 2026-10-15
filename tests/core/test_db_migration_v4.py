"""스키마 4 마이그레이션(tasks.dropped_at)."""

import datetime as dt
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from logbook.core import db
from tests.helpers import make_v1_database

from .test_db_migration_v3 import MakeEngine, counts, make_v2_database, stored_version

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 15, 9, 30, tzinfo=KST)
BACKUP_V3 = "logbook.db.v3-20261015-093000.bak"
BACKUP_V1 = "logbook.db.v1-20261015-093000.bak"
DROPPED_UPDATED_AT = "2026-10-05 01:02:03.000000"
TASK_SQL = (
    "INSERT INTO tasks (project_id, title, status, created_at, updated_at, done_at) "
    "VALUES (1, :title, :status, '2026-10-01 00:00:00', :updated, :done)"
)


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


def make_v3_database(path: Path, make_engine: MakeEngine) -> None:
    """v2 DB를 v3까지 올리고 할 일·완료·중단 태스크를 넣는다. 올리기 전 백업은 호출자가 센다."""
    make_v2_database(path, make_engine)
    engine = make_engine(path)
    with engine.begin() as conn:
        db._upgrade_to_3(conn)
        conn.execute(text("UPDATE schema_version SET version = 3"))
        rows = (
            ("할 일", "todo", "2026-10-02 00:00:00", None),
            ("완료", "done", "2026-10-03 00:00:00", "2026-10-03 00:00:00"),
            ("중단", "dropped", DROPPED_UPDATED_AT, None),
            ("중단 둘", "dropped", "2026-10-06 04:05:06.000000", None),
        )
        for title, status, updated, done in rows:
            conn.execute(
                text(TASK_SQL),
                {"title": title, "status": status, "updated": updated, "done": done},
            )


def task_rows(path: Path) -> list[tuple[object, ...]]:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT title, status, updated_at, done_at, dropped_at FROM tasks ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def table_shape(engine: Engine) -> list[tuple[object, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text("PRAGMA table_info(tasks)"))]


def test_schema_version_is_four() -> None:
    assert db.SCHEMA_VERSION == 4
    assert 4 in db.MIGRATIONS


def test_upgrade_v3_to_v4_fills_dropped_at_from_updated_at(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    path = tmp_path / "logbook.db"
    make_v3_database(path, make_engine)
    before = counts(path, ("projects", "tasks"))
    conn = sqlite3.connect(path)
    try:
        updated_before = conn.execute("SELECT updated_at FROM tasks ORDER BY id").fetchall()
    finally:
        conn.close()
    backups_before = {p.name for p in tmp_path.glob("*.bak")}

    result = db.init_db(make_engine(path), now=NOW)

    assert result == db.InitResult(3, 4, tmp_path / BACKUP_V3)
    assert counts(path, ("projects", "tasks")) == before
    assert stored_version(path) == 4
    rows = task_rows(path)
    assert [(r[0], r[4]) for r in rows] == [
        ("할 일", None),
        ("완료", None),
        ("중단", DROPPED_UPDATED_AT),
        ("중단 둘", "2026-10-06 04:05:06.000000"),
    ]
    assert [(r[2],) for r in rows] == updated_before  # updated_at은 그대로
    assert {p.name for p in tmp_path.glob("*.bak")} - backups_before == {BACKUP_V3}
    assert stored_version(tmp_path / BACKUP_V3) == 3


def test_upgrade_v1_to_v4_applies_all_steps_with_one_backup(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    path = tmp_path / "logbook.db"
    make_v1_database(path)

    result = db.init_db(make_engine(path), now=NOW)

    assert result == db.InitResult(1, 4, tmp_path / BACKUP_V1)
    assert [p.name for p in tmp_path.glob("*.bak")] == [BACKUP_V1]
    assert counts(path, ("week_notes", "category_colors", "tasks")) == {
        "week_notes": 0,
        "category_colors": 0,
        "tasks": 0,
    }
    assert task_rows(path) == []


def test_upgraded_and_new_databases_have_same_tasks_table(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    upgraded_path = tmp_path / "upgraded" / "logbook.db"
    upgraded_path.parent.mkdir()
    make_v3_database(upgraded_path, make_engine)
    upgraded = make_engine(upgraded_path)
    db.init_db(upgraded, now=NOW)
    created = make_engine(tmp_path / "new.db")
    db.init_db(created)

    assert table_shape(upgraded) == table_shape(created)
    assert "dropped_at" in [column[1] for column in table_shape(created)]
