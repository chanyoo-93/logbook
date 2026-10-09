"""기록 페이지 GET /logs 테스트 (W40 = 09-28 ~ 10-04, 오늘 = 2026-10-01 목요일 09:30 +09:00)."""

import json
import re
from datetime import date
from html import unescape

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.weeks import parse_week
from logbook.web.pages.views import worklog_version
from tests.web.helpers import (
    add_log,
    add_project,
    all_by_tag,
    by_id,
    named_input,
    parse_html,
    row_ids,
    select_options,
    week_links,
)

W40_MONDAY = date(2026, 9, 28)
W40_THURSDAY = date(2026, 10, 1)
W39_THURSDAY = date(2026, 9, 24)
HTMX = {"HX-Request": "true"}


def _seed(engine: Engine) -> dict[str, int]:
    """W40에 3건(날짜 역순으로 입력), W39에 1건."""
    add_project(engine, "payment", "결제 서버")
    return {
        "thu": add_log(engine, minutes=120, note="목요일", project="payment", day=W40_THURSDAY),
        "mon_a": add_log(engine, minutes=60, note="월요일 가", day=W40_MONDAY),
        "mon_b": add_log(
            engine,
            minutes=30,
            note="월요일 나",
            project="payment",
            category="meeting",
            day=W40_MONDAY,
        ),
        "old": add_log(engine, minutes=90, note="지난주", day=W39_THURSDAY),
    }


def _week_input_values(html: str) -> list[str | None]:
    return [e.attrs["value"] for e in parse_html(html) if e.attrs.get("name") == "week"]


def _link_hrefs(html: str) -> tuple[str, str]:
    """이전·다음 주 링크의 href. 같은 링크가 htmx 속성도 갖는지 함께 확인한다."""
    links = week_links(html)
    for link in links:
        assert link.attrs["hx-get"] == link.attrs["href"]
        assert link.attrs["hx-target"] == "#log-table"
        assert link.attrs["hx-swap"] == "outerHTML"
        assert link.attrs["hx-push-url"] == "true"
    assert [link.text for link in links] == ["◀ 이전 주", "다음 주 ▶"]
    return str(links[0].attrs["href"]), str(links[1].attrs["href"])


def test_page_lists_this_week_in_date_then_id_order(client: TestClient, web_engine: Engine) -> None:
    ids = _seed(web_engine)

    response = client.get("/logs")

    assert response.status_code == 200
    html = response.text
    assert by_id(html, "log-table").tag == "section"
    assert row_ids(html) == [f"log-{ids['mon_a']}", f"log-{ids['mon_b']}", f"log-{ids['thu']}"]
    assert by_id(html, "log-total").text == "합계 3h 30m / 기록 3건"
    assert "2026-W40 (09-28 ~ 10-04)" in by_id(html, "log-table-title").text
    assert [e.text for e in parse_html(html) if e.tag == "title"] == ["기록 · logbook"]
    nav = [e for e in parse_html(html) if e.tag == "a" and e.attrs.get("href") == "/logs"]
    assert [e.attrs.get("aria-current") for e in nav] == ["page"]
    headers = [e.text for e in all_by_tag(html, "th") if e.attrs.get("scope") == "col"]
    assert headers == ["ID", "날짜", "프로젝트", "카테고리", "시간", "메모", "태스크", "동작"]


def test_page_empty_week(client: TestClient) -> None:
    response = client.get("/logs")

    assert response.status_code == 200
    assert "기록이 없습니다." in response.text
    assert row_ids(response.text) == []


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("?week=last", ["old"]),
        ("?project=payment", ["mon_b", "thu"]),
        ("?category=dev", ["mon_a", "thu"]),
        ("?project=payment&category=dev", ["thu"]),
        ("?project=&category=", ["mon_a", "mon_b", "thu"]),
        ("?week=&project=&category=", ["mon_a", "mon_b", "thu"]),
        ("?week=2026-W39", ["old"]),
    ],
    ids=["last", "project", "category", "both", "blank-filters", "blank-all", "iso-week"],
)
def test_filters(client: TestClient, web_engine: Engine, query: str, expected: list[str]) -> None:
    ids = _seed(web_engine)

    response = client.get(f"/logs{query}")

    assert response.status_code == 200
    assert row_ids(response.text) == [f"log-{ids[key]}" for key in expected]


