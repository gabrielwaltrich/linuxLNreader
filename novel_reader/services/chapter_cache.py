from __future__ import annotations
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from novel_reader.models import Chapter


class ChapterCache:
    def __init__(self, cache_dir: str | Path | None = None):
        if cache_dir is None:
            try:
                from PySide6.QtCore import QStandardPaths
                base = Path(QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.CacheLocation
                ))
            except Exception:
                base = Path.home() / ".cache" / "novel-reader"
            cache_dir = base / "chapters"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, url: str) -> Path:
        return self.cache_dir / f"{sha256(url.encode('utf-8')).hexdigest()}.json"

    def save(self, chapter: Chapter) -> Path | None:
        if not chapter.url or not chapter.text:
            return None
        path = self.path_for(chapter.url)
        path.write_text(json.dumps(asdict(chapter), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, url: str) -> Chapter | None:
        path = self.path_for(url)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Chapter(**data)
        except Exception:
            return None

    def has(self, url: str) -> bool:
        return bool(url and self.path_for(url).exists())
