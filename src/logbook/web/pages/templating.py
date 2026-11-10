"""화면 렌더링 도우미: Jinja2 환경, render(), render_error().

환경은 항상 자동 이스케이프(`.html` 포함 모든 템플릿)와 StrictUndefined를 쓴다.
Starlette 기본 환경의 select_autoescape()는 `.j2`를 이스케이프하지 않으므로 쓰지 않는다.
템플릿에서 `|safe`와 `Markup()`을 쓰지 않는다.
"""

import re
from collections.abc import Mapping
from typing import Any

import jinja2
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from logbook.core.config import CATEGORY_KEY
from logbook.core.duration import format_duration
from logbook.core.errors import LogbookError
from logbook.core.weeks import week_heading, week_of
from logbook.web.assets import COLORS_CSS_URL, FONTS_CSS_URL, STATIC_CSS_URL, STYLESHEETS
from logbook.web.context import get_context
from logbook.web.errors import classify


def category_class(key: object) -> str:
    """카테고리 꼬리표 class. 형식이 틀린 키는 빈 문자열이라 기본 꼬리표가 된다."""
    if isinstance(key, str) and CATEGORY_KEY.fullmatch(key):
        return f"pill--cat-{key}"
    return ""


# 제목 속 주차·날짜(2026-W47, 2026-11-09, 11-16)와 붙은 괄호.
# 하이픈 뒤에서 줄이 바뀌지 않게 한 조각으로 둔다. 더 긴 숫자열(100-20-30 등) 한가운데는
# 날짜로 보지 않도록 앞뒤가 숫자·하이픈이 아니어야 한다(ASCII 숫자만)
_DATE_CHUNK = re.compile(
    r"\(?(?<![\d-])(?:\d{4}-W\d{2}|\d{4}-\d{2}-\d{2}|\d{2}-\d{2})(?![\d-])\)?", re.ASCII
)


def date_parts(text: str) -> list[tuple[str, bool]]:
    """글을 (조각, 날짜인가) 목록으로 나눈다. 조각을 이으면 원래 글이다(2026-11-09 결정 D5)."""
    parts: list[tuple[str, bool]] = []
    end = 0
    for match in _DATE_CHUNK.finditer(text):
        if match.start() > end:
            parts.append((text[end : match.start()], False))
        parts.append((match.group(), True))
        end = match.end()
    if end < len(text):
        parts.append((text[end:], False))
    return parts


def _environment() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("logbook.web", "templates"),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["STYLESHEETS"] = STYLESHEETS  # base.html이 링크 순서대로 반복한다
    env.globals["STATIC_CSS_URL"] = STATIC_CSS_URL
    env.globals["FONTS_CSS_URL"] = FONTS_CSS_URL
    env.globals["COLORS_CSS_URL"] = COLORS_CSS_URL
    env.filters["category_class"] = category_class  # 형식이 맞는 카테고리 키만 꼬리표 색 class
    env.filters["duration"] = format_duration  # 분 -> '1h 30m' (CLI와 같은 표기)
    env.filters["date_parts"] = date_parts  # 제목 속 날짜 조각(marks.html의 keep_dates가 쓴다)
    return env


TEMPLATES = Jinja2Templates(env=_environment())


def _shared_context(request: Request) -> dict[str, Any]:
    """모든 템플릿이 쓰는 값. 머리에 보여 줄 이번 주 표기와 설정 알림."""
    ctx = get_context(request)
    week = week_of(ctx.today(), ctx.cfg.week_start)
    return {
        "current_week": week_heading(week),
        "config_notice": ctx.config_notice,
        "config_notice_error": ctx.config_notice_error,
    }


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
