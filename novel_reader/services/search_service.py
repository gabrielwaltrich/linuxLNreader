from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata


def normalize_search_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def fuzzy_score(query: str, *fields: str) -> int:
    q = normalize_search_text(query)
    if not q:
        return 100

    best = 0.0
    q_tokens = set(q.split())

    for field in fields:
        text = normalize_search_text(field)
        if not text:
            continue
        if q == text:
            return 100
        if q in text:
            best = max(best, 94.0)

        best = max(best, SequenceMatcher(None, q, text).ratio() * 100)

        tokens = set(text.split())
        if q_tokens:
            overlap = len(q_tokens & tokens) / len(q_tokens)
            best = max(best, overlap * 92)

        for token in tokens:
            best = max(
                best,
                SequenceMatcher(None, q, token).ratio() * 88,
            )

    return int(round(best))


def fuzzy_match(query: str, *fields: str, threshold: int = 58) -> bool:
    return fuzzy_score(query, *fields) >= threshold


@dataclass(slots=True)
class SearchResult:
    source: str
    title: str
    author: str
    url: str
    score: int
    detail: str = ""
    book_id: int | None = None
    favorite: bool = False
    in_library: bool = False


class SearchHistory:
    def __init__(self, path: str | Path | None = None, *, limit: int = 20):
        self.path = Path(path).expanduser() if path else self.default_path()
        self.limit = max(1, int(limit))

    @staticmethod
    def default_path() -> Path:
        base = os.environ.get("XDG_STATE_HOME")
        root = Path(base).expanduser() if base else Path.home() / ".local" / "state"
        return root / "novel-reader" / "search-history.json"

    def load(self) -> list[str]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            values = raw.get("queries", raw) if isinstance(raw, dict) else raw
            if not isinstance(values, list):
                return []
            return [str(item) for item in values if str(item).strip()][: self.limit]
        except Exception:
            return []

    def add(self, query: str) -> list[str]:
        query = str(query).strip()
        if not query:
            return self.load()
        values = [
            item for item in self.load()
            if normalize_search_text(item) != normalize_search_text(query)
        ]
        values.insert(0, query)
        values = values[: self.limit]
        self._save(values)
        return values

    def clear(self) -> None:
        self._save([])

    def _save(self, values: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"queries": values}, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(
            prefix=".search-history-",
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
            os.replace(tmp, self.path)
        finally:
            try:
                Path(tmp).unlink(missing_ok=True)
            except Exception:
                pass
