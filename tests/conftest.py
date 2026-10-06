"""공용 테스트 fixture."""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from logbook.core.config import Config, load_config
from logbook.core.db import create_engine_for, init_db

pytest_plugins = ["pytester"]

# 목요일, ISO 2026-W40
FIXED_TODAY = date(2026, 10, 1)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """홈 디렉터리를 임시 경로로 돌리고 LOGBOOK_* 환경변수를 지운다."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))  # macOS/Linux
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows
    monkeypatch.delenv("LOGBOOK_DB", raising=False)
    monkeypatch.delenv("LOGBOOK_CONFIG", raising=False)
    return home


@pytest.fixture
def tmp_home(isolated_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """LOGBOOK_DB, LOGBOOK_CONFIG를 임시 데이터 디렉터리 하위로 설정한다.

    홈 디렉터리가 아니라 데이터 디렉터리를 반환한다 (홈은 isolated_home).
    """
    data_dir = tmp_path / "logbook-data"
    data_dir.mkdir()
    monkeypatch.setenv("LOGBOOK_DB", str(data_dir / "logbook.db"))
    monkeypatch.setenv("LOGBOOK_CONFIG", str(data_dir / "config.toml"))
    return data_dir


@pytest.fixture
def today() -> date:
    """날짜 의존 테스트의 기준 날짜."""
    return FIXED_TODAY


@pytest.fixture
def config(tmp_home: Path) -> Config:
    """기본 설정. 설정 파일이 없으므로 db_path만 LOGBOOK_DB(tmp_home/logbook.db)를 따른다."""
    return load_config()


@pytest.fixture
def engine(tmp_home: Path) -> Iterator[Engine]:
    """tmp_home/logbook.db에 스키마를 만든 엔진.

    Windows는 열린 DB 파일을 지울 수 없으므로 종료 시 반드시 dispose한다.
    """
    db_engine = create_engine_for(tmp_home / "logbook.db")
    try:
        init_db(db_engine)
        yield db_engine
    finally:
        db_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """engine에 연결된 세션. 종료 시 롤백하고 닫는다."""
    db_session = Session(engine, expire_on_commit=False)
    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.close()
