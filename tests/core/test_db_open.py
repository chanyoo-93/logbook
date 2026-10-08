"""logbook.core.db의 DB 진입점(open_database, initialize_database)과 SQLite 오류 변환 테스트."""

import os
import sqlite3
import stat
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import OperationalError

from logbook.core import db, services
from logbook.core.errors import DatabaseBusyError, DatabaseNotInitializedError, LogbookError
from tests.helpers import (
    add_extra_column,
    add_project,
    column_names,
    hold_lock,
    project_slugs,
    set_version,
)

# --- open_database / initialize_database ---

FAST_BUSY_TIMEOUT = 0.05


@pytest.fixture
def open_db() -> Iterator[Callable[[Path], Engine]]:
    """open_database로 연 엔진을 테스트가 끝나면 모두 dispose한다."""
    engines: list[Engine] = []

    def open_(path: Path) -> Engine:
        engine = db.open_database(path)
        engines.append(engine)
        return engine

    yield open_
    for engine in engines:
        engine.dispose()


def make_database(path: Path, *, slug: str | None = None, version: int | None = None) -> None:
    """초기화된 DB 파일을 만들고 엔진을 닫는다. slug·version으로 내용과 버전을 바꾼다."""
    engine = db.create_engine_for(path)
    try:
        db.init_db(engine)
        if slug is not None:
            add_project(engine, slug)
        if version is not None:
            set_version(engine, version)
    finally:
        engine.dispose()


def read_state(path: Path) -> tuple[int | None, list[str]]:
    """DB의 (스키마 버전, 프로젝트 slug 목록)을 읽고 엔진을 닫는다."""
    engine = db.create_engine_for(path)
    try:
        return db.current_version(engine), project_slugs(engine)
    finally:
        engine.dispose()


def require_pending_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "SCHEMA_VERSION", 2)
    monkeypatch.setitem(db.MIGRATIONS, 2, add_extra_column)


def test_open_database_rejects_missing_file_without_creating_it(tmp_path: Path) -> None:
    sub = tmp_path / "없음" / "sub"
    path = sub / "logbook.db"

    with pytest.raises(DatabaseNotInitializedError) as excinfo:
        db.open_database(path)

    assert str(excinfo.value) == (f"데이터베이스가 없습니다: {path}. 먼저 'lb init'을 실행하세요.")
    assert not path.exists()
    assert not sub.exists()


def test_open_database_rejects_empty_file_and_releases_it(tmp_path: Path) -> None:
    path = tmp_path / "logbook.db"
    path.write_bytes(b"")

    with pytest.raises(DatabaseNotInitializedError) as excinfo:
        db.open_database(path)

    assert str(excinfo.value) == (
        f"데이터베이스가 초기화되지 않았습니다: {path}. 먼저 'lb init'을 실행하세요."
    )
    path.unlink()


def test_open_database_rejects_sqlite_file_without_schema(tmp_path: Path) -> None:
    path = tmp_path / "logbook.db"
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE other (x INTEGER)")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(DatabaseNotInitializedError, match="초기화되지 않았습니다"):
        db.open_database(path)

    path.unlink()


def test_open_database_returns_engine_for_initialized_database(
    tmp_path: Path, open_db: Callable[[Path], Engine]
) -> None:
    path = tmp_path / "logbook.db"
    make_database(path)

    engine = open_db(path)

    assert isinstance(engine, Engine)
    assert db.current_version(engine) == db.SCHEMA_VERSION


