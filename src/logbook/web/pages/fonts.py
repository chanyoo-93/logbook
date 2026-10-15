"""GET /fonts.css: 설정 글꼴 스타일시트. /static/ 밖이라 no-store로 나가 새로 고침만으로 바뀐다."""

from fastapi import APIRouter
from starlette.responses import Response

from logbook.web.context import Ctx
from logbook.web.fonts import fonts_css

router = APIRouter()


@router.get("/fonts.css")
def fonts_stylesheet(ctx: Ctx) -> Response:
    return Response(fonts_css(ctx.cfg.web), media_type="text/css; charset=utf-8")
