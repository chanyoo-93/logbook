"""logbook.core.gitcollect 단위 테스트. 가짜 run_tool과 tmp_path의 실제 git 저장소를 쓴다."""

import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from logbook.core import external, gitcollect
from logbook.core.config import Config, GitConfig, GitRepo, ReportConfig
from logbook.core.errors import ExternalServiceError
from logbook.core.gitcollect import RepoCommits, collect_commits, report_commits, to_commit_groups
from logbook.core.report import CommitGroup, CommitLine
from logbook.core.weeks import Week

KST = timezone(timedelta(hours=9))
WEEK = Week(2026, 42)  # 2026-10-12 ~ 2026-10-18
SEP = "\x1f"


def log_line(hash_: str, author_date: str, subject: str) -> str:
    return f"{hash_}{SEP}{author_date}{SEP}{subject}"


class FakeRun:
    """저장소 경로(-C 다음 인자)별로 정해 둔 결과를 돌려주고 호출을 기록한다."""

    def __init__(self, logs: dict[str, str | Exception], email: str | Exception = "me@x.com"):
        self.logs = logs
        self.email = email
        self.calls: list[tuple[str, list[str], dict[str, Any]]] = []

    def __call__(self, name: str, args: Sequence[str], **kwargs: Any) -> str:
        self.calls.append((name, list(args), kwargs))
        if "config" in args:
            if isinstance(self.email, Exception):
                raise self.email
            return self.email
        result = self.logs[args[1]]
        if isinstance(result, Exception):
            raise result
        return result


def repos(tmp_path: Path, *names: str) -> GitConfig:
    paths = []
    for name in names:
        path = tmp_path / name
        path.mkdir()
        paths.append(GitRepo(project=f"p-{name}", path=path))
    return GitConfig(author_email="me@x.com", repos=tuple(paths))


def test_collect_commits_parses_lines_and_passes_exact_arguments(tmp_path: Path) -> None:
    git = repos(tmp_path, "a", "b")
    a, b = (str(r.path) for r in git.repos)
    run = FakeRun(
        {
            a: "\n".join(
                [
                    log_line("a1b2c3d4e5f6", "2026-10-12T10:00:00+09:00", " 첫 커밋 "),
                    log_line("0123456789ab", "2026-10-13T09:30:00+09:00", "둘째"),
                ]
            ),
            b: "\n".join(
                [
                    log_line("ffffffffffff", "2026-10-14T01:00:00+00:00", "UTC 새벽"),
                    log_line("eeeeeeeeeeee", "2026-10-18T23:59:59+09:00", "마지막 날"),
                ]
            ),
        }
    )

    results = collect_commits(git, WEEK, tz=KST, run=run)

    assert [r.project for r in results] == ["p-a", "p-b"]
    assert results[0].path == git.repos[0].path
    assert results[0].commits == (
        CommitLine("2026-10-12", "a1b2c3d", "첫 커밋"),
        CommitLine("2026-10-13", "0123456", "둘째"),
    )
    # UTC 01:00 은 KST 10:00 이라 같은 날이다.
    assert results[1].commits == (
        CommitLine("2026-10-14", "fffffff", "UTC 새벽"),
        CommitLine("2026-10-18", "eeeeeee", "마지막 날"),
    )
    assert all(r.error == "" for r in results)
    name, args, kwargs = run.calls[0]
    assert name == "git"
    assert args == [
        "-C",
        a,
        "-c",
        "i18n.logOutputEncoding=UTF-8",
        "log",
        "--all",
        "--no-merges",
        "--reverse",
        "--fixed-strings",
        "--regexp-ignore-case",
        "--author=<me@x.com>",
        "--since=2026-10-12T00:00:00+09:00",
        "--until=2026-10-19T00:00:00+09:00",
        "--format=%H%x1f%aI%x1f%s",
    ]
    assert kwargs["label"] == "git log"
    assert kwargs["missing_hint"] == gitcollect.GIT_MISSING_HINT


def test_collect_commits_uses_config_email_when_author_email_is_empty(tmp_path: Path) -> None:
    git = replace(repos(tmp_path, "a"), author_email="")
    path = str(git.repos[0].path)
    run = FakeRun({path: ""}, email="cfg@x.com\nignored\n")

    (result,) = collect_commits(git, WEEK, tz=KST, run=run)

    assert result.error == "" and result.commits == ()
    name, args, kwargs = run.calls[0]
    assert (name, args, kwargs["label"]) == (
        "git",
        ["-C", path, "config", "user.email"],
        "git config",
    )
    assert "--author=<cfg@x.com>" in run.calls[1][1]


