"""웹 테스트 fixture (fixture만 둔다. 그 밖의 도우미는 tests/web/helpers.py)."""

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine
from starlette.exceptions import HTTPException as StarletteHTTPException

from logbook.core import db, services
from logbook.core.config import Config
from logbook.core.errors import (
    DatabaseBusyError,
    DatabaseNotInitializedError,
    InvalidInputError,
    LogbookError,
    NotFoundError,
)
from logbook.web.app import create_app
from logbook.web.context import WebContext
from logbook.web.errors import ConflictError
from tests.helpers import Clock

LOCAL_BASE_URL = "http://127.0.0.1:8765"
FAST_BUSY_TIMEOUT = 0.05


class LockedApp(NamedTuple):
    """locked_client fixture의 값: 클라이언트, 엔진, DB 파일 경로(hold_lock에 넘긴다)."""

    client: TestClient
    engine: Engine
    db_path: Path


class IntBody(BaseModel):
    """시험용 요청 본문: strict 정수 하나."""

    model_config = ConfigDict(extra="forbid", strict=True)
    n: int


class ListBody(BaseModel):
    """시험용 요청 본문: 목록 안의 항목 검증 오류(loc에 정수 위치)."""

    model_config = ConfigDict(extra="forbid", strict=True)
    items: list[int]


# 시험용 경로가 던지는 오류
RAISED_ERRORS = {
    "invalid": InvalidInputError("입력이 잘못되었습니다: x"),
    "missing": NotFoundError("대상이 없습니다: 7"),
    "busy": DatabaseBusyError("DB가 사용 중입니다."),
    "uninitialized": DatabaseNotInitializedError("먼저 'lb init'을 실행하세요."),
    "plain": LogbookError("읽기 전용 DB입니다."),
    "markup": InvalidInputError("<b>굵게</b> & '따옴표'"),
    "conflict": ConflictError("다른 곳에서 기록이 바뀌었습니다: #7. 다시 시도하세요."),
}


@pytest.fixture
def clock() -> Clock:
    """WebContext의 '지금'(기본 FIXED_NOW). monkeypatch하지 않는다."""
    return Clock()


@pytest.fixture
def web_engine(tmp_home: Path) -> Iterator[Engine]:
    """tmp_home/logbook.db에 스키마와 common 프로젝트를 만든 엔진. 끝나면 dispose한다."""
    path = tmp_home / "logbook.db"
    db.initialize_database(path)
    engine = db.open_database(path)
    try:
        with db.session_scope(engine) as s:
            services.ensure_common_project(s)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def web_ctx(config: Config, web_engine: Engine, tmp_home: Path, clock: Clock) -> WebContext:
    return WebContext(
        cfg=config,
        engine=web_engine,
        config_file=tmp_home / "config.toml",
        now=lambda: clock.now,
    )


@pytest.fixture
def client(web_ctx: WebContext) -> Iterator[TestClient]:
    with TestClient(create_app(web_ctx), base_url=LOCAL_BASE_URL) as c:
        yield c


@pytest.fixture
def probe_calls() -> list[str]:
    """시험용 쓰기 경로가 불린 기록."""
    return []


@pytest.fixture
def probe_app(web_ctx: WebContext, probe_calls: list[str]) -> FastAPI:
    """create_app에 시험용 경로를 더한 앱. 같은 경로를 /api/ 아래와 화면 쪽에 둔다."""
    app = create_app(web_ctx)

    def raise_error(kind: str) -> None:
        raise RAISED_ERRORS[kind]

    def boom() -> None:
        raise RuntimeError("boom")

    def write() -> dict[str, bool]:
        probe_calls.append("write")
        return {"ok": True}

    def read() -> dict[str, bool]:
        return {"ok": True}

    def echo_int(body: IntBody) -> dict[str, int]:
        return {"n": body.n}

    def echo_list(body: ListBody) -> dict[str, list[int]]:
        return {"items": body.items}

    def teapot() -> None:
        raise StarletteHTTPException(418)

    def echo_query(limit: int) -> dict[str, int]:
        return {"limit": limit}

    for prefix in ("/api", ""):
        app.add_api_route(f"{prefix}/raise/{{kind}}", raise_error, methods=["GET"])
        app.add_api_route(f"{prefix}/boom", boom, methods=["GET"])
        app.add_api_route(f"{prefix}/x", read, methods=["GET"])
        app.add_api_route(f"{prefix}/x", write, methods=["POST"])
        app.add_api_route(f"{prefix}/get-only", read, methods=["GET"])
        app.add_api_route(f"{prefix}/echo", echo_int, methods=["POST"])
        app.add_api_route(f"{prefix}/list", echo_list, methods=["POST"])
        app.add_api_route(f"{prefix}/teapot", teapot, methods=["GET"])
        app.add_api_route(f"{prefix}/query", echo_query, methods=["GET"])
    return app


@pytest.fixture
def probe_client(probe_app: FastAPI) -> Iterator[TestClient]:
    """500도 응답으로 받는 시험용 클라이언트."""
    with TestClient(probe_app, base_url=LOCAL_BASE_URL, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def locked_client(
    monkeypatch: pytest.MonkeyPatch, config: Config, tmp_home: Path, clock: Clock
) -> Iterator[LockedApp]:
    """DB 잠금(503) 시험용: 대기 시간을 줄인 별도 엔진과 클라이언트. 본문에서 hold_lock을 건다."""
    monkeypatch.setattr(db, "BUSY_TIMEOUT_SECONDS", FAST_BUSY_TIMEOUT)
    path = tmp_home / "logbook.db"
    db.initialize_database(path)
    engine = db.open_database(path)
    try:
        with db.session_scope(engine) as s:
            services.ensure_common_project(s)
        ctx = WebContext(
            cfg=config, engine=engine, config_file=tmp_home / "config.toml", now=lambda: clock.now
        )
        with TestClient(create_app(ctx), base_url=LOCAL_BASE_URL) as c:
            yield LockedApp(c, engine, path)
    finally:
        engine.dispose()
