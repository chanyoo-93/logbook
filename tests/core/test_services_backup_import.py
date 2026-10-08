"""JSONL 가져오기(import_records) 테스트."""

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, event, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from logbook.core import db, services
from logbook.core.errors import DatabaseBusyError, InvalidInputError
from logbook.core.models import ActiveTimer, Project, Task, WorkLog
from logbook.core.services import backup, backup_import
from logbook.core.taskstatus import TaskStatus

NOW = datetime(2026, 10, 8, 3, 0, 0, tzinfo=UTC)
STAMP = "2026-09-01T00:00:00+00:00"
LS = chr(0x2028)
PS = chr(0x2029)
NEL = chr(0x85)
BOM = chr(0xFEFF)

INT_EXPECT = "1 이상 9223372036854775807 이하의 정수"
OPT_INT_EXPECT = "null 또는 " + INT_EXPECT
SLUG_EXPECT = "영문 소문자나 숫자로 시작하고 영문 소문자·숫자·'-'·'_'만 쓴 32자 이하 문자열"
STATUS_EXPECT = "todo, doing, done, dropped 중 하나"
DATE_EXPECT = "YYYY-MM-DD 형식의 날짜"
TIME_EXPECT = "시간대가 있는 ISO 8601 시각"
ENVELOPE_MESSAGE = (
    '레코드 형식이 올바르지 않습니다. {"row": {...}, "table": "..."} 형식이어야 합니다.'
)
NON_EMPTY_MESSAGE = (
    "데이터가 있는 데이터베이스에는 가져올 수 없습니다. 새 데이터베이스에서 실행하세요 "
    "(예: LOGBOOK_DB를 새 경로로 바꾸고 'lb init' 후 'lb import')."
)
NO_COMMON_MESSAGE = "가져올 파일에 common 프로젝트가 없습니다."

DEFAULT_ROWS: dict[str, dict[str, Any]] = {
    "projects": {
        "id": 1,
        "slug": "common",
        "name": "공통",
        "description": None,
        "color": None,
        "archived": False,
        "created_at": STAMP,
    },
    "tasks": {
        "id": 1,
        "project_id": 2,
        "title": "작업",
        "description": None,
        "status": "todo",
        "category": None,
        "estimate_minutes": None,
        "planned_week": None,
        "due_date": None,
        "external_ref": None,
        "created_at": STAMP,
        "updated_at": STAMP,
        "done_at": None,
    },
    "worklogs": {
        "id": 1,
        "project_id": 2,
        "task_id": 1,
        "category": "dev",
        "date": "2026-10-07",
        "minutes": 30,
        "note": "메모",
        "started_at": None,
        "ended_at": None,
        "created_at": STAMP,
    },
    "active_timer": {
        "id": 1,
        "project_id": 2,
        "task_id": 1,
        "category": "dev",
        "note": "타이머",
        "started_at": STAMP,
    },
}


