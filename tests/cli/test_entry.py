"""진입점 run(): 프로세스 내부 실행, 설치된 lb 실행 파일, import 가드."""

import io
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
import typer.main
from typer.core import TyperGroup
from typer.testing import Result

from logbook import __version__
from logbook.cli.group import LogbookCommand, LogbookGroup
from logbook.cli.main import app, run
from logbook.core import db, services
from tests.cli.helpers import (
    FORBIDDEN_MODULES,
    LAUNCHER,
    SUBPROCESS_TIMEOUT_SECONDS,
    lb_env,
    run_import_guard,
    run_lb,
    run_lb_closed_stdout,
)

# 파이프 버퍼(수십 KB)를 넘겨 읽는 쪽이 닫힌 뒤에도 쓰기가 이어지게 하는 기록 수
PIPE_TEST_LOG_COUNT = 2000
# 타이머 왕복 테스트: 이 시간이 지나면 경과가 1분으로 반올림되어 stop이 성공할 수 있다
SLOW_RUNNER_SECONDS = 30


def _run_in_process(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int | str | None, str]:
    """cp1252 콘솔을 흉내 낸 스트림으로 run()을 실행하고 (종료 코드, UTF-8로 디코드한 stdout).

    UTF-8 설정을 빼면 --help의 한글을 cp1252로 인코딩하지 못해 실패한다.
    """
    stdout_raw = io.BytesIO()
    stdout = io.TextIOWrapper(stdout_raw, encoding="cp1252")
    stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(sys, "argv", ["lb", *args])

    with pytest.raises(SystemExit) as exc_info:
        run()

    sys.stdout.flush()
    # TextIOWrapper는 Windows에서 \n을 \r\n으로 바꿔 쓴다.
    return exc_info.value.code, stdout_raw.getvalue().decode("utf-8").replace("\r\n", "\n")


def test_run_prints_version_as_utf8_on_cp1252_console(monkeypatch: pytest.MonkeyPatch) -> None:
    code, stdout = _run_in_process(monkeypatch, "--version")

    assert code == 0
    assert stdout == f"logbook {__version__}\n"


def test_run_prints_korean_help_on_cp1252_console(monkeypatch: pytest.MonkeyPatch) -> None:
    code, stdout = _run_in_process(monkeypatch, "--help")

    assert code == 0
    assert "업무 기록·공수 집계 도구" in stdout


def _walk(command: object, path: str) -> list[tuple[str, object]]:
    """명령 트리를 (경로, 명령) 목록으로 펼친다."""
    found = [(path, command)]
    if isinstance(command, TyperGroup):
        for name, child in command.commands.items():
            found.extend(_walk(child, f"{path} {name}"))
    return found


def _misregistered(typer_app: typer.Typer) -> list[str]:
    """LogbookGroup·LogbookCommand가 아닌 그룹과 명령의 '경로: 클래스' 목록."""
    return [
        f"{path}: {type(command).__name__}"
        for path, command in _walk(typer.main.get_command(typer_app), "lb")
        if not isinstance(command, LogbookGroup | LogbookCommand)
    ]


def test_every_command_uses_parse_boundary() -> None:
    # 하위 명령의 인자 파싱(--help, 인자 없는 하위 그룹의 help)은 부모 invoke 안에서 돌므로
    # 모든 명령과 그룹이 자기 make_context에서 닫힌 파이프를 처리해야 한다.
    assert _misregistered(app) == [], (
        "그룹은 cls=LogbookGroup, 명령은 cls=LogbookCommand로 등록하세요"
    )


def test_misregistered_finds_default_classes() -> None:
    scratch = typer.Typer(cls=LogbookGroup)
    sub = typer.Typer()
    scratch.add_typer(sub, name="sub")

    @scratch.callback()
    def root() -> None:
        pass

    @sub.command()
    def plain() -> None:
        pass

    assert _misregistered(scratch) == ["lb sub: TyperGroup", "lb sub plain: TyperCommand"]


def test_lb_fixture_separates_streams(lb: Callable[..., Result]) -> None:
    result = lb("--version")

    assert result.exit_code == 0
    assert result.stdout == f"logbook {__version__}\n"
    assert result.stderr == ""


@pytest.mark.subprocess
def test_launcher_calls_run() -> None:
    if LAUNCHER is None:
        pytest.fail("lb 실행 파일이 없습니다. 'uv sync'를 다시 실행하세요.")
    data = Path(LAUNCHER).read_bytes()
    if b"logbook.cli.main" not in data:
        pytest.skip("lb 실행 파일 형식을 알 수 없어 진입점을 확인하지 못했습니다.")

    assert b"import run" in data, (
        "lb 실행 파일이 예전 진입점(app)을 부릅니다. 'uv sync'를 다시 실행하세요."
    )


