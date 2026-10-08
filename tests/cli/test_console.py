"""cli.console: 결정적 Console, 출력 함수, 필요 폭 계산과 좁은 화면 대체 출력, 파이프 끊김."""

import errno
import io
import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
import typer
import typer.rich_utils
from rich.table import Table
from rich.text import Text
from typer.testing import CliRunner

from logbook.cli import console
from logbook.cli.group import LogbookGroup
from logbook.core import platform
from tests.cli.helpers import assert_fits, lb_env, run_python_closed_stderr, tokens

FOLD_CELL = "가나다라마바사아자차카"
# soft_wrap 검사: NARROW_WIDTH보다 넓은 한 줄(공백이 있어 단어 단위로 접힐 수 있다)
NARROW_WIDTH = 20
LONG_LINE = "기록 메모 " * 10 + "끝"
NARROW_NOTICE = "터미널 폭이 좁아 표 대신 목록으로 보여 줍니다 (표에는 23칸이 필요합니다).\n"

app = typer.Typer(cls=LogbookGroup)


@app.command()
def widths() -> None:
    console.print_line(f"{console.out().width} {console.err().width}")


@app.command()
def styled() -> None:
    console.print_line(
        (platform.symbol("✔", "v"), "green"), " 저장 ", (f"{platform.symbol('—', '-')} 메모", "dim")
    )
    console.print_warning("경고")
    console.print_error("실패")


class BrokenStream(io.StringIO):
    """쓰기마다 지정한 OSError를 내는 가짜 출력 스트림."""

    def __init__(self, error: OSError) -> None:
        super().__init__()
        self.error = error

    def write(self, s: str) -> int:
        raise self.error


def sample_table() -> Table:
    table = Table(box=None, pad_edge=False)
    table.add_column("A", no_wrap=True)
    table.add_column("B", overflow="fold", min_width=10)
    table.add_column("한글", no_wrap=True)
    table.add_row("12345", Text(FOLD_CELL), Text("x"))
    return table


def fallback_lines() -> list[Text]:
    return [Text(f"12345 {FOLD_CELL} x")]


def test_consoles_use_pipe_width_when_not_a_tty() -> None:
    result = CliRunner().invoke(app, ["widths"], catch_exceptions=False)

    assert result.stdout == f"{console.PIPE_WIDTH} {console.PIPE_WIDTH}\n"
    assert console.PIPE_WIDTH == 1000


def test_consoles_use_modern_renderer_when_not_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    # Windows에서 Rich는 콘솔이 아닌 fd 1/2에 legacy win32 렌더 경로를 고른다.
    # StringIO 스트림에는 fileno가 없어 그 경로에 닿지 않으므로 설정 자체를 확인한다.
    # pytest -s로 실행해도 비 TTY 분기를 타도록 스트림을 직접 바꾼다.
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    assert console.out().legacy_windows is False
    assert console.err().legacy_windows is False


def test_output_has_no_ansi_on_github_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    # 러너에서는 Typer가 import 시점에 GITHUB_ACTIONS를 읽어 FORCE_TERMINAL=True가 된다. 로컬에서도
    # 그 상태를 흉내 내, 우리 Console이 Typer 설정과 무관하게 ANSI를 내지 않는지 확인한다.
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", True)

    result = CliRunner().invoke(app, ["styled"], catch_exceptions=False)

    assert "\x1b" not in result.stdout
    assert "\x1b" not in result.stderr


def test_messages_go_to_their_streams() -> None:
    result = CliRunner().invoke(app, ["styled"], catch_exceptions=False)

    assert result.stdout == "✔ 저장 — 메모\n"
    assert result.stderr == "주의: 경고\n오류: 실패\n"


def test_symbols_fall_back_to_ascii(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "supports_unicode", lambda text="": False)

    result = CliRunner().invoke(app, ["styled"], catch_exceptions=False)

    assert result.stdout == "v 저장 - 메모\n"


def test_user_data_is_printed_literally(capsys: pytest.CaptureFixture[str]) -> None:
    console.print_line(Text("fix [/api] route [bold]x[/bold] :smile: 끝\\"))

    assert capsys.readouterr().out == "fix [/api] route [bold]x[/bold] :smile: 끝\\\n"


