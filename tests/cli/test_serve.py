"""lb serve: 설정·DB·포트 오류, 시작·종료 출력, 브라우저 열기, 실제 서브프로세스 서버."""

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import Result

from logbook.web import server as web_server
from tests.cli.helpers import assert_rejected, lb_env, run_lb

DEFAULT_PORT = 8765
STARTUP_TIMEOUT_SECONDS = 30
STOP_TIMEOUT_SECONDS = 10
# 설치된 lb.exe는 런처라 terminate()가 서버를 남길 수 있어 인터프리터로 직접 띄운다.
RUN_LB_CODE = "from logbook.cli.main import run; run()"


class FakeServer:
    """build_server 대역. run()은 Ctrl+C를 받은 것처럼 KeyboardInterrupt를 낸다."""

    def __init__(self) -> None:
        self.sockets: list[socket.socket] = []

    def run(self, sockets: list[socket.socket] | None = None) -> None:
        self.sockets = list(sockets or [])
        raise KeyboardInterrupt


def free_port() -> int:
    """지금 비어 있는 포트 번호(바인드 후 닫는다)."""
    with socket.create_server(("127.0.0.1", 0)) as probe:
        port: int = probe.getsockname()[1]
    return port


@pytest.fixture
def fake_server(monkeypatch: pytest.MonkeyPatch) -> FakeServer:
    fake = FakeServer()
    monkeypatch.setattr(web_server, "build_server", lambda app: fake)
    return fake


def start_line(port: int, host: str = "127.0.0.1") -> str:
    return f"✔ 웹 대시보드: http://{host}:{port} (끄려면 Ctrl+C)\n"


STOP_LINE = "웹 대시보드를 종료했습니다.\n"


def test_serve_before_init_reports_missing_database(
    lb: Callable[..., Result], tmp_home: Path
) -> None:
    result = lb("serve")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith(f"오류: 데이터베이스가 없습니다: {tmp_home / 'logbook.db'}")


def test_serve_rejects_non_loopback_host_in_config(
    lb: Callable[..., Result], initialized: Path, tmp_home: Path
) -> None:
    (tmp_home / "config.toml").write_text('[web]\nhost = "0.0.0.0"\n', encoding="utf-8")

    result = lb("serve")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("오류: ")
    assert "host" in result.stderr


def test_serve_prints_start_and_stop_lines_and_releases_resources(
    lb: Callable[..., Result], initialized: Path, fake_server: FakeServer, tmp_path: Path
) -> None:
    result = lb("serve")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == start_line(DEFAULT_PORT) + STOP_LINE
    assert result.stderr == ""
    # 엔진을 dispose하지 않았다면 Windows에서 열린 DB 파일을 옮길 수 없다.
    os.replace(initialized, tmp_path / "moved.db")
    # serve가 끝나면 소켓이 닫혀 있어야 한다.
    assert len(fake_server.sockets) == 1
    assert fake_server.sockets[0].fileno() == -1


def test_serve_closes_socket_so_port_can_be_reopened(
    lb: Callable[..., Result], initialized: Path, fake_server: FakeServer
) -> None:
    port = free_port()

    result = lb("serve", "--port", str(port))

    assert result.exit_code == 0, result.stderr
    with web_server.open_listen_socket(port):
        pass


def test_serve_uses_port_option(
    lb: Callable[..., Result], initialized: Path, fake_server: FakeServer
) -> None:
    port = free_port()

    result = lb("serve", "--port", str(port))

    assert result.stdout == start_line(port) + STOP_LINE


def test_serve_shows_configured_host_in_url(
    lb: Callable[..., Result], initialized: Path, tmp_home: Path, fake_server: FakeServer
) -> None:
    port = free_port()
    (tmp_home / "config.toml").write_text(
        f'[web]\nhost = "localhost"\nport = {port}\n', encoding="utf-8"
    )

    result = lb("serve")

    assert result.stdout == start_line(port, "localhost") + STOP_LINE


