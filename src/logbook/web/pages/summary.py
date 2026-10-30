"""대시보드 요약 숫자와 차트 데이터. 차트 값은 모두 분이다."""

from __future__ import annotations

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


class DonutChart(TypedDict):
    """도넛 차트(프로젝트별, 카테고리별 분)."""

    labels: list[str]
    colors: list[str]
    data: list[int]


class ChartData(TypedDict):
    """대시보드 차트 데이터. data-chart 속성에 JSON으로 들어간다."""

    daily: DailyChart
    projects: DonutChart
    categories: DonutChart


@dataclass(frozen=True)
class SummaryView:
    heading: str  # week_heading
    total: str  # format_duration, 0이면 '0m'
    count: int
    done_count: int
    chart: ChartData
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

    # 막대와 도넛이 같은 프로젝트 순서(합계 내림차순, 같으면 slug 순)와 색 점과 같은 색을 쓴다.
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
        "projects": {
            "labels": list(daily.projects),
            "colors": [colors[slug] for slug in daily.projects],
            "data": [project_minutes[slug] for slug in daily.projects],
        },
        "categories": {
            "labels": [row.label for row in by_category.rows],
            "colors": [category_color[row.key] for row in by_category.rows],
            "data": [row.minutes for row in by_category.rows],
        },
    }
    return SummaryView(
        heading=week_heading(week),
        total=format_duration(by_project.total_minutes),
        count=by_project.count,
        done_count=done_count,
        chart=chart,
        has_logs=by_project.count > 0,
        today_total=format_duration(today_minutes),
        today_target=format_duration(cfg.daily_target_minutes),
        today_percent=progress_percent(today_minutes, cfg.daily_target_minutes),
        today_reached=today_minutes >= cfg.daily_target_minutes,
    )
