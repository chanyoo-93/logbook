"""태스크 상태 변경 POST /tasks/{id}/status 테스트 (오늘 = 2026-10-01 목요일 09:30 +09:00)."""

from datetime import UTC, datetime
from html import unescape

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.taskstatus import TaskStatus, parse_status
from logbook.web.errors import TASK_CHANGED, user_message
from logbook.web.pages.task_views import task_version
from tests.helpers import Clock
from tests.web.helpers import (
    add_log,
    add_project,
    add_task,
    board_columns,
    by_id,
    parse_html,
)

HTMX = {"HX-Request": "true"}


def _version(engine: Engine, task_id: int) -> str:
    with db.session_scope(engine) as s:
        return task_version(services.get_task(s, task_id))


def _stored(engine: Engine, task_id: int) -> tuple[TaskStatus, bool]:
    """(상태, 완료 시각이 있는가)."""
    with db.session_scope(engine) as s:
        task = services.get_task(s, task_id)
        return task.status, task.done_at is not None


def _post(client: TestClient, engine: Engine, task_id: int, status: str, **overrides: str):  # type: ignore[no-untyped-def]
    form = {"status": status, "version": _version(engine, task_id), "project": ""}
    return client.post(f"/tasks/{task_id}/status", data={**form, **overrides}, headers=HTMX)


def _result(html: str) -> str:
    return by_id(html, "task-result").text


def test_todo_to_doing_moves_card_and_reports(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="결제 재시도")

    response = _post(client, web_engine, task_id, "doing")

    assert response.status_code == 200
    html = response.text
    assert "<html" not in html
    board = by_id(html, "task-board")
    assert board.tag == "section"
    assert "hx-swap-oob" not in board.attrs
    assert board_columns(html) == {"todo": [], "doing": [task_id], "done": [], "dropped": []}
    assert _result(html) == f"✔ #{task_id} 할 일 → 진행: common · 결제 재시도"
    assert _stored(web_engine, task_id) == (TaskStatus.DOING, False)


