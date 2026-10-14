"""logbook.core.external 단위 테스트."""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from logbook.core import external
from logbook.core.errors import ExternalServiceError
from logbook.core.external import run_tool

FOUND = "C:/tools/git.exe"
HINT = "git을 설치하세요: https://git-scm.com"


class FakeRun:
    """subprocess.run 대용. 받은 인자를 기록하고 정해 둔 결과나 예외를 돌려준다."""

    def __init__(
        self,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        error: BaseException | None = None,
    ) -> None:
        self.result = subprocess.CompletedProcess([], returncode, stdout, stderr)
        self.error = error
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(external.shutil, "which", lambda name: FOUND)


def install(monkeypatch: pytest.MonkeyPatch, fake: FakeRun) -> FakeRun:
    monkeypatch.setattr(external.subprocess, "run", fake)
    return fake


def test_missing_executable_raises_with_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(external.shutil, "which", lambda name: None)

    with pytest.raises(ExternalServiceError) as excinfo:
        run_tool("git", ["log"], missing_hint=HINT)

    assert str(excinfo.value) == f"명령을 찾을 수 없습니다: git. {HINT}"


@pytest.mark.usefixtures("found")
def test_runs_with_list_args_and_returns_utf8_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = install(monkeypatch, FakeRun(stdout="한글\n".encode()))
    before = dict(external.os.environ)

    output = run_tool("git", ["-C", "repo", "log"], missing_hint=HINT, timeout=3.5)

    assert output == "한글\n"
    [(args, kwargs)] = fake.calls
    assert args == [FOUND, "-C", "repo", "log"]
    assert kwargs["shell"] is False
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is False
    assert kwargs["timeout"] == 3.5
    assert kwargs["env"]["GH_PROMPT_DISABLED"] == "1"
    assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert dict(external.os.environ) == before


@pytest.mark.usefixtures("found")
def test_default_timeout_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = install(monkeypatch, FakeRun())

    run_tool("git", ["log"], missing_hint=HINT)

    assert fake.calls[0][1]["timeout"] == external.DEFAULT_TIMEOUT_SECONDS == 10.0


@pytest.mark.usefixtures("found")
def test_nonzero_exit_reports_first_stderr_line(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeRun(returncode=1, stderr=b"  fatal: bad\nmore"))

    with pytest.raises(ExternalServiceError) as excinfo:
        run_tool("git", ["-C", "x", "log"], missing_hint=HINT, label="git log")

    assert str(excinfo.value) == "명령이 실패했습니다: git log (종료 코드 1). fatal: bad"


@pytest.mark.usefixtures("found")
def test_nonzero_exit_without_stderr_has_no_trailing_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, FakeRun(returncode=2))

    with pytest.raises(ExternalServiceError) as excinfo:
        run_tool("git", ["log"], missing_hint=HINT)

    assert str(excinfo.value) == "명령이 실패했습니다: git (종료 코드 2)."


@pytest.mark.usefixtures("found")
def test_long_stderr_line_is_cut_at_200_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeRun(returncode=1, stderr=("가" * 300).encode()))

    with pytest.raises(ExternalServiceError) as excinfo:
        run_tool("git", ["log"], missing_hint=HINT)

    assert str(excinfo.value).endswith("(종료 코드 1). " + "가" * 200)


@pytest.mark.usefixtures("found")
def test_invalid_utf8_is_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeRun(stdout=b"ok\xff\n"))

    assert run_tool("git", ["log"], missing_hint=HINT) == "ok\ufffd\n"


@pytest.mark.usefixtures("found")
def test_timeout_reports_seconds_and_label(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeRun(error=subprocess.TimeoutExpired("git", 2.0)))

    with pytest.raises(ExternalServiceError) as excinfo:
        run_tool("git", ["log"], missing_hint=HINT, label="git log", timeout=2.0)

    assert str(excinfo.value) == "명령이 2초 안에 끝나지 않았습니다: git log."


@pytest.mark.usefixtures("found")
def test_os_error_reports_strerror(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeRun(error=OSError(13, "Permission denied")))

    with pytest.raises(ExternalServiceError) as excinfo:
        run_tool("git", ["log"], missing_hint=HINT, label="git log")

    assert str(excinfo.value) == "명령을 실행하지 못했습니다: git log (Permission denied)."


def test_runs_a_real_process(monkeypatch: pytest.MonkeyPatch) -> None:
    # 실제 프로세스를 띄우는 유일한 테스트: 현재 파이썬 인터프리터를 쓴다.
    python = Path(sys.executable)
    monkeypatch.setattr(shutil, "which", lambda name: str(python))

    code = "import sys; sys.stdout.buffer.write(b'ok\\n')"

    assert run_tool("python", ["-c", code], missing_hint=HINT) == "ok\n"
