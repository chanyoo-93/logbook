"""서버 실행: 루프백 소켓을 먼저 열고 uvicorn에 넘긴다.

소켓을 직접 열면 포트·DB 오류를 uvicorn의 영어 로그가 아니라 한국어 한 줄로 알릴 수 있다.
"""

import contextlib
import socket
import webbrowser
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from logbook.core import db
from logbook.core.config import Config
from logbook.core.errors import LogbookError
from logbook.web.app import create_app
from logbook.web.context import WebContext

BIND_ADDRESS = "127.0.0.1"


def open_listen_socket(port: int) -> socket.socket:
    """127.0.0.1:port에서 듣는 소켓을 연다. 0이면 빈 포트를 고른다.

    create_server는 Windows에서 SO_REUSEADDR를 켜지 않아 다른 프로그램이 같은 포트를 가로챌 수
    없다. errno가 OS마다 다르므로(Windows 10048, macOS 48) OSError 전체를 같은 문구로 바꾼다.
    """
    try:
        return socket.create_server((BIND_ADDRESS, port))
    except OSError as error:
        raise LogbookError(
            f"포트를 열 수 없습니다: {port} ({error.strerror or error}). "
            "다른 프로그램이 쓰고 있으면 --port로 다른 포트를 지정하세요."
        ) from error


def build_server(app: FastAPI) -> uvicorn.Server:
    config = uvicorn.Config(
        app, log_level="warning", access_log=False, server_header=False, lifespan="off"
    )
    return uvicorn.Server(config)


def _open_browser(url: str, on_browser_failed: Callable[[str], None]) -> None:
    try:
        opened = webbrowser.open(url)
    except webbrowser.Error:
        opened = False
    if not opened:
        on_browser_failed(url)


def serve(
    cfg: Config,
    *,
    config_file: Path,
    port: int,
    open_browser: bool,
    now: Callable[[], datetime],
    on_ready: Callable[[str], None],
    on_browser_failed: Callable[[str], None],
) -> None:
    """서버를 실행하고 종료(Ctrl+C)할 때까지 돌아오지 않는다."""
    engine = db.open_database(cfg.db_path)
    try:
        sock = open_listen_socket(port)
    except BaseException:
        engine.dispose()
        raise
    try:
        server = build_server(create_app(WebContext(cfg, engine, config_file, now)))
        url = f"http://{cfg.web.host}:{port}"
        on_ready(url)
        if open_browser:
            # 소켓이 이미 듣는 중이라 서버가 뜨기 전의 접속은 대기열에서 기다린다.
            _open_browser(url, on_browser_failed)
        # uvicorn은 Ctrl+C로 정상 종료한 뒤 SIGINT를 다시 일으킨다. 정상 종료다.
        with contextlib.suppress(KeyboardInterrupt):
            server.run(sockets=[sock])
    finally:
        sock.close()
        engine.dispose()
