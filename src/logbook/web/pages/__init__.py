"""화면(HTML) 라우터 묶음과 템플릿 도우미."""

from fastapi import APIRouter

from logbook.web.pages import dashboard

router = APIRouter()
router.include_router(dashboard.router)
