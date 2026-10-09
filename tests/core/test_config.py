"""logbook.core.config 단위 테스트."""

import re
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from logbook.core.config import (
    DEFAULT_CATEGORIES,
    Config,
    GitConfig,
    GitRepo,
    ReportConfig,
    WebConfig,
    config_path,
    load_config,
    write_default_config,
)
from logbook.core.config import default_db_path as configured_db_path
from logbook.core.errors import InvalidInputError, LogbookError

EXPECTED_CATEGORIES = {
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


def write_toml(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """아직 만들지 않은 설정 파일 경로."""
    return tmp_path / "conf" / "config.toml"


def default_db_path() -> Path:
    return Path.home() / ".logbook" / "logbook.db"


def defaults() -> Config:
    return Config(db_path=default_db_path())


# --- 기본값 ---


def test_default_categories_follow_spec_in_order() -> None:
    assert dict(DEFAULT_CATEGORIES) == EXPECTED_CATEGORIES
    assert list(DEFAULT_CATEGORIES) == list(EXPECTED_CATEGORIES)


def test_default_categories_are_immutable() -> None:
    with pytest.raises(TypeError):
        DEFAULT_CATEGORIES["x"] = "y"  # type: ignore[index]


def test_missing_file_gives_defaults(config_file: Path) -> None:
    config = load_config(config_file)

    assert config == defaults()
    assert config.db_path == default_db_path()
    assert config.week_start == "monday"
    assert config.default_project == "common"
    assert config.daily_target_minutes == 480
    assert config.categories == DEFAULT_CATEGORIES
    assert config.report == ReportConfig(
        author="", title_format="주간업무보고 ({start} ~ {end})", include_commits=True
    )
    assert config.git == GitConfig(author_email="", repos=())
    assert config.web == WebConfig(host="127.0.0.1", port=8765)


def test_load_config_without_path_reads_default_location() -> None:
    write_toml(Path.home() / ".logbook" / "config.toml", 'week_start = "sunday"\n')

    assert load_config().week_start == "sunday"


def test_missing_parent_directory_gives_defaults(tmp_path: Path) -> None:
    # 부모가 파일인 경로: macOS는 NotADirectoryError, Windows는 FileNotFoundError.
    not_a_dir = write_toml(tmp_path / "plain-file", "")

    assert load_config(not_a_dir / "config.toml") == defaults()


def test_config_categories_are_immutable_copy() -> None:
    source = {"dev": "개발"}
    config = Config(db_path=Path("db.sqlite"), categories=source)
    source["ops"] = "운영"

    assert dict(config.categories) == {"dev": "개발"}
    with pytest.raises(TypeError):
        config.categories["x"] = "y"  # type: ignore[index]


def test_config_fixture_returns_defaults_with_tmp_db(config: Config, tmp_home: Path) -> None:
    assert config == Config(db_path=tmp_home / "logbook.db")


# --- 값 읽기 ---


def test_partial_toml_keeps_other_defaults(config_file: Path) -> None:
    write_toml(config_file, 'week_start = "sunday"\n')

    assert load_config(config_file) == replace(defaults(), week_start="sunday")


def test_full_spec_example_is_loaded(config_file: Path) -> None:
    write_toml(
        config_file,
        """
db_path = "~/.logbook/logbook.db"
week_start = "monday"
default_project = "payment"
daily_target_minutes = 420

[report]
author = "홍길동"
title_format = "주간보고 {start}"
include_commits = false

[git]
author_email = "me@example.com"

[web]
host = "localhost"
port = 9000
""",
    )

    config = load_config(config_file)

    assert config.default_project == "payment"
    assert config.daily_target_minutes == 420
    assert config.report == ReportConfig(
        author="홍길동", title_format="주간보고 {start}", include_commits=False
    )
    assert config.git == GitConfig(author_email="me@example.com", repos=())
    assert config.web == WebConfig(host="localhost", port=9000)


def test_categories_table_replaces_defaults_in_file_order(config_file: Path) -> None:
    write_toml(config_file, '[categories]\nzeta = "제타"\nalpha-1 = "알파"\nb_2 = "베타"\n')

    categories = load_config(config_file).categories

    assert dict(categories) == {"zeta": "제타", "alpha-1": "알파", "b_2": "베타"}
    assert list(categories) == ["zeta", "alpha-1", "b_2"]
    with pytest.raises(TypeError):
        categories["x"] = "y"  # type: ignore[index]


@pytest.mark.parametrize("minutes", [1, 1440])
def test_daily_target_minutes_bounds_are_valid(config_file: Path, minutes: int) -> None:
    write_toml(config_file, f"daily_target_minutes = {minutes}\n")

    assert load_config(config_file).daily_target_minutes == minutes


# --- 경로 ---


def test_db_path_tilde_is_expanded(config_file: Path) -> None:
    write_toml(config_file, 'db_path = "~/x/db.sqlite"\n')

    assert load_config(config_file).db_path == Path.home() / "x" / "db.sqlite"


def test_absolute_db_path_is_kept(config_file: Path, tmp_path: Path) -> None:
    target = tmp_path / "elsewhere" / "logbook.db"
    # OS 고유 형식(Windows 백슬래시)은 TOML 리터럴 문자열로 쓴다.
    write_toml(config_file, f"db_path = '{target}'\n")

    assert load_config(config_file).db_path == target


def test_relative_db_path_is_resolved_against_config_dir(
    config_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_toml(config_file, 'db_path = "data/logbook.db"\n')
    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert load_config(config_file).db_path == config_file.parent / "data" / "logbook.db"


def test_relative_config_path_still_gives_absolute_db_path(
    config_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_toml(config_file, 'db_path = "data/logbook.db"\n')
    monkeypatch.chdir(tmp_path)

    db_path = load_config(Path("conf") / "config.toml").db_path

    assert db_path.is_absolute()
    assert db_path == tmp_path / "conf" / "data" / "logbook.db"


def test_logbook_db_env_wins_over_toml(
    config_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_toml(config_file, 'db_path = "~/x/db.sqlite"\n')
    monkeypatch.setenv("LOGBOOK_DB", str(tmp_path / "env.db"))

    assert load_config(config_file).db_path == tmp_path / "env.db"


def test_logbook_db_env_is_expanded(monkeypatch: pytest.MonkeyPatch, config_file: Path) -> None:
    monkeypatch.setenv("LOGBOOK_DB", "~/env.db")

    assert load_config(config_file).db_path == Path.home() / "env.db"


def test_empty_logbook_db_env_is_ignored(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_toml(config_file, 'db_path = "~/x/db.sqlite"\n')
    monkeypatch.setenv("LOGBOOK_DB", "")

    assert load_config(config_file).db_path == Path.home() / "x" / "db.sqlite"
    assert load_config(config_file.with_name("missing.toml")).db_path == default_db_path()


def test_git_repos_are_parsed_with_expanded_paths(config_file: Path) -> None:
    write_toml(
        config_file,
        """
[git]
author_email = "me@example.com"

[[git.repos]]
project = "payment"
path = "~/work/payment-server"

[[git.repos]]
project = "admin"
path = "repos/admin-web"
""",
    )

    git = load_config(config_file).git

    assert git == GitConfig(
        author_email="me@example.com",
        repos=(
            GitRepo(project="payment", path=Path.home() / "work" / "payment-server"),
            GitRepo(project="admin", path=config_file.parent / "repos" / "admin-web"),
        ),
    )


# --- config_path ---


def test_config_path_defaults_to_home_logbook_dir() -> None:
    assert config_path() == Path.home() / ".logbook" / "config.toml"


def test_logbook_config_env_changes_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = write_toml(tmp_path / "custom" / "my.toml", 'week_start = "sunday"\n')
    monkeypatch.setenv("LOGBOOK_CONFIG", str(custom))

    assert config_path() == custom
    assert load_config().week_start == "sunday"


def test_logbook_config_env_is_expanded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGBOOK_CONFIG", "~/cfg/my.toml")

    assert config_path() == Path.home() / "cfg" / "my.toml"


def test_empty_logbook_config_env_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGBOOK_CONFIG", "")

    assert config_path() == Path.home() / ".logbook" / "config.toml"


# --- 검증 오류 ---


def assert_invalid(config_file: Path, text: str, *fragments: str) -> None:
    write_toml(config_file, text)
    with pytest.raises(InvalidInputError) as excinfo:
        load_config(config_file)
    message = str(excinfo.value)
    for fragment in (str(config_file), *fragments):
        assert fragment in message


def test_invalid_toml_syntax_names_file(config_file: Path) -> None:
    assert_invalid(config_file, "week_start = \n", "TOML", "line 1")


def test_non_utf8_file_is_rejected(config_file: Path) -> None:
    config_file.parent.mkdir(parents=True)
    config_file.write_bytes('[report]\nauthor = "홍길동"\n'.encode("cp949"))

    with pytest.raises(InvalidInputError, match="UTF-8") as excinfo:
        load_config(config_file)
    assert str(config_file) in str(excinfo.value)


def test_utf8_bom_file_is_accepted(config_file: Path) -> None:
    # Windows PowerShell 5.1과 일부 편집기는 UTF-8 파일 앞에 BOM을 붙인다.
    config_file.parent.mkdir(parents=True)
    config_file.write_bytes(b"\xef\xbb\xbf" + b'week_start = "sunday"\n')

    assert load_config(config_file).week_start == "sunday"


def test_utf8_bom_file_with_korean_labels_is_accepted(config_file: Path) -> None:
    config_file.parent.mkdir(parents=True)
    config_file.write_bytes(b"\xef\xbb\xbf" + '[categories]\ndev = "개발"\n'.encode())

    assert dict(load_config(config_file).categories) == {"dev": "개발"}


def test_unreadable_config_path_raises_logbook_error(tmp_path: Path) -> None:
    # 디렉터리: Windows는 PermissionError, macOS는 IsADirectoryError.
    with pytest.raises(LogbookError, match=re.escape(str(tmp_path))):
        load_config(tmp_path)


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ('week_strat = "sunday"\n', "week_strat"),
        ('[report]\nautor = "홍길동"\n', "report.autor"),
        ('[git]\nemail = "me@example.com"\n', "git.email"),
        ("[web]\nprot = 9000\n", "web.prot"),
        ('[[git.repos]]\nproject = "a"\npath = "b"\nbranch = "main"\n', "git.repos[1].branch"),
        ('[extra]\nkey = "value"\n', "extra"),
    ],
)
def test_unknown_key_is_rejected_by_name(config_file: Path, text: str, key: str) -> None:
    assert_invalid(config_file, text, f"'{key}'")


def test_invalid_week_start(config_file: Path) -> None:
    assert_invalid(config_file, 'week_start = "friday"\n', "week_start", "friday", "sunday")


@pytest.mark.parametrize("value", ["-1", "0", "1441", '"480"', "true", "480.0"])
def test_invalid_daily_target_minutes(config_file: Path, value: str) -> None:
    assert_invalid(config_file, f"daily_target_minutes = {value}\n", "daily_target_minutes")


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
def test_local_web_hosts_are_accepted(config_file: Path, host: str) -> None:
    write_toml(config_file, f'[web]\nhost = "{host}"\n')

    assert load_config(config_file).web.host == host


@pytest.mark.parametrize("host", ["0.0.0.0", "::1", "192.168.0.10"])
def test_non_local_web_host_is_rejected(config_file: Path, host: str) -> None:
    write_toml(config_file, f'[web]\nhost = "{host}"\n')

    with pytest.raises(InvalidInputError) as excinfo:
        load_config(config_file)

    assert str(excinfo.value) == (
        f'설정 값이 올바르지 않습니다: web.host = "{host}" (파일: {config_file}). '
        "설정할 수 있는 값: '127.0.0.1' 또는 'localhost'."
    )


def test_empty_web_host_reports_non_empty_string_first(config_file: Path) -> None:
    assert_invalid(config_file, '[web]\nhost = ""\n', "web.host", "비어 있지 않은 문자열")


@pytest.mark.parametrize("value", ["0", "70000", "true", '"8765"'])
def test_invalid_web_port(config_file: Path, value: str) -> None:
    assert_invalid(config_file, f"[web]\nport = {value}\n", "web.port", "65535")


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ('default_project = ""\n', "default_project"),
        ("default_project = 3\n", "default_project"),
        ('db_path = ""\n', "db_path"),
        ("db_path = 1\n", "db_path"),
        ('[web]\nhost = " "\n', "web.host"),
        ("[report]\nauthor = 1\n", "report.author"),
        ("[report]\ntitle_format = []\n", "report.title_format"),
        ('[report]\ninclude_commits = "yes"\n', "report.include_commits"),
        ("[git]\nauthor_email = false\n", "git.author_email"),
        ('report = "x"\n', "report"),
        ('git = "x"\n', "git"),
        ("web = 1\n", "web"),
        ('categories = "dev"\n', "categories"),
    ],
)
def test_wrong_value_type_names_key(config_file: Path, text: str, key: str) -> None:
    assert_invalid(config_file, text, key)


def test_empty_categories_table_is_invalid(config_file: Path) -> None:
    assert_invalid(config_file, "[categories]\n", "categories")


def test_non_string_category_label_is_invalid(config_file: Path) -> None:
    assert_invalid(config_file, '[categories]\ndev = "개발"\nops = 3\n', "categories.ops")


def test_empty_category_label_is_invalid(config_file: Path) -> None:
    assert_invalid(config_file, '[categories]\ndev = ""\n', "categories.dev")


@pytest.mark.parametrize("key", ["Dev", "1dev", "_dev", '"개발"', '"de v"'])
def test_invalid_category_key(config_file: Path, key: str) -> None:
    assert_invalid(config_file, f'[categories]\n{key} = "개발"\n', key.strip('"'))


@pytest.mark.parametrize(
    "text",
    [
        '[git]\nrepos = ["a"]\n',
        '[git]\nrepos = "a"\n',
        '[git]\nrepos = [{project = "a", path = "b"}, 1]\n',
    ],
)
def test_git_repos_must_be_array_of_tables(config_file: Path, text: str) -> None:
    assert_invalid(config_file, text, "git.repos")


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ('[[git.repos]]\nproject = "payment"\n', "git.repos[1].path"),
        ('[[git.repos]]\npath = "~/a"\n', "git.repos[1].project"),
        (
            '[[git.repos]]\nproject = "a"\npath = "a"\n[[git.repos]]\nproject = "b"\n',
            "git.repos[2].path",
        ),
    ],
)
def test_git_repo_missing_key_is_invalid(config_file: Path, text: str, key: str) -> None:
    assert_invalid(config_file, text, key)


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ('[[git.repos]]\nproject = ""\npath = "~/a"\n', "git.repos[1].project"),
        ('[[git.repos]]\nproject = "a"\npath = 1\n', "git.repos[1].path"),
    ],
)
def test_git_repo_invalid_value(config_file: Path, text: str, key: str) -> None:
    assert_invalid(config_file, text, key)


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ('db_path = "~x.db"\n', "db_path"),
        ('[[git.repos]]\nproject = "a"\npath = "~work/repo"\n', "git.repos[1].path"),
    ],
)
def test_tilde_user_path_in_file_is_rejected(config_file: Path, text: str, key: str) -> None:
    assert_invalid(config_file, text, key, "'~/'")


