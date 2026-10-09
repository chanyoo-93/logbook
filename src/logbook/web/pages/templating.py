"""화면 렌더링 도우미: Jinja2 환경, render(), is_htmx().

환경은 항상 자동 이스케이프(`.html` 포함 모든 템플릿)와 StrictUndefined를 쓴다.
Starlette 기본 환경의 select_autoescape()는 `.j2`를 이스케이프하지 않으므로 쓰지 않는다.
템플릿에서 `|safe`와 `Markup()`을 쓰지 않는다.
"""

from collections.abc import Mapping
from typing import Any

import jinja2
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from logbook.core.duration import format_duration
from logbook.core.weeks import week_heading, week_of
from logbook.web.context import get_context

HTMX_REQUEST_HEADER = "HX-Request"
HTMX_HISTORY_RESTORE_HEADER = "HX-History-Restore-Request"


def _environment() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("logbook.web", "templates"),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["duration"] = format_duration  # 분 -> '1h 30m' (CLI와 같은 표기)
    return env


TEMPLATES = Jinja2Templates(env=_environment())


def is_htmx(request: Request) -> bool:
    """조각만 돌려줘야 하는 HTMX 요청인지.

    뒤로 가기 복원 요청(HX-History-Restore-Request)에는 전체 페이지를 줘야 하므로 제외한다.
    """
    headers = request.headers
    return bool(headers.get(HTMX_REQUEST_HEADER)) and HTMX_HISTORY_RESTORE_HEADER not in headers


def _shared_context(request: Request) -> dict[str, Any]:
    """모든 템플릿이 쓰는 값. 머리에 보여 줄 이번 주 표기."""
    ctx = get_context(request)
    week = week_of(ctx.today(), ctx.cfg.week_start)
    return {"current_week": week_heading(week)}


def render(
    request: Request,
    name: str,
    context: Mapping[str, Any],
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
) -> HTMLResponse:
    """템플릿을 HTML 응답으로 만든다. 세션을 닫은 뒤에 불러야 한다(뷰 데이터만 넘긴다)."""
    values = {**_shared_context(request), **context}
    return TEMPLATES.TemplateResponse(
        request, name, values, status_code=status_code, headers=headers
    )
