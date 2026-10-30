"""타이머 시작·취소 화면과 시작 폼 테스트 (시각 = 2026-10-01 09:30 +09:00)."""

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.models import ActiveTimer
from logbook.core.services.timer import NO_TIMER_WEB_MESSAGE
from logbook.core.taskstatus import TaskStatus
from logbook.web.pages.views import timer_version
from tests.helpers import FIXED_NOW, Clock
from tests.web.helpers import (
    add_log,
    add_project,
    add_task,
    all_by_tag,
    by_id,
    inline_code_violations,
    named_input,
    parse_html,
    select_options,
)

HTMX = {"HX-Request": "true"}
NOTE_REQUIRED = "메모를 입력하세요. 태스크를 고르면 태스크 제목을 씁니다."
CATEGORY_REQUIRED = "카테고리를 고르세요. 태스크를 고르면 태스크의 카테고리를 씁니다."
TIMER_CHANGED = "다른 곳에서 타이머가 바뀌었습니다. 패널에 지금 타이머를 다시 표시했습니다."
START_FORM = {"note": "환불 API 설계", "project": "payment", "category": "design"}


def _has_timer(engine: Engine) -> bool:
    with db.session_scope(engine) as s:
        return services.get_timer(s) is not None


def _log_count(engine: Engine) -> int:
    with db.session_scope(engine) as s:
        return len(services.list_worklogs(s))


def _start_directly(engine: Engine, note: str = "설계") -> None:
    with db.session_scope(engine) as s:
        services.start_timer(s, now=FIXED_NOW, note=note, project_slug="payment", category="design")


def _idle(html: str) -> bool:
    """진행 중이 아닌 타이머 영역: 시작 폼·선택 상자·안내 줄 없이 결과 줄만 둔다(2026-10-29 E1)."""
    timer = by_id(html, "timer")
    start = html.index('id="timer"')
    section = html[start : html.index("</section>", start)]
    return (
        "timer--running" not in str(timer.attrs["class"]).split()
        and "<select" not in section
        and "<form" not in section
        and "timer__idle" not in section
    )


def _cancel_version(html: str) -> str:
    button = next(e for e in all_by_tag(html, "button") if e.text == "취소")
    vals = json.loads(str(button.attrs["hx-vals"]))
    return str(vals["version"])


