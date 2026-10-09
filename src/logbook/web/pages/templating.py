"""화면 렌더링 도우미: Jinja2 환경, render(), render_error().

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
from logbook.core.errors import LogbookError
from logbook.core.weeks import week_heading, week_of
from logbook.web.context import get_context
from logbook.web.errors import classify


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


def render_error(
    request: Request,
    error: LogbookError,
    name: str,
    context: Mapping[str, Any],
    *,
    headers: Mapping[str, str] | None = None,
) -> HTMLResponse:
    """핸들러가 처리한 오류를 화면 조각으로 다시 그린다. 상태 코드는 classify가 정한다."""
    return render(request, name, context, status_code=classify(error).status, headers=headers)
