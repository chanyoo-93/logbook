"""scripts/bench_cli.py 측정 스크립트 테스트.

순수 함수(summarize, parse_importtime, render_markdown)와, subprocess.run을 가짜로 바꾼
main() 전체 흐름(측정 성공·실패, uv 행, 출력 파일)을 확인한다.
"""

import importlib.util
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bench_cli.py"


@pytest.fixture
def bench(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_cli", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # 등록하지 않으면 @dataclass가 문자열 어노테이션을 풀 때 모듈을 찾지 못한다.
    monkeypatch.setitem(sys.modules, "bench_cli", module)
    spec.loader.exec_module(module)
    return module


def test_summarize_returns_median_p90_min_and_runs(bench: ModuleType) -> None:
    assert bench.summarize([5, 1, 3, 2, 4]) == bench.Stats(3, 5, 1, 5)


def test_summarize_single_sample(bench: ModuleType) -> None:
    assert bench.summarize([10]) == bench.Stats(10, 10, 10, 1)


def test_summarize_empty_returns_none(bench: ModuleType) -> None:
    assert bench.summarize([]) is None


def test_summarize_p90_uses_nearest_rank(bench: ModuleType) -> None:
    # n=10: ceil(0.9·10)-1 = 8번째(0부터) → 9
    stats = bench.summarize([float(v) for v in range(10, 0, -1)])

    assert stats.p90_ms == 9
    assert stats.median_ms == 5.5


def test_parse_importtime_sums_self_time_by_top_level_package(bench: ModuleType) -> None:
    stderr_text = (
        "import time: self [us] | cumulative | imported package\n"
        "import time:      1000 |       1000 |     sqlalchemy.util\n"
        "import time:      2000 |       3000 |   sqlalchemy\n"
        "import time:       500 |        500 | typer\n"
        "import time:       250 |        250 |     logbook.core.duration\n"
        "import time:       100 |        100 | json\n"
        "✔ 기록 완료\n"
        "BENCH_MS=12.5\n"
    )

    result = bench.parse_importtime(stderr_text)

    assert result == {"sqlalchemy": 3.0, "typer": 0.5, "logbook": 0.25, "기타": 0.1}
    assert "rich" not in result


def test_parse_importtime_empty_input(bench: ModuleType) -> None:
    assert bench.parse_importtime("") == {}


def test_render_markdown_marks_failed_rows_and_ends_with_newline(bench: ModuleType) -> None:
    ok = bench.Stats(100.0, 120.0, 90.0, 5)
    rows = [
        ("기준선 python -c pass", ok, None),
        ("run() add", bench.Stats(300.0, 330.0, 280.0, 5), bench.Stats(200.0, 220.0, 190.0, 5)),
        ("lb add", None, None),
    ]

    text = bench.render_markdown({"OS": "TestOS", "runs": "5"}, rows, None)

    assert "| 항목 |" in text
    assert "TestOS" in text
    failed = [line for line in text.splitlines() if line.startswith("| lb add |")]
    assert failed
    assert "실패" in failed[0]
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_render_markdown_includes_import_breakdown(bench: ModuleType) -> None:
    text = bench.render_markdown({}, [], {"sqlalchemy": 380.0, "기타": 12.5})

    assert "| sqlalchemy | 380.0 |" in text
    assert "| 기타 | 12.5 |" in text
    assert text.endswith("\n")


def test_main_returns_zero_when_every_command_fails(
    bench: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def broken_run(args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise OSError("실행할 수 없음")

    monkeypatch.setattr(bench.subprocess, "run", broken_run)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    out_file = tmp_path / "한글 경로" / "bench.md"

    code = bench.main(["--runs", "2", "--warmup", "0", "--importtime", "--out", str(out_file)])

    captured = capsys.readouterr()
    assert code == 0
    assert "| 항목 |" in captured.out
    assert "실패" in captured.out
    assert out_file.read_bytes() == captured.out.encode("utf-8")


def _uv_row_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("| uv run lb add |")]


def test_main_with_uv_omits_uv_row_when_uv_is_missing(
    bench: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def broken_run(args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise OSError("실행할 수 없음")

    monkeypatch.setattr(bench.subprocess, "run", broken_run)
    monkeypatch.setattr(bench, "_find_uv", lambda: None)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    code = bench.main(["--runs", "1", "--warmup", "0", "--with-uv"])

    captured = capsys.readouterr()
    assert code == 0
    assert "| 항목 |" in captured.out
    assert _uv_row_lines(captured.out) == []
    assert "참고: uv를 찾지 못해" in captured.err
    assert "측정 경고: uv" not in captured.err


def test_main_with_uv_measures_uv_row_from_repo_root(
    bench: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    uv_cwds: list[Path] = []

    def broken_run(args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        if args[0] == "uv-fake":
            uv_cwds.append(kwargs["cwd"])
        raise OSError("실행할 수 없음")

    monkeypatch.setattr(bench.subprocess, "run", broken_run)
    monkeypatch.setattr(bench, "_find_uv", lambda: "uv-fake")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    code = bench.main(["--runs", "1", "--warmup", "0", "--with-uv"])

    captured = capsys.readouterr()
    assert code == 0
    assert uv_cwds == [bench.REPO_ROOT]
    rows = _uv_row_lines(captured.out)
    assert len(rows) == 1
    assert "실패" in rows[0]


def test_main_appends_to_github_step_summary(
    bench: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def broken_run(args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(args, 60)

    monkeypatch.setattr(bench.subprocess, "run", broken_run)
    summary = tmp_path / "summary.md"
    summary.write_bytes(b"before\n")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    code = bench.main(["--runs", "1", "--warmup", "0"])

    captured = capsys.readouterr()
    assert code == 0
    assert summary.read_bytes() == b"before\n" + captured.out.encode("utf-8")
    assert b"\r\n" not in summary.read_bytes()


def test_render_markdown_failed_row_has_no_run_count(bench: ModuleType) -> None:
    text = bench.render_markdown({}, [("lb add", None, None)], None)

    assert "| lb add | 실패 | 실패 | 실패 | 실패 | 실패 | - |" in text.splitlines()


def test_render_markdown_derived_difference_never_shows_negative_zero(bench: ModuleType) -> None:
    rows = [
        ("기준선 python -c pass", bench.Stats(100.04, 100.04, 100.04, 1), None),
        ("run() add", bench.Stats(100.0, 100.0, 100.0, 1), None),
    ]

    lines = bench.render_markdown({}, rows, None).splitlines()

    assert "| 순수 처리 추정 (run() add - 기준선) | 0.0 |" in lines


def test_driver_reports_bench_ms_after_partial_stderr_line(
    bench: ModuleType, tmp_path: Path
) -> None:
    # CLI가 줄바꿈 없이 stderr 출력을 끝내도 BENCH_MS 줄을 찾아야 한다.
    tail = "from logbook.cli.main import run\n\nrun()\n"
    assert bench.DRIVER_CODE.endswith(tail)
    code = bench.DRIVER_CODE.removesuffix(tail) + "sys.stderr.write('partial warning')\n"
    command = bench.Command("driver", (sys.executable, "-c", code), tmp_path, has_inner=True)

    sample = bench._run_once(command, dict(bench.os.environ))

    assert sample is not None
    assert sample[1] is not None


class _FakeRunner:
    """가짜 subprocess.run과 시계.

    명령마다 정해진 벽시계 시간만큼 시계를 진행하고, 명령별 호출 순번 n으로 BENCH_MS=n.0을 쓴다.
    """

    def __init__(self, bench: ModuleType, add_result: tuple[int, bytes] | None = None) -> None:
        self._bench = bench
        self._add_result = add_result
        self.now = 0.0
        self.calls: dict[tuple[str, ...], int] = {}

    def perf_counter(self) -> float:
        return self.now

    def _is_run_add(self, key: tuple[str, ...]) -> bool:
        return self._bench.DRIVER_CODE in key and "add" in key

    def _wall_ms(self, key: tuple[str, ...]) -> float:
        if key == (sys.executable, "-c", "pass"):
            return 10.0
        if self._is_run_add(key):
            return 50.0
        if key[0] == "lb-fake" and "add" in key:
            return 80.0
        return 20.0

    def run(self, args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        key = tuple(args)
        n = self.calls.get(key, 0) + 1
        self.calls[key] = n
        self.now += self._wall_ms(key) / 1000
        if self._add_result is not None and self._is_run_add(key):
            returncode, stderr = self._add_result
            return subprocess.CompletedProcess(args, returncode, b"", stderr)
        return subprocess.CompletedProcess(args, 0, b"", f"BENCH_MS={n}.0\n".encode())


def _install_fake_runner(
    bench: ModuleType, monkeypatch: pytest.MonkeyPatch, runner: _FakeRunner
) -> None:
    monkeypatch.setattr(bench.subprocess, "run", runner.run)
    monkeypatch.setattr(bench, "time", SimpleNamespace(perf_counter=runner.perf_counter))
    monkeypatch.setattr(bench, "_find_lb", lambda: "lb-fake")
    monkeypatch.setattr(bench, "_find_uv", lambda: None)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


def test_main_discards_warmup_and_reports_inner_and_derived_times(
    bench: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_fake_runner(bench, monkeypatch, _FakeRunner(bench))

    code = bench.main(["--runs", "3", "--warmup", "2"])

    lines = capsys.readouterr().out.splitlines()
    assert code == 0
    # 내부 시간 1, 2는 warmup으로 버리고 3, 4, 5만 남는다 → 중앙값 4, p90 5
    assert "| run() add | 50.0 | 50.0 | 50.0 | 4.0 | 5.0 | 3 |" in lines
    assert "| 기준선 python -c pass | 10.0 | 10.0 | 10.0 | - | - | 3 |" in lines
    assert "| 순수 처리 추정 (run() add - 기준선) | 40.0 |" in lines
    assert "| 실행 파일 오버헤드 (lb add - run() add) | 30.0 |" in lines


@pytest.mark.parametrize(
    "add_result",
    [(1, b"Error: boom\n"), (0, b"no timing here\n")],
    ids=["nonzero-exit", "missing-bench-ms"],
)
def test_main_marks_run_add_failed(
    bench: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    add_result: tuple[int, bytes],
) -> None:
    _install_fake_runner(bench, monkeypatch, _FakeRunner(bench, add_result))

    code = bench.main(["--runs", "3", "--warmup", "2"])

    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert code == 0
    assert "| run() add | 실패 | 실패 | 실패 | 실패 | 실패 | - |" in lines
    assert "| 순수 처리 추정 (run() add - 기준선) | 실패 |" in lines
    assert "| 실행 파일 오버헤드 (lb add - run() add) | 실패 |" in lines
    assert "| 기준선 python -c pass | 10.0 | 10.0 | 10.0 | - | - | 3 |" in lines
    assert "측정 경고: run() add" in captured.err


def test_main_returns_zero_when_collect_raises_unexpectedly(
    bench: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def exploding_collect(*args: Any, **kwargs: Any) -> str:
        raise RuntimeError("예상하지 못한 오류")

    monkeypatch.setattr(bench, "_collect", exploding_collect)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    code = bench.main(["--runs", "1", "--warmup", "0"])

    captured = capsys.readouterr()
    assert code == 0
    assert "| 항목 |" in captured.out
    assert "실패" in captured.out
    assert "측정 경고" in captured.err
    assert "예상하지 못한 오류" in captured.err
