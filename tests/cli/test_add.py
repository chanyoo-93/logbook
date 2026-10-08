"""lb add."""

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.core import db, platform, services
from tests.cli.helpers import OpenDb, assert_rejected
from tests.helpers import hold_lock

FAST_BUSY_TIMEOUT = 0.05
CATEGORY_LIST = "admin, design, dev, docs, meeting, ops, review, study, support"


def add_payment(lb: Callable[..., Result]) -> None:
    result = lb("project", "add", "payment", "결제 서버")
    assert result.exit_code == 0, result.stderr


def add_payment_task(open_db: OpenDb) -> int:
    """payment 프로젝트의 design 태스크를 만들고 ID를 반환한다."""
    with open_db() as s:
        task = services.create_task(
            s, title="결제 화면 설계", project_slug="payment", category="design"
        )
        s.flush()
        return task.id


def logged_date(open_db: OpenDb, log_id: int) -> date:
    with open_db() as s:
        return services.get_worklog(s, log_id).date


def test_add_with_project_and_category(lb: Callable[..., Result], initialized: Path) -> None:
    add_payment(lb)

    result = lb("add", "2h", "결제 재시도 로직 구현", "-p", "payment", "-c", "dev")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ #1 payment/dev 2h — 결제 재시도 로직 구현 (오늘 누적 2h)\n"
    assert result.stderr == ""
    os.replace(initialized, initialized.with_name("moved.db"))


def test_total_includes_earlier_logs_of_the_day(
    lb: Callable[..., Result], initialized: Path
) -> None:
    add_payment(lb)
    assert lb("add", "3h30m", "오전 작업", "-p", "payment", "-c", "dev").exit_code == 0

    result = lb("add", "2h", "결제 재시도 로직 구현", "-p", "payment", "-c", "dev")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ #2 payment/dev 2h — 결제 재시도 로직 구현 (오늘 누적 5h 30m)\n"


