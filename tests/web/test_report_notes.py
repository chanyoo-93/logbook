"""POST /report/notes 테스트 (오늘 = 2026-10-01, W40)."""

import httpx2
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.weeks import parse_week
from logbook.web.pages.panels import NO_CHANGE
from logbook.web.pages.report import NOTES_SAVED
from tests.helpers import FIXED_NOW, FakeCollect
from tests.web.helpers import by_id, inline_code_violations, parse_html

HTMX = {"HX-Request": "true"}
WEEK = parse_week("2026-W40", today=FIXED_NOW.date(), week_start="monday")


def _post(client: TestClient, **fields: str) -> httpx2.Response:
    data = {"week": "2026-W40", "notes": "", "risks": "", "version": "", **fields}
    return client.post("/report/notes", data=data, headers=HTMX)


def _stored(engine: Engine) -> tuple[str, str] | None:
    with db.session_scope(engine) as s:
        note = services.get_week_note(s, WEEK)
        return None if note is None else (note.notes, note.risks)


def _version(html: str) -> str:
    values = [
        e.attrs.get("value")
        for e in parse_html(html)
        if e.tag == "input" and e.attrs.get("name") == "version"
    ]
    assert len(values) == 1
    return str(values[0])


def test_save_notes_updates_preview_and_db(client: TestClient, web_engine: Engine) -> None:
    response = _post(client, notes="일정 지연", risks="인력 부족")

    html = response.text
    assert response.status_code == 200
    assert "### 특이사항" in by_id(html, "report-markdown").text
    assert NOTES_SAVED.format(week="2026-W40") in html
    assert by_id(html, "report-body").tag == "section"
    assert _stored(web_engine) == ("일정 지연", "인력 부족")
    assert inline_code_violations(html) == []


def test_save_normalizes_crlf(client: TestClient, web_engine: Engine) -> None:
    _post(client, notes="a\r\nb")

    assert _stored(web_engine) == ("a\nb", "")


def test_save_blank_deletes_row(client: TestClient, web_engine: Engine) -> None:
    with db.session_scope(web_engine) as s:
        services.save_week_note(s, WEEK, notes="x", risks="")
    version = _version(client.get("/report").text)

    response = _post(client, version=version)

    assert _stored(web_engine) is None
    assert "(작성하세요)" in by_id(response.text, "report-markdown").text


def test_save_same_values_again_says_no_change(client: TestClient) -> None:
    first = _post(client, notes="내용")
    version = _version(first.text)

    second = _post(client, notes="내용", version=version)

    assert NO_CHANGE in second.text
    assert NOTES_SAVED.format(week="2026-W40") not in second.text


def test_changing_saved_notes_says_saved(client: TestClient, web_engine: Engine) -> None:
    first = _post(client, notes="처음 내용")

    second = _post(client, notes="고친 내용", version=_version(first.text))

    assert NOTES_SAVED.format(week="2026-W40") in second.text
    assert NO_CHANGE not in second.text
    assert _stored(web_engine) == ("고친 내용", "")


def test_save_with_stale_version_is_conflict(client: TestClient, web_engine: Engine) -> None:
    with db.session_scope(web_engine) as s:
        services.save_week_note(s, WEEK, notes="다른 탭", risks="")

    response = _post(client, notes="내 입력", risks="내 위험", version="")

    html = response.text
    assert response.status_code == 409
    assert response.headers["hx-retarget"] == "#report-body"
    assert response.headers["hx-push-url"] == "false"
    assert "다른 곳에서 특이사항이 바뀌었습니다: 2026-W40" in html
    assert by_id(html, "report-notes-text").text == "내 입력"
    assert by_id(html, "report-risks-text").text == "내 위험"
    assert "다른 탭" in by_id(html, "report-markdown").text
    # 입력값은 저장되지 않았으므로 안내가 찬 채로 그린다(report.js도 이 표시를 본다)
    assert "data-unsaved" in by_id(html, "report-notes").attrs
    assert by_id(html, "report-notes-dirty").text.startswith("저장하지 않은 내용이 있습니다.")
    current = _version(html)
    assert current != ""
    assert _stored(web_engine) == ("다른 탭", "")
    # 지금 버전으로 다시 저장하면 입력한 내용으로 바뀐다.
    _post(client, notes="내 입력", risks="내 위험", version=current)
    assert _stored(web_engine) == ("내 입력", "내 위험")


def test_save_rejects_bad_week_keeping_input(client: TestClient) -> None:
    response = _post(client, week="abc", notes="남겨 둘 값")

    html = response.text
    assert response.status_code == 400
    assert "주차" in html
    assert by_id(html, "report-notes-text").text == "남겨 둘 값"


