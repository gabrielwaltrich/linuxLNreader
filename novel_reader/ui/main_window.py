from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from novel_reader.browser import BrowserSession
from novel_reader.models import Chapter
from novel_reader.sources import SourceManager
from novel_reader.styles import DARK_STYLE, LIGHT_STYLE
from novel_reader.ui.reader_view import ReaderView
from novel_reader.ui.source_worker import SourceWorker


DEMO_TEXT = """A v0.3.1 corrige a detecção de capítulos bloqueados e melhora a espera por conteúdo dinâmico.

Agora fontes simples continuam usando HTTP, enquanto fontes dinâmicas podem pedir um navegador QtWebEngine real para renderizar JavaScript antes da extração.

O ReaderView continua sem conhecer detalhes do site. Ele recebe apenas título, capítulo e texto limpo.

O adaptador WebNovel agora solicita o Browser Source. O DOM renderizado é enviado ao mesmo parser, sem lógica de desbloqueio, paywall ou automação de login.

A sessão do navegador mantém cookies e cache localmente para preservar uma navegação normal entre execuções.

Os botões de capítulo anterior e próximo aparecem quando o parser encontra relações de navegação na página."""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.settings = QSettings("NovelReader", "NovelReader")
        self.dark_mode = self.settings.value("dark_mode", False, bool)
        self.source_manager = SourceManager()
        self.browser = BrowserSession(self.source_manager, self)
        self.browser.loaded.connect(self._url_loaded)
        self.browser.failed.connect(self._url_failed)
        self.browser.loaded.connect(lambda _chapter: self._set_loading(False))
        self.browser.failed.connect(lambda _message: self._set_loading(False))
        self.browser.status_changed.connect(self.statusBar().showMessage)
        self.worker: SourceWorker | None = None
        self.current_chapter: Chapter | None = None

        self.setWindowTitle("Novel Reader — v0.3.1")
        self.resize(1050, 760)

        self._build_ui()
        self._build_actions()
        self._restore_settings()
        self._apply_theme()
        self.reader.set_chapter("", "", "")

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 18, 24, 8)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Cole uma URL pública de capítulo...")
        self.url_input.returnPressed.connect(self.open_url)

        self.open_url_button = QPushButton("Abrir")
        self.open_url_button.clicked.connect(self.open_url)

        self.open_txt_button = QPushButton("Abrir TXT")
        self.open_txt_button.clicked.connect(self.open_txt)

        self.demo_button = QPushButton("Demonstração")
        self.demo_button.clicked.connect(self.load_demo)

        top.addWidget(self.url_input, 1)
        top.addWidget(self.open_url_button)
        top.addWidget(self.open_txt_button)
        top.addWidget(self.demo_button)

        self.reader = ReaderView()
        self.reader.progress_changed.connect(self._set_progress)

        controls = QHBoxLayout()

        self.previous_button = QPushButton("← Anterior")
        self.previous_button.clicked.connect(self.open_previous)
        self.previous_button.setEnabled(False)

        self.decrease_button = QPushButton("A−")
        self.decrease_button.clicked.connect(self.decrease_font)

        self.increase_button = QPushButton("A+")
        self.increase_button.clicked.connect(self.increase_font)

        self.theme_button = QPushButton("Tema")
        self.theme_button.clicked.connect(self.toggle_theme)

        self.fullscreen_button = QPushButton("Tela cheia")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

        self.progress_label = QLabel("0%")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.next_button = QPushButton("Próximo →")
        self.next_button.clicked.connect(self.open_next)
        self.next_button.setEnabled(False)

        controls.addWidget(self.previous_button)
        controls.addWidget(self.decrease_button)
        controls.addWidget(self.increase_button)
        controls.addWidget(self.theme_button)
        controls.addStretch(1)
        controls.addWidget(self.progress_label)
        controls.addStretch(1)
        controls.addWidget(self.fullscreen_button)
        controls.addWidget(self.next_button)

        layout.addLayout(top)
        layout.addWidget(self.reader, 1)
        layout.addLayout(controls)

        self.setCentralWidget(root)
        self.statusBar().showMessage("v0.3.1 — extração progressiva e detecção de bloqueio corrigida.")

    def _build_actions(self) -> None:
        shortcuts = [
            ("increase_font", QKeySequence("+"), self.increase_font),
            ("increase_font_equal", QKeySequence("="), self.increase_font),
            ("decrease_font", QKeySequence("-"), self.decrease_font),
            ("theme", QKeySequence("T"), self.toggle_theme),
            ("fullscreen", QKeySequence("F"), self.toggle_fullscreen),
            ("escape_fullscreen", QKeySequence("Esc"), self.exit_fullscreen),
            ("open_txt", QKeySequence("Ctrl+O"), self.open_txt),
            ("previous", QKeySequence("Alt+Left"), self.open_previous),
            ("next", QKeySequence("Alt+Right"), self.open_next),
        ]

        for name, shortcut, callback in shortcuts:
            action = QAction(name, self)
            action.setShortcut(shortcut)
            action.triggered.connect(callback)
            self.addAction(action)

    def _restore_settings(self) -> None:
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        font_size = self.settings.value("font_size", 20, int)
        self.reader.set_font_size(font_size)

    def _apply_theme(self) -> None:
        self.setStyleSheet(DARK_STYLE if self.dark_mode else LIGHT_STYLE)
        self.theme_button.setText("☀ Claro" if self.dark_mode else "☾ Escuro")

    def toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self.settings.setValue("dark_mode", self.dark_mode)
        self._apply_theme()

    def increase_font(self) -> None:
        self.reader.set_font_size(self.reader.font_size + 1)
        self.settings.setValue("font_size", self.reader.font_size)

    def decrease_font(self) -> None:
        self.reader.set_font_size(self.reader.font_size - 1)
        self.settings.setValue("font_size", self.reader.font_size)

    def toggle_fullscreen(self) -> None:
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def exit_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()

    def load_demo(self) -> None:
        chapter = Chapter(
            source="Demonstração",
            url="",
            book_title="Novel Reader",
            chapter_title="v0.3.1 — Browser Source",
            text=DEMO_TEXT,
        )
        self._show_chapter(chapter)
        self.statusBar().showMessage("Demonstração carregada.")

    def open_txt(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir capítulo",
            "",
            "Arquivos de texto (*.txt);;Todos os arquivos (*)",
        )
        if not filename:
            return

        path = Path(filename)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")
        except OSError as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir o arquivo:\n{exc}")
            return

        chapter = Chapter(
            source="Arquivo local",
            url=path.as_uri(),
            book_title=path.stem,
            chapter_title=path.name,
            text=text,
        )
        self._show_chapter(chapter)
        self.statusBar().showMessage(str(path))

    def open_url(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.information(self, "URL", "Cole uma URL primeiro.")
            return
        if self.browser.is_busy or (self.worker and self.worker.isRunning()):
            return

        try:
            use_browser = self.source_manager.requires_browser(url)
        except Exception as exc:
            self._url_failed(str(exc))
            return

        self._set_loading(True)

        if use_browser:
            self.statusBar().showMessage("Abrindo no navegador embutido…")
            self.browser.load(url)
            return

        self.statusBar().showMessage("Carregando página por HTTP…")
        self.worker = SourceWorker(url, self.source_manager, self)
        self.worker.loaded.connect(self._url_loaded)
        self.worker.failed.connect(self._url_failed)
        self.worker.finished.connect(lambda: self._set_loading(False))
        self.worker.start()

    def _url_loaded(self, chapter: Chapter) -> None:
        self._show_chapter(chapter)
        self.url_input.setText(chapter.url)
        self.statusBar().showMessage(f"Fonte: {chapter.source} — {len(chapter.text):,} caracteres")

    def _url_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Não foi possível abrir", message)
        self.statusBar().showMessage("Falha ao carregar a página.")

    def _show_chapter(self, chapter: Chapter) -> None:
        self.current_chapter = chapter
        self.reader.set_chapter(
            chapter.display_book_title,
            chapter.display_chapter_title,
            chapter.text,
        )
        self.previous_button.setEnabled(bool(chapter.previous_url))
        self.next_button.setEnabled(bool(chapter.next_url))

    def open_previous(self) -> None:
        if self.current_chapter and self.current_chapter.previous_url:
            self.url_input.setText(self.current_chapter.previous_url)
            self.open_url()

    def open_next(self) -> None:
        if self.current_chapter and self.current_chapter.next_url:
            self.url_input.setText(self.current_chapter.next_url)
            self.open_url()

    def _set_loading(self, loading: bool) -> None:
        self.open_url_button.setEnabled(not loading)
        self.url_input.setEnabled(not loading)
        self.open_url_button.setText("Carregando…" if loading else "Abrir")

    def _set_progress(self, progress: int) -> None:
        self.progress_label.setText(f"{progress}%")

    def closeEvent(self, event) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("font_size", self.reader.font_size)
        self.settings.setValue("dark_mode", self.dark_mode)
        super().closeEvent(event)
