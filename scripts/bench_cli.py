"""lb CLI 응답 시간을 재서 Markdown 표로 보고한다.

표준 라이브러리만 쓴다. 측정이 실패해도 항상 종료 코드 0으로 끝난다(CI 비차단 보고).

    uv run python scripts/bench_cli.py
    uv run python scripts/bench_cli.py --runs 20 --with-uv --importtime --out bench.md

- 벽시계: 프로세스를 띄운 순간부터 끝날 때까지(time.perf_counter, 이 스크립트에서 잼)
- 내부: 드라이버 코드 첫 줄부터 인터프리터 종료 직전까지(import 포함, 파이썬 내부 시간)
"""

from __future__ import annotations

import argparse
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RUNS = 15
DEFAULT_WARMUP = 3
SUBPROCESS_TIMEOUT_SECONDS = 60
# 오류를 보고할 때 남길 stderr 끝부분 길이(글자)
ERROR_TAIL_CHARS = 300

ADD_ARGS = ("add", "10m", "측정", "-c", "dev")

FAILED = "실패"
NOT_MEASURED = "-"

# importtime 분해에서 따로 합산하는 최상위 패키지. 나머지는 OTHER_PACKAGE로 묶는다.
IMPORT_GROUPS = ("sqlalchemy", "typer", "rich", "logbook")
OTHER_PACKAGE = "기타"

LABEL_BASELINE = "기준선 python -c pass"
LABEL_RUN_VERSION = "run() --version"
LABEL_RUN_HELP = "run() --help"
LABEL_RUN_ADD = "run() add"
LABEL_LB_VERSION = "lb --version"
LABEL_LB_ADD = "lb add"
LABEL_UV_ADD = "uv run lb add"

# (이름, 피감수 행, 감수 행): 두 행의 벽시계 중앙값 차이
DERIVED = (
    ("순수 처리 추정 (run() add - 기준선)", LABEL_RUN_ADD, LABEL_BASELINE),
    ("실행 파일 오버헤드 (lb add - run() add)", LABEL_LB_ADD, LABEL_RUN_ADD),
)

# sys.executable -c 로 실행한다. 첫 줄에서 시작 시각을 잡고, 종료 직전에 경과 시간을 stderr에 쓴다.
# 앞의 stderr 출력이 줄바꿈 없이 끝났어도 BENCH_MS가 줄 맨 앞에 오도록 먼저 줄을 바꾼다.
DRIVER_CODE = """\
from time import perf_counter; t0 = perf_counter()
import atexit
import sys


def _report_elapsed():
    sys.stderr.write(f"\\nBENCH_MS={(perf_counter() - t0) * 1000:.3f}\\n")
    sys.stderr.flush()


atexit.register(_report_elapsed)
sys.argv = ["lb", *sys.argv[1:]]
from logbook.cli.main import run

run()
"""

_BENCH_MS_RE = re.compile(r"^BENCH_MS=(\d+(?:\.\d+)?)\s*$", re.MULTILINE)
_IMPORTTIME_RE = re.compile(r"^import time:\s*(\d+)\s*\|\s*\d+\s*\|\s*(\S+)\s*$")


@dataclass(frozen=True)
class Stats:
    median_ms: float
    p90_ms: float
    min_ms: float
    runs: int


@dataclass(frozen=True)
class Command:
    label: str
    args: tuple[str, ...]
    cwd: Path
    has_inner: bool = False
    # 실행할 수 없는 행이면 그 이유. 이때 args는 비어 있고 행은 실패로 표시한다.
    skip_reason: str | None = None


Row = tuple[str, Stats | None, Stats | None]


def summarize(samples_ms: Sequence[float]) -> Stats | None:
    """중앙값, p90(nearest-rank), 최솟값, 횟수. 빈 입력은 None."""
    if not samples_ms:
        return None
    ordered = sorted(samples_ms)
    rank = math.ceil(len(ordered) * 9 / 10)
    return Stats(
        median_ms=statistics.median(ordered),
        p90_ms=ordered[rank - 1],
        min_ms=ordered[0],
        runs=len(ordered),
    )


