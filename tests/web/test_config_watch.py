"""ConfigWatcher: 설정 파일 내용이 바뀌면 다시 읽는다."""

import threading
from pathlib import Path

import pytest

from logbook.core.config import Config, load_config
from logbook.web.config_watch import (
    CONFIG_RELOAD_FAILED,
    RESTART_KEYS,
    RESTART_REQUIRED,
    ConfigSnapshot,
    ConfigWatcher,
    restart_keys,
)

THREAD_COUNT = 8


class CountingLoader:
    """load_config를 감싸 불린 횟수를 센다."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, path: Path) -> Config:
        self.calls += 1
        return load_config(path)


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text("[web]\nport = 8765\n", encoding="utf-8")
    return path


@pytest.fixture
def loader() -> CountingLoader:
    return CountingLoader()


@pytest.fixture
def watcher(config_file: Path, loader: CountingLoader) -> ConfigWatcher:
    return ConfigWatcher(config_file, load_config(config_file), loader=loader)


def test_restart_keys_are_listed() -> None:
    assert RESTART_KEYS == ("db_path", "web.host", "web.port")


def test_unchanged_file_never_calls_loader(watcher: ConfigWatcher, loader: CountingLoader) -> None:
    first = watcher.current()
    for _ in range(3):
        snapshot = watcher.current()

    assert loader.calls == 0
    assert snapshot.cfg is first.cfg
    assert snapshot == ConfigSnapshot(cfg=first.cfg)


def test_added_category_is_picked_up_without_notice(
    watcher: ConfigWatcher, config_file: Path
) -> None:
    config_file.write_text('[web]\nport = 8765\n[categories]\nops = "운영"\n', encoding="utf-8")

    snapshot = watcher.current()

    assert snapshot.cfg.categories == {"ops": "운영"}
    assert snapshot.notice == ""
    assert snapshot.notice_error is False


def test_same_size_port_change_is_detected(watcher: ConfigWatcher, config_file: Path) -> None:
    before = config_file.stat().st_size
    config_file.write_text("[web]\nport = 8766\n", encoding="utf-8")
    assert config_file.stat().st_size == before

    snapshot = watcher.current()

    assert snapshot.cfg.web.port == 8766
    assert snapshot.notice == RESTART_REQUIRED.format(keys="web.port")
    assert snapshot.notice_error is False


def test_broken_toml_keeps_previous_config_and_reports_once(
    watcher: ConfigWatcher, config_file: Path, loader: CountingLoader
) -> None:
    initial = watcher.current().cfg
    config_file.write_text("[web\n", encoding="utf-8")

    snapshot = watcher.current()
    again = watcher.current()

    assert snapshot.cfg is initial
    assert snapshot.notice_error is True
    assert snapshot.notice.startswith("설정 파일을 다시 읽지 못해 이전 설정으로 동작합니다: ")
    assert "TOML 문법이 올바르지 않습니다" in snapshot.notice
    assert again == snapshot
    assert loader.calls == 1


def test_fixing_the_file_clears_the_notice(watcher: ConfigWatcher, config_file: Path) -> None:
    config_file.write_text("[web\n", encoding="utf-8")
    assert watcher.current().notice_error is True
    config_file.write_text('[categories]\nops = "운영"\n[web]\nport = 8765\n', encoding="utf-8")

    snapshot = watcher.current()

    assert snapshot.cfg.categories == {"ops": "운영"}
    assert snapshot.notice == ""
    assert snapshot.notice_error is False


def test_failure_message_uses_the_core_error_text(
    watcher: ConfigWatcher, config_file: Path
) -> None:
    config_file.write_text("[web\n", encoding="utf-8")

    snapshot = watcher.current()

    prefix = CONFIG_RELOAD_FAILED.format(error="")
    assert snapshot.notice.startswith(prefix)


def test_db_path_and_port_change_lists_keys_in_order(
    watcher: ConfigWatcher, config_file: Path, tmp_path: Path
) -> None:
    other = (tmp_path / "other.db").as_posix()
    config_file.write_text(f'db_path = "{other}"\n[web]\nport = 8000\n', encoding="utf-8")

    snapshot = watcher.current()

    assert snapshot.notice == RESTART_REQUIRED.format(keys="db_path, web.port")
    assert snapshot.notice_error is False
    assert snapshot.cfg.web.port == 8000
    assert snapshot.cfg.db_path == Path(other)


def test_deleted_file_falls_back_to_loader_defaults(
    watcher: ConfigWatcher, config_file: Path, loader: CountingLoader
) -> None:
    config_file.unlink()

    snapshot = watcher.current()

    assert loader.calls == 1
    assert snapshot.cfg.web.port == 8765
    assert snapshot.notice_error is False


def test_concurrent_current_calls_reload_once(
    watcher: ConfigWatcher, config_file: Path, loader: CountingLoader
) -> None:
    config_file.write_text('[web]\nport = 8765\n[categories]\nops = "운영"\n', encoding="utf-8")
    barrier = threading.Barrier(THREAD_COUNT)
    results: list[ConfigSnapshot] = []

    def call() -> None:
        barrier.wait()
        results.append(watcher.current())

    threads = [threading.Thread(target=call) for _ in range(THREAD_COUNT)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert loader.calls == 1
    assert len(results) == THREAD_COUNT
    assert all(snapshot == results[0] for snapshot in results)


def test_restart_keys_compares_only_restart_values(config_file: Path) -> None:
    base = load_config(config_file)
    config_file.write_text('[web]\nport = 8765\n[categories]\nops = "운영"\n', encoding="utf-8")

    assert restart_keys(base, load_config(config_file)) == ()
