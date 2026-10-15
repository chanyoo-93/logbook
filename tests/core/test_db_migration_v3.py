"""스키마 3 마이그레이션(category_colors)."""

import datetime as dt
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from logbook.core import db
from tests.helpers import make_v1_database

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 15, 9, 30, tzinfo=KST)
BACKUP_V2 = "logbook.db.v2-20261015-093000.bak"
BACKUP_V1 = "logbook.db.v1-20261015-093000.bak"

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


def make_v2_database(path: Path, make_engine: MakeEngine) -> None:
    """v1 DB를 v2까지만 올린다(프로젝트 한 건 포함). 백업 파일은 지워지지 않으므로 호출자가 센다."""
    make_v1_database(path)
    engine = make_engine(path)
    with engine.begin() as conn:
        db._upgrade_to_2(conn)
        conn.execute(text("UPDATE schema_version SET version = 2"))
        conn.execute(
            text("INSERT INTO projects (slug, name, archived, created_at) VALUES (:s, :n, 0, :c)"),
            {"s": "payment", "n": "결제", "c": "2026-10-01 00:00:00"},
        )
        conn.execute(
            text(
                "INSERT INTO week_notes (week, risks, notes, updated_at) VALUES (:w, '', 'x', :c)"
            ),
            {"w": "2026-W41", "c": "2026-10-01 00:00:00"},
        )


def counts(path: Path, tables: tuple[str, ...]) -> dict[str, int]:
    conn = sqlite3.connect(path)
    try:
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: S608
            for t in tables
        }
    finally:
        conn.close()


def stored_version(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("SELECT version FROM schema_version").fetchone()[0])
    finally:
        conn.close()


def table_shape(engine: Engine) -> list[tuple[object, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text("PRAGMA table_info(category_colors)"))]


def test_schema_version_is_three() -> None:
    assert db.SCHEMA_VERSION == 3
    assert 3 in db.MIGRATIONS


def test_upgrade_v2_to_v3_keeps_rows_and_adds_table(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    path = tmp_path / "logbook.db"
    make_v2_database(path, make_engine)
    tables = ("projects", "week_notes")
    before = counts(path, tables)
    assert before == {"projects": 1, "week_notes": 1}

    result = db.init_db(make_engine(path), now=NOW)

    assert result == db.InitResult(2, 3, tmp_path / BACKUP_V2)
    assert counts(path, (*tables, "category_colors")) == {**before, "category_colors": 0}
    assert stored_version(path) == 3
    assert [p.name for p in tmp_path.glob("*.bak")] == [BACKUP_V2]
    assert stored_version(tmp_path / BACKUP_V2) == 2


def test_upgrade_v1_to_v3_applies_both_steps_with_one_backup(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    path = tmp_path / "logbook.db"
    make_v1_database(path)

    result = db.init_db(make_engine(path), now=NOW)

    assert result == db.InitResult(1, 3, tmp_path / BACKUP_V1)
    assert [p.name for p in tmp_path.glob("*.bak")] == [BACKUP_V1]
    assert counts(path, ("week_notes", "category_colors")) == {
        "week_notes": 0,
        "category_colors": 0,
    }


def test_upgraded_and_new_databases_have_same_category_colors_table(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    upgraded_path = tmp_path / "upgraded" / "logbook.db"
    upgraded_path.parent.mkdir()
    make_v2_database(upgraded_path, make_engine)
    upgraded = make_engine(upgraded_path)
    db.init_db(upgraded, now=NOW)
    created = make_engine(tmp_path / "new.db")
    db.init_db(created)

    assert table_shape(upgraded) == table_shape(created)
    assert table_shape(created)  # 열이 비어 있지 않다(테이블이 실제로 있다)