@pytest.mark.subprocess
@pytest.mark.parametrize("encoding", ["cp1252", "cp949"])
def test_help_is_utf8_on_legacy_code_page(tmp_path: Path, encoding: str) -> None:
    proc = run_lb(["--help"], env=lb_env(tmp_path, encoding), cwd=tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert "Usage: lb " in proc.stdout
    assert "lb.EXE" not in proc.stdout
    assert "업무 기록" in proc.stdout


@pytest.mark.subprocess
@pytest.mark.parametrize("encoding", ["cp1252", "cp949"])
def test_version_is_exact_on_real_pipe(tmp_path: Path, encoding: str) -> None:
    # 실제 파이프(fd 1)는 CliRunner·capsys와 달리 Windows에서 Rich의 legacy 렌더 경로 후보가 된다.
    proc = run_lb(["--version"], env=lb_env(tmp_path, encoding), cwd=tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == f"logbook {__version__}\n"
    assert proc.stderr == ""


@pytest.mark.subprocess
@pytest.mark.parametrize(
    "args", [["--version"], ["--help"], []], ids=["version", "help", "no-args"]
)
def test_closed_stdout_exits_silently(tmp_path: Path, args: list[str]) -> None:
    proc = run_lb_closed_stdout(args, env=lb_env(tmp_path, "cp1252"), cwd=tmp_path)

    assert proc.returncode == 1
    assert proc.stderr == ""


@pytest.mark.subprocess
def test_no_args_shows_help(tmp_path: Path) -> None:
    proc = run_lb([], env=lb_env(tmp_path, "cp1252"), cwd=tmp_path)

    assert proc.returncode == 2
    assert "Usage: lb " in proc.stdout + proc.stderr


@pytest.mark.subprocess
@pytest.mark.parametrize("encoding", ["cp1252", "cp949"])
def test_add_keeps_note_verbatim_on_legacy_code_page(tmp_path: Path, encoding: str) -> None:
    # UTF-8 출력, windows_expand_args=False(%VAR%, $VAR, ~ 펼침 없음), 마크업 안전성을 한 번에 본다.
    env = lb_env(tmp_path, encoding)
    assert run_lb(["init"], env=env, cwd=tmp_path).returncode == 0
    note = "%USERNAME% $HOME ~x [/api] 한글"

    proc = run_lb(["add", "2h", note, "-c", "dev"], env=env, cwd=tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == f"✔ #1 common/dev 2h — {note} (오늘 누적 2h)\n"
    assert proc.stderr == ""


@pytest.mark.subprocess
@pytest.mark.parametrize("encoding", ["cp1252", "cp949"])
def test_add_error_is_utf8_on_legacy_code_page(tmp_path: Path, encoding: str) -> None:
    env = lb_env(tmp_path, encoding)
    assert run_lb(["init"], env=env, cwd=tmp_path).returncode == 0

    proc = run_lb(["add", "1h", "x", "-c", "nope"], env=env, cwd=tmp_path)

    assert proc.returncode == 1
    assert proc.stdout == ""
    assert proc.stderr.startswith("오류: 카테고리 'nope'는 쓸 수 없습니다.")


@pytest.mark.subprocess
def test_timer_round_trip_with_real_clock(tmp_path: Path) -> None:
    # 실제 로컬 시간대(astimezone())와 UTF-8 출력 경로를 거친다. 1분이 지나지 않아 stop은 거부된다.
    env = lb_env(tmp_path, "cp949")
    assert run_lb(["init"], env=env, cwd=tmp_path).returncode == 0

    started = run_lb(["start", "한글 타이머", "-c", "dev"], env=env, cwd=tmp_path)
    t0 = time.monotonic()
    assert started.returncode == 0, started.stderr
    assert started.stdout.startswith("✔ 타이머 시작: common/dev — 한글 타이머 (")

    shown = run_lb(["status"], env=env, cwd=tmp_path)
    assert shown.returncode == 0, shown.stderr
    assert shown.stdout.startswith("진행 중: common/dev — 한글 타이머\n")

    stopped = run_lb(["stop"], env=env, cwd=tmp_path)
    if stopped.returncode == 0 and time.monotonic() - t0 >= SLOW_RUNNER_SECONDS:
        # 경과가 30초를 넘으면 1분으로 반올림되어 stop이 저장에 성공한다.
        pytest.skip("느린 러너: 30초 경과")
    assert stopped.returncode == 1
    assert stopped.stderr.startswith("오류: 1분이 지나지 않아"), stopped.stderr

    cancelled = run_lb(["cancel", "--yes"], env=env, cwd=tmp_path)
    assert cancelled.returncode == 0, cancelled.stderr
    assert cancelled.stdout.startswith("✔ 타이머를 버렸습니다: common/dev — 한글 타이머 (경과 ")


@pytest.mark.subprocess
def test_log_rm_accepts_bom_prefixed_pipe_input(tmp_path: Path) -> None:
    # Windows PowerShell 5.1의 `"y" | lb log rm 1`은 EF BB BF 'y' CR LF를 보낸다.
    env = lb_env(tmp_path, "utf-8")
    assert run_lb(["init"], env=env, cwd=tmp_path).returncode == 0
    assert run_lb(["add", "1h", "지울 기록", "-c", "dev"], env=env, cwd=tmp_path).returncode == 0

    proc = run_lb(["log", "rm", "1"], env=env, cwd=tmp_path, input_bytes=b"\xef\xbb\xbfy\r\n")

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("✔ 삭제했습니다: #1 ")
    assert "#1 " not in run_lb(["log"], env=env, cwd=tmp_path).stdout


@pytest.mark.subprocess
def test_add_does_not_expand_windows_args(tmp_path: Path) -> None:
    # Click의 Windows 인자 펼침이 켜져 있으면 %USERNAME%, ~, glob이 'lbtest~a1'로 바뀐다.
    # 시간 파싱 오류가 DB보다 먼저 나므로 lb init이 필요 없다.
    (tmp_path / "lbtest~a1").write_text("", encoding="utf-8")
    pattern = "%USERNAME%~[ab]*"

    proc = run_lb(["add", pattern, "x"], env=lb_env(tmp_path, "cp1252"), cwd=tmp_path)

    assert proc.returncode == 1
    assert f"'{pattern}'" in proc.stderr


@pytest.mark.subprocess
def test_log_exits_quietly_when_reader_closes_pipe(tmp_path: Path) -> None:
    # `lb log | head -1`: 읽는 쪽이 첫 줄만 읽고 닫는다. 수정 전 Windows는 traceback과 rc 120이었다.
    if LAUNCHER is None:
        pytest.fail("lb 실행 파일이 없습니다. 'uv sync'를 다시 실행하세요.")
    env = lb_env(tmp_path, "cp1252")
    assert run_lb(["init"], env=env, cwd=tmp_path).returncode == 0
    _add_logs_today(Path(env["LOGBOOK_DB"]), PIPE_TEST_LOG_COUNT)

    proc = subprocess.Popen(
        [LAUNCHER, "log"],
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        env=env,
    )
    assert proc.stdout is not None
    first_line = proc.stdout.readline()
    proc.stdout.close()
    # None으로 바꾸지 않으면 Windows의 communicate()가 닫힌 파일을 읽는 스레드를 띄워
    # ValueError('read of closed file')가 난다.
    proc.stdout = None
    try:
        _, err_bytes = proc.communicate(timeout=SUBPROCESS_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        # subprocess.run처럼 멈춘 자식을 끝내야 임시 DB가 열린 채 남지 않는다(Windows 정리 실패).
        proc.kill()
        proc.communicate()
        raise
    stderr = err_bytes.decode("utf-8")

    assert first_line.startswith(b"20")
    assert proc.returncode in {0, 1}
    assert "Traceback" not in stderr
    assert "Exception ignored" not in stderr


def _add_logs_today(db_path: Path, count: int) -> None:
    """실제 오늘 날짜로 기록 count건을 만든다(서브프로세스 lb는 date.today()를 쓴다)."""
    today = date.today()
    engine = db.open_database(db_path)
    try:
        with db.session_scope(engine) as s:
            for number in range(count):
                services.add_worklog(
                    s,
                    minutes=1,
                    note=f"기록 {number}",
                    category="dev",
                    work_date=today,
                    today=today,
                )
    finally:
        engine.dispose()


@pytest.mark.subprocess
@pytest.mark.parametrize(
    ("args", "exit_code", "error"),
    [
        pytest.param([], None, None, id="import"),
        pytest.param(["--version"], 0, None, id="version"),
        pytest.param(["--help"], 0, None, id="help"),
        pytest.param(["init", "--help"], 0, None, id="init-help"),
        pytest.param(["project"], 2, None, id="project-no-args"),
        pytest.param(["project", "--help"], 0, None, id="project-help"),
        pytest.param(["add", "--help"], 0, None, id="add-help"),
        pytest.param(["add", "1h"], 2, None, id="add-missing-note"),
        pytest.param(["add", "abc", "x"], 1, "오류: 시간 형식이", id="add-bad-duration"),
        pytest.param(["add", "2h", "x", "-d", "13-45"], 1, "오류: 날짜 형식이", id="add-bad-date"),
        pytest.param(["add", "1h", "x", "-t", "abc"], 1, "오류: 태스크 ID가", id="add-bad-task"),
        pytest.param(["log", "--help"], 0, None, id="log-help"),
        pytest.param(["log", "-w", "2026-W99"], 1, "오류: 주차 형식이", id="log-bad-week"),
        pytest.param(["log", "edit", "--help"], 0, None, id="log-edit-help"),
        pytest.param(["log", "rm", "--help"], 0, None, id="log-rm-help"),
        pytest.param(["log", "edit", "2"], 1, "오류: 바꿀 항목을", id="log-edit-nothing"),
        pytest.param(["log", "edit", "abc", "-n", "x"], 1, "오류: 기록 ID가", id="log-edit-bad-id"),
        pytest.param(
            ["log", "edit", "2", "-m", "abc"], 1, "오류: 시간 형식이", id="log-edit-bad-duration"
        ),
        pytest.param(
            ["log", "edit", "2", "-t", "x"], 1, "오류: 태스크 ID가", id="log-edit-bad-task"
        ),
        pytest.param(["log", "rm", "abc"], 1, "오류: 기록 ID가", id="log-rm-bad-id"),
        pytest.param(["task", "--help"], 0, None, id="task-help"),
        pytest.param(["task", "add", "--help"], 0, None, id="task-add-help"),
        pytest.param(["task", "list", "--help"], 0, None, id="task-list-help"),
        pytest.param(
            ["task", "add", "x", "--est", "abc"], 1, "오류: 시간 형식이", id="task-add-bad-est"
        ),
        pytest.param(["task", "list", "-s", "x"], 1, "오류: 상태가", id="task-list-bad-status"),
        pytest.param(["task", "edit", "--help"], 0, None, id="task-edit-help"),
        pytest.param(["task", "edit", "1"], 1, "오류: 바꿀 항목을", id="task-edit-nothing"),
        pytest.param(
            ["task", "edit", "1", "--est", "1h", "--no-est"],
            1,
            "오류: --est와 --no-est",
            id="task-edit-conflict",
        ),
        pytest.param(
            ["task", "edit", "abc", "--est", "1h"], 1, "오류: 태스크 ID가", id="task-edit-bad-id"
        ),
        pytest.param(["task", "start", "abc"], 1, "오류: 태스크 ID가", id="task-start-bad-id"),
        pytest.param(["task", "done", "--help"], 0, None, id="task-done-help"),
        pytest.param(["plan", "--help"], 0, None, id="plan-help"),
        pytest.param(["plan", "carry", "--help"], 0, None, id="plan-carry-help"),
        pytest.param(["plan", "-w", "x"], 1, "오류: 주차 형식이", id="plan-bad-week"),
        pytest.param(
            ["plan", "carry", "-w", "x"], 1, "오류: 주차 형식이", id="plan-carry-bad-week"
        ),
        pytest.param(["start", "--help"], 0, None, id="start-help"),
        pytest.param(["status", "--help"], 0, None, id="status-help"),
        pytest.param(["start", "x", "-t", "abc"], 1, "오류: 태스크 ID가", id="start-bad-task"),
        pytest.param(["stop", "--help"], 0, None, id="stop-help"),
        pytest.param(["stop", "--round", "abc"], 1, "오류: 반올림 단위가", id="stop-bad-round"),
        pytest.param(["cancel", "--help"], 0, None, id="cancel-help"),
        pytest.param(["stats", "--help"], 0, None, id="stats-help"),
        pytest.param(["stats", "--by", "x"], 1, "오류: 집계 기준이", id="stats-bad-by"),
        pytest.param(["stats", "-w", "2026-W99"], 1, "오류: 주차 형식이", id="stats-bad-week"),
    ],
)
def test_startup_does_not_load_heavy_modules(
    tmp_path: Path, args: list[str], exit_code: int | None, error: str | None
) -> None:
    # pytest 프로세스는 conftest 때문에 이미 sqlalchemy를 로드했으므로 새 인터프리터에서 확인한다.
    guard = run_import_guard(args, env=lb_env(tmp_path, "utf-8"), cwd=tmp_path)

    assert guard.loaded == [], f"금지 모듈 로드됨: {guard.loaded} (검사 대상: {FORBIDDEN_MODULES})"
    # 다른 이유(설정 오류 등)로 더 일찍 끝나 지연 import 경로를 지나지 않은 경우를 걸러 낸다.
    assert guard.exit_code == exit_code, guard.stderr
    if error is not None:
        assert guard.stderr.startswith(error), guard.stderr
