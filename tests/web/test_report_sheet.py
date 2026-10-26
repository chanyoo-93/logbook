"""보고서 표 보기(#report-sheet)와 원문 탭 테스트 (오늘 = 2026-10-01, W40)."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core.report import TEMPLATE_NAME
from logbook.core.weeks import Week
from logbook.web.pages.report import category_totals
from tests.helpers import FIXED_NOW, FakeCollect
from tests.web.helpers import add_log, add_project, add_task, by_id, parse_html

W40 = Week(2026, 40)
W41 = Week(2026, 41)


def _seed(web_engine: Engine) -> int:
    add_project(web_engine, "payment", "결제")
    task_id = add_task(
        web_engine, title="환불 API", project="payment", category="dev", estimate=240
    )
    add_task(
        web_engine, title="정산 화면", project="payment", category="dev", week=W41, estimate=120
    )
    add_log(
        web_engine,
        minutes=90,
        note="환불",
        project="payment",
        day=FIXED_NOW.date(),
        task_id=task_id,
    )
    add_log(
        web_engine,
        minutes=30,
        note="회의",
        project="payment",
        category="meeting",
        day=FIXED_NOW.date(),
    )
    add_log(web_engine, minutes=45, note="문의", day=FIXED_NOW.date(), category="ops")
    return task_id


def _rows(html: str, table_id: str) -> list[list[str]]:
    """표의 행마다 셀 글자 목록(thead·tbody·tfoot 순서)."""
    marker = html.index(f'id="{table_id}"')
    chunk = html[marker : html.index("</table>", marker)]
    rows: list[list[str]] = []
    for element in parse_html("<table " + chunk + "</table>"):
        if element.tag == "tr":
            rows.append([])
        elif element.tag in ("th", "td") and rows:
            rows[-1].append(element.text)
    return rows


def test_sheet_is_the_default_view_with_tabs(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)

    html = client.get("/report").text

    tablist = by_id(html, "report-tabs")
    assert tablist.attrs.get("role") == "tablist"
    assert "hidden" in tablist.attrs  # JS가 켤 때 보인다
    sheet_tab = by_id(html, "tab-sheet")
    raw_tab = by_id(html, "tab-raw")
    assert (sheet_tab.text, sheet_tab.attrs.get("aria-selected")) == ("표 보기", "true")
    assert (raw_tab.text, raw_tab.attrs.get("aria-selected")) == ("원문", "false")
    assert sheet_tab.attrs.get("aria-controls") == "panel-sheet"
    assert raw_tab.attrs.get("aria-controls") == "panel-raw"
    assert by_id(html, "panel-sheet").attrs.get("role") == "tabpanel"
    assert by_id(html, "panel-raw").attrs.get("role") == "tabpanel"
    assert html.index('id="panel-sheet"') < html.index('id="panel-raw"')


def test_raw_panel_explains_markdown_and_falls_back_to_details(
    client: TestClient, web_engine: Engine
) -> None:
    _seed(web_engine)

    html = client.get("/report").text

    raw = html[html.index('id="panel-raw"') :]
    assert raw.index("<details") < raw.index('id="report-markdown"')
    assert "내려받기·lb report와 같은 Markdown입니다(보고서 템플릿 적용)." in raw
    assert "# 주간업무보고" in by_id(html, "report-markdown").text


def test_sheet_head_and_sections(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)

    html = client.get("/report").text

    sheet = by_id(html, "report-sheet")
    assert sheet.tag == "article"
    headings = [e.text for e in parse_html(html) if e.tag == "h4"]
    assert headings == [
        "1. 공수 요약",
        "2. 프로젝트별 실적",
        "3. 특이사항 / 리스크",
        "4. 다음 주 계획",
    ]
    assert "2026-W40" in by_id(html, "sheet-meta").text
    assert "2026-09-28 ~ 2026-10-04" in by_id(html, "sheet-meta").text


def test_hours_table_has_category_columns_rows_and_totals(
    client: TestClient, web_engine: Engine
) -> None:
    _seed(web_engine)

    rows = _rows(client.get("/report").text, "sheet-hours-table")

    head, *body, foot = rows
    assert head[0] == "프로젝트"
    assert head[-2:] == ["합계", "비율"]
    assert [row[0] for row in body] == ["payment", "common"]
    assert foot[0] == "합계"
    assert foot[-2:] == ["2h 45m", "100%"]
    categories = head[1:-2]
    by_category = dict(zip(categories, foot[1:-2], strict=True))
    assert by_category["개발"] == "1h 30m"


def test_category_totals_sum_cells_and_skip_dashes() -> None:
    assert category_totals((("1h 30m", "-"), ("30m", "2h"))) == ("2h", "2h")
    assert category_totals(()) == ()


def test_results_table_groups_tasks_under_project(client: TestClient, web_engine: Engine) -> None:
    task_id = _seed(web_engine)

    rows = _rows(client.get("/report").text, "sheet-results-table")

    assert rows[0] == ["프로젝트", "상태", "태스크", "실적", "예상"]
    payment = rows.index(["payment", "", "", "2h", ""])
    assert rows[payment + 1][2] == f"환불 API #{task_id}"
    assert rows[payment + 1][1] == "할 일"
    assert rows[payment + 1][4] == "4h"
    others = [row for row in rows if row[1] == "기타"]
    assert ["", "기타", "회의", "30m", ""] in others


def test_plan_table_groups_next_week_tasks(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)

    rows = _rows(client.get("/report").text, "sheet-plan-table")

    assert rows[0] == ["프로젝트", "태스크", "예상", "비고"]
    assert rows[1][0] == "payment"
    assert any(row[1].startswith("정산 화면 #") and row[2] == "2h" for row in rows)


def test_empty_sections_show_skipped_placeholders(client: TestClient) -> None:
    html = client.get("/report").text

    skipped = [e for e in parse_html(html) if "data-copy-skip" in e.attrs and e.tag == "p"]
    texts = [e.text for e in skipped]
    assert "기록이 없습니다." in texts
    assert "(작성하세요)" in texts
    assert "계획된 태스크가 없습니다." in texts
    assert all("sheet__empty" in str(e.attrs.get("class")).split() for e in skipped)


def test_saved_notes_appear_in_sheet(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)
    client.post(
        "/report/notes",
        data={"week": "2026-W40", "version": "", "notes": "배포 연기\n금요일", "risks": ""},
        headers={"HX-Request": "true"},
    )

    html = client.get("/report").text

    assert by_id(html, "sheet-notes-text").text == "배포 연기 금요일"
    assert "배포 연기\n금요일" in html  # 줄바꿈은 그대로 두고 CSS(pre-line)로 보인다
    assert (
        "(작성하세요)" not in html[html.index('id="report-sheet"') : html.index('id="panel-raw"')]
    )


def test_sheet_survives_broken_user_template(client: TestClient, tmp_home: Path) -> None:
    (tmp_home / TEMPLATE_NAME).write_text("a\n{% if %}\n", encoding="utf-8")

    html = client.get("/report").text

    assert by_id(html, "report-sheet").tag == "article"
    assert "보고서 템플릿을 읽지 못했습니다" in html[html.index('id="panel-raw"') :]


def _rich_copy_buttons(html: str) -> list[tuple[str, str, str, str]]:
    return [
        (
            str(e.attrs["data-copy-rich"]),
            e.text,
            str(e.attrs.get("aria-label")),
            str(e.attrs.get("data-copy-done")),
        )
        for e in parse_html(html)
        if "data-copy-rich" in e.attrs
    ]


def test_sheet_has_full_and_section_copy_buttons(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)

    html = client.get("/report").text

    assert _rich_copy_buttons(html) == [
        ("report-sheet", "전체 복사", "보고서 전체 복사", "보고서 전체를 복사했습니다."),
        ("sheet-hours", "복사", "공수 요약 복사", "공수 요약을 복사했습니다."),
        ("sheet-results", "복사", "프로젝트별 실적 복사", "프로젝트별 실적을 복사했습니다."),
        ("sheet-notes", "복사", "특이사항 / 리스크 복사", "특이사항 / 리스크를 복사했습니다."),
        ("sheet-plan", "복사", "다음 주 계획 복사", "다음 주 계획을 복사했습니다."),
    ]
    buttons = [e for e in parse_html(html) if "data-copy-rich" in e.attrs]
    for button in buttons:
        assert button.tag == "button"
        assert button.attrs.get("type") == "button"
        assert "data-copy-skip" in button.attrs  # 복사본에는 버튼이 들어가지 않는다
        assert by_id(html, str(button.attrs["data-copy-rich"]))


def test_commit_appendix_has_its_own_copy_button(
    git_client: TestClient, fake_collect: FakeCollect
) -> None:
    html = git_client.get("/report").text

    rows = _rows(html, "sheet-commits-table")
    assert ["payment (payment-server)", "", "", ""] in rows
    assert ("sheet-commits", "복사", "커밋 내역 복사", "커밋 내역을 복사했습니다.") in (
        _rich_copy_buttons(html)
    )
