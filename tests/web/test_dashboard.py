"""대시보드 GET / 테스트 (W40 = 09-28 ~ 10-04, 오늘 = 2026-10-01 목요일 09:30 +09:00)."""

import dataclasses
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.taskstatus import TaskStatus
from logbook.web.app import create_app
from logbook.web.context import WebContext
from tests.helpers import Clock, hold_lock
from tests.web.conftest import LOCAL_BASE_URL, LockedApp
from tests.web.helpers import (
    Element,
    add_log,
    add_project,
    add_task,
    all_by_tag,
    by_id,
    inline_code_violations,
    json_attr,
)

W40_MONDAY = date(2026, 9, 28)
W40_WEDNESDAY = date(2026, 9, 30)
W40_THURSDAY = date(2026, 10, 1)
W39_THURSDAY = date(2026, 9, 24)
INDIGO = "#4f46e5"
PALETTE_BLUE = "#2f6fde"
PALETTE_ORANGE = "#e8590c"
PALETTE_GREEN = "#2b8a3e"

EXPECTED_CHART = {
    "daily": {
        "labels": [
            "09-28 (월)",
            "09-29 (화)",
            "09-30 (수)",
            "10-01 (목)",
            "10-02 (금)",
            "10-03 (토)",
            "10-04 (일)",
        ],
        "target": 480,
        "totals": [60, 0, 30, 120, 0, 0, 0],
        "datasets": [
            {"label": "payment", "color": INDIGO, "data": [60, 0, 0, 120, 0, 0, 0]},
            {"label": "common", "color": PALETTE_ORANGE, "data": [0, 0, 30, 0, 0, 0, 0]},
        ],
    },
    "projects": {
        "labels": ["payment", "common"],
        "colors": [INDIGO, PALETTE_ORANGE],
        "data": [180, 30],
    },
    "categories": {
        "labels": ["개발", "회의"],
        "colors": [PALETTE_BLUE, PALETTE_GREEN],
        "data": [180, 30],
    },
}


def _seed_week(engine: Engine) -> None:
    add_project(engine, "payment", "결제", color=INDIGO)
    add_log(engine, minutes=60, note="설계", project="payment", day=W40_MONDAY)
    add_log(engine, minutes=120, note="구현", project="payment", day=W40_THURSDAY)
    add_log(engine, minutes=30, note="주간 회의", category="meeting", day=W40_WEDNESDAY)
    add_log(engine, minutes=45, note="지난주 작업", day=W39_THURSDAY)
    add_task(
        engine,
        title="끝낸 태스크",
        status=TaskStatus.DONE,
        done_at=datetime(2026, 9, 30, 3, 0, tzinfo=UTC),
    )


def _get(client: TestClient, path: str = "/") -> str:
    response = client.get(path)
    assert response.status_code == 200
    return response.text


