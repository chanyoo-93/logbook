"""CLI 테스트 도우미 (fixture가 아닌 함수와 상수)."""

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, NamedTuple

import pytest
from rich.cells import cell_len

# CLI 시작 경로(import, --version, --help)에서 로드되면 안 되는 모듈
FORBIDDEN_MODULES = (
    "sqlalchemy",
    "logbook.core.db",
    "logbook.core.models",
    "logbook.core.services",
    "fastapi",
    "uvicorn",
    "jinja2",
    "pyperclip",
)

# 현재 인터프리터와 같은 가상환경의 lb 실행 파일 (Windows: Scripts\lb.exe, macOS: bin/lb)
LAUNCHER: str | None = shutil.which("lb", path=str(Path(sys.executable).parent))

SUBPROCESS_TIMEOUT_SECONDS = 60

# 서브프로세스 출력 모양을 바꾸는 환경변수
_REMOVED_ENV_VARS = (
    "PYTHONUTF8",
    "COLUMNS",
    "LINES",
    "FORCE_COLOR",
    "NO_COLOR",
    "PY_COLORS",
    "TTY_COMPATIBLE",
    "TTY_INTERACTIVE",
    "GITHUB_ACTIONS",
)

# 새 인터프리터에서 run()을 실행한 뒤 로드된 금지 모듈을 결과 파일(JSON)에 기록한다.
# argv: <결과 파일> [lb 인자…]. lb 인자가 없으면 import만 한다.
_GUARD_DRIVER = """\
import json
import sys

FORBIDDEN = {forbidden!r}
result_path, cli_args = sys.argv[1], sys.argv[2:]
from logbook.cli.main import run

if cli_args:
    sys.argv = ["lb", *cli_args]
    try:
        run()
    except SystemExit:
        pass
loaded = sorted(name for name in FORBIDDEN if name in sys.modules)
with open(result_path, "w", encoding="utf-8") as f:
    json.dump(loaded, f)
"""


class Proc(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def tokens(line: str) -> list[str]:
    """표의 한 줄을 두 칸 이상의 공백으로 나눈 토큰 목록."""
    return re.split(r"\s{2,}", line.strip())


def assert_fits(text: str, width: int) -> None:
    """모든 줄이 width 칸 이하인지 확인한다."""
    for line in text.splitlines():
        assert cell_len(line) <= width, f"{cell_len(line)}칸 > {width}칸: {line!r}"


def lb_env(base: Path, encoding: str) -> dict[str, str]:
    """서브프로세스 lb 환경: 임시 홈·DB·설정, 지정한 콘솔 인코딩, 결정적인 Typer 출력."""
    env = {k: v for k, v in os.environ.items() if k not in _REMOVED_ENV_VARS}
    home = base / "home"
    home.mkdir(parents=True, exist_ok=True)
    data = base / "data"
    env.update(
        {
            "PYTHONIOENCODING": encoding,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "LOGBOOK_DB": str(data / "logbook.db"),
            "LOGBOOK_CONFIG": str(data / "config.toml"),
            # %USERNAME% 펼침을 감지하려면 값이 있어야 한다.
            "USERNAME": "lbtest",
            "_TYPER_FORCE_DISABLE_TERMINAL": "1",
            "TERMINAL_WIDTH": "200",
        }
    )
    return env


def _decode(data: bytes) -> str:
    return data.decode("utf-8").replace("\r\n", "\n")


def run_lb(
    args: Sequence[str], *, env: dict[str, str], cwd: Path, input: str | None = None
) -> Proc:
    """설치된 lb 실행 파일을 실행한다. 출력은 UTF-8 strict로 디코드하고 줄바꿈을 \\n으로 맞춘다.

    input은 자식 프로세스가 stdin을 읽는 인코딩(PYTHONIOENCODING)으로 인코딩한다.
    """
    if LAUNCHER is None:
        pytest.fail("lb 실행 파일이 없습니다. 'uv sync'를 다시 실행하세요.")
    # input이 없으면 stdin을 devnull로 준다(부모의 stdin을 물려받아 확인 프롬프트가 멈추지 않게).
    stdin_kwargs: dict[str, Any] = (
        {"stdin": subprocess.DEVNULL}
        if input is None
        else {"input": input.encode(env.get("PYTHONIOENCODING") or "utf-8")}
    )
    completed = subprocess.run(
        [LAUNCHER, *args],
        shell=False,
        capture_output=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        cwd=cwd,
        env=env,
        **stdin_kwargs,
    )
    return Proc(completed.returncode, _decode(completed.stdout), _decode(completed.stderr))


def run_lb_closed_stdout(args: Sequence[str], *, env: dict[str, str], cwd: Path) -> Proc:
    """읽는 쪽을 먼저 닫은 파이프를 stdout으로 주고 lb를 실행한다(`lb … | head`가 끝난 상황).

    첫 쓰기부터 실패한다: macOS는 BrokenPipeError, Windows는 EINVAL. Proc.stdout은 항상 ''다.
    """
    if LAUNCHER is None:
        pytest.fail("lb 실행 파일이 없습니다. 'uv sync'를 다시 실행하세요.")
    return _run_closed([LAUNCHER, *args], closed="stdout", env=env, cwd=cwd)


def run_python_closed_stdout(
    code: str, args: Sequence[str], *, env: dict[str, str], cwd: Path
) -> Proc:
    """run_lb_closed_stdout과 같은 조건에서 새 인터프리터로 `python -c code args…`를 실행한다."""
    return _run_closed([sys.executable, "-c", code, *args], closed="stdout", env=env, cwd=cwd)


def run_python_closed_stderr(
    code: str, args: Sequence[str], *, env: dict[str, str], cwd: Path
) -> Proc:
    """읽는 쪽을 먼저 닫은 파이프를 stderr로 주고 `python -c code args…`를 실행한다.

    Proc.stderr는 항상 ''다.
    """
    return _run_closed([sys.executable, "-c", code, *args], closed="stderr", env=env, cwd=cwd)


def _run_closed(
    command: Sequence[str],
    *,
    closed: Literal["stdout", "stderr"],
    env: dict[str, str],
    cwd: Path,
) -> Proc:
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    streams: dict[str, Any] = (
        {"stdout": write_fd, "stderr": subprocess.PIPE}
        if closed == "stdout"
        else {"stdout": subprocess.PIPE, "stderr": write_fd}
    )
    try:
        completed = subprocess.run(
            list(command),
            shell=False,
            stdin=subprocess.DEVNULL,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            cwd=cwd,
            env=env,
            **streams,
        )
    finally:
        os.close(write_fd)
    if closed == "stdout":
        return Proc(completed.returncode, "", _decode(completed.stderr))
    return Proc(completed.returncode, _decode(completed.stdout), "")


def loaded_forbidden(args: Sequence[str], *, env: dict[str, str], cwd: Path) -> list[str]:
    """새 인터프리터에서 lb 인자로 run()을 실행하고 로드된 FORBIDDEN_MODULES 목록을 반환한다.

    args가 비어 있으면 run()을 부르지 않고 import만 한다.
    """
    result_path = cwd / "loaded-modules.json"
    driver = _GUARD_DRIVER.format(forbidden=FORBIDDEN_MODULES)
    completed = subprocess.run(
        [sys.executable, "-c", driver, str(result_path), *args],
        shell=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        cwd=cwd,
        env=env,
    )
    if completed.returncode != 0:
        pytest.fail(f"import 가드 드라이버 실패: {completed.stderr.decode('utf-8', 'replace')}")
    loaded: list[str] = json.loads(result_path.read_text(encoding="utf-8"))
    return loaded
