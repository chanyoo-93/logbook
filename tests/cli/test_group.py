"""LogbookGroup: 도메인 오류와 닫힌 출력 파이프를 처리하는 유일한 오류 경계."""

import errno
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import pytest
import typer
import typer.rich_utils
from typer.testing import CliRunner, Result

from logbook.cli import console
from logbook.cli.group import LogbookCommand, LogbookGroup
from logbook.core.errors import DatabaseBusyError, InvalidInputError, NotFoundError
from tests.cli.helpers import lb_env, run_python_closed_stdout

MARKUP_MESSAGE = "경로가 올바르지 않습니다: 'fix [/api] route'와 [bold]x[/bold]"
LONG_MESSAGE = "오류 문구 " * 33 + "끝."  # 200자
# 줄바꿈 검사용 콘솔 폭. LONG_MESSAGE(333칸)가 이 폭을 넘어야 soft_wrap이 빠졌을 때 접힌다.
NARROW_WIDTH = 80

# --raise <이름>: 인자 파싱 중(make_context) 즉시 옵션 콜백에서 낼 예외
EAGER_ERRORS: dict[str, Callable[[], BaseException]] = {
    "domain": lambda: InvalidInputError("즉시 옵션 오류입니다."),
    "closed": console.OutputClosedError,
    "pipe": BrokenPipeError,
    "einval": lambda: OSError(errno.EINVAL, "Invalid argument"),
    "nospace": lambda: OSError(errno.ENOSPC, "No space"),
}


def _raise_eagerly(value: str | None) -> None:
    if value is not None:
        raise EAGER_ERRORS[value]()


RaiseOpt = Annotated[str | None, typer.Option("--raise", callback=_raise_eagerly, is_eager=True)]

app = typer.Typer(cls=LogbookGroup)
sub = typer.Typer(cls=LogbookGroup)
app.add_typer(sub, name="sub")


@app.callback()
def root(raise_: RaiseOpt = None) -> None:
    pass


@app.command(cls=LogbookCommand)
def fail() -> None:
    raise InvalidInputError("잘못된 입력입니다. 다시 입력하세요.")


@app.command(cls=LogbookCommand)
def busy() -> None:
    raise DatabaseBusyError(
        "데이터베이스를 다른 프로그램이 사용 중입니다: logbook.db. 잠시 후 다시 시도하세요."
    )


@app.command(cls=LogbookCommand)
def bug() -> None:
    raise RuntimeError("버그")


@app.command(cls=LogbookCommand)
def closed() -> None:
    raise console.OutputClosedError


@app.command(cls=LogbookCommand)
def long() -> None:
    raise InvalidInputError(LONG_MESSAGE)


@app.command(cls=LogbookCommand)
def markup() -> None:
    raise InvalidInputError(MARKUP_MESSAGE)


@sub.command(cls=LogbookCommand)
def nested() -> None:
    raise NotFoundError("프로젝트를 찾을 수 없습니다: 'x'.")


@sub.command(cls=LogbookCommand)
def eager(raise_: RaiseOpt = None) -> None:
    pass


# 명령 본문의 OSError(콘솔 쓰기가 아님). Windows에서도 파이프 끊김으로 보면 안 된다.
BODY_EINVAL = OSError(errno.EINVAL, "Invalid argument")


def _raise_einval() -> None:
    raise BODY_EINVAL


@app.command(cls=LogbookCommand)
def einval() -> None:
    _raise_einval()


@sub.command(cls=LogbookCommand, name="einval")
def sub_einval() -> None:
    _raise_einval()


def invoke(*args: str, catch_exceptions: bool = False) -> Result:
    return CliRunner().invoke(app, list(args), prog_name="lb", catch_exceptions=catch_exceptions)


def test_logbook_error_becomes_one_line_on_stderr() -> None:
    result = invoke("fail")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "오류: 잘못된 입력입니다. 다시 입력하세요.\n"


def test_error_in_nested_group_is_caught() -> None:
    result = invoke("sub", "nested")

    assert result.exit_code == 1
    assert result.stderr.startswith("오류: ")


def test_busy_error_is_reported() -> None:
    result = invoke("busy")

    assert result.exit_code == 1
    assert result.stderr.startswith("오류: 데이터베이스를 다른 프로그램이")


def test_error_message_is_printed_literally() -> None:
    result = invoke("markup")

    assert result.exit_code == 1
    assert result.stderr == f"오류: {MARKUP_MESSAGE}\n"


def test_long_error_is_not_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    assert len(LONG_MESSAGE) == 200
    monkeypatch.setattr(console, "PIPE_WIDTH", NARROW_WIDTH)

    result = invoke("long")

    assert result.exit_code == 1
    assert result.stderr == f"오류: {LONG_MESSAGE}\n"


