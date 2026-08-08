from pathlib import Path
from urllib.parse import urlparse, unquote

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from novel_reader.app_config import AppConfigStore
from novel_reader.browser import BrowserSession
from novel_reader.database import LibraryDatabase
from novel_reader.models import Book, Chapter, UrlKind
from novel_reader.services.chapter_cache import ChapterCache
from novel_reader.sources import SourceManager
from novel_reader.styles import DARK_STYLE, LIGHT_STYLE
from novel_reader.ui.library_panel import LibraryPanel
from novel_reader.ui.reader_view import ReaderView
from novel_reader.ui.preferences_dialog import PreferencesDialog
from novel_reader.ui.source_worker import SourceWorker


DEMO_TEXT = """A v0.5 organiza a biblioteca por livros, mantendo a leitura contínua.

Cada livro agora possui uma entrada própria na biblioteca. Os capítulos conhecidos aparecem agrupados abaixo dele, e o progresso continua sendo salvo por capítulo.

O banco SQLite da v0.4 é migrado automaticamente: histórico existente é associado aos novos registros de livros sem apagar seu progresso.

O Browser Source e o CLI continuam usando o mesmo SourceManager; a v0.5 altera principalmente a organização da biblioteca.

Use Biblioteca ou Ctrl+B. Dê duplo clique no livro para abrir o último capítulo, ou expanda-o para escolher um capítulo conhecido."""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.settings = QSettings("NovelReader", "NovelReader")
        self.app_config_store = AppConfigStore()
        self.app_config = self.app_config_store.load()
        self.dark_mode = self.settings.value("dark_mode", False, bool)
        self.source_manager = SourceManager()
        self.library_db = LibraryDatabase()
        self.chapter_cache = ChapterCache()
        self._pending_url = ""

        self.browser = BrowserSession(self.source_manager, self)
        self.browser.loaded.connect(self._url_loaded)
        self.browser.book_loaded.connect(self._book_loaded)
        self.browser.failed.connect(self._url_failed)
        self.browser.status_changed.connect(self.statusBar().showMessage)

        self.worker: SourceWorker | None = None
        self.current_chapter: Chapter | None = None
        self._current_previous_url: str | None = None
        self._current_next_url: str | None = None
        self._restoring_progress = False

        self.progress_timer = QTimer(self)
        self.progress_timer.setSingleShot(True)
        self.progress_timer.setInterval(650)
        self.progress_timer.timeout.connect(self._save_current_progress)

        self.setWindowTitle("Novel Reader 1.0.9")
        self.resize(1320, 860)

        self._build_ui()
        self._build_library()
        self._build_actions()
        self._restore_settings()
        self._apply_theme()
        self.reader.set_chapter("", "", "")
        self._refresh_continue_button()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 18, 22, 10)
        layout.setSpacing(12)

        # Brand/header
        header = QFrame()
        header.setObjectName("topHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 12, 14, 12)
        header_layout.setSpacing(10)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)
        brand = QLabel("Novel Reader")
        brand.setObjectName("brandTitle")
        subtitle = QLabel("Sua Library e leitura em um só lugar")
        subtitle.setObjectName("brandSubtitle")
        brand_col.addWidget(brand)
        brand_col.addWidget(subtitle)
        header_layout.addLayout(brand_col)
        header_layout.addStretch(1)

        self.continue_button = QPushButton("▶ Continuar")
        self.continue_button.setObjectName("primaryButton")
        self.continue_button.clicked.connect(self.continue_last)

        self.library_button = QPushButton("Library")
        self.library_button.setObjectName("accentButton")
        self.library_button.clicked.connect(self.toggle_library)

        self.preferences_button = QPushButton("⚙ Preferências")
        self.preferences_button.clicked.connect(self.open_preferences)

        self.theme_button = QPushButton("☾")
        self.theme_button.setObjectName("iconButton")
        self.theme_button.setToolTip("Alternar tema")
        self.theme_button.clicked.connect(self.toggle_theme)

        header_layout.addWidget(self.continue_button)
        header_layout.addWidget(self.library_button)
        header_layout.addWidget(self.preferences_button)
        header_layout.addWidget(self.theme_button)
        layout.addWidget(header)

        # URL/open card
        url_card = QFrame()
        url_card.setObjectName("urlCard")
        top = QHBoxLayout(url_card)
        top.setContentsMargins(14, 11, 14, 11)
        top.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "Cole uma URL de livro ou capítulo do WebNovel…"
        )
        self.url_input.setClearButtonEnabled(True)
        self.url_input.returnPressed.connect(self.open_url)

        self.open_url_button = QPushButton("Abrir")
        self.open_url_button.setObjectName("primaryButton")
        self.open_url_button.clicked.connect(self.open_url)

        self.open_txt_button = QPushButton("Abrir TXT")
        self.open_txt_button.clicked.connect(self.open_txt)

        top.addWidget(self.url_input, 1)
        top.addWidget(self.open_url_button)
        top.addWidget(self.open_txt_button)
        layout.addWidget(url_card)

        self.reader = ReaderView()
        self.reader.progress_changed.connect(self._set_progress)
        layout.addWidget(self.reader, 1)

        # Reader controls
        toolbar = QFrame()
        toolbar.setObjectName("readerToolbar")
        controls = QHBoxLayout(toolbar)
        controls.setContentsMargins(12, 9, 12, 9)
        controls.setSpacing(7)

        self.previous_button = QPushButton("← Anterior")
        self.previous_button.clicked.connect(self.open_previous)
        self.previous_button.setEnabled(False)

        self.decrease_button = QPushButton("A−")
        self.decrease_button.setObjectName("iconButton")
        self.decrease_button.setToolTip("Diminuir fonte")
        self.decrease_button.clicked.connect(self.decrease_font)

        self.increase_button = QPushButton("A+")
        self.increase_button.setObjectName("iconButton")
        self.increase_button.setToolTip("Aumentar fonte")
        self.increase_button.clicked.connect(self.increase_font)

        self.favorite_button = QPushButton("☆")
        self.favorite_button.setObjectName("iconButton")
        self.favorite_button.setToolTip("Favoritar livro atual")
        self.favorite_button.clicked.connect(self.toggle_current_favorite)
        self.favorite_button.setEnabled(False)

        self.current_library_button = QPushButton("＋ Library")
        self.current_library_button.setToolTip(
            "Adicionar/remover o livro atual da Library"
        )
        self.current_library_button.clicked.connect(self.toggle_current_library)
        self.current_library_button.setEnabled(False)

        self.fullscreen_button = QPushButton("⛶")
        self.fullscreen_button.setObjectName("iconButton")
        self.fullscreen_button.setToolTip("Tela cheia")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

        self.progress_label = QLabel("0%")
        self.progress_label.setObjectName("mutedLabel")
        self.progress_label.setMinimumWidth(52)
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.next_button = QPushButton("Próximo →")
        self.next_button.setObjectName("primaryButton")
        self.next_button.clicked.connect(self.open_next)
        self.next_button.setEnabled(False)

        controls.addWidget(self.previous_button)
        controls.addWidget(self.decrease_button)
        controls.addWidget(self.increase_button)
        controls.addWidget(self.favorite_button)
        controls.addWidget(self.current_library_button)
        controls.addStretch(1)
        controls.addWidget(self.progress_label)
        controls.addStretch(1)
        controls.addWidget(self.fullscreen_button)
        controls.addWidget(self.next_button)

        layout.addWidget(toolbar)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Novel Reader 1.0.9 — pronto para ler.")

    def _build_library(self) -> None:
        self.library_panel = LibraryPanel(self.library_db, self)
        self.library_panel.open_requested.connect(self.open_library_url)
        self.library_panel.sync_requested.connect(self.open_book_url)
        self.library_panel.changed.connect(self._refresh_continue_button)

        self.library_dock = QDockWidget("Biblioteca", self)
        self.library_dock.setObjectName("libraryDock")
        self.library_dock.setWidget(self.library_panel)
        self.library_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.library_dock)
        self.library_dock.hide()

    def _build_actions(self) -> None:
        shortcuts = [
            ("increase_font", QKeySequence("+"), self.increase_font),
            ("increase_font_equal", QKeySequence("="), self.increase_font),
            ("decrease_font", QKeySequence("-"), self.decrease_font),
            ("theme", QKeySequence("T"), self.toggle_theme),
            ("fullscreen", QKeySequence("F"), self.toggle_fullscreen),
            ("escape_fullscreen", QKeySequence("Esc"), self.exit_fullscreen),
            ("open_txt", QKeySequence("Ctrl+O"), self.open_txt),
            ("library", QKeySequence("Ctrl+B"), self.toggle_library),
            ("continue", QKeySequence("Ctrl+R"), self.continue_last),
            ("favorite", QKeySequence("Ctrl+D"), self.toggle_current_favorite),
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
        state = self.settings.value("window_state")
        if state:
            self.restoreState(state)
        self.reader.set_font_size(self.settings.value("font_size", 20, int))
        self.reader.set_content_width(self.settings.value("content_width", 760, int))
        self.reader.set_line_height(self.settings.value("line_height", 1.72, float))
        self.library_panel.set_ascii_options(
            self.settings.value("ascii_enabled", True, bool),
            self.settings.value("ascii_width", 38, int),
            self.settings.value("ascii_height", 18, int),
        )

    def _apply_theme(self) -> None:
        self.setStyleSheet(DARK_STYLE if self.dark_mode else LIGHT_STYLE)
        self.theme_button.setText("☀" if self.dark_mode else "☾")

    def open_preferences(self) -> None:
        dialog = PreferencesDialog(
            font_size=self.reader.font_size,
            content_width=self.reader.content_width,
            line_height=self.reader.line_height,
            ascii_enabled=self.settings.value("ascii_enabled", True, bool),
            ascii_width=self.settings.value("ascii_width", 38, int),
            ascii_height=self.settings.value("ascii_height", 18, int),
            parent=self,
        )
        if not dialog.exec():
            return
        values = dialog.values()
        for key, value in values.items():
            self.settings.setValue(key, value)
        self.reader.set_font_size(values["font_size"])
        self.reader.set_content_width(values["content_width"])
        self.reader.set_line_height(values["line_height"])
        self.library_panel.set_ascii_options(
            values["ascii_enabled"], values["ascii_width"], values["ascii_height"]
        )

    def toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self.settings.setValue("dark_mode", self.dark_mode)
        self._apply_theme()

    def increase_font(self) -> None:
        self.reader.set_font_size(self.reader.font_size + 1)
        self.settings.setValue("font_size", self.reader.font_size)
        self.settings.setValue("content_width", self.reader.content_width)
        self.settings.setValue("line_height", self.reader.line_height)

    def decrease_font(self) -> None:
        self.reader.set_font_size(self.reader.font_size - 1)
        self.settings.setValue("font_size", self.reader.font_size)
        self.settings.setValue("content_width", self.reader.content_width)
        self.settings.setValue("line_height", self.reader.line_height)

    def toggle_fullscreen(self) -> None:
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def exit_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()

    def toggle_library(self) -> None:
        self.library_panel.refresh()
        self.library_dock.setVisible(not self.library_dock.isVisible())

    def load_demo(self) -> None:
        chapter = Chapter(
            source="Demonstração",
            url="",
            book_title="Novel Reader",
            chapter_title="v0.5 — Biblioteca por livros",
            text=DEMO_TEXT,
        )
        self._show_chapter(chapter, persist=False)

    def open_txt(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Abrir capítulo", "", "Arquivos de texto (*.txt);;Todos os arquivos (*)"
        )
        if not filename:
            return
        self._open_local_file(Path(filename))

    def _open_local_file(self, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")
        except OSError as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir o arquivo:\n{exc}")
            return

        chapter = Chapter(
            source="Arquivo local",
            url=path.resolve().as_uri(),
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
        if url.startswith("file://"):
            self.open_library_url(url)
            return
        if self.browser.is_busy or (self.worker and self.worker.isRunning()):
            return

        try:
            kind = self.source_manager.classify_url(url)
            use_browser = self.source_manager.requires_browser(url)
        except Exception as exc:
            self._url_failed(str(exc))
            return

        if kind is UrlKind.BOOK:
            self.open_book_url(url)
            return

        self._pending_url = url
        self._set_loading(True)
        if use_browser:
            self.statusBar().showMessage("Abrindo capítulo no navegador embutido…")
            self.browser.loaded.connect(
                self._browser_finished,
                Qt.ConnectionType.SingleShotConnection,
            )
            self.browser.failed.connect(
                self._browser_failed_finished,
                Qt.ConnectionType.SingleShotConnection,
            )
            self.browser.load(url)
            return

        self.statusBar().showMessage("Carregando página por HTTP…")
        self.worker = SourceWorker(url, self.source_manager, self)
        self.worker.loaded.connect(self._url_loaded)
        self.worker.failed.connect(self._url_failed)
        self.worker.finished.connect(lambda: self._set_loading(False))
        self.worker.start()

    def open_book_url(self, url: str) -> None:
        if not url or self.browser.is_busy:
            return
        self.url_input.setText(url)
        self._set_loading(True)
        self.statusBar().showMessage("Sincronizando índice da obra…")
        self.browser.book_loaded.connect(
            self._browser_book_finished,
            Qt.ConnectionType.SingleShotConnection,
        )
        self.browser.failed.connect(
            self._browser_failed_finished,
            Qt.ConnectionType.SingleShotConnection,
        )
        self.browser.load_book(url)

    def _browser_finished(self, chapter: Chapter) -> None:
        self._set_loading(False)

    def _browser_book_finished(self, book: Book) -> None:
        self._set_loading(False)

    def _browser_failed_finished(self, message: str) -> None:
        self._set_loading(False)

    def _book_loaded(self, book: Book) -> None:
        existing = self.library_db.book_for_url(book.url)
        before = self.library_db.index_count(existing.id) if existing else 0
        book_id = self.library_db.save_book_index(book)
        after = self.library_db.index_count(book_id)
        added = max(0, after - before)

        self.library_panel.refresh()
        self.library_panel.focus_book(book_id)
        self.library_dock.show()
        self.url_input.setText(book.url)
        self._refresh_continue_button()

        suffix = f" (+{added} novos)" if added else " (sem novos capítulos)"
        self.statusBar().showMessage(
            f"{book.title} — {after} capítulos conhecidos{suffix}."
        )

    def _url_loaded(self, chapter: Chapter) -> None:
        self.chapter_cache.save(chapter)
        self._pending_url = ""
        self._show_chapter(chapter)
        self.url_input.setText(chapter.url)
        self.library_panel.set_current_url(chapter.url)
        self.statusBar().showMessage(
            f"Fonte: {chapter.source} — {len(chapter.text):,} caracteres"
        )

    def _url_failed(self, message: str) -> None:
        cached = self.chapter_cache.load(self._pending_url) if self._pending_url else None
        if cached:
            self._pending_url = ""
            self._show_chapter(cached)
            self.url_input.setText(cached.url)
            self.statusBar().showMessage("Rede indisponível/falhou — usando capítulo do cache local.")
            return
        self._pending_url = ""
        QMessageBox.warning(self, "Não foi possível abrir", message)
        self.statusBar().showMessage("Falha ao carregar a página.")

    def _show_chapter(self, chapter: Chapter, persist: bool = True) -> None:
        self._save_current_progress()
        self.current_chapter = chapter
        saved_progress = self.library_db.progress_for(chapter.url) if persist and chapter.url else 0

        self._restoring_progress = True
        self.reader.set_chapter(chapter.display_book_title, chapter.display_chapter_title, chapter.text)
        if saved_progress:
            self.reader.set_progress(saved_progress)
        QTimer.singleShot(100, lambda: setattr(self, "_restoring_progress", False))

        self._current_previous_url = chapter.previous_url
        self._current_next_url = chapter.next_url

        if persist and chapter.url:
            self.library_db.record_chapter(chapter, saved_progress)

            index_previous, index_next = self.library_db.index_neighbors(chapter.url)
            # O índice local é preferido porque representa a ordem completa
            # conhecida da obra. Links do capítulo servem como fallback.
            self._current_previous_url = index_previous or chapter.previous_url
            self._current_next_url = index_next or chapter.next_url

            self.library_panel.set_current_url(chapter.url)
            self._refresh_continue_button()
            self._refresh_favorite_button()
            self._refresh_current_library_button()
        else:
            self.library_panel.set_current_url("")

        self.previous_button.setEnabled(bool(self._current_previous_url))
        self.next_button.setEnabled(bool(self._current_next_url))

        if not persist or not chapter.url:
            self.favorite_button.setEnabled(False)
            self.current_library_button.setEnabled(False)
            self.current_library_button.setText("＋ Library")

    def open_previous(self) -> None:
        if self._current_previous_url:
            self.open_library_url(self._current_previous_url)

    def open_next(self) -> None:
        if self._current_next_url:
            self.open_library_url(self._current_next_url)

    def continue_last(self) -> None:
        entry = self.library_db.last_opened()
        if entry:
            self.open_library_url(entry.url)

    def open_library_url(self, url: str) -> None:
        if url.startswith("file://"):
            parsed = urlparse(url)
            path = Path(unquote(parsed.path))
            if path.exists():
                self._open_local_file(path)
            else:
                QMessageBox.warning(self, "Arquivo não encontrado", str(path))
            return
        self.url_input.setText(url)
        self.open_url()

    def toggle_current_library(self) -> None:
        if not self.current_chapter or not self.current_chapter.url:
            return
        book = self.library_db.book_for_url(self.current_chapter.url)
        if not book:
            return
        self.library_db.toggle_book_library(book.id)
        self.library_panel.refresh()
        self._refresh_current_library_button()
        self._refresh_favorite_button()

    def _refresh_current_library_button(self) -> None:
        if not self.current_chapter or not self.current_chapter.url:
            self.current_library_button.setEnabled(False)
            self.current_library_button.setText("＋ Library")
            return
        book = self.library_db.book_for_url(self.current_chapter.url)
        self.current_library_button.setEnabled(book is not None)
        in_library = bool(book and self.library_db.is_book_in_library(book.id))
        self.current_library_button.setText("✓ Library" if in_library else "＋ Library")

    def toggle_current_favorite(self) -> None:
        if not self.current_chapter or not self.current_chapter.url:
            return
        book = self.library_db.book_for_url(self.current_chapter.url)
        if not book:
            return
        self.library_db.toggle_book_favorite(book.id)
        self.library_panel.refresh()
        self._refresh_favorite_button()
        self._refresh_current_library_button()

    def _refresh_favorite_button(self) -> None:
        if not self.current_chapter or not self.current_chapter.url:
            self.favorite_button.setEnabled(False)
            self.favorite_button.setText("☆")
            return
        book = self.library_db.book_for_url(self.current_chapter.url)
        self.favorite_button.setEnabled(book is not None)
        self.favorite_button.setText("★" if book and book.favorite else "☆")

    def _refresh_continue_button(self) -> None:
        entry = self.library_db.last_opened()
        self.continue_button.setEnabled(entry is not None)
        if entry:
            self.continue_button.setToolTip(f"{entry.display_title} — {entry.display_chapter} ({entry.progress}%)")
        else:
            self.continue_button.setToolTip("Nenhuma leitura recente")

    def _set_loading(self, loading: bool) -> None:
        self.open_url_button.setEnabled(not loading)
        self.url_input.setEnabled(not loading)
        self.open_url_button.setText("Abrindo…" if loading else "Abrir")

    def _set_progress(self, progress: int) -> None:
        self.progress_label.setText(f"{progress}%")
        if not self._restoring_progress and self.current_chapter and self.current_chapter.url:
            self.progress_timer.start()

    def _save_current_progress(self) -> None:
        if self.current_chapter and self.current_chapter.url:
            text = self.progress_label.text().rstrip("%")
            try:
                progress = int(text)
            except ValueError:
                return
            self.library_db.save_progress(self.current_chapter.url, progress)
            self._refresh_continue_button()

    def closeEvent(self, event) -> None:
        self._save_current_progress()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())
        self.settings.setValue("font_size", self.reader.font_size)
        self.settings.setValue("content_width", self.reader.content_width)
        self.settings.setValue("line_height", self.reader.line_height)
        self.settings.setValue("dark_mode", self.dark_mode)
        super().closeEvent(event)


def _sync_app_config_from_reader(self) -> None:
    """Persist GUI reading preferences to the shared config file."""
    try:
        changes = {}
        if hasattr(self, "reader"):
            if hasattr(self.reader, "font_size"):
                changes["font_size"] = int(self.reader.font_size)
            if hasattr(self.reader, "content_width"):
                changes["content_width"] = int(self.reader.content_width)
            if hasattr(self.reader, "line_height"):
                changes["line_height"] = float(self.reader.line_height)
        if changes:
            self.app_config = self.app_config_store.update(**changes)
    except Exception:
        pass