@pytest.mark.parametrize("email", [ExternalServiceError("종료 코드 1"), "\n"])
def test_collect_commits_reports_unknown_email(tmp_path: Path, email: str | Exception) -> None:
    git = replace(repos(tmp_path, "a"), author_email="")
    run = FakeRun({}, email=email)

    (result,) = collect_commits(git, WEEK, tz=KST, run=run)

    assert result.error == gitcollect.EMAIL_UNKNOWN.format(path=git.repos[0].path)
    assert result.commits == ()
    assert len(run.calls) == 1


def test_collect_commits_reports_missing_git_instead_of_unknown_email(tmp_path: Path) -> None:
    git = replace(repos(tmp_path, "a"), author_email="")
    missing = external.ToolNotFoundError(
        external.TOOL_NOT_FOUND.format(name="git", hint=gitcollect.GIT_MISSING_HINT)
    )
    run = FakeRun({}, email=missing)

    (result,) = collect_commits(git, WEEK, tz=KST, run=run)

    assert result.error == str(missing)
    assert gitcollect.EMAIL_UNKNOWN.split("{")[0] not in result.error
    assert len(run.calls) == 1


def test_collect_commits_continues_after_missing_folder_and_run_error(tmp_path: Path) -> None:
    git = repos(tmp_path, "ok", "broken")
    missing = GitRepo(project="gone", path=tmp_path / "없는 폴더")
    git = replace(git, repos=(missing, git.repos[1], git.repos[0]))
    run = FakeRun(
        {
            str(git.repos[1].path): ExternalServiceError(
                "명령이 실패했습니다: git log (종료 코드 128)."
            ),
            str(git.repos[2].path): log_line("abcdefabcdef", "2026-10-15T12:00:00+09:00", "정상"),
        }
    )

    gone, broken, ok = collect_commits(git, WEEK, tz=KST, run=run)

    assert gone.error == gitcollect.REPO_MISSING.format(path=missing.path)
    assert gone.commits == ()
    assert broken.error == "명령이 실패했습니다: git log (종료 코드 128)."
    assert ok.error == "" and ok.commits == (CommitLine("2026-10-15", "abcdefa", "정상"),)
    assert len(run.calls) == 2  # 없는 폴더는 git을 부르지 않는다.


def test_collect_commits_skips_malformed_lines_and_out_of_week_dates(tmp_path: Path) -> None:
    git = repos(tmp_path, "a")
    path = str(git.repos[0].path)
    output = "\n".join(
        [
            "",
            "칸이 모자란 줄",
            f"aaaaaaa{SEP}2026-10-13T10:00:00+09:00",
            f"bbbbbbb{SEP}2026-10-13T10:00:00+09:00{SEP}칸이{SEP}넘침",
            log_line("1111111111", "2026-10-11T23:59:59+09:00", "주 시작 전"),
            log_line("2222222222", "2026-10-19T00:00:00+09:00", "끝 경계(다음 주 월요일)"),
            log_line("3333333333", "2026-10-16T08:00:00+09:00", "주 안"),
        ]
    )

    (result,) = collect_commits(git, WEEK, tz=KST, run=FakeRun({path: output}))

    assert result.commits == (CommitLine("2026-10-16", "3333333", "주 안"),)


@dataclass(frozen=True)
class EdgeWeek:
    """end 다음 날이 date 범위를 벗어나는 가짜 주."""

    start: date = date(9999, 12, 26)
    end: date = date.max
    label: str = "9999-W52"

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end


def test_collect_commits_marks_every_repo_when_week_range_overflows(tmp_path: Path) -> None:
    git = repos(tmp_path, "a", "b")
    run = FakeRun({})

    results = collect_commits(git, EdgeWeek(), tz=KST, run=run)  # type: ignore[arg-type]

    assert [r.error for r in results] == [gitcollect.WEEK_OUT_OF_RANGE.format(week="9999-W52")] * 2
    assert [r.project for r in results] == ["p-a", "p-b"]
    assert run.calls == []