def parse_importtime(stderr_text: str) -> dict[str, float]:
    """'-X importtime' 출력의 self 시간을 최상위 패키지별로 합한다(ms).

    입력에 나타난 묶음만 키로 넣는다.
    """
    totals_us: dict[str, int] = {}
    for line in stderr_text.splitlines():
        match = _IMPORTTIME_RE.match(line)
        if match is None:
            continue
        top = match.group(2).split(".", 1)[0]
        group = top if top in IMPORT_GROUPS else OTHER_PACKAGE
        totals_us[group] = totals_us.get(group, 0) + int(match.group(1))
    return {group: us / 1000 for group, us in totals_us.items()}


def _ms(value: float) -> str:
    # 0에 가까운 음수가 '-0.0'으로 보이지 않게 음의 0을 0으로 바꾼다.
    return f"{round(value, 1) + 0.0:.1f}"


def _stats_cells(stats: Stats | None) -> list[str]:
    if stats is None:
        return [NOT_MEASURED] * 2
    return [_ms(stats.median_ms), _ms(stats.p90_ms)]


def _table_row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _timing_table(rows: Sequence[Row]) -> list[str]:
    lines = [
        _table_row(
            [
                "항목",
                "벽시계 중앙값 (ms)",
                "벽시계 p90 (ms)",
                "벽시계 최소 (ms)",
                "내부 중앙값 (ms)",
                "내부 p90 (ms)",
                "횟수",
            ]
        ),
        _table_row(["---", "---:", "---:", "---:", "---:", "---:", "---:"]),
    ]
    for label, wall, inner in rows:
        if wall is None:
            lines.append(_table_row([label, *[FAILED] * 5, NOT_MEASURED]))
            continue
        lines.append(
            _table_row(
                [
                    label,
                    _ms(wall.median_ms),
                    _ms(wall.p90_ms),
                    _ms(wall.min_ms),
                    *_stats_cells(inner),
                    str(wall.runs),
                ]
            )
        )
    return lines


def _derived_table(rows: Sequence[Row]) -> list[str]:
    """두 행의 벽시계 중앙값 차이. 관련 행이 하나도 없으면 표를 만들지 않는다."""
    labels = {label for label, _, _ in rows}
    medians = {label: wall.median_ms for label, wall, _ in rows if wall is not None}
    lines: list[str] = []
    for name, minuend, subtrahend in DERIVED:
        if minuend not in labels and subtrahend not in labels:
            continue
        if minuend in medians and subtrahend in medians:
            value = _ms(medians[minuend] - medians[subtrahend])
        else:
            value = FAILED
        lines.append(_table_row([name, value]))
    if not lines:
        return []
    return [
        "",
        _table_row(["파생", "벽시계 중앙값 차이 (ms)"]),
        _table_row(["---", "---:"]),
        *lines,
    ]


def _import_table(imports: Mapping[str, float]) -> list[str]:
    lines = ["", f"import 시간 분해 ({LABEL_RUN_ADD}, -X importtime self 시간 합계, 1회)", ""]
    if not imports:
        return [*lines, f"import 시간: {FAILED}"]
    lines += [_table_row(["패키지", "self 합계 (ms)"]), _table_row(["---", "---:"])]
    for group, value in sorted(imports.items(), key=lambda item: (-item[1], item[0])):
        lines.append(_table_row([group, _ms(value)]))
    return lines


def render_markdown(
    meta: Mapping[str, str],
    rows: Sequence[Row],
    imports: Mapping[str, float] | None,
) -> str:
    """환경 정보, 시간 표, 파생 값, import 분해(있으면)를 Markdown으로 만든다."""
    lines = ["## lb CLI 응답 시간", ""]
    lines += [f"- {key}: {value}" for key, value in meta.items()]
    lines += [
        "- 벽시계: 프로세스 시작부터 종료까지. 내부: run() 드라이버의 import부터 종료까지"
        f"({NOT_MEASURED}는 해당 없음)",
        "",
        *_timing_table(rows),
        *_derived_table(rows),
    ]
    if imports is not None:
        lines += _import_table(imports)
    return "\n".join(lines) + "\n"


