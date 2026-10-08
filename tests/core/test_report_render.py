"""core.report 의 Markdown 렌더링과 기본·사용자 템플릿 테스트."""

import os
import shutil
import subprocess
import zipfile
from dataclasses import replace
from importlib import resources
from pathlib import Path

import jinja2
import pytest

from logbook.core.errors import InvalidInputError
from logbook.core.report import (
    TEMPLATE_NAME,
    MatrixRow,
    PlanGroup,
    PlanItem,
    ProjectSection,
    ReportData,
    TaskLine,
    render_markdown,
    user_template_path,
)

THREE_PROJECTS = """\
# 주간업무보고 (2026-09-28 ~ 2026-10-04)
작성자: 홍길동

## 1. 공수 요약
총 35h (기록 41건, 완료 태스크 6건)

| 프로젝트 | 개발 | 코드리뷰 | 회의 | 행정/기타 | 합계 | 비율 |
|---|---|---|---|---|---|---|
| payment | 14h | 3h | 2h | - | 19h | 54% |
| admin | 6h | 1h | 1h | - | 8h | 23% |
| common | - | - | 5h | 3h | 8h | 23% |

## 2. 프로젝트별 실적
### payment (19h)
- [완료] 결제 재시도 로직 구현 (#42) — 실제 8h / 예상 6h
- [진행] 환불 API 설계 (#43) — 누적 3h / 예상 4h
- 기타: 개발 3h, 코드리뷰 3h, 회의 2h

### admin (8h)
- [진행] 권한 정리 (#45) — 누적 6h / 예상 10h
- 기타: 코드리뷰 1h, 회의 1h

### common (8h)
- 기타: 회의 5h, 행정/기타 3h

## 3. 특이사항 / 리스크
(작성하세요)

## 4. 다음 주 계획
### admin (예상 10h)
- 권한 정리 (#45) — 예상 10h (이월 후보)

### payment (예상 12h)
- 환불 API 구현 (#44) — 예상 8h
- 환불 API 설계 (#43) — 예상 4h (이월 후보)
"""

EMPTY_WEEK = """\
# 주간업무보고 (2026-09-28 ~ 2026-10-04)

## 1. 공수 요약
총 0m (기록 0건, 완료 태스크 0건)

## 2. 프로젝트별 실적
기록이 없습니다.

## 3. 특이사항 / 리스크
(작성하세요)

## 4. 다음 주 계획
계획된 태스크가 없습니다.
"""


def three_project_data() -> ReportData:
    return ReportData(
        title="주간업무보고 (2026-09-28 ~ 2026-10-04)",
        author="홍길동",
        week_label="2026-W40",
        start="2026-09-28",
        end="2026-10-04",
        total="35h",
        log_count=41,
        done_task_count=6,
        categories=("개발", "코드리뷰", "회의", "행정/기타"),
        matrix=(
            MatrixRow("payment", ("14h", "3h", "2h", "-"), "19h", "54%"),
            MatrixRow("admin", ("6h", "1h", "1h", "-"), "8h", "23%"),
            MatrixRow("common", ("-", "-", "5h", "3h"), "8h", "23%"),
        ),
        sections=(
            ProjectSection(
                "payment",
                "19h",
                (
                    TaskLine("완료", "결제 재시도 로직 구현", 42, "8h", "6h", "실제"),
                    TaskLine("진행", "환불 API 설계", 43, "3h", "4h", "누적"),
                ),
                (("개발", "3h"), ("코드리뷰", "3h"), ("회의", "2h")),
            ),
            ProjectSection(
                "admin",
                "8h",
                (TaskLine("진행", "권한 정리", 45, "6h", "10h", "누적"),),
                (("코드리뷰", "1h"), ("회의", "1h")),
            ),
            ProjectSection("common", "8h", (), (("회의", "5h"), ("행정/기타", "3h"))),
        ),
        plan=(
            PlanGroup("admin", "10h", (PlanItem("권한 정리", 45, "10h", True),)),
            PlanGroup(
                "payment",
                "12h",
                (
                    PlanItem("환불 API 구현", 44, "8h", False),
                    PlanItem("환불 API 설계", 43, "4h", True),
                ),
            ),
        ),
    )


def empty_data() -> ReportData:
    return ReportData(
        title="주간업무보고 (2026-09-28 ~ 2026-10-04)",
        author="",
        week_label="2026-W40",
        start="2026-09-28",
        end="2026-10-04",
        total="0m",
        log_count=0,
        done_task_count=0,
        categories=(),
        matrix=(),
        sections=(),
        plan=(),
    )