def test_default_project_is_common(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("add", "1h", "스프린트 플래닝", "-c", "meeting")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ #1 common/meeting 1h — 스프린트 플래닝 (오늘 누적 1h)\n"


def test_default_project_from_config(lb: Callable[..., Result], tmp_home: Path) -> None:
    # 서비스의 기본값도 common이라, 설정값을 넘기지 않으면 이 테스트만 실패한다.
    (tmp_home / "config.toml").write_text(
        'default_project = "payment"\n', encoding="utf-8", newline="\n"
    )
    assert lb("init").exit_code == 0
    add_payment(lb)

    result = lb("add", "1h", "x", "-c", "dev")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ #1 payment/dev 1h — x (오늘 누적 1h)\n"


def test_yesterday_shows_that_days_total(
    lb: Callable[..., Result], initialized: Path, open_db: OpenDb
) -> None:
    add_payment(lb)

    result = lb("add", "30m", "장애 대응", "-p", "payment", "-c", "ops", "-d", "yesterday")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ #1 payment/ops 30m — 장애 대응 (09-30 누적 30m)\n"
    assert logged_date(open_db, 1) == date(2026, 9, 30)


def test_total_counts_only_that_day(lb: Callable[..., Result], initialized: Path) -> None:
    add_payment(lb)
    assert lb("add", "1h", "오늘 작업", "-p", "payment", "-c", "dev").exit_code == 0
    assert lb("add", "2h", "그제 작업", "-p", "payment", "-c", "dev", "-d", "09-29").exit_code == 0

    result = lb("add", "30m", "장애 대응", "-p", "payment", "-c", "ops", "-d", "yesterday")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ #3 payment/ops 30m — 장애 대응 (09-30 누적 30m)\n"


def test_weekday_date(lb: Callable[..., Result], initialized: Path, open_db: OpenDb) -> None:
    result = lb("add", "1h", "회고", "-c", "meeting", "-d", "mon")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ #1 common/meeting 1h — 회고 (09-28 누적 1h)\n"
    assert logged_date(open_db, 1) == date(2026, 9, 28)


def test_full_date(lb: Callable[..., Result], initialized: Path, open_db: OpenDb) -> None:
    result = lb("add", "45", "문서 정리", "-c", "docs", "-d", "2026-09-15")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ #1 common/docs 45m — 문서 정리 (09-15 누적 45m)\n"
    assert logged_date(open_db, 1) == date(2026, 9, 15)


def test_empty_date_is_rejected(
    lb: Callable[..., Result], initialized: Path, open_db: OpenDb
) -> None:
    result = lb("add", "1h", "x", "-c", "dev", "-d", "")

    assert_rejected(
        result,
        "날짜 형식이 올바르지 않습니다: ''. 예: today, yesterday, mon~sun, 2026-10-01, 10-01",
    )
    with open_db() as s:
        assert services.day_total_minutes(s, date(2026, 10, 1)) == 0


def test_task_supplies_project_and_category(
    lb: Callable[..., Result], initialized: Path, open_db: OpenDb
) -> None:
    add_payment(lb)
    task_id = add_payment_task(open_db)

    result = lb("add", "1h", "화면 흐름 정리", "-t", str(task_id))

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ #1 payment/design 1h — 화면 흐름 정리 (오늘 누적 1h)\n"


def test_explicit_category_wins_over_task(
    lb: Callable[..., Result], initialized: Path, open_db: OpenDb
) -> None:
    add_payment(lb)
    add_payment_task(open_db)

    result = lb("add", "1h", "화면 구현", "-t", "#1", "-c", "dev")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ #1 payment/dev 1h — 화면 구현 (오늘 누적 1h)\n"


def test_task_project_mismatch(
    lb: Callable[..., Result], initialized: Path, open_db: OpenDb
) -> None:
    add_payment(lb)
    add_payment_task(open_db)

    result = lb("add", "1h", "x", "-t", "1", "-p", "common")

    assert_rejected(
        result,
        "'payment' 프로젝트에 속한 태스크입니다 (#1). "
        "프로젝트를 빼거나 같은 프로젝트(-p payment)를 지정하세요.",
    )
    # 세션 안에서 난 오류 뒤에도 엔진이 정리되어 파일을 옮길 수 있다.
    os.replace(initialized, initialized.with_name("moved.db"))


@pytest.mark.parametrize("task", ["abc", "99999999999999999999"], ids=["letters", "too-large"])
def test_invalid_task_id(lb: Callable[..., Result], initialized: Path, task: str) -> None:
    result = lb("add", "1h", "x", "-c", "dev", "-t", task)

    assert_rejected(
        result, f"태스크 ID가 올바르지 않습니다: '{task}'. 숫자로 입력하세요 (예: 128 또는 #128)."
    )


def test_unknown_task(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("add", "1h", "x", "-c", "dev", "-t", "999")

    assert_rejected(result, "태스크를 찾을 수 없습니다: #999. 'lb task list'로 확인하세요.")
    os.replace(initialized, initialized.with_name("moved.db"))


@pytest.mark.parametrize(
    ("duration", "message"),
    [
        ("abc", "시간 형식이 올바르지 않습니다: 'abc'. 예: 2h, 1.5h, 90m, 1h30m, 1:30"),
        ("0m", "소요 시간은 1분 이상이어야 합니다: '0m'. 예: 30m, 1h"),
        (
            "25h",
            "소요 시간은 24시간 이하여야 합니다: '25h'. "
            "하루를 넘는 작업은 날짜별로 나눠 기록하세요.",
        ),
    ],
    ids=["format", "too-short", "too-long"],
)
def test_invalid_duration(
    lb: Callable[..., Result], initialized: Path, duration: str, message: str
) -> None:
    result = lb("add", duration, "x", "-c", "dev")

    assert_rejected(result, message)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ["x", "-c", "dev", "-d", "foo"],
            "날짜 형식이 올바르지 않습니다: 'foo'. "
            "예: today, yesterday, mon~sun, 2026-10-01, 10-01",
        ),
        (
            ["x", "-c", "dev", "-p", "nope"],
            "프로젝트를 찾을 수 없습니다: 'nope'. 'lb project list'로 확인하거나, "
            "새 프로젝트라면 'lb project add nope <이름>'으로 만드세요.",
        ),
        (["x"], "카테고리를 지정하세요. 예: -c dev"),
        (
            ["x", "-c", "xyz"],
            f"쓸 수 없는 카테고리입니다: 'xyz'. 사용할 수 있는 카테고리: {CATEGORY_LIST}",
        ),
        (["  ", "-c", "dev"], "메모를 입력하세요. 무엇을 했는지 한 줄로 적어 주세요."),
    ],
    ids=["date", "unknown-project", "no-category", "bad-category", "blank-note"],
)
def test_rejects_with_core_message(
    lb: Callable[..., Result], initialized: Path, args: list[str], message: str
) -> None:
    result = lb("add", "1h", *args)

    assert_rejected(result, message)


