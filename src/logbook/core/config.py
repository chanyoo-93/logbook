"""설정 파일(TOML) 읽기·검증과 기본 설정 파일 생성."""

import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast, get_args

import tomli_w

from logbook.core.duration import MAX_MINUTES
from logbook.core.errors import InvalidInputError, LogbookError
from logbook.core.platform import DATA_DIR_NAME, data_dir
from logbook.core.weeks import WeekStart

CONFIG_FILE_NAME = "config.toml"
DB_FILE_NAME = "logbook.db"
MAX_PORT = 65535
# 기본 설정 파일에 쓰는 OS 공통 표기
_DEFAULT_DB_PATH_TEXT = f"~/{DATA_DIR_NAME}/{DB_FILE_NAME}"

DEFAULT_CATEGORIES: Mapping[str, str] = MappingProxyType(
    {
        "dev": "개발",
        "review": "코드리뷰",
        "meeting": "회의",
        "docs": "문서",
        "design": "설계",
        "ops": "운영/배포/장애",
        "support": "문의대응",
        "study": "학습",
        "admin": "행정/기타",
    }
)

_CATEGORY_KEY = re.compile(r"[a-z][a-z0-9_-]*", re.ASCII)
# 오류 메시지에 그대로 보여줄 경로 값의 최대 길이
_MAX_ECHO_CHARS = 40


@dataclass(frozen=True)
class ReportConfig:
    author: str = ""
    title_format: str = "주간업무보고 ({start} ~ {end})"
    include_commits: bool = True


@dataclass(frozen=True)
class GitRepo:
    project: str
    path: Path


@dataclass(frozen=True)
class GitConfig:
    author_email: str = ""
    repos: tuple[GitRepo, ...] = ()


@dataclass(frozen=True)
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass(frozen=True)
class Config:
    """전체 설정.

    categories가 읽기 전용 매핑(MappingProxyType)이라 hash(), copy.deepcopy(),
    pickle, dataclasses.asdict()는 지원하지 않는다. 필요하면 필드를 직접 읽는다.
    """

    db_path: Path
    week_start: WeekStart = "monday"
    default_project: str = "common"
    daily_target_minutes: int = 480
    categories: Mapping[str, str] = field(default_factory=lambda: DEFAULT_CATEGORIES)
    report: ReportConfig = field(default_factory=ReportConfig)
    git: GitConfig = field(default_factory=GitConfig)
    web: WebConfig = field(default_factory=WebConfig)

    def __post_init__(self) -> None:
        # dict를 넘겨도 순서를 유지한 읽기 전용 복사본으로 고정한다.
        object.__setattr__(self, "categories", MappingProxyType(dict(self.categories)))


def _keys(cls: type[Any]) -> frozenset[str]:
    return frozenset(f.name for f in fields(cls))


def _expand_home(raw: str, where: str) -> Path:
    """'~'와 '~' 뒤에 '/' 또는 백슬래시가 오는 경로만 홈 디렉터리 기준으로 바꾼다.

    '~name' 형식은 where(설정 키·파일 또는 환경변수 이름)를 밝혀 InvalidInputError로 거부한다.

    expanduser()는 '~name'을 macOS에서 RuntimeError로, Windows에서 다른 사용자 프로필로 바꾼다.
    """
    if raw == "~":
        return Path.home()
    if raw[:2] in ("~/", "~\\"):
        # '~//x'처럼 구분자가 겹쳐도 홈 밖의 절대 경로가 되지 않게 앞쪽 구분자를 지운다.
        return Path.home() / raw[2:].lstrip("/\\")
    if raw.startswith("~"):
        raise InvalidInputError(
            f"경로가 올바르지 않습니다: {where}의 값 '{raw[:_MAX_ECHO_CHARS]}'. "
            "홈 디렉터리 기준 경로는 '~/'로 시작하세요."
        )
    return Path(raw)


def _path_from_env(name: str, fallback: Path) -> Path:
    """환경변수 name이 비어 있지 않으면 그 경로(~ 확장), 아니면 fallback."""
    value = os.environ.get(name)
    return _expand_home(value, f"환경변수 {name}") if value else fallback


def config_path() -> Path:
    """설정 파일 경로. LOGBOOK_CONFIG가 있으면 그 값, 없으면 ~/.logbook/config.toml."""
    return _path_from_env("LOGBOOK_CONFIG", data_dir() / CONFIG_FILE_NAME)


