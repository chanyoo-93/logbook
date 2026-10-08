"""CLI 출력의 유일한 통로: 결정적인 Rich Console, 출력 함수, 표 폭 계산, 파이프 끊김 처리.

rich는 CLI 시작 시간을 줄이려고 함수 안에서 지연 import한다.
"""

import contextlib
import errno
import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import TypeAlias

    from rich.console import Console, RenderableType
    from rich.table import Table
    from rich.text import Text

    # print_line·print_notice에 넘기는 한 조각: 고정 문구, (문자열, 스타일), 사용자 데이터(Text)
    LinePart: TypeAlias = str | tuple[str, str] | Text

# stdout/stderr가 TTY가 아닐 때(파이프, 파일, 테스트)의 고정 폭. 기록 한 건이 한 줄로 유지된다.
PIPE_WIDTH = 1000
# box=None, pad_edge=False, 기본 padding (0, 1)에서 열 사이 칸 수
COLUMN_GAP = 2


class OutputClosedError(Exception):
    """stdout 파이프가 닫혀 더 쓸 수 없음."""


def is_broken_pipe(error: OSError) -> bool:
    """출력 파이프가 닫혀 난 오류인지. Windows는 BrokenPipeError 대신 EINVAL을 낸다."""
    if isinstance(error, BrokenPipeError):
        return True
    return os.name == "nt" and error.errno == errno.EINVAL


def _silence(stream: Any) -> None:
    """stream의 파일 디스크립터를 devnull로 돌려 종료 시 flush 오류가 나지 않게 한다.

    쓰기에 실패한 바이트는 스트림 버퍼에 남아 인터프리터 종료 시 다시 flush된다. 그때 실패하면
    종료 코드가 120으로 바뀌므로, 닫힌 파이프 대신 devnull로 흘려보낸다.
    """
    # 의도적으로 best-effort: 파일 디스크립터가 없는 스트림(테스트 등)은 그대로 둔다.
    with contextlib.suppress(OSError, ValueError, AttributeError):
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, stream.fileno())
        finally:
            os.close(devnull)


def silence_stdout() -> None:
    """stdout 파일 디스크립터를 devnull로 돌린다(닫힌 stdout 파이프)."""
    _silence(sys.stdout)


def _silence_stderr() -> None:
    """stderr 파일 디스크립터를 devnull로 돌린다(닫힌 stderr 파이프는 조용히 무시한다)."""
    _silence(sys.stderr)


def _is_tty(stream: Any) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, OSError, ValueError):
        return False


def _raise_output_closed() -> None:
    raise OutputClosedError


def _make_console(*, stderr: bool) -> "Console":
    from rich.console import Console

    stream = sys.stderr if stderr else sys.stdout
    # TTY가 아니면 두 OS가 같은 바이트를 내도록 폭과 렌더 경로를 고정한다.
    # PIPE_WIDTH는 호출 시점에 읽는다(테스트가 monkeypatch로 바꾼다).
    options: dict[str, Any] = (
        {} if _is_tty(stream) else {"width": PIPE_WIDTH, "legacy_windows": False}
    )
    console = Console(stderr=stderr, markup=False, emoji=False, highlight=False, **options)
    # Rich 기본 동작(stdout을 devnull로 돌리고 SystemExit)을 대신한다.
    console.on_broken_pipe = _silence_stderr if stderr else _raise_output_closed  # type: ignore[method-assign]
    return console


def out() -> "Console":
    """stdout Console."""
    return _make_console(stderr=False)


def err() -> "Console":
    """stderr Console."""
    return _make_console(stderr=True)


def _write_out(console: "Console", renderable: "RenderableType", **kwargs: Any) -> None:
    try:
        console.print(renderable, **kwargs)
    except OSError as error:
        # 판정은 쓰기 지점에서만 한다(처리기 전체에서 EINVAL을 삼키면 진짜 경로 오류를 숨긴다).
        if is_broken_pipe(error):
            raise OutputClosedError from error
        raise


def _write_err(renderable: "RenderableType", **kwargs: Any) -> None:
    try:
        err().print(renderable, **kwargs)
    except OSError as error:
        if not is_broken_pipe(error):
            raise
        _silence_stderr()


def _assemble(parts: "Sequence[LinePart]") -> "Text":
    from rich.text import Text

    return Text.assemble(*parts)


def print_line(*parts: "LinePart") -> None:
    """stdout에 한 줄을 출력한다. 사용자 데이터는 Text나 (문자열, 스타일)로 넘긴다."""
    _write_out(out(), _assemble(parts), soft_wrap=True)


def print_notice(*parts: "LinePart", end: str = "\n") -> None:
    """stderr에 접두어 없는 안내를 출력한다. 확인 프롬프트는 end=""로 쓴다."""
    _write_err(_assemble(parts), soft_wrap=True, end=end)


def print_warning(message: str) -> None:
    """stderr에 '주의: ' 경고 한 줄."""
    from rich.text import Text

    _write_err(Text.assemble(("주의: ", "yellow"), Text(message)), soft_wrap=True)


def print_error(message: str) -> None:
    """stderr에 '오류: ' 오류 한 줄."""
    from rich.text import Text

    _write_err(Text.assemble(("오류: ", "bold red"), Text(message)), soft_wrap=True)


def _cell_width(cell: "RenderableType") -> int:
    from rich.cells import cell_len
    from rich.text import Text

    if isinstance(cell, Text):
        return cell.cell_len
    if isinstance(cell, str):
        return cell_len(cell)
    raise TypeError(f"폭을 계산할 수 없는 셀입니다: {type(cell).__name__}")


def required_width(table: "Table") -> int:
    """표를 자르지 않고 그리는 데 필요한 폭 (box=None, pad_edge=False, 기본 padding 기준).

    no_wrap 열은 머리글과 셀 중 가장 넓은 칸 수, 그 밖의 열은 min_width(없으면 1)를 쓴다.
    rich.measure.Measurement는 no_wrap 셀을 단어 단위로 재고 min_width를 무시해 쓰지 않는다.
    """
    if not table.columns:
        return 0
    total = COLUMN_GAP * (len(table.columns) - 1)
    for column in table.columns:
        if column.no_wrap:
            total += max(_cell_width(cell) for cell in (column.header, *column.cells))
        else:
            total += column.min_width or 1
    return total


def print_table(table: "Table", fallback: "Callable[[], Sequence[Text]] | None" = None) -> None:
    """표를 stdout에 출력한다. fallback이 있고 폭이 모자라면 표 대신 한 줄 목록을 출력한다."""
    console = out()
    needed = required_width(table)
    if fallback is not None and needed > console.width:
        print_notice(
            f"터미널 폭이 좁아 표 대신 목록으로 보여 줍니다 (표에는 {needed}칸이 필요합니다)."
        )
        for line in fallback():
            _write_out(console, line, soft_wrap=True)
        return
    _write_out(console, table)


def print_raw(text: str) -> None:
    """text를 Rich Text로 stdout에 쓴다. 마크업·이모지 해석, 줄 접기, 줄바꿈 추가를 하지 않는다.

    Rich Text를 거치므로 탭은 공백으로 펼쳐지고 제어 문자는 지워진다(받아들인 절충이다).
    """
    from rich.text import Text

    _write_out(out(), Text(text), soft_wrap=True, end="")
