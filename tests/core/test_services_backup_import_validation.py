"""JSONL 가져오기(import_records) 검증 실패 테스트."""

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.orm import Session

from logbook.core import db, services

from .backup_helpers import (
    BOM,
    COMMON,
    DATE_EXPECT,
    DEFAULT_ROWS,
    ENVELOPE_MESSAGE,
    HEADER,
    INT_EXPECT,
    NO_COMMON_MESSAGE,
    OPT_INT_EXPECT,
    PAY,
    PREFIX,
    SLUG_EXPECT,
    STAMP,
    STATUS_EXPECT,
    TASK,
    TIME_EXPECT,
    TIMER,
    WORKLOG,
    dumps,
    header,
    line,
    rejects,
)

# --- 머리글 ---


def _header_cases() -> Iterator[Any]:
    empty = "logbook 내보내기 파일이 아닙니다 (내용이 없습니다)."
    no_type = "logbook 내보내기 파일이 아닙니다 (첫 줄에 type 값이 없습니다)."
    version = "지원하지 않는 내보내기 형식 버전입니다: {}. 이 버전의 logbook이 읽을 수 있는 형식: 1"
    schema = "내보내기 파일의 스키마 버전이 올바르지 않습니다: {}"
    yield pytest.param([], empty, id="빈 입력")
    yield pytest.param(["", "  ", "\r\n"], empty, id="빈 줄만")
    yield pytest.param(["# 주간업무보고 (2026-09-28 ~ 2026-10-04)"], no_type, id="Markdown")
    yield pytest.param(["[1]"], no_type, id="배열")
    yield pytest.param(['"x"'], no_type, id="문자열")
    yield pytest.param(['{"format": 1}'], no_type, id="type 키 없음")
    yield pytest.param(["[" * 100000], no_type, id="깊은 중첩")
    other = "logbook 내보내기 파일이 아닙니다 (첫 줄의 type 값: {})."
    yield pytest.param([header(type="other")], other.format('"other"'), id="type 다름")
    long_value = '"' + "x" * 39 + "..."
    yield pytest.param([header(type="x" * 50)], other.format(long_value), id="type 길이 제한")
    for label, value, shown in (
        ("true", True, "true"),
        ("1.0", 1.0, "1.0"),
        ("문자열", "1", '"1"'),
        ("없음", "<missing>", "null"),
        ("2", 2, "2"),
    ):
        yield pytest.param([header(format=value)], version.format(shown), id=f"format {label}")
    for label, value, shown in (
        ("문자열", "2", '"2"'),
        ("0", 0, "0"),
        ("true", True, "true"),
        ("없음", "<missing>", "null"),
    ):
        yield pytest.param(
            [header(schema_version=value)], schema.format(shown), id=f"schema {label}"
        )
    newer = db.SCHEMA_VERSION + 1
    yield pytest.param(
        [header(schema_version=newer)],
        f"더 새로운 logbook에서 내보낸 파일입니다 (스키마 {newer}). "
        "logbook을 업데이트한 뒤 가져오세요.",
        id="더 새로운 스키마",
    )


@pytest.mark.parametrize(("lines", "message"), list(_header_cases()))
def test_header_errors(fresh: Session, lines: list[str], message: str) -> None:
    rejects(fresh, lines, message)


def test_header_only_reports_missing_common(fresh: Session) -> None:
    rejects(fresh, [HEADER], NO_COMMON_MESSAGE)


def test_header_then_blank_lines_reports_missing_common(fresh: Session) -> None:
    rejects(fresh, [HEADER, "", " "], NO_COMMON_MESSAGE)


def test_other_projects_without_common_is_error(fresh: Session) -> None:
    rejects(fresh, [HEADER, PAY], NO_COMMON_MESSAGE)


@pytest.mark.parametrize("count", [1, 2])
def test_strips_bom_at_start_of_first_line(fresh: Session, count: int) -> None:
    lines = [BOM * count + HEADER, COMMON]

    counts = services.import_records(fresh, lines)

    assert counts.projects == 1


def test_first_line_with_only_bom_counts_as_blank(fresh: Session) -> None:
    lines = [BOM, HEADER, "not json"]

    rejects(fresh, lines, "3번째 줄: JSON 형식이 올바르지 않습니다.")


def test_skips_blank_lines_before_header(fresh: Session) -> None:
    counts = services.import_records(fresh, ["", "  ", HEADER, COMMON])

    assert counts.projects == 1


