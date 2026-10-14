"""외부 명령(git, gh) 실행 공용 함수. DB에 접근하지 않는다."""

import os
import shutil
import subprocess
from collections.abc import Callable, Sequence

from logbook.core.errors import ExternalServiceError

DEFAULT_TIMEOUT_SECONDS = 10.0
# stderr 첫 줄을 문구에 담을 때의 최대 글자 수
MAX_STDERR_CHARS = 200

TOOL_NOT_FOUND = "명령을 찾을 수 없습니다: {name}. {hint}"
TOOL_TIMEOUT = "명령이 {seconds}초 안에 끝나지 않았습니다: {label}."
TOOL_OS_ERROR = "명령을 실행하지 못했습니다: {label} ({reason})."
TOOL_FAILED = "명령이 실패했습니다: {label} (종료 코드 {code})."

# 대화형 입력을 기다리며 멈추지 않게 한다.
_NON_INTERACTIVE_ENV = {"GH_PROMPT_DISABLED": "1", "GIT_TERMINAL_PROMPT": "0"}


class ToolNotFoundError(ExternalServiceError):
    """실행 파일(git, gh)을 찾지 못했다. 설치 안내가 들어 있는 한 줄 문구."""


def _first_stderr_line(stderr: bytes) -> str:
    text = stderr.decode("utf-8", errors="replace").strip()
    if not text:
        return ""
    return text.splitlines()[0].strip()[:MAX_STDERR_CHARS]


def run_tool(
    name: str,
    args: Sequence[str],
    *,
    missing_hint: str,
    label: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """name(git, gh)을 찾아 목록 인자로 실행하고 stdout(UTF-8, 잘못된 바이트는 대체)을 돌려준다.

    실패는 모두 ExternalServiceError(한 줄 문구)다. label은 문구에 쓸 이름이다(기본 name).
    """
    shown = label or name
    executable = shutil.which(name)
    if executable is None:
        raise ToolNotFoundError(TOOL_NOT_FOUND.format(name=name, hint=missing_hint))
    try:
        result = subprocess.run(
            [executable, *args],
            shell=False,
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            env={**os.environ, **_NON_INTERACTIVE_ENV},
        )
    except subprocess.TimeoutExpired as error:
        raise ExternalServiceError(
            TOOL_TIMEOUT.format(seconds=f"{timeout:g}", label=shown)
        ) from error
    except OSError as error:
        raise ExternalServiceError(
            TOOL_OS_ERROR.format(label=shown, reason=error.strerror or error)
        ) from error
    if result.returncode != 0:
        message = TOOL_FAILED.format(label=shown, code=result.returncode)
        detail = _first_stderr_line(result.stderr)
        raise ExternalServiceError(f"{message} {detail}" if detail else message)
    return result.stdout.decode("utf-8", errors="replace")


# run_tool과 같은 시그니처의 호출 가능 객체. 테스트가 가짜를 넘긴다.
RunTool = Callable[..., str]
