from PySide6.QtCore import QThread, Signal

from novel_reader.errors import NovelReaderError
from novel_reader.models import Chapter
from novel_reader.sources import SourceManager


class SourceWorker(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, url: str, manager: SourceManager, parent=None):
        super().__init__(parent)
        self.url = url
        self.manager = manager

    def run(self) -> None:
        try:
            chapter: Chapter = self.manager.load_chapter(self.url)
        except NovelReaderError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # proteção da UI contra falhas inesperadas
            self.failed.emit(f"Erro inesperado ao carregar a página: {exc}")
        else:
            self.loaded.emit(chapter)