def _dumps(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _header(**changes: Any) -> str:
    header: dict[str, Any] = {
        "type": "logbook-export",
        "format": 1,
        "schema_version": db.SCHEMA_VERSION,
        "exported_at": "2026-10-08T03:00:00+00:00",
    }
    header.update(changes)
    return _dumps({key: value for key, value in header.items() if value != "<missing>"})


HEADER = _header()


def _line(table: str, **changes: Any) -> str:
    row = {**DEFAULT_ROWS[table], **changes}
    return _dumps({"table": table, "row": row})


COMMON = _line("projects")
PAY = _line("projects", id=2, slug="pay", name="결제")
TASK = _line("tasks")
WORKLOG = _line("worklogs")
TIMER = _line("active_timer")

# 테이블 줄 앞에 와야 하는 정상 줄(머리글 포함)
PREFIX = {
    "projects": [HEADER],
    "tasks": [HEADER, COMMON, PAY],
    "worklogs": [HEADER, COMMON, PAY, TASK],
    "active_timer": [HEADER, COMMON, PAY, TASK, WORKLOG],
}


def _valid() -> list[str]:
    return [HEADER, COMMON, PAY, TASK, WORKLOG, TIMER]


def _assert_unchanged(session: Session) -> None:
    slugs = [p.slug for p in session.scalars(select(Project))]
    assert slugs == ["common"]
    for model in (Task, WorkLog, ActiveTimer):
        assert session.scalar(select(func.count()).select_from(model)) == 0


@pytest.fixture
def fresh(session: Session) -> Session:
    """lb init 직후와 같은 DB(common 프로젝트만 있음)."""
    services.ensure_common_project(session)
    session.flush()
    return session


def _rejects(fresh: Session, lines: list[str], message: str) -> None:
    with pytest.raises(InvalidInputError) as excinfo:
        services.import_records(fresh, lines)
    assert str(excinfo.value) == message
    _assert_unchanged(fresh)


# --- 성공 경로와 왕복 ---


def test_imports_valid_file_and_returns_counts(fresh: Session) -> None:
    counts = services.import_records(fresh, _valid())

    assert counts == services.BackupCounts(projects=2, tasks=1, worklogs=1, timers=1)
    fresh.flush()
    assert [(p.id, p.slug) for p in fresh.scalars(select(Project).order_by(Project.id))] == [
        (1, "common"),
        (2, "pay"),
    ]
    task = fresh.scalars(select(Task)).one()
    assert (task.id, task.project_id, task.status) == (1, 2, TaskStatus.TODO)
    worklog = fresh.scalars(select(WorkLog)).one()
    assert (worklog.date, worklog.minutes, worklog.note) == (date(2026, 10, 7), 30, "메모")
    assert fresh.scalars(select(ActiveTimer)).one().note == "타이머"


def test_allows_db_with_only_common_or_no_projects(session: Session) -> None:
    counts = services.import_records(session, [HEADER, COMMON])

    assert counts == services.BackupCounts(projects=1, tasks=0, worklogs=0, timers=0)


def test_allows_trailing_newlines_and_crlf(fresh: Session) -> None:
    lines = [line + "\r\n" for line in _valid()]

    counts = services.import_records(fresh, lines)

    assert counts.projects == 2


def test_imports_lines_with_unescaped_line_separators(fresh: Session) -> None:
    note = f"앞{LS}가운데{PS}가운데{NEL}뒤"
    lines = [HEADER, COMMON, PAY, TASK, _line("worklogs", note=note)]
    assert note in lines[-1]

    services.import_records(fresh, lines)
    fresh.flush()

    assert fresh.scalars(select(WorkLog)).one().note == note


def _new_engine(path: Path) -> Engine:
    engine = db.create_engine_for(path)
    db.init_db(engine)
    return engine


def _populate(s: Session) -> None:
    common = services.ensure_common_project(s)
    pay = Project(id=5, slug="pay", name="결제", description="설명", color="#112233", archived=True)
    pay.created_at = datetime(2026, 9, 1, tzinfo=UTC)
    s.add(pay)
    s.flush()
    mixed = f"앞{LS}가운데{PS}가운데{NEL}뒤 한글"
    micro = datetime(2026, 10, 8, 3, 0, 0, 123456, tzinfo=UTC)
    full = Task(
        project_id=pay.id,
        title=mixed,
        description=mixed,
        status=TaskStatus.DONE,
        category="dev",
        estimate_minutes=90,
        planned_week="2026-W41",
        due_date=date(2026, 10, 9),
        external_ref="JIRA-1",
        created_at=micro,
        updated_at=micro,
        done_at=micro,
    )
    sparse = Task(project_id=common.id, title="빈 필드", created_at=NOW, updated_at=NOW)
    s.add_all([full, sparse])
    s.flush()
    s.add_all(
        [
            WorkLog(
                project_id=pay.id,
                task_id=full.id,
                category="dev",
                date=date(2026, 10, 7),
                minutes=90,
                note=mixed,
                started_at=micro,
                ended_at=micro,
                created_at=micro,
            ),
            WorkLog(
                project_id=common.id,
                category="meeting",
                date=date(2026, 10, 6),
                minutes=30,
                note="",
                created_at=NOW,
            ),
            ActiveTimer(project_id=pay.id, category="dev", note=mixed, started_at=micro),
        ]
    )
    s.flush()


def test_export_import_export_is_byte_identical_except_header_time(
    session: Session, tmp_path: Path
) -> None:
    _populate(session)
    first, counts = services.export_records(session, now=NOW)
    other = _new_engine(tmp_path / "other.db")
    try:
        with Session(other, expire_on_commit=False) as target:
            services.ensure_common_project(target)
            target.flush()
            imported = services.import_records(target, first)
            target.flush()
            second, _ = services.export_records(
                target, now=datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC)
            )
            micro = target.scalars(select(WorkLog).order_by(WorkLog.id)).first()
            assert micro is not None
            assert micro.started_at == datetime(2026, 10, 8, 3, 0, 0, 123456, tzinfo=UTC)
            assert micro.created_at.microsecond == 123456
    finally:
        other.dispose()

    assert imported == counts
    assert second[1:] == first[1:]
    assert json.loads(second[0])["exported_at"] != json.loads(first[0])["exported_at"]
    assert {k: v for k, v in json.loads(second[0]).items() if k != "exported_at"} == {
        k: v for k, v in json.loads(first[0]).items() if k != "exported_at"
    }


