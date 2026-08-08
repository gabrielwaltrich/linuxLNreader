from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import time


@dataclass(slots=True)
class CacheStats:
    chapters_bytes: int = 0
    covers_bytes: int = 0
    other_bytes: int = 0
    files: int = 0

    @property
    def total_bytes(self) -> int:
        return self.chapters_bytes + self.covers_bytes + self.other_bytes

    @staticmethod
    def human_size(value: int) -> str:
        size = float(max(0, value))
        units = ("B", "KB", "MB", "GB")
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"


class CacheManager:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.chapters_dir = self.root / "chapters"
        self.covers_dir = self.root / "ascii-media"

    def _iter_files(self, path: Path):
        if not path.exists():
            return []
        return [item for item in path.rglob("*") if item.is_file()]

    def stats(self) -> CacheStats:
        chapter_files = self._iter_files(self.chapters_dir)
        cover_files = self._iter_files(self.covers_dir)
        known = set(chapter_files) | set(cover_files)
        all_files = self._iter_files(self.root)

        def total(items):
            value = 0
            for item in items:
                try:
                    value += item.stat().st_size
                except OSError:
                    pass
            return value

        other = [item for item in all_files if item not in known]
        return CacheStats(
            chapters_bytes=total(chapter_files),
            covers_bytes=total(cover_files),
            other_bytes=total(other),
            files=len(all_files),
        )

    def clear_chapters(self) -> int:
        return self._clear_dir(self.chapters_dir)

    def clear_covers(self) -> int:
        return self._clear_dir(self.covers_dir)

    def clear_all(self) -> int:
        count = len(self._iter_files(self.root))
        if self.root.exists():
            for child in self.root.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    try:
                        child.unlink()
                    except OSError:
                        pass
        return count

    def _clear_dir(self, path: Path) -> int:
        files = self._iter_files(path)
        count = len(files)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        return count

    def enforce_limit(self, limit_mb: int) -> tuple[int, int]:
        """Remove oldest cache files until usage is under the configured limit.

        Returns (files_removed, bytes_removed).
        """
        limit = max(0, int(limit_mb)) * 1024 * 1024
        files = self._iter_files(self.root)
        entries = []
        total = 0
        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            total += stat.st_size
            entries.append((stat.st_mtime, stat.st_size, path))

        if total <= limit:
            return 0, 0

        entries.sort(key=lambda item: item[0])
        removed = 0
        removed_bytes = 0

        for _, size, path in entries:
            if total <= limit:
                break
            try:
                path.unlink()
            except OSError:
                continue
            total -= size
            removed += 1
            removed_bytes += size

        return removed, removed_bytes
