"""/api/stats: 주간 공수 집계."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Query
from starlette.responses import JSONResponse

from logbook.core import services
from logbook.core.weeks import parse_week
from logbook.web.api.envelope import ok
from logbook.web.api.schemas import optional_text
from logbook.web.api.serialize import stats_json
from logbook.web.context import Ctx

router = APIRouter()

DEFAULT_BY = "project"


@router.get("/stats")
def get_stats(
    ctx: Ctx,
    week: Annotated[str | None, Query()] = None,
    by: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    the_week = parse_week(
        optional_text(week) or "this", today=ctx.today(), week_start=ctx.cfg.week_start
    )
    grouping = optional_text(by) or DEFAULT_BY
    with ctx.session() as s:
        # 잘못된 값은 stats_by가 한국어 문구로 거부한다.
        result = services.stats_by(
            s, the_week, cast("services.StatsBy", grouping), category_labels=ctx.cfg.categories
        )
        data = stats_json(result)
    return ok(data)
