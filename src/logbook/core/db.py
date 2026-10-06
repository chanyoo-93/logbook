"""SQLite 엔진·세션 생성과 버전 테이블 기반 스키마 마이그레이션."""

import sqlite3
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import (
    Connection,
    Engine,
    create_engine,
    event,
    func,
    insert,
    inspect,
    select,
    update,
)
from sqlalchemy.engine import URL
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry

# 설정 로드와 같은 기본 경로 규칙을 쓰도록 config의 함수를 재노출한다.
from logbook.core.config import default_db_path as default_db_path
from logbook.core.errors import LogbookError
from logbook.core.models import Base, SchemaVersion

SCHEMA_VERSION = 1

Migration = Callable[[Connection], None]
# 버전 v-1 스키마를 v로 올리는 함수. 예: {2: upgrade_to_2}
# 주의: 마이그레이션은 트랜잭션 안에서 foreign_keys=ON 상태로 실행된다. SQLite는 트랜잭션 안의
# PRAGMA foreign_keys 변경을 무시하므로, 테이블 재생성이 필요하면 이 실행 방식부터 바꿔야 한다.
MIGRATIONS: dict[int, Migration] = {}


def create_engine_for(path: Path | str) -> Engine:
    """SQLite 엔진을 만든다. 상위 디렉터리를 만들고, 연결마다 외래 키 검사를 켠다."""
    db_path = Path(path).expanduser()
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise LogbookError(
            f"데이터베이스 디렉터리를 만들 수 없습니다: {db_path.parent} "
            f"({error.strerror or error}). 같은 이름의 파일이 있는지, "
            "쓰기 권한이 있는지 확인하세요."
        ) from error
    connect_args: dict[str, object] = {}
    if sys.version_info >= (3, 12):
        # 3.16에서 기본값이 autocommit=False로 바뀌어도 _transaction이 쓰는 레거시 모드를 유지한다.
        connect_args = {"autocommit": sqlite3.LEGACY_TRANSACTION_CONTROL}
    engine = create_engine(
        URL.create("sqlite+pysqlite", database=str(db_path)), connect_args=connect_args
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    return engine


def _enable_foreign_keys(
    dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def current_version(engine: Engine) -> int | None:
    """기록된 스키마 버전. 버전 테이블이 없거나 비어 있으면 None."""
    try:
        with engine.connect() as conn:
            return _read_version(conn)
    except DatabaseError as error:
        raise LogbookError(
            f"데이터베이스 파일을 열 수 없습니다: {engine.url.database}. "
            "경로와 파일이 올바른지 확인하세요."
        ) from error


def _read_version(conn: Connection) -> int | None:
    if not inspect(conn).has_table(SchemaVersion.__tablename__):
        return None
    return conn.scalar(select(func.max(SchemaVersion.version)))


def init_db(engine: Engine) -> int:
    """새 DB면 스키마를 만들고, 기존 DB면 최신 버전까지 마이그레이션한다. 결과 버전을 반환한다."""
    # monkeypatch가 먹도록 모듈 전역 값을 호출 시점에 읽는다.
    target = SCHEMA_VERSION
    found = current_version(engine)
    if found == target:
        return target
    _check_upgradable(found, target)
    # 동시에 실행된 다른 프로세스가 먼저 초기화·마이그레이션했을 수 있으므로
    # 쓰기 잠금을 잡은 뒤 버전을 다시 읽고 한 단계씩 올린다.
    while True:
        with _transaction(engine) as conn:
            found = _read_version(conn)
            if found is None:
                Base.metadata.create_all(conn)
                conn.execute(insert(SchemaVersion).values(version=target))
                return target
            _check_upgradable(found, target)
            if found == target:
                return target
            version = found + 1
            MIGRATIONS[version](conn)
            conn.execute(update(SchemaVersion).values(version=version))


def _check_upgradable(found: int | None, target: int) -> None:
    """DB가 더 새롭거나 필요한 마이그레이션이 하나라도 없으면 아무것도 바꾸기 전에 거부한다."""
    if found is None:
        return
    if found > target:
        raise LogbookError(
            f"데이터베이스가 더 새로운 버전(v{found})입니다. 최신 버전의 logbook이 필요합니다."
        )
    missing = [version for version in range(found + 1, target + 1) if version not in MIGRATIONS]
    if missing:
        raise LogbookError(
            f"데이터베이스를 업그레이드할 수 없습니다: v{missing[0]} 마이그레이션이 없습니다. "
            "logbook을 다시 설치하세요."
        )


@contextmanager
def _transaction(engine: Engine) -> Iterator[Connection]:
    """DDL까지 함께 커밋·롤백되는 쓰기 잠금 트랜잭션.

    sqlite3 드라이버(레거시 트랜잭션 모드)는 DDL 앞에서 BEGIN을 내지 않으므로 직접 연다.
    IMMEDIATE로 시작해 다른 프로세스의 동시 초기화·마이그레이션과 겹치지 않게 한다.
    """
    with engine.connect() as conn:
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        yield conn
        conn.commit()


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """성공하면 커밋, 예외면 롤백하고 다시 던진다.

    expire_on_commit=False라 커밋 후에도 반환된 객체의 속성을 읽을 수 있다.
    """
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
