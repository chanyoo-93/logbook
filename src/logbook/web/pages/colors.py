"""GET /colors.css: 카테고리 꼬리표 색 스타일시트. no-store라 저장 직후 반영된다."""

from fastapi import APIRouter
from starlette.responses import Response

from logbook.core import services
from logbook.web.colors import colors_css
from logbook.web.context import Ctx

router = APIRouter()


@router.get("/colors.css")
def colors_stylesheet(ctx: Ctx) -> Response:
    with ctx.session() as s:
        stored = services.category_colors(s)
    return Response(
        colors_css(tuple(ctx.cfg.categories), stored), media_type="text/css; charset=utf-8"
    )
