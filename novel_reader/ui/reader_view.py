from html import escape

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTextBrowser


class ReaderView(QTextBrowser):
    progress_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._font_size = 20
        self._content_width = 760
        self._line_height = 1.72
        self._title = ""
        self._chapter = ""
        self._text = ""

        self.setOpenExternalLinks(False)
        self.setReadOnly(True)

        scrollbar = self.verticalScrollBar()
        scrollbar.valueChanged.connect(self._emit_progress)
        scrollbar.rangeChanged.connect(lambda *_: self._emit_progress())

    @property
    def font_size(self) -> int:
        return self._font_size

    def set_font_size(self, size: int) -> None:
        self._font_size = max(12, min(size, 40))
        font = QFont()
        font.setPointSize(self._font_size)
        self.setFont(font)
        self._render()

    @property
    def content_width(self) -> int:
        return self._content_width

    @property
    def line_height(self) -> float:
        return self._line_height

    def set_content_width(self, width: int) -> None:
        self._content_width = max(480, min(int(width), 1200))
        self._render()

    def set_line_height(self, value: float) -> None:
        self._line_height = max(1.2, min(float(value), 2.4))
        self._render()

    def set_chapter(self, title: str, chapter: str, text: str) -> None:
        self._title = title
        self._chapter = chapter
        self._text = text
        self._render()
        self.verticalScrollBar().setValue(0)


    def set_progress(self, progress: int) -> None:
        progress = max(0, min(int(progress), 100))

        def apply_progress() -> None:
            scrollbar = self.verticalScrollBar()
            maximum = scrollbar.maximum()
            scrollbar.setValue(int(maximum * (progress / 100))) if maximum > 0 else None

        QTimer.singleShot(0, apply_progress)

    def _render(self) -> None:
        if not self._text:
            self.setHtml(
                f"""
                <div style="max-width: {self._content_width}px; margin: 90px auto; text-align:center;">
                    <h2>Nenhum capítulo aberto</h2>
                    <p>Use “Abrir TXT” ou “Carregar demonstração”.</p>
                </div>
                """
            )
            return

        paragraphs = []
        for paragraph in self._text.split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph:
                paragraphs.append(
                    f'<p style="line-height:{self._line_height}; margin:0 0 1.15em 0;">'
                    f'{escape(paragraph).replace(chr(10), "<br>")}</p>'
                )

        body = "\n".join(paragraphs)

        self.setHtml(
            f"""
            <div style="max-width: {self._content_width}px; margin: 55px auto 120px auto;">
                <div style="text-align:center; margin-bottom:50px;">
                    <div style="font-size:0.70em; opacity:0.65;">{escape(self._title)}</div>
                    <h2 style="font-weight:600; margin-top:10px;">{escape(self._chapter)}</h2>
                </div>
                {body}
            </div>
            """
        )

    def _emit_progress(self) -> None:
        scrollbar = self.verticalScrollBar()
        maximum = scrollbar.maximum()
        progress = 0 if maximum <= 0 else int((scrollbar.value() / maximum) * 100)
        self.progress_changed.emit(progress)
