from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from novel_reader.services.media_ascii import MediaAsciiService


class AsciiCoverWorker(QThread):
    rendered = Signal(str, str, str)  # url, ascii, backend
    failed = Signal(str, str)         # url, message

    def __init__(
        self,
        url: str,
        *,
        width: int = 34,
        height: int = 18,
        parent=None,
    ):
        super().__init__(parent)
        self.url = url
        self.width = width
        self.height = height

    def run(self) -> None:
        try:
            result = MediaAsciiService().render_url(
                self.url,
                width=self.width,
                height=self.height,
            )
        except Exception as exc:
            self.failed.emit(self.url, str(exc))
            return

        self.rendered.emit(self.url, result.text, result.backend)