def write_template(tmp_path: Path, content: bytes) -> Path:
    path = tmp_path / TEMPLATE_NAME
    path.write_bytes(content)
    return path


def test_three_projects_exact_output() -> None:
    assert render_markdown(three_project_data()) == THREE_PROJECTS


def test_empty_week_exact_output() -> None:
    assert render_markdown(empty_data()) == EMPTY_WEEK


def test_empty_week_shows_done_task_count() -> None:
    text = render_markdown(replace(empty_data(), done_task_count=2))
    assert "총 0m (기록 0건, 완료 태스크 2건)" in text
    assert "기록이 없습니다." in text
    assert "|" not in text


def test_no_author_drops_author_line() -> None:
    text = render_markdown(replace(three_project_data(), author=""))
    assert "작성자" not in text
    assert text.startswith("# 주간업무보고 (2026-09-28 ~ 2026-10-04)\n\n## 1.")


def test_no_plan_shows_placeholder() -> None:
    text = render_markdown(replace(three_project_data(), plan=()))
    assert text.endswith("## 4. 다음 주 계획\n계획된 태스크가 없습니다.\n")


def test_task_without_estimate_and_plan_item_without_estimate() -> None:
    data = three_project_data()
    section = replace(
        data.sections[0],
        tasks=(TaskLine("할 일", "초안", 7, "0m", None, "누적"),),
        others=(),
    )
    group = PlanGroup("payment", "0m", (PlanItem("초안", 7, None, False),))
    text = render_markdown(replace(data, sections=(section,), plan=(group,)))
    assert "- [할 일] 초안 (#7) — 누적 0m\n" in text
    assert "- 초안 (#7)\n" in text
    assert "- 기타:" not in text


def test_pipe_in_table_cells_is_escaped_but_not_in_lists() -> None:
    data = three_project_data()
    data = replace(
        data,
        categories=("a|b", "코드리뷰", "회의", "행정/기타"),
        matrix=(replace(data.matrix[0], project="p|q"), *data.matrix[1:]),
        sections=(replace(data.sections[0], project="p|q"), *data.sections[1:]),
    )
    text = render_markdown(data)
    assert "| 프로젝트 | a\\|b | 코드리뷰 |" in text
    assert "| p\\|q | 14h |" in text
    assert "### p|q (19h)" in text


def test_user_template_path_is_next_to_config() -> None:
    config = Path("some") / "dir" / "config.toml"
    assert user_template_path(config) == Path("some") / "dir" / TEMPLATE_NAME


def test_user_template_overrides_default(tmp_path: Path) -> None:
    path = write_template(tmp_path, b"{{ data.title }}")
    assert render_markdown(empty_data(), template_path=path) == (
        "주간업무보고 (2026-09-28 ~ 2026-10-04)\n"
    )


def test_user_template_with_bom(tmp_path: Path) -> None:
    path = write_template(tmp_path, b"\xef\xbb\xbf" + "{{ data.author }}가".encode())
    text = render_markdown(replace(empty_data(), author="홍"), template_path=path)
    assert text == "홍가\n"


def test_user_template_crlf_becomes_lf(tmp_path: Path) -> None:
    path = write_template(tmp_path, b"a\r\nb\r\n\r\n")
    assert render_markdown(empty_data(), template_path=path) == "a\nb\n"


def test_missing_template_file_uses_default(tmp_path: Path) -> None:
    missing = tmp_path / TEMPLATE_NAME
    assert render_markdown(empty_data(), template_path=missing) == EMPTY_WEEK


def test_syntax_error_message(tmp_path: Path) -> None:
    path = write_template(tmp_path, b"a\nb\n{% if %}\n")
    with pytest.raises(InvalidInputError) as info:
        render_markdown(empty_data(), template_path=path)
    message = str(info.value)
    prefix = f"보고서 템플릿을 읽지 못했습니다: {path} (3번째 줄: "
    suffix = "). 기본 템플릿을 쓰려면 이 파일을 지우거나 이름을 바꾸세요."
    assert message.startswith(prefix)
    assert message.endswith(suffix)
    assert "Expected an expression" in message  # 가운데는 Jinja2가 만든 {message}다.


