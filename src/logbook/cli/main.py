"""lb CLI 엔트리포인트."""

from typing import Annotated

import typer
from rich.console import Console

from logbook import __version__

app = typer.Typer(help="업무 기록·공수 집계 도구", no_args_is_help=True)


def _version_callback(value: bool) -> None:
    if value:
        Console(highlight=False).print(f"logbook {__version__}")
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
