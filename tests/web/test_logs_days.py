"""기록 화면 날짜 묶음(2026-10-30 결정 H1·H2): 날마다 tbody 하나, 머리글에 그날 합계와 목표 막대.

W40 = 09-28 ~ 10-04, 오늘 = 2026-10-01 목요일, 하루 목표는 기본값 8h.
"""

import json
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.web.helpers import Element, add_log, add_project, all_by_tag, by_class, by_id, parse_html

W40_MONDAY = date(2026, 9, 28)
W40_THURSDAY = date(2026, 10, 1)
HTMX = {"HX-Request": "true"}


def _days(html: str) -> list[Element]:
    return by_class(html, "log-day__head")


def _day_heads(html: str) -> list[Element]:
    """날짜 머리글 칸(th scope=rowgroup)."""
    return [th for th in all_by_tag(html, "th") if th.attrs.get("scope") == "rowgroup"]


def _fill(html: str) -> list[str]:
    """머리글 막대의 채움 폭(문서 순서)."""
    return [str(e.attrs.get("width")) for e in by_class(html, "progress__fill")]


def _seed(engine: Engine) -> dict[str, int]:
    """월요일 2건(6h 30m), 목요일 2건(8h 30m, 목표 넘음). 입력은 날짜 역순."""
    add_project(engine, "payment", "결제 서버")
    return {
        "thu_a": add_log(engine, minutes=300, note="목 가", project="payment", day=W40_THURSDAY),
        "thu_b": add_log(engine, minutes=210, note="목 나", day=W40_THURSDAY),
        "mon_a": add_log(engine, minutes=240, note="월 가", project="payment", day=W40_MONDAY),
        "mon_b": add_log(engine, minutes=150, note="월 나", category="meeting", day=W40_MONDAY),
    }


def test_rows_are_grouped_by_day_with_total_and_target(
    client: TestClient, web_engine: Engine
) -> None:
    ids = _seed(web_engine)

    html = client.get("/logs").text

    bodies = [b for b in all_by_tag(html, "tbody") if "log-day" in str(b.attrs.get("class"))]
    assert len(bodies) == 2
    assert [th.text for th in _day_heads(html)] == [
        "09-28 (월) 6h 30m / 8h",
        "10-01 (목) 8h 30m / 8h",
    ]
    assert [th.attrs.get("colspan") for th in _day_heads(html)] == ["7", "7"]
    assert _fill(html) == ["81", "100"]
    bars = [e for e in parse_html(html) if e.tag == "svg" and "progress" in str(e.attrs["class"])]
    assert [("progress--done" in str(b.attrs["class"])) for b in bars] == [False, True]
    assert all(b.attrs.get("aria-hidden") == "true" for b in bars)
    # 날짜 순서와 같은 날 안의 순서는 그대로(날짜 → ID 오름차순)
    order = [str(e.attrs["id"]) for e in parse_html(html) if e.tag == "tr" and e.attrs.get("id")]
    assert order == [f"log-{ids[k]}" for k in ("mon_a", "mon_b", "thu_a", "thu_b")]


def test_grouped_rows_have_no_date_cell(client: TestClient, web_engine: Engine) -> None:
    log_id = add_log(web_engine, minutes=30, note="한 건", day=W40_THURSDAY)

    html = client.get("/logs").text

    row_html = html[html.index(f'<tr id="log-{log_id}"') :]
    row_html = row_html[: row_html.index("</tr>")]
    cells = all_by_tag(row_html, "td")
    assert len(cells) == 7
    assert not [td.text for td in cells if td.text.startswith("10-01")]  # 날짜는 머리글이 맡는다
    headers = [e.text for e in all_by_tag(html, "th") if e.attrs.get("scope") == "col"]
    assert headers == ["ID", "프로젝트", "카테고리", "시간", "메모", "태스크", "동작"]
    assert by_id(html, "log-total").attrs.get("colspan") == "7"


def test_filtered_day_shows_total_only(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)

    for query, heads in (
        ("?project=payment", ["09-28 (월) 4h", "10-01 (목) 5h"]),
        ("?category=meeting", ["09-28 (월) 2h 30m"]),
    ):
        html = client.get(f"/logs{query}").text

        assert [th.text for th in _day_heads(html)] == heads, query
        assert by_class(html, "progress") == [], query
        assert by_class(html, "log-day__target") == [], query


def test_week_total_and_empty_state_stay(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)

    assert by_id(client.get("/logs").text, "log-total").text == "합계 15h / 기록 4건"
    empty = client.get("/logs?week=2026-W39").text
    assert _days(empty) == []
    assert "이 주에는 기록이 없습니다." in by_class(empty, "empty")[0].text


def test_edit_row_keeps_date_input_within_seven_cells(
    client: TestClient, web_engine: Engine
) -> None:
    log_id = add_log(web_engine, minutes=30, note="편집", day=W40_THURSDAY)

    html = client.get(f"/logs/{log_id}/edit").text

    assert len(all_by_tag(html, "td")) == 7
    first_cell = html[html.index("<td") : html.index("</td>")]  # 첫 칸(ID)
    assert 'name="log_date"' in first_cell
    assert all_by_tag(html, "td")[0].text == str(log_id)


def test_moving_a_log_to_another_day_redraws_both_totals(
    client: TestClient, web_engine: Engine
) -> None:
    ids = _seed(web_engine)
    page = client.get(f"/logs/{ids['thu_b']}/edit").text
    version = str(
        next(e for e in parse_html(page) if e.attrs.get("name") == "version").attrs["value"]
    )

    response = client.patch(
        f"/logs/{ids['thu_b']}",
        data={
            "duration": "3h 30m",
            "note": "목 나",
            "log_date": W40_MONDAY.isoformat(),
            "log_project": "common",
            "log_category": "dev",
            "log_task": "",
            "version": version,
            "week": "",
            "project": "",
            "category": "",
        },
        headers=HTMX,
    )

    assert response.status_code == 200
    assert [th.text for th in _day_heads(response.text)] == [
        "09-28 (월) 10h / 8h",
        "10-01 (목) 5h / 8h",
    ]


def test_deleting_the_last_log_of_a_day_removes_its_head(
    client: TestClient, web_engine: Engine
) -> None:
    ids = _seed(web_engine)
    for key in ("mon_a", "mon_b"):
        page = client.get("/logs").text
        version = next(
            str(e.attrs["hx-vals"])
            for e in parse_html(page)
            if e.attrs.get("hx-delete") == f"/logs/{ids[key]}"
        )
        response = client.delete(
            f"/logs/{ids[key]}", params={"version": json.loads(version)["version"]}, headers=HTMX
        )
        assert response.status_code == 200

    assert [th.text for th in _day_heads(response.text)] == ["10-01 (목) 8h 30m / 8h"]
