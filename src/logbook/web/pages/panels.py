"""기록이 바뀐 뒤 함께 다시 그리는 대시보드 영역(#summary, #recent)의 뷰 데이터."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from logbook.core import services
from logbook.core.duration import format_duration
from logbook.core.weeks import total_label, week_of
from logbook.web.pages.summary import build_summary
from logbook.web.pages.views import (
    RECENT_LIMIT,
    QuickFormValues,
    log_row,
    quick_form_options,
    record_text,
)

if TYPE_CHECKING:
    from datetime import date, datetime

    from sqlalchemy.orm import Session

    from logbook.core.models import WorkLog
    from logbook.web.context import WebContext

RESULT_MARK = "✔"


def result_line(s: Session, log: WorkLog, today: date) -> str:
    """기록 직후의 결과 줄: '✔ #128 payment/dev 2h — 메모 (오늘 누적 5h 30m)'.

    기록이 s에 flush된 뒤 부른다(누적에 이 기록이 들어가야 한다).
    """
    day_total = services.day_total_minutes(s, log.date)
    return (
        f"{RESULT_MARK} {record_text(log, with_date=False)} "
        f"({total_label(log.date, today)} 누적 {format_duration(day_total)})"
    )


def refreshed_panels(s: Session, ctx: WebContext, now: datetime) -> dict[str, Any]:
    """요약과 최근 기록의 템플릿 값. oob=True라 응답에 실으면 htmx가 해당 영역을 바꾼다."""
    week = week_of(now.date(), ctx.cfg.week_start)
    return {
        "summary": build_summary(s, ctx, week, now),
        "rows": [log_row(log) for log in services.recent_worklogs(s, limit=RECENT_LIMIT)],
        "oob": True,
    }


def quick_form_context(
    s: Session,
    ctx: WebContext,
    values: QuickFormValues,
    *,
    message: str = "",
    is_error: bool = False,
) -> dict[str, Any]:
    """빠른 기록 폼의 템플릿 값(선택지, 채워 둘 값, 결과 줄)."""
    return {
        "quick_options": quick_form_options(s, ctx.cfg),
        "quick_values": values,
        "quick_message": message,
        "quick_error": is_error,
        "default_project": ctx.cfg.default_project,
    }
