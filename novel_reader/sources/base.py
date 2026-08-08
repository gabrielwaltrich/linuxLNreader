from abc import ABC, abstractmethod

from novel_reader.models import Book, Chapter, UrlKind
from novel_reader.services.downloader import DownloadedPage


class NovelSource(ABC):
    name = "Fonte"
    priority = 0
    requires_browser = False

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        raise NotImplementedError

    def classify_url(self, url: str) -> UrlKind:
        return UrlKind.CHAPTER

    @abstractmethod
    def parse(self, page: DownloadedPage) -> Chapter:
        raise NotImplementedError

    def parse_book(self, page: DownloadedPage) -> Book:
        raise NotImplementedError(
            f"{self.name} ainda não implementa leitura de página de livro."
        )