def test_to_commit_groups_keeps_only_repos_with_commits(tmp_path: Path) -> None:
    line = CommitLine("2026-10-12", "a1b2c3d", "제목")
    results = (
        RepoCommits("p1", tmp_path / "r1", ()),
        RepoCommits("p2", tmp_path / "r2", (line,)),
        RepoCommits("p3", tmp_path / "r3", (), error="실패"),
        RepoCommits("p4", tmp_path / "r4", (line,)),
    )

    assert to_commit_groups(results) == (
        CommitGroup("p2", "r2", (line,)),
        CommitGroup("p4", "r4", (line,)),
    )


def make_config(tmp_path: Path, git: GitConfig, *, include_commits: bool = True) -> Config:
    return Config(
        db_path=tmp_path / "x.db",
        report=ReportConfig(include_commits=include_commits),
        git=git,
    )


def test_report_commits_returns_empty_when_disabled_or_no_repos(tmp_path: Path) -> None:
    git = repos(tmp_path, "a")
    run = FakeRun({})

    assert report_commits(
        make_config(tmp_path, git, include_commits=False), WEEK, tz=KST, run=run
    ) == ((), ())
    assert report_commits(make_config(tmp_path, GitConfig()), WEEK, tz=KST, run=run) == ((), ())
    assert run.calls == []


def test_report_commits_returns_groups_and_warnings(tmp_path: Path) -> None:
    git = repos(tmp_path, "good", "bad")
    run = FakeRun(
        {
            str(git.repos[0].path): log_line("abcdefabcdef", "2026-10-15T12:00:00+09:00", "정상"),
            str(git.repos[1].path): ExternalServiceError("실패 문구"),
        }
    )

    groups, warnings = report_commits(make_config(tmp_path, git), WEEK, tz=KST, run=run)

    assert groups == (
        CommitGroup("p-good", "good", (CommitLine("2026-10-15", "abcdefa", "정상"),)),
    )
    assert warnings == (gitcollect.REPO_WARNING.format(project="p-bad", message="실패 문구"),)


@pytest.fixture
def git_env(tmp_path: Path) -> dict[str, str]:
    """사용자 전역·시스템 git 설정이 테스트에 섞이지 않게 하는 환경 변수."""
    empty = tmp_path / "empty-gitconfig"
    empty.write_text("", encoding="utf-8", newline="\n")
    return {"GIT_CONFIG_GLOBAL": str(empty), "GIT_CONFIG_NOSYSTEM": "1"}


def run_git(repo: Path, *args: str, env: dict[str, str]) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={**os.environ, **env},
    )


def commit(repo: Path, subject: str, when: str, email: str, env: dict[str, str]) -> None:
    run_git(
        repo,
        "-c",
        f"user.email={email}",
        "-c",
        "user.name=me",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--allow-empty",
        "-m",
        subject,
        env={**env, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when},
    )


def test_collect_commits_with_real_git(tmp_path: Path, git_env: dict[str, str]) -> None:
    if shutil.which("git") is None:
        pytest.skip("git이 없습니다.")
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", env=git_env)
    # 지난주를 먼저 만든다(git은 --since보다 오래된 커밋을 만나면 탐색을 멈춘다).
    commit(repo, "지난주 작업", "2026-10-09T12:00:00+09:00", "me@example.com", git_env)
    commit(repo, "이번 주 한글 제목", "2026-10-14T12:00:00+09:00", "me@example.com", git_env)
    commit(repo, "남의 커밋", "2026-10-15T12:00:00+09:00", "other@example.com", git_env)
    commit(repo, "부분 일치 이메일", "2026-10-15T13:00:00+09:00", "some@example.com", git_env)
    commit(repo, "대문자 이메일", "2026-10-16T12:00:00+09:00", "ME@Example.com", git_env)
    commit(repo, "끝 경계", "2026-10-19T00:00:00+09:00", "me@example.com", git_env)
    git = GitConfig(author_email="me@example.com", repos=(GitRepo("proj", repo),))

    (result,) = collect_commits(git, WEEK, tz=KST)

    assert result.error == ""
    assert [(c.date, c.subject) for c in result.commits] == [
        ("2026-10-14", "이번 주 한글 제목"),
        ("2026-10-16", "대문자 이메일"),
    ]
    assert len(result.commits[0].hash) == 7