def test_serve_rejects_bad_port_before_touching_database(lb: Callable[..., Result]) -> None:
    result = lb("serve", "--port", "abc")

    assert_rejected(
        result,
        "포트가 올바르지 않습니다: 'abc'. 1~65535 사이의 숫자로 입력하세요 (예: --port 8765).",
    )


@pytest.fixture
def opened_urls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """webbrowser.open 호출 기록. 실제 브라우저는 열지 않는다."""
    calls: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, *a, **k: calls.append(url) or True)
    return calls


def test_serve_open_calls_browser_once_with_url(
    lb: Callable[..., Result], initialized: Path, fake_server: FakeServer, opened_urls: list[str]
) -> None:
    port = free_port()

    result = lb("serve", "--port", str(port), "--open")

    assert result.exit_code == 0, result.stderr
    assert opened_urls == [f"http://127.0.0.1:{port}"]
    assert result.stderr == ""


def test_serve_without_open_does_not_call_browser(
    lb: Callable[..., Result], initialized: Path, fake_server: FakeServer, opened_urls: list[str]
) -> None:
    lb("serve")

    assert opened_urls == []


def browser_warning(port: int) -> str:
    return f"주의: 브라우저를 열지 못했습니다. 주소를 직접 여세요: http://127.0.0.1:{port}\n"