def test_error_line_numbers_count_blank_lines(fresh: Session) -> None:
    lines = ["", HEADER, "", "  ", COMMON, "", "not json"]

    rejects(fresh, lines, "7번째 줄: JSON 형식이 올바르지 않습니다.")


# --- 줄별 오류 ---


def _raw(table: str, line: str, suffix: str) -> Any:
    return pytest.param(table, line, suffix, id=f"{table}: {suffix[:40]}")


def _field_case(table: str, field: str, value: Any, expect: str) -> Any:
    shown = dumps(value)
    suffix = f"{table}.{field} 값이 올바르지 않습니다: {shown} ({expect})."
    return pytest.param(table, line(table, **{field: value}), suffix, id=f"{table}.{field}={shown}")


def _value_cases() -> Iterator[Any]:
    for value in (2**63, 0, -1, True, 1.5, "1"):
        yield _field_case("projects", "id", value, INT_EXPECT)
    for value in ("Bad", "a b", "", "x" * 33, "-a", 5):
        yield _field_case("projects", "slug", value, SLUG_EXPECT)
    yield _field_case("projects", "archived", 1, "true 또는 false")
    yield _field_case("projects", "name", None, "문자열")
    yield _field_case("projects", "description", 5, "null 또는 문자열")
    yield _field_case("projects", "created_at", None, TIME_EXPECT)
    for value in (
        "2026-10-08T03:00:00",
        "0001-01-01T00:00:00+09:00",
        "0001-01-01T00:00:00+00:00",
        "9999-12-31T00:00:00+00:00",
        "9999-12-31T23:00:00-05:00",
        "not a time",
        20261008,
    ):
        yield _field_case("projects", "created_at", value, TIME_EXPECT)
    yield _field_case("tasks", "project_id", 0, INT_EXPECT)
    yield _field_case("tasks", "title", 3, "문자열")
    yield _field_case("tasks", "status", "wip", STATUS_EXPECT)
    yield _field_case("tasks", "status", None, STATUS_EXPECT)
    for value in (-30, 0, 1.5, True, 2**63):
        yield _field_case("tasks", "estimate_minutes", value, OPT_INT_EXPECT)
    yield _field_case("tasks", "due_date", "20261008", "null 또는 " + DATE_EXPECT)
    yield _field_case("tasks", "done_at", "2026-10-08", "null 또는 " + TIME_EXPECT)
    yield _field_case("worklogs", "task_id", 0, OPT_INT_EXPECT)
    for value in (True, 1.5, 1441, 0, "30"):
        yield _field_case("worklogs", "minutes", value, "1 이상 1440 이하의 정수")
    yield _field_case("worklogs", "date", "20261008", DATE_EXPECT)
    yield _field_case("worklogs", "date", "2026-10-8", DATE_EXPECT)
    yield _field_case("worklogs", "date", None, DATE_EXPECT)
    yield _field_case("worklogs", "note", None, "문자열")
    yield _field_case("worklogs", "started_at", "2026-10-08T03:00:00", "null 또는 " + TIME_EXPECT)
    yield _field_case("active_timer", "id", 2, "1")
    yield _field_case("active_timer", "id", True, "1")
    yield _field_case("active_timer", "started_at", None, TIME_EXPECT)


@pytest.mark.parametrize(("table", "bad", "suffix"), list(_value_cases()))
def test_field_value_errors(fresh: Session, table: str, bad: str, suffix: str) -> None:
    lines = [*PREFIX[table], bad]

    rejects(fresh, lines, f"{len(lines)}번째 줄: {suffix}")


def _raw_text_cases() -> Iterator[Any]:
    yield _raw("projects", "not json", "JSON 형식이 올바르지 않습니다.")
    yield _raw("projects", '{"row": {', "JSON 형식이 올바르지 않습니다.")
    yield _raw(
        "projects",
        '{"row": {"id": ' + "9" * 5000 + '}, "table": "projects"}',
        "JSON 형식이 올바르지 않습니다.",
    )
    yield _raw("tasks", "[" * 100000, "JSON 형식이 올바르지 않습니다.")
    for text in (
        "[1,2]",
        '"x"',
        "null",
        HEADER,
        '{"table": 1, "row": {}}',
        '{"table": "projects", "row": []}',
        '{"table": "projects"}',
        '{"table": "projects", "row": {}, "extra": 1}',
    ):
        yield _raw("tasks", text, ENVELOPE_MESSAGE)
    names = "projects, tasks, worklogs, active_timer 중 하나여야 합니다."
    yield _raw("tasks", '{"table": "foo", "row": {}}', f'알 수 없는 테이블입니다: "foo". {names}')
    yield _raw(
        "tasks",
        dumps({"table": "x" * 50, "row": {}}),
        '알 수 없는 테이블입니다: "' + "x" * 39 + f".... {names}",
    )