def default_db_path() -> Path:
    """설정 파일을 보지 않는 DB 경로. LOGBOOK_DB가 있으면 그 값, 없으면 ~/.logbook/logbook.db."""
    return _path_from_env("LOGBOOK_DB", data_dir() / DB_FILE_NAME)


def load_config(path: Path | None = None) -> Config:
    """설정 파일을 읽어 검증한다. 파일이 없으면 기본값을 쓴다."""
    source = config_path() if path is None else _expand_home(str(path), "설정 파일 경로")
    return _Table(source, "", _read_toml(source)).to_config()


def write_default_config(path: Path) -> None:
    """기본 설정 파일을 만든다.

    대상 파일이 이미 있으면 덮어쓰지 않고 FileExistsError를 낸다.
    그 밖의 파일 시스템 오류(상위 경로가 파일, 권한 없음 등)는 LogbookError로 바꾼다.
    """
    target = _expand_home(str(path), "설정 파일 경로")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise LogbookError(
            f"설정 파일 디렉터리를 만들 수 없습니다: {target.parent} "
            f"({error.strerror or error}). 같은 이름의 파일이 있는지, "
            "쓰기 권한이 있는지 확인하세요."
        ) from error
    try:
        with target.open("x", encoding="utf-8", newline="\n") as file:
            file.write(tomli_w.dumps(_default_document()))
    except FileExistsError:
        raise
    except OSError as error:
        raise LogbookError(
            f"설정 파일을 쓸 수 없습니다: {target} ({error.strerror or error}). "
            "쓰기 권한이 있는지 확인하세요."
        ) from error


def _defaults() -> Config:
    return Config(db_path=data_dir() / DB_FILE_NAME)


def _default_document() -> dict[str, object]:
    defaults = _defaults()
    return {
        "db_path": _DEFAULT_DB_PATH_TEXT,
        "week_start": defaults.week_start,
        "default_project": defaults.default_project,
        "daily_target_minutes": defaults.daily_target_minutes,
        "categories": dict(defaults.categories),
        "report": asdict(defaults.report),
        # repos는 쓰지 않는다: 인라인 배열은 뒤에 덧붙인 [[git.repos]] 블록과 충돌한다.
        "git": {"author_email": defaults.git.author_email},
        "web": asdict(defaults.web),
    }


def _read_toml(source: Path) -> dict[str, object]:
    try:
        # utf-8-sig: PowerShell 5.1 등이 붙이는 BOM을 허용한다.
        return tomllib.loads(source.read_bytes().decode("utf-8-sig"))
    except (FileNotFoundError, NotADirectoryError):
        return {}
    except tomllib.TOMLDecodeError as error:
        raise InvalidInputError(
            f"설정 파일의 TOML 문법이 올바르지 않습니다: {source} ({error}). "
            "표시된 위치를 고친 뒤 다시 실행하세요."
        ) from error
    except UnicodeDecodeError as error:
        raise InvalidInputError(
            f"설정 파일을 UTF-8로 읽을 수 없습니다: {source}. 파일을 UTF-8로 다시 저장하세요."
        ) from error
    except OSError as error:
        raise LogbookError(
            f"설정 파일을 열 수 없습니다: {source} ({error.strerror or error}). "
            "경로가 파일인지, 읽기 권한이 있는지 확인하세요."
        ) from error


