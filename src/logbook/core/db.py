"""SQLite 엔진·세션 생성과 버전 테이블 기반 스키마 마이그레이션."""

import sqlite3
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
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
from sqlalchemy.exc import DatabaseError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry, NullPool

# 설정 로드와 같은 기본 경로 규칙을 쓰도록 config의 함수를 재노출한다.
from logbook.core.config import default_db_path as default_db_path
from logbook.core.errors import DatabaseBusyError, DatabaseNotInitializedError, LogbookError
from logbook.core.models import Base, SchemaVersion

SCHEMA_VERSION = 3

# 다른 연결이 잠금을 잡고 있을 때 기다리는 시간(초). sqlite3 기본값과 같다.
# monkeypatch가 먹도록 create_engine_for가 호출 시점에 읽는다.
BUSY_TIMEOUT_SECONDS = 5.0

Migration = Callable[[Connection], None]


def _upgrade_to_2(conn: Connection) -> None:
    """v2: week_notes 테이블. 모델이 나중에 바뀌어도 이 단계는 그대로 두도록 DDL을 고정한다."""
    conn.exec_driver_sql(
        "CREATE TABLE week_notes ("
        "week VARCHAR(8) NOT NULL, risks TEXT NOT NULL, notes TEXT NOT NULL, "
        "updated_at DATETIME NOT NULL, PRIMARY KEY (week))"
    )


def _upgrade_to_3(conn: Connection) -> None:
    """v3: category_colors 테이블. 고정 DDL이다."""
    conn.exec_driver_sql(
        "CREATE TABLE category_colors ("
        "category VARCHAR(32) NOT NULL, color VARCHAR(7) NOT NULL, "
        "updated_at DATETIME NOT NULL, PRIMARY KEY (category))"
    )


# 버전 v-1 스키마를 v로 올리는 함수. 2는 week_notes 추가, 3은 category_colors 추가
# 주의: 마이그레이션은 트랜잭션 안에서 foreign_keys=ON 상태로 실행된다. SQLite는 트랜잭션 안의
# PRAGMA foreign_keys 변경을 무시하므로, 테이블 재생성이 필요하면 이 실행 방식부터 바꿔야 한다.
MIGRATIONS: dict[int, Migration] = {2: _upgrade_to_2, 3: _upgrade_to_3}

BACKUP_FAILED = (
    "마이그레이션 전에 데이터베이스를 백업하지 못했습니다: {target} ({detail}). "
    "디스크 공간과 쓰기 권한을 확인한 뒤 다시 실행하세요. 데이터베이스는 바뀌지 않았습니다."
)


