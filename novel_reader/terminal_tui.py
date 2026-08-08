from __future__ import annotations

import curses
from dataclasses import dataclass
import textwrap

from novel_reader.database import LibraryDatabase
from novel_reader.services.chapter_cache import ChapterCache
from novel_reader.terminal_config import COVER_MODES, TerminalConfigStore, TerminalUiConfig
from novel_reader.terminal_cover import CoverRender, TerminalCoverRenderer
from novel_reader.error_handling import classify_exception, log_exception
from novel_reader.app_config import AppConfigStore
from novel_reader.services.cache_manager import CacheManager, CacheStats
from novel_reader.services.sync_policy import decide_refresh, relative_sync_text
from novel_reader.terminal_reader import (
    TerminalReaderSettings,
    page_index_from_progress,
    paginate_chapter,
    progress_from_page,
)


@dataclass(slots=True)
class TuiState:
    selected: int = 0
    offset: int = 0
    query: str = ""
    message: str = ""


def run_book_tui_inplace(
    stdscr,
    *,
    runtime,
    book_url: str,
    database: LibraryDatabase,
    reader_settings: TerminalReaderSettings,
) -> int:
    """Run the book UI inside an already active curses session.

    This is the path used by Home/Ranking/Library. It deliberately does not
    call curses.wrapper(), endwin(), def_prog_mode() or reset_prog_mode().
    """
    _setup_terminal(stdscr)
    try:
        curses.flushinp()
    except curses.error:
        pass

    _draw_loading(
        stdscr,
        "NOVEL READER",
        "Carregando obra…",
        "QtWebEngine está processando a página em segundo plano.",
    )

    try:
        book = runtime.load_book(book_url)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        _draw_error(
            stdscr,
            "Não foi possível carregar a obra",
            str(exc),
        )
        stdscr.getch()
        return 1

    app = NovelReaderTui(
        runtime=runtime,
        book=book,
        database=database,
        reader_settings=reader_settings,
    )
    result = app._main(stdscr)

    # Throw away key sequences that may have been buffered while the nested
    # view was closing (notably ESC [ A/B from arrow keys).
    try:
        curses.flushinp()
    except curses.error:
        pass
    stdscr.keypad(True)
    stdscr.erase()
    stdscr.refresh()
    return result


def run_book_tui(
    *,
    runtime,
    book_url: str,
    database: LibraryDatabase,
    reader_settings: TerminalReaderSettings,
) -> int:
    """Standalone entry point: owns the terminal with a single wrapper."""

    def wrapped(stdscr):
        return run_book_tui_inplace(
            stdscr,
            runtime=runtime,
            book_url=book_url,
            database=database,
            reader_settings=reader_settings,
        )

    return curses.wrapper(wrapped)


def _setup_terminal(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    try:
        curses.use_default_colors()
    except curses.error:
        pass

    if curses.has_colors():
        try:
            curses.start_color()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_RED, -1)
            curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)
            curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_CYAN)
        except curses.error:
            pass


def _color(pair: int) -> int:
    if not curses.has_colors():
        return 0
    try:
        return curses.color_pair(pair)
    except curses.error:
        return 0


