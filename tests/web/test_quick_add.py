"""빠른 기록 폼(#quick-form)과 POST /logs 테스트 (오늘 = 2026-10-01 목요일 09:30 +09:00)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.duration import parse_duration
from logbook.core.errors import InvalidInputError
from logbook.core.taskstatus import TaskStatus
from tests.conftest import FIXED_TODAY
from tests.web.conftest import LOCAL_BASE_URL
from tests.web.helpers import (
    Element,
    add_log,
    add_project,
    add_task,
    all_by_tag,
    by_id,
    json_attr,
    parse_html,
)

DURATION_REQUIRED = "시간을 입력하세요. 예: 2h, 90m, 1:30"
CATEGORY_REQUIRED = "카테고리를 고르세요. 태스크를 고르면 태스크의 카테고리를 씁니다."
NOTE_REQUIRED = "메모를 입력하세요. 무엇을 했는지 한 줄로 적어 주세요."
TASK_OF_PAYMENT = (
    "'payment' 프로젝트에 속한 태스크입니다 (#1). "
    "프로젝트를 빼거나 같은 프로젝트(-p payment)를 지정하세요."
)
FORM = {"duration": "2h", "note": "결제 재시도", "project": "payment", "category": "dev"}
HTMX = {"HX-Request": "true"}


def _bad_duration_message() -> str:
    with pytest.raises(InvalidInputError) as caught:
        parse_duration("abc")
    return str(caught.value)


def _count_logs(engine: Engine) -> int:
    with db.session_scope(engine) as s:
        return len(services.list_worklogs(s))


def _options(html: str, name: str) -> list[tuple[str, str, bool]]:
    """name 속성이 name인 select의 (value, 표시 글, 선택됨) 목록."""
    result: list[tuple[str, str, bool]] = []
    in_select = False
    for element in parse_html(html):
        if element.tag == "select":
            in_select = element.attrs.get("name") == name
        elif in_select and element.tag == "option":
            result.append((str(element.attrs["value"]), element.text, "selected" in element.attrs))
    return result


def _selected(html: str, name: str) -> list[str]:
    return [value for value, _, selected in _options(html, name) if selected]


def _input(html: str, name: str) -> Element:
    for element in parse_html(html):
        if element.tag in {"input", "select"} and element.attrs.get("name") == name:
            return element
    raise AssertionError(f"name이 '{name}'인 입력이 없습니다")


def _seed_form(engine: Engine) -> int:
    add_project(engine, "payment", "결제 서버")
    return add_task(engine, title="환불 API 설계", project="payment", category="design")


def test_form_attributes(client: TestClient) -> None:
    form = by_id(client.get("/").text, "quick-form")

    assert form.tag == "form"
    assert form.attrs["hx-post"] == "/logs"
    assert form.attrs["hx-target"] == "this"
    assert form.attrs["hx-swap"] == "outerHTML"
    assert form.attrs["hx-sync"] == "this:drop"
    assert form.attrs["hx-disabled-elt"] == "find button"


def test_form_inputs_are_labelled(client: TestClient) -> None:
    html = client.get("/").text

    label_targets = {e.attrs["for"] for e in all_by_tag(html, "label")}
    for name in ("duration", "note", "project", "category", "task"):
        assert _input(html, name).attrs["id"] in label_targets
    duration = _input(html, "duration")
    assert duration.attrs["autocomplete"] == "off"
    assert duration.attrs["placeholder"] == "2h, 90m, 1:30"
    assert "autofocus" in duration.attrs
    assert [e.text for e in all_by_tag(html, "button")] == ["기록"]


def test_form_options(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    add_project(web_engine, "old", "옛 프로젝트")
    add_task(web_engine, title="환불 API 설계", project="payment", status=TaskStatus.DOING)
    add_task(web_engine, title="할 일", project="payment")
    add_task(web_engine, title="끝난 일", project="payment", status=TaskStatus.DONE)
    add_task(web_engine, title="옛 일", project="old")
    with db.session_scope(web_engine) as s:
        services.archive_project(s, "old")

    html = client.get("/").text

    projects = _options(html, "project")
    assert projects[0] == ("", "자동 (태스크 또는 common)", False)
    assert [value for value, _, _ in projects[1:]] == ["common", "payment"]
    assert projects[2] == ("payment", "payment — 결제 서버", False)
    categories = _options(html, "category")
    assert categories[0] == ("", "자동 (태스크)", False)
    assert categories[1:4] == [
        ("dev", "dev — 개발", False),
        ("review", "review — 코드리뷰", False),
        ("meeting", "meeting — 회의", False),
    ]
    assert _options(html, "task") == [
        ("", "없음", False),
        ("1", "#1 payment · 환불 API 설계", False),
        ("2", "#2 payment · 할 일", False),
    ]


def test_post_success(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    add_log(web_engine, minutes=90, note="앞선 기록")

    response = client.post("/logs", data=FORM, headers=HTMX)

    html = response.text
    assert response.status_code == 200
    result = by_id(html, "quick-result")
    assert result.text == "✔ #2 payment/dev 2h — 결제 재시도 (오늘 누적 3h 30m)"
    assert result.attrs["role"] == "status"
    with db.session_scope(web_engine) as s:
        log = services.list_worklogs(s, project_slug="payment")[0]
        assert (log.minutes, log.note, log.category, log.date) == (
            120,
            "결제 재시도",
            "dev",
            FIXED_TODAY,
        )
    for name in ("summary", "recent"):
        assert by_id(html, name).attrs["hx-swap-oob"] == "true"
    assert "기록 2건" in by_id(html, "summary").text
    assert "3h 30m" in by_id(html, "summary").text
    assert "payment/dev 2h 결제 재시도" in by_id(html, "recent").text
    assert "hx-swap-oob" not in by_id(html, "quick-form").attrs


def test_post_success_keeps_selections_and_clears_text(
    client: TestClient, web_engine: Engine
) -> None:
    _seed_form(web_engine)

    html = client.post("/logs", data={**FORM, "task": "1"}, headers=HTMX).text

    assert _selected(html, "project") == ["payment"]
    assert _selected(html, "category") == ["dev"]
    assert _selected(html, "task") == ["1"]
    assert _input(html, "duration").attrs.get("value", "") == ""
    assert _input(html, "note").attrs.get("value", "") == ""


def test_post_success_summary_chart_is_updated(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    html = client.post("/logs", data=FORM, headers=HTMX).text

    chart = json_attr(html, "summary", "data-chart")
    assert isinstance(chart, dict)
    projects = chart["projects"]
    assert isinstance(projects, dict)
    assert (projects["labels"], projects["data"]) == (["payment"], [120])
    assert "<script" not in html  # htmx가 지우는 script에 데이터를 싣지 않는다


def test_post_task_only_uses_task_project_and_category(
    client: TestClient, web_engine: Engine
) -> None:
    task_id = _seed_form(web_engine)

    response = client.post("/logs", data={"duration": "1h", "note": "설계", "task": str(task_id)})

    assert response.status_code == 200
    assert by_id(response.text, "quick-result").text.startswith("✔ #1 payment/design 1h — 설계")
    with db.session_scope(web_engine) as s:
        log = services.list_worklogs(s, project_slug="payment")[0]
        assert (log.category, log.task_id) == ("design", task_id)


def test_post_without_project_uses_default_project(client: TestClient) -> None:
    response = client.post("/logs", data={"duration": "1h", "note": "정리", "category": "admin"})

    assert response.status_code == 200
    assert by_id(response.text, "quick-result").text.startswith("✔ #1 common/admin 1h — 정리")


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        pytest.param({**FORM, "duration": ""}, DURATION_REQUIRED, id="no-duration"),
        pytest.param({**FORM, "duration": "abc"}, _bad_duration_message(), id="bad-duration"),
        pytest.param({**FORM, "note": ""}, NOTE_REQUIRED, id="no-note"),
        pytest.param({**FORM, "category": ""}, CATEGORY_REQUIRED, id="no-category-or-task"),
        pytest.param(
            {**FORM, "task": "1", "project": "other"}, TASK_OF_PAYMENT, id="task-of-other-project"
        ),
    ],
)
def test_post_errors_keep_input_and_change_nothing(
    client: TestClient, web_engine: Engine, fields: dict[str, str], message: str
) -> None:
    _seed_form(web_engine)
    add_project(web_engine, "other", "다른 프로젝트")

    response = client.post("/logs", data=fields, headers=HTMX)

    html = response.text
    assert response.status_code == 400
    alert = by_id(html, "quick-result")
    assert alert.attrs["role"] == "alert"
    assert alert.text == message
    assert _input(html, "duration").attrs.get("value", "") == fields["duration"]
    assert _input(html, "note").attrs.get("value", "") == fields["note"]
    assert _selected(html, "project") == [fields["project"]]
    assert _selected(html, "category") == ([fields["category"]] if fields["category"] else [])
    assert "summary" not in {e.attrs.get("id") for e in parse_html(html)}
    assert _count_logs(web_engine) == 0


def test_post_error_for_bad_task_id(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/logs", data={**FORM, "task": "abc"})

    assert response.status_code == 400
    assert "태스크 ID가 올바르지 않습니다" in by_id(response.text, "quick-result").text
    assert _count_logs(web_engine) == 0


def test_post_from_other_origin_is_forbidden(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/logs", data=FORM, headers={"Origin": "http://evil.example"})

    assert response.status_code == 403
    assert _count_logs(web_engine) == 0


def test_post_same_origin_is_allowed(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/logs", data=FORM, headers={"Origin": LOCAL_BASE_URL})

    assert response.status_code == 200


def test_result_line_escapes_note(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/logs", data={**FORM, "note": "<b>x</b>"})

    assert "<b>x</b>" not in response.text
    assert "&lt;b&gt;x&lt;/b&gt;" in response.text
    assert by_id(response.text, "quick-result").text == (
        "✔ #1 payment/dev 2h — <b>x</b> (오늘 누적 2h)"
    )
