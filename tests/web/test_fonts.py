"""글꼴 설정: fonts_css 출력, GET /fonts.css 응답, 설정 자동 반영, 화면 링크와 CSS 기본값."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import logbook.web
from logbook.core.config import WebConfig, load_config
from logbook.web.app import create_app
from logbook.web.config_watch import ConfigWatcher
from logbook.web.context import WebContext
from logbook.web.fonts import fonts_css
from tests.web.conftest import LOCAL_BASE_URL

CSS_ROOT = Path(logbook.web.__file__).parent / "static" / "css"
COMMENT = "/* 설정 [web]의 글꼴. PC에 설치되지 않은 글꼴이면 다음 글꼴로 넘어간다. */\n"


def test_fonts_css_default_config() -> None:
    assert fonts_css(WebConfig()) == (
        COMMENT
        + ":root {\n"
        + '  --font-heading: "Bookk Gothic", var(--font-sans);\n'
        + '  --font-document: "Bookk Gothic", var(--font-sans);\n'
        + '  --font-body: "Bookk Gothic", var(--font-sans);\n'
        + "}\n"
    )


def test_fonts_css_all_empty_gives_empty_root() -> None:
    web = WebConfig(heading_font="", document_font="", body_font="")

    assert fonts_css(web) == COMMENT + ":root {\n}\n"


def test_fonts_css_body_only() -> None:
    web = WebConfig(heading_font="", document_font="", body_font="나눔고딕")

    assert fonts_css(web) == (
        COMMENT + ":root {\n" + '  --font-body: "나눔고딕", var(--font-sans);\n' + "}\n"
    )


def test_fonts_stylesheet_response_and_headers(client: TestClient) -> None:
    response = client.get("/fonts.css")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/css; charset=utf-8"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in response.headers
    assert '"Bookk Gothic"' in response.text


@pytest.fixture
def watched_client(web_ctx: WebContext) -> Iterator[TestClient]:
    path = web_ctx.config_file
    path.write_text("[web]\nport = 8765\n", encoding="utf-8")
    watcher = ConfigWatcher(path, load_config(path))
    with TestClient(create_app(web_ctx, watcher=watcher), base_url=LOCAL_BASE_URL) as c:
        yield c


def test_fonts_stylesheet_follows_config_changes(
    watched_client: TestClient, web_ctx: WebContext
) -> None:
    web_ctx.config_file.write_text(
        '[web]\nport = 8765\nheading_font = "나눔고딕"\n', encoding="utf-8"
    )

    response = watched_client.get("/fonts.css")

    assert '--font-heading: "나눔고딕", var(--font-sans);' in response.text
    assert '--font-heading: "Bookk Gothic"' not in response.text


def test_app_css_defines_font_tokens_and_body_uses_font_body() -> None:
    css = (CSS_ROOT / "app.css").read_text(encoding="utf-8")
    root = css[css.index(":root") : css.index("}", css.index(":root"))]

    assert "--font-serif" not in root
    for line in (
        "--font-body: var(--font-sans);",
        "--font-heading: var(--font-sans);",
        "--font-document: var(--font-sans);",
        "--tracking-title: -0.01em;",
        "--tracking-display: -0.035em;",
    ):
        assert line in root
    body = css[css.index("\nbody {") :]
    assert "font-family: var(--font-body);" in body[: body.index("}")]


def test_settings_css_has_font_preview_rules() -> None:
    css = (CSS_ROOT / "settings.css").read_text(encoding="utf-8")

    for name in ("font-preview", "font-preview--heading", "font-preview--document"):
        assert f".{name}" in css
    assert "var(--font-heading)" in css
    assert "var(--font-document)" in css
    assert "var(--font-body)" in css


def test_no_css_uses_the_removed_serif_token() -> None:
    for path in CSS_ROOT.glob("*.css"):
        assert "--font-serif" not in path.read_text(encoding="utf-8"), path.name


def test_dashboard_chart_font_follows_the_body_font() -> None:
    js = (CSS_ROOT.parent / "js" / "dashboard.js").read_text(encoding="utf-8")

    assert 'Chart.defaults.font.family = cssVariable("--font-body");' in js
    assert "--font-sans" not in js
