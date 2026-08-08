from __future__ import annotations

from dataclasses import dataclass
import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


RANKING_PERIODS = (
    ("monthly", "Mensal", "≤30 dias"),
    ("season", "Temporada", "31–90 dias"),
    ("bi_annual", "Semestral", "91–180 dias"),
    ("annual", "Anual", "181–365 dias"),
    ("all_time", "Todos os tempos", ">365 dias"),
)


def ranking_url(period: str) -> str:
    valid = {item[0] for item in RANKING_PERIODS}
    period = period if period in valid else "monthly"
    return f"https://www.webnovel.com/ranking/fanfic/{period}/power_rank"


@dataclass(slots=True)
class RankingBook:
    rank: int
    title: str
    url: str
    author: str = ""
    synopsis: str = ""
    cover_url: str = ""
    score_text: str = ""
    source_rank: int = 0


def normalize_loaded_ranking(items: list[RankingBook]) -> list[RankingBook]:
    """Sort by the authoritative WebNovel position without renumbering.

    The old implementation assigned new contiguous UI ranks to sparse captures.
    That made displayed positions diverge from WebNovel. ``rank`` now always
    remains the source position.
    """
    dedup: dict[str, RankingBook] = {}
    for item in items:
        key = item.url.casefold()
        current = dedup.get(key)
        source_rank = item.source_rank or item.rank
        if current is None or source_rank < (current.source_rank or current.rank):
            if not item.source_rank:
                item.source_rank = item.rank
            dedup[key] = item

    return sorted(
        dedup.values(),
        key=lambda item: (
            item.source_rank or item.rank,
            item.title.casefold(),
        ),
    )


