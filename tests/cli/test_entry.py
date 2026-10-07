"""진입점 run(): 프로세스 내부 실행, 설치된 lb 실행 파일, import 가드."""

import io
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
import typer.main
from typer.core import TyperGroup
from typer.testing import Result

from logbook import __version__
from logbook.cli.group import LogbookCommand, LogbookGroup
from logbook.cli.main import app, run
from tests.cli.helpers import (
    FORBIDDEN_MODULES,
    LAUNCHER,
    lb_env,
    loaded_forbidden,
    run_lb,
    run_lb_closed_stdout,
)


def _run_in_process(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int | str | None, str]:
    """cp1252 콘솔을 흉내 낸 스트림으로 run()을 실행하고 (종료 코드, UTF-8로 디코드한 stdout).

    UTF-8 설정을 빼면 --help의 한글을 cp1252로 인코딩하지 못해 실패한다.
    """
    stdout_raw = io.BytesIO()
    stdout = io.TextIOWrapper(stdout_raw, encoding="cp1252")
    stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(sys, "argv", ["lb", *args])

    with pytest.raises(SystemExit) as exc_info:
        run()

    sys.stdout.flush()
    # TextIOWrapper는 Windows에서 \n을 \r\n으로 바꿔 쓴다.
    return exc_info.value.code, stdout_raw.getvalue().decode("utf-8").replace("\r\n", "\n")


def test_run_prints_version_as_utf8_on_cp1252_console(monkeypatch: pytest.MonkeyPatch) -> None:
    code, stdout = _run_in_process(monkeypatch, "--version")

    assert code == 0
    assert stdout == f"logbook {__version__}\n"


def test_run_prints_korean_help_on_cp1252_console(monkeypatch: pytest.MonkeyPatch) -> None:
    code, stdout = _run_in_process(monkeypatch, "--help")

    assert code == 0
    assert "업무 기록·공수 집계 도구" in stdout


def _walk(command: object, path: str) -> list[tuple[str, object]]:
    """명령 트리를 (경로, 명령) 목록으로 펼친다."""
    found = [(path, command)]
    if isinstance(command, TyperGroup):
        for name, child in command.commands.items():
            found.extend(_walk(child, f"{path} {name}"))
    return found


def _misregistered(typer_app: typer.Typer) -> list[str]:
    """LogbookGroup·LogbookCommand가 아닌 그룹과 명령의 '경로: 클래스' 목록."""
    return [
        f"{path}: {type(command).__name__}"
        for path, command in _walk(typer.main.get_command(typer_app), "lb")
        if not isinstance(command, LogbookGroup | LogbookCommand)
    ]


def test_every_command_uses_parse_boundary() -> None:
    # 하위 명령의 인자 파싱(--help, 인자 없는 하위 그룹의 help)은 부모 invoke 안에서 돌므로
    # 모든 명령과 그룹이 자기 make_context에서 닫힌 파이프를 처리해야 한다.
    assert _misregistered(app) == [], (
        "그룹은 cls=LogbookGroup, 명령은 cls=LogbookCommand로 등록하세요"
    )


def test_misregistered_finds_default_classes() -> None:
    scratch = typer.Typer(cls=LogbookGroup)
    sub = typer.Typer()
    scratch.add_typer(sub, name="sub")

    @scratch.callback()
    def root() -> None:
        pass

    @sub.command()
    def plain() -> None:
        pass

    assert _misregistered(scratch) == ["lb sub: TyperGroup", "lb sub plain: TyperCommand"]


def test_lb_fixture_separates_streams(lb: Callable[..., Result]) -> None:
    result = lb("--version")

    assert result.exit_code == 0
    assert result.stdout == f"logbook {__version__}\n"
    assert result.stderr == ""


@pytest.mark.subprocess
def test_launcher_calls_run() -> None:
    if LAUNCHER is None:
        pytest.fail("lb 실행 파일이 없습니다. 'uv sync'를 다시 실행하세요.")
    data = Path(LAUNCHER).read_bytes()
    if b"logbook.cli.main" not in data:
        pytest.skip("lb 실행 파일 형식을 알 수 없어 진입점을 확인하지 못했습니다.")

    assert b"import run" in data, (
        "lb 실행 파일이 예전 진입점(app)을 부릅니다. 'uv sync'를 다시 실행하세요."
    )


@pytest.mark.subprocess
@pytest.mark.parametrize("encoding", ["cp1252", "cp949"])
def test_help_is_utf8_on_legacy_code_page(tmp_path: Path, encoding: str) -> None:
    proc = run_lb(["--help"], env=lb_env(tmp_path, encoding), cwd=tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert "Usage: lb " in proc.stdout
    assert "lb.EXE" not in proc.stdout
    assert "업무 기록" in proc.stdout


@pytest.mark.subprocess
@pytest.mark.parametrize("encoding", ["cp1252", "cp949"])
def test_version_is_exact_on_real_pipe(tmp_path: Path, encoding: str) -> None:
    # 실제 파이프(fd 1)는 CliRunner·capsys와 달리 Windows에서 Rich의 legacy 렌더 경로 후보가 된다.
    proc = run_lb(["--version"], env=lb_env(tmp_path, encoding), cwd=tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == f"logbook {__version__}\n"
    assert proc.stderr == ""


@pytest.mark.subprocess
@pytest.mark.parametrize(
    "args", [["--version"], ["--help"], []], ids=["version", "help", "no-args"]
)
def test_closed_stdout_exits_silently(tmp_path: Path, args: list[str]) -> None:
    proc = run_lb_closed_stdout(args, env=lb_env(tmp_path, "cp1252"), cwd=tmp_path)

    assert proc.returncode == 1
    assert proc.stderr == ""


@pytest.mark.subprocess
def test_no_args_shows_help(tmp_path: Path) -> None:
    proc = run_lb([], env=lb_env(tmp_path, "cp1252"), cwd=tmp_path)

    assert proc.returncode == 2
    assert "Usage: lb " in proc.stdout + proc.stderr


@pytest.mark.subprocess
@pytest.mark.parametrize("args", [[], ["--version"], ["--help"]], ids=["import", "version", "help"])
def test_startup_does_not_load_heavy_modules(tmp_path: Path, args: list[str]) -> None:
    # pytest 프로세스는 conftest 때문에 이미 sqlalchemy를 로드했으므로 새 인터프리터에서 확인한다.
    loaded = loaded_forbidden(args, env=lb_env(tmp_path, "utf-8"), cwd=tmp_path)

    assert loaded == [], f"금지 모듈 로드됨: {loaded} (검사 대상: {FORBIDDEN_MODULES})"
