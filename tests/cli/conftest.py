"""CLI 테스트 fixture (fixture만 둔다. 그 밖의 도우미는 tests/cli/helpers.py)."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import typer.rich_utils
from sqlalchemy.orm import Session
from typer.testing import CliRunner, Result

from logbook.cli import runtime
from logbook.cli.main import app
from logbook.core import db, platform, services
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import parse_week
from tests.cli.helpers import Clipboard, Clock, OpenDb

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


@pytest.fixture
def clock() -> Clock:
    """runtime.now()가 돌려줄 시각(기본 FIXED_NOW). clock.advance(minutes=85)로 옮긴다."""
    return Clock()


@pytest.fixture(autouse=True)
def deterministic_cli(monkeypatch: pytest.MonkeyPatch, today: date, clock: Clock) -> None:
    """두 OS와 CI에서 같은 출력이 나오도록 환경과 '오늘'·'지금'을 고정한다."""
    for name in _OUTPUT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # GitHub 러너는 GITHUB_ACTIONS=true라 Typer가 패널에 ANSI 코드를 넣는다(import 시점에 계산됨).
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", False)
    monkeypatch.setattr(typer.rich_utils, "MAX_WIDTH", TYPER_PANEL_WIDTH)
    monkeypatch.setattr(runtime, "today", lambda: today)
    monkeypatch.setattr(runtime, "now", lambda: clock.now)


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
def initialized(lb: Callable[..., Result], tmp_home: Path) -> Path:
    """'lb init'을 마친 임시 DB 경로."""
    result = lb("init")
    assert result.exit_code == 0, result.stderr
    return tmp_home / "logbook.db"


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


# W40(2026-09-28 ~ 10-04) 안, 정오 부근이라 날짜 경계와 멀다
DONE_AT = datetime(2026, 9, 30, 3, 0, tzinfo=UTC)


@pytest.fixture
def seeded(initialized: Path, open_db: OpenDb, today: date) -> Path:
    """W40에 기록 2건과 완료 태스크 1건, 다음 주 계획 1건이 있는 DB."""
    with open_db() as s:
        services.create_project(s, "payment", "결제 서버")
        services.add_worklog(
            s, minutes=120, note="결제 재시도", project_slug="payment", category="dev",
            work_date=date(2026, 9, 30), today=today,
        )  # fmt: skip
        services.add_worklog(
            s, minutes=60, note="주간 회의", category="meeting",
            work_date=date(2026, 10, 1), today=today,
        )  # fmt: skip
        task = services.create_task(
            s, title="결제 재시도 구현", project_slug="payment", estimate_minutes=180,
            planned_week=parse_week("2026-W40", today=today, week_start="monday"),
        )  # fmt: skip
        task.status = TaskStatus.DONE
        task.done_at = DONE_AT
        services.create_task(
            s, title="환불 API 구현", project_slug="payment", estimate_minutes=480,
            planned_week=parse_week("2026-W41", today=today, week_start="monday"),
        )  # fmt: skip
    return initialized


@pytest.fixture
def clipboard(monkeypatch: pytest.MonkeyPatch) -> Clipboard:
    fake = Clipboard(ok=True)
    monkeypatch.setattr(platform, "copy_to_clipboard", fake)
    return fake


@pytest.fixture
def failing_clipboard(monkeypatch: pytest.MonkeyPatch) -> Clipboard:
    fake = Clipboard(ok=False)
    monkeypatch.setattr(platform, "copy_to_clipboard", fake)
    return fake
