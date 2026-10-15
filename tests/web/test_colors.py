"""카테고리 색: category_color_map, colors_css, GET /colors.css, category_class, 링크, 대비."""

import dataclasses
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.web.app import create_app
from logbook.web.assets import COLORS_CSS_URL
from logbook.web.colors import colors_css
from logbook.web.context import WebContext
from logbook.web.pages.templating import TEMPLATES
from logbook.web.pages.views import CHART_PALETTE, category_color_map
from tests.web.conftest import LOCAL_BASE_URL
from tests.web.helpers import all_by_tag
from tests.web.test_theme import CSS_PATH, _blocks, _contrast, _tokens

CONFIGURED = ("dev", "review", "meeting")
MIN_TEXT_CONTRAST = 4.5
TINT = 0.20
EXTREMES = ("#000000", "#ffffff", "#ffff00", "#00bfff", "#ff00ff")


def test_color_map_uses_palette_position_without_stored_colors() -> None:
    result = category_color_map(CONFIGURED, {})

    assert result == {
        "dev": CHART_PALETTE[0],
        "review": CHART_PALETTE[1],
        "meeting": CHART_PALETTE[2],
    }


def test_color_map_prefers_stored_color() -> None:
    result = category_color_map(CONFIGURED, {"review": "#123456"})

    assert result["review"] == "#123456"
    assert result["dev"] == CHART_PALETTE[0]


def test_color_map_unknown_present_keys_follow_configured_in_name_order() -> None:
    result = category_color_map(CONFIGURED, {"zzz": "#abcdef"}, present=("zzz", "old", "dev"))

    assert result["old"] == CHART_PALETTE[3]
    assert result["zzz"] == "#abcdef"
    assert result["dev"] == CHART_PALETTE[0]


def test_color_map_without_present_has_only_configured_keys() -> None:
    assert list(category_color_map(CONFIGURED, {"zzz": "#abcdef"})) == list(CONFIGURED)


def test_colors_css_default_follows_configured_order() -> None:
    css = colors_css(CONFIGURED, {})

    lines = [line for line in css.splitlines() if line.startswith(".pill--cat-")]
    assert [line.split(" ")[0] for line in lines] == [
        ".pill--cat-dev",
        ".pill--cat-review",
        ".pill--cat-meeting",
    ]
    assert (
        f".pill--cat-dev {{ background: color-mix(in srgb, {CHART_PALETTE[0]} "
        "var(--pill-tint), var(--surface)); color: var(--ink); }"
    ) in css


def test_colors_css_reflects_stored_color_and_keeps_removed_category() -> None:
    css = colors_css(CONFIGURED, {"dev": "#111111", "gone": "#222222", "alpha": "#333333"})

    assert "color-mix(in srgb, #111111 var(--pill-tint)" in css
    names = [line.split(" ")[0] for line in css.splitlines() if line.startswith(".pill--cat-")]
    assert names == [
        ".pill--cat-dev",
        ".pill--cat-review",
        ".pill--cat-meeting",
        ".pill--cat-alpha",
        ".pill--cat-gone",
    ]


def test_colors_css_skips_bad_keys_and_colors() -> None:
    stored = {"Bad Key": "#111111", "x{}": "#111111", "ok": "red", "ok2": "#12345"}

    css = colors_css(("dev", "Bad"), stored)

    assert "Bad" not in css
    assert "ok" not in css
    assert "red" not in css
    assert ".pill--cat-dev" in css


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("dev", "pill--cat-dev"),
        ("ops-2", "pill--cat-ops-2"),
        ("Bad Key", ""),
        ("한글", ""),
        ("", ""),
    ],
)
def test_category_class_filter(key: str, expected: str) -> None:
    assert TEMPLATES.env.filters["category_class"](key) == expected


def test_colors_stylesheet_response_and_headers(client: TestClient) -> None:
    response = client.get(COLORS_CSS_URL)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/css; charset=utf-8"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in response.headers
    assert ".pill--cat-dev" in response.text


def test_colors_stylesheet_shows_color_saved_just_before(
    client: TestClient, web_engine: Engine
) -> None:
    with db.session_scope(web_engine) as s:
        services.set_category_color(s, "dev", "#abcdef")

    assert "color-mix(in srgb, #abcdef var(--pill-tint)" in client.get(COLORS_CSS_URL).text


def test_colors_stylesheet_respects_config_categories(web_ctx: WebContext) -> None:
    cfg = dataclasses.replace(web_ctx.cfg, categories={"solo": "하나"})
    ctx = dataclasses.replace(web_ctx, cfg=cfg)

    with TestClient(create_app(ctx), base_url=LOCAL_BASE_URL) as c:
        text = c.get(COLORS_CSS_URL).text

    assert ".pill--cat-solo" in text
    assert ".pill--cat-dev" not in text


def _linked(html: str) -> list[str | None]:
    return [
        e.attrs.get("href") for e in all_by_tag(html, "link") if e.attrs.get("rel") == "stylesheet"
    ]


def test_screen_links_colors_css_after_fonts_css(client: TestClient) -> None:
    links = _linked(client.get("/").text)

    assert links[-2:] == ["/fonts.css", "/colors.css"]


def test_error_page_does_not_link_colors_css(client: TestClient) -> None:
    error = client.get("/no-such-page")

    assert error.status_code == 404
    assert "/colors.css" not in _linked(error.text)


def _mix(foreground: str, background: str) -> str:
    """sRGB 값으로 foreground를 TINT만큼 background에 섞는다."""
    mixed = [
        round(int(foreground[i : i + 2], 16) * TINT + int(background[i : i + 2], 16) * (1 - TINT))
        for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{c:02x}" for c in mixed)


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("color", [*CHART_PALETTE, *EXTREMES])
def test_tinted_background_keeps_ink_contrast(theme: str, color: str) -> None:
    css = CSS_PATH.read_text(encoding="utf-8")
    light, dark = _blocks(css)
    span = light if theme == "light" else dark
    tokens = _tokens(css[span[0] + 1 : span[1]])
    assert re.fullmatch(r"20%", _tokens(css[light[0] + 1 : light[1]])["--pill-tint"])
    ratio = _contrast(tokens["--ink"], _mix(color, tokens["--surface"]))

    assert ratio >= MIN_TEXT_CONTRAST, f"{theme} {color}: {ratio:.2f}"
