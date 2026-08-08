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
        self.setObjectName("readerSurface")
        self.setFrameShape(self.Shape.NoFrame)

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
                <div style="max-width:{self._content_width}px; margin:120px auto; text-align:center;">
                    <div style="font-size:46px; margin-bottom:18px;">📖</div>
                    <div style="font-size:24px; font-weight:700; margin-bottom:10px;">
                        Sua leitura começa aqui
                    </div>
                    <div style="font-size:14px; opacity:.62; line-height:1.6;">
                        Cole a URL de uma obra ou capítulo no topo,<br>
                        escolha algo na Library ou abra um arquivo TXT.
                    </div>
                </div>
                """
            )
            return

        paragraphs = []
        for paragraph in self._text.split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph:
                paragraphs.append(
                    f'<p style="line-height:{self._line_height}; margin:0 0 1.28em 0;">'
                    f'{escape(paragraph).replace(chr(10), "<br>")}</p>'
                )

        body = "\n".join(paragraphs)
        safe_title = escape(self._title)
        safe_chapter = escape(self._chapter)

        self.setHtml(
            f"""
            <article style="
                max-width:{self._content_width}px;
                margin:64px auto 150px auto;
                padding:0 34px;
            ">
                <header style="
                    text-align:left;
                    margin-bottom:52px;
                    padding-bottom:30px;
                    border-bottom:1px solid rgba(127,127,127,.20);
                ">
                    <div style="
                        font-size:12px;
                        text-transform:uppercase;
                        letter-spacing:1.3px;
                        opacity:.58;
                        font-weight:600;
                        margin-bottom:12px;
                    ">{safe_title}</div>
                    <div style="
                        font-size:1.55em;
                        font-weight:750;
                        line-height:1.25;
                    ">{safe_chapter}</div>
                </header>
                <section style="
                    font-size:1em;
                    letter-spacing:.05px;
                ">
                    {body}
                </section>
            </article>
            """
        )

    def _emit_progress(self) -> None:
        scrollbar = self.verticalScrollBar()
        maximum = scrollbar.maximum()
        progress = 0 if maximum <= 0 else int((scrollbar.value() / maximum) * 100)
        self.progress_changed.emit(progress)
