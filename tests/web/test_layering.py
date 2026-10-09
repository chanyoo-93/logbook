"""web 계층 규칙: logbook.cli를 import하지 않고, SQL·ORM은 타입 표기로만 import한다."""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

import logbook.web
from tests.cli.helpers import SUBPROCESS_TIMEOUT_SECONDS

WEB_ROOT = Path(logbook.web.__file__).parent
_PROBE = """\
import json
import sys

import logbook.web.app

print(json.dumps(sorted(name for name in sys.modules if name.startswith("logbook.cli"))))
"""


@pytest.mark.subprocess
def test_importing_web_app_does_not_load_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        encoding="utf-8",
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


def _is_type_checking(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _imported_modules(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    module = node.module or ""
    # `from logbook import cli`처럼 모듈 이름이 이름 목록에 있는 경우도 모듈로 본다.
    return [module, *(f"{module}.{alias.name}" for alias in node.names)]


def _web_imports() -> list[tuple[Path, str, bool]]:
    """(파일, import하는 모듈, `if TYPE_CHECKING:` 안에 있는지) 목록."""
    result: list[tuple[Path, str, bool]] = []
    for path in sorted(WEB_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        guarded: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and _is_type_checking(node.test):
                for statement in node.body:
                    guarded.update(id(inner) for inner in ast.walk(statement))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                result.extend(
                    (path, module, id(node) in guarded) for module in _imported_modules(node)
                )
    return result


def test_web_files_are_found() -> None:
    names = {path.name for path, _, _ in _web_imports()}
    assert {"app.py", "security.py", "errors.py"} <= names


def test_web_does_not_import_cli() -> None:
    offenders = [
        f"{path.name}: {module}"
        for path, module, _ in _web_imports()
        if module == "logbook.cli" or module.startswith("logbook.cli.")
    ]
    assert offenders == []


def test_web_imports_sqlalchemy_only_for_type_checking() -> None:
    offenders = [
        f"{path.name}: {module}"
        for path, module, guarded in _web_imports()
        if (module == "sqlalchemy" or module.startswith("sqlalchemy.")) and not guarded
    ]
    assert offenders == []


@pytest.mark.subprocess
@pytest.mark.parametrize(
    "first",
    ["logbook.web.errors", "logbook.web.pages", "logbook.web.pages.dashboard", "logbook.web.app"],
)
def test_web_modules_import_in_any_order(first: str) -> None:
    # errors와 pages가 서로를 import해도 어느 쪽을 먼저 불러도 순환 import가 나지 않는다.
    result = subprocess.run(
        [sys.executable, "-c", f"import {first}"],
        capture_output=True,
        encoding="utf-8",
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, result.stderr
