"""web.server: 실제 uvicorn을 스레드에서 띄워 요청을 보낸다."""

import socket
import threading
import time

import httpx2
import pytest

from logbook.core.errors import LogbookError
from logbook.web.app import create_app
from logbook.web.context import WebContext
from logbook.web.server import BIND_ADDRESS, build_server, open_listen_socket

STARTUP_TIMEOUT_SECONDS = 10
JOIN_TIMEOUT_SECONDS = 10


def test_serves_api_over_real_socket(web_ctx: WebContext) -> None:
    sock = open_listen_socket(0)
    port = sock.getsockname()[1]
    server = build_server(create_app(web_ctx))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started, "서버가 시작되지 않았습니다"

        response = httpx2.get(f"http://127.0.0.1:{port}/api/stats", timeout=5)
    finally:
        server.should_exit = True
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)
        sock.close()

    assert not thread.is_alive()
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["error"] is None
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "server" not in response.headers


def test_open_listen_socket_binds_loopback_only() -> None:
    with open_listen_socket(0) as sock:
        assert sock.getsockname()[0] == BIND_ADDRESS == "127.0.0.1"


def test_open_listen_socket_reports_port_in_use_in_korean() -> None:
    with open_listen_socket(0) as holder:
        port = holder.getsockname()[1]

        with pytest.raises(LogbookError) as exc_info:
            open_listen_socket(port)

    message = str(exc_info.value)
    assert message.startswith(f"포트를 열 수 없습니다: {port} (")
    assert message.endswith("). 다른 프로그램이 쓰고 있으면 --port로 다른 포트를 지정하세요.")


def test_open_listen_socket_returns_listening_socket() -> None:
    with open_listen_socket(0) as sock:
        port = sock.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
