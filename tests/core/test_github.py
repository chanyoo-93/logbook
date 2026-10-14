"""logbook.core.github 단위 테스트. 가짜 run_tool만 쓰고 실제 gh는 부르지 않는다."""

import json
from collections.abc import Sequence
from typing import Any

import pytest

from logbook.core import github
from logbook.core.errors import ExternalServiceError, InvalidInputError
from logbook.core.github import Issue

UNREADABLE = "gh 출력을 읽지 못했습니다. gh를 최신 버전으로 업데이트하세요."


class FakeRun:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[tuple[str, list[str], dict[str, Any]]] = []

    def __call__(self, name: str, args: Sequence[str], **kwargs: Any) -> str:
        self.calls.append((name, list(args), kwargs))
        return self.output


def issues_json(*items: object) -> str:
    return json.dumps(list(items))


@pytest.mark.parametrize("text", ["a/b", " a-1/b.c_d "])
def test_parse_repo_accepts_owner_repo(text: str) -> None:
    assert github.parse_repo(text) == text.strip()


@pytest.mark.parametrize("text", ["a", "a/b/c", "https://github.com/a/b", "한/글"])
def test_parse_repo_rejects_other_forms(text: str) -> None:
    with pytest.raises(InvalidInputError) as error:
        github.parse_repo(text)

    assert str(error.value) == (
        f"저장소 형식이 올바르지 않습니다: '{text.strip()}'. "
        "owner/repo 형식으로 쓰세요 (예: chanyoo-93/logbook)."
    )


@pytest.mark.parametrize("state", ["open", "closed", "all"])
def test_check_state_accepts_known_states(state: str) -> None:
    assert github.check_state(state) == state


def test_check_state_rejects_unknown() -> None:
    with pytest.raises(InvalidInputError) as error:
        github.check_state("x")

    assert str(error.value) == (
        "이슈 상태가 올바르지 않습니다: 'x'. open, closed, all 중 하나를 쓰세요."
    )


@pytest.mark.parametrize("value", [1, 100, 1000])
def test_check_limit_accepts_range(value: int) -> None:
    assert github.check_limit(value) == value


@pytest.mark.parametrize("value", [0, -1, 1001])
def test_check_limit_rejects_out_of_range(value: int) -> None:
    with pytest.raises(InvalidInputError) as error:
        github.check_limit(value)

    assert str(error.value) == f"가져올 개수는 1~1000 사이의 정수여야 합니다: {value}"


def test_issue_ref_joins_repo_and_number() -> None:
    assert github.issue_ref("a/b", 7) == "a/b#7"


def test_list_issues_builds_gh_arguments_and_parses_output() -> None:
    run = FakeRun(
        issues_json(
            {"number": 2, "title": "둘", "url": "u2", "extra": 1},
            {"number": 1, "title": "하나", "url": "u1"},
        )
    )

    issues = github.list_issues("a/b", labels=["bug", "ui"], state="open", limit=100, run=run)

    assert issues == (Issue(2, "둘", "u2"), Issue(1, "하나", "u1"))
    name, args, kwargs = run.calls[0]
    assert name == "gh"
    assert args == [
        "issue",
        "list",
        "-R",
        "a/b",
        "--state",
        "open",
        "--limit",
        "100",
        "--json",
        "number,title,url",
        "--label",
        "bug",
        "--label",
        "ui",
    ]
    assert kwargs["timeout"] == 30.0
    assert kwargs["label"] == "gh issue list"
    assert kwargs["missing_hint"] == github.GH_MISSING_HINT


def test_list_issues_without_labels_has_no_label_arguments() -> None:
    run = FakeRun("[]")

    assert github.list_issues("a/b", labels=[], state="all", limit=5, run=run) == ()
    assert "--label" not in run.calls[0][1]


@pytest.mark.parametrize(
    "output",
    [
        "not json",
        '{"number": 1}',
        issues_json(1),
        issues_json({"number": "1", "title": "t", "url": "u"}),
        issues_json({"number": True, "title": "t", "url": "u"}),
        issues_json({"number": 1, "title": 2, "url": "u"}),
        issues_json({"number": 1, "title": "t"}),
    ],
)
def test_list_issues_rejects_unexpected_output(output: str) -> None:
    with pytest.raises(ExternalServiceError) as error:
        github.list_issues("a/b", labels=[], state="open", limit=1, run=FakeRun(output))

    assert str(error.value) == UNREADABLE


def test_list_issues_propagates_run_errors() -> None:
    def failing(name: str, args: Sequence[str], **kwargs: Any) -> str:
        raise ExternalServiceError("명령을 찾을 수 없습니다: gh. x")

    with pytest.raises(ExternalServiceError):
        github.list_issues("a/b", labels=[], state="open", limit=1, run=failing)
