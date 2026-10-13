"""lb project add|list|edit|archive|unarchive."""

from typing import Annotated

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand, LogbookGroup
from logbook.core.errors import InvalidInputError

project_app = typer.Typer(
    cls=LogbookGroup, help="프로젝트를 추가·조회·수정·보관합니다.", no_args_is_help=True
)

EDIT_NOTHING = '바꿀 항목을 하나 이상 지정하세요. 예: lb project edit payment --color "#22c55e"'

# (값 옵션, 비우기 옵션, update_project 필드). 충돌 검사와 비우기 매핑이 이 표 하나를 쓴다.
_CLEARABLE = (
    ("--color", "--no-color", "color"),
    ("--description", "--no-description", "description"),
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


@project_app.command("edit", cls=LogbookCommand)
def edit(
    slug: Annotated[str, typer.Argument(metavar="SLUG", help="수정할 프로젝트 slug")],
    name: Annotated[str | None, typer.Option("--name", help="표시 이름")] = None,
    color: Annotated[str | None, typer.Option("--color", help="색상 (예: '#4f46e5')")] = None,
    description: Annotated[str | None, typer.Option("--description", help="설명")] = None,
    no_color: Annotated[bool, typer.Option("--no-color", help="색상을 비웁니다.")] = False,
    no_description: Annotated[
        bool, typer.Option("--no-description", help="설명을 비웁니다.")
    ] = False,
) -> None:
    """프로젝트의 이름·색상·설명을 고칩니다. slug는 바꿀 수 없습니다."""
    from rich.text import Text

    values = {"color": color, "description": description}
    clears = {"color": no_color, "description": no_description}
    # DB와 설정 없이 끝낼 수 있는 검사를 먼저 한다(실패하면 SQLAlchemy를 로드하지 않는다).
    for value_flag, clear_flag, field in _CLEARABLE:
        if values[field] is not None and clears[field]:
            raise InvalidInputError(runtime.CONFLICT_MESSAGE.format(value_flag, clear_flag))
    if name is None and all(v is None for v in values.values()) and not any(clears.values()):
        raise InvalidInputError(EDIT_NOTHING)

    fields: dict[str, str | None] = {} if name is None else {"name": name}
    for _, _, field in _CLEARABLE:
        if values[field] is not None:
            fields[field] = values[field]
        elif clears[field]:
            fields[field] = None

    from logbook.core import services

    cfg = runtime.settings()
    with runtime.session(cfg) as s:
        project = services.update_project(s, slug, **fields)

    color_parts = (" ", Text(project.color)) if project.color else ()
    console.print_line(
        render.ok_mark(),
        " 프로젝트 수정: ",
        Text(project.slug),
        " (",
        Text(project.name),
        ")",
        *color_parts,
    )


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


@project_app.command("unarchive", cls=LogbookCommand)
def unarchive(
    slug: Annotated[str, typer.Argument(metavar="SLUG", help="보관을 해제할 프로젝트 slug")],
) -> None:
    """보관한 프로젝트를 다시 사용 중으로 되돌립니다."""
    from rich.text import Text

    from logbook.core import services

    cfg = runtime.settings()
    with runtime.session(cfg) as s:
        was_archived = services.get_project(s, slug).archived
        project = services.unarchive_project(s, slug)

    if was_archived:
        console.print_line(render.ok_mark(), " 프로젝트 보관 해제: ", Text(project.slug))
    else:
        console.print_line(
            f"{render.info_mark()} 보관되지 않은 프로젝트입니다: ", Text(project.slug)
        )


def register(app: typer.Typer) -> None:
    app.add_typer(project_app, name="project")