def test_dashboard_is_a_korean_html_page(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert '<html lang="ko">' in response.text
    assert [e.text for e in all_by_tag(response.text, "title")] == ["대시보드 · logbook"]


def test_dashboard_marks_current_nav_link(client: TestClient) -> None:
    html = _get(client)

    links: dict[str, Element] = {}
    for link in all_by_tag(html, "a"):
        href = link.attrs.get("href")
        if href in {"/", "/logs"}:
            links.setdefault(str(href), link)  # 머리의 탐색 링크가 먼저 나온다
    assert links["/"].attrs.get("aria-current") == "page"
    assert links["/"].text == "대시보드"
    assert links["/logs"].text == "기록"
    assert "aria-current" not in links["/logs"].attrs


def test_dashboard_header_shows_this_week(client: TestClient) -> None:
    html = _get(client)

    assert "2026-W40 (09-28 ~ 10-04)" in all_by_tag(html, "header")[0].text


def test_dashboard_page_skeleton(client: TestClient) -> None:
    html = _get(client)

    main = by_id(html, "main")
    assert main.tag == "main"
    assert main.attrs.get("tabindex") == "-1"  # skip link의 이동 대상이 포커스를 받는다
    flash = by_id(html, "flash")
    assert flash.attrs["role"] == "status"
    assert flash.attrs["aria-live"] == "polite"
    assert [by_id(html, name).tag for name in ("quick-form", "summary", "timer", "recent")] == [
        "form",
        "section",
        "section",
        "section",
    ]


def test_dashboard_sections_are_in_reading_order(client: TestClient) -> None:
    html = _get(client)

    positions = [
        html.index(f'id="{name}"') for name in ("quick-form", "summary", "timer", "recent")
    ]
    assert positions == sorted(positions)


def test_summary_numbers(client: TestClient, web_engine: Engine) -> None:
    _seed_week(web_engine)

    summary = by_id(_get(client), "summary").text

    assert "3h 30m" in summary
    assert "기록 3건" in summary
    assert "완료 태스크 1건" in summary


def test_summary_chart_data(client: TestClient, web_engine: Engine) -> None:
    _seed_week(web_engine)

    assert json_attr(_get(client), "summary", "data-chart") == EXPECTED_CHART


def test_summary_has_three_labelled_canvases_with_table_alternatives(
    client: TestClient, web_engine: Engine
) -> None:
    _seed_week(web_engine)
    html = _get(client)

    canvases = all_by_tag(html, "canvas")
    assert [c.attrs["id"] for c in canvases] == [
        "chart-daily",
        "chart-projects",
        "chart-categories",
    ]
    assert all(c.attrs["role"] == "img" and c.attrs.get("aria-label") for c in canvases)
    assert [e.text for e in all_by_tag(html, "summary")] == ["표로 보기"] * 3
    assert len(all_by_tag(html, "details")) == 3


def test_summary_tables_repeat_the_chart_values(client: TestClient, web_engine: Engine) -> None:
    _seed_week(web_engine)

    summary = by_id(_get(client), "summary").text

    for expected in ("09-28 (월)", "payment", "common", "개발", "회의", "1h", "2h", "30m", "3h"):
        assert expected in summary


def test_summary_without_logs_shows_empty_message(client: TestClient, web_engine: Engine) -> None:
    add_log(web_engine, minutes=45, note="지난주 작업", day=W39_THURSDAY)

    html = _get(client)

    assert "이번 주 기록이 없습니다." in by_id(html, "summary").text
    assert all_by_tag(html, "canvas") == []
    assert "0m" in by_id(html, "summary").text


def test_recent_logs_are_newest_first_and_limited(client: TestClient, web_engine: Engine) -> None:
    ids = [
        add_log(web_engine, minutes=10, note=f"기록 {n}", day=W40_THURSDAY) for n in range(1, 13)
    ]

    rows = [
        e.attrs["id"]
        for e in all_by_tag(_get(client), "tr")
        if str(e.attrs.get("id")).startswith("log-")
    ]

    assert rows == [f"log-{log_id}" for log_id in reversed(ids[-10:])]


def test_recent_logs_table_columns_and_cells(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")
    task_id = add_task(web_engine, title="태스크", project="payment")
    log_id = add_log(
        web_engine,
        minutes=90,
        note="재시도 로직",
        project="payment",
        day=W40_THURSDAY,
        task_id=task_id,
    )

    html = _get(client)

    recent = by_id(html, "recent").text
    assert "최근 기록" in recent
    for header in ("ID", "날짜", "프로젝트/카테고리", "시간", "메모", "태스크"):
        assert header in recent
    row = next(e for e in all_by_tag(html, "tr") if e.attrs.get("id") == f"log-{log_id}")
    assert row.text == f"{log_id} 10-01 (목) payment/dev 1h 30m 재시도 로직 #{task_id}"


def test_recent_logs_without_task_show_dash(client: TestClient, web_engine: Engine) -> None:
    log_id = add_log(web_engine, minutes=30, note="메모", day=W40_THURSDAY)

    row = next(e for e in all_by_tag(_get(client), "tr") if e.attrs.get("id") == f"log-{log_id}")

    assert row.text.endswith("메모 -")


def test_recent_logs_empty_message(client: TestClient) -> None:
    assert "기록이 없습니다." in by_id(_get(client), "recent").text


def test_timer_idle_message(client: TestClient) -> None:
    timer = by_id(_get(client), "timer").text

    assert "진행 중인 타이머가 없습니다. 터미널에서 lb start로 시작하세요." in timer


def test_timer_running(client: TestClient, web_engine: Engine, clock: Clock) -> None:
    add_project(web_engine, "payment", "결제")
    task_id = add_task(web_engine, title="환불", project="payment")
    with db.session_scope(web_engine) as s:
        services.start_timer(
            s,
            now=clock.now,
            note="환불 API 설계",
            project_slug="payment",
            category="design",
            task_id=task_id,
        )
    clock.advance(minutes=85)

    timer = by_id(_get(client), "timer").text

    assert "진행 중 " in f"{timer} "
    assert f"payment/design — 환불 API 설계 [#{task_id}]" in timer
    assert "시작 09:30 · 경과 1h 25m" in timer
    assert "진행 중인 타이머가 없습니다" not in timer


def test_dashboard_escapes_user_text(client: TestClient, web_engine: Engine, clock: Clock) -> None:
    add_log(web_engine, minutes=10, note="<script>alert(1)</script>", day=W40_THURSDAY)
    with db.session_scope(web_engine) as s:
        services.start_timer(s, now=clock.now, note="<img src=x onerror=alert(2)>", category="dev")

    html = _get(client)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img" not in html
    assert "&lt;img src=x onerror=alert(2)&gt;" in html


def test_dashboard_escapes_category_labels_in_chart_attribute_and_tables(
    web_ctx: WebContext, web_engine: Engine
) -> None:
    label = "a\"b'c<d>&e"
    cfg = dataclasses.replace(web_ctx.cfg, categories={"dev": label})
    ctx = dataclasses.replace(web_ctx, cfg=cfg)
    add_log(web_engine, minutes=10, note="n", day=W40_THURSDAY)

    with TestClient(create_app(ctx), base_url=LOCAL_BASE_URL) as client:
        html = _get(client)

    assert "<d>" not in html
    chart = json_attr(html, "summary", "data-chart")
    assert isinstance(chart, dict)
    assert chart["categories"]["labels"] == [label]
    assert "a&#34;b&#39;c&lt;d&gt;&amp;e" in html


def test_dashboard_has_no_inline_code(client: TestClient, web_engine: Engine, clock: Clock) -> None:
    _seed_week(web_engine)
    with db.session_scope(web_engine) as s:
        services.start_timer(s, now=clock.now, note="진행 중인 작업", category="dev")
    html = _get(client)

    scripts = all_by_tag(html, "script")
    assert scripts
    assert all(script.attrs.get("src") for script in scripts)
    assert all(script.text == "" for script in scripts)
    assert inline_code_violations(html) == []


def test_inline_code_check_ignores_note_text(client: TestClient, web_engine: Engine) -> None:
    note = 'x onclick=alert(1) style="a" hx-on:click=y javascript:z'
    add_log(web_engine, minutes=10, note=note, day=W40_THURSDAY)
    html = _get(client)

    assert "onclick=alert(1)" in html  # 메모 본문이 화면에 있어도
    assert inline_code_violations(html) == []  # 태그 속성만 보므로 오탐하지 않는다


def test_inline_code_violations_finds_tag_attributes() -> None:
    markup = (
        '<p style="a" onclick="x" hx-on:click="y"></p>'
        '<a href="javascript:1">l</a><script>1</script>'
    )

    assert inline_code_violations(markup) == [
        "<p style>",
        "<p onclick>",
        "<p hx-on:click>",
        "<a href=javascript:>",
        "<script> without src",
    ]


def test_dashboard_loads_local_deferred_scripts_in_order(client: TestClient) -> None:
    html = _get(client)

    scripts = all_by_tag(html, "script")
    assert [s.attrs["src"] for s in scripts] == [
        "/static/vendor/htmx-2.0.11.min.js",
        "/static/js/app.js",
        "/static/vendor/chart-4.5.1.umd.min.js",
        "/static/js/dashboard.js",
    ]
    assert all("defer" in s.attrs for s in scripts)


def test_dashboard_references_only_local_assets(client: TestClient) -> None:
    html = _get(client)

    urls = [
        e.attrs.get(name)
        for e in all_by_tag(html, "link") + all_by_tag(html, "script")
        for name in ("href", "src")
        if e.attrs.get(name)
    ]
    assert urls
    assert all(str(url).startswith("/static/") for url in urls)
    assert "https://" not in html and "http://" not in html


def test_dashboard_uses_current_week_for_sunday_start(
    web_ctx: WebContext, web_engine: Engine
) -> None:
    cfg = dataclasses.replace(web_ctx.cfg, week_start="sunday")
    ctx = dataclasses.replace(web_ctx, cfg=cfg)
    add_log(web_engine, minutes=30, note="일요일 시작 주", day=W40_THURSDAY)

    with TestClient(create_app(ctx), base_url=LOCAL_BASE_URL) as client:
        html = _get(client)

    assert "2026-W40 (09-27 ~ 10-03)" in all_by_tag(html, "header")[0].text
    assert "기록 1건" in by_id(html, "summary").text


def test_dashboard_when_database_is_locked(locked_client: LockedApp) -> None:
    client, _engine, path = locked_client
    with hold_lock(path, "EXCLUSIVE"):
        response = client.get("/")
    assert response.status_code == 503
    assert "사용 중" in response.text
    assert response.headers["content-type"] == "text/html; charset=utf-8"