def _show(value: object) -> str:
    """오류 메시지에 보여줄 TOML 표기 비슷한 값."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, dict):
        return "{...}" if value else "{}"
    if isinstance(value, list):
        return "[...]" if value else "[]"
    return str(value)


@dataclass(frozen=True)
class _Table:
    """TOML 테이블 하나. 오류 메시지에 쓸 파일 경로와 키 접두어("report." 등)를 함께 가진다."""

    source: Path
    prefix: str
    data: Mapping[str, object]

    def _invalid(self, name: str, value: object, expected: str) -> InvalidInputError:
        return InvalidInputError(
            f"설정 값이 올바르지 않습니다: {self.prefix}{name} = {_show(value)} "
            f"(파일: {self.source}). {expected}로 설정하세요."
        )

    def _value(self, name: str, default: object | None) -> object:
        if name in self.data:
            return self.data[name]
        if default is None:
            raise InvalidInputError(
                f"필수 설정 키가 없습니다: '{self.prefix}{name}' (파일: {self.source}). "
                "이 키를 추가하세요."
            )
        return default

    def check_keys(self, allowed: frozenset[str]) -> None:
        for name in self.data:
            if name not in allowed:
                raise InvalidInputError(
                    f"알 수 없는 설정 키입니다: '{self.prefix}{name}' (파일: {self.source}). "
                    "철자를 확인하거나 해당 줄을 지우세요."
                )

    def string(self, name: str, default: str | None = None, *, non_empty: bool = False) -> str:
        value = self._value(name, default)
        if isinstance(value, str) and (value.strip() or not non_empty):
            return value
        raise self._invalid(name, value, "비어 있지 않은 문자열" if non_empty else "문자열")

    def integer(self, name: str, default: int, maximum: int) -> int:
        value = self._value(name, default)
        # bool은 int의 하위 타입이라 따로 막는다.
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise self._invalid(name, value, f"1~{maximum} 사이의 정수")
        return value

    def boolean(self, name: str, default: bool) -> bool:
        value = self._value(name, default)
        if not isinstance(value, bool):
            raise self._invalid(name, value, "true 또는 false")
        return value

    def path(self, name: str) -> Path:
        """~를 확장하고, 상대 경로는 설정 파일이 있는 디렉터리 기준으로 바꾼다."""
        expanded = _expand_home(
            self.string(name, non_empty=True), f"{self.prefix}{name} (파일: {self.source})"
        )
        if expanded.is_absolute():
            return expanded
        return self.source.absolute().parent / expanded

    def table(self, name: str) -> "_Table":
        value = self._value(name, {})
        if not isinstance(value, dict):
            raise self._invalid(name, value, f"테이블([{self.prefix}{name}])")
        return _Table(self.source, f"{self.prefix}{name}.", value)

    def to_config(self) -> Config:
        self.check_keys(_keys(Config))
        defaults = _defaults()
        return Config(
            db_path=self._db_path(defaults.db_path),
            week_start=self._week_start(defaults.week_start),
            default_project=self.string(
                "default_project", defaults.default_project, non_empty=True
            ),
            daily_target_minutes=self.integer(
                "daily_target_minutes", defaults.daily_target_minutes, MAX_MINUTES
            ),
            categories=self._categories() if "categories" in self.data else defaults.categories,
            report=self.table("report").to_report(),
            git=self.table("git").to_git(),
            web=self.table("web").to_web(),
        )

    def _db_path(self, default: Path) -> Path:
        # 환경변수가 이기더라도 파일 값은 검증한다.
        from_file = self.path("db_path") if "db_path" in self.data else default
        return _path_from_env("LOGBOOK_DB", from_file)

    def _week_start(self, default: WeekStart) -> WeekStart:
        value = self._value("week_start", default)
        if value not in get_args(WeekStart):
            raise self._invalid("week_start", value, "'monday' 또는 'sunday'")
        return cast(WeekStart, value)

    def _categories(self) -> Mapping[str, str]:
        table = self.table("categories")
        if not table.data:
            raise self._invalid("categories", table.data, "카테고리를 하나 이상 담은 테이블")
        for key in table.data:
            if _CATEGORY_KEY.fullmatch(key) is None:
                raise InvalidInputError(
                    f"카테고리 키가 올바르지 않습니다: '{key}' (파일: {self.source}). "
                    "영문 소문자로 시작하고 영문 소문자·숫자·'_'·'-'만 쓰세요."
                )
        return {key: table.string(key, non_empty=True) for key in table.data}

    def to_report(self) -> ReportConfig:
        self.check_keys(_keys(ReportConfig))
        defaults = ReportConfig()
        return ReportConfig(
            author=self.string("author", defaults.author),
            title_format=self.string("title_format", defaults.title_format),
            include_commits=self.boolean("include_commits", defaults.include_commits),
        )

    def to_git(self) -> GitConfig:
        self.check_keys(_keys(GitConfig))
        return GitConfig(
            author_email=self.string("author_email", GitConfig().author_email),
            repos=self._repos(),
        )

    def _repos(self) -> tuple[GitRepo, ...]:
        value = self._value("repos", [])
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise self._invalid("repos", value, f"테이블 배열([[{self.prefix}repos]])")
        return tuple(
            _Table(self.source, f"{self.prefix}repos[{number}].", item).to_repo()
            for number, item in enumerate(value, start=1)
        )

    def to_repo(self) -> GitRepo:
        self.check_keys(_keys(GitRepo))
        return GitRepo(project=self.string("project", non_empty=True), path=self.path("path"))

    def to_web(self) -> WebConfig:
        self.check_keys(_keys(WebConfig))
        defaults = WebConfig()
        return WebConfig(
            host=self.string("host", defaults.host, non_empty=True),
            port=self.integer("port", defaults.port, MAX_PORT),
        )
