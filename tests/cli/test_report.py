"""lb report."""

import os
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.cli import runtime
from logbook.core import platform, services
from logbook.core.config import load_config
from logbook.core.report import render_markdown, user_template_path
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import parse_week
from tests.cli.helpers import FIXED_NOW, OpenDb, assert_rejected, run_ok

BAD_WEEK_MESSAGE = "주차 형식이 올바르지 않습니다: 'x'. 예: this, last, next, 2026-W41"
COPY_FAILED = "주의: 클립보드에 복사하지 못했습니다. --out으로 파일에 저장하세요.\n"
# W40(2026-09-28 ~ 10-04) 안, 정오 부근이라 날짜 경계와 멀다
DONE_AT = datetime(2026, 9, 30, 3, 0, tzinfo=UTC)
LAST_WEEK_TITLE = "# 주간업무보고 (2026-09-21 ~ 2026-09-27)"


@pytest.fixture
def seeded(initialized: Path, open_db: OpenDb, today: date) -> Path:
    """W40에 기록 2건과 완료 태스크 1건, 다음 주 계획 1건이 있는 DB."""
    with open_db() as s:
        services.create_project(s, "payment", "결제 서버")
        services.add_worklog(
            s, minutes=120, note="결제 재시도", project_slug="payment", category="dev",
            work_date=date(2026, 9, 30), today=today,
        )  # fmt: skip
        services.add_worklog(
            s, minutes=60, note="주간 회의", category="meeting",
            work_date=date(2026, 10, 1), today=today,
        )  # fmt: skip
        task = services.create_task(
            s, title="결제 재시도 구현", project_slug="payment", estimate_minutes=180,
            planned_week=parse_week("2026-W40", today=today, week_start="monday"),
        )  # fmt: skip
        task.status = TaskStatus.DONE
        task.done_at = DONE_AT
        services.create_task(
            s, title="환불 API 구현", project_slug="payment", estimate_minutes=480,
            planned_week=parse_week("2026-W41", today=today, week_start="monday"),
        )  # fmt: skip
    return initialized


def expected_report(week: str = "this") -> str:
    """CLI와 같은 입력으로 만든 보고서(렌더링 기준값)."""
    cfg = load_config()
    the_week = parse_week(week, today=runtime.today(), week_start=cfg.week_start)
    from logbook.cli.runtime import session

    with session(cfg) as s:
        data = services.weekly_report(
            s,
            the_week,
            tz=FIXED_NOW.tzinfo or UTC,
            title_format=cfg.report.title_format,
            author=cfg.report.author,
            category_labels=cfg.categories,
        )
    return render_markdown(
        data, template_path=user_template_path(Path(os.environ["LOGBOOK_CONFIG"]))
    )


class Clipboard:
    """copy_to_clipboard 대역: 받은 텍스트를 기록하고 정해 둔 결과를 돌려준다."""

    def __init__(self, ok: bool) -> None:
        self.ok = ok
        self.copied: list[str] = []

    def __call__(self, text: str) -> bool:
        self.copied.append(text)
        return self.ok


@pytest.fixture
def clipboard(monkeypatch: pytest.MonkeyPatch) -> Clipboard:
    fake = Clipboard(ok=True)
    monkeypatch.setattr(platform, "copy_to_clipboard", fake)
    return fake


@pytest.fixture
def failing_clipboard(monkeypatch: pytest.MonkeyPatch) -> Clipboard:
    fake = Clipboard(ok=False)
    monkeypatch.setattr(platform, "copy_to_clipboard", fake)
    return fake


def test_report_prints_rendered_markdown(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "report")

    assert result.stdout == expected_report()
    assert result.stdout.startswith("# 주간업무보고 (2026-09-28 ~ 2026-10-04)\n")
    assert "완료 태스크 1건" in result.stdout
    assert result.stderr == ""


def test_report_last_week_title(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "report", "-w", "last")

    assert result.stdout.splitlines()[0] == LAST_WEEK_TITLE
    assert result.stdout == expected_report("last")


def test_report_follows_sunday_week_start(
    lb: Callable[..., Result], tmp_home: Path, open_db: OpenDb
) -> None:
    (tmp_home / "config.toml").write_text('week_start = "sunday"\n', encoding="utf-8", newline="\n")
    run_ok(lb, "init")
    with open_db() as s:
        for day in (date(2026, 9, 27), date(2026, 10, 4)):
            services.add_worklog(
                s, minutes=60, note="기록", category="dev", work_date=day, today=runtime.today()
            )

    result = run_ok(lb, "report")

    assert result.stdout.splitlines()[0] == "# 주간업무보고 (2026-09-27 ~ 2026-10-03)"
    assert "기록 1건" in result.stdout


