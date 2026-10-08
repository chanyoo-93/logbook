"""전체 데이터 JSONL 가져오기.

파일 전체를 먼저 검증하고 통과했을 때만 빈 DB(common만 있음)에 원래 id로 쓴다.
형식 상수와 필드 목록은 backup.py의 것을 그대로 쓴다.
"""

import datetime as dt
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from logbook.core import db
from logbook.core.duration import MAX_MINUTES, echo_input
from logbook.core.errors import InvalidInputError
from logbook.core.models import ActiveTimer, Project, Task, WorkLog
from logbook.core.services.backup import (
    EXPORT_TYPE,
    FIELDS,
    FORMAT_VERSION,
    MODELS,
    TABLE_ORDER,
    BackupCounts,
)
from logbook.core.services.projects import COMMON_SLUG, is_valid_slug
from logbook.core.taskstatus import TaskStatus

MAX_SQLITE_INTEGER = 2**63 - 1
BOM = chr(0xFEFF)
_MIN_UTC_DATE = dt.date(1, 1, 2)
_MAX_UTC_DATE = dt.date(9999, 12, 30)
_TABLE_LIST = ", ".join(TABLE_ORDER)
_INT_RANGE = f"1 이상 {MAX_SQLITE_INTEGER} 이하의 정수"
_SLUG_RULE = "영문 소문자나 숫자로 시작하고 영문 소문자·숫자·'-'·'_'만 쓴 32자 이하 문자열"
_STATUS_VALUES = tuple(status.value for status in TaskStatus)

# 필드별 값 종류. 키 순서는 FIELDS와 같아야 한다(왕복 테스트가 확인한다).
_KINDS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "projects": {
            "id": "id",
            "slug": "slug",
            "name": "str",
            "description": "opt_str",
            "color": "opt_str",
            "archived": "bool",
            "created_at": "datetime",
        },
        "tasks": {
            "id": "id",
            "project_id": "id",
            "title": "str",
            "description": "opt_str",
            "status": "status",
            "category": "opt_str",
            "estimate_minutes": "opt_id",
            "planned_week": "opt_str",
            "due_date": "opt_date",
            "external_ref": "opt_str",
            "created_at": "datetime",
            "updated_at": "datetime",
            "done_at": "opt_datetime",
        },
        "worklogs": {
            "id": "id",
            "project_id": "id",
            "task_id": "opt_id",
            "category": "str",
            "date": "date",
            "minutes": "minutes",
            "note": "str",
            "started_at": "opt_datetime",
            "ended_at": "opt_datetime",
            "created_at": "datetime",
        },
        "active_timer": {
            "id": "timer_id",
            "project_id": "id",
            "task_id": "opt_id",
            "category": "str",
            "note": "str",
            "started_at": "datetime",
        },
    }
)

_EXPECTED: Mapping[str, str] = MappingProxyType(
    {
        "id": _INT_RANGE,
        "opt_id": f"null 또는 {_INT_RANGE}",
        "minutes": f"1 이상 {MAX_MINUTES} 이하의 정수",
        "timer_id": "1",
        "slug": _SLUG_RULE,
        "status": f"{', '.join(_STATUS_VALUES)} 중 하나",
        "bool": "true 또는 false",
        "str": "문자열",
        "opt_str": "null 또는 문자열",
        "date": "YYYY-MM-DD 형식의 날짜",
        "opt_date": "null 또는 YYYY-MM-DD 형식의 날짜",
        "datetime": "시간대가 있는 ISO 8601 시각",
        "opt_datetime": "null 또는 시간대가 있는 ISO 8601 시각",
    }
)

# 테이블별 (필드, 가리키는 테이블). 필드 튜플 순서로 검사한다.
_REFERENCES: Mapping[str, tuple[tuple[str, str], ...]] = MappingProxyType(
    {
        "projects": (),
        "tasks": (("project_id", "projects"),),
        "worklogs": (("project_id", "projects"), ("task_id", "tasks")),
        "active_timer": (("project_id", "projects"), ("task_id", "tasks")),
    }
)


def _show(value: object) -> str:
    """오류 문구에 넣는 JSON 값(길면 줄인다)."""
    return echo_input(json.dumps(value, ensure_ascii=False))