def test_tilde_user_path_message_echoes_at_most_40_chars(config_file: Path) -> None:
    value = "~" + "x" * 60
    write_toml(config_file, f'db_path = "{value}"\n')

    with pytest.raises(InvalidInputError) as excinfo:
        load_config(config_file)
    message = str(excinfo.value)
    assert value[:40] in message
    assert value[:41] not in message


def test_tilde_user_path_in_logbook_db_env_is_rejected(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOGBOOK_DB", "~x")

    with pytest.raises(InvalidInputError, match="LOGBOOK_DB"):
        load_config(config_file)
    with pytest.raises(InvalidInputError, match="LOGBOOK_DB"):
        configured_db_path()


def test_tilde_user_path_in_logbook_config_env_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGBOOK_CONFIG", "~x/c.toml")

    with pytest.raises(InvalidInputError, match="LOGBOOK_CONFIG"):
        config_path()
    with pytest.raises(InvalidInputError, match="LOGBOOK_CONFIG"):
        load_config()


@pytest.mark.parametrize(
    ("raw", "parts"),
    [
        ("~", ()),
        ("~/a", ("a",)),
        ("~\\a", ("a",)),
        ("~/a/b.db", ("a", "b.db")),
        # 구분자가 겹쳐도 홈 밖(절대 경로)으로 빠지지 않는다.
        ("~//a", ("a",)),
        ("~/\\a", ("a",)),
    ],
)
def test_home_relative_paths_resolve_under_home(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch, raw: str, parts: tuple[str, ...]
) -> None:
    expected = isolated_home.joinpath(*parts)
    monkeypatch.setenv("LOGBOOK_DB", raw)

    assert configured_db_path() == expected


@pytest.mark.parametrize(
    ("raw", "parts"),
    [("~", ()), ("~/a", ("a",)), ("~\\a", ("a",))],
)
def test_home_relative_toml_paths_resolve_under_home(
    config_file: Path, isolated_home: Path, raw: str, parts: tuple[str, ...]
) -> None:
    # 리터럴 문자열이라 백슬래시를 그대로 쓴다.
    write_toml(config_file, f"db_path = '{raw}'\n")

    assert load_config(config_file).db_path == isolated_home.joinpath(*parts)


def test_tilde_user_path_argument_is_rejected() -> None:
    with pytest.raises(InvalidInputError, match="'~/'"):
        load_config(Path("~x/c.toml"))
    with pytest.raises(InvalidInputError, match="'~/'"):
        write_default_config(Path("~x/c.toml"))


def test_invalid_toml_db_path_is_rejected_even_when_env_is_set(
    config_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOGBOOK_DB", str(tmp_path / "env.db"))

    assert_invalid(config_file, "db_path = 1\n", "db_path")


# --- write_default_config ---


def test_write_default_config_roundtrip_equals_defaults(config_file: Path) -> None:
    write_default_config(config_file)

    assert load_config(config_file) == load_config(config_file.with_name("missing.toml"))
    assert load_config(config_file) == defaults()


def test_write_default_config_roundtrip_with_logbook_db_env(
    config_file: Path, tmp_home: Path
) -> None:
    write_default_config(config_file)

    assert load_config(config_file) == Config(db_path=tmp_home / "logbook.db")


def test_write_default_config_document(config_file: Path) -> None:
    write_default_config(config_file)

    document = tomllib.loads(config_file.read_text(encoding="utf-8"))

    assert document == {
        "db_path": "~/.logbook/logbook.db",
        "week_start": "monday",
        "default_project": "common",
        "daily_target_minutes": 480,
        "categories": EXPECTED_CATEGORIES,
        "report": {
            "author": "",
            "title_format": "주간업무보고 ({start} ~ {end})",
            "include_commits": True,
        },
        "git": {"author_email": ""},
        "web": {"host": "127.0.0.1", "port": 8765},
    }
    assert list(document["categories"]) == list(EXPECTED_CATEGORIES)


def test_write_default_config_accepts_appended_git_repos(config_file: Path) -> None:
    # SPEC 3절처럼 기본 파일 끝에 [[git.repos]] 블록을 덧붙여도 읽혀야 한다.
    write_default_config(config_file)
    with config_file.open("a", encoding="utf-8", newline="\n") as file:
        file.write('\n[[git.repos]]\nproject = "payment"\npath = "repos/payment"\n')

    assert load_config(config_file).git.repos == (
        GitRepo(project="payment", path=config_file.parent / "repos" / "payment"),
    )


def test_write_default_config_is_utf8_with_lf(config_file: Path) -> None:
    write_default_config(config_file)

    raw = config_file.read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")
    text = raw.decode("utf-8")
    for label in EXPECTED_CATEGORIES.values():
        assert label in text


def test_write_default_config_creates_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "config.toml"

    write_default_config(target)

    assert target.is_file()


def test_write_default_config_expands_tilde() -> None:
    write_default_config(Path("~/cfg/config.toml"))

    assert (Path.home() / "cfg" / "config.toml").is_file()


def test_write_default_config_does_not_overwrite(config_file: Path) -> None:
    write_default_config(config_file)
    first = config_file.read_bytes()

    with pytest.raises(FileExistsError):
        write_default_config(config_file)
    assert config_file.read_bytes() == first


def test_write_default_config_keeps_user_edits(config_file: Path) -> None:
    write_toml(config_file, 'week_start = "sunday"\n')
    before = config_file.read_bytes()

    with pytest.raises(FileExistsError):
        write_default_config(config_file)
    assert config_file.read_bytes() == before


def test_write_default_config_parent_is_file_raises_logbook_error(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")

    with pytest.raises(LogbookError, match=re.escape(str(blocker))) as info:
        write_default_config(blocker / "config.toml")
    assert not isinstance(info.value, FileExistsError)
    assert blocker.read_bytes() == b""


def test_write_default_config_write_failure_raises_logbook_error(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny(*args: object, **kwargs: object) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "open", deny)

    with pytest.raises(LogbookError, match=re.escape(str(config_file))) as info:
        write_default_config(config_file)
    assert not isinstance(info.value, OSError)