def test_filter_form_attributes_and_selected_values(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)
    html = client.get("/logs?project=payment&category=meeting").text

    form = by_id(html, "log-filters")
    assert form.tag == "form"
    assert form.attrs["hx-get"] == "/logs"
    assert form.attrs["hx-target"] == "#log-table"
    assert form.attrs["hx-swap"] == "outerHTML"
    assert form.attrs["hx-push-url"] == "true"
    assert form.attrs["hx-trigger"] == "change, submit"
    project = select_options(html, "project")
    assert project[0] == ("", "전체", False)
    assert [value for value, _, selected in project if selected] == ["payment"]
    category = select_options(html, "category")
    assert category[0] == ("", "전체", False)
    assert [value for value, _, selected in category if selected] == ["meeting"]


def test_archived_project_is_marked_in_filter(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "legacy", "옛 프로젝트", archived=True)

    options = select_options(client.get("/logs").text, "project")

    labels = {value: label for value, label, _ in options}
    assert "(보관)" in labels["legacy"]
    assert "(보관)" not in labels["common"]


def test_week_links_keep_other_filters(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)

    assert _link_hrefs(client.get("/logs").text) == (
        "/logs?week=2026-W39",
        "/logs?week=2026-W41",
    )
    assert _link_hrefs(client.get("/logs?project=payment&category=dev").text) == (
        "/logs?week=2026-W39&project=payment&category=dev",
        "/logs?week=2026-W41&project=payment&category=dev",
    )


def test_week_input_value(client: TestClient) -> None:
    assert _week_input_values(client.get("/logs").text) == ["2026-W40"]
    assert _week_input_values(client.get("/logs?week=last").text) == ["2026-W39"]


def test_htmx_get_returns_table_and_oob_week_nav(client: TestClient, web_engine: Engine) -> None:
    ids = _seed(web_engine)

    response = client.get("/logs?week=2026-W39", headers=HTMX)

    assert response.status_code == 200
    html = response.text
    assert "<html" not in html
    assert row_ids(html) == [f"log-{ids['old']}"]
    assert by_id(html, "week-nav").attrs["hx-swap-oob"] == "true"
    assert _week_input_values(html) == ["2026-W39"]
    assert _link_hrefs(html) == ("/logs?week=2026-W38", "/logs?week=2026-W40")
    assert "hx-swap-oob" not in by_id(html, "log-table").attrs


def test_full_page_week_nav_is_not_oob(client: TestClient) -> None:
    assert "hx-swap-oob" not in by_id(client.get("/logs").text, "week-nav").attrs


def test_htmx_request_returns_fragment_only(client: TestClient) -> None:
    response = client.get("/logs", headers=HTMX)

    assert "<html" not in response.text
    assert by_id(response.text, "log-table").tag == "section"


def test_history_restore_returns_full_page(client: TestClient) -> None:
    response = client.get("/logs", headers={**HTMX, "HX-History-Restore-Request": "true"})

    assert "<html" in response.text
    assert by_id(response.text, "log-filters").tag == "form"


def _bad_week_message() -> str:
    with pytest.raises(InvalidInputError) as caught:
        parse_week("x")
    return str(caught.value)


def test_bad_week_full_page_shows_filters_and_error(client: TestClient) -> None:
    response = client.get("/logs?week=x")

    assert response.status_code == 400
    html = response.text
    assert "<html" in html
    assert _week_input_values(html) == ["x"]
    alerts = [e.text for e in parse_html(html) if e.attrs.get("role") == "alert"]
    assert alerts == [_bad_week_message()]
    assert row_ids(html) == []


def test_bad_week_htmx_writes_to_flash(client: TestClient) -> None:
    response = client.get("/logs?week=x", headers=HTMX)

    assert response.status_code == 400
    assert response.headers["HX-Retarget"] == "#flash"
    assert response.headers["HX-Push-Url"] == "false"
    assert _bad_week_message() in unescape(response.text)
    assert "<html" not in response.text


