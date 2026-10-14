"""gh CLI로 GitHub 이슈 목록을 읽는다(태스크 가져오기). DB에 접근하지 않는다."""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from logbook.core.errors import ExternalServiceError, InvalidInputError
from logbook.core.external import RunTool, run_tool

ISSUE_STATES = ("open", "closed", "all")
MAX_ISSUE_LIMIT = 1000
DEFAULT_ISSUE_LIMIT = 100
GH_TIMEOUT_SECONDS = 30.0

GH_MISSING_HINT = "GitHub CLI를 설치한 뒤 'gh auth login'을 실행하세요: https://cli.github.com"
BAD_REPO = (
    "저장소 형식이 올바르지 않습니다: '{echo}'. "
    "owner/repo 형식으로 쓰세요 (예: chanyoo-93/logbook)."
)
BAD_STATE = "이슈 상태가 올바르지 않습니다: '{echo}'. open, closed, all 중 하나를 쓰세요."
BAD_LIMIT = "가져올 개수는 1~{max} 사이의 정수여야 합니다: {value}"
UNREADABLE_OUTPUT = "gh 출력을 읽지 못했습니다. gh를 최신 버전으로 업데이트하세요."

# 소유자는 영숫자로 시작하는 영숫자·하이픈, 저장소는 영숫자·점·밑줄·하이픈(ASCII만)
_REPO_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+")


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    url: str


def parse_repo(text: str) -> str:
    """'owner/repo'만 받는다(앞뒤 공백 제거). 형식이 다르면 InvalidInputError."""
    repo = text.strip()
    if _REPO_PATTERN.fullmatch(repo) is None:
        raise InvalidInputError(BAD_REPO.format(echo=repo))
    return repo


def check_state(text: str) -> str:
    if text not in ISSUE_STATES:
        raise InvalidInputError(BAD_STATE.format(echo=text))
    return text


def check_limit(value: int) -> int:
    if not 1 <= value <= MAX_ISSUE_LIMIT:
        raise InvalidInputError(BAD_LIMIT.format(max=MAX_ISSUE_LIMIT, value=value))
    return value


def issue_ref(repo: str, number: int) -> str:
    return f"{repo}#{number}"


def _parse_issue(item: object) -> Issue:
    if not isinstance(item, dict):
        raise ExternalServiceError(UNREADABLE_OUTPUT)
    number, title, url = item.get("number"), item.get("title"), item.get("url")
    # bool은 int의 하위 클래스라 따로 거른다.
    if isinstance(number, bool) or not isinstance(number, int):
        raise ExternalServiceError(UNREADABLE_OUTPUT)
    if not isinstance(title, str) or not isinstance(url, str):
        raise ExternalServiceError(UNREADABLE_OUTPUT)
    return Issue(number, title, url)


def list_issues(
    repo: str,
    *,
    labels: Sequence[str],
    state: str,
    limit: int,
    run: RunTool = run_tool,
) -> tuple[Issue, ...]:
    """gh issue list -R repo --state state --limit limit --json number,title,url [--label L ...]"""
    args = [
        "issue",
        "list",
        "-R",
        repo,
        "--state",
        state,
        "--limit",
        str(limit),
        "--json",
        "number,title,url",
    ]
    for label in labels:
        args.extend(("--label", label))
    output = run(
        "gh",
        args,
        missing_hint=GH_MISSING_HINT,
        label="gh issue list",
        timeout=GH_TIMEOUT_SECONDS,
    )
    try:
        data = json.loads(output)
    except ValueError as error:
        raise ExternalServiceError(UNREADABLE_OUTPUT) from error
    if not isinstance(data, list):
        raise ExternalServiceError(UNREADABLE_OUTPUT)
    return tuple(_parse_issue(item) for item in data)
