"""lb serve: 웹 대시보드 실행."""

from typing import Annotated

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand


def _announce_ready(url: str) -> None:
    console.print_line(render.ok_mark(), f" 웹 대시보드: {url} (끄려면 Ctrl+C)")


def _warn_browser_failed(url: str) -> None:
    console.print_warning(f"브라우저를 열지 못했습니다. 주소를 직접 여세요: {url}")


def serve(
    port: Annotated[
        str | None,
        typer.Option("--port", metavar="PORT", help="포트 (기본: 설정 web.port, 8765)"),
    ] = None,
    open_browser: Annotated[
        bool, typer.Option("--open", help="브라우저로 대시보드를 엽니다.")
    ] = False,
) -> None:
    """웹 대시보드를 실행합니다. 이 컴퓨터(127.0.0.1)에서만 열리고 Ctrl+C로 끕니다."""
    # DB·설정 없이 끝나는 검증을 먼저 한다.
    chosen_port = runtime.parse_port(port) if port is not None else None

    cfg = runtime.settings()

    # FastAPI·uvicorn은 이 명령에서만 로드한다(다른 명령의 시작 시간을 늘리지 않는다).
    from logbook.core.config import config_path
    from logbook.web.server import serve as run_server

    run_server(
        cfg,
        config_file=config_path(),
        port=chosen_port if chosen_port is not None else cfg.web.port,
        open_browser=open_browser,
        now=runtime.now,
        on_ready=_announce_ready,
        on_browser_failed=_warn_browser_failed,
    )
    console.print_line("웹 대시보드를 종료했습니다.")


def register(app: typer.Typer) -> None:
    app.command("serve", cls=LogbookCommand)(serve)
