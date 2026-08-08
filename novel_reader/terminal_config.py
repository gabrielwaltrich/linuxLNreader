from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from novel_reader.app_config import (
    COVER_MODES,
    AppConfigStore,
    migrate_legacy_terminal_config,
)


@dataclass(slots=True)
class TerminalUiConfig:
    cover_mode: str = "auto"
    prefetch_count: int = 3

    def normalized(self) -> "TerminalUiConfig":
        mode = self.cover_mode if self.cover_mode in COVER_MODES else "auto"
        return TerminalUiConfig(
            cover_mode=mode,
            prefetch_count=max(0, min(int(self.prefetch_count), 20)),
        )


class TerminalConfigStore:
    """Compatibility layer for older TUI code.

    Reads/writes the centralized AppConfig instead of a separate cli.json.
    """

    def __init__(self, path: str | Path | None = None):
        self._app_store = AppConfigStore(path)
        migrate_legacy_terminal_config(self._app_store)
        self.path = self._app_store.path

    def load(self) -> TerminalUiConfig:
        cfg = self._app_store.load()
        return TerminalUiConfig(
            cover_mode=cfg.cover_mode,
            prefetch_count=cfg.prefetch_count,
        ).normalized()

    def save(self, config: TerminalUiConfig) -> None:
        normalized = config.normalized()
        self._app_store.update(
            cover_mode=normalized.cover_mode,
            prefetch_count=normalized.prefetch_count,
        )
