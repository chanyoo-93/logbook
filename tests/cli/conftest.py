"""CLI 테스트 fixture (fixture만 둔다. 그 밖의 도우미는 tests/cli/helpers.py)."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import date
from pathlib import Path

import pytest
import typer.rich_utils
from sqlalchemy.orm import Session
from typer.testing import CliRunner, Result

from logbook.cli import runtime
from logbook.cli.main import app
from logbook.core import db

# Rich·Typer 출력 모양을 바꾸는 환경변수 (CI 러너나 개발자 셸에 있을 수 있다)
_OUTPUT_ENV_VARS = (
    "COLUMNS",
    "LINES",
    "FORCE_COLOR",
    "NO_COLOR",
    "PY_COLORS",
    "TTY_COMPATIBLE",
    "TTY_INTERACTIVE",
)
# Typer help·오류 패널 폭
TYPER_PANEL_WIDTH = 200


@pytest.fixture(autouse=True)
def deterministic_cli(monkeypatch: pytest.MonkeyPatch, today: date) -> None:
    """두 OS와 CI에서 같은 출력이 나오도록 환경과 '오늘'을 고정한다."""
    for name in _OUTPUT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # GitHub 러너는 GITHUB_ACTIONS=true라 Typer가 패널에 ANSI 코드를 넣는다(import 시점에 계산됨).
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", False)
    monkeypatch.setattr(typer.rich_utils, "MAX_WIDTH", TYPER_PANEL_WIDTH)
    monkeypatch.setattr(runtime, "today", lambda: today)


@pytest.fixture
def lb(tmp_home: Path) -> Callable[..., Result]:
    """lb("add", "2h", "메모", input=None): 임시 DB·설정으로 앱을 실행한다.

    catch_exceptions=False라 예상 밖 예외는 곧바로 테스트 실패가 된다.
    """
    runner = CliRunner()

    def invoke(*args: str, input: str | None = None) -> Result:
        return runner.invoke(app, list(args), input=input, prog_name="lb", catch_exceptions=False)

    return invoke


@pytest.fixture
def open_db(tmp_home: Path) -> Callable[[], AbstractContextManager[Session]]:
    """데이터 준비·검증용 세션을 여는 함수. 블록이 끝나면 커밋하고 엔진을 dispose한다."""

    @contextmanager
    def opener() -> Iterator[Session]:
        engine = db.open_database(tmp_home / "logbook.db")
        try:
            with db.session_scope(engine) as session:
                yield session
        finally:
            engine.dispose()

    return opener
