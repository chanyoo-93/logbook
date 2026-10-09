"""/api/report: 주간보고서(Markdown 또는 JSON)."""

from __future__ import annotations

import dataclasses
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette.responses import JSONResponse

from logbook.core import services
from logbook.core.duration import echo_input
from logbook.core.errors import InvalidInputError
from logbook.core.report import render_markdown, user_template_path
from logbook.core.weeks import parse_week
from logbook.web.api.envelope import ok
from logbook.web.api.schemas import optional_text
from logbook.web.context import WebContext, get_context

router = APIRouter()

FORMAT_MARKDOWN = "md"
FORMAT_JSON = "json"
FORMAT_INVALID = "보고서 형식이 올바르지 않습니다: '{value}'. md 또는 json을 쓰세요."


@router.get("/report")
def get_report(
    ctx: Annotated[WebContext, Depends(get_context)],
    week: Annotated[str | None, Query()] = None,
    report_format: Annotated[str | None, Query(alias="format")] = None,
) -> JSONResponse:
    requested = optional_text(report_format) or FORMAT_MARKDOWN
    fmt = requested.lower()
    if fmt not in (FORMAT_MARKDOWN, FORMAT_JSON):
        raise InvalidInputError(FORMAT_INVALID.format(value=echo_input(requested)))
    now = ctx.now()
    the_week = parse_week(
        optional_text(week) or "this", today=now.date(), week_start=ctx.cfg.week_start
    )
    with ctx.session() as s:
        data = services.weekly_report(
            s,
            the_week,
            tz=now.tzinfo or UTC,
            title_format=ctx.cfg.report.title_format,
            author=ctx.cfg.report.author,
            category_labels=ctx.cfg.categories,
        )
    # 렌더링(jinja2)은 세션을 닫은 뒤에 한다.
    if fmt == FORMAT_JSON:
        return ok(dataclasses.asdict(data))
    markdown = render_markdown(data, template_path=user_template_path(ctx.config_file))
    return ok({"week": the_week.label, "markdown": markdown})
