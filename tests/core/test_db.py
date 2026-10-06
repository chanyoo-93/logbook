"""logbook.core.db 단위 테스트."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import Connection, Engine, inspect, select, text
from sqlalchemy.orm import Session

from logbook.core import db
from logbook.core.config import load_config
from logbook.core.errors import LogbookError
from logbook.core.models import Project

TABLES = {"projects", "tasks", "worklogs", "active_timer", "schema_version"}

MakeEngine = Callable[[Path | str], Engine]


@pytest.fixture
def make_engine() -> Iterator[MakeEngine]:
    """create_engine_for로 만든 엔진을 테스트가 끝나면 모두 dispose한다."""
    engines: list[Engine] = []

    def make(path: Path | str) -> Engine:
        engine = db.create_engine_for(path)
        engines.append(engine)
        return engine

    yield make
    for engine in engines:
        engine.dispose()


def column_names(engine: Engine, table: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table)}


def version_rows(engine: Engine) -> list[int]:
    with engine.connect() as conn:
        return list(conn.scalars(text("SELECT version FROM schema_version")))


def project_slugs(engine: Engine) -> list[str]:
    with Session(engine) as session:
        return list(session.scalars(select(Project.slug).order_by(Project.slug)))


def add_project(engine: Engine, slug: str = "payment") -> None:
    with db.session_scope(engine) as session:
        session.add(Project(slug=slug, name="결제 시스템"))


def set_version(engine: Engine, version: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE schema_version SET version = :v"), {"v": version})


def add_extra_column(conn: Connection) -> None:
    conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN extra TEXT")


# --- default_db_path ---


def test_default_db_path_without_env_is_in_data_dir() -> None:
    expected = Path.home() / ".logbook" / "logbook.db"

    assert db.default_db_path() == expected
    assert load_config().db_path == expected


def test_default_db_path_follows_logbook_db(tmp_home: Path) -> None:
    assert db.default_db_path() == tmp_home / "logbook.db"
    assert load_config().db_path == db.default_db_path()


def test_default_db_path_expands_tilde(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOGBOOK_DB", "~/work/my.db")

    assert db.default_db_path() == isolated_home / "work" / "my.db"


def test_default_db_path_ignores_empty_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGBOOK_DB", "")

    assert db.default_db_path() == Path.home() / ".logbook" / "logbook.db"


# --- create_engine_for ---


def test_create_engine_for_creates_parent_directories(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    path = tmp_path / "a" / "b" / "logbook.db"

    engine = make_engine(path)
    assert path.parent.is_dir()

    db.init_db(engine)
    assert path.is_file()


def test_create_engine_for_accepts_str_with_tilde(
    isolated_home: Path, make_engine: MakeEngine
) -> None:
    engine = make_engine("~/data/logbook.db")

    db.init_db(engine)

    assert (isolated_home / "data" / "logbook.db").is_file()


def test_create_engine_for_reports_unusable_parent(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")

    with pytest.raises(LogbookError, match="디렉터리를 만들 수 없습니다"):
        db.create_engine_for(blocker / "sub" / "logbook.db")


def test_foreign_keys_are_enabled_on_every_connection(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    engine = make_engine(tmp_path / "logbook.db")

    # 동시에 두 개를 열어 풀이 서로 다른 DBAPI 연결을 만들게 한다.
    with engine.connect() as first, engine.connect() as second:
        assert first.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert second.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_dispose_releases_database_file(tmp_path: Path) -> None:
    path = tmp_path / "logbook.db"
    engine = db.create_engine_for(path)
    try:
        db.init_db(engine)
        add_project(engine)
        assert project_slugs(engine) == ["payment"]
    finally:
        engine.dispose()

    # Windows에서는 열린 파일을 지울 수 없으므로, 연결이 남아 있으면 여기서 실패한다.
    path.unlink()
    assert not path.exists()


# --- init_db / current_version ---


def test_init_db_creates_schema_on_new_file(tmp_path: Path, make_engine: MakeEngine) -> None:
    engine = make_engine(tmp_path / "logbook.db")

    assert db.init_db(engine) == 1

    assert set(inspect(engine).get_table_names()) == TABLES
    assert version_rows(engine) == [1]
    assert db.current_version(engine) == 1


def test_init_db_is_idempotent(engine: Engine) -> None:
    add_project(engine)

    assert db.init_db(engine) == 1
    assert db.init_db(engine) == 1

    assert version_rows(engine) == [1]
    assert project_slugs(engine) == ["payment"]


def test_current_version_is_none_for_empty_database_file(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    path = tmp_path / "logbook.db"
    path.write_bytes(b"")

    assert db.current_version(make_engine(path)) is None


def test_init_db_fills_empty_version_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM schema_version"))
    assert db.current_version(engine) is None

    assert db.init_db(engine) == 1

    assert version_rows(engine) == [1]


def test_init_db_migrates_and_keeps_data(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    add_project(engine)
    monkeypatch.setattr(db, "SCHEMA_VERSION", 2)
    monkeypatch.setitem(db.MIGRATIONS, 2, add_extra_column)

    assert db.init_db(engine) == 2

    assert "extra" in column_names(engine, "projects")
    assert version_rows(engine) == [2]
    assert project_slugs(engine) == ["payment"]
    # 이미 최신이면 마이그레이션을 다시 실행하지 않는다 (ALTER가 두 번 돌면 실패).
    assert db.init_db(engine) == 2


def test_init_db_runs_migrations_in_order(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def upgrade_to_2(conn: Connection) -> None:
        calls.append(2)
        add_extra_column(conn)

    def upgrade_to_3(conn: Connection) -> None:
        calls.append(3)
        conn.exec_driver_sql("UPDATE projects SET extra = 'v3'")

    add_project(engine)
    monkeypatch.setattr(db, "SCHEMA_VERSION", 3)
    monkeypatch.setitem(db.MIGRATIONS, 3, upgrade_to_3)
    monkeypatch.setitem(db.MIGRATIONS, 2, upgrade_to_2)

    assert db.init_db(engine) == 3

    assert calls == [2, 3]
    assert version_rows(engine) == [3]
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT extra FROM projects")) == "v3"


def test_failed_migration_rolls_back_schema_change(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_upgrade(conn: Connection) -> None:
        add_extra_column(conn)
        raise RuntimeError("boom")

    monkeypatch.setattr(db, "SCHEMA_VERSION", 2)
    monkeypatch.setitem(db.MIGRATIONS, 2, broken_upgrade)

    with pytest.raises(RuntimeError, match="boom"):
        db.init_db(engine)

    assert "extra" not in column_names(engine, "projects")
    assert db.current_version(engine) == 1


def test_init_db_rejects_newer_database(engine: Engine) -> None:
    set_version(engine, 99)

    with pytest.raises(LogbookError, match="최신 버전의 logbook이 필요") as excinfo:
        db.init_db(engine)

    assert str(excinfo.value) == (
        "데이터베이스가 더 새로운 버전(v99)입니다. 최신 버전의 logbook이 필요합니다."
    )
    assert db.current_version(engine) == 99


def test_init_db_requires_every_migration(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "SCHEMA_VERSION", 3)
    monkeypatch.setitem(db.MIGRATIONS, 2, add_extra_column)

    with pytest.raises(LogbookError, match="v3"):
        db.init_db(engine)

    # 하나라도 빠져 있으면 아무 마이그레이션도 적용하지 않는다.
    assert db.current_version(engine) == 1
    assert "extra" not in column_names(engine, "projects")


def test_init_db_reports_file_that_is_not_a_database(
    tmp_path: Path, make_engine: MakeEngine
) -> None:
    path = tmp_path / "logbook.db"
    path.write_bytes(b"this is not a sqlite database" * 100)

    with pytest.raises(LogbookError, match="데이터베이스 파일을 열 수 없습니다"):
        db.init_db(make_engine(path))


def test_init_db_reports_path_that_is_a_directory(tmp_path: Path, make_engine: MakeEngine) -> None:
    path = tmp_path / "logbook.db"
    path.mkdir()

    with pytest.raises(LogbookError, match="경로와 파일이 올바른지 확인하세요"):
        db.init_db(make_engine(path))


def test_init_db_rechecks_version_under_lock(
    tmp_path: Path, make_engine: MakeEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 다른 프로세스가 먼저 초기화한 상황: 잠금 전 읽기는 None, 잠금 후에는 이미 v1.
    engine = make_engine(tmp_path / "logbook.db")
    db.init_db(engine)
    monkeypatch.setattr(db, "current_version", lambda _engine: None)

    assert db.init_db(engine) == 1
    assert version_rows(engine) == [1]


# --- session_scope ---


def test_session_scope_commits_on_success(engine: Engine) -> None:
    with db.session_scope(engine) as session:
        project = Project(slug="payment", name="결제 시스템")
        session.add(project)

    assert project_slugs(engine) == ["payment"]
    # expire_on_commit=False: 블록 밖에서도 속성을 읽을 수 있다.
    assert isinstance(project.id, int)
    assert project.slug == "payment"
    assert project.created_at.tzinfo is not None


def test_session_scope_rolls_back_on_error(engine: Engine) -> None:
    with pytest.raises(RuntimeError, match="boom"), db.session_scope(engine) as session:
        session.add(Project(slug="payment", name="결제 시스템"))
        session.flush()
        raise RuntimeError("boom")

    assert project_slugs(engine) == []
