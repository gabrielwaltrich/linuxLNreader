from html import escape

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTextBrowser


class ReaderView(QTextBrowser):
    progress_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._font_size = 20
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

    def set_chapter(self, title: str, chapter: str, text: str) -> None:
        self._title = title
        self._chapter = chapter
        self._text = text
        self._render()
        self.verticalScrollBar().setValue(0)

    def _render(self) -> None:
        if not self._text:
            self.setHtml(
                """
                <div style="max-width: 760px; margin: 90px auto; text-align:center;">
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
                    f'<p style="line-height:1.72; margin:0 0 1.15em 0;">'
                    f'{escape(paragraph).replace(chr(10), "<br>")}</p>'
                )

        body = "\n".join(paragraphs)

        self.setHtml(
            f"""
            <div style="max-width: 760px; margin: 55px auto 120px auto;">
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