def test_report_rejects_bad_week(lb: Callable[..., Result], tmp_home: Path) -> None:
    # init 전이어도 주차 오류가 먼저 나온다(DB 접근 전).
    assert_rejected(lb("report", "-w", "x"), BAD_WEEK_MESSAGE)


def test_report_rejects_empty_week(lb: Callable[..., Result], tmp_home: Path) -> None:
    result = lb("report", "-w", "")

    assert result.exit_code == 1
    assert result.stderr.startswith("오류: 주차 형식이 올바르지 않습니다: ''.")


def test_report_requires_init(lb: Callable[..., Result], tmp_home: Path) -> None:
    result = lb("report")

    assert_rejected(
        result,
        f"데이터베이스가 없습니다: {tmp_home / 'logbook.db'}. 먼저 'lb init'을 실행하세요.",
    )


def test_report_out_writes_utf8_lf_file(
    lb: Callable[..., Result], seeded: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = run_ok(lb, "report", "-o", "out.md")

    data = (tmp_path / "out.md").read_bytes()
    assert data == expected_report().encode("utf-8")
    assert b"\r" not in data
    assert result.stdout == "✔ 보고서를 저장했습니다: out.md\n"
    assert result.stderr == ""


def test_report_out_uses_ascii_mark_without_unicode(
    lb: Callable[..., Result], seeded: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(platform, "supports_unicode", lambda text="": False)

    result = run_ok(lb, "report", "-o", "out.md")

    assert result.stdout == "v 보고서를 저장했습니다: out.md\n"


@pytest.fixture
def saved(
    lb: Callable[..., Result], seeded: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """out.md가 이미 저장된 작업 폴더."""
    monkeypatch.chdir(tmp_path)
    run_ok(lb, "report", "-o", "out.md")
    (tmp_path / "out.md").write_text("old", encoding="utf-8")
    return tmp_path / "out.md"


def test_report_overwrite_yes_answer(lb: Callable[..., Result], saved: Path) -> None:
    result = lb("report", "-o", "out.md", input="y\n")

    assert result.exit_code == 0
    assert result.stderr == "파일이 이미 있습니다: out.md\n덮어쓸까요? [y/N]: "
    assert result.stdout == "✔ 보고서를 저장했습니다: out.md\n"
    assert saved.read_text(encoding="utf-8") == expected_report()


def test_report_overwrite_no_answer(lb: Callable[..., Result], saved: Path) -> None:
    result = lb("report", "-o", "out.md", input="n\n")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.endswith("덮어쓸까요? [y/N]: 덮어쓰지 않았습니다.\n")
    assert saved.read_text(encoding="utf-8") == "old"


def test_report_overwrite_without_input(lb: Callable[..., Result], saved: Path) -> None:
    result = lb("report", "-o", "out.md")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.endswith(
        "확인 입력을 받지 못해 덮어쓰지 않았습니다. 확인 없이 덮어쓰려면 --yes를 붙이세요.\n"
    )
    assert saved.read_text(encoding="utf-8") == "old"


def test_report_overwrite_with_yes_option(lb: Callable[..., Result], saved: Path) -> None:
    result = lb("report", "-o", "out.md", "--yes")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert saved.read_text(encoding="utf-8") == expected_report()


def test_report_out_missing_folder(
    lb: Callable[..., Result], seeded: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = lb("report", "-o", "없는폴더/out.md")

    assert_rejected(
        result,
        f"저장할 폴더가 없습니다: {Path('없는폴더')}. 폴더를 먼저 만들거나 다른 경로를 지정하세요.",
    )


def test_report_out_directory(
    lb: Callable[..., Result], seeded: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = lb("report", "-o", ".")

    assert_rejected(result, "파일 경로가 아니라 폴더입니다: .. 파일 이름까지 지정하세요.")


def test_report_out_expands_home(
    lb: Callable[..., Result], seeded: Path, isolated_home: Path
) -> None:
    result = run_ok(lb, "report", "-o", "~/주간.md")

    assert (isolated_home / "주간.md").read_text(encoding="utf-8") == expected_report()
    assert result.stdout == f"✔ 보고서를 저장했습니다: {isolated_home / '주간.md'}\n"


def test_report_out_rejects_other_user_home(lb: Callable[..., Result], seeded: Path) -> None:
    result = lb("report", "-o", "~nouser/x.md")

    assert_rejected(
        result,
        "경로가 올바르지 않습니다: --out 값 '~nouser/x.md'. "
        "홈 디렉터리 기준 경로는 '~/'로 시작하세요.",
    )


def test_report_out_korean_path_with_space(
    lb: Callable[..., Result], seeded: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "보고 서").mkdir()

    result = run_ok(lb, "report", "-o", "보고 서/주간.md")

    assert (tmp_path / "보고 서" / "주간.md").read_text(encoding="utf-8") == expected_report()
    assert result.stdout == f"✔ 보고서를 저장했습니다: {Path('보고 서') / '주간.md'}\n"


def test_report_copy_success(lb: Callable[..., Result], seeded: Path, clipboard: Clipboard) -> None:
    result = run_ok(lb, "report", "--copy")

    assert clipboard.copied == [expected_report()]
    assert result.stdout == "✔ 보고서를 클립보드에 복사했습니다.\n"
    assert result.stderr == ""


def test_report_copy_failure_prints_report(
    lb: Callable[..., Result], seeded: Path, failing_clipboard: Clipboard
) -> None:
    result = lb("report", "--copy")

    assert result.exit_code == 0
    assert result.stderr == COPY_FAILED
    assert result.stdout == expected_report()


def test_report_out_and_copy(
    lb: Callable[..., Result],
    seeded: Path,
    clipboard: Clipboard,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = run_ok(lb, "report", "-o", "out.md", "--copy")

    assert result.stdout == (
        "✔ 보고서를 저장했습니다: out.md\n✔ 보고서를 클립보드에 복사했습니다.\n"
    )
    assert (tmp_path / "out.md").read_text(encoding="utf-8") == expected_report()
    assert clipboard.copied == [expected_report()]


def test_report_out_and_copy_failure_keeps_stdout_short(
    lb: Callable[..., Result],
    seeded: Path,
    failing_clipboard: Clipboard,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = lb("report", "-o", "out.md", "--copy")

    assert result.exit_code == 0
    assert result.stdout == "✔ 보고서를 저장했습니다: out.md\n"
    assert result.stderr == (
        "주의: 클립보드에 복사하지 못했습니다. 보고서는 파일로 저장했습니다: out.md\n"
    )
    assert (tmp_path / "out.md").read_text(encoding="utf-8") == expected_report()


def test_report_uses_user_template(lb: Callable[..., Result], seeded: Path, tmp_home: Path) -> None:
    (tmp_home / "report.md.j2").write_text("내 보고서: {{ data.title }}\n", encoding="utf-8")

    result = run_ok(lb, "report")

    assert result.stdout == "내 보고서: 주간업무보고 (2026-09-28 ~ 2026-10-04)\n"


def test_report_template_syntax_error(
    lb: Callable[..., Result], seeded: Path, tmp_home: Path
) -> None:
    (tmp_home / "report.md.j2").write_text("{% if %}\n", encoding="utf-8")

    result = lb("report")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("오류: 보고서 템플릿을 읽지 못했습니다:")
    assert "Traceback" not in result.stderr


def test_report_bad_title_format(lb: Callable[..., Result], tmp_home: Path) -> None:
    (tmp_home / "config.toml").write_text(
        '[report]\ntitle_format = "주간보고 ({start} ~ {end)"\n', encoding="utf-8", newline="\n"
    )
    run_ok(lb, "init")

    result = lb("report")

    assert_rejected(
        result,
        "보고서 제목 형식이 올바르지 않습니다: '주간보고 ({start} ~ {end)'. "
        "사용할 수 있는 이름: {start}, {end}",
    )


def test_database_is_released_after_report(lb: Callable[..., Result], seeded: Path) -> None:
    run_ok(lb, "report")

    os.replace(seeded, seeded.with_name("moved.db"))


def test_database_is_released_after_template_error(
    lb: Callable[..., Result], seeded: Path, tmp_home: Path
) -> None:
    (tmp_home / "report.md.j2").write_text("{% if %}\n", encoding="utf-8")
    assert lb("report").exit_code == 1

    os.replace(seeded, seeded.with_name("moved.db"))
