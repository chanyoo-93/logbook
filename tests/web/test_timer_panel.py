"""타이머 패널(/timer, /timer/elapsed, /timer/stop) 테스트 (시작 = 2026-10-01 09:30 +09:00)."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.services.timer import NO_TIMER_WEB_MESSAGE
from tests.conftest import FIXED_TODAY
from tests.helpers import FIXED_NOW, Clock
from tests.web.helpers import add_log, add_project, all_by_tag, by_class, by_id, parse_html

HTMX = {"HX-Request": "true"}
ONE_MINUTE_MESSAGE = "1분이 지나지 않아 기록하지 않았습니다. 버리려면 취소를 누르세요."


def _start(engine: Engine) -> None:
    add_project(engine, "payment", "결제 서버")
    with db.session_scope(engine) as s:
        services.start_timer(
            s,
            now=FIXED_NOW,
            note="환불 API 설계",
            project_slug="payment",
            category="design",
        )


def _has_timer(engine: Engine) -> bool:
    with db.session_scope(engine) as s:
        return services.get_timer(s) is not None


def _ids(html: str) -> set[str]:
    return {str(e.attrs["id"]) for e in parse_html(html) if "id" in e.attrs}


def test_panel_without_timer(client: TestClient) -> None:
    response = client.get("/timer", headers=HTMX)

    assert response.status_code == 200
    assert "진행 중인 타이머가 없습니다" not in response.text  # 안내 줄을 없앴다(2026-10-29 E1)
    assert "timer-elapsed" not in _ids(response.text)
    assert all_by_tag(response.text, "button") == []  # 시작은 빠른 기록 폼의 버튼이다


def test_panel_with_timer(client: TestClient, web_engine: Engine, clock: Clock) -> None:
    _start(web_engine)
    clock.advance(minutes=85)

    html = client.get("/timer", headers=HTMX).text

    assert "payment/design" in by_id(html, "timer").text
    elapsed = by_id(html, "timer-elapsed")
    assert elapsed.text == "경과 1h 25m"
    assert elapsed.attrs["hx-get"] == "/timer/elapsed"
    assert elapsed.attrs["hx-trigger"] == "every 60s"
    assert elapsed.attrs["hx-swap"] == "outerHTML"
    button = next(e for e in all_by_tag(html, "button") if e.text == "정지")
    assert [e.text for e in all_by_tag(html, "button")] == ["정지", "취소"]
    assert button.attrs["hx-post"] == "/timer/stop"
    assert button.attrs["hx-target"] == "#timer"
    assert button.attrs["hx-swap"] == "outerHTML"
    assert button.attrs["hx-sync"] == "this:drop"
    assert button.attrs["hx-disabled-elt"] == "this"


def test_panel_with_timer_shows_running_pill(client: TestClient, web_engine: Engine) -> None:
    _start(web_engine)

    html = client.get("/timer", headers=HTMX).text

    pills = by_class(html, "pill--ok")
    assert [(e.tag, e.text) for e in pills] == [("span", "진행 중")]
    assert str(pills[0].attrs["class"]).split() == ["pill", "pill--ok"]


def test_dashboard_embeds_the_same_panel(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    _start(web_engine)
    clock.advance(minutes=85)

    html = client.get("/").text

    assert by_id(html, "timer-elapsed").attrs["hx-trigger"] == "every 60s"
    assert "정지" in [e.text for e in all_by_tag(html, "button")]


def test_elapsed_fragment(client: TestClient, web_engine: Engine, clock: Clock) -> None:
    _start(web_engine)
    clock.advance(minutes=85)

    response = client.get("/timer/elapsed", headers=HTMX)

    assert response.status_code == 200
    assert by_id(response.text, "timer-elapsed").text == "경과 1h 25m"
    assert "HX-Retarget" not in response.headers
    assert "timer" not in _ids(response.text)


def test_elapsed_fragment_carries_the_latest_cancel_confirm(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    _start(web_engine)
    clock.advance(seconds=61)

    response = client.get("/timer/elapsed", headers=HTMX)

    confirm = str(by_id(response.text, "timer-elapsed").attrs["data-cancel-confirm"])
    assert "경과 1m" in confirm
    assert "환불 API 설계" in confirm


def test_panel_cancel_confirm_matches_the_elapsed_span(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    _start(web_engine)
    clock.advance(minutes=85)

    html = client.get("/timer", headers=HTMX).text

    cancel = next(e for e in all_by_tag(html, "button") if e.text == "취소")
    elapsed = by_id(html, "timer-elapsed")
    assert elapsed.attrs["data-cancel-confirm"] == cancel.attrs["hx-confirm"]
    assert "경과 1h 25m" in str(cancel.attrs["hx-confirm"])


def test_elapsed_without_timer_returns_empty_panel(client: TestClient) -> None:
    response = client.get("/timer/elapsed", headers=HTMX)

    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#timer"
    assert response.headers["HX-Reswap"] == "outerHTML"
    assert "timer--running" not in str(by_id(response.text, "timer").attrs["class"]).split()


def test_stop_saves_log_and_refreshes_panels(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    _start(web_engine)
    add_log(web_engine, minutes=330 - 85, note="앞선 기록", day=FIXED_TODAY)
    clock.advance(minutes=85)

    response = client.post("/timer/stop", headers=HTMX)

    html = response.text
    assert response.status_code == 200
    result = by_id(html, "timer-result")
    assert result.attrs["role"] == "status"
    assert result.text == "✔ #2 payment/design 1h 25m — 환불 API 설계 (오늘 누적 5h 30m)"
    assert not _has_timer(web_engine)
    with db.session_scope(web_engine) as s:
        log = services.list_worklogs(s, project_slug="payment")[0]
        assert (log.minutes, log.date) == (85, FIXED_TODAY)
    assert "timer--running" not in str(by_id(html, "timer").attrs["class"]).split()
    assert "hx-swap-oob" not in by_id(html, "timer").attrs
    for name in ("summary", "recent"):
        assert by_id(html, name).attrs["hx-swap-oob"] == "true"
    assert "timer-elapsed" not in _ids(html)


def test_stop_log_date_is_the_start_day(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    _start(web_engine)
    clock.advance(hours=20)  # 다음 날 05:30

    response = client.post("/timer/stop", headers=HTMX)

    assert response.status_code == 200
    with db.session_scope(web_engine) as s:
        assert services.list_worklogs(s)[0].date == FIXED_TODAY
    assert "(10-01 누적 20h)" in by_id(response.text, "timer-result").text


def test_stop_under_one_minute_keeps_running_panel(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    _start(web_engine)
    clock.advance(seconds=29)  # 30초부터는 1분으로 올림되므로 29초

    response = client.post("/timer/stop", headers=HTMX)

    html = response.text
    assert response.status_code == 400
    alert = by_id(html, "timer-result")
    assert alert.attrs["role"] == "alert"
    assert alert.text == ONE_MINUTE_MESSAGE
    assert "payment/design" in by_id(html, "timer").text
    assert "timer-elapsed" in _ids(html)
    assert "summary" not in _ids(html)
    assert _has_timer(web_engine)
    with db.session_scope(web_engine) as s:
        assert services.list_worklogs(s) == []


def test_stop_without_timer(client: TestClient) -> None:
    response = client.post("/timer/stop", headers=HTMX)

    html = response.text
    assert response.status_code == 404
    assert by_id(html, "timer-result").text == NO_TIMER_WEB_MESSAGE
    assert by_id(html, "timer-result").attrs["role"] == "alert"
    assert "timer--running" not in str(by_id(html, "timer").attrs["class"]).split()
    assert "timer-elapsed" not in _ids(html)


def _refocus(html: str) -> bool:
    return "data-refocus" in by_id(html, "timer").attrs


def test_running_panel_refocuses_stop_after_failure(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    # 진행 중이거나 정지·취소가 실패했을 때만 #timer에 data-refocus를 둔다.
    # 실패 응답(4xx) 뒤에도 포커스가 정지 버튼으로 돌아온다(app.js).
    assert not _refocus(client.get("/timer", headers=HTMX).text)

    _start(web_engine)
    assert _refocus(client.get("/timer", headers=HTMX).text)

    clock.advance(seconds=29)
    failed = client.post("/timer/stop", headers=HTMX)
    assert failed.status_code == 400
    assert _refocus(failed.text)

    clock.advance(minutes=30)
    stopped = client.post("/timer/stop", headers=HTMX).text
    assert not _refocus(stopped)
    # 타이머가 없는 정지 실패(CLI가 먼저 정지)는 정지 버튼이 없으므로 결과 줄로 포커스를 보낸다.
    missing = client.post("/timer/stop", headers=HTMX)
    assert missing.status_code == 404
    assert _refocus(missing.text)
    assert "data-focus" in by_id(missing.text, "timer-result").attrs


def test_stop_from_other_origin_is_forbidden(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    _start(web_engine)
    clock.advance(minutes=85)

    response = client.post("/timer/stop", headers={"Origin": "http://evil.example"})

    assert response.status_code == 403
    assert _has_timer(web_engine)


def test_running_timer_panel_has_running_class_and_idle_does_not(
    client: TestClient, web_engine: Engine
) -> None:
    idle = client.get("/timer", headers=HTMX).text
    _start(web_engine)
    running = client.get("/timer", headers=HTMX).text

    assert "timer--running" not in str(by_id(idle, "timer").attrs["class"]).split()
    # 작업 기록 패널 안의 한 줄이라 panel 클래스는 없다(2026-10-26 D1).
    assert str(by_id(running, "timer").attrs["class"]).split() == ["timer", "timer--running"]
