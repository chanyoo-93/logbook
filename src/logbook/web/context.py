"""웹 요청이 공유하는 실행 맥락: 설정, DB 엔진, 설정 파일 위치, 시계."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from starlette.requests import Request

from logbook.core.config import Config
from logbook.core.db import session_scope
from logbook.web.config_watch import ConfigSnapshot, ConfigWatcher

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
    config_notice: str = ""  # 화면 위 설정 알림. 비면 없음
    config_notice_error: bool = False

    def with_snapshot(self, snapshot: ConfigSnapshot) -> WebContext:
        """cfg와 알림을 스냅숏 값으로 바꾼 사본."""
        return replace(
            self,
            cfg=snapshot.cfg,
            config_notice=snapshot.notice,
            config_notice_error=snapshot.notice_error,
        )

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
    """요청의 맥락. watcher가 없으면 app.state.ctx를 그대로 돌려준다.

    watcher가 있으면 그 요청의 설정 스냅숏으로 만든 맥락을 request.state에 두고 돌려준다.
    그래서 한 요청 안에서는 핸들러와 템플릿이 같은 설정을 본다.
    """
    cached: WebContext | None = getattr(request.state, "web_context", None)
    if cached is not None:
        return cached
    ctx: WebContext = request.app.state.ctx
    watcher: ConfigWatcher | None = getattr(request.app.state, "watcher", None)
    if watcher is None:
        return ctx
    request.state.web_context = ctx.with_snapshot(watcher.current())
    result: WebContext = request.state.web_context
    return result


Ctx = Annotated[WebContext, Depends(get_context)]
"""라우트 핸들러의 `ctx: Ctx` 매개변수 별칭. API와 화면이 함께 쓴다."""
TASK_LABEL = "태스크"
"""태스크 ID 입력 오류 문구에 쓰는 이름(parse_id·check_id의 what)."""
