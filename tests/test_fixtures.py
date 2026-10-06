import os
from datetime import date
from pathlib import Path

import pytest

CONFTEST = Path(__file__).with_name("conftest.py")


def test_isolated_home_redirects_path_home(isolated_home: Path, tmp_path: Path) -> None:
    assert Path.home() == isolated_home
    assert Path("~").expanduser() == isolated_home
    assert isolated_home.is_relative_to(tmp_path)


def test_logbook_env_vars_are_cleared_without_tmp_home() -> None:
    assert "LOGBOOK_DB" not in os.environ
    assert "LOGBOOK_CONFIG" not in os.environ


def test_isolated_home_clears_preexisting_logbook_env_vars(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 개발자 환경에 LOGBOOK_* 가 설정되어 있어도 테스트 안에서는 지워져야 한다.
    monkeypatch.setenv("LOGBOOK_DB", "real.db")
    monkeypatch.setenv("LOGBOOK_CONFIG", "real.toml")
    pytester.makeconftest(CONFTEST.read_text(encoding="utf-8"))
    pytester.makepyfile(
        """
        import os

        def test_env_cleared():
            assert "LOGBOOK_DB" not in os.environ
            assert "LOGBOOK_CONFIG" not in os.environ
        """
    )
    result = pytester.runpytest_inprocess("-p", "no:cacheprovider")
    result.assert_outcomes(passed=1)


def test_tmp_home_points_env_vars_into_tmp_path(tmp_home: Path, tmp_path: Path) -> None:
    assert tmp_home.is_dir()
    assert tmp_home.is_relative_to(tmp_path)
    assert Path(os.environ["LOGBOOK_DB"]) == tmp_home / "logbook.db"
    assert Path(os.environ["LOGBOOK_CONFIG"]) == tmp_home / "config.toml"


def test_tmp_home_is_not_default_data_dir(tmp_home: Path) -> None:
    assert tmp_home != Path.home() / ".logbook"


def test_today_is_fixed_thursday_of_week_40(today: date) -> None:
    assert today == date(2026, 10, 1)
    assert today.isocalendar() == (2026, 40, 4)
