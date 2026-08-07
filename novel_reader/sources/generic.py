import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from novel_reader.errors import ParseError
from novel_reader.models import Chapter
from novel_reader.services.downloader import DownloadedPage
from novel_reader.sources.base import NovelSource


NOISE_TAGS = {
    "script", "style", "noscript", "svg", "nav", "footer", "form", "button", "aside"
}

CONTENT_SELECTORS = (
    "article",
    "[itemprop='articleBody']",
    ".chapter-content",
    ".chapter_content",
    ".chapter-text",
    ".chapterText",
    ".entry-content",
    ".post-content",
    "main",
)


class GenericHtmlSource(NovelSource):
    name = "Página HTML"
    priority = -100

    def can_handle(self, url: str) -> bool:
        return url.startswith("http://") or url.startswith("https://")

    def parse(self, page: DownloadedPage) -> Chapter:
        soup = BeautifulSoup(page.html, "html.parser")
        self._remove_noise(soup)

        json_ld = self._json_ld_article(soup)
        book_title = self._book_title(soup, json_ld)
        chapter_title = self._chapter_title(soup, json_ld)

        container = self._find_content_container(soup)
        text = self._extract_paragraphs(container)

        if len(text) < 120:
            raise ParseError(
                "Não encontrei texto suficiente nessa página. Ela pode depender de "
                "JavaScript ou usar uma estrutura que precisa de um adaptador específico."
            )

        previous_url, next_url = self._navigation(soup, page.final_url)

        return Chapter(
            source=self.name,
            url=page.final_url,
            book_title=book_title,
            chapter_title=chapter_title,
            text=text,
            previous_url=previous_url,
            next_url=next_url,
        )

    @staticmethod
    def _remove_noise(soup: BeautifulSoup) -> None:
        for tag_name in NOISE_TAGS:
            for node in soup.find_all(tag_name):
                node.decompose()

    @staticmethod
    def _json_ld_article(soup: BeautifulSoup) -> dict:
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text("", strip=True)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue

            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                kind = item.get("@type")
                kinds = kind if isinstance(kind, list) else [kind]
                if any(k in {"Article", "NewsArticle", "BlogPosting", "Chapter"} for k in kinds):
                    return item
        return {}

    @staticmethod
    def _book_title(soup: BeautifulSoup, json_ld: dict) -> str:
        part_of = json_ld.get("isPartOf")
        if isinstance(part_of, dict) and part_of.get("name"):
            return str(part_of["name"]).strip()

        og_site = soup.select_one("meta[property='og:site_name']")
        if og_site and og_site.get("content"):
            return str(og_site["content"]).strip()
        return ""

    @staticmethod
    def _chapter_title(soup: BeautifulSoup, json_ld: dict) -> str:
        for key in ("headline", "name"):
            if json_ld.get(key):
                return str(json_ld[key]).strip()

        for selector in ("h1", "meta[property='og:title']", "title"):
            node = soup.select_one(selector)
            if not node:
                continue
            value = node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)
            if value:
                return str(value).strip()
        return "Capítulo"

    @staticmethod
    def _find_content_container(soup: BeautifulSoup) -> Tag:
        best = None
        best_score = 0

        for selector in CONTENT_SELECTORS:
            for node in soup.select(selector):
                text = node.get_text(" ", strip=True)
                p_count = len(node.find_all("p"))
                score = len(text) + p_count * 250
                if score > best_score:
                    best = node
                    best_score = score

        if best is not None:
            return best

        body = soup.body
        if body is None:
            raise ParseError("A página não contém um corpo HTML válido.")
        return body

    @staticmethod
    def _extract_paragraphs(container: Tag) -> str:
        paragraphs = []
        for p in container.find_all(["p", "div"], recursive=True):
            if p.name == "div" and p.find(["p", "div"], recursive=False):
                continue
            text = " ".join(p.stripped_strings)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) >= 25:
                paragraphs.append(text)

        if not paragraphs:
            raw = container.get_text("\n", strip=True)
            paragraphs = [line.strip() for line in raw.splitlines() if len(line.strip()) >= 25]

        # Remove duplicatas preservando a ordem.
        seen = set()
        unique = []
        for paragraph in paragraphs:
            key = paragraph.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(paragraph)

        return "\n\n".join(unique)

    @staticmethod
    def _navigation(soup: BeautifulSoup, base_url: str) -> tuple[str | None, str | None]:
        previous = None
        nxt = None

        prev_node = soup.select_one("a[rel='prev'], link[rel='prev']")
        next_node = soup.select_one("a[rel='next'], link[rel='next']")

        if prev_node and prev_node.get("href"):
            previous = urljoin(base_url, str(prev_node["href"]))
        if next_node and next_node.get("href"):
            nxt = urljoin(base_url, str(next_node["href"]))

        return previous, nxt