@dataclass(frozen=True)
class InitResult:
    """init_db·initialize_database의 결과."""

    previous_version: int | None  # None: 스키마를 새로 만들었음(파일이 없었거나 비어 있었음)
    version: int  # 적용 후 버전
    backup_path: Path | None = None  # 마이그레이션 전에 만든 백업. 올리지 않았으면 None


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
    connect_args: dict[str, object] = {"timeout": BUSY_TIMEOUT_SECONDS}
    if sys.version_info >= (3, 12):
        # 3.16에서 기본값이 autocommit=False로 바뀌어도 _transaction이 쓰는 레거시 모드를 유지한다.
        connect_args["autocommit"] = sqlite3.LEGACY_TRANSACTION_CONTROL
    engine = create_engine(
        URL.create("sqlite+pysqlite", database=str(db_path)), connect_args=connect_args
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    return engine


def open_readonly(path: Path | str) -> Engine | None:
    """자동완성 전용. 파일이 있고 스키마 버전이 SCHEMA_VERSION과 같을 때만 읽기 전용 엔진을 준다.

    파일을 만들거나 마이그레이션하지 않는다. 없거나 버전이 다르거나 열 수 없으면 None이다.
    엔진의 dispose는 호출자 책임이다.
    """
    db_path = Path(path).expanduser()
    if not db_path.is_file():
        return None
    uri = db_path.absolute().as_uri() + "?mode=ro"

    def connect() -> sqlite3.Connection:
        return sqlite3.connect(uri, uri=True, timeout=BUSY_TIMEOUT_SECONDS)

    engine = create_engine("sqlite+pysqlite://", creator=connect, poolclass=NullPool)
    try:
        if current_version(engine) == SCHEMA_VERSION:
            return engine
    except (LogbookError, SQLAlchemyError):
        pass
    engine.dispose()
    return None


def _enable_foreign_keys(
    dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def open_database(
    path: Path | str,
    *,
    now: datetime | None = None,
    on_upgrade: Callable[[InitResult], None] | None = None,
) -> Engine:
    """'lb init'으로 만든 DB만 연다(CLI·Web 공용). 엔진의 dispose는 호출자 책임이다.

    파일을 만들지 않는다. 파일이 없거나 스키마가 없으면 DatabaseNotInitializedError.
    버전은 한 번만 읽고, 최신과 다를 때만 init_db로 대기 중인 마이그레이션을 적용한다.
    실제로 버전을 올렸으면 on_upgrade(결과)를 한 번 부른다(core는 출력하지 않는다).
    존재 확인과 연결 사이에 다른 프로세스가 파일을 지우면 sqlite3가 빈 파일을 만들 수 있다.
    이때도 DatabaseNotInitializedError로 'lb init'을 안내하므로 데이터는 잃지 않는다.
    """
    db_path = Path(path).expanduser()
    if not db_path.exists():
        raise DatabaseNotInitializedError(
            f"데이터베이스가 없습니다: {db_path}. 먼저 'lb init'을 실행하세요."
        )
    engine = create_engine_for(db_path)
    try:
        found = current_version(engine)
        if found is None:
            raise DatabaseNotInitializedError(
                f"데이터베이스가 초기화되지 않았습니다: {db_path}. 먼저 'lb init'을 실행하세요."
            )
        # monkeypatch가 먹도록 모듈 전역 값을 호출 시점에 읽는다.
        if found != SCHEMA_VERSION:
            result = init_db(engine, now=now)
            if on_upgrade is not None and result.previous_version != result.version:
                on_upgrade(result)
    except BaseException:
        engine.dispose()
        raise
    return engine


def initialize_database(path: Path | str, *, now: datetime | None = None) -> InitResult:
    """'lb init' 전용: 스키마를 만들거나 최신 버전까지 올린다. 엔진은 항상 dispose한다."""
    engine = create_engine_for(path)
    try:
        return init_db(engine, now=now)
    finally:
        engine.dispose()


def _translate_sqlite_error(error: DatabaseError, path: str | None) -> LogbookError | None:
    """SQLite 잠금·권한·용량 오류를 한국어 LogbookError로 바꾼다. 그 밖의 오류는 None."""
    errorname = getattr(error.orig, "sqlite_errorname", None)
    if not isinstance(errorname, str):
        return None
    # 확장 코드(예: SQLITE_BUSY_SNAPSHOT)는 기본 코드(SQLITE_BUSY)로 본다.
    base_code = "_".join(errorname.split("_")[:2])
    if base_code in ("SQLITE_BUSY", "SQLITE_LOCKED"):
        return DatabaseBusyError(
            f"데이터베이스를 다른 프로그램이 사용 중입니다: {path}. 잠시 후 다시 시도하세요."
        )
    if base_code == "SQLITE_READONLY":
        return LogbookError(
            f"데이터베이스 파일에 쓸 수 없습니다: {path}. "
            "파일이 읽기 전용인지, 쓰기 권한이 있는지 확인하세요."
        )
    if base_code == "SQLITE_FULL":
        return LogbookError(
            f"디스크 공간이 부족해 데이터베이스에 쓸 수 없습니다: {path}. "
            "공간을 확보한 뒤 다시 시도하세요."
        )
    return None


def current_version(engine: Engine) -> int | None:
    """기록된 스키마 버전. 버전 테이블이 없거나 비어 있으면 None."""
    try:
        with engine.connect() as conn:
            return _read_version(conn)
    except DatabaseError as error:
        translated = _translate_sqlite_error(error, engine.url.database)
        if translated is not None:
            raise translated from error
        raise LogbookError(
            f"데이터베이스 파일을 열 수 없습니다: {engine.url.database}. "
            "경로와 파일이 올바른지 확인하세요."
        ) from error


def _read_version(conn: Connection) -> int | None:
    if not inspect(conn).has_table(SchemaVersion.__tablename__):
        return None
    return conn.scalar(select(func.max(SchemaVersion.version)))


def init_db(engine: Engine, *, now: datetime | None = None) -> InitResult:
    """새 DB면 스키마를 만들고, 기존 DB면 최신 버전까지 마이그레이션한다.

    올릴 때는 첫 단계를 적용하기 직전에 DB를 같은 폴더에 한 번 백업한다. now는 백업 파일
    이름에만 쓴다(None이면 지금 시각).
    """
    # monkeypatch가 먹도록 모듈 전역 값을 호출 시점에 읽는다.
    target = SCHEMA_VERSION
    found = current_version(engine)
    if found == target:
        return InitResult(target, target)
    _check_upgradable(found, target)
    # 동시에 실행된 다른 프로세스가 먼저 초기화·마이그레이션했을 수 있으므로
    # 쓰기 잠금을 잡은 뒤 버전을 다시 읽고, 같은 잠금 안에서 백업과 모든 단계를 적용한다.
    with _transaction(engine) as conn:
        found = _read_version(conn)
        if found is None:
            Base.metadata.create_all(conn)
            conn.execute(insert(SchemaVersion).values(version=target))
            return InitResult(None, target)
        _check_upgradable(found, target)
        if found == target:
            return InitResult(target, target)
        previous = found
        backup_path = _backup_database(engine, found, now or datetime.now().astimezone())
        while found < target:
            found += 1
            MIGRATIONS[found](conn)
            conn.execute(update(SchemaVersion).values(version=found))
    return InitResult(previous, target, backup_path)


def backup_path_for(db_file: Path, version: int, now: datetime) -> Path:
    """'logbook.db.v1-20261013-153000.bak'. 이름이 겹치면 '-2', '-3'…을 붙인다(덮어쓰지 않는다)."""
    stem = f"{db_file.name}.v{version}-{now.strftime('%Y%m%d-%H%M%S')}"
    candidate = db_file.with_name(f"{stem}.bak")
    number = 2
    while candidate.exists():
        candidate = db_file.with_name(f"{stem}-{number}.bak")
        number += 1
    return candidate


def _copy_database(source: Path, target: Path) -> None:
    """sqlite3 백업 API로 일관된 사본을 만든다. 두 연결은 반드시 닫는다(Windows 파일 잠금)."""
    source_conn = sqlite3.connect(source, timeout=BUSY_TIMEOUT_SECONDS)
    try:
        target_conn = sqlite3.connect(target)
        try:
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
    finally:
        source_conn.close()


def _backup_database(engine: Engine, version: int, now: datetime) -> Path | None:
    """마이그레이션 전 백업. 파일 DB가 아니면 None. 실패하면 부분 파일을 치우고 오류를 낸다."""
    database = engine.url.database
    if not database or database == ":memory:":
        return None
    target = backup_path_for(Path(database), version, now)
    try:
        _copy_database(Path(database), target)
    except (sqlite3.Error, OSError) as error:
        with suppress(OSError):
            target.unlink(missing_ok=True)
        detail = getattr(error, "strerror", None) or error
        raise LogbookError(BACKUP_FAILED.format(target=target, detail=detail)) from error
    return target


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
    BEGIN부터 본문, 커밋까지의 SQLite 잠금·권한·용량 오류는 롤백 뒤 한국어 오류로 바꾼다.
    """
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
    except OperationalError as error:
        translated = _translate_sqlite_error(error, engine.url.database)
        if translated is None:
            raise
        raise translated from error


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """성공하면 커밋, 예외면 롤백하고 다시 던진다.

    expire_on_commit=False라 커밋 후에도 반환된 객체의 속성을 읽을 수 있다.
    flush·커밋 중의 SQLite 잠금·권한·용량 오류는 롤백 뒤 한국어 오류로 바꾼다.
    """
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except BaseException as error:
        session.rollback()
        if isinstance(error, OperationalError):
            translated = _translate_sqlite_error(error, engine.url.database)
            if translated is not None:
                raise translated from error
        raise
    finally:
        session.close()
