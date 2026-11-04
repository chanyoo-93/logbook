"""대시보드 요약 숫자, 요일별 차트 데이터(값은 분), 프로젝트·카테고리 비율 막대."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict

from logbook.core import services
from logbook.core.duration import format_duration
from logbook.core.weeks import Week, day_label, week_heading
from logbook.web.pages.views import category_color_map, progress_percent, project_color

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from logbook.web.context import WebContext


class DailyDataset(TypedDict):
    """막대 차트의 프로젝트 하나(요일별 분)."""

    label: str
    color: str
    data: list[int]


class DailyChart(TypedDict):
    labels: list[str]
    target: int
    totals: list[int]
    datasets: list[DailyDataset]


class ChartData(TypedDict):
    """대시보드 차트 데이터. data-chart 속성에 JSON으로 들어간다."""

    daily: DailyChart


@dataclass(frozen=True)
class ShareRow:
    """비율 막대의 조각 하나와 그 글줄. x·width는 SVG viewBox(0~100) 좌표."""

    label: str
    color: str  # '#rrggbb'
    time: str  # format_duration
    percent: str  # '86%', 1% 미만은 '<1%'
    x: str  # '85.71'
    width: str  # '14.29'


@dataclass(frozen=True)
class ShareGroup:
    title: str  # '프로젝트별'
    rows: tuple[ShareRow, ...]


SCALE = 10_000  # 막대 폭 100을 1/100 단위 정수로 다룬다
MIN_PART = 100  # 가장 좁은 조각 폭(막대의 1%, 1280px에서 약 3px)


def _number(value: float) -> str:
    """SVG 좌표 표기: 소수 둘째 자리, 끝의 0은 뺀다('0', '85.71', '14.3')."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _percent(minutes: int, total: int) -> str:
    percent = round(minutes * 100 / total)
    return f"{percent}%" if percent >= 1 else "<1%"


def _part_widths(minutes: Sequence[int]) -> list[int]:
    """조각 폭(1/100 단위, 합 10000).

    경계는 누적 분의 비율로 구한다(조각마다 반올림하면 오차가 쌓여 마지막 폭이 음수가 될 수 있다).
    MIN_PART보다 좁은 조각은 테두리 틈에 덮여 보이지 않으므로 MIN_PART로 넓히고
    늘어난 만큼 가장 넓은 조각에서 뺀다. 글줄의 비율은 실제 값 그대로다.
    """
    if not minutes:
        return []
    total = sum(minutes)
    edges: list[int] = []
    cumulative = 0
    for value in minutes:
        cumulative += value
        edges.append(round(cumulative * SCALE / total))
    widths = [edge - before for before, edge in zip([0, *edges], edges, strict=False)]
    deficit = sum(MIN_PART - width for width in widths if width < MIN_PART)
    widths = [max(width, MIN_PART) for width in widths]
    widest = widths.index(max(widths))
    widths[widest] -= deficit
    return widths


def share_rows(
    labels: Sequence[str], colors: Sequence[str], minutes: Sequence[int]
) -> tuple[ShareRow, ...]:
    """주어진 순서대로 비율 막대 조각을 만든다. 조각은 빈틈없이 이어지고 끝이 100이다."""
    total = sum(minutes)
    rows: list[ShareRow] = []
    start = 0
    for label, color, value, width in zip(
        labels, colors, minutes, _part_widths(minutes), strict=True
    ):
        time, percent = format_duration(value), _percent(value, total)
        rows.append(
            ShareRow(label, color, time, percent, _number(start / 100), _number(width / 100))
        )
        start += width
    return tuple(rows)


@dataclass(frozen=True)
class SummaryView:
    heading: str  # week_heading
    total: str  # format_duration, 0이면 '0m'
    count: int
    done_count: int
    chart: ChartData
    shares: tuple[ShareGroup, ...]  # 프로젝트별, 카테고리별(기록이 없으면 ())
    has_logs: bool
    today_total: str  # 오늘 공수(format_duration)
    today_target: str  # 하루 목표(format_duration)
    today_percent: int  # 목표 대비 0~100
    today_reached: bool  # 오늘 >= 목표


def build_summary(s: Session, ctx: WebContext, week: Week, now: datetime) -> SummaryView:
    """week의 요약. 세션 안에서 불러 모든 값을 일반 값으로 바꿔 돌려준다."""
    cfg = ctx.cfg
    today_minutes = services.day_total_minutes(s, now.date())
    daily = services.daily_project_minutes(s, week)
    by_project = services.stats_by(s, week, "project")
    by_category = services.stats_by(s, week, "category", category_labels=cfg.categories)
    done_count = services.count_done_tasks(s, week, tz=now.tzinfo or UTC)
    colors = {p.slug: project_color(p) for p in services.list_projects(s, include_archived=True)}

    # 요일별 막대와 비율 막대가 같은 프로젝트 순서(합계 내림차순, 같으면 slug 순)와
    # 색 점과 같은 색을 쓴다.
    project_minutes = {row.key: row.minutes for row in by_project.rows}
    category_color = category_color_map(
        tuple(cfg.categories),
        services.category_colors(s),
        [row.key for row in by_category.rows],
    )
    chart: ChartData = {
        "daily": {
            "labels": [day_label(day) for day in daily.days],
            "target": cfg.daily_target_minutes,
            "totals": [daily.day_totals[day] for day in daily.days],
            "datasets": [
                {
                    "label": slug,
                    "color": colors[slug],
                    "data": [daily.cells.get((day, slug), 0) for day in daily.days],
                }
                for slug in daily.projects
            ],
        },
    }
    shares = (
        ShareGroup(
            "프로젝트별",
            share_rows(
                daily.projects,
                [colors[slug] for slug in daily.projects],
                [project_minutes[slug] for slug in daily.projects],
            ),
        ),
        ShareGroup(
            "카테고리별",
            share_rows(
                [row.label for row in by_category.rows],
                [category_color[row.key] for row in by_category.rows],
                [row.minutes for row in by_category.rows],
            ),
        ),
    )
    has_logs = by_project.count > 0
    return SummaryView(
        heading=week_heading(week),
        total=format_duration(by_project.total_minutes),
        count=by_project.count,
        done_count=done_count,
        chart=chart,
        shares=shares if has_logs else (),
        has_logs=has_logs,
        today_total=format_duration(today_minutes),
        today_target=format_duration(cfg.daily_target_minutes),
        today_percent=progress_percent(today_minutes, cfg.daily_target_minutes),
        today_reached=today_minutes >= cfg.daily_target_minutes,
    )
