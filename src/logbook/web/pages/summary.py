"""대시보드 요약 숫자와 차트 데이터. 차트 값은 모두 분이다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from logbook.core import services
from logbook.core.duration import format_duration
from logbook.core.weeks import Week, day_label, week_heading

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from logbook.web.context import WebContext

# 색을 정하지 않은 프로젝트와 카테고리에 순서대로 돌려 쓰는 색. 모두 흰 배경에서 구분된다.
CHART_PALETTE = (
    "#2f6fde",
    "#e8590c",
    "#2b8a3e",
    "#c2255c",
    "#7048e8",
    "#0b7285",
    "#e67700",
    "#5c940d",
    "#a61e4d",
    "#495057",
)


@dataclass(frozen=True)
class SummaryView:
    heading: str  # week_heading
    total: str  # format_duration, 0이면 '0m'
    count: int
    done_count: int
    chart: dict[str, object]
    has_logs: bool


def _palette_color(position: int) -> str:
    return CHART_PALETTE[position % len(CHART_PALETTE)]


def project_colors(slugs: Sequence[str], explicit: Mapping[str, str | None]) -> dict[str, str]:
    """설정한 색(projects.color)이 있으면 그 색, 없으면 slugs 순서대로 CHART_PALETTE를 돌려 쓴다."""
    return {slug: explicit.get(slug) or _palette_color(i) for i, slug in enumerate(slugs)}


def category_colors(present: Sequence[str], configured: Sequence[str]) -> dict[str, str]:
    """카테고리 색. 설정 순서 위치로 팔레트에서 고르므로 주마다 같은 카테고리는 같은 색이다.

    설정에 없는 key는 설정 개수 뒤의 위치를 이름 순으로 받는다.
    """
    position = {key: i for i, key in enumerate(configured)}
    unknown = sorted(key for key in present if key not in position)
    position.update({key: len(configured) + i for i, key in enumerate(unknown)})
    return {key: _palette_color(position[key]) for key in present}


def build_summary(s: Session, ctx: WebContext, week: Week, now: datetime) -> SummaryView:
    """week의 요약. 세션 안에서 불러 모든 값을 일반 값으로 바꿔 돌려준다."""
    cfg = ctx.cfg
    daily = services.daily_project_minutes(s, week)
    by_project = services.stats_by(s, week, "project")
    by_category = services.stats_by(s, week, "category", category_labels=cfg.categories)
    done_count = services.count_done_tasks(s, week, tz=now.tzinfo or UTC)
    explicit = {p.slug: p.color for p in services.list_projects(s, include_archived=True)}

    # 막대와 도넛이 같은 프로젝트 순서·색을 쓴다(둘 다 합계 내림차순, 같으면 slug 순).
    colors = project_colors(daily.projects, explicit)
    project_minutes = {row.key: row.minutes for row in by_project.rows}
    category_color = category_colors([row.key for row in by_category.rows], tuple(cfg.categories))
    chart: dict[str, object] = {
        "daily": {
            "labels": [day_label(day) for day in daily.days],
            "target": cfg.daily_target_minutes,
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
    )