def _focus_ids(html: str) -> list[str]:
    return [str(e.attrs.get("id")) for e in parse_html(html) if "data-focus" in e.attrs]


def _inside(html: str, element_id: str, container_id: str) -> bool:
    """element_id가 container_id 요소 안(여는 태그부터 닫는 태그 전)에 있는지."""
    start = html.index(f'id="{container_id}"')
    tag = html.rindex("<", 0, start) + 1
    name = html[tag : html.index(" ", tag)]
    end = html.index(f"</{name}>", start)
    return start < html.index(f'id="{element_id}"') < end


def test_saved_result_shows_in_sheet_section_with_focus(client: TestClient) -> None:
    html = _post(client, notes="일정 지연").text

    result = by_id(html, "sheet-notes-result")
    assert result.text == NOTES_SAVED.format(week="2026-W40")
    assert result.attrs.get("role") == "status"
    assert "data-copy-skip" in result.attrs  # 복사본에는 결과 줄이 들어가지 않는다
    assert _inside(html, "sheet-notes-result", "sheet-notes")
    assert 'id="report-notes-result"' not in html
    assert _focus_ids(html) == ["sheet-notes-title"]
    assert by_id(html, "sheet-notes-title").attrs.get("tabindex") == "-1"


def test_no_change_result_also_shows_in_sheet_section(client: TestClient) -> None:
    first = _post(client, notes="내용")

    html = _post(client, notes="내용", version=_version(first.text)).text

    assert by_id(html, "sheet-notes-result").text == NO_CHANGE
    assert _focus_ids(html) == ["sheet-notes-title"]


def test_conflict_result_stays_in_form(client: TestClient, web_engine: Engine) -> None:
    with db.session_scope(web_engine) as s:
        services.save_week_note(s, WEEK, notes="다른 탭", risks="")

    html = _post(client, notes="내 입력", version="").text

    assert by_id(html, "report-notes-result").attrs.get("role") == "alert"
    assert _inside(html, "report-notes-result", "report-notes")
    assert 'id="sheet-notes-result"' not in html
    assert _focus_ids(html) == ["report-notes-title"]


def test_bad_week_result_stays_in_form(client: TestClient) -> None:
    html = _post(client, week="abc", notes="값").text

    assert by_id(html, "report-notes-result").attrs.get("role") == "alert"
    assert 'id="sheet-notes-result"' not in html
    assert _focus_ids(html) == ["report-notes-title"]


def test_page_and_week_move_have_no_sheet_result(client: TestClient) -> None:
    _post(client, notes="내용")

    page = client.get("/report").text
    moved = client.get("/report?week=2026-W39", headers=HTMX).text

    for html in (page, moved):
        assert 'id="sheet-notes-result"' not in html
        assert 'id="report-notes-result"' not in html
        assert "sheet-notes-title" not in _focus_ids(html)


def test_cross_origin_post_is_forbidden(client: TestClient, web_engine: Engine) -> None:
    response = client.post(
        "/report/notes",
        data={"week": "2026-W40", "notes": "x", "risks": "", "version": ""},
        headers={"Origin": "http://evil.example"},
    )

    assert response.status_code == 403
    assert _stored(web_engine) is None


def test_save_response_keeps_commit_appendix_and_warnings(git_client: TestClient) -> None:
    html = _post(git_client, notes="일정 지연").text

    assert "## 부록. 커밋 내역" in by_id(html, "report-markdown").text
    assert "커밋을 모으지 못했습니다: admin (git 실패)" in html


def test_conflict_response_keeps_commit_appendix_and_warnings(
    git_client: TestClient, web_engine: Engine
) -> None:
    with db.session_scope(web_engine) as s:
        services.save_week_note(s, WEEK, notes="다른 탭", risks="")

    response = _post(git_client, notes="내 입력", version="")

    assert response.status_code == 409
    assert "## 부록. 커밋 내역" in by_id(response.text, "report-markdown").text
    assert "커밋을 모으지 못했습니다: admin (git 실패)" in response.text


def test_bad_week_response_does_not_collect_commits(
    git_client: TestClient, fake_collect: FakeCollect
) -> None:
    response = _post(git_client, week="abc")

    assert response.status_code == 400
    assert fake_collect.calls == []


def test_successful_save_clears_unsaved_mark(client: TestClient) -> None:
    html = _post(client, notes="내용").text

    assert "data-unsaved" not in by_id(html, "report-notes").attrs
    assert by_id(html, "report-notes-dirty").text == ""
    assert by_id(html, "report-sheet").tag == "article"
