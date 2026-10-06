import subprocess
import sys
import tomllib
from pathlib import Path

from typer.testing import CliRunner

import logbook
from logbook.cli.main import app

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_help_runs() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "업무" in result.output


def test_version_prints() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "logbook" in result.output
    assert logbook.__version__ in result.output


def test_version_matches_pyproject() -> None:
    with PYPROJECT.open("rb") as f:
        project = tomllib.load(f)["project"]

    assert project["version"] == logbook.__version__
    assert project["scripts"]["lb"] == "logbook.cli.main:app"


def test_cli_import_does_not_load_web_stack() -> None:
    code = (
        "import sys\n"
        "import logbook.cli.main\n"
        "loaded = {'fastapi', 'uvicorn'} & set(sys.modules)\n"
        "assert not loaded, loaded\n"
    )

    subprocess.run([sys.executable, "-c", code], shell=False, check=True)
