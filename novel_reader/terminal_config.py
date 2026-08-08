from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


COVER_MODES = ("auto", "kitty", "chafa", "pillow", "off")


@dataclass(slots=True)
class TerminalUiConfig:
    cover_mode: str = "auto"
    prefetch_count: int = 3

    def normalized(self) -> "TerminalUiConfig":
        mode = self.cover_mode if self.cover_mode in COVER_MODES else "auto"
        return TerminalUiConfig(cover_mode=mode, prefetch_count=max(0, min(int(self.prefetch_count), 20)))


class TerminalConfigStore:
    def __init__(self, path: str | Path | None = None):
        if path is None:
            path = Path.home() / ".config" / "novel-reader" / "cli.json"
        self.path = Path(path)

    def load(self) -> TerminalUiConfig:
        if not self.path.exists():
            return TerminalUiConfig()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return TerminalUiConfig(
                cover_mode=str(data.get("cover_mode", "auto")),
                prefetch_count=int(data.get("prefetch_count", 3)),
            ).normalized()
        except Exception:
            return TerminalUiConfig()

    def save(self, config: TerminalUiConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(config.normalized()), indent=2),
            encoding="utf-8",
        )
