"""공용 부품: 아이콘·컨텍스트 메뉴 매크로, 메뉴 동작·스타일 구조 테스트."""

import re
from pathlib import Path

import pytest

import logbook.web
from logbook.web.pages.templating import TEMPLATES
from tests.web.helpers import all_by_tag, by_class, inline_code_violations

STATIC_ROOT = Path(logbook.web.__file__).parent / "static"
APP_JS = STATIC_ROOT / "js" / "app.js"
COMPONENTS_CSS = STATIC_ROOT / "css" / "components.css"

ICONS = ("icon_copy", "icon_download", "icon_more")


def _render(source: str) -> str:
    """테스트 전용 템플릿을 앱의 jinja 환경으로 그린다."""
    return TEMPLATES.env.from_string(source).render()


@pytest.mark.parametrize("name", ICONS)
def test_icon_macro_renders_a_decorative_inline_svg(name: str) -> None:
    html = _render(f'{{% from "partials/icons.html" import {name} %}}{{{{ {name}() }}}}')

    svg = all_by_tag(html, "svg")[0]
    assert svg.attrs["aria-hidden"] == "true"
    assert svg.attrs["class"] == "icon"
    assert svg.attrs["viewbox"]  # HTML 파서가 속성 이름을 소문자로 바꾼다
    assert "currentColor" in html
    assert inline_code_violations(html) == []


def test_menu_macro_renders_a_button_and_a_hidden_menu_with_the_caller_items() -> None:
    html = _render(
        '{% from "partials/menu.html" import row_menu %}'
        '{% call row_menu("동작") %}'
        '<button type="button" role="menuitem">수정</button>'
        "{% endcall %}"
    )

    button = by_class(html, "menu__button")[0]
    assert button.tag == "button"
    assert button.attrs["type"] == "button"
    assert button.attrs["aria-haspopup"] == "menu"
    assert button.attrs["aria-expanded"] == "false"
    assert button.attrs["aria-label"] == "동작"
    assert button.attrs["title"] == "동작"
    menu = by_class(html, "menu__list")[0]
    assert menu.attrs["role"] == "menu"
    assert "hidden" in menu.attrs
    assert "수정" in menu.text
    assert by_class(html, "menu")
    assert inline_code_violations(html) == []


def test_menu_macro_button_contains_the_more_icon() -> None:
    html = _render(
        '{% from "partials/menu.html" import row_menu %}{% call row_menu("동작") %}{% endcall %}'
    )

    assert all_by_tag(html, "svg")[0].attrs["aria-hidden"] == "true"


@pytest.mark.parametrize(
    "needle",
    [
        "aria-expanded",
        "ArrowDown",
        "ArrowUp",
        "Escape",
        '"Tab"',
        "menuitem",
        "menu__button",
        "menu__list",
        "hidden",
        "closeMenus",
        # 항목을 누르면 ⋮로 포커스를 돌린다(삭제 확인 창 취소 뒤에도 포커스가 남는다)
        'closeMenu(item.closest(".menu"), true)',
        # 크기를 재기 전에 이전 자리를 지운다
        'list.style.left = "0px"',
    ],
)
def test_app_js_handles_the_context_menu(needle: str) -> None:
    script = APP_JS.read_text(encoding="utf-8")

    assert needle in script


def test_app_js_menu_uses_delegation_and_no_inline_eval() -> None:
    script = APP_JS.read_text(encoding="utf-8")

    assert 'document.addEventListener("click"' in script
    assert "eval(" not in script
    assert "innerHTML" not in script


def _declarations(selector: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", COMPONENTS_CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        if " ".join(match.group(1).split()) == selector:
            return match.group(2)
    raise AssertionError(f"{selector} 규칙이 없습니다")


@pytest.mark.parametrize(
    "selector",
    [
        ".icon",
        ".icon-button",
        ".menu",
        ".menu__button",
        ".menu__list",
        ".menu__list[hidden]",
        ".menu__item",
    ],
)
def test_components_css_has_menu_and_icon_rules(selector: str) -> None:
    assert _declarations(selector).strip()


def test_menu_list_floats_above_scroll_boxes_and_is_kept_on_screen() -> None:
    menu = _declarations(".menu")
    lst = _declarations(".menu__list")

    assert "position: relative" in menu
    assert "position: fixed" in lst  # 표 스크롤 상자에 잘리지 않게. 위치는 app.js가 정한다
    assert "max-width: calc(100vw" in lst
    assert "z-index" in lst
    assert "display: none" in _declarations(".menu__list[hidden]")


def test_menu_rules_use_color_tokens_only() -> None:
    block = "".join(
        _declarations(s) for s in (".icon-button", ".menu__button", ".menu__list", ".menu__item")
    )

    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|oklch)\(", block)
    assert "var(--" in block
