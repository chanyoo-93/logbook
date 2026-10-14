"""lb git-collect와 lb report의 커밋 부록 테스트 (오늘 = 2026-10-01, W40)."""

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.core import gitcollect
from logbook.core.gitcollect import RepoCommits
from logbook.core.report import CommitLine
from tests.cli.helpers import assert_rejected, run_ok
from tests.helpers import FakeCollect

NO_REPOS = "설정된 저장소가 없습니다. 설정 파일에 [[git.repos]]를 추가하세요."
BAD_WEEK = "주차 형식이 올바르지 않습니다: 'x'. 예: this, last, next, 2026-W41"


def write_config(tmp_home: Path, repos: tuple[tuple[str, str], ...], extra: str = "") -> None:
    blocks = "".join(
        f'[[git.repos]]\nproject = "{project}"\npath = "{(tmp_home / name).as_posix()}"\n'
        for project, name in repos
    )
    (tmp_home / "config.toml").write_text(extra + blocks, encoding="utf-8", newline="\n")


def results(tmp_home: Path) -> tuple[RepoCommits, ...]:
    return (
        RepoCommits(
            "payment",
            tmp_home / "payment-server",
            (
                CommitLine("2026-09-29", "a1b2c3d", "재시도 백오프 구현"),
                CommitLine("2026-09-30", "b2c3d4e", "환불 API 초안 [x]"),
            ),
        ),
        RepoCommits("admin", tmp_home / "admin-web", ()),
    )


@pytest.fixture
def fake_collect(monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> FakeCollect:
    fake = FakeCollect(results(tmp_home))
    monkeypatch.setattr(gitcollect, "collect_commits", fake)
    return fake


def test_git_collect_prints_commits_per_repo(
    lb: Callable[..., Result], tmp_home: Path, fake_collect: FakeCollect
) -> None:
    write_config(tmp_home, (("payment", "payment-server"), ("admin", "admin-web")))

    result = run_ok(lb, "git-collect")

    assert result.stdout == (
        "payment (payment-server) 2건\n"
        "  2026-09-29 a1b2c3d 재시도 백오프 구현\n"
        "  2026-09-30 b2c3d4e 환불 API 초안 [x]\n"
        "admin (admin-web) 0건\n"
    )
    assert result.stderr == ""
    assert [call[1].label for call in fake_collect.calls] == ["2026-W40"]


def test_git_collect_does_not_need_database(
    lb: Callable[..., Result], tmp_home: Path, fake_collect: FakeCollect
) -> None:
    write_config(tmp_home, (("payment", "payment-server"),))

    result = run_ok(lb, "git-collect", "-w", "last")

    assert not (tmp_home / "logbook.db").exists()
    assert [call[1].label for call in fake_collect.calls] == ["2026-W39"]
    assert result.exit_code == 0


def test_git_collect_without_repos_is_rejected(lb: Callable[..., Result], tmp_home: Path) -> None:
    assert_rejected(lb("git-collect"), NO_REPOS)


def test_git_collect_reports_repo_errors_and_exits_1(
    lb: Callable[..., Result], tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_home, (("payment", "payment-server"), ("admin", "admin-web")))
    broken = (
        RepoCommits("payment", tmp_home / "payment-server", (), "저장소 폴더가 없습니다: x."),
        RepoCommits(
            "admin", tmp_home / "admin-web", (CommitLine("2026-09-30", "b2c3d4e", "수정"),)
        ),
    )
    monkeypatch.setattr(gitcollect, "collect_commits", FakeCollect(broken))

    result = lb("git-collect")

    assert result.exit_code == 1
    assert result.stdout == "admin (admin-web) 1건\n  2026-09-30 b2c3d4e 수정\n"
    assert (
        result.stderr
        == "주의: 저장소 폴더가 없습니다: x.\n오류: 저장소 1곳에서 커밋을 읽지 못했습니다.\n"
    )


def test_git_collect_rejects_bad_week(lb: Callable[..., Result], tmp_home: Path) -> None:
    assert_rejected(lb("git-collect", "-w", "x"), BAD_WEEK)


def test_report_appends_commits(
    lb: Callable[..., Result], initialized: Path, tmp_home: Path, fake_collect: FakeCollect
) -> None:
    write_config(tmp_home, (("payment", "payment-server"), ("admin", "admin-web")))

    result = run_ok(lb, "report")

    assert "## 부록. 커밋 내역\n" in result.stdout
    assert "### payment (payment-server)\n" in result.stdout
    assert "- 2026-09-29 a1b2c3d 재시도 백오프 구현\n" in result.stdout
    assert "admin-web" not in result.stdout
    assert result.stderr == ""


def test_report_skips_commits_when_disabled(
    lb: Callable[..., Result], initialized: Path, tmp_home: Path, fake_collect: FakeCollect
) -> None:
    write_config(
        tmp_home, (("payment", "payment-server"),), extra="[report]\ninclude_commits = false\n"
    )

    result = run_ok(lb, "report")

    assert "부록" not in result.stdout
    assert fake_collect.calls == []


def test_report_warns_on_collect_errors_and_still_prints(
    lb: Callable[..., Result], initialized: Path, tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_home, (("payment", "payment-server"),))
    broken = (RepoCommits("payment", tmp_home / "payment-server", (), "git 실패"),)
    monkeypatch.setattr(gitcollect, "collect_commits", FakeCollect(broken))

    result = run_ok(lb, "report")

    assert result.stderr == "주의: 커밋을 모으지 못했습니다: payment (git 실패)\n"
    assert result.stdout.startswith("# 주간업무보고 (2026-09-28 ~ 2026-10-04)\n")
    assert "부록" not in result.stdout
