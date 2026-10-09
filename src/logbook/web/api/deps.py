"""API 모듈이 함께 쓰는 의존성 별칭과 문구."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from logbook.web.context import WebContext, get_context

Ctx = Annotated[WebContext, Depends(get_context)]
TASK_LABEL = "태스크"
