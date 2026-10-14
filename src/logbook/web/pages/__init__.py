"""화면(HTML) 라우터 묶음과 템플릿 도우미."""

from fastapi import APIRouter

from logbook.web.pages import (
    dashboard,
    fonts,
    logs,
    report,
    report_polish,
    settings,
    tasks,
    timer,
)

router = APIRouter()
router.include_router(dashboard.router)
router.include_router(fonts.router)
router.include_router(logs.router)
router.include_router(timer.router)
router.include_router(tasks.router)
router.include_router(report.router)
router.include_router(report_polish.router)
router.include_router(settings.router)