@pytest.mark.parametrize(
    ("printer", "prefix", "stream"),
    [
        (console.print_line, "", "out"),
        (console.print_notice, "", "err"),
        (console.print_warning, "주의: ", "err"),
        (console.print_error, "오류: ", "err"),
    ],
    ids=["line", "notice", "warning", "error"],
)
def test_line_wider_than_console_is_not_wrapped(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    printer: Callable[[str], None],
    prefix: str,
    stream: str,
) -> None:
    monkeypatch.setattr(console, "PIPE_WIDTH", NARROW_WIDTH)

    printer(LONG_LINE)

    captured = capsys.readouterr()
    assert getattr(captured, stream) == f"{prefix}{LONG_LINE}\n"


def test_broken_pipe_error_is_broken_pipe() -> None:
    assert console.is_broken_pipe(BrokenPipeError())


@pytest.mark.skipif(os.name != "nt", reason="Windows 전용 동작")
def test_einval_is_broken_pipe_on_windows() -> None:
    assert console.is_broken_pipe(OSError(errno.EINVAL, "Invalid argument"))


@pytest.mark.skipif(os.name == "nt", reason="Windows가 아닌 OS의 동작")
def test_einval_is_not_broken_pipe_elsewhere() -> None:
    assert not console.is_broken_pipe(OSError(errno.EINVAL, "Invalid argument"))


def test_other_os_error_is_not_broken_pipe() -> None:
    assert not console.is_broken_pipe(OSError(errno.ENOENT, "No such file"))


def test_broken_stdout_raises_output_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", BrokenStream(BrokenPipeError()))

    with pytest.raises(console.OutputClosedError):
        console.print_line("x")


@pytest.mark.skipif(os.name != "nt", reason="Windows 전용 동작")
def test_einval_on_stdout_raises_output_closed_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdout", BrokenStream(OSError(errno.EINVAL, "Invalid argument")))

    with pytest.raises(console.OutputClosedError):
        console.print_line("x")


def test_other_os_error_on_stdout_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", BrokenStream(OSError(errno.ENOSPC, "No space")))

    with pytest.raises(OSError) as exc_info:
        console.print_line("x")

    assert not isinstance(exc_info.value, console.OutputClosedError)
    assert exc_info.value.errno == errno.ENOSPC


@pytest.mark.parametrize(
    "error", [BrokenPipeError(), OSError(errno.EINVAL, "Invalid argument")], ids=["pipe", "einval"]
)
def test_broken_stderr_is_ignored(monkeypatch: pytest.MonkeyPatch, error: OSError) -> None:
    if not console.is_broken_pipe(error):
        pytest.skip("이 OS에서는 파이프 끊김이 아니다")
    monkeypatch.setattr(sys, "stderr", BrokenStream(error))

    console.print_error("실패")
    console.print_notice("안내")
    console.print_warning("주의")


def test_other_os_error_on_stderr_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stderr", BrokenStream(OSError(errno.ENOSPC, "No space")))

    with pytest.raises(OSError) as exc_info:
        console.print_error("실패")

    assert exc_info.value.errno == errno.ENOSPC


def test_silence_stdout_ignores_streams_without_fileno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())

    console.silence_stdout()


def test_required_width_sums_columns_and_gaps() -> None:
    assert console.required_width(sample_table()) == 5 + 10 + 4 + 2 * 2


def test_required_width_of_empty_table() -> None:
    assert console.required_width(Table(box=None, pad_edge=False)) == 0


