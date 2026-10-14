"""git 저장소에서 한 주의 본인 커밋을 모은다(보고서 부록). DB에 접근하지 않는다."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from pathlib import Path

from logbook.core.config import Config, GitConfig, GitRepo
from logbook.core.errors import ExternalServiceError
from logbook.core.external import RunTool, run_tool
from logbook.core.report import CommitGroup, CommitLine
from logbook.core.weeks import Week

GIT_MISSING_HINT = "git을 설치하세요: https://git-scm.com"
REPO_MISSING = "저장소 폴더가 없습니다: {path}. 설정의 [[git.repos]] path를 확인하세요."
EMAIL_UNKNOWN = "작성자 이메일을 알 수 없습니다: {path}. 설정 [git].author_email을 지정하세요."
WEEK_OUT_OF_RANGE = "이 주의 커밋은 모을 수 없습니다: {week}."
REPO_WARNING = "커밋을 모으지 못했습니다: {project} ({message})"

_FIELD_SEPARATOR = "\x1f"
_FIELD_COUNT = 3
_SHORT_HASH_LENGTH = 7
_LOG_FORMAT = "--format=%H%x1f%aI%x1f%s"


@dataclass(frozen=True)
class RepoCommits:
    project: str
    path: Path
    commits: tuple[CommitLine, ...]
    error: str = ""  # 이 저장소에서 실패했으면 한국어 한 줄, 아니면 ''


def _author_email(git: GitConfig, repo: GitRepo, run: RunTool) -> str:
    """설정의 이메일, 없으면 저장소의 git config user.email 첫 줄. 알 수 없으면 ''."""
    if git.author_email:
        return git.author_email
    try:
        output = run(
            "git",
            ["-C", str(repo.path), "config", "user.email"],
            missing_hint=GIT_MISSING_HINT,
            label="git config",
        )
    except ExternalServiceError:
        return ""
    lines = output.strip().splitlines()
    return lines[0].strip() if lines else ""


def _parse_commits(output: str, week: Week, tz: tzinfo) -> tuple[CommitLine, ...]:
    commits: list[CommitLine] = []
    for line in output.splitlines():
        fields = line.split(_FIELD_SEPARATOR)
        if len(fields) != _FIELD_COUNT:
            continue
        full_hash, author_date, subject = fields
        day = datetime.fromisoformat(author_date).astimezone(tz).date()
        # --since/--until은 커미터 날짜 기준이라 작성 날짜가 범위 밖인 커밋이 섞인다.
        if not week.contains(day):
            continue
        commits.append(CommitLine(day.isoformat(), full_hash[:_SHORT_HASH_LENGTH], subject.strip()))
    return tuple(commits)


def _collect_one(
    git: GitConfig, repo: GitRepo, since: str, until: str, week: Week, tz: tzinfo, run: RunTool
) -> RepoCommits:
    if not repo.path.is_dir():
        return RepoCommits(repo.project, repo.path, (), REPO_MISSING.format(path=repo.path))
    email = _author_email(git, repo, run)
    if not email:
        return RepoCommits(repo.project, repo.path, (), EMAIL_UNKNOWN.format(path=repo.path))
    args = [
        "-C",
        str(repo.path),
        "-c",
        "i18n.logOutputEncoding=UTF-8",
        "log",
        "--all",
        "--no-merges",
        "--reverse",
        "--fixed-strings",
        "--regexp-ignore-case",
        f"--author={email}",
        f"--since={since}",
        f"--until={until}",
        _LOG_FORMAT,
    ]
    try:
        output = run("git", args, missing_hint=GIT_MISSING_HINT, label="git log")
    except ExternalServiceError as error:
        return RepoCommits(repo.project, repo.path, (), str(error))
    return RepoCommits(repo.project, repo.path, _parse_commits(output, week, tz))


def _midnight(day: date, tz: tzinfo) -> str:
    return datetime.combine(day, time(), tzinfo=tz).isoformat()


def collect_commits(
    git: GitConfig, week: Week, *, tz: tzinfo, run: RunTool = run_tool
) -> tuple[RepoCommits, ...]:
    """설정의 저장소마다 week 동안의 본인 커밋을 모은다. 저장소 하나가 실패해도 계속한다."""
    try:
        since = _midnight(week.start, tz)
        until = _midnight(week.end + timedelta(days=1), tz)
    except (OverflowError, ValueError):
        message = WEEK_OUT_OF_RANGE.format(week=week.label)
        return tuple(RepoCommits(repo.project, repo.path, (), message) for repo in git.repos)
    return tuple(_collect_one(git, repo, since, until, week, tz, run) for repo in git.repos)


def to_commit_groups(results: Sequence[RepoCommits]) -> tuple[CommitGroup, ...]:
    """커밋이 있는 저장소만 설정 순서대로 CommitGroup으로 바꾼다."""
    return tuple(
        CommitGroup(result.project, result.path.name, result.commits)
        for result in results
        if result.commits
    )


def report_commits(
    cfg: Config, week: Week, *, tz: tzinfo, run: RunTool = run_tool
) -> tuple[tuple[CommitGroup, ...], tuple[str, ...]]:
    """보고서 부록용 (커밋 묶음, 경고 문구들). 꺼져 있거나 저장소가 없으면 ((), ())."""
    if not cfg.report.include_commits or not cfg.git.repos:
        return (), ()
    results = collect_commits(cfg.git, week, tz=tz, run=run)
    warnings = tuple(
        REPO_WARNING.format(project=result.project, message=result.error)
        for result in results
        if result.error
    )
    return to_commit_groups(results), warnings
