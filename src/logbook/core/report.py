"""주간보고서 데이터 클래스와 표기 도우미. SQLAlchemy를 import하지 않는다.

DB에서 읽어 이 데이터를 만드는 일은 core.services.weekly_report가 맡는다.
시간·비율은 모두 표기가 끝난 문자열로 담아, 템플릿이 표기를 다시 구현하지 않게 한다.
"""

import importlib.resources
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from logbook.core.errors import InvalidInputError

if TYPE_CHECKING:
    import jinja2


@dataclass(frozen=True)
class MatrixRow:
    project: str  # slug
    cells: tuple[str, ...]  # categories 순서의 시간 표기, 0이면 "-"
    total: str
    percent: str


@dataclass(frozen=True)
class TaskLine:
    status: str  # "완료" | "진행" | "할 일" | "중단"
    title: str
    task_id: int
    actual: str  # 보고 주 마지막 날까지의 누적(이번 주만이 아님)
    estimate: str | None
    actual_label: str  # "실제"(완료) | "누적"


@dataclass(frozen=True)
class ProjectSection:
    project: str
    total: str  # 이번 주 이 프로젝트 합계
    tasks: tuple[TaskLine, ...]
    others: tuple[tuple[str, str], ...]  # (카테고리 라벨, 시간), 비면 기타 줄 생략


@dataclass(frozen=True)
class PlanItem:
    title: str
    task_id: int
    estimate: str | None
    carried: bool  # 이번 주 미완료에서 넘어온 후보


@dataclass(frozen=True)
class PlanGroup:
    project: str
    estimate_total: str  # 예상 합계, 하나도 없으면 "0m"
    items: tuple[PlanItem, ...]


@dataclass(frozen=True)
class ReportData:
    title: str
    author: str
    week_label: str  # "2026-W40"
    start: str  # "2026-09-28"
    end: str
    total: str  # "35h"
    log_count: int
    done_task_count: int
    categories: tuple[str, ...]  # 표 머리글(라벨)
    matrix: tuple[MatrixRow, ...]
    sections: tuple[ProjectSection, ...]
    plan: tuple[PlanGroup, ...]


NO_VALUE = "-"


def percent_text(part: int, total: int) -> str:
    """비율의 정수 반올림(half-up) 표기: '54%'. total이나 part가 0이면 '-'."""
    if total == 0 or part == 0:
        return NO_VALUE
    return f"{(200 * part + total) // (2 * total)}%"


TEMPLATE_NAME = "report.md.j2"
_TEMPLATE_FILENAME = "<template>"  # env.from_string이 컴파일할 때 쓰는 파일 이름


def user_template_path(config_file: Path) -> Path:
    """사용자 템플릿 위치: 설정 파일과 같은 폴더의 report.md.j2."""
    return config_file.parent / TEMPLATE_NAME


def _escape_cell(value: object) -> str:
    """Markdown 표 칸 안의 '|'를 백슬래시 + '|'로 바꾼다."""
    return str(value).replace("|", "\\|")


def _build_environment() -> "jinja2.Environment":
    import jinja2  # 지연 import: CLI 시작 때 로드하지 않는다

    env = jinja2.Environment(
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja2.StrictUndefined,
    )
    env.filters["cell"] = _escape_cell
    return env


def _default_source() -> str:
    resource = importlib.resources.files("logbook.core").joinpath("templates", TEMPLATE_NAME)
    return resource.read_text(encoding="utf-8")


def _read_user_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise InvalidInputError(
            f"보고서 템플릿을 UTF-8로 읽을 수 없습니다: {path}. 파일을 UTF-8로 다시 저장하세요."
        ) from error
    except OSError as error:
        raise InvalidInputError(
            f"보고서 템플릿 파일을 열 수 없습니다: {path} ({error.strerror or error})."
        ) from error


def _runtime_lineno(error: BaseException) -> int | None:
    """렌더링 중 예외의 traceback에서 템플릿 코드의 마지막 줄 번호를 찾는다."""
    frames = [
        f for f in traceback.extract_tb(error.__traceback__) if f.filename == _TEMPLATE_FILENAME
    ]
    return frames[-1].lineno if frames else None


def _where(lineno: int | None) -> str:
    return f"{lineno}번째 줄: " if lineno is not None else ""


def _render_user_template(env: "jinja2.Environment", path: Path, data: ReportData) -> str:
    import jinja2

    source = _read_user_source(path)
    try:
        template = env.from_string(source)
    except jinja2.TemplateSyntaxError as error:
        raise InvalidInputError(
            f"보고서 템플릿을 읽지 못했습니다: {path} ({_where(error.lineno)}{error.message}). "
            "기본 템플릿을 쓰려면 이 파일을 지우거나 이름을 바꾸세요."
        ) from error
    try:
        return template.render(data=data)
    except jinja2.UndefinedError as error:
        raise InvalidInputError(
            f"보고서 템플릿에 없는 값을 썼습니다: {path} "
            f"({_where(_runtime_lineno(error))}{error.message}). "
            "쓸 수 있는 값은 README의 '보고서 템플릿' 절을 보세요."
        ) from error
    except Exception as error:
        # CLI 오류는 한 줄이어야 하므로 여러 줄 메시지는 첫 줄만 쓴다.
        detail = str(error).splitlines()[0] if str(error) else ""
        raise InvalidInputError(
            f"보고서 템플릿을 처리하지 못했습니다: {path} "
            f"({_where(_runtime_lineno(error))}{type(error).__name__}: {detail}). "
            "템플릿을 고치거나, 기본 템플릿을 쓰려면 이 파일을 지우거나 이름을 바꾸세요."
        ) from error


def _normalize_output(text: str) -> str:
    """CRLF를 LF로 바꾸고 끝의 빈 줄을 줄바꿈 하나로 맞춘다."""
    return text.replace("\r\n", "\n").rstrip("\n") + "\n"


def render_markdown(data: ReportData, *, template_path: Path | None = None) -> str:
    """template_path가 있고 파일이 있으면 그 템플릿, 아니면 기본 템플릿으로 렌더링한다."""
    env = _build_environment()
    if template_path is not None and template_path.exists():
        text = _render_user_template(env, template_path, data)
    else:
        text = env.from_string(_default_source()).render(data=data)
    return _normalize_output(text)
