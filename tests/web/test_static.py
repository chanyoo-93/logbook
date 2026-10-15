"""정적 파일(/static/)과 base.html의 htmx 설정 테스트."""

import hashlib
import json
import mimetypes
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import logbook.web
from logbook.web.app import create_app
from logbook.web.assets import FONTS_CSS_URL, STYLESHEETS
from logbook.web.context import WebContext
from tests.web.conftest import LOCAL_BASE_URL
from tests.web.helpers import all_by_tag

STATIC_ROOT = Path(logbook.web.__file__).parent / "static"
VENDOR_ROOT = STATIC_ROOT / "vendor"

CSS = "text/css; charset=utf-8"
JS = "text/javascript; charset=utf-8"

# 공통 규칙 '화면(HTMX) 공통'의 htmx 설정 값(그대로)
HTMX_CONFIG = {
    "includeIndicatorStyles": False,
    "allowEval": False,
    "allowScriptTags": False,
    "selfRequestsOnly": True,
    "responseHandling": [
        {"code": "204", "swap": False},
        {"code": "[23]..", "swap": True},
        {"code": "[45]..", "swap": True, "error": True},
    ],
}

VENDOR_FILES = (
    "htmx-2.0.11.min.js",
    "chart-4.5.1.umd.min.js",
    "sortable-1.15.7.min.js",
    "LICENSE-htmx.txt",
    "LICENSE-chartjs.md",
    "LICENSE-sortablejs.txt",
)
_README_ROW = re.compile(r"^\|\s*`(?P<name>[^`]+)`.*`(?P<sha>[0-9a-f]{64})`\s*\|\s*$", re.MULTILINE)


def _readme_hashes() -> dict[str, str]:
    text = (VENDOR_ROOT / "README.md").read_text(encoding="utf-8")
    return {match["name"]: match["sha"] for match in _README_ROW.finditer(text)}


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        *[(f"/static/css/{name}", CSS) for name in STYLESHEETS],
        ("/static/js/app.js", JS),
        ("/static/js/dashboard.js", JS),
        ("/static/js/report.js", JS),
        ("/static/vendor/htmx-2.0.11.min.js", JS),
        ("/static/vendor/chart-4.5.1.umd.min.js", JS),
        ("/static/vendor/sortable-1.15.7.min.js", JS),
    ],
)
def test_static_files_are_served_with_type_and_security_headers(
    client: TestClient, path: str, content_type: str
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"] == content_type
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["etag"]
    assert response.content


def test_static_conditional_request_gets_304_with_security_headers(client: TestClient) -> None:
    etag = client.get("/static/css/app.css").headers["etag"]

    response = client.get("/static/css/app.css", headers={"If-None-Match": etag})

    assert response.status_code == 304
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_pages_stay_no_store(client: TestClient) -> None:
    assert client.get("/").headers["cache-control"] == "no-store"


def test_static_favicon_is_svg(client: TestClient) -> None:
    response = client.get("/static/favicon.svg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert "<script" not in response.text


def test_static_missing_file_is_a_korean_not_found_page(client: TestClient) -> None:
    response = client.get("/static/nope.js")

    assert response.status_code == 404
    assert "페이지를 찾을 수 없습니다: /static/nope.js" in response.text
    assert response.headers["content-type"] == "text/html; charset=utf-8"


def test_static_paths_cannot_leave_the_static_directory(client: TestClient) -> None:
    response = client.get("/static/%2e%2e/app.py")

    assert response.status_code == 404


def test_create_app_overrides_a_registry_mime_type_for_js(
    monkeypatch: pytest.MonkeyPatch, web_ctx: WebContext
) -> None:
    # Windows 레지스트리가 .js를 text/plain으로 등록한 PC에서도 nosniff가 스크립트를 막지 않는다.
    monkeypatch.setitem(mimetypes.types_map, ".js", "text/plain")
    monkeypatch.setitem(mimetypes.types_map, ".css", "text/plain")

    with TestClient(create_app(web_ctx), base_url=LOCAL_BASE_URL) as client:
        assert client.get("/static/js/app.js").headers["content-type"] == JS
        for name in STYLESHEETS:
            assert client.get(f"/static/css/{name}").headers["content-type"] == CSS


def test_vendor_readme_lists_every_vendor_file() -> None:
    assert set(_readme_hashes()) == set(VENDOR_FILES)


@pytest.mark.parametrize("name", VENDOR_FILES)
def test_vendor_file_matches_readme_sha256(name: str) -> None:
    digest = hashlib.sha256((VENDOR_ROOT / name).read_bytes()).hexdigest()

    assert digest == _readme_hashes()[name]


def test_vendor_directory_has_nothing_unlisted() -> None:
    names = {path.name for path in VENDOR_ROOT.iterdir()}

    assert names == {*VENDOR_FILES, "README.md"}


def test_vendor_readme_names_versions_licenses_and_sources() -> None:
    text = (VENDOR_ROOT / "README.md").read_text(encoding="utf-8")

    words = ("2.0.11", "4.5.1", "1.15.7", "0BSD", "MIT", "registry.npmjs.org", "tasks.html")
    for expected in words:
        assert expected in text


def test_base_template_sets_the_htmx_config(client: TestClient) -> None:
    html = client.get("/").text

    metas = [m for m in all_by_tag(html, "meta") if m.attrs.get("name") == "htmx-config"]
    assert len(metas) == 1
    content = metas[0].attrs["content"]
    assert content is not None
    assert json.loads(content) == HTMX_CONFIG


def test_stylesheet_list_has_every_css_file_exactly_once() -> None:
    on_disk = sorted(path.name for path in (STATIC_ROOT / "css").glob("*.css"))

    assert sorted(STYLESHEETS) == on_disk


def _linked_sheets(html: str) -> list[str | None]:
    return [
        e.attrs.get("href") for e in all_by_tag(html, "link") if e.attrs.get("rel") == "stylesheet"
    ]


def test_base_template_links_every_stylesheet_in_order(client: TestClient) -> None:
    assert _linked_sheets(client.get("/").text) == [
        *[f"/static/css/{n}" for n in STYLESHEETS],
        "/fonts.css",
        "/colors.css",
    ]
    assert FONTS_CSS_URL == "/fonts.css"


def test_error_page_links_the_same_stylesheets_in_the_same_order(client: TestClient) -> None:
    error = client.get("/no-such-page")

    assert error.status_code == 404
    assert _linked_sheets(error.text) == _linked_sheets(client.get("/").text)[:-1]


def test_css_files_define_color_tokens_and_reduced_motion() -> None:
    css = "\n".join(
        (STATIC_ROOT / "css" / name).read_text(encoding="utf-8") for name in STYLESHEETS
    )

    for token in (
        "--bg",
        "--surface",
        "--ink",
        "--ink-muted",
        "--rule",
        "--accent",
        "--ok",
        "--danger",
    ):
        assert re.search(rf"{re.escape(token)}\s*:", css)
    assert "prefers-reduced-motion: reduce" in css
    assert "font-variant-numeric: tabular-nums" in css
    assert ".visually-hidden" in css


def test_static_text_files_are_utf8_without_carriage_returns() -> None:
    for path in (
        *[STATIC_ROOT / "css" / name for name in STYLESHEETS],
        STATIC_ROOT / "js" / "app.js",
        STATIC_ROOT / "js" / "dashboard.js",
        STATIC_ROOT / "js" / "report.js",
        STATIC_ROOT / "favicon.svg",
    ):
        data = path.read_bytes()
        data.decode("utf-8")
        assert b"\r" not in data
