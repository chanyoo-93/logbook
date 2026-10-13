"""좁은 화면(320px)에서 넘치지 않게 하는 스타일 규칙이 남아 있는지 확인하는 구조 테스트.

실제 폭은 브라우저로 재야 하지만, 규칙을 되돌리는 실수는 여기서 잡는다.
"""

import re
from pathlib import Path

import pytest

import logbook.web

CSS_ROOT = Path(logbook.web.__file__).parent / "static" / "css"


def _declarations(file_name: str, selector: str) -> str:
    """파일에서 정확히 `selector {`로 시작하는 첫 규칙의 선언부."""
    css = (CSS_ROOT / file_name).read_text(encoding="utf-8")
    match = re.search(rf"(?m)^{re.escape(selector)} \{{([^}}]*)\}}", css)
    assert match, f"{file_name}에 {selector} 규칙이 없습니다"
    return match.group(1)


@pytest.mark.parametrize(
    ("file_name", "selector", "declaration"),
    [
        ("logs.css", ".week-nav", "flex-wrap: wrap"),
        ("dashboard.css", ".charts", "minmax(0, 2fr) minmax(0, 1fr)"),
        ("dashboard.css", ".chart", "min-width: 0"),
        ("tasks.css", ".plan", "padding: var(--space-3)"),
        ("tasks.css", ".task-edit input,\n.task-edit select", "min-height: 2.25rem"),
        ("tasks.css", ".task-edit input,\n.task-edit select", "border: 1px solid var(--ink-muted)"),
        ("report.css", ".report > .form-message:empty", "margin: 0"),
    ],
)
def test_layout_rule_is_declared(file_name: str, selector: str, declaration: str) -> None:
    assert declaration in _declarations(file_name, selector)


def test_narrow_chart_grid_can_shrink() -> None:
    css = (CSS_ROOT / "tasks.css").read_text(encoding="utf-8")

    assert "grid-template-columns: minmax(0, 1fr);" in css
