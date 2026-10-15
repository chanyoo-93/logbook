"""설정 화면 카테고리 색 표: 표시, 저장, 자동으로 되돌림, 오류, 인라인 코드, 꼬리표·차트 반영."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import Engine

import logbook.web
from logbook.core import db, services
from logbook.web.errors import CATEGORY_CHANGED
from logbook.web.pages.panels import NO_CHANGE
from logbook.web.pages.settings import (
    CATEGORY_NOTE,
    CATEGORY_RESET,
    CATEGORY_SAVED,
    category_version,
)
from logbook.web.pages.views import CHART_PALETTE
from tests.web.helpers import (
    add_log,
    all_by_tag,
    by_class,
    by_id,
    flash_text,
    inline_code_violations,
    json_attr,
    parse_html,
)
from tests.web.test_dashboard import W40_THURSDAY

HTMX = {"HX-Request": "true"}
APP_JS = Path(logbook.web.__file__).parent / "static" / "js" / "app.js"


def _stored(engine: Engine) -> dict[str, str]:
    with db.session_scope(engine) as s:
        return services.category_colors(s)


def _version(engine: Engine, key: str) -> str:
    return category_version(key, _stored(engine).get(key))


def _post(client: TestClient, engine: Engine, key: str, **fields: str):  # type: ignore[no-untyped-def]
    form = {"color": "", "version": _version(engine, key)}
    return client.post(f"/settings/categories/{key}/color", data={**form, **fields}, headers=HTMX)


def _row_inputs(html: str, key: str) -> dict[str, dict[str, str | None]]:
    """행(tr id=category-키) 안의 input을 name -> attrs로."""
    result: dict[str, dict[str, str | None]] = {}
    in_row = False
    for e in parse_html(html):
        if e.tag == "tr":
            in_row = e.attrs.get("id") == f"category-{key}"
        elif in_row and e.tag == "input":
            result[str(e.attrs["name"])] = e.attrs
    return result


def test_table_shows_configured_categories_in_order(client: TestClient) -> None:
    html = client.get("/settings").text

    rows = [
        str(e.attrs["id"])
        for e in all_by_tag(html, "tr")
        if str(e.attrs.get("id", "")).startswith("category-")
    ]
    assert rows[:3] == ["category-dev", "category-review", "category-meeting"]
    assert by_id(html, "category-section").tag == "section"
    assert by_id(html, "category-dev").text.startswith("dev 개발")
    assert CATEGORY_NOTE in html
    assert "info__categories" not in html


def _row_cells(html: str, key: str) -> list[str]:
    """행(tr id=category-키) 안 td의 class 문자열 목록(순서대로)."""
    cells: list[str] = []
    in_row = False
    for e in parse_html(html):
        if e.tag == "tr":
            in_row = e.attrs.get("id") == f"category-{key}"
        elif in_row and e.tag == "td":
            cells.append(str(e.attrs.get("class") or ""))
    return cells


def test_label_cell_does_not_wrap_on_narrow_screens(client: TestClient) -> None:
    # 다른 칸이 모두 nowrap이라 320px에서 이름 칸만 줄어 글자가 세로로 쌓였다.
    # 이름도 nowrap으로 두고 표 안 가로 스크롤로 본다.
    html = client.get("/settings").text

    cells = _row_cells(html, "ops")

    assert len(cells) == 4
    assert "nowrap" in cells[1].split()


def test_default_row_uses_palette_color_and_auto_is_on(client: TestClient) -> None:
    html = client.get("/settings").text

    inputs = _row_inputs(html, "review")

    assert inputs["color"]["type"] == "color"
    assert inputs["color"]["value"] == CHART_PALETTE[1]
    assert inputs["auto"]["type"] == "checkbox"
    assert inputs["auto"]["value"] == "1"
    assert "checked" in inputs["auto"]
    assert inputs["version"]["type"] == "hidden"
    assert inputs["version"]["value"] == category_version("review", None)


def test_stored_color_shows_and_auto_is_off(client: TestClient, web_engine: Engine) -> None:
    with db.session_scope(web_engine) as s:
        services.set_category_color(s, "dev", "#2F6FDE")

    inputs = _row_inputs(client.get("/settings").text, "dev")

    assert inputs["color"]["value"] == "#2F6FDE"
    assert "checked" not in inputs["auto"]
    assert inputs["version"]["value"] == category_version("dev", "#2F6FDE")


def test_save_stores_color_and_shows_result(client: TestClient, web_engine: Engine) -> None:
    response = _post(client, web_engine, "dev", color="#123456")

    assert response.status_code == 200
    assert _stored(web_engine) == {"dev": "#123456"}
    assert CATEGORY_SAVED.format(key="dev") in response.text
    assert by_id(response.text, "category-section").tag == "section"
    assert CATEGORY_SAVED.format(key="dev") == "✔ dev 색을 저장했습니다."


def test_auto_clears_stored_color(client: TestClient, web_engine: Engine) -> None:
    with db.session_scope(web_engine) as s:
        services.set_category_color(s, "dev", "#123456")

    response = _post(client, web_engine, "dev", color="#123456", auto="1")

    assert response.status_code == 200
    assert _stored(web_engine) == {}
    assert CATEGORY_RESET.format(key="dev") in response.text
    assert CATEGORY_RESET.format(key="dev") == "✔ dev 색을 자동으로 되돌렸습니다."


def test_auto_without_stored_color_is_no_change(client: TestClient, web_engine: Engine) -> None:
    response = _post(client, web_engine, "dev", auto="1")

    assert NO_CHANGE in response.text
    assert _stored(web_engine) == {}


def test_same_color_is_no_change(client: TestClient, web_engine: Engine) -> None:
    with db.session_scope(web_engine) as s:
        services.set_category_color(s, "dev", "#123456")

    response = _post(client, web_engine, "dev", color="#123456")

    assert NO_CHANGE in response.text


def test_same_color_in_other_case_is_no_change(client: TestClient, web_engine: Engine) -> None:
    with db.session_scope(web_engine) as s:
        services.set_category_color(s, "dev", "#2F6FDE")

    response = _post(client, web_engine, "dev", color="#2f6fde")

    assert NO_CHANGE in response.text
    assert _stored(web_engine) == {"dev": "#2F6FDE"}


def test_other_version_is_409_flash(client: TestClient, web_engine: Engine) -> None:
    stale = _version(web_engine, "dev")
    with db.session_scope(web_engine) as s:
        services.set_category_color(s, "dev", "#111111")

    response = client.post(
        "/settings/categories/dev/color",
        data={"color": "#222222", "version": stale},
        headers=HTMX,
    )

    assert response.status_code == 409
    assert response.headers["HX-Retarget"] == "#flash"
    assert flash_text(response.text) == CATEGORY_CHANGED.format(key="dev")
    assert _stored(web_engine) == {"dev": "#111111"}


def test_unknown_key_is_404_flash(client: TestClient, web_engine: Engine) -> None:
    response = client.post(
        "/settings/categories/nope/color", data={"color": "#222222", "version": ""}, headers=HTMX
    )

    assert response.status_code == 404
    assert response.headers["HX-Retarget"] == "#flash"
    assert _stored(web_engine) == {}


def test_invalid_color_is_400_flash(client: TestClient, web_engine: Engine) -> None:
    response = _post(client, web_engine, "dev", color="red")

    assert response.status_code == 400
    assert response.headers["HX-Retarget"] == "#flash"
    assert "색상이 올바르지 않습니다" in flash_text(response.text)
    assert _stored(web_engine) == {}


def test_cross_origin_write_is_forbidden(client: TestClient, web_engine: Engine) -> None:
    response = client.post(
        "/settings/categories/dev/color",
        data={"color": "#222222", "version": _version(web_engine, "dev")},
        headers={"Origin": "http://evil.example"},
    )

    assert response.status_code == 403
    assert _stored(web_engine) == {}


def test_settings_page_and_save_response_have_no_inline_code(
    client: TestClient, web_engine: Engine
) -> None:
    page = client.get("/settings").text
    saved = _post(client, web_engine, "dev", color="#123456").text

    assert inline_code_violations(page) == []
    assert inline_code_violations(saved) == []


def test_chart_follows_saved_color(client: TestClient, web_engine: Engine) -> None:
    add_log(web_engine, minutes=30, note="작업", category="meeting", day=W40_THURSDAY)
    with db.session_scope(web_engine) as s:
        services.set_category_color(s, "meeting", "#010203")

    chart = json_attr(client.get("/").text, "summary", "data-chart")

    assert isinstance(chart, dict)
    assert chart["categories"]["colors"] == ["#010203"]


def test_pill_class_is_added_to_log_rows(client: TestClient, web_engine: Engine) -> None:
    add_log(web_engine, minutes=30, note="작업", category="meeting", day=W40_THURSDAY)

    html = client.get("/logs").text

    assert '<span class="pill pill--cat-meeting">meeting</span>' in html
    assert by_class(html, "pill--cat-meeting")


def test_app_js_clears_auto_checkbox_when_color_input_changes() -> None:
    script = APP_JS.read_text(encoding="utf-8")

    assert 'addEventListener("input"' in script
    assert 'input[type="color"]' in script
    assert "[data-color-field]" in script
    assert "checked = false" in script