def _safe_add(win, y, x, text, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    try:
        win.addnstr(y, x, str(text), max(0, w - x - 1), attr)
    except curses.error:
        pass


def _hline(win, y, x, width, char="─", attr=0):
    if width <= 0:
        return
    _safe_add(win, y, x, char * width, attr)


def _box_title(win, y, x, width, title, attr=0):
    if width < 4:
        return
    _safe_add(win, y, x, "┌" + "─" * (width - 2) + "┐", attr)
    shown = f" {title} "
    _safe_add(win, y, x + 2, shown[: max(0, width - 4)], attr)


def _draw_loading(stdscr, title: str, message: str, detail: str = ""):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    box_w = min(max(44, len(detail) + 6), max(20, w - 4))
    x = max(1, (w - box_w) // 2)
    y = max(1, h // 2 - 4)

    _box_title(stdscr, y, x, box_w, title, curses.A_BOLD | _color(1))
    _safe_add(stdscr, y + 2, x + 3, message, curses.A_BOLD | _color(3))
    if detail:
        for row, line in enumerate(textwrap.wrap(detail, max(20, box_w - 6))):
            _safe_add(stdscr, y + 4 + row, x + 3, line)
    _safe_add(
        stdscr,
        min(h - 2, y + 7),
        x + 3,
        "Ctrl+C cancela e devolve o terminal.",
        curses.A_DIM,
    )
    stdscr.refresh()


def _draw_error(stdscr, title: str, message: str):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    _safe_add(stdscr, 1, 2, f"✕ {title}", curses.A_BOLD | _color(4))
    row = 3
    for part in textwrap.wrap(str(message), max(20, w - 5)):
        _safe_add(stdscr, row, 2, part)
        row += 1
    _safe_add(stdscr, min(h - 2, row + 1), 2, "Pressione qualquer tecla para sair.")
    stdscr.refresh()


class NovelReaderTui:
    def __init__(
        self,
        *,
        runtime,
        book,
        database: LibraryDatabase,
        reader_settings: TerminalReaderSettings,
    ):
        self.runtime = runtime
        self.book = book
        self.database = database
        self.reader_settings = reader_settings
        self.cache = ChapterCache()
        self.book_id = self.database.save_book_index(book)
        self.state = TuiState()
        self.config_store = TerminalConfigStore()
        self.ui_config = self.config_store.load()
        self.app_config_store = AppConfigStore()
        self.app_config = self.app_config_store.load()
        self.cache_manager = CacheManager(self.cache.cache_root)
        self._offline_filter = False
        self.cover_renderer = TerminalCoverRenderer()
        self.cover: CoverRender = CoverRender(mode="off", label="sem capa")
        self._kitty_drawn = False
        self._prepare_cover()

    def _prepare_cover(self) -> None:
        try:
            self.cover = self.cover_renderer.prepare(
                self.book.cover_url,
                self.ui_config.cover_mode,
                ascii_width=34,
                ascii_height=17,
            )
        except Exception:
            self.cover = CoverRender(mode="off", label="capa indisponível")
        self._kitty_drawn = False


    def run(self) -> int:
        return curses.wrapper(self._main)

    def _entries(self):
        entries = self.database.known_index(self.book_id)

        if self._offline_filter:
            cached_urls = self.cache.cached_urls()
            entries = [
                item
                for item in entries
                if item.url in cached_urls
            ]

        query = self.state.query.strip().casefold()
        if not query:
            return entries
        return [
            item
            for item in entries
            if query in item.title.casefold()
            or (
                item.position is not None
                and query in str(item.position)
            )
        ]

    @staticmethod
    def _status(item) -> tuple[str, int]:
        if item.progress >= 95:
            return "✓ 100%", 2
        if item.read:
            return f"◐ {item.progress:>3}%", 3
        if item.accessible is False:
            return "🔒 lock", 4
        return "· novo", 0

    def _book_stats(self):
        entries = self.database.known_index(self.book_id)
        read = sum(1 for item in entries if item.read)
        done = sum(1 for item in entries if item.progress >= 95)
        current = sum(1 for item in entries if item.read and item.progress < 95)
        return len(entries), read, done, current

    def _main(self, stdscr) -> int:
        _setup_terminal(stdscr)

        while True:
            entries = self._entries()
            self._normalize(entries, stdscr)
            self._draw_index(stdscr, entries)
            key = stdscr.getch()

            if key in (ord("q"), ord("Q")):
                self._clear_graphics(stdscr)
                self.cover_renderer.close()
                return 0
            if key in (ord("i"), ord("I")):
                self._cover_mode_popup(stdscr)
                continue
            if key in (ord("?"), curses.KEY_F2):
                self._clear_graphics(stdscr)
                self._kitty_diagnostics_popup(stdscr)
                continue
            if key in (ord("L"), ord("l")):
                added = self.database.toggle_book_library(self.book_id)
                self.state.message = "Adicionado à Library." if added else "Removido da Library."
                continue
            if key in (ord("F"), ord("f")):
                value = self.database.toggle_book_favorite(self.book_id)
                self.state.message = "Favoritado ★." if value else "Removido dos favoritos."
                continue
            if key in (ord("O"), ord("o")):
                self._offline_filter = not self._offline_filter
                self.state.selected = 0
                self.state.offset = 0
                self.state.message = (
                    "Filtro Offline ativado."
                    if self._offline_filter
                    else "Filtro Offline desativado."
                )
                continue
            if key in (ord("X"), ord("x")):
                self._cache_manager_popup(stdscr)
                continue
            if key in (ord("A"), ord("a")):
                self._prefetch_next(stdscr, entries)
                continue
            if key in (curses.KEY_UP, ord("k"), ord("K")):
                self.state.selected = max(0, self.state.selected - 1)
                continue
            if key in (curses.KEY_DOWN, ord("j"), ord("J")):
                self.state.selected = min(max(0, len(entries) - 1), self.state.selected + 1)
                continue
            if key in (curses.KEY_PPAGE,):
                self.state.selected = max(0, self.state.selected - 10)
                continue
            if key in (curses.KEY_NPAGE,):
                self.state.selected = min(max(0, len(entries) - 1), self.state.selected + 10)
                continue
            if key == curses.KEY_HOME:
                self.state.selected = 0
                continue
            if key == curses.KEY_END:
                self.state.selected = max(0, len(entries) - 1)
                continue
            if key in (ord("/"), ord("s"), ord("S")):
                self._search_popup(stdscr)
                continue
            if key == 27:
                if self.state.query:
                    self.state.query = ""
                    self.state.selected = 0
                continue
            if key in (ord("c"), ord("C")):
                url = self.database.continue_url_for_book(self.book_id)
                if url:
                    self._open_reader(stdscr, url)
                continue
            if key in (ord("u"), ord("U")):
                url = self.database.first_unread_url(self.book_id)
                if url:
                    self._open_reader(stdscr, url)
                continue
            if key in (ord("r"), ord("R")):
                self._refresh_index(stdscr, force=False)
                continue
            if key == curses.KEY_F5:
                self._refresh_index(stdscr, force=True)
                continue
            if key in (10, 13, curses.KEY_ENTER):
                if entries:
                    self._open_reader(stdscr, entries[self.state.selected].url)
                continue

    def _layout(self, stdscr):
        h, w = stdscr.getmaxyx()

        # On small terminals we fall back to a one-column interface.
        side_w = 0
        if w >= 96:
            side_w = min(40, max(32, w // 3))

        header_h = 4
        footer_h = 3
        body_y = header_h
        body_h = max(4, h - header_h - footer_h)

        list_x = 1
        list_w = w - 2 if side_w == 0 else w - side_w - 3
        side_x = list_x + list_w + 1

        return {
            "h": h,
            "w": w,
            "header_h": header_h,
            "footer_h": footer_h,
            "body_y": body_y,
            "body_h": body_h,
            "list_x": list_x,
            "list_w": list_w,
            "side_x": side_x,
            "side_w": side_w,
        }

    def _normalize(self, entries, stdscr) -> None:
        layout = self._layout(stdscr)
        visible = max(3, layout["body_h"] - 3)

        if not entries:
            self.state.selected = 0
            self.state.offset = 0
            return

        self.state.selected = max(0, min(self.state.selected, len(entries) - 1))
        if self.state.selected < self.state.offset:
            self.state.offset = self.state.selected
        elif self.state.selected >= self.state.offset + visible:
            self.state.offset = self.state.selected - visible + 1

        self.state.offset = min(
            self.state.offset,
            max(0, len(entries) - visible),
        )

    def _draw_keybar(
        self,
        win,
        y: int,
        items,
        *,
        start_x: int = 2,
    ) -> None:
        """Draw compact keycaps: [K] Ação  [Enter] Ação."""
        _, width = win.getmaxyx()
        x = start_x

        for key_label, action in items:
            cap = f" {key_label} "
            needed = len(cap) + 1 + len(action) + 2
            if x + needed >= width - 1:
                break

            # Keycap
            _safe_add(
                win,
                y,
                x,
                cap,
                curses.A_BOLD | curses.A_REVERSE | _color(1),
            )
            x += len(cap)

            # Action
            _safe_add(
                win,
                y,
                x,
                f" {action}",
                curses.A_DIM,
            )
            x += 1 + len(action)

            # Separator
            if x + 2 < width - 1:
                _safe_add(win, y, x, "  ", curses.A_DIM)
                x += 2

    def _draw_index(self, stdscr, entries) -> None:
        # Sync metadata is displayed in the header/status area below.
        stdscr.erase()
        L = self._layout(stdscr)
        last_sync_label = relative_sync_text(
            self.database.book_index_updated_at(self.book_id)
        )
        h, w = L["h"], L["w"]

        # Header
        _safe_add(
            stdscr,
            0,
            1,
            " NOVEL READER ",
            curses.A_BOLD | _color(6),
        )
        _safe_add(
            stdscr,
            0,
            16,
            self.book.title,
            curses.A_BOLD | _color(1),
        )
        _safe_add(
            stdscr,
            1,
            2,
            f"Autor: {self.book.author or '—'}",
            curses.A_DIM,
        )

        total, read, done, current = self._book_stats()
        stats = (
            f"{total} capítulos  •  {read} lidos  •  {done} concluídos  •  "
            f"{current} em andamento  •  Última sync: {last_sync_label}"
        )
        _safe_add(stdscr, 2, 2, stats)

        if self.state.query:
            _safe_add(
                stdscr,
                3,
                2,
                f"⌕ Busca: {self.state.query}  ({len(entries)} resultado(s))",
                curses.A_BOLD | _color(3),
            )
        else:
            _hline(stdscr, 3, 1, max(0, w - 2), "─", curses.A_DIM)

        # Main list panel
        _box_title(
            stdscr,
            L["body_y"],
            L["list_x"],
            L["list_w"],
            "ÍNDICE",
            curses.A_BOLD,
        )

        visible = max(3, L["body_h"] - 3)
        subset = entries[self.state.offset:self.state.offset + visible]

        for row_offset, item in enumerate(subset, start=1):
            y = L["body_y"] + row_offset
            absolute = self.state.offset + row_offset - 1
            selected = absolute == self.state.selected
            status, status_color = self._status(item)
            number = f"{item.position:>4}" if item.position is not None else "   -"

            prefix = "▶" if selected else " "
            cache_mark = "◆" if self.cache.has(item.url) else " "
            title_space = max(10, L["list_w"] - 23)
            title = item.title[:title_space]
            line = f"{prefix} {cache_mark} {number}  {title:<{title_space}} {status:>7}"

            if selected:
                attr = curses.A_BOLD | curses.A_REVERSE
                if curses.has_colors():
                    attr |= _color(5)
            else:
                attr = _color(status_color)

            _safe_add(stdscr, y, L["list_x"] + 1, line, attr)

        # Right info/cover panel
        if L["side_w"]:
            self._draw_side_panel(stdscr, L, entries)

        # Footer/help
        footer_y = h - 3
        _hline(stdscr, footer_y, 1, max(0, w - 2), "─", curses.A_DIM)

        self._draw_keybar(
            stdscr,
            footer_y + 1,
            [
                ("↑↓", "Mover"),
                ("Enter", "Abrir"),
                ("/", "Buscar"),
                ("I", "Capa"),
                ("?", "Kitty"),
                ("L", "Library"),
                ("F", "Favorito"),
                ("A", "Offline"),
                ("O", "Filtro offline"),
                ("X", "Cache"),
                ("C", "Continuar"),
                ("U", "Próximo"),
                ("R", "Atualizar"),
                ("F5", "Forçar sync"),
                ("Q", "Sair"),
            ],
        )

        if entries:
            selected = entries[self.state.selected]
            pos = selected.position if selected.position is not None else "—"
            footer = f"Capítulo {pos}  •  {self.state.selected + 1}/{len(entries)}"
            if self.state.query:
                footer += "  •  Esc limpa busca"
            _safe_add(stdscr, footer_y + 2, 2, footer, _color(1))

        if self.state.message:
            _safe_add(
                stdscr,
                footer_y + 2,
                max(2, w // 2),
                self.state.message,
                curses.A_BOLD | _color(3),
            )

        stdscr.refresh()
        self._draw_native_cover(stdscr, L)

    def _draw_side_panel(self, stdscr, L, entries) -> None:
        x = L["side_x"]
        y = L["body_y"]
        width = L["side_w"]
        height = L["body_h"]

        _box_title(
            stdscr,
            y,
            x,
            width,
            "OBRA",
            curses.A_BOLD | _color(1),
        )

        row = y + 1

        # Cover area: either terminal-native kitty image or curses ASCII.
        cover_top = row
        cover_height = min(17, max(5, height - 11))
        cover_width = max(8, width - 4)

        if self.cover.mode == "kitty" and self.cover.image_path:
            # Keep the rectangle text-free; image is placed after curses refresh.
            for blank_row in range(cover_height):
                _safe_add(stdscr, cover_top + blank_row, x + 2, " " * cover_width)
            row += cover_height
            label = "Imagem · kitten icat"
            _safe_add(
                stdscr,
                row,
                x + max(1, (width - len(label)) // 2),
                label,
                curses.A_DIM | _color(1),
            )
            row += 2
        elif self.cover.ascii_text:
            cover_lines = self.cover.ascii_text.splitlines()
            for line in cover_lines[:cover_height]:
                clipped = line[:cover_width]
                left = x + max(1, (width - len(clipped)) // 2)
                _safe_add(stdscr, row, left, clipped, _color(1))
                row += 1
            row += 1
            label = self.cover.label
            _safe_add(
                stdscr,
                row,
                x + max(1, (width - len(label)) // 2),
                label,
                curses.A_DIM,
            )
            row += 2
        else:
            _safe_add(stdscr, row, x + 2, "Capa desativada/indisponível", curses.A_DIM)
            row += 2

        if entries:
            selected = entries[self.state.selected]
            _hline(stdscr, row, x + 1, max(0, width - 2), "─", curses.A_DIM)
            row += 1

            _safe_add(
                stdscr,
                row,
                x + 2,
                "SELECIONADO",
                curses.A_BOLD | _color(3),
            )
            row += 1

            title_width = max(10, width - 4)
            for line in textwrap.wrap(selected.title, title_width)[:3]:
                _safe_add(stdscr, row, x + 2, line, curses.A_BOLD)
                row += 1

            status, status_color = self._status(selected)
            _safe_add(
                stdscr,
                row,
                x + 2,
                f"Status: {status}",
                _color(status_color),
            )
            row += 1

            if selected.position is not None:
                _safe_add(
                    stdscr,
                    row,
                    x + 2,
                    f"Número: {selected.position}",
                )

    def _draw_native_cover(self, stdscr, L) -> None:
        if (
            self.cover.mode != "kitty"
            or not self.cover.image_path
            or not L["side_w"]
        ):
            if self._kitty_drawn:
                self._clear_graphics(stdscr)
            return

        # The inner panel starts one cell under its top border.
        left = L["side_x"] + 2
        top = L["body_y"] + 1
        width = max(8, L["side_w"] - 4)
        height = min(17, max(5, L["body_h"] - 11))

        ok = self.cover_renderer.draw_kitty(
            image_path=self.cover.image_path,
            screen_cols=L["w"],
            screen_rows=L["h"],
            left=left,
            top=top,
            width=width,
            height=height,
        )
        self._kitty_drawn = bool(ok)

    def _clear_graphics(self, stdscr) -> None:
        if not self._kitty_drawn:
            return
        h, w = stdscr.getmaxyx()
        self.cover_renderer.clear_kitty(
            screen_cols=w,
            screen_rows=h,
        )
        self._kitty_drawn = False

    def _kitty_diagnostics_popup(self, stdscr) -> None:
        h, w = stdscr.getmaxyx()
        diag = self.cover_renderer.diagnostics(
            screen_cols=w,
            screen_rows=h,
        )

        popup_w = min(86, max(48, w - 8))
        popup_h = min(16, max(11, h - 6))
        win = curses.newwin(
            popup_h,
            popup_w,
            max(0, (h - popup_h)//2),
            max(0, (w - popup_w)//2),
        )
        win.keypad(True)

        values = [
            f"kitten: {diag.kitten_path or 'não encontrado'}",
            f"terminal: {diag.terminal_name or 'desconhecido'}",
            f"KITTY_WINDOW_ID: {diag.kitty_window_id or 'ausente'}",
            f"células: {diag.cols}x{diag.rows}",
            f"pixels reais/estimados: {diag.pixel_width}x{diag.pixel_height}",
            f"tmux: {'sim' if diag.tmux else 'não'}",
            f"screen: {'sim' if diag.screen else 'não'}",
            f"estado: {diag.reason}",
        ]

        win.erase()
        win.box()
        _safe_add(
            win,
            0,
            2,
            " DIAGNÓSTICO KITTEN ICAT ",
            curses.A_BOLD | _color(1),
        )
        row = 2
        for text in values:
            for line in textwrap.wrap(text, max(20, popup_w - 6)):
                if row >= popup_h - 2:
                    break
                _safe_add(win, row, 3, line)
                row += 1
        _safe_add(win, popup_h - 1, 2, " qualquer tecla fecha · ? = diagnóstico ", curses.A_DIM)
        win.refresh()
        win.getch()

    def _cover_mode_popup(self, stdscr) -> None:
        self._clear_graphics(stdscr)

        modes = [
            ("auto", "Auto"),
            ("kitty", "Kitten icat"),
            ("chafa", "Chafa ASCII"),
            ("pillow", "Pillow ASCII"),
            ("off", "Desativada"),
        ]
        current = next(
            (i for i, (value, _) in enumerate(modes)
             if value == self.ui_config.cover_mode),
            0,
        )

        h, w = stdscr.getmaxyx()
        popup_w = min(48, max(34, w - 8))
        popup_h = 10
        win = curses.newwin(
            popup_h,
            popup_w,
            max(0, (h - popup_h) // 2),
            max(0, (w - popup_w) // 2),
        )
        win.keypad(True)

        while True:
            win.erase()
            win.box()
            _safe_add(win, 0, 2, " CAPA DO LIVRO ", curses.A_BOLD | _color(1))
            _safe_add(win, 1, 2, "Escolha o backend de renderização:", curses.A_DIM)

            for idx, (_, label) in enumerate(modes):
                marker = "▶" if idx == current else " "
                attr = curses.A_REVERSE | curses.A_BOLD if idx == current else 0
                _safe_add(win, 3 + idx, 3, f"{marker} {label}", attr)

            _safe_add(
                win,
                popup_h - 1,
                2,
                " ↑↓ escolher   Enter salvar   Esc cancelar ",
                curses.A_DIM,
            )
            win.refresh()

            key = win.getch()
            if key in (curses.KEY_UP, ord("k"), ord("K")):
                current = (current - 1) % len(modes)
            elif key in (curses.KEY_DOWN, ord("j")):
                current = (current + 1) % len(modes)
            elif key == 27:
                return
            elif key in (10, 13, curses.KEY_ENTER):
                mode = modes[current][0]
                self.ui_config = TerminalUiConfig(cover_mode=mode)
                self.config_store.save(self.ui_config)
                self._prepare_cover()
                self.state.message = f"Capa: {modes[current][1]}"
                return

    def _prefetch_next(self, stdscr, entries) -> None:
        if not entries:
            return
        if self.app_config.offline_mode:
            self.state.message = "Modo offline ativo: pré-cache pela rede desativado."
            return
        count = max(0, min(int(self.ui_config.prefetch_count), 20))
        if count <= 0:
            self.state.message = "Prefetch está desativado."
            return

        start = self.state.selected + 1
        candidates = [
            item for item in entries[start:]
            if item.accessible is not False
        ][:count]
        if not candidates:
            self.state.message = "Não há próximos capítulos públicos para cache."
            return

        saved = 0
        for idx, item in enumerate(candidates, start=1):
            self.state.message = f"Cache offline {idx}/{len(candidates)}: {item.title}"
            self._draw_index(stdscr, entries)
            if self.cache.has(item.url):
                saved += 1
                continue
            try:
                chapter = self.runtime.load_chapter(item.url)
                self.cache.save(chapter)
                self.cache_manager.enforce_limit(self.app_config.cache_limit_mb)
                saved += 1
            except Exception:
                # Stop at first inaccessible/network failure; never attempt
                # bypasses or alternate endpoints.
                break
        self.state.message = f"{saved}/{len(candidates)} próximo(s) capítulo(s) em cache."

    def _cache_manager_popup(self, stdscr) -> None:
        options = [
            "Atualizar estatísticas",
            "Limpar capítulos",
            "Limpar capas",
            "Limpar tudo",
            "Alternar modo offline",
            "Voltar",
        ]
        selected = 0
        message = ""

        while True:
            stats = self.cache_manager.stats()
            h, w = stdscr.getmaxyx()
            popup_w = min(72, max(48, w - 10))
            popup_h = min(18, max(14, h - 6))
            win = curses.newwin(
                popup_h,
                popup_w,
                max(0, (h-popup_h)//2),
                max(0, (w-popup_w)//2),
            )
            win.keypad(True)
            win.erase()
            win.box()
            _safe_add(win, 0, 2, " GERENCIADOR DE CACHE ", curses.A_BOLD | _color(1))

            _safe_add(
                win, 2, 3,
                f"Total: {CacheStats.human_size(stats.total_bytes)} / "
                f"{self.app_config.cache_limit_mb} MB",
                curses.A_BOLD,
            )
            _safe_add(
                win, 3, 3,
                f"Capítulos: {CacheStats.human_size(stats.chapters_bytes)}",
            )
            _safe_add(
                win, 4, 3,
                f"Capas: {CacheStats.human_size(stats.covers_bytes)}",
            )
            _safe_add(
                win, 5, 3,
                f"Arquivos: {stats.files}",
            )
            _safe_add(
                win, 6, 3,
                f"Modo offline: {'ATIVO' if self.app_config.offline_mode else 'desativado'}",
                _color(3) if self.app_config.offline_mode else curses.A_DIM,
            )

            row = 8
            for index, label in enumerate(options):
                attr = curses.A_REVERSE | curses.A_BOLD if index == selected else 0
                _safe_add(
                    win,
                    row + index,
                    3,
                    f"{'▶' if index == selected else ' '} {label}",
                    attr,
                )

            if message:
                _safe_add(win, popup_h - 2, 3, message[:popup_w-6], curses.A_DIM)
            win.refresh()

            key = win.getch()
            if key in (27, ord("q"), ord("Q")):
                return
            if key in (curses.KEY_UP, ord("k"), ord("K")):
                selected = (selected - 1) % len(options)
                continue
            if key in (curses.KEY_DOWN, ord("j"), ord("J")):
                selected = (selected + 1) % len(options)
                continue
            if key not in (10, 13, curses.KEY_ENTER):
                continue

            action = options[selected]
            if action == "Voltar":
                return
            if action == "Atualizar estatísticas":
                message = "Estatísticas atualizadas."
            elif action == "Limpar capítulos":
                count = self.cache_manager.clear_chapters()
                message = f"{count} arquivo(s) de capítulo removido(s)."
            elif action == "Limpar capas":
                count = self.cache_manager.clear_covers()
                message = f"{count} arquivo(s) de capa removido(s)."
            elif action == "Limpar tudo":
                count = self.cache_manager.clear_all()
                message = f"{count} arquivo(s) removido(s)."
            elif action == "Alternar modo offline":
                self.app_config = self.app_config_store.update(
                    offline_mode=not self.app_config.offline_mode
                )
                message = (
                    "Modo offline ativado."
                    if self.app_config.offline_mode
                    else "Modo offline desativado."
                )

    def _search_popup(self, stdscr) -> None:
        h, w = stdscr.getmaxyx()
        popup_w = max(36, min(72, w - 8))
        popup_h = 7
        y = max(0, (h - popup_h) // 2)
        x = max(0, (w - popup_w) // 2)
        win = curses.newwin(popup_h, popup_w, y, x)
        win.keypad(True)

        query = self.state.query
        curses.curs_set(1)

        while True:
            win.erase()
            win.box()
            _safe_add(
                win,
                0,
                2,
                " SEARCH ",
                curses.A_BOLD | _color(1),
            )
            _safe_add(win, 2, 2, "Título ou número do capítulo:")
            _safe_add(
                win,
                3,
                2,
                query + "▌",
                curses.A_BOLD | _color(3),
            )
            _safe_add(
                win,
                5,
                2,
                "Enter aplicar  •  Backspace apagar  •  Esc limpar/cancelar",
                curses.A_DIM,
            )
            win.refresh()

            key = win.getch()
            if key in (10, 13, curses.KEY_ENTER):
                self.state.query = query.strip()
                self.state.selected = 0
                self.state.offset = 0
                break
            if key == 27:
                self.state.query = ""
                self.state.selected = 0
                self.state.offset = 0
                break
            if key in (curses.KEY_BACKSPACE, 127, 8):
                query = query[:-1]
                continue
            if 32 <= key <= 126:
                query += chr(key)

        curses.curs_set(0)

    def _refresh_index(self, stdscr, force: bool = False) -> None:
        last_sync = self.database.book_index_updated_at(self.book_id)
        decision = decide_refresh(
            last_sync=last_sync,
            ttl_minutes=self.app_config.index_refresh_minutes,
            force=force,
            offline=self.app_config.offline_mode,
        )

        if decision.reason == "offline":
            self.state.message = "Modo offline: atualização do índice desativada."
            return

        if not decision.should_refresh:
            self.state.message = (
                f"Índice ainda recente ({relative_sync_text(last_sync)}). "
                "Use F5 para forçar."
            )
            return

        self.state.message = (
            "Forçando atualização do índice…"
            if force
            else "Atualizando índice…"
        )
        self._draw_index(stdscr, self._entries())

        def status_callback(message: str) -> None:
            if not message:
                return
            self.state.message = message
            self._draw_index(stdscr, self._entries())

        try:
            try:
                self.book = self.runtime.load_book(
                    self.book.url,
                    status_callback=status_callback,
                )
            except TypeError:
                self.book = self.runtime.load_book(self.book.url)

            self.book_id = self.database.save_book_index(self.book)
            self.database.touch_book_index_sync(self.book_id)
            self._prepare_cover()
            self.state.message = (
                f"Índice atualizado agora: "
                f"{len(self.database.known_index(self.book_id))} capítulos."
            )
        except Exception as exc:
            error = log_exception(exc, context="terminal_tui.refresh_index")
            self.state.message = f"{error.title} — log: {error.log_file}"

    def _load_chapter(self, url: str):
        cached = self.cache.load(url)

        if self.app_config.offline_mode:
            if cached is not None:
                self.state.message = "Modo offline: usando cache local."
                return cached
            raise RuntimeError(
                "Modo offline: este capítulo não está em cache."
            )

        try:
            try:
                chapter = self.runtime.load_chapter(
                    url,
                    status_callback=lambda message: setattr(
                        self.state,
                        "message",
                        message or "Capítulo: carregando…",
                    ),
                )
            except TypeError:
                chapter = self.runtime.load_chapter(url)
            self.cache.save(chapter)
            self.cache_manager.enforce_limit(
                self.app_config.cache_limit_mb
            )
            return chapter
        except Exception:
            if cached is not None:
                self.state.message = "Rede indisponível; usando cache local."
                return cached
            raise

    def _open_reader(self, stdscr, url: str) -> None:
        self._clear_graphics(stdscr)
        self.state.message = "Abrindo capítulo…"
        self._draw_index(stdscr, self._entries())

        try:
            chapter = self._load_chapter(url)
        except Exception as exc:
            error = log_exception(exc, context="terminal_tui.open_reader")
            self.state.message = f"{error.title} — veja {error.log_file}"
            return

        old_progress = self.database.progress_for(url)
        self.database.record_chapter(chapter, old_progress)

        title = f"{chapter.display_book_title} — {chapter.display_chapter_title}"
        pages = paginate_chapter(title, chapter.text, self.reader_settings)
        page = page_index_from_progress(old_progress, len(pages))

        while True:
            self._draw_reader(stdscr, pages, page, title)
            key = stdscr.getch()

            if key in (ord("q"), ord("Q"), 27):
                break
            if key in (
                curses.KEY_RIGHT,
                curses.KEY_DOWN,
                curses.KEY_NPAGE,
                ord(" "),
                ord("n"),
                ord("N"),
            ):
                if page < len(pages) - 1:
                    page += 1
                continue
            if key in (
                curses.KEY_LEFT,
                curses.KEY_UP,
                curses.KEY_PPAGE,
                ord("p"),
                ord("P"),
            ):
                if page > 0:
                    page -= 1
                continue
            if key in (ord("g"), ord("G")):
                target = self._goto_page_popup(stdscr, len(pages))
                if target is not None:
                    page = target

        progress = progress_from_page(page, len(pages))
        self.database.save_progress(url, progress)
        self.state.message = (
            f"{chapter.display_chapter_title}: {progress}% salvo."
        )

    def _draw_reader(self, stdscr, pages, page: int, title: str) -> None:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        _safe_add(
            stdscr,
            0,
            1,
            " NOVEL READER ",
            curses.A_BOLD | _color(6),
        )
        _safe_add(
            stdscr,
            0,
            16,
            title,
            curses.A_BOLD | _color(1),
        )
        _hline(stdscr, 1, 1, max(0, w - 2), "─", curses.A_DIM)

        lines = pages[page].splitlines()
        max_lines = max(1, h - 5)

        # Center text column when terminal is wide.
        text_width = min(
            max((len(line) for line in lines), default=40),
            max(20, w - 4),
        )
        left = max(1, (w - text_width) // 2)

        for row, line in enumerate(lines[:max_lines], start=2):
            _safe_add(stdscr, row, left, line)

        _hline(stdscr, h - 3, 1, max(0, w - 2), "─", curses.A_DIM)
        percentage = round(((page + 1) / max(1, len(pages))) * 100)
        _safe_add(
            stdscr,
            h - 2,
            2,
            f"Página {page + 1}/{len(pages)}  •  {percentage}%",
            curses.A_BOLD | _color(2),
        )
        self._draw_keybar(
            stdscr,
            h - 2,
            [
                ("←→", "Página"),
                ("G", "Ir para"),
                ("Q/Esc", "Índice"),
            ],
            start_x=max(24, w // 2),
        )
        stdscr.refresh()

    def _goto_page_popup(self, stdscr, total_pages: int) -> int | None:
        h, w = stdscr.getmaxyx()
        popup_w = min(46, max(30, w - 6))
        win = curses.newwin(6, popup_w, max(0, h // 2 - 3), max(1, (w-popup_w)//2))
        value = ""
        curses.curs_set(1)

        while True:
            win.erase()
            win.box()
            _safe_add(win, 0, 2, " IR PARA PÁGINA ", curses.A_BOLD | _color(1))
            _safe_add(win, 2, 2, f"Página (1-{total_pages}):")
            _safe_add(win, 3, 2, value + "▌", curses.A_BOLD | _color(3))
            _safe_add(win, 4, 2, "Enter confirmar  •  Esc cancelar", curses.A_DIM)
            win.refresh()

            key = win.getch()
            if key == 27:
                curses.curs_set(0)
                return None
            if key in (10, 13, curses.KEY_ENTER):
                try:
                    target = int(value) - 1
                except ValueError:
                    target = -1
                curses.curs_set(0)
                if 0 <= target < total_pages:
                    return target
                return None
            if key in (curses.KEY_BACKSPACE, 127, 8):
                value = value[:-1]
            elif ord("0") <= key <= ord("9"):
                value += chr(key)