def test_unknown_project_filter_is_404(client: TestClient, web_engine: Engine) -> None:
    with db.session_scope(web_engine) as s, pytest.raises(NotFoundError) as caught:
        services.get_project(s, "nope")

    response = client.get("/logs?project=nope")

    assert response.status_code == 404
    assert str(caught.value) in unescape(response.text)


def test_row_buttons_carry_confirm_text_and_version(client: TestClient, web_engine: Engine) -> None:
    log_id = add_log(web_engine, minutes=120, note="결제 재시도", day=W40_THURSDAY)
    with db.session_scope(web_engine) as s:
        version = worklog_version(services.get_worklog(s, log_id))

    html = client.get("/logs").text

    assert by_id(html, f"log-{log_id}").tag == "tr"
    deletes = [e for e in parse_html(html) if e.attrs.get("hx-delete") == f"/logs/{log_id}"]
    assert len(deletes) == 1
    button = deletes[0]
    assert button.attrs["hx-confirm"] == (
        f"삭제할 기록: #{log_id} 2026-10-01 (목) common/dev 2h — 결제 재시도\n삭제할까요?"
    )
    assert json.loads(str(button.attrs["hx-vals"])) == {"version": version}
    assert button.attrs["hx-include"] == "#log-filters"
    assert button.attrs["hx-target"] == "#log-table"
    assert button.attrs["hx-swap"] == "outerHTML"
    assert button.attrs["hx-sync"] == "this:drop"
    assert button.attrs["hx-disabled-elt"] == "this"
    edits = [e for e in parse_html(html) if e.attrs.get("hx-get") == f"/logs/{log_id}/edit"]
    assert len(edits) == 1
    assert edits[0].attrs["hx-target"] == "closest tr"
    assert edits[0].attrs["hx-swap"] == "outerHTML"


HOSTILE_NOTE = "\"><script>alert(1)</script>'<img src=x onerror=alert(2)>"


def test_user_text_is_escaped_in_table_attributes_and_edit_row(
    client: TestClient, web_engine: Engine
) -> None:
    log_id = add_log(web_engine, minutes=10, note=HOSTILE_NOTE, day=W40_THURSDAY)

    for html in (client.get("/logs").text, client.get(f"/logs/{log_id}/edit").text):
        assert "<script>alert(1)" not in html
        assert "<img" not in html
    table = client.get("/logs").text
    delete = [e for e in parse_html(table) if e.attrs.get("hx-delete")][0]
    assert HOSTILE_NOTE in str(delete.attrs["hx-confirm"])
    edit = client.get(f"/logs/{log_id}/edit").text
    assert named_input(edit, "note").attrs["value"] == HOSTILE_NOTE


def test_pages_have_no_inline_code(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed(web_engine)["thu"]
    pages = [
        client.get("/logs").text,
        client.get("/logs?week=x").text,
        client.get(f"/logs/{log_id}/edit").text,
        client.get(f"/logs/{log_id}/row").text,
    ]

    for html in pages:
        assert all(s.attrs.get("src") and s.text == "" for s in all_by_tag(html, "script"))
        assert "<style" not in html
        assert not re.search(r"\sstyle\s*=", html, re.IGNORECASE)
        assert not re.search(r"\son[a-z]+\s*=", html, re.IGNORECASE)
        assert "hx-on" not in html
        assert "javascript:" not in html


@pytest.mark.parametrize(
    ("week", "labels"),
    [("0001-W01", ["다음 주 ▶"]), ("9999-W51", ["◀ 이전 주"])],
    ids=["first-week", "last-week"],
)
def test_week_links_are_omitted_at_range_end(
    client: TestClient, week: str, labels: list[str]
) -> None:
    response = client.get(f"/logs?week={week}")

    assert response.status_code == 200
    assert [link.text for link in week_links(response.text)] == labels


def test_table_title_can_take_focus_after_delete(client: TestClient) -> None:
    assert by_id(client.get("/logs").text, "log-table-title").attrs["tabindex"] == "-1"
