"""좁은 폭 기록 표(2026-11-05 결정 N1): 720px 미만에서 행을 두 줄로 쌓아 메모를 둘째 줄에 둔다.

행을 CSS grid로 바꾸면 일부 브라우저가 표 의미를 버리므로, 표 요소에 role을 명시한다.
실제 폭은 브라우저로 재고, 여기서는 role·칸 이름표·CSS 규칙이 남아 있는지 확인한다.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.web.helpers import Element, add_log, all_by_tag, by_id, parse_html
from tests.web.test_css_layout import NARROW_QUERY, _declarations, _media_block, _read

W40_THURSDAY = date(2026, 10, 1)

TABLE_ROLES = {
    "table": "table",
    "thead": "rowgroup",
    "tbody": "rowgroup",
    "tfoot": "rowgroup",
    "tr": "row",
    "td": "cell",
}


def _inside(html: str, element_id: str) -> list[Element]:
    """id 요소의 바깥 HTML(같은 태그 짝을 세어 자른다)을 파싱한 요소들."""
    start = html.index(f'id="{element_id}"')
    start = html.rindex("<", 0, start)
    tag = html[start + 1 : html.index(" ", start)]
    depth = 0
    position = start
    while True:
        next_open = html.find(f"<{tag}", position + 1)
        next_close = html.find(f"</{tag}>", position + 1)
        if next_open != -1 and next_open < next_close:
            depth += 1
            position = next_open
            continue
        if depth == 0:
            return parse_html(html[start : next_close + len(tag) + 3])
        depth -= 1
        position = next_close


def _assert_table_roles(elements: list[Element]) -> None:
    for element in elements:
        expected = TABLE_ROLES.get(element.tag)
        if element.tag == "th":
            expected = "columnheader" if element.attrs.get("scope") == "col" else "rowheader"
        if expected is not None:
            assert element.attrs.get("role") == expected, (element.tag, element.attrs)


def _cell_classes(row: Element, elements: list[Element]) -> list[str]:
    start = elements.index(row)
    cells: list[str] = []
    for element in elements[start + 1 :]:
        if element.tag == "tr":
            break
        if element.tag == "td":
            cells.append(str(element.attrs.get("class") or ""))
    return cells


def _seed(engine: Engine) -> int:
    return add_log(engine, minutes=90, note="결제 승인 오류 코드 정리", day=W40_THURSDAY)


def test_recent_table_keeps_table_roles_and_names_each_cell(
    client: TestClient, web_engine: Engine
) -> None:
    _seed(web_engine)

    elements = _inside(client.get("/").text, "recent")

    table = next(e for e in elements if e.tag == "table")
    assert "grid--recent" in str(table.attrs.get("class"))
    _assert_table_roles(elements)
    row = next(e for e in elements if e.tag == "tr" and e.attrs.get("id", "").startswith("log-"))
    names = [cell.split()[0] if cell else "" for cell in _cell_classes(row, elements)]
    assert names == [
        "grid__id",
        "grid__day",
        "grid__mark",
        "grid__time",
        "grid__note",
        "grid__task",
    ]


def test_record_table_keeps_table_roles_and_names_each_cell(
    client: TestClient, web_engine: Engine
) -> None:
    log_id = _seed(web_engine)

    elements = _inside(client.get("/logs?week=2026-W40").text, "log-table")

    _assert_table_roles(elements)
    row = next(e for e in elements if e.tag == "tr" and e.attrs.get("id") == f"log-{log_id}")
    classes = _cell_classes(row, elements)
    for name, cell in zip(
        (
            "grid__id",
            "grid__project",
            "grid__category",
            "grid__time",
            "grid__note",
            "grid__task",
            "grid__menu-cell",
        ),
        classes,
        strict=True,
    ):
        assert name in cell.split()


def test_edit_row_keeps_row_and_cell_roles_and_names_each_cell(
    client: TestClient, web_engine: Engine
) -> None:
    log_id = _seed(web_engine)

    html = client.get(f"/logs/{log_id}/edit").text

    elements = parse_html(html)
    _assert_table_roles(elements)
    row = all_by_tag(html, "tr")[0]
    assert row.attrs.get("role") == "row"
    classes = _cell_classes(row, elements)
    for name, cell in zip(
        (
            "grid__id",
            "grid__project",
            "grid__category",
            "grid__time",
            "grid__note",
            "grid__task",
            "grid__actions",
        ),
        classes,
        strict=True,
    ):
        assert name in cell.split()


def test_recent_and_record_tables_still_render_their_row(
    client: TestClient, web_engine: Engine
) -> None:
    log_id = _seed(web_engine)

    assert "결제 승인 오류 코드 정리" in by_id(client.get("/").text, "recent").text
    assert by_id(client.get("/logs?week=2026-W40").text, f"log-{log_id}").tag == "tr"


def _narrow() -> str:
    return _media_block(_read("responsive.css"), NARROW_QUERY)


@pytest.mark.parametrize(
    ("selector", "areas"),
    [
        (".grid--recent tbody tr", '"id day mark time" "note note note task"'),
        (
            ".grid--records tbody tr:not(.log-day__head, .is-editing)",
            '"id project project time menu" ". category category task task" '
            '"note note note note note"',
        ),
    ],
)
def test_record_rows_stack_into_two_lines_on_narrow_screens(selector: str, areas: str) -> None:
    declarations = _declarations(_narrow(), selector)

    assert "display: grid" in declarations
    assert f"grid-template-areas: {areas}" in declarations


@pytest.mark.parametrize(
    "selector",
    [".grid--recent tbody tr", ".grid--records tbody tr:not(.log-day__head, .is-editing)"],
)
def test_id_column_keeps_a_minimum_width_so_rows_line_up(selector: str) -> None:
    # 행마다 grid라 ID 자릿수(9 → 10)가 바뀌면 뒤 칸 시작 위치가 어긋난다. 999까지는 맞춘다.
    columns = next(
        d for d in _declarations(_narrow(), selector) if d.startswith("grid-template-columns: ")
    )

    assert columns.startswith("grid-template-columns: minmax(3ch, auto) ")


def test_note_takes_the_second_line_and_may_shrink_on_narrow_screens() -> None:
    declarations = _declarations(_narrow(), ".grid--logs .grid__note")

    assert "grid-area: note" in declarations
    assert "min-width: 0" in declarations


def test_record_tables_stop_being_table_boxes_on_narrow_screens() -> None:
    narrow = _narrow()

    assert "display: block" in _declarations(
        narrow, ".grid--logs, .grid--logs tbody, .grid--logs tfoot"
    )
    cells = _declarations(narrow, ".grid--logs td, .grid--logs th")
    assert "display: block" in cells
    assert "height: auto" in cells


def test_edit_row_folds_fields_into_two_columns_on_narrow_screens() -> None:
    declarations = _declarations(_narrow(), ".grid--records .is-editing")

    assert "display: grid" in declarations
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in declarations
    wide = _declarations(
        _narrow(),
        ".grid--records .is-editing .grid__id, .grid--records .is-editing .grid__note, "
        ".grid--records .is-editing .grid__actions",
    )
    assert "grid-column: 1 / -1" in wide


def test_recent_column_heads_hide_visually_on_narrow_screens() -> None:
    declarations = _declarations(_narrow(), ".grid--recent thead")

    assert "position: absolute" in declarations
    assert "clip-path: inset(50%)" in declarations


def test_first_and_last_cells_drop_wide_screen_side_padding_on_narrow_screens() -> None:
    # 넓은 화면의 첫·끝 칸 여백(.grid--logs td:first-child, 명시도 0,2,1)이 남으면
    # 행 안쪽 여백과 겹쳐 ID는 두 배로 들여 쓰이고 끝 칸은 시간 칸과 오른쪽이 어긋난다.
    declarations = _declarations(
        _narrow(), ".grid--logs tbody td:first-child, .grid--logs tbody td:last-child"
    )

    assert "padding-inline: 0" in declarations


def test_day_head_keeps_its_strong_rule_on_narrow_screens() -> None:
    declarations = _declarations(_narrow(), ".grid--logs tbody tr.log-day__head")

    assert "border-bottom-color: var(--rule-strong)" in declarations


# 넘치는 표 상자 가장자리 그림자(2026-11-05 결정 N2). JS 없이 배경 네 겹:
# 가림막 둘은 내용과 함께 움직이고(local), 그림자 둘은 상자 가장자리에 붙어 있다(scroll).
SCROLL_BOXES = ".table-wrap, .sheet__scroll"


def test_scroll_boxes_show_edge_shadows_where_content_is_hidden() -> None:
    declarations = _declarations(_read("components.css"), SCROLL_BOXES)

    assert "background-attachment: local, local, scroll, scroll" in declarations
    image = next(d for d in declarations if d.startswith("background-image: "))
    assert image.count("var(--surface)") == 2
    assert image.count("var(--scroll-shadow)") == 2


@pytest.mark.parametrize("dark", [False, True])
def test_scroll_shadow_token_is_set_for_both_themes(dark: bool) -> None:
    css = _read("app.css")
    if dark:
        css = _media_block(css, "@media screen and (prefers-color-scheme: dark)")

    assert any(d.startswith("--scroll-shadow: ") for d in _declarations(css, ":root"))


def test_print_drops_the_edge_shadows() -> None:
    printed = _media_block(_read("responsive.css"), "@media print")

    assert "background: none" in _declarations(printed, SCROLL_BOXES)