def test_imports_common_with_id_3_and_new_ids_follow_max(fresh: Session) -> None:
    lines = [
        HEADER,
        _line("projects", id=3),
        _line("projects", id=4, slug="pay"),
        _line("worklogs", id=7, project_id=3, task_id=None),
    ]

    services.import_records(fresh, lines)
    fresh.flush()

    assert fresh.scalars(select(Project).where(Project.slug == "common")).one().id == 3
    project = Project(slug="new", name="새", created_at=NOW)
    worklog = WorkLog(
        project_id=3, category="dev", date=date(2026, 10, 8), minutes=5, note="", created_at=NOW
    )
    fresh.add_all([project, worklog])
    fresh.flush()
    assert project.id == 5
    assert worklog.id == 8


# --- 빈 DB 확인 ---


def _add_task(s: Session) -> None:
    common = services.ensure_common_project(s)
    s.add(Task(project_id=common.id, title="t", created_at=NOW, updated_at=NOW))


def _add_worklog(s: Session) -> None:
    common = services.ensure_common_project(s)
    s.add(
        WorkLog(
            project_id=common.id,
            category="dev",
            date=date(2026, 10, 8),
            minutes=5,
            note="",
            created_at=NOW,
        )
    )


def _add_timer(s: Session) -> None:
    common = services.ensure_common_project(s)
    s.add(ActiveTimer(project_id=common.id, category="dev", note="", started_at=NOW))


def _add_project(s: Session) -> None:
    s.add(Project(slug="extra", name="추가", created_at=NOW))


@pytest.mark.parametrize("add", [_add_task, _add_worklog, _add_timer, _add_project])
def test_rejects_db_with_data_and_changes_nothing(fresh: Session, add: Any) -> None:
    add(fresh)
    fresh.flush()
    before = [p.slug for p in fresh.scalars(select(Project).order_by(Project.id))]

    with pytest.raises(InvalidInputError) as excinfo:
        services.import_records(fresh, _valid())

    assert str(excinfo.value) == NON_EMPTY_MESSAGE
    assert [p.slug for p in fresh.scalars(select(Project).order_by(Project.id))] == before


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
    yield pytest.param([_header(type="other")], other.format('"other"'), id="type 다름")
    long_value = '"' + "x" * 39 + "..."
    yield pytest.param([_header(type="x" * 50)], other.format(long_value), id="type 길이 제한")
    for label, value, shown in (
        ("true", True, "true"),
        ("1.0", 1.0, "1.0"),
        ("문자열", "1", '"1"'),
        ("없음", "<missing>", "null"),
        ("2", 2, "2"),
    ):
        yield pytest.param([_header(format=value)], version.format(shown), id=f"format {label}")
    for label, value, shown in (
        ("문자열", "2", '"2"'),
        ("0", 0, "0"),
        ("true", True, "true"),
        ("없음", "<missing>", "null"),
    ):
        yield pytest.param(
            [_header(schema_version=value)], schema.format(shown), id=f"schema {label}"
        )
    newer = db.SCHEMA_VERSION + 1
    yield pytest.param(
        [_header(schema_version=newer)],
        f"더 새로운 logbook에서 내보낸 파일입니다 (스키마 {newer}). "
        "logbook을 업데이트한 뒤 가져오세요.",
        id="더 새로운 스키마",
    )


@pytest.mark.parametrize(("lines", "message"), list(_header_cases()))
def test_header_errors(fresh: Session, lines: list[str], message: str) -> None:
    _rejects(fresh, lines, message)


def test_header_only_reports_missing_common(fresh: Session) -> None:
    _rejects(fresh, [HEADER], NO_COMMON_MESSAGE)


def test_header_then_blank_lines_reports_missing_common(fresh: Session) -> None:
    _rejects(fresh, [HEADER, "", " "], NO_COMMON_MESSAGE)


def test_other_projects_without_common_is_error(fresh: Session) -> None:
    _rejects(fresh, [HEADER, PAY], NO_COMMON_MESSAGE)


@pytest.mark.parametrize("count", [1, 2])
def test_strips_bom_at_start_of_first_line(fresh: Session, count: int) -> None:
    lines = [BOM * count + HEADER, COMMON]

    counts = services.import_records(fresh, lines)

    assert counts.projects == 1


def test_first_line_with_only_bom_counts_as_blank(fresh: Session) -> None:
    lines = [BOM, HEADER, "not json"]

    _rejects(fresh, lines, "3번째 줄: JSON 형식이 올바르지 않습니다.")


