"""lb export, lb import."""

import json
import os
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.core import platform, services
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import parse_week
from tests.cli.helpers import OpenDb, assert_rejected, run_ok

# W40(2026-09-28 ~ 10-04) 안, 정오 부근이라 날짜 경계와 멀다
DONE_AT = datetime(2026, 9, 30, 3, 0, tzinfo=UTC)
COUNTS = "(프로젝트 2 · 태스크 2 · 기록 2 · 타이머 0)"
SEPARATORS = (chr(0x2028), chr(0x2029), chr(0x85))
STAMP = "20261001-093000"


def seed(
    open_db: OpenDb, today: date, *, memo: str = "결제 재시도", title: str = "결제 구현"
) -> None:
    """프로젝트 2(common 포함), 태스크 2, 기록 2가 있는 데이터."""
    with open_db() as s:
        services.create_project(s, "payment", "결제 서버")
        services.add_worklog(
            s, minutes=120, note=memo, project_slug="payment", category="dev",
            work_date=date(2026, 9, 30), today=today,
        )  # fmt: skip
        services.add_worklog(
            s, minutes=60, note="주간 회의", category="meeting",
            work_date=date(2026, 10, 1), today=today,
        )  # fmt: skip
        task = services.create_task(
            s, title=title, project_slug="payment", estimate_minutes=180,
            planned_week=parse_week("2026-W40", today=today, week_start="monday"),
        )  # fmt: skip
        task.status = TaskStatus.DONE
        task.done_at = DONE_AT
        services.create_task(
            s, title="환불 API 구현", project_slug="payment", estimate_minutes=480,
            planned_week=parse_week("2026-W41", today=today, week_start="monday"),
        )  # fmt: skip


@pytest.fixture
def seeded(initialized: Path, open_db: OpenDb, today: date) -> Path:
    seed(open_db, today)
    return initialized


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def switch_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lb: Callable[..., Result]
) -> Callable[[str], Path]:
    """LOGBOOK_DB를 새 경로로 바꾸고 lb init을 실행한다. 새 DB 경로를 돌려준다."""

    def switch(name: str) -> Path:
        folder = tmp_path / name
        folder.mkdir()
        db_path = folder / "logbook.db"
        monkeypatch.setenv("LOGBOOK_DB", str(db_path))
        run_ok(lb, "init")
        return db_path

    return switch


def test_export_writes_file_and_prints_summary(
    lb: Callable[..., Result], seeded: Path, workdir: Path
) -> None:
    result = run_ok(lb, "export", "-o", "b.jsonl")

    assert result.stdout == f"✔ 내보냈습니다: b.jsonl {COUNTS}\n"
    assert result.stderr == ""
    data = (workdir / "b.jsonl").read_bytes()
    assert b"\r" not in data
    assert data.endswith(b"\n")
    # 머리글 1줄 + 프로젝트 2 + 태스크 2 + 기록 2
    assert len(data.decode("utf-8").splitlines()) == 1 + 2 + 2 + 2
    assert json.loads(data.decode("utf-8").splitlines()[0])["exported_at"].startswith("2026-10-01")


