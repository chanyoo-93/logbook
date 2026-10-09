"""FastAPI 앱 조립. 정적 파일과 화면 라우터는 Task 5-6에서 더한다."""

from fastapi import FastAPI

from logbook.web import api
from logbook.web.context import WebContext
from logbook.web.errors import install_error_handlers
from logbook.web.security import LocalOnlyMiddleware


def create_app(ctx: WebContext) -> FastAPI:
    # Swagger UI 같은 문서 화면은 CDN 스크립트를 불러 CSP와 어긋나므로 끈다.
    app = FastAPI(title="logbook", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.ctx = ctx
    install_error_handlers(app)
    app.include_router(api.router, prefix="/api")
    app.add_middleware(LocalOnlyMiddleware)
    return app
