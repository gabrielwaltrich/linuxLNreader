from urllib.parse import urlparse

from novel_reader.errors import UnsupportedSourceError
from novel_reader.models import Book, Chapter, UrlKind
from novel_reader.services.downloader import DownloadedPage, PageDownloader
from novel_reader.sources.base import NovelSource
from novel_reader.sources.generic import GenericHtmlSource
from novel_reader.sources.webnovel import WebNovelSource


class SourceManager:
    def __init__(self, downloader: PageDownloader | None = None):
        self.downloader = downloader or PageDownloader()
        self.sources: list[NovelSource] = [
            WebNovelSource(),
            GenericHtmlSource(),
        ]
        self.sources.sort(key=lambda source: source.priority, reverse=True)

    def source_for(self, url: str) -> NovelSource:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise UnsupportedSourceError("Informe uma URL HTTP ou HTTPS válida.")

        for source in self.sources:
            if source.can_handle(url):
                return source

        raise UnsupportedSourceError("Nenhuma fonte disponível para essa URL.")

    def classify_url(self, url: str) -> UrlKind:
        source = self.source_for(url)
        return source.classify_url(url)

    def is_book_url(self, url: str) -> bool:
        return self.classify_url(url) is UrlKind.BOOK

    def is_chapter_url(self, url: str) -> bool:
        return self.classify_url(url) is UrlKind.CHAPTER

    def requires_browser(self, url: str) -> bool:
        return bool(self.source_for(url).requires_browser)

    def load_chapter(self, url: str) -> Chapter:
        """Caminho HTTP leve, usado por fontes que não exigem navegador."""
        source = self.source_for(url)
        page = self.downloader.get(url)
        return source.parse(page)

    def parse_rendered_html(
        self,
        *,
        requested_url: str,
        final_url: str,
        html: str,
    ) -> Chapter:
        """Interpreta um DOM de capítulo já renderizado pelo QtWebEngine."""
        source = self.source_for(final_url or requested_url)
        page = DownloadedPage(
            requested_url=requested_url,
            final_url=final_url or requested_url,
            html=html,
            status_code=200,
        )
        return source.parse(page)

    def parse_rendered_book_html(
        self,
        *,
        requested_url: str,
        final_url: str,
        html: str,
    ) -> Book:
        """Interpreta o DOM renderizado da página raiz de uma obra."""
        source = self.source_for(final_url or requested_url)
        page = DownloadedPage(
            requested_url=requested_url,
            final_url=final_url or requested_url,
            html=html,
            status_code=200,
        )
        return source.parse_book(page)
