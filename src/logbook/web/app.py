"""FastAPI 앱 조립: 보안 미들웨어, 오류 처리, JSON API, 화면, 정적 파일."""

import mimetypes

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from logbook.web import api, pages
from logbook.web.context import WebContext
from logbook.web.errors import install_error_handlers
from logbook.web.security import LocalOnlyMiddleware

# Windows 레지스트리가 .js를 text/plain 등으로 바꿔 둔 PC에서는 X-Content-Type-Options: nosniff가
# 스크립트를 막으므로, 쓰는 확장자의 MIME을 직접 정한다.
_MIME_TYPES = (("text/javascript", ".js"), ("text/css", ".css"))


def create_app(ctx: WebContext) -> FastAPI:
    for mime_type, extension in _MIME_TYPES:
        mimetypes.add_type(mime_type, extension)
    # Swagger UI 같은 문서 화면은 CDN 스크립트를 불러 CSP와 어긋나므로 끈다.
    app = FastAPI(title="logbook", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.ctx = ctx
    install_error_handlers(app)
    app.include_router(api.router, prefix="/api")
    app.include_router(pages.router)
    # __file__ 기준 경로가 아니라 패키지 리소스로 찾는다(휠로 설치해도 같다).
    app.mount("/static", StaticFiles(packages=[("logbook.web", "static")]), name="static")
    app.add_middleware(LocalOnlyMiddleware)
    return app
