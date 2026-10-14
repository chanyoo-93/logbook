"""WebContext: 시계, 세션, 요청에서 꺼내기."""

from dataclasses import replace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from logbook.core import services
from logbook.core.errors import InvalidInputError
from logbook.web.config_watch import ConfigSnapshot
from logbook.web.context import WebContext, get_context
from tests.conftest import FIXED_TODAY
from tests.helpers import FIXED_NOW


def test_today_follows_injected_clock(web_ctx: WebContext) -> None:
    assert web_ctx.now() == FIXED_NOW
    assert web_ctx.today() == FIXED_TODAY


def test_default_clock_is_timezone_aware(web_ctx: WebContext) -> None:
    default = WebContext(cfg=web_ctx.cfg, engine=web_ctx.engine, config_file=web_ctx.config_file)
    assert default.now().tzinfo is not None
    assert default.today() == default.now().date()


def test_session_commits_on_success(web_ctx: WebContext) -> None:
    with web_ctx.session() as s:
        services.create_project(s, "payment", "결제")
    with web_ctx.session() as s:
        assert services.get_project(s, "payment").name == "결제"


def test_session_rolls_back_on_error(web_ctx: WebContext) -> None:
    with pytest.raises(InvalidInputError), web_ctx.session() as s:
        services.create_project(s, "payment", "결제")
        raise InvalidInputError("중단")
    with web_ctx.session() as s:
        slugs = [p.slug for p in services.list_projects(s)]
    assert "payment" not in slugs


def test_get_context_reads_app_state(web_ctx: WebContext) -> None:
    app = FastAPI()
    app.state.ctx = web_ctx

    @app.get("/same")
    def same(request: Request) -> dict[str, bool]:
        return {"same": get_context(request) is web_ctx}

    with TestClient(app) as client:
        assert client.get("/same").json() == {"same": True}


def test_with_snapshot_replaces_config_and_notice(web_ctx: WebContext) -> None:
    other = replace(web_ctx.cfg, default_project="payment")

    updated = web_ctx.with_snapshot(ConfigSnapshot(other, "알림", notice_error=True))

    assert updated.cfg is other
    assert updated.config_notice == "알림"
    assert updated.config_notice_error is True
    assert updated.engine is web_ctx.engine
    assert web_ctx.config_notice == ""


def test_get_context_with_watcher_caches_one_context_per_request(web_ctx: WebContext) -> None:
    calls: list[int] = []
    snapshot = ConfigSnapshot(replace(web_ctx.cfg, default_project="payment"))

    class FakeWatcher:
        def current(self) -> ConfigSnapshot:
            calls.append(1)
            return snapshot

    app = FastAPI()
    app.state.ctx = web_ctx
    app.state.watcher = FakeWatcher()

    @app.get("/twice")
    def twice(request: Request) -> dict[str, object]:
        first = get_context(request)
        return {"same": get_context(request) is first, "project": first.cfg.default_project}

    with TestClient(app) as client:
        assert client.get("/twice").json() == {"same": True, "project": "payment"}
        assert client.get("/twice").json() == {"same": True, "project": "payment"}
    assert len(calls) == 2