def _to_int(value: object, maximum: int = MAX_SQLITE_INTEGER) -> int:
    """bool·float을 받지 않는 1 이상 maximum 이하의 정수."""
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(value)
    return value


def _to_minutes(value: object) -> int:
    return _to_int(value, MAX_MINUTES)


def _to_timer_id(value: object) -> int:
    if type(value) is not int or value != 1:
        raise ValueError(value)
    return value


def _to_slug(value: object) -> str:
    if type(value) is not str or not is_valid_slug(value):
        raise ValueError(value)
    return value


def _to_status(value: object) -> TaskStatus:
    if type(value) is not str or value not in _STATUS_VALUES:
        raise ValueError(value)
    return TaskStatus(value)


def _to_bool(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError(value)
    return value


def _to_str(value: object) -> str:
    if type(value) is not str:
        raise ValueError(value)
    return value


def _to_date(value: object) -> dt.date:
    if type(value) is not str:
        raise ValueError(value)
    parsed = dt.date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError(value)
    return parsed


def _to_datetime(value: object) -> dt.datetime:
    """시간대가 있는 시각. 어느 시간대로 보여도 범위를 넘지 않도록 UTC 날짜에 하루 여유를 둔다."""
    if type(value) is not str:
        raise ValueError(value)
    parsed = dt.datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError(value)
    try:
        utc_date = parsed.astimezone(dt.UTC).date()
    except OverflowError:
        raise ValueError(value) from None
    if not _MIN_UTC_DATE <= utc_date <= _MAX_UTC_DATE:
        raise ValueError(value)
    return parsed


_CONVERTERS: Mapping[str, Callable[[object], Any]] = MappingProxyType(
    {
        "id": _to_int,
        "minutes": _to_minutes,
        "timer_id": _to_timer_id,
        "slug": _to_slug,
        "status": _to_status,
        "bool": _to_bool,
        "str": _to_str,
        "date": _to_date,
        "datetime": _to_datetime,
    }
)


def _convert(kind: str, value: object) -> Any:
    """값 하나를 검증해 int·str·bool·date·aware datetime 등으로 바꾼다. 틀리면 ValueError."""
    if kind.startswith("opt_"):
        return None if value is None else _convert(kind.removeprefix("opt_"), value)
    return _CONVERTERS[kind](value)


@dataclass
class _ImportState:
    """파일을 앞에서부터 읽으며 쌓는 검증 상태. 이 모듈 안에서만 쓴다."""

    last_table: str | None = None
    ids: dict[str, set[int]] = field(default_factory=lambda: {t: set() for t in TABLE_ORDER})
    slugs: set[str] = field(default_factory=set)
    task_projects: dict[int, int] = field(default_factory=dict)
    has_common: bool = False
    objects: dict[str, list[Any]] = field(default_factory=lambda: {t: [] for t in TABLE_ORDER})


def _load_object(text: str) -> Any:
    """JSON 한 줄을 읽는다. 읽을 수 없으면 ValueError(깊은 중첩 RecursionError 포함)."""
    try:
        return json.loads(text)
    except (ValueError, RecursionError) as error:
        raise ValueError(text) from error


def _check_header(text: str | None) -> None:
    if text is None:
        raise InvalidInputError("logbook 내보내기 파일이 아닙니다 (내용이 없습니다).")
    try:
        header = _load_object(text)
    except ValueError:
        header = None
    if not isinstance(header, dict) or "type" not in header:
        raise InvalidInputError("logbook 내보내기 파일이 아닙니다 (첫 줄에 type 값이 없습니다).")
    if header["type"] != EXPORT_TYPE:
        raise InvalidInputError(
            f"logbook 내보내기 파일이 아닙니다 (첫 줄의 type 값: {_show(header['type'])})."
        )
    version = header.get("format")
    if type(version) is not int or version != FORMAT_VERSION:
        raise InvalidInputError(
            f"지원하지 않는 내보내기 형식 버전입니다: {_show(version)}. "
            f"이 버전의 logbook이 읽을 수 있는 형식: {FORMAT_VERSION}"
        )
    schema = header.get("schema_version")
    if type(schema) is not int or schema < 1:
        raise InvalidInputError(f"내보내기 파일의 스키마 버전이 올바르지 않습니다: {_show(schema)}")
    if schema > db.SCHEMA_VERSION:
        raise InvalidInputError(
            f"더 새로운 logbook에서 내보낸 파일입니다 (스키마 {schema}). "
            "logbook을 업데이트한 뒤 가져오세요."
        )


def _parse_envelope(n: int, text: str) -> tuple[str, dict[str, Any]]:
    """한 줄을 {"table", "row"} 봉투로 읽는다(검사 1~3단계)."""
    try:
        record = _load_object(text)
    except ValueError:
        raise InvalidInputError(f"{n}번째 줄: JSON 형식이 올바르지 않습니다.") from None
    if (
        not isinstance(record, dict)
        or set(record) != {"table", "row"}
        or not isinstance(record["table"], str)
        or not isinstance(record["row"], dict)
    ):
        raise InvalidInputError(
            f'{n}번째 줄: 레코드 형식이 올바르지 않습니다. {{"row": {{...}}, "table": "..."}} '
            "형식이어야 합니다."
        )
    table = record["table"]
    if table not in FIELDS:
        raise InvalidInputError(
            f"{n}번째 줄: 알 수 없는 테이블입니다: {_show(table)}. "
            f"{_TABLE_LIST} 중 하나여야 합니다."
        )
    return table, record["row"]


def _check_order(n: int, table: str, state: _ImportState) -> None:
    previous = state.last_table
    if previous is not None and TABLE_ORDER.index(table) < TABLE_ORDER.index(previous):
        raise InvalidInputError(
            f"{n}번째 줄: 테이블 순서가 올바르지 않습니다: {table} 행이 {previous} 행 뒤에 "
            f"있습니다. {_TABLE_LIST} 순서여야 합니다."
        )
    state.last_table = table


def _check_field_names(n: int, table: str, row: dict[str, Any]) -> None:
    expected = FIELDS[table]
    unknown = sorted(set(row) - set(expected))
    if unknown:
        raise InvalidInputError(
            f"{n}번째 줄: {table} 행에 알 수 없는 필드가 있습니다: {', '.join(unknown)}."
        )
    missing = [name for name in expected if name not in row]
    if missing:
        raise InvalidInputError(
            f"{n}번째 줄: {table} 행에 빠진 필드가 있습니다: {', '.join(missing)}."
        )


def _convert_fields(n: int, table: str, row: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name in FIELDS[table]:
        kind = _KINDS[table][name]
        try:
            values[name] = _convert(kind, row[name])
        except ValueError:
            raise InvalidInputError(
                f"{n}번째 줄: {table}.{name} 값이 올바르지 않습니다: {_show(row[name])} "
                f"({_EXPECTED[kind]})."
            ) from None
    return values


def _check_unique(n: int, table: str, values: dict[str, Any], state: _ImportState) -> None:
    if table == "active_timer" and state.ids[table]:
        raise InvalidInputError(f"{n}번째 줄: active_timer 행은 하나만 있을 수 있습니다.")
    if values["id"] in state.ids[table]:
        raise InvalidInputError(f"{n}번째 줄: {table} 행의 id가 중복됩니다: {values['id']}.")
    if table == "projects" and values["slug"] in state.slugs:
        raise InvalidInputError(
            f"{n}번째 줄: projects.slug 값이 중복됩니다: {_show(values['slug'])}."
        )


def _check_references(n: int, table: str, values: dict[str, Any], state: _ImportState) -> None:
    for name, target in _REFERENCES[table]:
        ref = values[name]
        if ref is not None and ref not in state.ids[target]:
            raise InvalidInputError(
                f"{n}번째 줄: {table}.{name} 값이 가리키는 {target} 행이 파일에 없습니다: {ref}."
            )


def _check_invariants(
    n: int, table: str, values: dict[str, Any], row: dict[str, Any], state: _ImportState
) -> None:
    if table == "projects" and values["slug"] == COMMON_SLUG and values["archived"]:
        raise InvalidInputError(
            f"{n}번째 줄: projects.archived 값이 올바르지 않습니다: true "
            "(common 프로젝트는 false여야 합니다)."
        )
    if table == "tasks" and (values["status"] is TaskStatus.DONE) != (
        values["done_at"] is not None
    ):
        raise InvalidInputError(
            f"{n}번째 줄: tasks.done_at 값이 올바르지 않습니다: "
            f"{_show(row['done_at'])} "
            "(status가 done이면 시각, 아니면 null이어야 합니다)."
        )
    task_id = values.get("task_id")
    if task_id is not None and state.task_projects[task_id] != values["project_id"]:
        raise InvalidInputError(
            f"{n}번째 줄: {table}.task_id 값이 올바르지 않습니다: {task_id} "
            "(그 태스크의 project_id와 같은 프로젝트여야 합니다)."
        )


def _record(n: int, text: str, state: _ImportState) -> None:
    """데이터 줄 하나를 검사 순서대로 검증하고 상태에 반영한다."""
    table, row = _parse_envelope(n, text)
    _check_order(n, table, state)
    _check_field_names(n, table, row)
    values = _convert_fields(n, table, row)
    _check_unique(n, table, values, state)
    _check_references(n, table, values, state)
    _check_invariants(n, table, values, row, state)
    state.ids[table].add(values["id"])
    if table == "projects":
        state.slugs.add(values["slug"])
        state.has_common = state.has_common or values["slug"] == COMMON_SLUG
    elif table == "tasks":
        state.task_projects[values["id"]] = values["project_id"]
    state.objects[table].append(MODELS[table](**values))


def _parse_lines(lines: Iterable[str]) -> _ImportState:
    """모든 줄을 검증한다. 빈 줄은 건너뛰되 줄 번호에는 센다."""
    state = _ImportState()
    header_seen = False
    for n, raw in enumerate(lines, start=1):
        text = (raw.lstrip(BOM) if n == 1 else raw).strip()
        if not text:
            continue
        if not header_seen:
            _check_header(text)
            header_seen = True
            continue
        _record(n, text, state)
    if not header_seen:
        _check_header(None)
    if not state.has_common:
        raise InvalidInputError("가져올 파일에 common 프로젝트가 없습니다.")
    return state


def _existing_common(s: Session) -> Project | None:
    """빈 DB인지 확인하고 기존 common 프로젝트(없으면 None)를 돌려준다."""
    projects = s.scalars(select(Project)).all()
    has_other_project = any(project.slug != COMMON_SLUG for project in projects)
    has_rows = any(
        s.scalar(select(func.count()).select_from(model)) for model in (Task, WorkLog, ActiveTimer)
    )
    if has_other_project or has_rows:
        raise InvalidInputError(
            "데이터가 있는 데이터베이스에는 가져올 수 없습니다. 새 데이터베이스에서 실행하세요 "
            "(예: LOGBOOK_DB를 새 경로로 바꾸고 'lb init' 후 'lb import')."
        )
    return next(iter(projects), None)


def _write(s: Session, state: _ImportState, common: Project | None) -> None:
    """common을 먼저 지우고(INSERT가 먼저 나가 UNIQUE(slug)가 깨지지 않게) 원래 id로 넣는다."""
    try:
        if common is not None:
            s.delete(common)
            s.flush()
        for table in TABLE_ORDER:
            s.add_all(state.objects[table])
            s.flush()
    except IntegrityError as error:
        raise InvalidInputError(
            f"가져온 데이터가 데이터베이스 규칙에 맞지 않습니다: {error.orig}. "
            "'lb export'로 만든 파일인지 확인하세요."
        ) from error


def import_records(s: Session, lines: Iterable[str]) -> BackupCounts:
    """빈 DB(common만 있음)에 JSONL 줄을 원래 id로 복원한다.

    파일 전체를 검증한 뒤에만 쓴다. 검증 실패는 InvalidInputError이고 DB는 바뀌지 않는다.
    쓰는 도중 IntegrityError가 나면 InvalidInputError로 바꿔 던지며, 롤백은 호출자의
    session_scope가 한다(이 함수는 커밋도 롤백도 하지 않는다).
    """
    # 빈 DB 확인과 쓰기 사이에 잠금이 없다. 단일 사용자 로컬 도구라 허용한다.
    common = _existing_common(s)
    state = _parse_lines(lines)
    _write(s, state, common)
    return BackupCounts(
        projects=len(state.objects["projects"]),
        tasks=len(state.objects["tasks"]),
        worklogs=len(state.objects["worklogs"]),
        timers=len(state.objects["active_timer"]),
    )