@pytest.mark.parametrize(("table", "bad", "suffix"), list(_raw_text_cases()))
def test_format_errors(fresh: Session, table: str, bad: str, suffix: str) -> None:
    lines = [*PREFIX[table], bad]

    rejects(fresh, lines, f"{len(lines)}번째 줄: {suffix}")


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        pytest.param(
            [HEADER, COMMON, PAY, TASK, line("projects", id=3, slug="x")],
            "5번째 줄: 테이블 순서가 올바르지 않습니다: projects 행이 tasks 행 뒤에 있습니다. "
            "projects, tasks, worklogs, active_timer 순서여야 합니다.",
            id="projects가 tasks 뒤",
        ),
        pytest.param(
            [HEADER, COMMON, PAY, TASK, WORKLOG, line("tasks", id=2)],
            "6번째 줄: 테이블 순서가 올바르지 않습니다: tasks 행이 worklogs 행 뒤에 있습니다. "
            "projects, tasks, worklogs, active_timer 순서여야 합니다.",
            id="tasks가 worklogs 뒤",
        ),
        pytest.param(
            [HEADER, COMMON, PAY, TASK, WORKLOG, TIMER, WORKLOG],
            "7번째 줄: 테이블 순서가 올바르지 않습니다: worklogs 행이 active_timer 행 뒤에 "
            "있습니다. projects, tasks, worklogs, active_timer 순서여야 합니다.",
            id="worklogs가 active_timer 뒤",
        ),
    ],
)
def test_table_order_violation(fresh: Session, lines: list[str], message: str) -> None:
    rejects(fresh, lines, message)


def _row_text(table: str, row: dict[str, Any]) -> str:
    return dumps({"table": table, "row": row})


def _without(table: str, *names: str) -> dict[str, Any]:
    return {k: v for k, v in DEFAULT_ROWS[table].items() if k not in names}


def _field_name_cases() -> Iterator[Any]:
    yield pytest.param(
        _row_text("tasks", {**DEFAULT_ROWS["tasks"], "zzz": 1}),
        "tasks 행에 알 수 없는 필드가 있습니다: zzz.",
        id="알 수 없는 필드",
    )
    yield pytest.param(
        _row_text("tasks", {**DEFAULT_ROWS["tasks"], "b": 1, "a": 2}),
        "tasks 행에 알 수 없는 필드가 있습니다: a, b.",
        id="알 수 없는 필드는 이름순",
    )
    yield pytest.param(
        _row_text("tasks", _without("tasks", "title", "id")),
        "tasks 행에 빠진 필드가 있습니다: id, title.",
        id="빠진 필드는 튜플 순서",
    )
    yield pytest.param(
        _row_text("tasks", {**_without("tasks", "id"), "zzz": 1, "minutes": "x"}),
        "tasks 행에 알 수 없는 필드가 있습니다: minutes, zzz.",
        id="알 수 없는 필드가 빠진 필드보다 먼저",
    )
    yield pytest.param(
        _row_text("tasks", {**DEFAULT_ROWS["tasks"], "zzz": 1, "id": 0}),
        "tasks 행에 알 수 없는 필드가 있습니다: zzz.",
        id="알 수 없는 필드가 값 오류보다 먼저",
    )


@pytest.mark.parametrize(("bad", "suffix"), list(_field_name_cases()))
def test_field_name_errors(fresh: Session, bad: str, suffix: str) -> None:
    lines = [*PREFIX["tasks"], bad]

    rejects(fresh, lines, f"{len(lines)}번째 줄: {suffix}")


def test_value_error_reports_first_invalid_field_in_tuple_order(fresh: Session) -> None:
    bad = line("tasks", title=3, id=0)
    lines = [*PREFIX["tasks"], bad]

    rejects(
        fresh, lines, f"{len(lines)}번째 줄: tasks.id 값이 올바르지 않습니다: 0 ({INT_EXPECT})."
    )


