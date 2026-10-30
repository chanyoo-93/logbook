"""오류 페이지(2026-10-29 G3): 다른 화면과 같은 머리, 오류 카드, 관련 화면·대시보드 링크."""

import pytest
from fastapi.testclient import TestClient

from logbook.web import errors
from tests.helpers import hold_lock
from tests.web.conftest import RAISED_ERRORS, LockedApp
from tests.web.helpers import all_by_tag, by_class, inline_code_violations


@pytest.mark.parametrize(
    ("kind", "title"),
    [
        ("missing", "찾을 수 없습니다"),
        ("busy", "지금은 열 수 없습니다"),
        ("invalid", "요청을 처리할 수 없습니다"),
        ("conflict", "요청을 처리할 수 없습니다"),
    ],
)
def test_title_follows_status(probe_client: TestClient, kind: str, title: str) -> None:
    assert _title(probe_client.get(f"/raise/{kind}").text) == title


def test_internal_error_title(probe_client: TestClient) -> None:
    assert _title(probe_client.get("/boom").text) == "서버 오류가 났습니다"


def _between(html: str, start: str, end: str) -> str:
    """start가 처음 나오는 곳부터 그 뒤 첫 end까지의 HTML."""
    begin = html.index(start)
    return html[begin : html.index(end, begin)]


def _nav(html: str) -> list[tuple[str, bool]]:
    """머리 메뉴의 (글, 현재 화면 여부)."""
    nav = _between(html, '<nav class="masthead__nav"', "</nav>")
    return [(a.text, a.attrs.get("aria-current") == "page") for a in all_by_tag(nav, "a")]


def _card(html: str) -> str:
    return _between(html, '<section class="panel error-card"', "</section>")


def _card_links(html: str) -> list[tuple[str, str]]:
    return [(a.text, str(a.attrs.get("href"))) for a in all_by_tag(_card(html), "a")]


def _title(html: str) -> str:
    [title] = by_class(_card(html), "error-card__title")
    return title.text


def _current(html: str) -> list[str]:
    return [text for text, current in _nav(html) if current]


def test_missing_task_page_has_masthead_and_links(client: TestClient) -> None:
    response = client.get("/tasks/99/edit")

    assert response.status_code == 404
    html = response.text
    assert [text for text, _ in _nav(html)] == ["대시보드", "기록", "태스크", "보고서", "설정"]
    assert _current(html) == ["태스크"]
    [alert] = [p for p in all_by_tag(_card(html), "p") if p.attrs.get("role") == "alert"]
    assert alert.text == "태스크를 찾을 수 없습니다: #99. 태스크 화면에서 확인하세요."
    assert _title(html) == "찾을 수 없습니다"
    assert _card_links(html) == [("태스크 화면으로", "/tasks"), ("대시보드로", "/")]
    assert [(h.text, h.attrs.get("class")) for h in all_by_tag(html, "h1")] == [
        ("오류", "visually-hidden")
    ]


@pytest.mark.parametrize(
    ("path", "current", "related"),
    [
        ("/logs/nope", ["기록"], [("기록 화면으로", "/logs")]),
        ("/report/nope", ["보고서"], [("보고서 화면으로", "/report")]),
        ("/settings/nope", ["설정"], [("설정 화면으로", "/settings")]),
        ("/nope", [], []),
    ],
)
def test_related_screen_follows_first_path_segment(
    client: TestClient, path: str, current: list[str], related: list[tuple[str, str]]
) -> None:
    html = client.get(path).text

    assert _current(html) == current
    assert _card_links(html) == [*related, ("대시보드로", "/")]


def test_error_page_has_no_week_or_inline_code(client: TestClient) -> None:
    html = client.get("/tasks/99/edit").text

    assert by_class(html, "masthead__week") == []  # DB 없이 그리므로 이번 주 표기는 뺀다
    assert "/colors.css" not in html  # 카테고리 색은 DB를 읽는다
    assert inline_code_violations(html) == []


def test_locked_database_page_has_same_masthead(locked_client: LockedApp) -> None:
    client, _engine, path = locked_client
    with hold_lock(path, "EXCLUSIVE"):
        response = client.get("/tasks")

    assert response.status_code == 503
    assert _current(response.text) == ["태스크"]
    assert "사용 중" in _card(response.text)
    assert _title(response.text) == "지금은 열 수 없습니다"
    assert _card_links(response.text) == [("태스크 화면으로", "/tasks"), ("대시보드로", "/")]


def test_htmx_and_api_errors_have_no_masthead(probe_client: TestClient) -> None:
    flash = probe_client.get("/raise/missing", headers={"HX-Request": "true"}).text
    api = probe_client.get("/api/raise/missing").text

    assert "masthead" not in flash
    assert "masthead" not in api


def test_falls_back_to_plain_page_when_rendering_fails(
    probe_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(path: str, status: int, message: str) -> str:
        raise RuntimeError("template")

    monkeypatch.setattr(errors, "_templated_error_page", broken)
    response = probe_client.get("/raise/missing")

    assert response.status_code == 404
    assert "masthead" not in response.text
    [alert] = [p for p in all_by_tag(response.text, "p") if p.attrs.get("role") == "alert"]
    assert alert.text == str(RAISED_ERRORS["missing"])
    assert [a.attrs["href"] for a in all_by_tag(response.text, "a")] == ["/"]
