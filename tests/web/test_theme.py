"""다크모드: 색 토큰, 대비, 하드코딩 금지, color-scheme meta."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import logbook.web
from tests.web.helpers import all_by_tag

STATIC_ROOT = Path(logbook.web.__file__).parent / "static"
CSS_ROOT = STATIC_ROOT / "css"
CSS_PATH = CSS_ROOT / "app.css"
DARK_QUERY = "@media screen and (prefers-color-scheme: dark) {"

COLOR_TOKENS = (
    "--bg",
    "--surface",
    "--ink",
    "--ink-muted",
    "--rule",
    "--rule-strong",
    "--control-border",
    "--row-hover",
    "--accent",
    "--accent-hover",
    "--accent-ink",
    "--ok",
    "--danger",
    "--tag-bg",
    "--ok-soft",
    "--danger-soft",
    "--accent-soft",
    "--band-bg",
    "--band-ink",
    "--band-muted",
    "--shadow-soft",
    "--shadow-raised",
)
CONTRAST_PAIRS = (
    ("--ink", "--bg"),
    ("--ink", "--surface"),
    ("--ink-muted", "--surface"),
    ("--ink-muted", "--bg"),
    ("--accent", "--surface"),
    ("--accent-ink", "--accent"),
    ("--danger", "--surface"),
    ("--ok", "--surface"),
    ("--ink-muted", "--tag-bg"),
    ("--ok", "--ok-soft"),
    ("--danger", "--danger-soft"),
    ("--accent-hover", "--accent-soft"),
    ("--band-ink", "--band-bg"),
    ("--band-muted", "--band-bg"),
)
NON_TEXT_PAIRS = (
    ("--control-border", "--surface"),
    ("--control-border", "--bg"),
    ("--band-muted", "--band-bg"),
)
MIN_CONTRAST = 4.5
MIN_NON_TEXT_CONTRAST = 3.0


def _matching_brace(text: str, open_index: int) -> int:
    """open_index의 `{`와 짝이 맞는 `}`의 위치."""
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise AssertionError("중괄호 짝이 맞지 않습니다")


def _block_span(css: str, header: str, start: int = 0) -> tuple[int, int]:
    """header 뒤의 `{…}` 블록의 (여는 위치, 닫는 위치)."""
    header_index = css.index(header, start)
    open_index = css.index("{", header_index)
    return open_index, _matching_brace(css, open_index)


def _blocks(css: str) -> tuple[tuple[int, int], tuple[int, int]]:
    light = _block_span(css, ":root")
    media_open, media_close = _block_span(css, DARK_QUERY.removesuffix(" {"))
    dark_open, dark_close = _block_span(css, ":root", media_open)
    assert dark_close < media_close
    return light, (dark_open, dark_close)


def _tokens(body: str) -> dict[str, str]:
    return {name: value.strip() for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body)}


def _luminance(color: str) -> float:
    digits = color.lstrip("#")
    channels = [int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.fixture(scope="module")
def css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def other_css() -> str:
    """app.css(:root 토큰 두 블록이 있는 파일)를 뺀 나머지 스타일 파일 전부."""
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(CSS_ROOT.glob("*.css"))
        if path != CSS_PATH
    )


@pytest.fixture(scope="module")
def themes(css: str) -> dict[str, dict[str, str]]:
    light, dark = _blocks(css)
    return {
        "light": _tokens(css[light[0] + 1 : light[1]]),
        "dark": _tokens(css[dark[0] + 1 : dark[1]]),
    }


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_both_themes_define_every_color_token(
    themes: dict[str, dict[str, str]], theme: str
) -> None:
    missing = [token for token in COLOR_TOKENS if token not in themes[theme]]
    assert missing == []


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(("foreground", "background"), CONTRAST_PAIRS)
def test_theme_pairs_meet_wcag_contrast(
    themes: dict[str, dict[str, str]], theme: str, foreground: str, background: str
) -> None:
    colors = themes[theme]

    ratio = _contrast(colors[foreground], colors[background])

    assert ratio >= MIN_CONTRAST, f"{theme} {foreground}/{background}: {ratio:.2f}"


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(("foreground", "background"), NON_TEXT_PAIRS)
def test_control_border_meets_non_text_contrast(
    themes: dict[str, dict[str, str]], theme: str, foreground: str, background: str
) -> None:
    colors = themes[theme]

    ratio = _contrast(colors[foreground], colors[background])

    assert ratio >= MIN_NON_TEXT_CONTRAST, f"{theme} {foreground}/{background}: {ratio:.2f}"


def test_colors_are_literals_only_inside_the_two_root_blocks(css: str, other_css: str) -> None:
    light, dark = _blocks(css)
    rest = css[: light[0]] + css[light[1] + 1 : dark[0]] + css[dark[1] + 1 :] + other_css

    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", rest)
    assert not re.search(r"\b(?:rgb|rgba|hsl|hsla|oklch)\(", rest)


def test_dark_theme_applies_to_screen_only(css: str, other_css: str) -> None:
    assert DARK_QUERY in css
    assert "@media (prefers-color-scheme: dark)" not in css + other_css
    assert "prefers-color-scheme" not in other_css


def test_root_blocks_live_only_in_app_css(other_css: str) -> None:
    assert ":root" not in other_css


def test_root_declares_color_scheme(css: str) -> None:
    light, _ = _blocks(css)

    assert re.search(r"color-scheme\s*:\s*light dark\s*;", css[light[0] : light[1]])


def test_dashboard_declares_color_scheme_meta(client: TestClient) -> None:
    html = client.get("/").text

    metas = [m for m in all_by_tag(html, "meta") if m.attrs.get("name") == "color-scheme"]
    assert [m.attrs["content"] for m in metas] == ["light dark"]


def test_error_page_declares_color_scheme_meta(probe_client: TestClient) -> None:
    html = probe_client.get("/raise/missing").text

    metas = [m for m in all_by_tag(html, "meta") if m.attrs.get("name") == "color-scheme"]
    assert [m.attrs["content"] for m in metas] == ["light dark"]


def test_dashboard_script_redraws_charts_when_os_theme_changes() -> None:
    script = (STATIC_ROOT / "js" / "dashboard.js").read_text(encoding="utf-8")

    assert 'matchMedia("(prefers-color-scheme: dark)")' in script
    assert re.search(r'addEventListener\("change",\s*drawCharts\)', script)


def test_pill_rules_exist_and_old_tag_rules_are_gone(other_css: str) -> None:
    assert re.search(r"\.pill\s*\{", other_css)
    assert re.search(r"\.pill--ok\s*\{", other_css)
    assert re.search(r"\.pill--danger\s*\{", other_css)
    for old in (".task-card__tag", ".task-card__over", ".timer__state"):
        assert old not in other_css
