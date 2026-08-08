import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from novel_reader.errors import AccessRestrictedError, ParseError
from novel_reader.models import Book, BookChapter, Chapter, UrlKind
from novel_reader.services.downloader import DownloadedPage
from novel_reader.sources.generic import GenericHtmlSource


class WebNovelSource(GenericHtmlSource):
    """Adaptador conservador para páginas públicas do webnovel.com.

    A regra principal é: primeiro procuramos texto real do capítulo. Só quando
    não há conteúdo suficiente tentamos classificar a página como bloqueada.
    Isso evita falsos positivos causados por elementos globais da interface,
    como "Batch unlock chapters", que também aparecem em capítulos gratuitos.
    """

    name = "WebNovel"
    priority = 100
    requires_browser = True

    # Seletores deliberadamente focados na área de leitura. WebNovel altera
    # classes com frequência, por isso mantemos várias formas tolerantes.
    CONTENT_SELECTORS = (
        "[class*='chapter_content'] p",
        "[class*='chapter-content'] p",
        "[class*='chapterContent'] p",
        "[class*='cha-content'] p",
        "[class*='chapter_content']",
        "[class*='chapter-content']",
        "[class*='chapterContent']",
        "[class*='cha-content']",
        "article p",
        "article",
    )

    RESTRICTED_MARKERS = (
        "unlock this chapter",
        "chapter locked",
        "locked chapter",
        "use coins to unlock",
        "purchase privilege",
        "subscribe to unlock",
    )

    def can_handle(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host == "webnovel.com" or host.endswith(".webnovel.com")

    def classify_url(self, url: str) -> UrlKind:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]

        # Supported examples:
        # /book/36369162300248305
        # /book/36369162300248305/97747003273963430
        if "book" not in parts:
            return UrlKind.UNKNOWN

        index = parts.index("book")
        tail = parts[index + 1:]

        if len(tail) == 1:
            return UrlKind.BOOK
        if len(tail) >= 2:
            return UrlKind.CHAPTER
        return UrlKind.UNKNOWN

    def parse_book(self, page: DownloadedPage) -> Book:
        """Interpreta a página raiz de uma obra WebNovel.

        O parser trabalha sobre o DOM já renderizado. Ele não baixa o texto dos
        capítulos: apenas metadados e links presentes no índice da página.
        """
        soup = BeautifulSoup(page.html, "html.parser")
        parsed = urlparse(page.final_url or page.requested_url)
        parts = [part for part in parsed.path.split("/") if part]

        if "book" not in parts:
            raise ParseError("A página não parece ser uma obra do WebNovel.")

        book_index = parts.index("book")
        if book_index + 1 >= len(parts):
            raise ParseError("Não encontrei o identificador da obra na URL.")

        source_id = parts[book_index + 1]
        canonical_url = f"{parsed.scheme or 'https'}://{parsed.netloc}/book/{source_id}"

        title = self._extract_book_title(soup)
        author = self._extract_book_author(soup)
        synopsis = self._extract_book_synopsis(soup)
        cover_url = self._meta_content(soup, "property", "og:image")

        chapters = self._extract_book_chapters(
            soup=soup,
            page_url=page.final_url or page.requested_url,
            source_id=source_id,
        )

        if not title:
            raise ParseError(
                "A página da obra foi carregada, mas não consegui identificar o título."
            )

        if not chapters:
            raise ParseError(
                "A obra foi identificada, mas nenhum capítulo apareceu no DOM "
                "renderizado. Abra a aba/área “Table of Contents” no site e tente "
                "novamente se o índice for carregado sob demanda."
            )

        return Book(
            source=self.name,
            source_id=source_id,
            url=canonical_url,
            title=title,
            author=author,
            synopsis=synopsis,
            cover_url=cover_url,
            chapters=chapters,
        )

    def _extract_book_title(self, soup: BeautifulSoup) -> str:
        # OpenGraph costuma ser o dado mais estável.
        og_title = self._meta_content(soup, "property", "og:title")
        if og_title:
            # WebNovel pode acrescentar "- <autor> - WebNovel".
            cleaned = re.sub(r"\s*[-|]\s*WebNovel\s*$", "", og_title, flags=re.I)
            if cleaned.strip():
                return cleaned.strip()

        for selector in (
            "main h1",
            "[class*='book'] h1",
            "h1",
        ):
            node = soup.select_one(selector)
            if node:
                text = self._clean_text(node.get_text(" ", strip=True))
                if text:
                    return text

        title_node = soup.select_one("title")
        if title_node:
            title = self._clean_text(title_node.get_text(" ", strip=True))
            title = re.sub(r"\s*-\s*WebNovel.*$", "", title, flags=re.I).strip()
            return title

        return ""

    def _extract_book_author(self, soup: BeautifulSoup) -> str:
        for selector in (
            "a[href*='/profile/']",
            "a[href*='/author/']",
            "[class*='author'] a",
            "[class*='author']",
        ):
            node = soup.select_one(selector)
            if node:
                text = self._clean_text(node.get_text(" ", strip=True))
                text = re.sub(r"^Author\s*:\s*", "", text, flags=re.I).strip()
                if text and len(text) <= 120:
                    return text

        # Fallback por texto visível "Author: Nome".
        for text_node in soup.find_all(string=re.compile(r"\bAuthor\s*:", re.I)):
            parent = text_node.parent
            if parent:
                text = self._clean_text(parent.get_text(" ", strip=True))
                match = re.search(r"Author\s*:\s*(.+)", text, re.I)
                if match:
                    candidate = match.group(1).strip()
                    if candidate:
                        return candidate[:120]

        return ""

    def _extract_book_synopsis(self, soup: BeautifulSoup) -> str:
        for selector in (
            "[class*='synopsis']",
            "[class*='summary']",
            "[data-testid*='synopsis']",
        ):
            node = soup.select_one(selector)
            if node:
                text = self._clean_text(node.get_text("\n", strip=True))
                if len(text) >= 40:
                    return text

        # Fallback sem depender de classes: procura um heading "Synopsis" e
        # acumula irmãos próximos até outra seção.
        heading = None
        for tag in soup.find_all(["h2", "h3", "h4", "div", "span"]):
            text = self._clean_text(tag.get_text(" ", strip=True))
            if text.casefold() == "synopsis":
                heading = tag
                break

        if heading:
            pieces: list[str] = []
            sibling = heading.find_next_sibling()
            while sibling and len(pieces) < 6:
                text = self._clean_text(sibling.get_text("\n", strip=True))
                if text:
                    if text.casefold() in {
                        "tags",
                        "fans",
                        "reviews",
                        "table of contents",
                    }:
                        break
                    pieces.append(text)
                sibling = sibling.find_next_sibling()
            joined = "\n\n".join(pieces).strip()
            if len(joined) >= 40:
                return joined

        description = self._meta_content(soup, "name", "description")
        return description.strip() if description else ""

    def _extract_book_chapters(
        self,
        *,
        soup: BeautifulSoup,
        page_url: str,
        source_id: str,
    ) -> list[BookChapter]:
        # O índice é representado por links para /book/<book-id>/<chapter-id>.
        # Links como "Read" e "Latest Release" podem duplicar capítulos;
        # consolidamos por URL e preferimos o título mais informativo.
        pattern = re.compile(
            rf"/book/{re.escape(source_id)}/([^/?#]+)",
            re.I,
        )

        found: dict[str, BookChapter] = {}
        order: list[str] = []

        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            match = pattern.search(href)
            if not match:
                continue

            chapter_id = match.group(1)
            url = urljoin(page_url, href)
            # Remove query/fragment from the stable chapter key.
            parsed = urlparse(url)
            url = parsed._replace(query="", fragment="").geturl()

            raw_title = self._clean_text(anchor.get_text(" ", strip=True))
            title = self._clean_chapter_link_title(raw_title)

            # Ignore obviously generic navigation labels unless this is the
            # only occurrence; a later TOC occurrence will improve it.
            if not title:
                title = "Capítulo"

            position = self._chapter_position(title)

            chapter = BookChapter(
                source=self.name,
                source_id=chapter_id,
                url=url,
                title=title,
                position=position,
                accessible=self._chapter_accessible(anchor),
            )

            if url not in found:
                found[url] = chapter
                order.append(url)
                continue

            current = found[url]
            if self._chapter_title_score(chapter.title) > self._chapter_title_score(
                current.title
            ):
                current.title = chapter.title
                current.position = chapter.position

            # A locked marker wins over unknown, but an explicit accessible
            # signal wins over unknown as well.
            if chapter.accessible is not None:
                current.accessible = chapter.accessible

        # Prefer semantic numeric positions. Auxiliary chapters without a
        # leading number retain None and stay where the DOM introduced them.
        chapters = [found[url] for url in order]

        # If most numbered chapters are known, sort numbered items numerically
        # but keep auxiliaries before/after according to their DOM position.
        numbered = [chapter for chapter in chapters if chapter.position is not None]
        if len(numbered) >= 2:
            auxiliary = [
                (index, chapter)
                for index, chapter in enumerate(chapters)
                if chapter.position is None
            ]
            numbered.sort(key=lambda chapter: chapter.position or 0)
            # Typical WebNovel pages put auxiliary volume before chapter 1.
            if auxiliary and auxiliary[0][0] < order.index(numbered[0].url):
                chapters = [chapter for _, chapter in auxiliary] + numbered
            else:
                chapters = numbered + [chapter for _, chapter in auxiliary]

        return chapters

    @staticmethod
    def _chapter_title_score(title: str) -> int:
        lowered = title.casefold().strip()
        generic = {
            "",
            "read",
            "latest release",
            "chapter",
            "continue reading",
        }
        if lowered in generic:
            return 0
        score = min(len(title), 200)
        if re.match(r"^\d+\b", title):
            score += 100
        return score

    def _clean_chapter_link_title(self, text: str) -> str:
        text = self._clean_text(text)
        text = re.sub(
            r"\s+\d+\s+(?:seconds?|minutes?|hours?|days?|months?|years?)\s+ago\s*$",
            "",
            text,
            flags=re.I,
        )
        text = re.sub(r"^Chapter\s+(\d+)\s*:\s*", r"\1 ", text, flags=re.I)
        if text.casefold() in {"read", "latest release", "continue reading"}:
            return text
        return text

    @staticmethod
    def _chapter_position(title: str) -> int | None:
        match = re.match(r"^\s*(\d+)\b", title)
        return int(match.group(1)) if match else None

    @staticmethod
    def _chapter_accessible(anchor) -> bool | None:
        haystack = " ".join(
            [
                str(anchor.get("class") or ""),
                str(anchor.get("aria-label") or ""),
                str(anchor.get("title") or ""),
                anchor.get_text(" ", strip=True),
            ]
        ).casefold()

        if any(token in haystack for token in ("locked", "unlock", "privilege")):
            return False
        return None

    @staticmethod
    def _meta_content(
        soup: BeautifulSoup,
        attribute: str,
        value: str,
    ) -> str:
        node = soup.find("meta", attrs={attribute: value})
        if node and node.get("content"):
            return str(node.get("content")).strip()
        return ""

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"[ \t\r\f\v]+", " ", text or "").strip()


    def parse(self, page: DownloadedPage) -> Chapter:
        soup = BeautifulSoup(page.html, "html.parser")

        # 1. Primeiro extraímos conteúdo. Não classificamos a página como
        # bloqueada com base no texto global antes desta etapa.
        chunks = self._extract_content(soup)

        # 2. Se os seletores específicos não acharam conteúdo, tentamos o
        # parser genérico. Ele pode funcionar para variações legítimas do DOM.
        if not chunks:
            try:
                chapter = super().parse(page)
            except ParseError:
                chapter = None
            else:
                # Evita aceitar como capítulo um bloco curto de UI/menu.
                if len(chapter.text.strip()) >= 300:
                    chapter.source = self.name
                    return chapter

        if chunks:
            return self._build_chapter(page, soup, chunks)

        # 3. Somente sem texto suficiente verificamos controles de acesso.
        if self._looks_restricted(soup):
            raise AccessRestrictedError(
                "Este capítulo parece estar bloqueado ou exigir acesso adicional. "
                "O Novel Reader não tenta contornar paywall ou controle de acesso."
            )

        raise ParseError(
            "A página foi renderizada, mas ainda não encontrei texto público "
            "suficiente para formar um capítulo. O conteúdo pode ainda estar "
            "carregando, a estrutura da página pode ter mudado ou o site pode "
            "estar mostrando uma tela intermediária."
        )

    def _extract_content(self, soup: BeautifulSoup) -> list[str]:
        for selector in self.CONTENT_SELECTORS:
            nodes = soup.select(selector)
            candidate: list[str] = []

            for node in nodes:
                text = " ".join(node.stripped_strings)
                text = re.sub(r"\s+", " ", text).strip()

                # Parágrafos muito curtos normalmente são botões, labels ou UI.
                if len(text) >= 25:
                    candidate.append(text)

            unique = self._deduplicate(candidate)
            if sum(map(len, unique)) >= 300:
                return unique

        return []

    @staticmethod
    def _deduplicate(chunks: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for chunk in chunks:
            key = re.sub(r"\s+", " ", chunk).strip().casefold()
            if key and key not in seen:
                seen.add(key)
                result.append(chunk)
        return result

    def _looks_restricted(self, soup: BeautifulSoup) -> bool:
        # Prioriza elementos semanticamente próximos de bloqueio/paywall em vez
        # de procurar qualquer ocorrência no documento inteiro.
        restricted_selectors = (
            "[class*='lock']",
            "[class*='locked']",
            "[class*='unlock']",
            "[class*='paywall']",
            "[class*='privilege']",
            "[data-testid*='lock']",
            "[data-testid*='unlock']",
        )

        focused_texts: list[str] = []
        for selector in restricted_selectors:
            for node in soup.select(selector):
                text = " ".join(node.stripped_strings).casefold()
                if text:
                    focused_texts.append(text)

        if any(
            marker in text
            for text in focused_texts
            for marker in self.RESTRICTED_MARKERS
        ):
            return True

        # Fallback conservador: aceita somente frases inequívocas. Não usamos
        # "unlock chapter" sozinho porque a UI global possui "Batch unlock
        # chapters" até em capítulos gratuitos.
        page_text = " ".join(soup.stripped_strings).casefold()
        return any(marker in page_text for marker in self.RESTRICTED_MARKERS)

    def _build_chapter(
        self,
        page: DownloadedPage,
        soup: BeautifulSoup,
        chunks: list[str],
    ) -> Chapter:
        title_node = soup.select_one("h1") or soup.select_one("title")
        chapter_title = (
            title_node.get_text(" ", strip=True) if title_node else "Capítulo"
        )

        book_title = "WebNovel"
        site_title = soup.select_one("meta[property='og:title']")
        if site_title and site_title.get("content"):
            book_title = str(site_title["content"]).split("-")[0].strip() or book_title

        previous_url = None
        next_url = None
        prev_node = soup.select_one("a[rel='prev']")
        next_node = soup.select_one("a[rel='next']")
        if prev_node and prev_node.get("href"):
            previous_url = urljoin(page.final_url, str(prev_node["href"]))
        if next_node and next_node.get("href"):
            next_url = urljoin(page.final_url, str(next_node["href"]))

        return Chapter(
            source=self.name,
            url=page.final_url,
            book_title=book_title,
            chapter_title=chapter_title,
            text="\n\n".join(chunks),
            previous_url=previous_url,
            next_url=next_url,
        )