def test_table_fits_at_required_width(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(console, "PIPE_WIDTH", 23)
    called: list[bool] = []

    def fallback() -> list[Text]:
        called.append(True)
        return fallback_lines()

    console.print_table(sample_table(), fallback)

    captured = capsys.readouterr()
    assert_fits(captured.out, 23)
    rows = captured.out.splitlines()
    assert tokens(rows[0]) == ["A", "B", "한글"]
    assert tokens(rows[1])[0] == "12345"
    assert tokens(rows[1])[-1] == "x"
    assert called == []
    assert captured.err == ""


def test_narrow_console_prints_fallback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(console, "PIPE_WIDTH", 22)

    console.print_table(sample_table(), fallback_lines)

    captured = capsys.readouterr()
    # 대체 줄(30칸)이 콘솔 폭(22칸)보다 넓어도 접히지 않는다(soft_wrap).
    assert captured.out == f"12345 {FOLD_CELL} x\n"
    assert captured.err == NARROW_NOTICE


def test_narrow_console_without_fallback_prints_table(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(console, "PIPE_WIDTH", 22)

    console.print_table(sample_table())

    captured = capsys.readouterr()
    assert captured.out.splitlines()[0].startswith("A")
    assert captured.err == ""


def test_print_notice_without_newline(capsys: pytest.CaptureFixture[str]) -> None:
    console.print_notice("질문 [y/N]: ", end="")

    assert capsys.readouterr().err == "질문 [y/N]: "


# 닫힌 stderr 회귀용 앱. stderr 쓰기가 실패해도 버퍼에 남은 바이트 때문에 인터프리터 종료 시
# flush가 실패하면 종료 코드가 120이 된다. 이를 새 인터프리터에서 확인한다.
_CLOSED_STDERR_DRIVER = """\
import typer

from logbook.cli import console
from logbook.cli.group import LogbookCommand, LogbookGroup
from logbook.core.errors import InvalidInputError
from logbook.core.platform import ensure_utf8_console

app = typer.Typer(cls=LogbookGroup)


@app.callback()
def root() -> None:
    pass


@app.command(cls=LogbookCommand)
def fail() -> None:
    raise InvalidInputError("잘못된 입력입니다.")


@app.command(cls=LogbookCommand)
def warn() -> None:
    console.print_warning("주의할 점")
    console.print_line("저장")


ensure_utf8_console()
app(prog_name="lb", windows_expand_args=False)
"""


@pytest.mark.subprocess
@pytest.mark.parametrize(
    ("command", "returncode", "stdout"),
    [("fail", 1, ""), ("warn", 0, "저장\n")],
    ids=["error", "success-with-warning"],
)
def test_closed_stderr_keeps_exit_code(
    tmp_path: Path, command: str, returncode: int, stdout: str
) -> None:
    proc = run_python_closed_stderr(
        _CLOSED_STDERR_DRIVER, [command], env=lb_env(tmp_path, "cp1252"), cwd=tmp_path
    )

    assert proc.returncode == returncode
    assert proc.stdout == stdout


# --- print_raw ---


def test_print_raw_keeps_single_trailing_newline(capsys: pytest.CaptureFixture[str]) -> None:
    console.print_raw("# 제목\n본문\n")

    assert capsys.readouterr().out == "# 제목\n본문\n"


def test_print_raw_adds_no_newline(capsys: pytest.CaptureFixture[str]) -> None:
    console.print_raw("끝")

    assert capsys.readouterr().out == "끝"


def test_print_raw_keeps_blank_lines_and_trailing_spaces(
    capsys: pytest.CaptureFixture[str],
) -> None:
    text = "a  \n\n\nb \n"

    console.print_raw(text)

    assert capsys.readouterr().out == text


@pytest.mark.parametrize("line", ["x" * 1500, "가" * 600], ids=["ascii", "korean"])
def test_print_raw_does_not_wrap_long_lines(capsys: pytest.CaptureFixture[str], line: str) -> None:
    console.print_raw(line + "\n")

    assert capsys.readouterr().out == line + "\n"


def test_print_raw_does_not_interpret_markup(capsys: pytest.CaptureFixture[str]) -> None:
    console.print_raw("[bold]x[/bold] :smile: [/api]\n")

    assert capsys.readouterr().out == "[bold]x[/bold] :smile: [/api]\n"


def test_print_raw_raises_output_closed_on_broken_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", BrokenStream(BrokenPipeError()))

    with pytest.raises(console.OutputClosedError):
        console.print_raw("x\n")
