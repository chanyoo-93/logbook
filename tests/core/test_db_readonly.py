"""core.db.open_readonly(자동완성 전용 읽기 전용 엔진) 테스트."""

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from logbook.core import db
from tests.helpers import make_v1_database


def test_returns_none_without_creating_file_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "none.db"

    assert db.open_readonly(path) is None
    assert not path.exists()


def test_returns_none_and_keeps_old_version_without_backup(tmp_path: Path) -> None:
    folder = tmp_path / "data"
    folder.mkdir()
    path = folder / "v1.db"
    make_v1_database(path)

    assert db.open_readonly(path) is None

    engine = db.create_engine_for(path)
    try:
        assert db.current_version(engine) == 1
    finally:
        engine.dispose()
    assert [p.name for p in folder.iterdir()] == ["v1.db"]


def test_returns_none_when_file_is_not_a_database(tmp_path: Path) -> None:
    path = tmp_path / "broken.db"
    path.write_bytes(b"not a sqlite database" * 100)

    assert db.open_readonly(path) is None


def test_returns_engine_for_current_database(tmp_path: Path) -> None:
    path = tmp_path / "now.db"
    db.initialize_database(path)

    engine = db.open_readonly(path)

    assert engine is not None
    try:
        assert db.current_version(engine) == db.SCHEMA_VERSION
    finally:
        engine.dispose()


def test_engine_rejects_writes(tmp_path: Path) -> None:
    path = tmp_path / "now.db"
    db.initialize_database(path)
    engine = db.open_readonly(path)
    assert engine is not None

    try:
        with pytest.raises(OperationalError), engine.begin() as conn:
            conn.execute(text("DELETE FROM schema_version"))
    finally:
        engine.dispose()


def test_opens_path_with_korean_space_and_hash(tmp_path: Path) -> None:
    folder = tmp_path / "내 로그 #1"
    folder.mkdir()
    path = folder / "기록 장부.db"
    db.initialize_database(path)

    engine = db.open_readonly(path)

    assert engine is not None
    engine.dispose()
