from __future__ import annotations

from dataclasses import dataclass
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


class WebNovelRankingParser:
    """Parse the public Fan-Fic Power Ranking page.

    The title links currently point to /book/<slug_or_id>; "Read" links tend to
    point deeper into the book and are intentionally ignored.
    """

    BOOK_RE = re.compile(r"/book/([^/?#]+)", re.I)

    def parse(self, html: str, page_url: str) -> list[RankingBook]:
        soup = BeautifulSoup(html or "", "html.parser")
        results: list[RankingBook] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            match = self.BOOK_RE.search(href)
            if not match:
                continue

            parsed_href = urlparse(urljoin(page_url, href))
            parts = [p for p in parsed_href.path.split("/") if p]

            # Book title links have exactly /book/<book-key>. Chapter/"Read"
            # links have additional path segments and are excluded.
            if "book" not in parts:
                continue
            idx = parts.index("book")
            tail = parts[idx + 1:]
            if len(tail) != 1:
                continue

            book_key = tail[0].casefold()
            if book_key in seen:
                continue

            title = self._clean(anchor.get_text(" ", strip=True))
            if not title or title.casefold() in {
                "read", "add in library", "add to library", "book"
            }:
                continue

            card = self._find_card(anchor)
            card_text = self._clean(card.get_text(" ", strip=True)) if card else title

            rank = self._extract_rank(card_text)
            if rank is None:
                # A ranking title without a numeric position is likely a
                # recommendation/navigation link rather than the ranked list.
                continue

            seen.add(book_key)
            results.append(
                RankingBook(
                    rank=rank,
                    title=title,
                    url=f"{parsed_href.scheme or 'https'}://{parsed_href.netloc}/book/{tail[0]}",
                    author=self._extract_author(card, title),
                    synopsis=self._extract_synopsis(card, title),
                    cover_url=self._extract_cover(card, page_url),
                    score_text=self._extract_score(card_text),
                )
            )

        results.sort(key=lambda item: item.rank)
        return results

    def _find_card(self, anchor):
        # Walk upward until a compact container contains a rank AND only one
        # root book link. This prevents page-level containers from making
        # unrelated recommendation links inherit rank 001/002 from the list.
        node = anchor
        for _ in range(8):
            node = getattr(node, "parent", None)
            if node is None:
                break

            text = self._clean(node.get_text(" ", strip=True))
            if len(text) > 6000:
                break

            has_rank = bool(
                re.search(r"(?:^|\s)0*\d{1,3}(?:\s|$)", text)
            )
            if not has_rank:
                continue

            root_book_links = 0
            for link in node.find_all("a", href=True):
                href = str(link.get("href") or "")
                match = self.BOOK_RE.search(href)
                if not match:
                    continue
                parsed = urlparse(urljoin("https://www.webnovel.com", href))
                parts = [p for p in parsed.path.split("/") if p]
                if "book" not in parts:
                    continue
                idx = parts.index("book")
                if len(parts[idx + 1:]) == 1:
                    root_book_links += 1

            if root_book_links == 1:
                return node

        return None

    @staticmethod
    def _extract_rank(text: str) -> int | None:
        # Current page presents ranks as 001, 002, ...
        match = re.search(r"(?:^|\s)(\d{1,3})(?:\s|$)", text)
        if not match:
            return None
        value = int(match.group(1))
        if value <= 0 or value > 999:
            return None
        return value

    def _extract_author(self, card, title: str) -> str:
        if card is None:
            return ""
        for selector in (
            "a[href*='/profile/']",
            "a[href*='/author/']",
        ):
            node = card.select_one(selector)
            if node:
                text = self._clean(node.get_text(" ", strip=True))
                if text and text != title:
                    return text

        # Current ranking cards often end metadata with "·Author".
        text = self._clean(card.get_text(" ", strip=True))
        matches = re.findall(r"·\s*([A-Za-z0-9_][A-Za-z0-9_\- ]{1,80})", text)
        if matches:
            return matches[-1].strip()
        return ""

    def _extract_synopsis(self, card, title: str) -> str:
        if card is None:
            return ""
        candidates = []
        for node in card.find_all(["p", "div"]):
            text = self._clean(node.get_text(" ", strip=True))
            if (
                len(text) >= 50
                and title.casefold() not in text.casefold()
                and "add in library" not in text.casefold()
            ):
                candidates.append(text)
        if candidates:
            return max(candidates, key=len)[:700]
        return ""

    @staticmethod
    def _extract_cover(card, page_url: str) -> str:
        if card is None:
            return ""
        image = card.find("img")
        if not image:
            return ""
        value = (
            image.get("src")
            or image.get("data-src")
            or image.get("data-original")
            or ""
        )
        return urljoin(page_url, str(value)) if value else ""

    @staticmethod
    def _extract_score(text: str) -> str:
        # Power values on the current page look like 5.8K, 906, 1.6K.
        match = re.search(r"(?:^|\s)(\d+(?:\.\d+)?[KMB]?)(?:\||\s)", text, re.I)
        return match.group(1) if match else ""

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()