def test_export_default_file_name(
    lb: Callable[..., Result], seeded: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(platform, "timestamp_for_filename", lambda now=None: STAMP)

    result = run_ok(lb, "export")

    name = f"logbook-export-{STAMP}.jsonl"
    assert (workdir / name).is_file()
    assert result.stdout == f"✔ 내보냈습니다: {name} {COUNTS}\n"


def test_export_default_file_name_uses_same_now_as_header(
    lb: Callable[..., Result], seeded: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[datetime | None] = []

    def fake(now: datetime | None = None) -> str:
        seen.append(now)
        return STAMP

    monkeypatch.setattr(platform, "timestamp_for_filename", fake)

    run_ok(lb, "export")

    header = json.loads(
        (workdir / f"logbook-export-{STAMP}.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert len(seen) == 1
    assert seen[0] is not None
    assert datetime.fromisoformat(header["exported_at"]) == seen[0]


@pytest.fixture
def exported(lb: Callable[..., Result], seeded: Path, workdir: Path) -> Path:
    run_ok(lb, "export", "-o", "b.jsonl")
    (workdir / "b.jsonl").write_text("old", encoding="utf-8")
    return workdir / "b.jsonl"


def test_export_overwrite_yes_answer(lb: Callable[..., Result], exported: Path) -> None:
    result = lb("export", "-o", "b.jsonl", input="y\n")

    assert result.exit_code == 0
    assert result.stderr == "파일이 이미 있습니다: b.jsonl\n덮어쓸까요? [y/N]: "
    assert result.stdout == f"✔ 내보냈습니다: b.jsonl {COUNTS}\n"
    assert exported.read_text(encoding="utf-8") != "old"


def test_export_overwrite_no_answer(lb: Callable[..., Result], exported: Path) -> None:
    result = lb("export", "-o", "b.jsonl", input="n\n")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.endswith("덮어쓸까요? [y/N]: 덮어쓰지 않았습니다.\n")
    assert exported.read_text(encoding="utf-8") == "old"


def test_export_overwrite_without_input(lb: Callable[..., Result], exported: Path) -> None:
    result = lb("export", "-o", "b.jsonl")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.endswith(
        "확인 입력을 받지 못해 덮어쓰지 않았습니다. 확인 없이 덮어쓰려면 --yes를 붙이세요.\n"
    )
    assert exported.read_text(encoding="utf-8") == "old"


def test_export_overwrite_with_yes_option(lb: Callable[..., Result], exported: Path) -> None:
    result = lb("export", "-o", "b.jsonl", "--yes")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert exported.read_text(encoding="utf-8") != "old"


def test_export_out_missing_folder(lb: Callable[..., Result], seeded: Path, workdir: Path) -> None:
    result = lb("export", "-o", "없는폴더/x.jsonl")

    assert_rejected(
        result,
        f"저장할 폴더가 없습니다: {Path('없는폴더')}. 폴더를 먼저 만들거나 다른 경로를 지정하세요.",
    )


def test_export_out_directory(lb: Callable[..., Result], seeded: Path, workdir: Path) -> None:
    result = lb("export", "-o", ".")

    assert_rejected(result, "파일 경로가 아니라 폴더입니다: .. 파일 이름까지 지정하세요.")


def test_export_out_korean_path_with_space(
    lb: Callable[..., Result], seeded: Path, workdir: Path
) -> None:
    (workdir / "백업 폴더").mkdir()

    result = run_ok(lb, "export", "-o", "백업 폴더/전체.jsonl")

    assert (workdir / "백업 폴더" / "전체.jsonl").is_file()
    assert result.stdout == f"✔ 내보냈습니다: {Path('백업 폴더') / '전체.jsonl'} {COUNTS}\n"


def test_export_requires_init(lb: Callable[..., Result], tmp_home: Path, workdir: Path) -> None:
    result = lb("export", "-o", "b.jsonl")

    assert_rejected(
        result,
        f"데이터베이스가 없습니다: {tmp_home / 'logbook.db'}. 먼저 'lb init'을 실행하세요.",
    )
    assert not (workdir / "b.jsonl").exists()


def test_export_uses_ascii_mark_without_unicode(
    lb: Callable[..., Result], seeded: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(platform, "supports_unicode", lambda text="": False)

    result = run_ok(lb, "export", "-o", "b.jsonl")

    assert result.stdout == "v 내보냈습니다: b.jsonl (프로젝트 2 - 태스크 2 - 기록 2 - 타이머 0)\n"


def test_import_round_trip_into_other_db(
    lb: Callable[..., Result],
    seeded: Path,
    workdir: Path,
    switch_db: Callable[[str], Path],
) -> None:
    original_log = run_ok(lb, "log").stdout
    original_tasks = run_ok(lb, "task", "list", "-s", "all").stdout
    run_ok(lb, "export", "-o", "b.jsonl")
    switch_db("other")

    result = run_ok(lb, "import", "b.jsonl")

    assert result.stdout == f"✔ 가져왔습니다: b.jsonl {COUNTS}\n"
    assert result.stderr == ""
    assert run_ok(lb, "log").stdout == original_log
    assert run_ok(lb, "task", "list", "-s", "all").stdout == original_tasks


def test_import_uses_ascii_mark_without_unicode(
    lb: Callable[..., Result],
    seeded: Path,
    workdir: Path,
    switch_db: Callable[[str], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_ok(lb, "export", "-o", "b.jsonl")
    switch_db("other")
    monkeypatch.setattr(platform, "supports_unicode", lambda text="": False)

    result = run_ok(lb, "import", "b.jsonl")

    assert result.stdout == "v 가져왔습니다: b.jsonl (프로젝트 2 - 태스크 2 - 기록 2 - 타이머 0)\n"


def test_import_rejects_database_with_data(
    lb: Callable[..., Result], seeded: Path, workdir: Path
) -> None:
    run_ok(lb, "export", "-o", "b.jsonl")
    before = run_ok(lb, "log").stdout

    result = lb("import", "b.jsonl")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("오류: 데이터가 있는 데이터베이스에는 가져올 수 없습니다.")
    assert run_ok(lb, "log").stdout == before


def test_import_missing_file(lb: Callable[..., Result], initialized: Path, workdir: Path) -> None:
    result = lb("import", "없는파일.jsonl")

    assert_rejected(result, "가져올 파일이 없습니다: 없는파일.jsonl")


def test_import_directory(lb: Callable[..., Result], initialized: Path, workdir: Path) -> None:
    (workdir / "폴더").mkdir()

    result = lb("import", "폴더")

    assert_rejected(result, "파일 경로가 아니라 폴더입니다: 폴더. 파일 이름까지 지정하세요.")


def test_import_rejects_other_user_home(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("import", "~nouser/x.jsonl")

    assert_rejected(
        result,
        "경로가 올바르지 않습니다: 가져올 파일 경로 값 '~nouser/x.jsonl'. "
        "홈 디렉터리 기준 경로는 '~/'로 시작하세요.",
    )


def test_import_expands_home(
    lb: Callable[..., Result],
    seeded: Path,
    workdir: Path,
    isolated_home: Path,
    switch_db: Callable[[str], Path],
) -> None:
    run_ok(lb, "export", "-o", "~/백업.jsonl")
    switch_db("other")

    result = run_ok(lb, "import", "~/백업.jsonl")

    assert result.stdout == f"✔ 가져왔습니다: {isolated_home / '백업.jsonl'} {COUNTS}\n"


def test_import_rejects_cp949_file(
    lb: Callable[..., Result], initialized: Path, workdir: Path
) -> None:
    (workdir / "c.jsonl").write_bytes("한글".encode("cp949"))

    result = lb("import", "c.jsonl")

    assert_rejected(
        result, "UTF-8 텍스트 파일이 아닙니다: c.jsonl. 'lb export'로 만든 파일을 지정하세요."
    )


def test_import_read_error_message(
    lb: Callable[..., Result],
    initialized: Path,
    workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (workdir / "b.jsonl").write_text("{}\n", encoding="utf-8")
    original = Path.read_text

    def fake(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == "b.jsonl":
            raise PermissionError(13, "Permission denied")
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", fake)

    result = lb("import", "b.jsonl")

    assert_rejected(result, "가져올 파일을 읽지 못했습니다: b.jsonl (Permission denied).")


def test_import_reports_line_number_and_keeps_db(
    lb: Callable[..., Result],
    seeded: Path,
    workdir: Path,
    switch_db: Callable[[str], Path],
) -> None:
    run_ok(lb, "export", "-o", "b.jsonl")
    lines = (workdir / "b.jsonl").read_text(encoding="utf-8").split("\n")
    lines[3] = "{깨진 줄"
    (workdir / "bad.jsonl").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    switch_db("other")

    result = lb("import", "bad.jsonl")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("오류: 4번째 줄: ")
    assert run_ok(lb, "task", "list", "-s", "all").stdout.count("결제") == 0


def test_import_accepts_bom(
    lb: Callable[..., Result],
    seeded: Path,
    workdir: Path,
    switch_db: Callable[[str], Path],
) -> None:
    run_ok(lb, "export", "-o", "b.jsonl")
    data = (workdir / "b.jsonl").read_bytes()
    (workdir / "bom.jsonl").write_bytes(b"\xef\xbb\xbf" + data)
    switch_db("other")

    result = run_ok(lb, "import", "bom.jsonl")

    assert result.stdout == f"✔ 가져왔습니다: bom.jsonl {COUNTS}\n"


def test_import_requires_init(lb: Callable[..., Result], tmp_home: Path, workdir: Path) -> None:
    (workdir / "b.jsonl").write_text(
        json.dumps({"type": "logbook-export", "format": 1, "schema": 1}) + "\n", encoding="utf-8"
    )

    result = lb("import", "b.jsonl")

    assert_rejected(
        result,
        f"데이터베이스가 없습니다: {tmp_home / 'logbook.db'}. 먼저 'lb init'을 실행하세요.",
    )


def test_unicode_separators_survive_round_trip(
    lb: Callable[..., Result],
    initialized: Path,
    open_db: OpenDb,
    today: date,
    workdir: Path,
    switch_db: Callable[[str], Path],
) -> None:
    memo = "가" + SEPARATORS[0] + "나" + SEPARATORS[1] + "다" + SEPARATORS[2] + "라"
    title = "제목" + SEPARATORS[0] + SEPARATORS[1] + SEPARATORS[2] + "끝"
    seed(open_db, today, memo=memo, title=title)
    run_ok(lb, "export", "-o", "a.jsonl")
    a_bytes = (workdir / "a.jsonl").read_bytes()
    a_text = a_bytes.decode("utf-8")
    for separator in SEPARATORS:
        assert separator not in a_text
    # 이스케이프를 풀어 원문자가 든 파일을 만든다.
    raw_lines = [
        json.dumps(json.loads(line), ensure_ascii=False, sort_keys=True)
        for line in a_text.split("\n")
        if line
    ]
    raw_text = "\n".join(raw_lines) + "\n"
    assert any(separator in raw_text for separator in SEPARATORS)
    (workdir / "raw.jsonl").write_text(raw_text, encoding="utf-8", newline="\n")
    switch_db("other")

    imported = run_ok(lb, "import", "raw.jsonl")
    run_ok(lb, "export", "-o", "c.jsonl")

    assert imported.stdout == f"✔ 가져왔습니다: raw.jsonl {COUNTS}\n"
    a_rest = a_bytes.split(b"\n", 1)[1]
    c_rest = (workdir / "c.jsonl").read_bytes().split(b"\n", 1)[1]
    assert c_rest == a_rest


def test_database_is_released_after_export(
    lb: Callable[..., Result], seeded: Path, workdir: Path
) -> None:
    run_ok(lb, "export", "-o", "b.jsonl")

    os.replace(seeded, seeded.with_name("moved.db"))


def test_database_is_released_after_import(
    lb: Callable[..., Result],
    seeded: Path,
    workdir: Path,
    switch_db: Callable[[str], Path],
) -> None:
    run_ok(lb, "export", "-o", "b.jsonl")
    other = switch_db("other")
    run_ok(lb, "import", "b.jsonl")

    os.replace(other, other.with_name("moved.db"))


def test_database_is_released_after_failed_import(
    lb: Callable[..., Result],
    seeded: Path,
    workdir: Path,
    switch_db: Callable[[str], Path],
) -> None:
    run_ok(lb, "export", "-o", "b.jsonl")
    lines = (workdir / "b.jsonl").read_text(encoding="utf-8").split("\n")
    lines[2] = "{깨진 줄"
    (workdir / "bad.jsonl").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    other = switch_db("other")
    assert lb("import", "bad.jsonl").exit_code == 1

    os.replace(other, other.with_name("moved.db"))


def test_database_is_released_after_rejected_import(
    lb: Callable[..., Result], seeded: Path, workdir: Path
) -> None:
    run_ok(lb, "export", "-o", "b.jsonl")
    assert lb("import", "b.jsonl").exit_code == 1

    os.replace(seeded, seeded.with_name("moved.db"))
