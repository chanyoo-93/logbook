"""JSON API 라우터 묶음(`/api`). tasks·report·timer는 Task 5-4에서 더해진다."""

from fastapi import APIRouter

from logbook.web.api import logs, stats

router = APIRouter()
router.include_router(logs.router)
router.include_router(stats.router)