def _duplicate_cases() -> Iterator[Any]:
    yield pytest.param(
        [HEADER, COMMON, line("projects", slug="pay")],
        "3번째 줄: projects 행의 id가 중복됩니다: 1.",
        id="project id",
    )
    yield pytest.param(
        [HEADER, COMMON, line("projects", id=2)],
        '3번째 줄: projects.slug 값이 중복됩니다: "common".',
        id="project slug",
    )
    yield pytest.param(
        [*PREFIX["worklogs"], TASK],
        "5번째 줄: tasks 행의 id가 중복됩니다: 1.",
        id="task id",
    )
    yield pytest.param(
        [*PREFIX["active_timer"], WORKLOG],
        "6번째 줄: worklogs 행의 id가 중복됩니다: 1.",
        id="worklog id",
    )
    yield pytest.param(
        [*PREFIX["active_timer"], TIMER, TIMER],
        "7번째 줄: active_timer 행은 하나만 있을 수 있습니다.",
        id="timer 둘째",
    )


@pytest.mark.parametrize(("lines", "message"), list(_duplicate_cases()))
def test_duplicate_errors(fresh: Session, lines: list[str], message: str) -> None:
    rejects(fresh, lines, message)


def _ref_message(table: str, field: str, target: str, value: int) -> str:
    return f"{table}.{field} 값이 가리키는 {target} 행이 파일에 없습니다: {value}."


def _reference_cases() -> Iterator[Any]:
    yield pytest.param(
        "tasks", line("tasks", project_id=9), _ref_message("tasks", "project_id", "projects", 9)
    )
    yield pytest.param(
        "worklogs",
        line("worklogs", id=2, project_id=9),
        _ref_message("worklogs", "project_id", "projects", 9),
    )
    yield pytest.param(
        "worklogs",
        line("worklogs", id=2, task_id=9),
        _ref_message("worklogs", "task_id", "tasks", 9),
    )
    yield pytest.param(
        "active_timer",
        line("active_timer", project_id=9),
        _ref_message("active_timer", "project_id", "projects", 9),
    )
    yield pytest.param(
        "active_timer",
        line("active_timer", task_id=9),
        _ref_message("active_timer", "task_id", "tasks", 9),
    )


@pytest.mark.parametrize(("table", "bad", "suffix"), list(_reference_cases()))
def test_missing_references(fresh: Session, table: str, bad: str, suffix: str) -> None:
    lines = [*PREFIX[table], bad]

    rejects(fresh, lines, f"{len(lines)}번째 줄: {suffix}")


def _invariant_cases() -> Iterator[Any]:
    done = "(status가 done이면 시각, 아니면 null이어야 합니다)."
    same = "(그 태스크의 project_id와 같은 프로젝트여야 합니다)."
    yield pytest.param(
        "tasks",
        line("tasks", id=2, status="done"),
        f"tasks.done_at 값이 올바르지 않습니다: null {done}",
        id="done인데 done_at 없음",
    )
    yield pytest.param(
        "tasks",
        line("tasks", id=2, status="doing", done_at=STAMP),
        f'tasks.done_at 값이 올바르지 않습니다: "{STAMP}" {done}',
        id="done 아닌데 done_at 있음",
    )
    yield pytest.param(
        "worklogs",
        line("worklogs", id=2, project_id=1),
        f"worklogs.task_id 값이 올바르지 않습니다: 1 {same}",
        id="다른 프로젝트 태스크의 기록",
    )
    yield pytest.param(
        "active_timer",
        line("active_timer", project_id=1),
        f"active_timer.task_id 값이 올바르지 않습니다: 1 {same}",
        id="다른 프로젝트 태스크의 타이머",
    )


@pytest.mark.parametrize(("table", "bad", "suffix"), list(_invariant_cases()))
def test_invariant_errors(fresh: Session, table: str, bad: str, suffix: str) -> None:
    lines = [*PREFIX[table], bad]

    rejects(fresh, lines, f"{len(lines)}번째 줄: {suffix}")


def test_rejects_archived_common_project(fresh: Session) -> None:
    lines = [HEADER, line("projects", archived=True)]

    rejects(
        fresh,
        lines,
        "2번째 줄: projects.archived 값이 올바르지 않습니다: true "
        "(common 프로젝트는 false여야 합니다).",
    )


def test_allows_other_archived_projects(fresh: Session) -> None:
    lines = [HEADER, COMMON, line("projects", id=2, slug="old", archived=True)]

    assert services.import_records(fresh, lines).projects == 2


def test_allows_null_task_id_rows_in_any_project(fresh: Session) -> None:
    lines = [*PREFIX["active_timer"], line("worklogs", id=2, project_id=1, task_id=None)]

    assert services.import_records(fresh, lines).worklogs == 2
