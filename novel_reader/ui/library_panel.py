from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from novel_reader.ui.ascii_worker import AsciiCoverWorker

from novel_reader.database import (
    BookEntry,
    BookIndexEntry,
    LibraryDatabase,
    LibraryEntry,
)


class LibraryPanel(QWidget):
    open_requested = Signal(str)
    sync_requested = Signal(str)
    changed = Signal()

    KIND_ROLE = Qt.ItemDataRole.UserRole
    ID_ROLE = Qt.ItemDataRole.UserRole + 1
    URL_ROLE = Qt.ItemDataRole.UserRole + 2
    READ_ROLE = Qt.ItemDataRole.UserRole + 3
    PROGRESS_ROLE = Qt.ItemDataRole.UserRole + 4

    def __init__(self, database: LibraryDatabase, parent=None):
        super().__init__(parent)
        self.database = database
        self._current_url = ""
        self._selected_book_id_value: int | None = None
        self._cover_worker: AsciiCoverWorker | None = None
        self._cover_url = ""
        self._ascii_enabled = True
        self._ascii_width = 38
        self._ascii_height = 18

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QLabel("Biblioteca / Índice")
        header.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(header)

        self.details = QFrame()
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(10, 10, 10, 10)
        details_layout.setSpacing(6)

        self.cover_ascii = QPlainTextEdit()
        self.cover_ascii.setReadOnly(True)
        self.cover_ascii.setMaximumHeight(210)
        self.cover_ascii.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.cover_ascii.setPlaceholderText("Capa ASCII")
        self.cover_ascii.setStyleSheet(
            "font-family: monospace; font-size: 9px;"
        )
        self.cover_ascii.hide()
        details_layout.addWidget(self.cover_ascii)

        self.book_title = QLabel("Selecione um livro")
        self.book_title.setWordWrap(True)
        self.book_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        details_layout.addWidget(self.book_title)

        self.book_author = QLabel("")
        self.book_author.setWordWrap(True)
        details_layout.addWidget(self.book_author)

        self.book_stats = QLabel("")
        self.book_stats.setWordWrap(True)
        details_layout.addWidget(self.book_stats)

        self.synopsis = QTextBrowser()
        self.synopsis.setMaximumHeight(115)
        self.synopsis.setOpenExternalLinks(False)
        self.synopsis.setPlaceholderText("Sinopse não disponível.")
        details_layout.addWidget(self.synopsis)

        continue_row = QHBoxLayout()
        self.continue_book_button = QPushButton("▶ Continuar leitura")
        self.continue_book_button.clicked.connect(self.continue_selected_book)
        self.first_unread_button = QPushButton("Próximo não lido")
        self.first_unread_button.clicked.connect(self.open_first_unread)
        continue_row.addWidget(self.continue_book_button)
        continue_row.addWidget(self.first_unread_button)
        details_layout.addLayout(continue_row)

        goto_row = QHBoxLayout()
        self.goto_input = QLineEdit()
        self.goto_input.setPlaceholderText("Nº do capítulo")
        self.goto_input.returnPressed.connect(self.goto_chapter)
        self.goto_button = QPushButton("Ir")
        self.goto_button.clicked.connect(self.goto_chapter)
        goto_row.addWidget(self.goto_input, 1)
        goto_row.addWidget(self.goto_button)
        details_layout.addLayout(goto_row)

        layout.addWidget(self.details)

        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar livro ou capítulo…")
        self.search.textChanged.connect(self._apply_filter)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Todos", "all")
        self.filter_combo.addItem("Não lidos", "unread")
        self.filter_combo.addItem("Em andamento", "progress")
        self.filter_combo.addItem("Concluídos", "completed")
        self.filter_combo.currentIndexChanged.connect(
            lambda *_: self._apply_filter(self.search.text())
        )

        controls.addWidget(self.search, 1)
        controls.addWidget(self.filter_combo)
        layout.addLayout(controls)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(18)
        self.tree.itemDoubleClicked.connect(self._open_item)
        self.tree.currentItemChanged.connect(self._selection_changed)
        layout.addWidget(self.tree, 1)

        buttons = QHBoxLayout()

        self.sync_button = QPushButton("↻ Atualizar índice")
        self.sync_button.clicked.connect(self.sync_selected)

        self.favorite_button = QPushButton("★ Favoritar livro")
        self.favorite_button.clicked.connect(self.toggle_selected_favorite)

        self.remove_button = QPushButton("Remover")
        self.remove_button.clicked.connect(self.remove_selected)

        buttons.addWidget(self.sync_button)
        buttons.addWidget(self.favorite_button)
        buttons.addWidget(self.remove_button)
        layout.addLayout(buttons)

        self.refresh()

    def set_current_url(self, url: str) -> None:
        self._current_url = url or ""
        self.refresh()

    def focus_book(self, book_id: int) -> None:
        self._selected_book_id_value = int(book_id)
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.data(0, self.ID_ROLE) == int(book_id):
                item.setExpanded(True)
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                self._show_book_details(int(book_id))
                return

    def refresh(self) -> None:
        selected = self._selection_identity()
        selected_book = self._selected_book_id_value

        self.tree.clear()
        for book in self.database.books():
            book_item = self._add_book(book)
            index = self.database.known_index(book.id)
            if index:
                for chapter in index:
                    self._add_index_chapter(book_item, chapter)
            else:
                for chapter in self.database.chapters_for_book(book.id):
                    self._add_history_chapter(book_item, chapter)

        self._restore_selection(selected)
        if self.tree.currentItem() is None and selected_book is not None:
            self.focus_book(selected_book)
        self._apply_filter(self.search.text())
        self._update_buttons()

    def _add_book(self, book: BookEntry) -> QTreeWidgetItem:
        star = "★ " if book.favorite else ""
        chapter_word = "capítulo" if book.chapter_count == 1 else "capítulos"
        text = (
            f"{star}{book.display_title}\n"
            f"{book.last_chapter_title} · {book.last_progress}% · "
            f"{book.chapter_count} {chapter_word}"
        )
        item = QTreeWidgetItem([text])
        item.setData(0, self.KIND_ROLE, "book")
        item.setData(0, self.ID_ROLE, book.id)
        item.setData(0, self.URL_ROLE, book.last_chapter_url or book.book_url)
        self.tree.addTopLevelItem(item)
        return item

    def _add_index_chapter(
        self,
        parent: QTreeWidgetItem,
        chapter: BookIndexEntry,
    ) -> None:
        if chapter.url == self._current_url:
            marker = "▶ "
        elif chapter.progress >= 95:
            marker = "✓ "
        elif chapter.read:
            marker = "• "
        else:
            marker = "  "

        lock = " 🔒" if chapter.accessible is False else ""
        progress = f" · {chapter.progress}%" if chapter.read else ""
        item = QTreeWidgetItem([f"{marker}{chapter.title}{progress}{lock}"])
        item.setData(0, self.KIND_ROLE, "chapter")
        item.setData(0, self.ID_ROLE, chapter.book_id)
        item.setData(0, self.URL_ROLE, chapter.url)
        item.setData(0, self.READ_ROLE, chapter.read)
        item.setData(0, self.PROGRESS_ROLE, chapter.progress)
        item.setToolTip(0, chapter.url)

        if chapter.url == self._current_url:
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            parent.setExpanded(True)

        parent.addChild(item)

    def _add_history_chapter(
        self,
        parent: QTreeWidgetItem,
        chapter: LibraryEntry,
    ) -> None:
        if chapter.url == self._current_url:
            marker = "▶ "
        elif chapter.progress >= 95:
            marker = "✓ "
        else:
            marker = "• "
        item = QTreeWidgetItem(
            [f"{marker}{chapter.display_chapter} · {chapter.progress}%"]
        )
        item.setData(0, self.KIND_ROLE, "chapter")
        item.setData(0, self.ID_ROLE, chapter.book_id)
        item.setData(0, self.URL_ROLE, chapter.url)
        item.setData(0, self.READ_ROLE, True)
        item.setData(0, self.PROGRESS_ROLE, chapter.progress)
        parent.addChild(item)

    def _selection_changed(self, current, previous) -> None:
        book_id = self._selected_book_id()
        if book_id is not None:
            self._selected_book_id_value = book_id
            self._show_book_details(book_id)
        self._update_buttons()

    def _show_book_details(self, book_id: int) -> None:
        book = self.database.get_book(book_id)
        if not book:
            return

        stats = self.database.book_stats(book_id)
        self.book_title.setText(book.display_title)
        self.book_author.setText(
            f"Autor: {book.author}" if book.author else "Autor não identificado"
        )
        self.book_stats.setText(
            f"{stats.read}/{stats.total} lidos · "
            f"{stats.completed} concluídos · "
            f"{stats.in_progress} em andamento · "
            f"{stats.unread} não lidos"
        )
        self.synopsis.setPlainText(book.synopsis or "Sinopse não disponível.")
        self._load_ascii_cover(book.cover_url)

        self.continue_book_button.setEnabled(
            bool(self.database.continue_url_for_book(book_id))
        )
        self.first_unread_button.setEnabled(
            bool(self.database.first_unread_url(book_id))
        )
        self.goto_input.setEnabled(stats.total > 0)
        self.goto_button.setEnabled(stats.total > 0)

    def set_ascii_options(self, enabled: bool, width: int, height: int) -> None:
        self._ascii_enabled = bool(enabled)
        self._ascii_width = max(20, min(int(width), 80))
        self._ascii_height = max(8, min(int(height), 40))
        self._cover_url = ""
        if not self._ascii_enabled:
            self.cover_ascii.clear()
            self.cover_ascii.hide()
        elif self._selected_book_id_value is not None:
            self._show_book_details(self._selected_book_id_value)

    def _load_ascii_cover(self, cover_url: str) -> None:
        cover_url = cover_url or ""

        if not self._ascii_enabled or not cover_url:
            self._cover_url = ""
            self.cover_ascii.clear()
            self.cover_ascii.hide()
            return

        if cover_url == self._cover_url and self.cover_ascii.toPlainText().strip():
            return

        self._cover_url = cover_url
        self.cover_ascii.setPlainText("Gerando capa ASCII…")
        self.cover_ascii.show()

        worker = AsciiCoverWorker(
            cover_url,
            width=self._ascii_width,
            height=self._ascii_height,
            parent=self,
        )
        worker.rendered.connect(self._ascii_cover_ready)
        worker.failed.connect(self._ascii_cover_failed)
        worker.finished.connect(worker.deleteLater)
        self._cover_worker = worker
        worker.start()

    def _ascii_cover_ready(self, url: str, text: str, backend: str) -> None:
        if url != self._cover_url:
            return
        self.cover_ascii.setPlainText(text)
        self.cover_ascii.setToolTip(f"Capa ASCII · backend: {backend}")

    def _ascii_cover_failed(self, url: str, message: str) -> None:
        if url != self._cover_url:
            return
        self.cover_ascii.setPlainText("Capa ASCII indisponível.")
        self.cover_ascii.setToolTip(message)

    def continue_selected_book(self) -> None:
        book_id = self._selected_book_id()
        if book_id is None:
            return
        url = self.database.continue_url_for_book(book_id)
        if url:
            self.open_requested.emit(url)

    def open_first_unread(self) -> None:
        book_id = self._selected_book_id()
        if book_id is None:
            return
        url = self.database.first_unread_url(book_id)
        if url:
            self.open_requested.emit(url)

    def goto_chapter(self) -> None:
        book_id = self._selected_book_id()
        if book_id is None:
            return
        text = self.goto_input.text().strip()
        try:
            number = int(text)
        except ValueError:
            QMessageBox.information(
                self, "Ir para capítulo", "Digite um número de capítulo válido."
            )
            return

        url = self.database.chapter_url_by_number(book_id, number)
        if not url:
            QMessageBox.information(
                self,
                "Ir para capítulo",
                f"O capítulo {number} não está no índice conhecido.",
            )
            return
        self.open_requested.emit(url)

    def _selection_identity(self):
        item = self.tree.currentItem()
        if not item:
            return None
        return (
            item.data(0, self.KIND_ROLE),
            item.data(0, self.ID_ROLE),
            item.data(0, self.URL_ROLE),
        )

    def _restore_selection(self, identity) -> None:
        if not identity:
            return
        kind, item_id, url = identity
        for i in range(self.tree.topLevelItemCount()):
            book_item = self.tree.topLevelItem(i)
            if kind == "book" and book_item.data(0, self.ID_ROLE) == item_id:
                self.tree.setCurrentItem(book_item)
                return
            for j in range(book_item.childCount()):
                child = book_item.child(j)
                if kind == "chapter" and child.data(0, self.URL_ROLE) == url:
                    book_item.setExpanded(True)
                    self.tree.setCurrentItem(child)
                    return

    def _open_item(self, item: QTreeWidgetItem) -> None:
        url = item.data(0, self.URL_ROLE)
        if url:
            self.open_requested.emit(str(url))

    def _selected_book_id(self) -> int | None:
        item = self.tree.currentItem()
        if item:
            if item.data(0, self.KIND_ROLE) == "book":
                value = item.data(0, self.ID_ROLE)
            else:
                parent = item.parent()
                value = parent.data(0, self.ID_ROLE) if parent else None
            return int(value) if value is not None else None
        return self._selected_book_id_value

    def selected_url(self) -> str | None:
        item = self.tree.currentItem()
        if not item:
            return None
        url = item.data(0, self.URL_ROLE)
        return str(url) if url else None

    def sync_selected(self) -> None:
        book_id = self._selected_book_id()
        if book_id is None:
            return
        book = self.database.get_book(book_id)
        if book and book.book_url:
            self.sync_requested.emit(book.book_url)

    def toggle_selected_favorite(self) -> None:
        book_id = self._selected_book_id()
        if book_id is None:
            return
        self.database.toggle_book_favorite(book_id)
        self.refresh()
        self.changed.emit()

    def remove_selected(self) -> None:
        item = self.tree.currentItem()
        if not item:
            return

        kind = item.data(0, self.KIND_ROLE)
        if kind == "book":
            book_id = int(item.data(0, self.ID_ROLE))
            book = self.database.get_book(book_id)
            title = book.display_title if book else "este livro"
            answer = QMessageBox.question(
                self,
                "Remover livro",
                f"Remover “{title}”, seu índice e histórico da biblioteca?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.database.remove_book(book_id)
            self._selected_book_id_value = None
        else:
            url = item.data(0, self.URL_ROLE)
            if url:
                self.database.remove(str(url))

        self.refresh()
        self.changed.emit()

    def _chapter_matches_filter(self, child: QTreeWidgetItem) -> bool:
        mode = self.filter_combo.currentData()
        if mode == "all":
            return True

        read = bool(child.data(0, self.READ_ROLE))
        progress = int(child.data(0, self.PROGRESS_ROLE) or 0)

        if mode == "unread":
            return not read
        if mode == "progress":
            return read and progress < 95
        if mode == "completed":
            return read and progress >= 95
        return True

    def _apply_filter(self, text: str) -> None:
        query = text.strip().casefold()

        for i in range(self.tree.topLevelItemCount()):
            book_item = self.tree.topLevelItem(i)
            book_match = query in book_item.text(0).casefold()

            child_match = False
            for j in range(book_item.childCount()):
                child = book_item.child(j)
                text_match = not query or query in child.text(0).casefold()
                state_match = self._chapter_matches_filter(child)
                match = text_match and state_match
                child.setHidden(not match)
                child_match = child_match or match

            # Keep the book visible when its own title matches in "all" mode,
            # otherwise a state filter requires at least one matching chapter.
            state_mode = self.filter_combo.currentData()
            visible = child_match or (book_match and state_mode == "all")
            if not query and state_mode == "all":
                visible = True

            book_item.setHidden(not visible)
            if (query or state_mode != "all") and visible:
                book_item.setExpanded(True)

    def _update_buttons(self) -> None:
        book_id = self._selected_book_id()
        enabled = book_id is not None
        self.favorite_button.setEnabled(enabled)
        self.remove_button.setEnabled(self.tree.currentItem() is not None)

        book = self.database.get_book(book_id) if book_id is not None else None
        self.sync_button.setEnabled(bool(book and book.book_url))
        self.favorite_button.setText(
            "☆ Desfavoritar livro"
            if book and book.favorite
            else "★ Favoritar livro"
        )
