"""설정 자동 반영이 앱에서 동작하는지: 요청별 스냅숏, 알림, 조각·API에는 알림 없음."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from logbook.core.config import load_config
from logbook.web.app import create_app
from logbook.web.config_watch import ConfigWatcher
from logbook.web.context import WebContext, get_context
from tests.web.conftest import LOCAL_BASE_URL
from tests.web.helpers import all_by_tag

HTMX = {"HX-Request": "true"}


@pytest.fixture
def config_file(web_ctx: WebContext) -> Path:
    path = web_ctx.config_file
    path.write_text("[web]\nport = 8765\n", encoding="utf-8")
    return path


@pytest.fixture
def watched_client(web_ctx: WebContext, config_file: Path) -> Iterator[TestClient]:
    watcher = ConfigWatcher(config_file, load_config(config_file))
    with TestClient(create_app(web_ctx, watcher=watcher), base_url=LOCAL_BASE_URL) as c:
        yield c


def _notices(html: str) -> list[str]:
    return [
        e.attrs.get("class") or ""
        for e in all_by_tag(html, "p")
        if "config-notice" in (e.attrs.get("class") or "")
    ]


def test_added_category_shows_up_in_quick_form(
    watched_client: TestClient, config_file: Path
) -> None:
    config_file.write_text(
        '[web]\nport = 8765\n[categories]\ndev = "개발"\nops = "운영"\n', encoding="utf-8"
    )

    html = watched_client.get("/").text

    assert "ops — 운영" in html
    assert _notices(html) == []


def test_broken_config_shows_alert_and_keeps_old_categories(
    watched_client: TestClient, config_file: Path
) -> None:
    config_file.write_text("[web\n", encoding="utf-8")

    response = watched_client.get("/logs")

    assert response.status_code == 200
    assert "config-notice--error" in response.text
    assert 'role="alert"' in response.text
    assert "dev — 개발" in response.text


def test_broken_config_has_no_notice_in_api(watched_client: TestClient, config_file: Path) -> None:
    config_file.write_text("[web\n", encoding="utf-8")

    response = watched_client.get("/api/logs")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "config-notice" not in response.text


def test_broken_config_has_no_notice_in_htmx_fragment(
    watched_client: TestClient, config_file: Path
) -> None:
    config_file.write_text("[web\n", encoding="utf-8")

    response = watched_client.get("/logs", headers=HTMX)

    assert response.status_code == 200
    assert "config-notice" not in response.text


def test_restart_required_notice_is_a_status(watched_client: TestClient, config_file: Path) -> None:
    config_file.write_text("[web]\nport = 8766\n", encoding="utf-8")

    html = watched_client.get("/").text

    assert _notices(html) == ["config-notice"]
    assert 'role="status"' in html
    assert "web.port" in html


def test_one_request_sees_one_snapshot(web_ctx: WebContext, config_file: Path) -> None:
    watcher = ConfigWatcher(config_file, load_config(config_file))
    app = create_app(web_ctx, watcher=watcher)

    @app.get("/probe")
    def probe(request: Request) -> dict[str, bool]:
        first = get_context(request)
        config_file.write_text('[categories]\nops = "운영"\n[web]\nport = 8765\n', encoding="utf-8")
        return {"same": get_context(request) is first}

    with TestClient(app, base_url=LOCAL_BASE_URL) as client:
        assert client.get("/probe").json() == {"same": True}
        assert "ops" in watcher.current().cfg.categories


def test_app_without_watcher_has_no_notice(client: TestClient) -> None:
    html = client.get("/").text

    assert "config-notice" not in html
    assert "dev — 개발" in html


def test_get_context_without_watcher_state_returns_app_ctx(web_ctx: WebContext) -> None:
    app = FastAPI()
    app.state.ctx = web_ctx

    @app.get("/same")
    def same(request: Request) -> dict[str, bool]:
        return {"same": get_context(request) is web_ctx}

    with TestClient(app) as client:
        assert client.get("/same").json() == {"same": True}
