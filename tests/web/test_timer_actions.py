"""타이머 시작·취소 화면과 시작 폼 테스트 (시각 = 2026-10-01 09:30 +09:00)."""

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.models import ActiveTimer
from logbook.core.services.timer import NO_TIMER_MESSAGE
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


def _cancel_version(html: str) -> str:
    button = next(e for e in all_by_tag(html, "button") if e.text == "취소")
    vals = json.loads(str(button.attrs["hx-vals"]))
    return str(vals["version"])


def test_idle_panel_has_start_form_with_same_choices_as_quick_form(
    client: TestClient, web_engine: Engine
) -> None:
    add_project(web_engine, "payment", "결제 서버")
    add_task(web_engine, title="환불 API 설계", project="payment")

    html = client.get("/").text

    form = by_id(html, "timer-start")
    assert form.attrs["hx-post"] == "/timer/start"
    assert form.attrs["hx-target"] == "#timer"
    assert form.attrs["hx-swap"] == "outerHTML"
    assert form.attrs["hx-sync"] == "this:drop"
    assert form.attrs["hx-disabled-elt"] == "find button"
    note = by_id(html, "timer-note")
    assert note.attrs["placeholder"] == "무엇을 하나요"
    assert note.attrs["title"] == "태스크를 고르면 비워도 됩니다."
    assert "터미널에서 lb start로 시작하세요." not in html
    quick_ids = {"project": "quick-project", "category": "quick-category", "task": "quick-task"}
    for name, quick_id in quick_ids.items():
        assert by_id(html, f"timer-{name}").tag == "select"
        assert by_id(html, quick_id).tag == "select"
    timer_html = client.get("/timer", headers=HTMX).text
    quick_html = client.post("/logs", data={"duration": "", "note": ""}, headers=HTMX).text
    for name in ("project", "category", "task"):
        assert select_options(timer_html, name) == select_options(quick_html, name)
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
def test_start_validation_errors_keep_input(
    client: TestClient, web_engine: Engine, form: dict[str, str], message: str
) -> None:
    response = client.post("/timer/start", data={"project": "common", **form}, headers=HTMX)

    html = response.text
    assert response.status_code == 400
    assert by_id(html, "timer-result").text == message
    assert by_id(html, "timer-result").attrs["role"] == "alert"
    assert by_id(html, "timer-note").attrs["value"] == form.get("note", "")
    selected = [v for v, _, sel in select_options(html, "category") if sel]
    assert selected == ([form["category"]] if "category" in form else [])
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
    assert by_id(html, "timer-start").tag == "form"
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
    assert by_id(html, "timer-result").text == NO_TIMER_MESSAGE
    assert by_id(html, "timer-start").tag == "form"


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


def test_stop_response_has_start_form_with_choices(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    add_project(web_engine, "payment", "결제 서버")
    _start_directly(web_engine)
    clock.advance(minutes=85)

    html = client.post("/timer/stop", headers=HTMX).text

    assert by_id(html, "timer-start").tag == "form"
    assert ("payment", "payment — 결제 서버", False) in select_options(html, "project")


def test_elapsed_without_timer_returns_start_form(client: TestClient) -> None:
    html = client.get("/timer/elapsed", headers=HTMX).text

    assert by_id(html, "timer-start").tag == "form"
    assert select_options(html, "category")[0] == ("", "카테고리 자동", False)


def test_data_focus_on_timer_states(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    idle = client.get("/timer", headers=HTMX).text
    focus = [e for e in parse_html(idle) if "data-focus" in e.attrs]
    assert [e.attrs.get("id") for e in focus] == ["timer-note"]

    _start_directly(web_engine)
    running = client.get("/timer", headers=HTMX).text
    focus = [e for e in parse_html(running) if "data-focus" in e.attrs]
    assert [e.text for e in focus] == ["정지"]


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
    """빠른 기록 폼 조각만 잘라 낸다(타이머 시작 폼과 섞이지 않게)."""
    start = html.index('id="quick-form"')
    end = html.index("</form>", start)
    return html[start:end]


def test_timer_start_selects_explain_auto_rule_in_title(client: TestClient) -> None:
    """빈 값 문구는 짧게, 자동 규칙 전체 설명은 말풍선(title)에 둔다(2026-10-26 D2)."""
    html = client.get("/timer", headers=HTMX).text

    assert select_options(html, "project")[0] == ("", "프로젝트 자동", False)
    assert select_options(html, "task")[0] == ("", "태스크 없음", False)
    assert named_input(html, "project").attrs["title"] == (
        "비우면 태스크의 프로젝트를 쓰고, 태스크도 없으면 기본 프로젝트(common)에 기록합니다."
    )
    assert named_input(html, "category").attrs["title"] == "비우면 태스크의 카테고리를 씁니다."
    assert "title" not in named_input(html, "task").attrs
