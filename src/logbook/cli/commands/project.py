"""lb project add|list|archive."""

from typing import Annotated

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand, LogbookGroup

project_app = typer.Typer(
    cls=LogbookGroup, help="프로젝트를 추가·조회·보관합니다.", no_args_is_help=True
)


@project_app.command("add", cls=LogbookCommand)
def add(
    slug: Annotated[
        str, typer.Argument(metavar="SLUG", help="영문 소문자 짧은 이름 (예: payment)")
    ],
    name: Annotated[
        str, typer.Argument(metavar="이름", help="표시 이름. 공백이 있으면 따옴표로 감쌉니다.")
    ],
    color: Annotated[str | None, typer.Option("--color", help="색상 (예: '#4f46e5')")] = None,
) -> None:
    """프로젝트를 추가합니다."""
    from rich.text import Text

    from logbook.core import services

    cfg = runtime.settings()
    with runtime.session(cfg) as s:
        project = services.create_project(s, slug, name, color=color)

    color_parts = (" ", Text(project.color)) if project.color else ()
    console.print_line(
        render.ok_mark(),
        " 프로젝트 추가: ",
        Text(project.slug),
        " (",
        Text(project.name),
        ")",
        *color_parts,
    )


@project_app.command("list", cls=LogbookCommand)
def list_(
    include_all: Annotated[
        bool, typer.Option("--all", "-a", help="보관된 프로젝트도 보여 줍니다.")
    ] = False,
) -> None:
    """프로젝트 목록을 slug 순으로 보여 줍니다."""
    from logbook.core import services

    cfg = runtime.settings()
    with runtime.session(cfg) as s:
        projects = services.list_projects(s, include_archived=include_all)

    # 열이 적은 표라 좁은 화면 대체 출력 없이 이름 열만 접는다.
    console.print_table(render.project_table(projects, show_status=include_all))


@project_app.command("archive", cls=LogbookCommand)
def archive(
    slug: Annotated[str, typer.Argument(metavar="SLUG", help="보관할 프로젝트 slug")],
) -> None:
    """프로젝트를 보관합니다. 과거 기록은 집계에 계속 포함됩니다."""
    from rich.text import Text

    from logbook.core import services

    cfg = runtime.settings()
    with runtime.session(cfg) as s:
        already_archived = services.get_project(s, slug).archived
        project = services.archive_project(s, slug)

    if already_archived:
        console.print_line(f"{render.info_mark()} 이미 보관된 프로젝트입니다: ", Text(project.slug))
    else:
        console.print_line(
            render.ok_mark(),
            " 프로젝트 보관: ",
            Text(project.slug),
            " (과거 기록은 집계에 계속 포함됩니다)",
        )
    if project.slug == cfg.default_project:
        console.print_warning(
            f"보관한 프로젝트가 설정의 default_project입니다: '{project.slug}'. "
            "-p 없이 기록하려면 설정 파일의 default_project를 바꾸세요."
        )


def register(app: typer.Typer) -> None:
    app.add_typer(project_app, name="project")