def _emit(text: str, stream: TextIO) -> None:
    """콘솔 인코딩(cp949, cp1252)과 무관하게 UTF-8로 쓴다."""
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        stream.write(text)
        stream.flush()
        return
    stream.flush()
    buffer.write(text.encode("utf-8"))
    buffer.flush()


def _warn(message: str) -> None:
    _emit(f"측정 경고: {message}\n", sys.stderr)


def _tail(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").strip()[-ERROR_TAIL_CHARS:]


def _run_once(command: Command, env: Mapping[str, str]) -> tuple[float, float | None] | None:
    """한 번 실행해 (벽시계 ms, 내부 ms 또는 None)을 돌려준다. 실패하면 None."""
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            list(command.args),
            shell=False,
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            cwd=command.cwd,
            env=dict(env),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _warn(f"{command.label}: {exc}")
        return None
    wall_ms = (time.perf_counter() - start) * 1000
    if proc.returncode != 0:
        _warn(f"{command.label}: 종료 코드 {proc.returncode}: {_tail(proc.stderr)}")
        return None
    if not command.has_inner:
        return wall_ms, None
    match = _BENCH_MS_RE.search(proc.stderr.decode("utf-8", errors="replace"))
    if match is None:
        _warn(f"{command.label}: 내부 시간(BENCH_MS)을 찾지 못했습니다")
        return None
    return wall_ms, float(match.group(1))


def _measure(
    command: Command, env: Mapping[str, str], runs: int, warmup: int
) -> tuple[Stats | None, Stats | None]:
    """warmup번 버리고 runs번 잰다. 한 번이라도 실패하면 (None, None)."""
    walls: list[float] = []
    inners: list[float] = []
    for index in range(warmup + runs):
        sample = _run_once(command, env)
        if sample is None:
            return None, None
        if index < warmup:
            continue
        wall_ms, inner_ms = sample
        walls.append(wall_ms)
        if inner_ms is not None:
            inners.append(inner_ms)
    return summarize(walls), summarize(inners)


def _measure_imports(python: str, workdir: Path, env: Mapping[str, str]) -> dict[str, float]:
    """run() add 경로를 '-X importtime'으로 한 번 실행해 패키지별로 나눈다. 실패하면 빈 dict."""
    args = (python, "-X", "importtime", "-c", DRIVER_CODE, *ADD_ARGS)
    try:
        proc = subprocess.run(
            list(args),
            shell=False,
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            cwd=workdir,
            env=dict(env),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _warn(f"importtime: {exc}")
        return {}
    if proc.returncode != 0:
        _warn(f"importtime: 종료 코드 {proc.returncode}: {_tail(proc.stderr)}")
        return {}
    return parse_importtime(proc.stderr.decode("utf-8", errors="replace"))


def _find_lb() -> str | None:
    """venv 실행 파일 디렉터리에서 lb 실행 파일을 찾는다."""
    return shutil.which("lb", path=str(Path(sys.executable).parent))


def _find_uv() -> str | None:
    # uv run은 하위 프로세스에 자기 경로를 UV로 넘긴다.
    return os.environ.get("UV") or shutil.which("uv")


def _commands(workdir: Path, uv: str | None) -> list[Command]:
    """측정할 명령 목록. uv가 None이면 uv 행을 만들지 않는다.

    lb 실행 파일을 찾지 못한 행은 args 없이 skip_reason을 채운다.
    """
    python = sys.executable
    items = [
        Command(LABEL_BASELINE, (python, "-c", "pass"), workdir),
        Command(
            LABEL_RUN_VERSION, (python, "-c", DRIVER_CODE, "--version"), workdir, has_inner=True
        ),
        Command(LABEL_RUN_HELP, (python, "-c", DRIVER_CODE, "--help"), workdir, has_inner=True),
        Command(LABEL_RUN_ADD, (python, "-c", DRIVER_CODE, *ADD_ARGS), workdir, has_inner=True),
    ]
    launcher = _find_lb()
    if launcher is None:
        reason = "lb 실행 파일을 찾지 못했습니다(uv sync를 실행하세요)"
        items += [
            Command(LABEL_LB_VERSION, (), workdir, skip_reason=reason),
            Command(LABEL_LB_ADD, (), workdir, skip_reason=reason),
        ]
    else:
        items += [
            Command(LABEL_LB_VERSION, (launcher, "--version"), workdir),
            Command(LABEL_LB_ADD, (launcher, *ADD_ARGS), workdir),
        ]
    if uv is not None:
        # 임시 디렉터리에서는 uv가 프로젝트를 찾지 못하므로 저장소 루트에서 실행한다.
        items.append(Command(LABEL_UV_ADD, (uv, "run", "lb", *ADD_ARGS), REPO_ROOT))
    return items


def _meta(runs: int, warmup: int) -> dict[str, str]:
    return {
        "OS": platform.platform(),
        "Python": platform.python_version(),
        "CPU 수": str(os.cpu_count() or "알 수 없음"),
        "runs": str(runs),
        "warmup": str(warmup),
    }


def _write_text(path: Path, text: str, mode: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open(mode, encoding="utf-8", newline="\n") as f:
            f.write(text)
    except OSError as exc:
        _warn(f"{path}: 쓰지 못했습니다: {exc}")


def _non_negative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"정수가 아닙니다: {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"0 이상이어야 합니다: {value}")
    return value


def _positive_int(text: str) -> int:
    value = _non_negative_int(text)
    if value == 0:
        raise argparse.ArgumentTypeError("1 이상이어야 합니다: 0")
    return value


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="lb CLI 응답 시간을 재서 Markdown 표로 보고한다.")
    parser.add_argument("--runs", type=_positive_int, default=DEFAULT_RUNS, help="측정 반복 횟수")
    parser.add_argument(
        "--warmup", type=_non_negative_int, default=DEFAULT_WARMUP, help="버리는 사전 실행 횟수"
    )
    parser.add_argument("--with-uv", action="store_true", help="uv run lb add도 잰다")
    parser.add_argument(
        "--importtime", action="store_true", help="run() add 경로의 import 시간을 패키지별로 나눈다"
    )
    parser.add_argument("--out", type=Path, default=None, help="Markdown 표를 저장할 파일")
    return parser.parse_args(argv)


def _collect(runs: int, warmup: int, with_uv: bool, importtime: bool) -> str:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        workdir = Path(tmp)
        env = {
            **os.environ,
            "LOGBOOK_DB": str(workdir / "logbook.db"),
            "LOGBOOK_CONFIG": str(workdir / "config.toml"),
        }
        init = Command("lb init", (sys.executable, "-c", DRIVER_CODE, "init"), workdir)
        if _run_once(init, env) is None:
            _warn("lb init에 실패해 add 행은 실패로 표시될 수 있습니다")

        uv = _find_uv() if with_uv else None
        if with_uv and uv is None:
            # uv가 없으면 행을 만들지 않는다(실패로 표시하지 않음).
            _emit(f"참고: uv를 찾지 못해 {LABEL_UV_ADD} 행을 생략합니다\n", sys.stderr)

        rows: list[Row] = []
        for command in _commands(workdir, uv):
            if command.skip_reason is not None:
                _warn(f"{command.label}: {command.skip_reason}")
                rows.append((command.label, None, None))
                continue
            wall, inner = _measure(command, env, runs, warmup)
            rows.append((command.label, wall, inner))

        imports = _measure_imports(sys.executable, workdir, env) if importtime else None
    return render_markdown(_meta(runs, warmup), rows, imports)


def main(argv: Sequence[str] | None = None) -> int:
    """측정 결과를 stdout(과 --out, GITHUB_STEP_SUMMARY)에 쓴다. 측정이 실패해도 항상 0."""
    args = _parse_args(argv)
    try:
        report = _collect(args.runs, args.warmup, args.with_uv, args.importtime)
    except Exception as exc:
        # 예상하지 못한 오류도 보고만 하고 CI를 막지 않는다.
        _warn(f"측정을 끝내지 못했습니다: {exc!r}")
        report = render_markdown({**_meta(args.runs, args.warmup), "측정": FAILED}, [], None)
    _emit(report, sys.stdout)
    if args.out is not None:
        _write_text(args.out, report, "w")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        _write_text(Path(summary_path), report, "a")
    return 0


if __name__ == "__main__":
    sys.exit(main())