class WebNovelRankingParser:
    """Parser for WebNovel Fan-Fic Power Ranking.

    Current page structure provides two independent sources for position:
    1. JSON-LD ItemList in <head> with URL + official ``position``.
    2. ``i.ff_number`` inside each rendered card.

    JSON-LD is authoritative because it is semantic page metadata and avoids
    confusing ``strong.ff_number`` (Power) with the ranking position.
    """

    BOOK_RE = re.compile(r"/book/([^/?#]+)", re.I)

    def parse(self, html: str, page_url: str) -> list[RankingBook]:
        soup = BeautifulSoup(html or "", "html.parser")
        position_map = self._jsonld_positions(soup, page_url)

        cards = self._ranking_cards(soup)
        results: list[RankingBook] = []
        seen: set[str] = set()

        for card in cards:
            anchor = self._book_anchor(card)
            if anchor is None:
                continue

            href = str(anchor.get("href") or "").strip()
            absolute_url = urljoin(page_url, href)
            book_key = self._book_key(absolute_url)
            if not book_key or book_key in seen:
                continue

            title = self._clean(
                anchor.get("title")
                or anchor.get_text(" ", strip=True)
            )
            if not title:
                continue

            semantic_rank = position_map.get(book_key)
            dom_rank = self._extract_dom_rank(card)
            rank = semantic_rank or dom_rank
            if rank is None:
                continue

            seen.add(book_key)
            results.append(
                RankingBook(
                    rank=rank,
                    source_rank=rank,
                    title=title,
                    url=absolute_url,
                    author=self._extract_author(card, title),
                    synopsis=self._extract_synopsis(card, title),
                    cover_url=self._extract_cover(card, page_url),
                    score_text=self._extract_power(card),
                )
            )

        # Compatibility fallback for older cached HTML/fixtures without the
        # current wrapper. It still requires a zero-padded rank and a single
        # root book link; arbitrary Power numbers are never accepted.
        if not results:
            results = self._parse_legacy_cards(soup, page_url)

        return normalize_loaded_ranking(results)

    def _ranking_cards(self, soup) -> list:
        wrapper = soup.select_one(".j_rank_wrapper")
        if wrapper is not None:
            direct = [
                node
                for node in wrapper.find_all(recursive=False)
                if node.select_one("i.ff_number") is not None
                and self._root_book_link_count(node) == 1
            ]
            if direct:
                return direct

        # Compatibility with compact HTML snapshots/tests: walk upward from
        # i.ff_number and choose the smallest ancestor containing exactly one
        # root book link. The tag may be section, div, article, etc.
        cards = []
        seen_nodes: set[int] = set()
        for marker in soup.select("i.ff_number"):
            node = marker
            card = None
            for _ in range(8):
                node = getattr(node, "parent", None)
                if node is None:
                    break
                if self._root_book_link_count(node) == 1:
                    card = node
                    break
            if card is not None and id(card) not in seen_nodes:
                seen_nodes.add(id(card))
                cards.append(card)
        return cards

    def _root_book_link_count(self, node) -> int:
        keys: set[str] = set()
        for anchor in node.find_all("a", href=True):
            key = self._book_key(
                urljoin(
                    "https://www.webnovel.com",
                    str(anchor.get("href") or ""),
                )
            )
            if key:
                keys.add(key)
        return len(keys)

    def _jsonld_positions(self, soup, page_url: str) -> dict[str, int]:
        positions: dict[str, int] = {}
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue

            candidates = payload if isinstance(payload, list) else [payload]
            for obj in candidates:
                if not isinstance(obj, dict):
                    continue
                if obj.get("@type") != "ItemList":
                    continue
                for item in obj.get("itemListElement") or []:
                    if not isinstance(item, dict):
                        continue
                    try:
                        position = int(item.get("position"))
                    except (TypeError, ValueError):
                        continue
                    url = str(item.get("url") or "")
                    key = self._book_key(urljoin(page_url, url))
                    if key and 1 <= position <= 10000:
                        positions[key] = position
        return positions

    def _book_anchor(self, card):
        # Prefer the actual title link. The thumbnail is a useful fallback.
        for selector in (
            "h3 a[href*='/book/']",
            "a.c_l[href*='/book/']",
            "a.g_thumb[href*='/book/']",
        ):
            anchor = card.select_one(selector)
            if anchor is not None:
                return anchor

        for anchor in card.find_all("a", href=True):
            href = str(anchor.get("href") or "")
            key = self._book_key(urljoin("https://www.webnovel.com", href))
            if key:
                return anchor
        return None

    def _book_key(self, url: str) -> str:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if "book" not in parts:
            return ""
        idx = parts.index("book")
        tail = parts[idx + 1:]
        if len(tail) != 1:
            return ""
        return tail[0].casefold()

    @staticmethod
    def _extract_dom_rank(card) -> int | None:
        marker = card.select_one("i.ff_number")
        if marker is None:
            return None
        text = marker.get_text(" ", strip=True)
        match = re.fullmatch(r"0*(\d{1,4})", text.strip())
        if not match:
            return None
        value = int(match.group(1))
        return value if 1 <= value <= 10000 else None

    def _extract_author(self, card, title: str) -> str:
        # Current cards put author after the category separator as:
        # <strong class="c_l ...">Author</strong>
        for node in card.select("p strong.c_l"):
            text = self._clean(node.get_text(" ", strip=True))
            if text and text != title:
                return text

        for selector in (
            "a[href*='/profile/']",
            "a[href*='/author/']",
        ):
            node = card.select_one(selector)
            if node:
                text = self._clean(node.get_text(" ", strip=True))
                if text and text != title:
                    return text
        return ""

    def _extract_synopsis(self, card, title: str) -> str:
        # Current ranking description paragraph.
        node = card.select_one("p.fw400.lh20.fs14")
        if node is not None:
            text = self._clean(node.get_text(" ", strip=True))
            if text and title.casefold() not in text.casefold():
                return text[:1200]

        candidates = []
        for node in card.find_all("p"):
            text = self._clean(node.get_text(" ", strip=True))
            if (
                len(text) >= 40
                and title.casefold() not in text.casefold()
                and "add in library" not in text.casefold()
            ):
                candidates.append(text)
        return max(candidates, key=len)[:1200] if candidates else ""

    @staticmethod
    def _extract_power(card) -> str:
        container = card.select_one("strong.ff_number")
        if container is None:
            return ""
        node = container.select_one("span")
        if node is None:
            return ""
        value = WebNovelRankingParser._clean(node.get_text(" ", strip=True))
        return (
            value
            if re.fullmatch(r"\d+(?:\.\d+)?[KMB]?", value, re.I)
            else ""
        )

    @staticmethod
    def _extract_cover(card, page_url: str) -> str:
        image = card.select_one(
            "a.g_thumb img[data-original], "
            "a.g_thumb img[src], "
            "img[data-original], img[src], img[data-src]"
        )
        if image is None:
            return ""
        value = (
            image.get("data-original")
            or image.get("src")
            or image.get("data-src")
            or ""
        )
        value = str(value).strip()
        return urljoin(page_url, value) if value else ""

    def _parse_legacy_cards(self, soup, page_url: str) -> list[RankingBook]:
        results: list[RankingBook] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            absolute = urljoin(page_url, str(anchor.get("href") or ""))
            key = self._book_key(absolute)
            if not key or key in seen:
                continue

            node = anchor
            card = None
            for _ in range(8):
                node = getattr(node, "parent", None)
                if node is None:
                    break
                text = self._clean(node.get_text(" ", strip=True))
                if len(text) > 6000:
                    break
                if node.select_one("strong.ff_number") is not None:
                    continue
                if self._root_book_link_count(node) != 1:
                    continue
                if re.search(r"(?:^|\s)0\d{2}(?:\s|$)", text):
                    card = node
                    break

            if card is None:
                continue

            card_text = self._clean(card.get_text(" ", strip=True))
            match = re.search(r"(?:^|\s)(0\d{2})(?:\s|$)", card_text)
            if not match:
                continue
            rank = int(match.group(1))
            title = self._clean(anchor.get_text(" ", strip=True))
            if not title or title.casefold() == "read":
                continue

            seen.add(key)
            results.append(
                RankingBook(
                    rank=rank,
                    source_rank=rank,
                    title=title,
                    url=absolute,
                    author=self._extract_author(card, title),
                    synopsis=self._extract_synopsis(card, title),
                    cover_url=self._extract_cover(card, page_url),
                    score_text="",
                )
            )
        return results

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()
