"""공용 테스트 fixture.

engine, session fixture는 Phase 1(Task 1-5)에서 추가한다.
"""

from datetime import date
from pathlib import Path

import pytest

from logbook.core.config import Config, load_config

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
