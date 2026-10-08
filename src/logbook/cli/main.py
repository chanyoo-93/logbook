"""lb CLI 엔트리포인트."""

from typing import Annotated

import typer

from logbook import __version__
from logbook.cli import console
from logbook.cli.commands import CommandModule, add, init, log, project, stats
from logbook.cli.group import LogbookGroup
from logbook.core.platform import ensure_utf8_console

app = typer.Typer(
    name="lb",
    cls=LogbookGroup,
    help="업무 기록·공수 집계 도구",
    no_args_is_help=True,
    add_completion=False,  # 영어 자동완성 옵션은 Phase 7에서 다시 켠다.
)

# 등록 순서대로 help에 나온다. 단, Typer는 단일 명령(init, add, stats)을 그룹(project, log)보다
# 먼저 보여 준다.
COMMAND_MODULES: tuple[CommandModule, ...] = (init, project, add, log, stats)


def _register_commands(target: typer.Typer) -> None:
    for module in COMMAND_MODULES:
        module.register(target)


_register_commands(app)


def _version_callback(value: bool) -> None:
    if value:
        console.print_line(f"logbook {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="버전을 출력하고 종료합니다.",
        ),
    ] = False,
) -> None:
    pass


def run() -> None:
    """설치된 lb 실행 파일의 진입점.

    Click이 인자를 파싱하기 전에 콘솔을 UTF-8로 맞춘다.
    - prog_name: Windows에서 'Usage: lb.EXE'가 되는 것을 막는다.
    - windows_expand_args=False: Windows에서 Click이 인자에 ~, %VAR%, $VAR, glob을 펼쳐
      메모를 바꾸는 것을 막는다(예: '%USERNAME% 미팅' → 'User 미팅').
    """
    ensure_utf8_console()
    app(prog_name="lb", windows_expand_args=False)
