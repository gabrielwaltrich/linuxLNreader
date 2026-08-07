import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from novel_reader.errors import AccessRestrictedError, ParseError
from novel_reader.models import Chapter
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