def test_serve_open_warns_when_browser_returns_false(
    lb: Callable[..., Result],
    initialized: Path,
    fake_server: FakeServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = free_port()
    monkeypatch.setattr("webbrowser.open", lambda url, *a, **k: False)

    result = lb("serve", "--port", str(port), "--open")

    assert result.exit_code == 0
    assert result.stderr == browser_warning(port)
    assert result.stdout == start_line(port) + STOP_LINE


def test_serve_open_warns_when_browser_raises(
    lb: Callable[..., Result],
    initialized: Path,
    fake_server: FakeServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import webbrowser

    port = free_port()

    def fail(url: str, *args: Any, **kwargs: Any) -> bool:
        raise webbrowser.Error("no browser")

    monkeypatch.setattr("webbrowser.open", fail)

    result = lb("serve", "--port", str(port), "--open")

    assert result.exit_code == 0
    assert result.stderr == browser_warning(port)


def test_serve_open_warns_when_browser_raises_os_error(
    lb: Callable[..., Result],
    initialized: Path,
    fake_server: FakeServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = free_port()

    def fail(url: str, *args: Any, **kwargs: Any) -> bool:
        raise OSError("xdg-open을 실행할 수 없습니다")

    monkeypatch.setattr("webbrowser.open", fail)

    result = lb("serve", "--port", str(port), "--open")

    assert result.exit_code == 0
    assert result.stderr == browser_warning(port)
    assert result.stdout == start_line(port) + STOP_LINE


def test_serve_reports_port_in_use(
    lb: Callable[..., Result], initialized: Path, fake_server: FakeServer, tmp_path: Path
) -> None:
    with socket.create_server(("127.0.0.1", 0)) as holder:
        port = holder.getsockname()[1]

        result = lb("serve", "--port", str(port))

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith(f"오류: 포트를 열 수 없습니다: {port} (")
    assert result.stderr.endswith(
        "). 다른 프로그램이 쓰고 있으면 --port로 다른 포트를 지정하세요.\n"
    )
    # 오류 경로에서도 엔진을 dispose했는지 확인한다.
    os.replace(initialized, tmp_path / "moved.db")


def _with_log(message: str, log_path: Path | None) -> str:
    """실패 메시지에 서버가 남긴 출력(stdout·stderr)을 붙인다."""
    if log_path is None or not log_path.exists():
        return message
    output = log_path.read_text(encoding="utf-8", errors="replace").strip()
    return "\n".join([message, "--- 서버 출력 ---", output or "(없음)"])


def wait_until_ready(
    url: str, proc: "subprocess.Popen[bytes]", log_path: Path | None = None
) -> httpx2.Response:
    """/api/stats가 200이 될 때까지 폴링한다. 서버가 먼저 죽으면 실패로 끝낸다.

    log_path가 있으면 실패 메시지에 그 파일(서버 출력)의 내용을 붙인다.
    """
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    last_error = ""
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            pytest.fail(_with_log(f"서버 프로세스가 먼저 끝났습니다: {proc.returncode}", log_path))
        try:
            response = httpx2.get(url, timeout=2)
        except httpx2.HTTPError as error:
            last_error = str(error)
            time.sleep(0.2)
            continue
        if response.status_code == 200:
            return response
        last_error = f"status {response.status_code}"
        time.sleep(0.2)
    pytest.fail(
        _with_log(
            f"서버가 {STARTUP_TIMEOUT_SECONDS}초 안에 응답하지 않았습니다: {last_error}", log_path
        )
    )


@pytest.fixture
def serve_env(tmp_path: Path) -> dict[str, str]:
    """lb init을 마친 서브프로세스 환경."""
    env = lb_env(tmp_path, "utf-8")
    assert run_lb(["init"], env=env, cwd=tmp_path).returncode == 0
    return env


def spawn_serve(
    port: int, env: dict[str, str], cwd: Path, *, capture: bool, log_path: Path | None = None
) -> "subprocess.Popen[bytes]":
    """서버를 띄운다. capture면 출력을 파이프로 받고, log_path가 있으면 그 파일로 받는다."""
    command = [sys.executable, "-c", RUN_LB_CODE, "serve", "--port", str(port)]
    if log_path is not None:
        # 자식이 핸들을 복제해 쓰므로 부모는 Popen 직후 닫아도 된다.
        with log_path.open("wb") as log:
            return subprocess.Popen(
                command,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=cwd,
                env=env,
            )
    stream = subprocess.PIPE if capture else subprocess.DEVNULL
    return subprocess.Popen(
        command,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=stream,
        stderr=stream,
        cwd=cwd,
        env=env,
    )


@pytest.fixture
def spawned() -> Iterator[list["subprocess.Popen[bytes]"]]:
    """이 테스트가 띄운 서버 프로세스만 끝내고 기다린다(실패해도 남기지 않는다)."""
    procs: list[subprocess.Popen[bytes]] = []
    try:
        yield procs
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=STOP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                pytest.fail(f"서버 프로세스가 끝나지 않았습니다: pid {proc.pid}")
            for pipe in (proc.stdout, proc.stderr):
                if pipe is not None:
                    pipe.close()


@pytest.mark.subprocess
def test_real_server_process_answers_api(
    tmp_path: Path, serve_env: dict[str, str], spawned: list["subprocess.Popen[bytes]"]
) -> None:
    port = free_port()
    log_path = tmp_path / "serve-output.log"
    proc = spawn_serve(port, serve_env, tmp_path, capture=False, log_path=log_path)
    spawned.append(proc)

    response = wait_until_ready(f"http://127.0.0.1:{port}/api/stats", proc, log_path)

    assert response.json()["ok"] is True
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.subprocess
@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows는 자식 프로세스에만 Ctrl+C를 보내기 어렵다."
)
def test_real_server_exits_zero_on_sigint(
    tmp_path: Path, serve_env: dict[str, str], spawned: list["subprocess.Popen[bytes]"]
) -> None:
    port = free_port()
    proc = spawn_serve(port, serve_env, tmp_path, capture=True)
    spawned.append(proc)
    wait_until_ready(f"http://127.0.0.1:{port}/api/stats", proc)

    proc.send_signal(signal.SIGINT)
    out, _ = proc.communicate(timeout=STOP_TIMEOUT_SECONDS)

    assert proc.returncode == 0
    assert out.decode("utf-8").replace("\r\n", "\n").endswith(STOP_LINE)
