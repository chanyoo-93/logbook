"""lb init: 설정 파일과 데이터베이스를 만들고 기본 프로젝트를 준비한다(여러 번 실행해도 같다)."""

from typing import TYPE_CHECKING

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand

if TYPE_CHECKING:
    from pathlib import Path

    from logbook.core.config import Config
    from logbook.core.db import InitResult
    from logbook.core.models import Project


def _config_line(path: "Path", created: bool) -> "tuple[console.LinePart, ...]":
    from rich.text import Text

    if created:
        return (render.ok_mark(), " 설정 파일 생성: ", Text(str(path)))
    return (f"{render.info_mark()} 설정 파일 유지 (이미 있음): ", Text(str(path)))


def _database_line(path: "Path", result: "InitResult") -> "tuple[console.LinePart, ...]":
    from rich.text import Text

    shown = Text(str(path))
    if result.previous_version is None:
        return (render.ok_mark(), " 데이터베이스 생성: ", shown, f" (스키마 v{result.version})")
    if result.previous_version == result.version:
        return (
            render.ok_mark(),
            " 데이터베이스 확인: ",
            shown,
            f" (스키마 v{result.version}, 최신)",
        )
    return (
        render.ok_mark(),
        " 데이터베이스 업그레이드: ",
        shown,
        f" (v{result.previous_version} {render.arrow()} v{result.version})",
    )


def _prepare_projects(cfg: "Config") -> "tuple[Project, str | None]":
    """common을 준비하고 기본 프로젝트를 점검한다. (common 프로젝트, 경고 문구 또는 None)."""
    from logbook.core import services
    from logbook.core.errors import NotFoundError

    slug = cfg.default_project
    warning: str | None = None
    with runtime.session(cfg) as s:
        common = services.ensure_common_project(s)
        # NotFoundError는 세션 안에서 잡는다. 밖으로 내보내면 common 생성이 롤백된다.
        try:
            default = services.get_project(s, slug)
        except NotFoundError:
            # 쓸 수 없는 slug로 만들라고 안내하지 않도록 자리표시자를 쓴다(core 문구와 같은 규칙).
            hint = slug if services.is_valid_slug(slug) else "<slug>"
            warning = (
                f"설정의 default_project가 가리키는 프로젝트가 없습니다: '{slug}'. "
                f"'lb project add {hint} <이름>'으로 만들거나 "
                "설정 파일의 default_project를 바꾸세요."
            )
        else:
            if default.archived:
                warning = (
                    f"설정의 default_project가 보관된 프로젝트입니다: '{slug}'. "
                    "설정 파일의 default_project를 바꾸세요."
                )
    return common, warning


def init() -> None:
    """설정 파일과 데이터베이스를 만들고 기본 프로젝트(common)를 준비합니다."""
    from rich.text import Text

    from logbook.core import db
    from logbook.core.config import config_path, load_config, write_default_config

    path = config_path()
    try:
        write_default_config(path)
        config_created = True
    except FileExistsError:
        config_created = False
    cfg = load_config(path)
    result = db.initialize_database(cfg.db_path)
    common, warning = _prepare_projects(cfg)

    # 모든 단계가 성공한 뒤에 출력한다(실패하면 stdout이 비어 있다).
    console.print_line(*_config_line(path, config_created))
    console.print_line(*_database_line(cfg.db_path, result))
    console.print_line(
        render.ok_mark(),
        " 기본 프로젝트 준비: ",
        Text(common.slug),
        " (",
        Text(common.name),
        ")",
    )
    if warning is not None:
        console.print_warning(warning)


def register(app: typer.Typer) -> None:
    app.command("init", cls=LogbookCommand)(init)