def test_skips_blank_lines_before_header(fresh: Session) -> None:
    counts = services.import_records(fresh, ["", "  ", HEADER, COMMON])

    assert counts.projects == 1


def test_error_line_numbers_count_blank_lines(fresh: Session) -> None:
    lines = ["", HEADER, "", "  ", COMMON, "", "not json"]

    _rejects(fresh, lines, "7번째 줄: JSON 형식이 올바르지 않습니다.")


# --- 줄별 오류 ---


def _raw(table: str, line: str, suffix: str) -> Any:
    return pytest.param(table, line, suffix, id=f"{table}: {suffix[:40]}")


def _field_case(table: str, field: str, value: Any, expect: str) -> Any:
    shown = _dumps(value)
    suffix = f"{table}.{field} 값이 올바르지 않습니다: {shown} ({expect})."
    return pytest.param(
        table, _line(table, **{field: value}), suffix, id=f"{table}.{field}={shown}"
    )


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

    _rejects(fresh, lines, f"{len(lines)}번째 줄: {suffix}")


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
        _dumps({"table": "x" * 50, "row": {}}),
        '알 수 없는 테이블입니다: "' + "x" * 39 + f".... {names}",
    )


@pytest.mark.parametrize(("table", "bad", "suffix"), list(_raw_text_cases()))
def test_format_errors(fresh: Session, table: str, bad: str, suffix: str) -> None:
    lines = [*PREFIX[table], bad]

    _rejects(fresh, lines, f"{len(lines)}번째 줄: {suffix}")


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        pytest.param(
            [HEADER, COMMON, PAY, TASK, _line("projects", id=3, slug="x")],
            "5번째 줄: 테이블 순서가 올바르지 않습니다: projects 행이 tasks 행 뒤에 있습니다. "
            "projects, tasks, worklogs, active_timer 순서여야 합니다.",
            id="projects가 tasks 뒤",
        ),
        pytest.param(
            [HEADER, COMMON, PAY, TASK, WORKLOG, _line("tasks", id=2)],
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
    _rejects(fresh, lines, message)


def _row_text(table: str, row: dict[str, Any]) -> str:
    return _dumps({"table": table, "row": row})


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

    _rejects(fresh, lines, f"{len(lines)}번째 줄: {suffix}")


def test_value_error_reports_first_invalid_field_in_tuple_order(fresh: Session) -> None:
    bad = _line("tasks", title=3, id=0)
    lines = [*PREFIX["tasks"], bad]

    _rejects(
        fresh, lines, f"{len(lines)}번째 줄: tasks.id 값이 올바르지 않습니다: 0 ({INT_EXPECT})."
    )


def _duplicate_cases() -> Iterator[Any]:
    yield pytest.param(
        [HEADER, COMMON, _line("projects", slug="pay")],
        "3번째 줄: projects 행의 id가 중복됩니다: 1.",
        id="project id",
    )
    yield pytest.param(
        [HEADER, COMMON, _line("projects", id=2)],
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
    _rejects(fresh, lines, message)


def _ref_message(table: str, field: str, target: str, value: int) -> str:
    return f"{table}.{field} 값이 가리키는 {target} 행이 파일에 없습니다: {value}."


def _reference_cases() -> Iterator[Any]:
    yield pytest.param(
        "tasks", _line("tasks", project_id=9), _ref_message("tasks", "project_id", "projects", 9)
    )
    yield pytest.param(
        "worklogs",
        _line("worklogs", id=2, project_id=9),
        _ref_message("worklogs", "project_id", "projects", 9),
    )
    yield pytest.param(
        "worklogs",
        _line("worklogs", id=2, task_id=9),
        _ref_message("worklogs", "task_id", "tasks", 9),
    )
    yield pytest.param(
        "active_timer",
        _line("active_timer", project_id=9),
        _ref_message("active_timer", "project_id", "projects", 9),
    )
    yield pytest.param(
        "active_timer",
        _line("active_timer", task_id=9),
        _ref_message("active_timer", "task_id", "tasks", 9),
    )


@pytest.mark.parametrize(("table", "bad", "suffix"), list(_reference_cases()))
def test_missing_references(fresh: Session, table: str, bad: str, suffix: str) -> None:
    lines = [*PREFIX[table], bad]

    _rejects(fresh, lines, f"{len(lines)}번째 줄: {suffix}")


def _invariant_cases() -> Iterator[Any]:
    done = "(status가 done이면 시각, 아니면 null이어야 합니다)."
    same = "(그 태스크의 project_id와 같은 프로젝트여야 합니다)."
    yield pytest.param(
        "tasks",
        _line("tasks", id=2, status="done"),
        f"tasks.done_at 값이 올바르지 않습니다: null {done}",
        id="done인데 done_at 없음",
    )
    yield pytest.param(
        "tasks",
        _line("tasks", id=2, status="doing", done_at=STAMP),
        f'tasks.done_at 값이 올바르지 않습니다: "{STAMP}" {done}',
        id="done 아닌데 done_at 있음",
    )
    yield pytest.param(
        "worklogs",
        _line("worklogs", id=2, project_id=1),
        f"worklogs.task_id 값이 올바르지 않습니다: 1 {same}",
        id="다른 프로젝트 태스크의 기록",
    )
    yield pytest.param(
        "active_timer",
        _line("active_timer", project_id=1),
        f"active_timer.task_id 값이 올바르지 않습니다: 1 {same}",
        id="다른 프로젝트 태스크의 타이머",
    )


@pytest.mark.parametrize(("table", "bad", "suffix"), list(_invariant_cases()))
def test_invariant_errors(fresh: Session, table: str, bad: str, suffix: str) -> None:
    lines = [*PREFIX[table], bad]

    _rejects(fresh, lines, f"{len(lines)}번째 줄: {suffix}")


def test_rejects_archived_common_project(fresh: Session) -> None:
    lines = [HEADER, _line("projects", archived=True)]

    _rejects(
        fresh,
        lines,
        "2번째 줄: projects.archived 값이 올바르지 않습니다: true "
        "(common 프로젝트는 false여야 합니다).",
    )


def test_allows_other_archived_projects(fresh: Session) -> None:
    lines = [HEADER, COMMON, _line("projects", id=2, slug="old", archived=True)]

    assert services.import_records(fresh, lines).projects == 2


def test_allows_null_task_id_rows_in_any_project(fresh: Session) -> None:
    lines = [*PREFIX["active_timer"], _line("worklogs", id=2, project_id=1, task_id=None)]

    assert services.import_records(fresh, lines).worklogs == 2


# --- 쓰기 단계 오류 ---


class FakeSqliteError(Exception):
    def __init__(self, errorname: str) -> None:
        super().__init__("fake")
        self.sqlite_errorname = errorname


def _fail_inserts(engine: Engine, error: Exception) -> None:
    def raise_on_insert(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
    ) -> None:
        if statement.lstrip().upper().startswith("INSERT"):
            raise error

    event.listen(engine, "before_cursor_execute", raise_on_insert)


def test_flush_integrity_error_becomes_import_error(fresh: Session, engine: Engine) -> None:
    error = IntegrityError("INSERT ...", None, Exception("UNIQUE constraint failed: x"))
    _fail_inserts(engine, error)

    with pytest.raises(InvalidInputError) as excinfo:
        services.import_records(fresh, _valid())

    assert str(excinfo.value) == (
        "가져온 데이터가 데이터베이스 규칙에 맞지 않습니다: UNIQUE constraint failed: x. "
        "'lb export'로 만든 파일인지 확인하세요."
    )


def test_flush_operational_error_is_not_translated(
    engine: Engine,
) -> None:
    with db.session_scope(engine) as setup:
        services.ensure_common_project(setup)
    error = OperationalError("INSERT ...", None, FakeSqliteError("SQLITE_BUSY"))
    _fail_inserts(engine, error)

    with pytest.raises(DatabaseBusyError) as excinfo, db.session_scope(engine) as session:
        services.import_records(session, _valid())

    assert not isinstance(excinfo.value, InvalidInputError)
    assert excinfo.value.__cause__ is error
    with Session(engine) as check:
        assert [p.slug for p in check.scalars(select(Project))] == ["common"]


def test_validation_kind_tables_are_consistent() -> None:
    assert tuple(backup_import._KINDS) == backup.TABLE_ORDER
    assert set(backup_import._REFERENCES) == set(backup.TABLE_ORDER)
    used_kinds = set()
    for table, fields in backup.FIELDS.items():
        assert tuple(backup_import._KINDS[table]) == fields, table
        used_kinds.update(backup_import._KINDS[table].values())
    base_kinds = {kind.removeprefix("opt_") for kind in used_kinds}
    # 모든 종류에 변환기와 기대 문구가 있다(opt_ 접두 종류는 접두 없는 변환기를 쓴다).
    assert base_kinds <= set(backup_import._CONVERTERS)
    # 쓰이지 않는 변환기·문구가 남아 있지 않다.
    assert set(backup_import._CONVERTERS) == base_kinds
    assert set(backup_import._EXPECTED) == used_kinds
