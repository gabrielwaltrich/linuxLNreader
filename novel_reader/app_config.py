from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile


COVER_MODES = ("auto", "kitty", "chafa", "pillow", "off")
THEMES = ("system", "light", "dark")
CACHE_POLICIES = ("normal", "aggressive", "conservative")


@dataclass(slots=True)
class AppConfig:
    # Reader
    font_size: int = 18
    content_width: int = 760
    line_height: float = 1.72
    theme: str = "system"

    # Terminal reader
    terminal_width: int = 82
    lines_per_page: int = 24
    terminal_margin: int = 2
    paragraph_spacing: int = 1
    text_size: str = "normal"

    # Covers
    cover_mode: str = "auto"
    ascii_width: int = 34
    ascii_height: int = 17

    # Cache/offline groundwork
    prefetch_count: int = 3
    cache_limit_mb: int = 500
    cache_policy: str = "normal"
    offline_mode: bool = False

    # Behavior
    index_refresh_minutes: int = 120

    # Data safety
    automatic_backups: bool = True
    backup_retention: int = 5
    backup_interval_hours: int = 12

    def normalized(self) -> "AppConfig":
        return AppConfig(
            font_size=max(12, min(int(self.font_size), 40)),
            content_width=max(480, min(int(self.content_width), 1200)),
            line_height=max(1.2, min(float(self.line_height), 2.4)),
            theme=self.theme if self.theme in THEMES else "system",
            terminal_width=max(30, min(int(self.terminal_width), 160)),
            lines_per_page=max(5, min(int(self.lines_per_page), 80)),
            terminal_margin=max(0, min(int(self.terminal_margin), 12)),
            paragraph_spacing=max(0, min(int(self.paragraph_spacing), 3)),
            text_size=self.text_size if self.text_size in {"small", "normal", "large"} else "normal",
            cover_mode=self.cover_mode if self.cover_mode in COVER_MODES else "auto",
            ascii_width=max(12, min(int(self.ascii_width), 120)),
            ascii_height=max(6, min(int(self.ascii_height), 60)),
            prefetch_count=max(0, min(int(self.prefetch_count), 20)),
            cache_limit_mb=max(50, min(int(self.cache_limit_mb), 20_000)),
            cache_policy=self.cache_policy if self.cache_policy in CACHE_POLICIES else "normal",
            offline_mode=bool(self.offline_mode),
            index_refresh_minutes=max(5, min(int(self.index_refresh_minutes), 10_080)),
            automatic_backups=bool(self.automatic_backups),
            backup_retention=max(1, min(int(self.backup_retention), 20)),
            backup_interval_hours=max(1, min(int(self.backup_interval_hours), 168)),
        )


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base).expanduser() / "novel-reader"
    return Path.home() / ".config" / "novel-reader"


def config_path() -> Path:
    return config_dir() / "config.json"


class AppConfigStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path).expanduser() if path else config_path()

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = AppConfig.__dataclass_fields__.keys()
            data = {key: raw[key] for key in allowed if key in raw}
            return AppConfig(**data).normalized()
        except Exception:
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        config = config.normalized()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            asdict(config),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

        # Atomic replacement so a crash cannot leave half-written JSON.
        fd, tmp_name = tempfile.mkstemp(
            prefix=".config-",
            suffix=".json",
            dir=self.path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        finally:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except Exception:
                pass

    def update(self, **changes) -> AppConfig:
        current = self.load()
        data = asdict(current)
        data.update(changes)
        updated = AppConfig(**data).normalized()
        self.save(updated)
        return updated


def migrate_legacy_terminal_config(
    store: AppConfigStore | None = None,
    legacy_path: str | Path | None = None,
) -> bool:
    """Migrate ~/.config/novel-reader/cli.json once.

    The old file only held cover_mode and prefetch_count. It is left in place
    so older builds remain usable.
    """
    store = store or AppConfigStore()
    legacy = (
        Path(legacy_path).expanduser()
        if legacy_path
        else config_dir() / "cli.json"
    )

    if store.path.exists() or not legacy.exists():
        return False

    try:
        raw = json.loads(legacy.read_text(encoding="utf-8"))
    except Exception:
        return False

    cfg = AppConfig(
        cover_mode=str(raw.get("cover_mode", "auto")),
        prefetch_count=int(raw.get("prefetch_count", 3)),
    ).normalized()
    store.save(cfg)
    return True