def test_open_database_skips_init_db_when_up_to_date(
    tmp_path: Path, open_db: Callable[[Path], Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "logbook.db"
    make_database(path)

    def fail_init_db(engine: Engine) -> int:
        raise AssertionError("최신 DB에서는 init_db를 부르지 않아야 한다")

    monkeypatch.setattr(db, "init_db", fail_init_db)

    assert db.current_version(open_db(path)) == db.SCHEMA_VERSION


def test_open_database_applies_pending_migration(
    tmp_path: Path, open_db: Callable[[Path], Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "logbook.db"
    make_database(path, slug="payment")
    require_pending_migration(monkeypatch)

    engine = open_db(path)

    assert db.current_version(engine) == 2
    assert "extra" in column_names(engine, "projects")
    assert project_slugs(engine) == ["payment"]


def test_open_database_rejects_newer_database_and_releases_it(tmp_path: Path) -> None:
    path = tmp_path / "logbook.db"
    make_database(path, version=99)

    with pytest.raises(LogbookError, match="최신 버전의 logbook이 필요"):
        db.open_database(path)

    path.unlink()


def test_initialize_database_creates_new_database(tmp_path: Path) -> None:
    sub = tmp_path / "새 폴더" / "sub"
    path = sub / "logbook.db"

    assert db.initialize_database(path) == db.InitResult(None, db.SCHEMA_VERSION)

    assert sub.is_dir()
    assert path.is_file()
    path.unlink()


def test_initialize_database_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "logbook.db"
    db.initialize_database(path)

    assert db.initialize_database(path) == db.InitResult(db.SCHEMA_VERSION, db.SCHEMA_VERSION)


def test_initialize_database_fills_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "logbook.db"
    path.write_bytes(b"")

    assert db.initialize_database(path) == db.InitResult(None, db.SCHEMA_VERSION)


def test_initialize_database_applies_pending_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "logbook.db"
    make_database(path, slug="payment")
    require_pending_migration(monkeypatch)

    assert db.initialize_database(path) == db.InitResult(1, 2)

    assert read_state(path) == (2, ["payment"])


def test_initialize_database_rejects_newer_database_and_releases_it(tmp_path: Path) -> None:
    path = tmp_path / "logbook.db"
    make_database(path, version=99)

    with pytest.raises(LogbookError, match="최신 버전의 logbook이 필요"):
        db.initialize_database(path)

    path.unlink()


def test_init_result_is_frozen() -> None:
    result = db.InitResult(None, 1)

    with pytest.raises(AttributeError):
        result.version = 2  # type: ignore[misc]


# --- SQLite 오류의 한국어 변환 ---


class FakeSqliteError(Exception):
    """sqlite_errorname 속성을 지정할 수 있는 가짜 드라이버 오류."""

    def __init__(self, errorname: str | None) -> None:
        super().__init__("fake")
        if errorname is not None:
            self.sqlite_errorname = errorname


def fake_operational_error(errorname: str | None) -> OperationalError:
    return OperationalError("INSERT ...", None, FakeSqliteError(errorname))


@pytest.fixture
def fast_busy_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "BUSY_TIMEOUT_SECONDS", FAST_BUSY_TIMEOUT)


def busy_message(path: Path) -> str:
    return f"데이터베이스를 다른 프로그램이 사용 중입니다: {path}. 잠시 후 다시 시도하세요."


def test_busy_timeout_default_matches_sqlite3() -> None:
    assert db.BUSY_TIMEOUT_SECONDS == 5.0


@pytest.mark.usefixtures("fast_busy_timeout")
def test_open_database_reports_exclusive_lock_as_busy(tmp_path: Path) -> None:
    path = tmp_path / "logbook.db"
    make_database(path)

    started = time.monotonic()
    with hold_lock(path, "EXCLUSIVE"), pytest.raises(DatabaseBusyError) as excinfo:
        db.open_database(path)
    elapsed = time.monotonic() - started

    assert str(excinfo.value) == busy_message(path)
    cause = excinfo.value.__cause__
    assert isinstance(cause, OperationalError)
    assert cause.orig.sqlite_errorname.startswith("SQLITE_BUSY")  # type: ignore[union-attr]
    assert elapsed < 2
    path.unlink()


@pytest.mark.usefixtures("fast_busy_timeout")
def test_session_scope_reports_write_lock_as_busy_and_rolls_back(
    tmp_path: Path, open_db: Callable[[Path], Engine]
) -> None:
    path = tmp_path / "logbook.db"
    make_database(path)
    engine = open_db(path)

    with (
        hold_lock(path, "IMMEDIATE"),
        pytest.raises(DatabaseBusyError) as excinfo,
        db.session_scope(engine) as session,
    ):
        services.create_project(session, "payment", "결제 시스템")

    assert str(excinfo.value) == busy_message(path)
    assert isinstance(excinfo.value.__cause__, OperationalError)
    assert project_slugs(engine) == []


def test_session_scope_translates_error_after_write_and_rolls_back(engine: Engine) -> None:
    error = fake_operational_error("SQLITE_FULL")

    with (
        pytest.raises(LogbookError, match="디스크 공간이 부족해") as excinfo,
        db.session_scope(engine) as session,
    ):
        services.create_project(session, "payment", "결제 시스템")
        session.flush()
        raise error

    assert excinfo.value.__cause__ is error
    # flush까지 한 쓰기도 커밋되지 않아야 한다.
    assert project_slugs(engine) == []


@pytest.mark.usefixtures("fast_busy_timeout")
def test_init_db_reports_write_lock_on_begin_as_busy(
    tmp_path: Path, open_db: Callable[[Path], Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "logbook.db"
    make_database(path)
    # 최신 DB를 먼저 연 뒤 대기 마이그레이션을 만들어 init_db의 BEGIN 경로만 시험한다.
    engine = open_db(path)
    require_pending_migration(monkeypatch)

    with hold_lock(path, "IMMEDIATE"), pytest.raises(DatabaseBusyError):
        db.init_db(engine)

    assert db.current_version(engine) == 1


def test_transaction_translates_error_in_migration_body_and_rolls_back(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def disk_full_upgrade(conn: Connection) -> None:
        add_extra_column(conn)
        raise fake_operational_error("SQLITE_FULL")

    monkeypatch.setattr(db, "SCHEMA_VERSION", 2)
    monkeypatch.setitem(db.MIGRATIONS, 2, disk_full_upgrade)

    with pytest.raises(LogbookError, match="디스크 공간이 부족해") as excinfo:
        db.init_db(engine)

    assert isinstance(excinfo.value.__cause__, OperationalError)
    assert db.current_version(engine) == 1
    assert "extra" not in column_names(engine, "projects")


def test_transaction_keeps_untranslated_operational_error(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = fake_operational_error("SQLITE_ERROR")

    def broken_upgrade(conn: Connection) -> None:
        add_extra_column(conn)
        raise error

    monkeypatch.setattr(db, "SCHEMA_VERSION", 2)
    monkeypatch.setitem(db.MIGRATIONS, 2, broken_upgrade)

    with pytest.raises(OperationalError) as excinfo:
        db.init_db(engine)

    assert excinfo.value is error
    assert db.current_version(engine) == 1
    assert "extra" not in column_names(engine, "projects")


def make_read_only(path: Path) -> None:
    if sys.platform == "win32":
        os.chmod(path, stat.S_IREAD)
    else:
        os.chmod(path, 0o444)


def test_session_scope_reports_read_only_file(
    tmp_path: Path, open_db: Callable[[Path], Engine]
) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root는 읽기 전용 파일에도 쓸 수 있다")
    path = tmp_path / "logbook.db"
    make_database(path)
    make_read_only(path)
    try:
        engine = open_db(path)
        with pytest.raises(LogbookError) as excinfo, db.session_scope(engine) as session:
            services.create_project(session, "payment", "결제 시스템")
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)

    assert str(excinfo.value) == (
        f"데이터베이스 파일에 쓸 수 없습니다: {path}. "
        "파일이 읽기 전용인지, 쓰기 권한이 있는지 확인하세요."
    )


@pytest.mark.parametrize(
    ("errorname", "expected_type", "expected_message"),
    [
        ("SQLITE_BUSY", DatabaseBusyError, "다른 프로그램이 사용 중입니다"),
        ("SQLITE_BUSY_SNAPSHOT", DatabaseBusyError, "다른 프로그램이 사용 중입니다"),
        ("SQLITE_LOCKED", DatabaseBusyError, "다른 프로그램이 사용 중입니다"),
        ("SQLITE_LOCKED_SHAREDCACHE", DatabaseBusyError, "다른 프로그램이 사용 중입니다"),
        ("SQLITE_READONLY", LogbookError, "데이터베이스 파일에 쓸 수 없습니다"),
        ("SQLITE_READONLY_DBMOVED", LogbookError, "데이터베이스 파일에 쓸 수 없습니다"),
        ("SQLITE_FULL", LogbookError, "디스크 공간이 부족해"),
    ],
)
def test_translate_sqlite_error_maps_known_codes(
    errorname: str, expected_type: type[LogbookError], expected_message: str
) -> None:
    translated = db._translate_sqlite_error(fake_operational_error(errorname), "x.db")

    assert type(translated) is expected_type
    assert expected_message in str(translated)
    assert "x.db" in str(translated)


def test_translate_sqlite_error_full_message() -> None:
    translated = db._translate_sqlite_error(fake_operational_error("SQLITE_FULL"), "x.db")

    assert str(translated) == (
        "디스크 공간이 부족해 데이터베이스에 쓸 수 없습니다: x.db. "
        "공간을 확보한 뒤 다시 시도하세요."
    )


@pytest.mark.parametrize("errorname", ["SQLITE_ERROR", "SQLITE_CORRUPT", "SQLITE", "", None])
def test_translate_sqlite_error_ignores_other_errors(errorname: str | None) -> None:
    assert db._translate_sqlite_error(fake_operational_error(errorname), "x.db") is None


def test_session_scope_keeps_untranslated_operational_error(engine: Engine) -> None:
    error = fake_operational_error("SQLITE_ERROR")

    with pytest.raises(OperationalError) as excinfo, db.session_scope(engine):
        raise error

    assert excinfo.value is error