def test_quick_form_has_timer_start_button(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    add_task(web_engine, title="환불 API 설계", project="payment")

    html = client.get("/").text

    # 타이머 시작 폼은 없고, 빠른 기록 폼의 선택 상자를 함께 쓴다(2026-10-29 E1).
    ids = {str(e.attrs.get("id")) for e in parse_html(html)}
    assert not ids & {"timer-start", "timer-note", "timer-project", "timer-category", "timer-task"}
    assert _idle(html)
    form = by_form(html)
    buttons = all_by_tag(form, "button")
    assert [b.text for b in buttons] == ["기록", "타이머 시작"]
    record, start = buttons
    assert (record.attrs["type"], record.attrs["class"]) == ("submit", "btn btn--primary")
    # Enter는 늘 기록이다: 타이머 시작은 submit 버튼이 아니다(E2).
    assert start.attrs["type"] == "button"
    assert "btn--primary" not in str(start.attrs["class"]).split()
    assert "quick__timer" in str(start.attrs["class"]).split()
    assert start.attrs["hx-post"] == "/timer/start"
    assert start.attrs["hx-target"] == "#timer"
    assert start.attrs["hx-swap"] == "outerHTML"
    assert start.attrs["hx-sync"] == "closest form:drop"
    assert "<svg" in form[form.index("quick__timer") :]
    assert inline_code_violations(html) == []


def test_start_with_note_and_category(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/timer/start", data=START_FORM, headers=HTMX)

    html = response.text
    assert response.status_code == 200
    assert (
        by_id(html, "timer-result").text == "✔ 타이머 시작: payment/design — 환불 API 설계 (09:30)"
    )
    assert by_id(html, "timer-result").attrs["role"] == "status"
    assert "timer-elapsed" in {str(e.attrs.get("id")) for e in parse_html(html)}
    # 입력한 메모가 다음 기록에 섞이지 않게 빠른 기록 폼을 빈 값으로 다시 그린다.
    quick = by_id(html, "quick-form")
    assert quick.attrs["hx-swap-oob"] == "true"
    for name in ("duration", "note"):
        assert named_input(html, name).attrs.get("value", "") == ""
    for name in ("project", "category", "task"):
        assert [v for v, _, sel in select_options(html, name) if sel] == []
    with db.session_scope(web_engine) as s:
        timer = services.get_timer(s)
        assert timer is not None
        assert (timer.project.slug, timer.category, timer.note) == (
            "payment",
            "design",
            "환불 API 설계",
        )


def test_start_from_todo_task_uses_title_and_marks_doing(
    client: TestClient, web_engine: Engine
) -> None:
    add_project(web_engine, "payment", "결제 서버")
    task_id = add_task(web_engine, title="태스크 제목", project="payment", category="docs")

    response = client.post("/timer/start", data={"task": str(task_id)}, headers=HTMX)

    assert response.status_code == 200
    assert by_id(response.text, "timer-result").text == (
        f"✔ 타이머 시작: payment/docs — 태스크 제목 (09:30) (태스크 #{task_id}: 할 일 → 진행)"
    )
    with db.session_scope(web_engine) as s:
        assert services.get_task(s, task_id).status == TaskStatus.DOING


@pytest.mark.parametrize(
    ("form", "message"),
    [
        pytest.param({"category": "dev"}, NOTE_REQUIRED, id="no-note-no-task"),
        pytest.param({"note": "메모"}, CATEGORY_REQUIRED, id="no-category-no-task"),
    ],
)
def test_start_validation_errors_leave_quick_form_alone(
    client: TestClient, web_engine: Engine, form: dict[str, str], message: str
) -> None:
    response = client.post(
        "/timer/start", data={"duration": "", "project": "common", **form}, headers=HTMX
    )

    html = response.text
    assert response.status_code == 400
    assert by_id(html, "timer-result").text == message
    assert by_id(html, "timer-result").attrs["role"] == "alert"
    # 입력값은 빠른 기록 폼에 그대로 남는다. 응답은 타이머 영역만 바꾼다.
    assert 'id="quick-form"' not in html
    assert _idle(html)
    # 시작 실패는 포커스를 옮기지 않는다(입력하던 칸에 남는다).
    assert "data-refocus" not in by_id(html, "timer").attrs
    assert not _has_timer(web_engine)


def test_start_while_running_shows_running_panel(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    _start_directly(web_engine)

    response = client.post("/timer/start", data=START_FORM, headers=HTMX)

    html = response.text
    assert response.status_code == 400
    assert "이미 진행 중인 타이머가 있습니다" in by_id(html, "timer-result").text
    assert "timer-elapsed" in {str(e.attrs.get("id")) for e in parse_html(html)}


def test_start_in_archived_project_is_rejected(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "old", "옛 프로젝트", archived=True)

    response = client.post(
        "/timer/start", data={"note": "메모", "project": "old", "category": "dev"}, headers=HTMX
    )

    assert response.status_code == 400
    assert by_id(response.text, "timer-result").attrs["role"] == "alert"
    assert not _has_timer(web_engine)


def test_cancel_with_same_version(client: TestClient, web_engine: Engine, clock: Clock) -> None:
    add_project(web_engine, "payment", "결제 서버")
    _start_directly(web_engine)
    clock.advance(minutes=85)
    version = _cancel_version(client.get("/timer", headers=HTMX).text)

    response = client.post("/timer/cancel", data={"version": version}, headers=HTMX)

    html = response.text
    assert response.status_code == 200
    assert by_id(html, "timer-result").text == (
        "✔ 타이머를 버렸습니다: payment/design — 설계 (경과 1h 25m)"
    )
    assert _idle(html)
    assert not _has_timer(web_engine)
    assert _log_count(web_engine) == 0


def test_cancel_right_after_web_start_with_start_response_version(
    client: TestClient, web_engine: Engine
) -> None:
    add_project(web_engine, "payment", "결제 서버")
    started = client.post("/timer/start", data=START_FORM, headers=HTMX)
    version = _cancel_version(started.text)

    response = client.post("/timer/cancel", data={"version": version}, headers=HTMX)

    assert response.status_code == 200
    assert not _has_timer(web_engine)
    assert _log_count(web_engine) == 0


def test_cancel_after_elapsed_refresh_with_start_response_version(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    add_project(web_engine, "payment", "결제 서버")
    version = _cancel_version(client.post("/timer/start", data=START_FORM, headers=HTMX).text)
    clock.advance(seconds=61)
    assert client.get("/timer/elapsed", headers=HTMX).status_code == 200

    response = client.post("/timer/cancel", data={"version": version}, headers=HTMX)

    assert response.status_code == 200
    assert not _has_timer(web_engine)


def test_timer_version_is_the_same_for_the_same_instant_in_any_offset() -> None:
    utc_start = datetime(2026, 10, 1, 0, 30, tzinfo=UTC)
    kst_start = utc_start.astimezone(timezone(timedelta(hours=9)))
    assert kst_start.isoformat() != utc_start.isoformat()

    def make(started_at: datetime) -> ActiveTimer:
        return ActiveTimer(
            started_at=started_at, project_id=1, category="dev", note="메모", task_id=None
        )

    assert timer_version(make(utc_start)) == timer_version(make(kst_start))
    assert timer_version(make(utc_start)) != timer_version(make(utc_start + timedelta(seconds=1)))


def test_cancel_with_other_version_conflicts(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    _start_directly(web_engine, "처음")
    old_version = _cancel_version(client.get("/timer", headers=HTMX).text)
    with db.session_scope(web_engine) as s:
        services.cancel_timer(s)
    _start_directly(web_engine, "다시 시작")

    response = client.post("/timer/cancel", data={"version": old_version}, headers=HTMX)

    html = response.text
    assert response.status_code == 409
    assert by_id(html, "timer-result").text == TIMER_CHANGED
    assert "다시 시작" in by_id(html, "timer").text
    assert _has_timer(web_engine)


def test_cancel_without_timer(client: TestClient) -> None:
    response = client.post("/timer/cancel", data={"version": "x"}, headers=HTMX)

    html = response.text
    assert response.status_code == 404
    assert by_id(html, "timer-result").text == NO_TIMER_WEB_MESSAGE
    assert _idle(html)
    # CLI가 먼저 취소한 경우: 취소 버튼이 사라지므로 포커스는 결과 줄로 간다(app.js의 data-refocus).
    assert "data-refocus" in by_id(html, "timer").attrs
    assert "data-focus" in by_id(html, "timer-result").attrs


def test_cancel_from_other_origin_is_forbidden(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    _start_directly(web_engine)

    response = client.post(
        "/timer/cancel", data={"version": "x"}, headers={"Origin": "http://evil.example"}
    )

    assert response.status_code == 403
    assert _has_timer(web_engine)


def test_cancel_button_has_confirm_and_version(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    add_project(web_engine, "payment", "결제 서버")
    _start_directly(web_engine)
    clock.advance(minutes=85)

    html = client.get("/timer", headers=HTMX).text

    button = next(e for e in all_by_tag(html, "button") if e.text == "취소")
    assert button.attrs["hx-post"] == "/timer/cancel"
    assert button.attrs["hx-confirm"] == (
        "버릴 타이머: payment/design — 설계 (시작 09:30 · 경과 1h 25m)\n"
        "버릴까요? 기록은 남지 않습니다."
    )
    assert len(_cancel_version(html)) == 16
    assert inline_code_violations(html) == []


def test_stop_response_has_idle_panel(client: TestClient, web_engine: Engine, clock: Clock) -> None:
    add_project(web_engine, "payment", "결제 서버")
    _start_directly(web_engine)
    clock.advance(minutes=85)

    html = client.post("/timer/stop", headers=HTMX).text

    assert _idle(html)


def test_elapsed_without_timer_returns_idle_panel(client: TestClient) -> None:
    html = client.get("/timer/elapsed", headers=HTMX).text

    assert _idle(html)
    assert by_id(html, "timer").text == "타이머"  # 숨은 제목만 남는다


def test_data_focus_on_timer_states(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    idle = client.get("/timer", headers=HTMX).text
    assert [e for e in parse_html(idle) if "data-focus" in e.attrs] == []

    _start_directly(web_engine)
    running = client.get("/timer", headers=HTMX).text
    focus = [e for e in parse_html(running) if "data-focus" in e.attrs]
    assert [e.text for e in focus] == ["정지"]

    # 정지·취소 뒤에는 정지 버튼이 사라지므로 결과 줄이 포커스를 받는다.
    version = _cancel_version(running)
    stopped = client.post("/timer/cancel", data={"version": version}, headers=HTMX).text
    focus = [e for e in parse_html(stopped) if "data-focus" in e.attrs]
    assert [(e.attrs.get("id"), e.attrs.get("tabindex")) for e in focus] == [("timer-result", "-1")]


def test_data_focus_on_log_areas(client: TestClient, web_engine: Engine) -> None:
    log_id = add_log(web_engine, minutes=60, note="기록")

    quick = client.get("/").text
    focus = [e for e in parse_html(by_form(quick)) if "data-focus" in e.attrs]
    assert [e.attrs.get("name") for e in focus] == ["duration"]

    table = client.get("/logs").text
    focus = [e for e in parse_html(table) if "data-focus" in e.attrs]
    assert [e.attrs.get("id") for e in focus] == ["log-table-title"]

    edit = client.get(f"/logs/{log_id}/edit").text
    focus = [e for e in parse_html(edit) if "data-focus" in e.attrs]
    assert [e.attrs.get("name") for e in focus] == ["duration"]


def by_form(html: str) -> str:
    """빠른 기록 폼 조각만 잘라 낸다."""
    start = html.index('id="quick-form"')
    end = html.index("</form>", start)
    return html[start:end]
