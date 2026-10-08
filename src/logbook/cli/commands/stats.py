"""lb stats: 주간 공수 집계(프로젝트 x 카테고리 행렬, 또는 --by 묶음별 합계)."""

from typing import TYPE_CHECKING, Annotated, cast

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand
from logbook.core.errors import InvalidInputError

if TYPE_CHECKING:
    from logbook.core.services import StatsBy

# core.services.StatsBy와 같은 값. 모듈 상단에서 services를 import하지 않으려고 따로 둔다.
STATS_BY_CHOICES: tuple[str, ...] = ("project", "category", "day")
NO_RECORDS_MESSAGE = "이 주에는 기록이 없습니다."


def stats(
    week: runtime.WeekOpt = None,
    by: Annotated[
        str | None, typer.Option("--by", help="묶음 기준: project, category, day")
    ] = None,
) -> None:
    """주간 공수를 집계합니다. --by가 없으면 프로젝트 x 카테고리 표를 보여 줍니다."""
    # DB를 열기 전에 막는다(빈 문자열도 여기서 걸린다). 문구는 core.services.stats_by와 같다.
    if by is not None and by not in STATS_BY_CHOICES:
        raise InvalidInputError(
            f"집계 기준이 올바르지 않습니다: '{by}'. "
            f"{', '.join(STATS_BY_CHOICES)} 중 하나를 쓰세요."
        )

    from logbook.core.weeks import parse_week, week_heading

    cfg = runtime.settings()
    the_week = parse_week(
        week if week is not None else "this", today=runtime.today(), week_start=cfg.week_start
    )
    heading = week_heading(the_week)

    # services는 SQLAlchemy를 로드하므로 검증이 끝난 뒤에 import한다.
    from logbook.core import services

    if by is None:
        with runtime.session(cfg) as s:
            matrix = services.stats_matrix(s, the_week, category_order=tuple(cfg.categories))
        if _print_summary(heading, matrix.total_minutes, matrix.count):
            console.print_table(
                render.matrix_table(matrix, cfg.categories),
                lambda: render.matrix_lines(matrix, cfg.categories),
            )
        return

    with runtime.session(cfg) as s:
        # STATS_BY_CHOICES로 검증했으므로 StatsBy 값이다.
        grouped = services.stats_by(
            s, the_week, cast("StatsBy", by), category_labels=cfg.categories
        )
    if _print_summary(heading, grouped.total_minutes, grouped.count):
        # 열이 적어 좁은 화면 대체 출력 없이 이름 열만 접는다.
        console.print_table(render.by_table(grouped))


def _print_summary(heading: str, total_minutes: int, count: int) -> bool:
    """머리줄을 출력하고, 기록이 없으면 안내를 덧붙인다. 표를 이어서 출력할지 돌려준다."""
    from logbook.core.duration import format_duration

    console.print_line(f"{heading}   총 {format_duration(total_minutes)} / 기록 {count}건")
    if count == 0:
        console.print_line(NO_RECORDS_MESSAGE)
        return False
    return True


def register(app: typer.Typer) -> None:
    app.command("stats", cls=LogbookCommand)(stats)
