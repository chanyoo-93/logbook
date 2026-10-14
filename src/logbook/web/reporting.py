"""보고서 데이터와 Markdown 만들기 (JSON API와 보고서 화면이 함께 쓴다)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from logbook.core import gitcollect, services
from logbook.core.report import ReportData, render_markdown, user_template_path

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from logbook.core.weeks import Week
    from logbook.web.context import WebContext

DOWNLOAD_NAME = "weekly-report-{week}.md"


def report_data(s: Session, ctx: WebContext, week: Week, now: datetime) -> ReportData:
    """설정(제목 형식·작성자·카테고리 이름)을 반영한 주간보고서 데이터."""
    return services.weekly_report(
        s,
        week,
        tz=now.tzinfo or UTC,
        title_format=ctx.cfg.report.title_format,
        author=ctx.cfg.report.author,
        category_labels=ctx.cfg.categories,
    )


def report_with_commits(
    ctx: WebContext, data: ReportData, week: Week, now: datetime
) -> tuple[ReportData, tuple[str, ...]]:
    """커밋 부록을 채운 데이터와 수집 경고. git을 실행하므로 DB 세션을 닫은 뒤에 부른다."""
    commits, warnings = gitcollect.report_commits(ctx.cfg, week, tz=now.tzinfo or UTC)
    return replace(data, commits=commits), warnings


def report_markdown(ctx: WebContext, data: ReportData) -> str:
    """사용자 템플릿이 있으면 그것으로 렌더링한다. 세션을 닫은 뒤에 부른다."""
    return render_markdown(data, template_path=user_template_path(ctx.config_file))


def download_name(week: Week) -> str:
    """내려받기 파일 이름. ASCII라서 Content-Disposition에 filename*이 필요 없다."""
    return DOWNLOAD_NAME.format(week=week.label)
