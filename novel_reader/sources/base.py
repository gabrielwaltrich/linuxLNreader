from abc import ABC, abstractmethod

from novel_reader.models import Chapter
from novel_reader.services.downloader import DownloadedPage


class NovelSource(ABC):
    name = "Fonte"
    priority = 0
    requires_browser = False

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, page: DownloadedPage) -> Chapter:
        raise NotImplementedError
