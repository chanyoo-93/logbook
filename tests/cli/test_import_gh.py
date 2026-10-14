"""lb task import-gh 테스트. 가짜 list_issues만 쓰고 실제 gh는 부르지 않는다."""

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.cli import render
from logbook.core import github, services
from logbook.core.errors import ExternalServiceError
from logbook.core.github import Issue
from tests.cli.helpers import OpenDb, assert_rejected, run_ok

BAD_REPO = (
    "저장소 형식이 올바르지 않습니다: 'x'. owner/repo 형식으로 쓰세요 (예: chanyoo-93/logbook)."
)
ISSUES = (
    Issue(7, "결제 오류 수정", "https://github.com/a/b/issues/7"),
    Issue(3, "환불 문서", "https://github.com/a/b/issues/3"),
)


class FakeListIssues:
    def __init__(self, issues: Sequence[Issue] = ISSUES) -> None:
        self.issues = tuple(issues)
        self.calls: list[tuple[str, list[str], str, int]] = []

    def __call__(
        self, repo: str, *, labels: Sequence[str], state: str, limit: int, run: object = None
    ) -> tuple[Issue, ...]:
        self.calls.append((repo, list(labels), state, limit))
        return self.issues


@pytest.fixture
def fake_issues(monkeypatch: pytest.MonkeyPatch) -> FakeListIssues:
    fake = FakeListIssues()
    monkeypatch.setattr(github, "list_issues", fake)
    return fake


@pytest.fixture
def payment(lb: Callable[..., Result], initialized: Path) -> Path:
    run_ok(lb, "project", "add", "payment", "결제 서버")
    return initialized


def test_import_gh_creates_tasks_and_prints_them(
    lb: Callable[..., Result], payment: Path, open_db: OpenDb, fake_issues: FakeListIssues
) -> None:
    result = run_ok(
        lb, "task", "import-gh", "a/b", "-l", "bug", "-l", "ui", "-p", "payment", "-c", "dev",
        "-w", "this",
    )  # fmt: skip

    assert result.stdout == (
        f"{render.ok_mark()[0]} 이슈를 태스크로 가져왔습니다: 추가 2건, 건너뜀 0건 (이미 있음)\n"
        "  #1 payment/dev 환불 문서\n"
        "  #2 payment/dev 결제 오류 수정\n"
    )
    assert fake_issues.calls == [("a/b", ["bug", "ui"], "open", 100)]
    with open_db() as s:
        tasks = services.list_tasks(s, project_slug="payment", statuses=None)
        assert [(t.title, t.external_ref, t.planned_week) for t in tasks] == [
            ("환불 문서", "a/b#3", "2026-W40"),
            ("결제 오류 수정", "a/b#7", "2026-W40"),
        ]


def test_import_gh_uses_default_project_and_options(
    lb: Callable[..., Result], initialized: Path, fake_issues: FakeListIssues
) -> None:
    result = run_ok(lb, "task", "import-gh", " a/b ", "--state", "all", "--limit", "5")

    assert "#1 common 환불 문서" in result.stdout
    assert fake_issues.calls == [("a/b", [], "all", 5)]


def test_import_gh_dry_run_changes_nothing(
    lb: Callable[..., Result], payment: Path, open_db: OpenDb, fake_issues: FakeListIssues
) -> None:
    result = run_ok(lb, "task", "import-gh", "a/b", "-p", "payment", "--dry-run")

    assert result.stdout == (
        f"{render.info_mark()} 가져올 이슈: 2건, 건너뛸 이슈: 0건 (이미 있음). "
        "--dry-run이라 추가하지 않았습니다.\n"
        "  #3 환불 문서\n"
        "  #7 결제 오류 수정\n"
    )
    with open_db() as s:
        assert services.list_tasks(s, statuses=None) == []