def test_closed_output_silences_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(console, "silence_stdout", lambda: calls.append("silenced"))

    result = invoke("closed")

    assert result.exit_code == 1
    assert calls == ["silenced"]
    assert result.stderr == ""


# 즉시 옵션이 실행되는 위치: 루트 그룹, 또는 하위 그룹의 명령(부모 invoke 안에서 파싱된다)
EAGER_POSITIONS = pytest.mark.parametrize(
    "position", [(), ("sub", "eager")], ids=["root", "subcommand"]
)


@EAGER_POSITIONS
def test_logbook_error_in_eager_option_is_reported(position: tuple[str, ...]) -> None:
    result = invoke(*position, "--raise", "domain")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "오류: 즉시 옵션 오류입니다.\n"


@EAGER_POSITIONS
@pytest.mark.parametrize("name", ["closed", "pipe", "einval"])
def test_closed_output_in_eager_option_silences_stdout(
    monkeypatch: pytest.MonkeyPatch, position: tuple[str, ...], name: str
) -> None:
    error = EAGER_ERRORS[name]()
    if isinstance(error, OSError) and not console.is_broken_pipe(error):
        pytest.skip("이 OS에서는 파이프 끊김이 아니다")
    calls: list[str] = []
    monkeypatch.setattr(console, "silence_stdout", lambda: calls.append("silenced"))

    result = invoke(*position, "--raise", name)

    assert result.exit_code == 1
    assert calls == ["silenced"]
    assert result.stderr == ""


@EAGER_POSITIONS
def test_other_os_error_in_eager_option_propagates(position: tuple[str, ...]) -> None:
    result = invoke(*position, "--raise", "nospace", catch_exceptions=True)

    assert isinstance(result.exception, OSError)
    assert result.exception.errno == errno.ENOSPC


@pytest.mark.parametrize("position", [(), ("sub",)], ids=["root", "sub"])
def test_einval_in_command_body_propagates(
    monkeypatch: pytest.MonkeyPatch, position: tuple[str, ...]
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(console, "silence_stdout", lambda: calls.append("silenced"))

    result = invoke(*position, "einval", catch_exceptions=True)

    assert result.exception is BODY_EINVAL
    assert calls == []


def test_other_exceptions_propagate() -> None:
    result = invoke("bug", catch_exceptions=True)

    assert isinstance(result.exception, RuntimeError)


def test_usage_error_has_no_ansi_on_github_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    result = invoke("--bogus")

    # Typer는 GITHUB_ACTIONS를 import 시점에 FORCE_TERMINAL로 읽어 위 setenv는 로컬에서 효과가 없다.
    # 러너에서 ANSI를 막는 것은 fixture이므로 그 효과를 어느 PC에서나 확인한다.
    assert typer.rich_utils.FORCE_TERMINAL is False
    assert result.exit_code == 2
    assert "\x1b" not in result.stderr


# 닫힌 stdout 회귀용 앱. 실제 파이프에서 Typer help 출력은 우리 출력 함수를 거치지 않으므로
# (Windows는 EINVAL, macOS는 Rich의 BrokenPipeError 처리) 새 인터프리터에서 확인한다.
_CLOSED_STDOUT_DRIVER = """\
import typer

from logbook.cli import console
from logbook.cli.group import LogbookCommand, LogbookGroup
from logbook.core.platform import ensure_utf8_console

app = typer.Typer(cls=LogbookGroup, no_args_is_help=True)
project = typer.Typer(cls=LogbookGroup, no_args_is_help=True)
app.add_typer(project, name="project")


@app.callback()
def root() -> None:
    pass


@app.command(cls=LogbookCommand)
def show() -> None:
    console.print_line("기록")


@project.command(cls=LogbookCommand)
def add(slug: str) -> None:
    console.print_line(slug)


ensure_utf8_console()
app(prog_name="lb", windows_expand_args=False)
"""


@pytest.mark.subprocess
@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["show"],
        ["show", "--help"],
        ["project"],
        ["project", "--help"],
        ["project", "add", "--help"],
        ["project", "add", "x"],
    ],
    ids=lambda args: " ".join(args),
)
def test_closed_stdout_exits_silently_at_every_level(tmp_path: Path, args: list[str]) -> None:
    proc = run_python_closed_stdout(
        _CLOSED_STDOUT_DRIVER, args, env=lb_env(tmp_path, "cp1252"), cwd=tmp_path
    )

    assert proc.returncode == 1
    assert proc.stderr == ""