def test_doing_to_done_records_done_at_and_reports_actual(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    clock.now = datetime.now().astimezone()  # 완료 시각은 실제 지금이라 화면의 지금도 맞춘다
    task_id = add_task(web_engine, title="결제 재시도", status=TaskStatus.DOING, estimate=240)
    add_log(web_engine, minutes=200, note="가", task_id=task_id)
    add_log(web_engine, minutes=130, note="나", task_id=task_id)

    response = _post(client, web_engine, task_id, "done")

    assert response.status_code == 200
    expected = f"✔ #{task_id} 진행 → 완료: common · 결제 재시도 (실적 5h 30m / 예상 4h)"
    assert _result(response.text) == expected
    assert board_columns(response.text)["done"] == [task_id]
    assert _stored(web_engine, task_id) == (TaskStatus.DONE, True)


def test_done_without_estimate_reports_actual_only(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="예상 없음", status=TaskStatus.DOING)
    add_log(web_engine, minutes=90, note="가", task_id=task_id)

    response = _post(client, web_engine, task_id, "done")

    assert _result(response.text) == f"✔ #{task_id} 진행 → 완료: common · 예상 없음 (실적 1h 30m)"


def test_reopen_clears_done_at(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="다시 열기", status=TaskStatus.DONE)
    assert _stored(web_engine, task_id) == (TaskStatus.DONE, True)

    response = _post(client, web_engine, task_id, "doing")

    assert response.status_code == 200
    assert _result(response.text) == f"✔ #{task_id} 완료 → 진행: common · 다시 열기"
    assert _stored(web_engine, task_id) == (TaskStatus.DOING, False)


def test_drop_moves_card_to_dropped_column(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    clock.now = datetime.now().astimezone()  # 중단 시각은 실제 지금이라 화면의 지금도 맞춘다
    task_id = add_task(web_engine, title="접는 일")

    response = _post(client, web_engine, task_id, "dropped")

    assert response.status_code == 200
    assert _result(response.text) == f"✔ #{task_id} 할 일 → 중단: common · 접는 일"
    assert board_columns(response.text) == {
        "todo": [],
        "doing": [],
        "done": [],
        "dropped": [task_id],
    }
    assert _stored(web_engine, task_id)[0] == TaskStatus.DROPPED


def test_board_response_keeps_the_filter(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    mine = add_task(web_engine, title="결제", project="payment")
    other = add_task(web_engine, title="공통")

    response = _post(client, web_engine, mine, "doing", project="payment")

    assert board_columns(response.text) == {"todo": [], "doing": [mine], "done": [], "dropped": []}
    assert f'id="task-{other}"' not in response.text


def test_stale_version_conflicts_and_changes_nothing(
    client: TestClient, web_engine: Engine
) -> None:
    task_id = add_task(web_engine, title="결제 재시도")
    stale = _version(web_engine, task_id)
    with db.session_scope(web_engine) as s:
        services.update_task(s, task_id, title="다른 곳에서 고침")

    response = _post(client, web_engine, task_id, "doing", version=stale)

    assert response.status_code == 409
    assert response.headers["HX-Retarget"] == "#flash"
    assert response.headers["HX-Push-Url"] == "false"
    assert unescape(response.text).count(TASK_CHANGED.format(id=task_id)) == 1
    assert "<html" not in response.text
    assert _stored(web_engine, task_id) == (TaskStatus.TODO, False)


def test_task_changed_message() -> None:
    assert TASK_CHANGED.format(id=7) == (
        "다른 곳에서 태스크가 바뀌었습니다: #7. 목록을 새로 고친 뒤 다시 시도하세요."
    )


def test_invalid_status_is_rejected(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="결제 재시도")
    try:
        parse_status("x")
    except InvalidInputError as error:
        message = user_message(error)

    response = _post(client, web_engine, task_id, "x")

    assert response.status_code == 400
    assert unescape(response.text).count(message) == 1
    assert _stored(web_engine, task_id) == (TaskStatus.TODO, False)


def test_unknown_task_is_not_found(client: TestClient, web_engine: Engine) -> None:
    with db.session_scope(web_engine) as s:
        try:
            services.get_task(s, 999)
        except NotFoundError as error:
            message = user_message(error)

    response = client.post(
        "/tasks/999/status", data={"status": "doing", "version": "x", "project": ""}, headers=HTMX
    )

    assert response.status_code == 404
    assert unescape(response.text).count(message) == 1


def test_bad_task_id_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/tasks/abc/status", data={"status": "doing", "version": "x"}, headers=HTMX
    )

    assert response.status_code == 400
    assert "태스크 ID가 올바르지 않습니다" in unescape(response.text)


def test_unknown_filter_project_is_not_found_and_changes_nothing(
    client: TestClient, web_engine: Engine
) -> None:
    task_id = add_task(web_engine, title="결제 재시도")

    response = _post(client, web_engine, task_id, "doing", project="nope")

    assert response.status_code == 404
    assert _stored(web_engine, task_id) == (TaskStatus.TODO, False)


def test_post_from_other_origin_is_forbidden(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="결제 재시도")
    form = {"status": "doing", "version": _version(web_engine, task_id)}

    response = client.post(
        f"/tasks/{task_id}/status", data=form, headers={"Origin": "http://evil.example"}
    )

    assert response.status_code == 403
    assert _stored(web_engine, task_id) == (TaskStatus.TODO, False)


def test_status_message_is_escaped(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="<i>기울임</i>")

    response = _post(client, web_engine, task_id, "doing")

    assert "<i>기울임</i>" not in response.text
    assert [e for e in parse_html(response.text) if e.tag == "i"] == []


def test_dragging_dropped_card_back_to_todo(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="되살림")
    _post(client, web_engine, task_id, "dropped")

    response = _post(client, web_engine, task_id, "todo")

    assert response.status_code == 200
    assert _result(response.text) == f"✔ #{task_id} 중단 → 할 일: common · 되살림"
    assert board_columns(response.text)["todo"] == [task_id]
    assert _stored(web_engine, task_id)[0] == TaskStatus.TODO


def test_version_changes_when_dropped_at_changes(web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="중단 시각", status=TaskStatus.DROPPED)
    before = _version(web_engine, task_id)
    with db.session_scope(web_engine) as s:
        services.get_task(s, task_id).dropped_at = datetime(2026, 9, 1, tzinfo=UTC)

    assert _version(web_engine, task_id) != before
