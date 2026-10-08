"""lb init: 설정 파일·DB 생성, 재실행, 업그레이드, 기본 프로젝트 점검."""

import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

import pytest
from sqlalchemy.orm import Session
from typer.testing import Result

from logbook.core import db, services
from tests.helpers import add_extra_column, set_version

MISSING_DEFAULT_WARNING = (
    "주의: 설정의 default_project가 가리키는 프로젝트가 없습니다: 'payment'. "
    "'lb project add payment <이름>'으로 만들거나 설정 파일의 default_project를 바꾸세요.\n"
)
ARCHIVED_DEFAULT_WARNING = (
    "주의: 설정의 default_project가 보관된 프로젝트입니다: 'payment'. "
    "설정 파일의 default_project를 바꾸세요.\n"
)


def write_config(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def project_slugs(open_db: Callable[[], AbstractContextManager[Session]]) -> list[str]:
    with open_db() as s:
        return [p.slug for p in services.list_projects(s, include_archived=True)]


def assert_db_released(db_path: Path) -> None:
    """엔진이 dispose되어 Windows에서도 DB 파일을 옮길 수 있는지 확인한다."""
    os.replace(db_path, db_path.with_name("moved.db"))


def test_first_run_creates_config_db_and_common(lb: Callable[..., Result], tmp_home: Path) -> None:
    cfg = tmp_home / "config.toml"
    db_path = tmp_home / "logbook.db"

    result = lb("init")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == (
        f"✔ 설정 파일 생성: {cfg}\n"
        f"✔ 데이터베이스 생성: {db_path} (스키마 v1)\n"
        "✔ 기본 프로젝트 준비: common (공통)\n"
    )
    assert result.stderr == ""
    assert cfg.is_file()
    assert db_path.is_file()
    assert_db_released(db_path)


def test_rerun_keeps_config_and_checks_db(
    lb: Callable[..., Result],
    tmp_home: Path,
    open_db: Callable[[], AbstractContextManager[Session]],
) -> None:
    cfg = tmp_home / "config.toml"
    db_path = tmp_home / "logbook.db"
    assert lb("init").exit_code == 0
    original = cfg.read_bytes()

    result = lb("init")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == (
        f"· 설정 파일 유지 (이미 있음): {cfg}\n"
        f"✔ 데이터베이스 확인: {db_path} (스키마 v1, 최신)\n"
        "✔ 기본 프로젝트 준비: common (공통)\n"
    )
    assert result.stderr == ""
    assert cfg.read_bytes() == original
    assert project_slugs(open_db) == ["common"]


def test_empty_db_file_is_created_as_new(
    lb: Callable[..., Result],
    tmp_home: Path,
    open_db: Callable[[], AbstractContextManager[Session]],
) -> None:
    db_path = tmp_home / "logbook.db"
    db_path.write_bytes(b"")

    result = lb("init")

    assert result.exit_code == 0, result.stderr
    assert result.stdout.splitlines()[1] == f"✔ 데이터베이스 생성: {db_path} (스키마 v1)"
    assert project_slugs(open_db) == ["common"]


def test_pending_migration_is_reported_as_upgrade(
    lb: Callable[..., Result], tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_home / "logbook.db"
    assert lb("init").exit_code == 0
    monkeypatch.setattr(db, "SCHEMA_VERSION", 2)
    monkeypatch.setattr(db, "MIGRATIONS", {2: add_extra_column})

    result = lb("init")

    assert result.exit_code == 0, result.stderr
    assert result.stdout.splitlines()[1] == f"✔ 데이터베이스 업그레이드: {db_path} (v1 → v2)"
    assert_db_released(db_path)


def test_newer_db_fails_without_stdout(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"
    assert lb("init").exit_code == 0
    engine = db.create_engine_for(db_path)
    try:
        set_version(engine, 99)
    finally:
        engine.dispose()

    result = lb("init")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "오류: 데이터베이스가 더 새로운 버전(v99)입니다. 최신 버전의 logbook이 필요합니다.\n"
    )
    assert_db_released(db_path)


def test_broken_config_fails_before_creating_db(lb: Callable[..., Result], tmp_home: Path) -> None:
    write_config(tmp_home / "config.toml", "week_start = \n")

    result = lb("init")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("오류: 설정 파일의 TOML 문법이 올바르지 않습니다:")
    assert not (tmp_home / "logbook.db").exists()


def test_missing_default_project_warns_and_keeps_common(
    lb: Callable[..., Result],
    tmp_home: Path,
    open_db: Callable[[], AbstractContextManager[Session]],
) -> None:
    write_config(tmp_home / "config.toml", 'default_project = "payment"\n')

    result = lb("init")

    assert result.exit_code == 0
    assert result.stdout.splitlines()[2] == "✔ 기본 프로젝트 준비: common (공통)"
    assert result.stderr == MISSING_DEFAULT_WARNING
    # 경고는 세션 안에서 처리하므로 common 생성이 롤백되지 않는다.
    assert project_slugs(open_db) == ["common"]


@pytest.mark.parametrize("slug", ["Payment", "my proj"])
def test_missing_invalid_default_project_warns_with_placeholder(
    lb: Callable[..., Result], tmp_home: Path, slug: str
) -> None:
    # 쓸 수 없는 slug로 만들라고 안내하지 않는다(core의 NotFoundError 문구와 같은 규칙).
    write_config(tmp_home / "config.toml", f'default_project = "{slug}"\n')

    result = lb("init")

    assert result.exit_code == 0
    assert result.stderr == (
        f"주의: 설정의 default_project가 가리키는 프로젝트가 없습니다: '{slug}'. "
        "'lb project add <slug> <이름>'으로 만들거나 설정 파일의 default_project를 바꾸세요.\n"
    )


def test_archived_default_project_warns(lb: Callable[..., Result], tmp_home: Path) -> None:
    write_config(tmp_home / "config.toml", 'default_project = "payment"\n')
    assert lb("init").exit_code == 0
    assert lb("project", "add", "payment", "결제 서버").exit_code == 0
    assert lb("project", "archive", "payment").exit_code == 0

    result = lb("init")

    assert result.exit_code == 0
    assert result.stderr == ARCHIVED_DEFAULT_WARNING


def test_korean_path_with_space(
    lb: Callable[..., Result], tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_home / "데이터 폴더" / "logbook.db"
    monkeypatch.setenv("LOGBOOK_DB", str(db_path))

    result = lb("init")

    assert result.exit_code == 0, result.stderr
    assert result.stdout.splitlines()[1] == f"✔ 데이터베이스 생성: {db_path} (스키마 v1)"
    assert db_path.is_file()
    assert_db_released(db_path)
