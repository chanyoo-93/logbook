"""웹 요청이 공유하는 실행 맥락: 설정, DB 엔진, 설정 파일 위치, 시계."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from starlette.requests import Request

from logbook.core.config import Config
from logbook.core.db import session_scope

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session


def _local_now() -> datetime:
    return datetime.now().astimezone()


@dataclass(frozen=True)
class WebContext:
    cfg: Config
    engine: Engine
    config_file: Path  # 사용자 보고서 템플릿 위치(user_template_path)를 정한다
    now: Callable[[], datetime] = _local_now

    def today(self) -> date:
        return self.now().date()

    @contextmanager
    def session(self) -> Iterator[Session]:
        """성공하면 커밋, 예외면 롤백하는 세션. 핸들러 본문에서 `with ctx.session() as s:`로 연다.

        yield 의존성이 아니라 핸들러 안에서 열어야 커밋 오류가 그 응답에 반영된다.
        """
        with session_scope(self.engine) as s:
            yield s


def get_context(request: Request) -> WebContext:
    ctx: WebContext = request.app.state.ctx
    return ctx


Ctx = Annotated[WebContext, Depends(get_context)]
"""라우트 핸들러의 `ctx: Ctx` 매개변수 별칭. API와 화면이 함께 쓴다."""
TASK_LABEL = "태스크"
"""태스크 ID 입력 오류 문구에 쓰는 이름(parse_id·check_id의 what)."""
