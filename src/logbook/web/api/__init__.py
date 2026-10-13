"""JSON API 라우터 묶음(`/api`)."""

from fastapi import APIRouter

from logbook.web.api import logs, report, stats, tasks, timer

router = APIRouter()
router.include_router(logs.router)
router.include_router(stats.router)
router.include_router(tasks.router)
router.include_router(report.router)
router.include_router(timer.router)
