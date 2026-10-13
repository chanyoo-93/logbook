"""설정 파일 자동 반영: 파일 내용이 바뀌면 다시 읽고, 요청마다 스냅숏 하나를 돌려준다.

바로 반영되는 값은 요청이 설정을 읽는 곳(카테고리, 기본 프로젝트 등)이다. DB 경로와 포트는
시작할 때 정해지므로 바뀌면 알림만 보여 준다.
"""

import hashlib
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from logbook.core.config import Config, load_config
from logbook.core.errors import LogbookError

RESTART_KEYS = ("db_path", "web.host", "web.port")
CONFIG_RELOAD_FAILED = "설정 파일을 다시 읽지 못해 이전 설정으로 동작합니다: {error}"
RESTART_REQUIRED = "다시 시작해야 반영되는 설정이 바뀌었습니다: {keys}. lb serve를 다시 시작하세요."


@dataclass(frozen=True)
class ConfigSnapshot:
    cfg: Config
    notice: str = ""  # 화면 위 알림. 비면 없음
    notice_error: bool = False


def restart_keys(before: Config, after: Config) -> tuple[str, ...]:
    """RESTART_KEYS 중 값이 다른 것(RESTART_KEYS 순서)."""
    values = {
        "db_path": (before.db_path, after.db_path),
        "web.host": (before.web.host, after.web.host),
        "web.port": (before.web.port, after.web.port),
    }
    return tuple(key for key in RESTART_KEYS if values[key][0] != values[key][1])


def _signature(path: Path) -> str | None:
    """파일 바이트의 sha256. 읽을 수 없으면(없는 파일 포함) None."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


class ConfigWatcher:
    """설정 파일 내용(바이트)이 바뀌면 다시 읽는다. 여러 스레드가 함께 불러도 된다(Lock)."""

    def __init__(
        self, path: Path, initial: Config, *, loader: Callable[[Path], Config] = load_config
    ) -> None:
        self._path = path
        self._initial = initial
        self._loader = loader
        self._lock = threading.Lock()
        self._signature = _signature(path)
        self._snapshot = ConfigSnapshot(initial)

    def current(self) -> ConfigSnapshot:
        with self._lock:
            # loader 전에 서명을 잰다. 읽는 사이 파일이 또 바뀌면 다음 요청이 다시 읽는다.
            signature = _signature(self._path)
            if signature != self._signature:
                self._signature = signature
                self._snapshot = self._reload()
            return self._snapshot

    def _reload(self) -> ConfigSnapshot:
        try:
            cfg = self._loader(self._path)
        except LogbookError as error:
            return ConfigSnapshot(
                self._snapshot.cfg, CONFIG_RELOAD_FAILED.format(error=str(error)), True
            )
        keys = restart_keys(self._initial, cfg)
        if keys:
            return ConfigSnapshot(cfg, RESTART_REQUIRED.format(keys=", ".join(keys)))
        return ConfigSnapshot(cfg)
