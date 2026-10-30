"""웹 화면의 오류 문구(2026-10-29 G1): 화면은 웹 문구, /api/는 CLI 문구.

시작 = 2026-10-01 09:30 +09:00.
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.errors import NotFoundError
from logbook.web.errors import user_message
from tests.helpers import FIXED_NOW, Clock
from tests.web.helpers import add_project, by_id, flash_text, parse_html

HTMX = {"HX-Request": "true"}
CLI_HINT = "'lb "
WEB_LOG_MISSING = "기록을 찾을 수 없습니다: #7. 기록 화면에서 확인하세요."


def _start(engine: Engine) -> None:
    add_project(engine, "payment", "결제 서버")
    with db.session_scope(engine) as s:
        services.start_timer(
            s, now=FIXED_NOW, note="환불 API 설계", project_slug="payment", category="design"
        )


def _alert(html: str) -> str:
    """오류 페이지의 <p role="alert"> 문구."""
    [alert] = [e for e in parse_html(html) if e.tag == "p" and e.attrs.get("role") == "alert"]
    return alert.text


def test_user_message_prefers_web_message() -> None:
    assert user_message(NotFoundError("CLI", web_message="웹")) == "웹"
    assert user_message(NotFoundError("CLI")) == "CLI"


def test_handler_uses_web_message_on_screens_and_cli_message_on_api(
    probe_client: TestClient,
) -> None:
    assert flash_text(probe_client.get("/raise/web", headers=HTMX).text) == WEB_LOG_MISSING
    assert _alert(probe_client.get("/raise/web").text) == WEB_LOG_MISSING
    api = probe_client.get("/api/raise/web").json()
    assert api["error"]["message"] == "기록을 찾을 수 없습니다: #7. 'lb log'로 확인하세요."


def test_stop_under_one_minute_says_press_cancel(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    _start(web_engine)
    clock.advance(seconds=29)

    html = client.post("/timer/stop", headers=HTMX).text

    assert by_id(html, "timer-result").text == (
        "1분이 지나지 않아 기록하지 않았습니다. 버리려면 취소를 누르세요."
    )


def test_start_while_running_points_to_stop_and_cancel(
    client: TestClient, web_engine: Engine
) -> None:
    _start(web_engine)

    html = client.post(
        "/timer/start", data={"note": "메모", "project": "common", "category": "dev"}, headers=HTMX
    ).text

    assert by_id(html, "timer-result").text.endswith(
        "대시보드의 정지로 저장하거나 취소로 버리세요."
    )


def test_missing_log_and_task_screens(client: TestClient) -> None:
    log = client.get("/logs/99/edit", headers=HTMX)
    assert log.status_code == 404
    assert flash_text(log.text) == "기록을 찾을 수 없습니다: #99. 기록 화면에서 확인하세요."

    task = client.get("/tasks/99/edit")
    assert task.status_code == 404
    assert _alert(task.text) == "태스크를 찾을 수 없습니다: #99. 태스크 화면에서 확인하세요."


def test_quick_add_with_missing_project(client: TestClient) -> None:
    response = client.post(
        "/logs",
        data={"duration": "1h", "note": "메모", "project": "nope", "category": "dev"},
        headers=HTMX,
    )

    assert response.status_code == 404
    assert by_id(response.text, "quick-result").text == (
        "프로젝트를 찾을 수 없습니다: 'nope'. 설정 화면의 프로젝트 목록에서 확인하거나 추가하세요."
    )


def test_duplicate_project_in_settings(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")

    response = client.post(
        "/settings/projects", data={"slug": "payment", "name": "또 결제", "color": ""}, headers=HTMX
    )

    assert by_id(response.text, "project-result").text == (
        "이미 존재하는 프로젝트입니다: 'payment'. 설정 화면의 프로젝트 목록에서 확인하세요."
    )


def test_api_keeps_cli_message(client: TestClient, web_engine: Engine, clock: Clock) -> None:
    _start(web_engine)
    clock.advance(seconds=29)

    error = client.post("/api/timer/stop", json={}).json()["error"]

    assert error["message"] == (
        "1분이 지나지 않아 기록하지 않았습니다. 버리려면 'lb cancel'을 실행하세요."
    )


def test_screens_never_show_cli_hints(client: TestClient, web_engine: Engine, clock: Clock) -> None:
    # 웹 문구를 빠뜨린 오류를 잡는 그물: 웹에 나올 수 있는 오류 응답에 'lb ...' 안내가 없다.
    responses = [
        client.post("/timer/stop", headers=HTMX),
        client.post("/timer/cancel", data={"version": "1"}, headers=HTMX),
        client.get("/logs/99/edit", headers=HTMX),
        client.get("/logs/99/row", headers=HTMX),
        client.patch("/logs/99", data={"version": "1"}, headers=HTMX),
        client.delete("/logs/99?version=1", headers=HTMX),
        client.get("/tasks/99/edit"),
        client.post("/tasks/99/status", data={"status": "done"}, headers=HTMX),
        client.get("/settings/projects/nope/edit", headers=HTMX),
        client.post("/settings/projects/nope/archive", headers=HTMX),
    ]
    _start(web_engine)
    responses.append(
        client.post("/timer/start", data={"note": "x", "category": "dev"}, headers=HTMX)
    )
    clock.advance(seconds=29)
    responses.append(client.post("/timer/stop", headers=HTMX))
    clock.advance(hours=25)
    responses.append(client.post("/timer/stop", headers=HTMX))

    for response in responses:
        assert response.status_code >= 400, response.request.url
        assert CLI_HINT not in response.text, (response.request.url, response.text[:300])