def test_archived_project_is_rejected(lb: Callable[..., Result], initialized: Path) -> None:
    add_payment(lb)
    assert lb("project", "archive", "payment").exit_code == 0

    result = lb("add", "1h", "x", "-p", "payment", "-c", "dev")

    assert_rejected(
        result,
        "보관된 프로젝트에는 새 기록이나 태스크를 추가할 수 없습니다: 'payment'. "
        "다른 프로젝트를 지정하세요.",
    )
    os.replace(initialized, initialized.with_name("moved.db"))


def test_add_before_init(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"

    result = lb("add", "1h", "x", "-c", "dev")

    assert_rejected(result, f"데이터베이스가 없습니다: {db_path}. 먼저 'lb init'을 실행하세요.")
    assert not db_path.exists()


def test_duration_is_parsed_before_database(lb: Callable[..., Result], tmp_home: Path) -> None:
    result = lb("add", "abc", "x")

    assert_rejected(result, "시간 형식이 올바르지 않습니다: 'abc'. 예: 2h, 1.5h, 90m, 1h30m, 1:30")
    assert not (tmp_home / "logbook.db").exists()


def test_empty_database_file(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"
    db_path.touch()

    result = lb("add", "1h", "x", "-c", "dev")

    assert_rejected(
        result, f"데이터베이스가 초기화되지 않았습니다: {db_path}. 먼저 'lb init'을 실행하세요."
    )


@pytest.mark.parametrize(
    "note",
    ["[/api] fix", "[bold]x[/bold]", ":smile:", "C:\\work\\"],
    ids=["closing-tag", "bold", "emoji", "backslash"],
)
def test_note_is_printed_verbatim(lb: Callable[..., Result], initialized: Path, note: str) -> None:
    result = lb("add", "1h", note, "-c", "dev")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == f"✔ #1 common/dev 1h — {note} (오늘 누적 1h)\n"


def test_note_starting_with_dash_after_double_dash(
    lb: Callable[..., Result], initialized: Path
) -> None:
    result = lb("add", "30m", "-c", "dev", "--", "-5% 개선")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ #1 common/dev 30m — -5% 개선 (오늘 누적 30m)\n"


def test_ascii_symbols_when_console_lacks_unicode(
    lb: Callable[..., Result], initialized: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(platform, "supports_unicode", lambda text="": False)

    result = lb("add", "1h", "x", "-c", "dev")

    assert result.stdout == "v #1 common/dev 1h - x (오늘 누적 1h)\n"


def test_busy_database(
    lb: Callable[..., Result], initialized: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db, "BUSY_TIMEOUT_SECONDS", FAST_BUSY_TIMEOUT)

    with hold_lock(initialized, "EXCLUSIVE"):
        result = lb("add", "1h", "x", "-c", "dev")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("오류: 데이터베이스를 다른 프로그램이 사용 중입니다:")
    os.replace(initialized, initialized.with_name("moved.db"))