def test_import_gh_second_run_skips_existing(
    lb: Callable[..., Result], payment: Path, fake_issues: FakeListIssues
) -> None:
    run_ok(lb, "task", "import-gh", "a/b", "-p", "payment")

    result = run_ok(lb, "task", "import-gh", "a/b", "-p", "payment")

    assert result.stdout == (
        f"{render.ok_mark()[0]} 이슈를 태스크로 가져왔습니다: 추가 0건, 건너뜀 2건 (이미 있음)\n"
    )


def test_import_gh_dry_run_counts_skipped(
    lb: Callable[..., Result], payment: Path, fake_issues: FakeListIssues
) -> None:
    run_ok(lb, "task", "import-gh", "a/b", "-p", "payment")

    result = run_ok(lb, "task", "import-gh", "a/b", "-p", "payment", "--dry-run")

    assert result.stdout.startswith(
        f"{render.info_mark()} 가져올 이슈: 0건, 건너뛸 이슈: 2건 (이미 있음). "
    )


def test_import_gh_without_issues_says_so(
    lb: Callable[..., Result], payment: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(github, "list_issues", FakeListIssues(()))

    result = run_ok(lb, "task", "import-gh", "a/b")

    assert result.stdout == f"{render.info_mark()} 가져올 이슈가 없습니다: a/b\n"


def test_import_gh_reports_external_errors(
    lb: Callable[..., Result], payment: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(*args: object, **kwargs: object) -> tuple[Issue, ...]:
        raise ExternalServiceError("명령을 찾을 수 없습니다: gh. 설치하세요.")

    monkeypatch.setattr(github, "list_issues", failing)

    assert_rejected(lb("task", "import-gh", "a/b"), "명령을 찾을 수 없습니다: gh. 설치하세요.")


def test_import_gh_rejects_bad_repo_without_calling_gh(
    lb: Callable[..., Result], fake_issues: FakeListIssues
) -> None:
    assert_rejected(lb("task", "import-gh", "x"), BAD_REPO)
    assert fake_issues.calls == []


def test_import_gh_rejects_bad_state_limit_and_week(
    lb: Callable[..., Result], fake_issues: FakeListIssues
) -> None:
    assert_rejected(
        lb("task", "import-gh", "a/b", "--state", "x"),
        "이슈 상태가 올바르지 않습니다: 'x'. open, closed, all 중 하나를 쓰세요.",
    )
    assert_rejected(
        lb("task", "import-gh", "a/b", "--limit", "0"),
        "가져올 개수는 1~1000 사이의 정수여야 합니다: 0",
    )
    assert_rejected(
        lb("task", "import-gh", "a/b", "-w", "x"),
        "주차 형식이 올바르지 않습니다: 'x'. 예: this, last, next, 2026-W41",
    )
    assert fake_issues.calls == []


def test_import_gh_unknown_project_creates_nothing(
    lb: Callable[..., Result], initialized: Path, fake_issues: FakeListIssues, open_db: OpenDb
) -> None:
    result = lb("task", "import-gh", "a/b", "-p", "nope")

    assert result.exit_code == 1
    with open_db() as s:
        assert services.list_tasks(s, statuses=None) == []


def test_import_gh_dry_run_rejects_unknown_project_and_category(
    lb: Callable[..., Result], payment: Path, fake_issues: FakeListIssues
) -> None:
    unknown = lb("task", "import-gh", "a/b", "-p", "nope", "--dry-run")
    bad_category = lb("task", "import-gh", "a/b", "-p", "payment", "-c", "zzz", "--dry-run")

    assert unknown.exit_code == 1 and unknown.stdout == ""
    assert bad_category.exit_code == 1 and bad_category.stdout == ""
    # 실제 실행과 같은 오류 문구다.
    real = lb("task", "import-gh", "a/b", "-p", "payment", "-c", "zzz")
    assert bad_category.stderr == real.stderr


def test_import_gh_all_skipped_still_rejects_unknown_project(
    lb: Callable[..., Result], payment: Path, fake_issues: FakeListIssues
) -> None:
    run_ok(lb, "task", "import-gh", "a/b", "-p", "payment")

    result = lb("task", "import-gh", "a/b", "-p", "nope")

    assert result.exit_code == 1 and result.stdout == ""
