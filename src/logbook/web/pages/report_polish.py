"""보고서 문장 다듬기: POST /report/polish.

커밋 부록은 외부로 보내지 않으므로 수집하지 않는다. 외부 요청은 DB 세션을 닫은 뒤에 한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse

from logbook.core.polish import PROVIDER_LABELS, choose_provider, polish_report
from logbook.core.weeks import parse_week
from logbook.web.context import Ctx
from logbook.web.pages.forms import FormText
from logbook.web.pages.templating import render
from logbook.web.reporting import report_data

router = APIRouter()

POLISH_TEMPLATE = "partials/report_polish.html"
DEFAULT_WEEK = "this"


@dataclass(frozen=True)
class PolishView:
    label: str  # 'Claude' | 'ChatGPT'
    model: str
    summary: str


@router.post("/report/polish", response_class=HTMLResponse)
def polish_page(
    request: Request, ctx: Ctx, week: FormText = "", provider: FormText = ""
) -> HTMLResponse:
    now = ctx.now()
    the_week = parse_week(
        week.strip() or DEFAULT_WEEK, today=ctx.today(), week_start=ctx.cfg.week_start
    )
    chosen = choose_provider(ctx.cfg.llm, provider.strip() or None)
    with ctx.session() as s:
        data = report_data(s, ctx, the_week, now)
    result = polish_report(data, ctx.cfg.llm, chosen)
    view = PolishView(PROVIDER_LABELS[result.provider], result.model, result.summary)
    return render(request, POLISH_TEMPLATE, {"polish": view})