@pytest.mark.parametrize(
    ("source", "name", "lineno"),
    [
        (
            "a\n{{ data.titel }}\n",
            "'logbook.core.report.ReportData object' has no attribute 'titel'",
            2,
        ),
        ("{{ foo }}", "'foo' is undefined", 1),
    ],
)
def test_undefined_error_message(tmp_path: Path, source: str, name: str, lineno: int) -> None:
    path = write_template(tmp_path, source.encode())
    with pytest.raises(InvalidInputError) as info:
        render_markdown(empty_data(), template_path=path)
    message = str(info.value)
    prefix = f"보고서 템플릿에 없는 값을 썼습니다: {path} ({lineno}번째 줄: "
    suffix = "). 쓸 수 있는 값은 README의 '보고서 템플릿' 절을 보세요."
    assert message.startswith(prefix)
    assert message.endswith(suffix)
    assert name in message


PROCESS_PREFIX = "보고서 템플릿을 처리하지 못했습니다: "
PROCESS_SUFFIX = "). 템플릿을 고치거나, 기본 템플릿을 쓰려면 이 파일을 지우거나 이름을 바꾸세요."


@pytest.mark.parametrize(
    ("source", "lineno", "error_name"),
    [
        ("{% if data.author %}{{ data.author | nofilter }}{% endif %}", 1, "TemplateRuntimeError"),
        ("x\n{{ data.log_count + '건' }}", 2, "TypeError"),
        ("\n\n{{ 1 / 0 }}", 3, "ZeroDivisionError"),
        ("{% include 'x.j2' %}", 1, "TypeError"),
    ],
)
def test_runtime_error_message(tmp_path: Path, source: str, lineno: int, error_name: str) -> None:
    path = write_template(tmp_path, source.encode())
    data = replace(empty_data(), author="홍")
    with pytest.raises(InvalidInputError) as info:
        render_markdown(data, template_path=path)
    message = str(info.value)
    assert message.startswith(f"{PROCESS_PREFIX}{path} ({lineno}번째 줄: {error_name}: ")
    assert message.endswith(PROCESS_SUFFIX)


def test_runtime_error_message_uses_only_first_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(self: object, *args: object, **kwargs: object) -> str:
        raise RuntimeError("첫 줄\n둘째 줄")

    monkeypatch.setattr(jinja2.Template, "render", fail)
    path = write_template(tmp_path, b"x")
    with pytest.raises(InvalidInputError) as info:
        render_markdown(empty_data(), template_path=path)
    message = str(info.value)
    assert "RuntimeError: 첫 줄)" in message
    assert "\n" not in message


def test_unknown_filter_outside_if_is_syntax_error(tmp_path: Path) -> None:
    path = write_template(tmp_path, b"a\n{{ data.title | nofilter }}")
    with pytest.raises(InvalidInputError) as info:
        render_markdown(empty_data(), template_path=path)
    message = str(info.value)
    assert message.startswith(f"보고서 템플릿을 읽지 못했습니다: {path} (2번째 줄: ")
    assert "nofilter" in message


def test_cp949_template_is_reported(tmp_path: Path) -> None:
    path = write_template(tmp_path, "{# 한글 주석 #}".encode("cp949"))
    with pytest.raises(InvalidInputError) as info:
        render_markdown(empty_data(), template_path=path)
    assert str(info.value) == (
        f"보고서 템플릿을 UTF-8로 읽을 수 없습니다: {path}. 파일을 UTF-8로 다시 저장하세요."
    )


def test_utf16_template_is_reported(tmp_path: Path) -> None:
    path = write_template(tmp_path, "{{ data.title }}".encode("utf-16"))
    with pytest.raises(InvalidInputError) as info:
        render_markdown(empty_data(), template_path=path)
    assert str(info.value) == (
        f"보고서 템플릿을 UTF-8로 읽을 수 없습니다: {path}. 파일을 UTF-8로 다시 저장하세요."
    )


def test_unreadable_template_path_is_reported(tmp_path: Path) -> None:
    folder = tmp_path / TEMPLATE_NAME
    folder.mkdir()
    with pytest.raises(InvalidInputError) as info:
        render_markdown(empty_data(), template_path=folder)
    assert str(info.value).startswith(f"보고서 템플릿 파일을 열 수 없습니다: {folder} (")
    assert str(info.value).endswith(").")


def test_default_template_resource_is_a_real_file() -> None:
    resource = resources.files("logbook.core").joinpath("templates/report.md.j2")
    assert resource.is_file()
    assert Path(str(resource)).is_file()


@pytest.mark.subprocess
def test_wheel_contains_default_template(tmp_path: Path) -> None:
    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        pytest.skip("uv가 없어 휠 빌드를 건너뜁니다")
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(tmp_path), str(repo_root)],
        shell=False,
        capture_output=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        assert "logbook/core/templates/report.md.j2" in archive.namelist()
