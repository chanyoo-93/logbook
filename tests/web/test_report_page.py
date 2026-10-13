"""보고서 화면 GET /report 테스트 (오늘 = 2026-10-01, W40)."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core.report import TEMPLATE_NAME
from logbook.core.weeks import Week
from logbook.web.pages.report import _neighbor_url
from tests.helpers import FIXED_NOW
from tests.web.helpers import (
    add_log,
    add_project,
    by_id,
    inline_code_violations,
    parse_html,
)

HTMX = {"HX-Request": "true"}


def test_report_page_shows_preview_copy_download_and_notes_form(
    client: TestClient, web_engine: Engine
) -> None:
    add_project(web_engine, "payment", "결제")
    add_log(web_engine, minutes=90, note="결제 재시도", project="payment", day=FIXED_NOW.date())

    response = client.get("/report")

    html = response.text
    elements = parse_html(html)
    assert response.status_code == 200
    preview = by_id(html, "report-markdown")
    assert preview.tag == "pre"
    assert "# 주간업무보고" in preview.text
    current = [e for e in elements if e.tag == "a" and e.attrs.get("aria-current") == "page"]
    assert [e.attrs.get("href") for e in current] == ["/report"]
    copy = [e for e in elements if e.attrs.get("data-copy-target") == "report-markdown"]
    assert len(copy) == 1
    links = [e.attrs.get("href") for e in elements if e.tag == "a"]
    assert "/report/download?week=2026-W40" in links
    assert by_id(html, "report-notes").attrs.get("hx-post") == "/report/notes"
    assert by_id(html, "report-notes-text").text == ""
    assert by_id(html, "report-risks-text").text == ""
    assert by_id(html, "copy-status").attrs.get("role") == "status"
    assert "/static/js/report.js" in [e.attrs.get("src") for e in elements if e.tag == "script"]
    assert inline_code_violations(html) == []


def test_report_page_last_week_has_neighbor_links(client: TestClient) -> None:
    html = client.get("/report", params={"week": "last"}).text

    assert "2026-W39 (09-21 ~ 09-27)" in by_id(html, "report-body").text
    hrefs = [e.attrs.get("href") for e in parse_html(html) if e.tag == "a"]
    assert "/report?week=2026-W38" in hrefs
    assert "/report?week=2026-W40" in hrefs


def test_neighbor_url_is_none_beyond_the_supported_range() -> None:
    # /report 화면은 범위 끝 주를 그리지 못한다(0001-W01은 시간대에 따라 UTC 변환이 넘치고,
    # 9999년 마지막 주는 다음 주 계획 계산이 실패한다). 그래서 링크 규칙은 함수로 확인한다.
    assert _neighbor_url(Week(1, 1), forward=False) is None
    assert _neighbor_url(Week(1, 1), forward=True) == "/report?week=0001-W02"
    assert _neighbor_url(Week(9999, 51), forward=True) is None
    assert _neighbor_url(Week(9999, 51), forward=False) == "/report?week=9999-W50"


def test_report_page_rejects_bad_week_with_full_page(client: TestClient) -> None:
    response = client.get("/report", params={"week": "abc"})

    assert response.status_code == 400
    assert "주차" in response.text
    assert 'role="alert"' in response.text
    assert "<html" in response.text


def test_report_page_bad_week_for_htmx_is_flash_fragment(client: TestClient) -> None:
    response = client.get("/report", params={"week": "abc"}, headers=HTMX)

    assert response.status_code == 400
    assert response.headers["hx-retarget"] == "#flash"
    assert "주차" in response.text
    assert "<html" not in response.text


def test_report_htmx_returns_body_and_oob_nav(client: TestClient) -> None:
    response = client.get("/report", params={"week": "last"}, headers=HTMX)

    assert response.status_code == 200
    assert "<html" not in response.text
    assert by_id(response.text, "report-body")
    assert by_id(response.text, "report-nav").attrs.get("hx-swap-oob") == "true"


def test_report_page_broken_user_template_still_renders(client: TestClient, tmp_home: Path) -> None:
    (tmp_home / TEMPLATE_NAME).write_text("a\n{% if %}\n", encoding="utf-8")

    response = client.get("/report")

    assert response.status_code == 200
    assert "보고서 템플릿을 읽지 못했습니다" in response.text
    assert by_id(response.text, "report-notes").tag == "form"
    # 미리보기가 없으므로 복사·내려받기 버튼은 숨는다.
    elements = parse_html(response.text)
    assert not [e for e in elements if "data-copy-target" in e.attrs]
    assert not [e for e in elements if str(e.attrs.get("href", "")).startswith("/report/download")]
    assert not [e for e in elements if e.attrs.get("id") == "report-markdown"]
