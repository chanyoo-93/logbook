"""화면(HTML) 라우터 묶음과 템플릿 도우미."""

from fastapi import APIRouter

from logbook.web.pages import dashboard, logs, timer

router = APIRouter()
router.include_router(dashboard.router)
router.include_router(logs.router)
router.include_router(timer.router)
