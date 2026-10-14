"""lb git-collect: 설정한 git 저장소에서 한 주의 본인 커밋을 모아 보여 준다(DB 저장 안 함)."""

from datetime import UTC
from typing import TYPE_CHECKING

import typer

from logbook.cli import console, runtime
from logbook.cli.group import LogbookCommand

if TYPE_CHECKING:
    from logbook.core.gitcollect import RepoCommits

NO_REPOS_MESSAGE = "설정된 저장소가 없습니다. 설정 파일에 [[git.repos]]를 추가하세요."
READ_FAILED_MESSAGE = "저장소 {count}곳에서 커밋을 읽지 못했습니다."
COMMIT_INDENT = "  "


def _print_repo(result: "RepoCommits") -> None:
    from rich.text import Text

    console.print_line(Text(f"{result.project} ({result.path.name}) {len(result.commits)}건"))
    for commit in result.commits:
        console.print_line(Text(f"{COMMIT_INDENT}{commit.date} {commit.hash} {commit.subject}"))


def git_collect(week: runtime.WeekOpt = None) -> None:
    """설정한 git 저장소에서 이번 주 본인 커밋을 모아 보여 줍니다. DB에는 저장하지 않습니다."""
    from logbook.core.errors import InvalidInputError, LogbookError
    from logbook.core.weeks import parse_week

    # DB·설정 없이 끝나는 검증을 먼저 한다.
    cfg = runtime.settings()
    the_week = parse_week(
        week if week is not None else "this", today=runtime.today(), week_start=cfg.week_start
    )
    if not cfg.git.repos:
        raise InvalidInputError(NO_REPOS_MESSAGE)

    from logbook.core import gitcollect

    results = gitcollect.collect_commits(cfg.git, the_week, tz=runtime.now().tzinfo or UTC)
    failed = 0
    for result in results:
        if result.error:
            console.print_warning(result.error)
            failed += 1
        else:
            _print_repo(result)
    if failed:
        raise LogbookError(READ_FAILED_MESSAGE.format(count=failed))


def register(app: typer.Typer) -> None:
    app.command("git-collect", cls=LogbookCommand)(git_collect)
