from __future__ import annotations

import curses
from dataclasses import dataclass
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from novel_reader.database import LibraryDatabase
from novel_reader.services.webnovel_ranking import (
    RANKING_PERIODS,
    ranking_url,
)
from novel_reader.terminal_reader import TerminalReaderSettings
from novel_reader.terminal_config import TerminalConfigStore
from novel_reader.terminal_cover import CoverRender, TerminalCoverRenderer
from novel_reader.services.chapter_cache import ChapterCache
from novel_reader.error_handling import classify_exception, log_exception
from novel_reader.app_config import AppConfigStore
from novel_reader.services.cache_manager import CacheManager, CacheStats
from novel_reader.services.search_service import SearchHistory, SearchResult, fuzzy_match, fuzzy_score
from novel_reader.terminal_tui import run_book_tui_inplace


@dataclass(slots=True)
class StartupState:
    selected: int = 0
    message: str = ""


def run_startup_tui(*, runtime, database: LibraryDatabase, reader_settings: TerminalReaderSettings) -> int:
    def wrapped(stdscr):
        _setup(stdscr)
        return StartupTui(
            stdscr=stdscr,
            runtime=runtime,
            database=database,
            reader_settings=reader_settings,
        ).run()

    return curses.wrapper(wrapped)


def _setup(stdscr):
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
            curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN)
        except curses.error:
            pass


def _color(n):
    try:
        return curses.color_pair(n) if curses.has_colors() else 0
    except curses.error:
        return 0


def _add(win, y, x, text, attr=0):
    h, w = win.getmaxyx()
    if not (0 <= y < h and 0 <= x < w):
        return
    try:
        win.addnstr(y, x, str(text), max(0, w - x - 1), attr)
    except curses.error:
        pass


class StartupTui:
    OPTIONS = (
        ("link", "Abrir por link", "Cole a URL de um livro do WebNovel."),
        ("ranking", "Explorar Fan-Fic Ranking", "Navegue pelo Power Ranking do WebNovel."),
        ("library", "Minha Library", "Lidos, progresso e favoritos em um só lugar."),
        ("search", "Busca unificada", "Pesquise Library, ranking ou cole uma URL."),
        ("continue", "Continuar última leitura", "Volte à obra mais recente da biblioteca."),
        ("quit", "Sair", "Fechar o Novel Reader."),
    )

    def __init__(self, *, stdscr, runtime, database, reader_settings):
        self.stdscr = stdscr
        self.runtime = runtime
        self.database = database
        self.reader_settings = reader_settings
        self.state = StartupState()

        self.config_store = TerminalConfigStore()
        self.ui_config = self.config_store.load()
        self.app_config_store = AppConfigStore()
        self.app_config = self.app_config_store.load()
        self.cover_renderer = TerminalCoverRenderer()
        self._chapter_cache = ChapterCache()
        self.cache_manager = CacheManager(self._chapter_cache.cache_root)
        self._ranking_cover_cache: dict[str, CoverRender] = {}
        self._ranking_native_drawn = False
        self._ranking_native_key = ""
        self._ranking_cache: dict[str, list] = {}
        self.search_history = SearchHistory()

    def run(self) -> int:
        while True:
            self._draw_home()
            key = self.stdscr.getch()

            if key in (ord("q"), ord("Q"), 27):
                self._clear_ranking_native()
                self.cover_renderer.close()
                return 0
            if key in (curses.KEY_UP, ord("k"), ord("K")):
                self.state.selected = (self.state.selected - 1) % len(self.OPTIONS)
            elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
                self.state.selected = (self.state.selected + 1) % len(self.OPTIONS)
            elif key in (10, 13, curses.KEY_ENTER):
                action = self.OPTIONS[self.state.selected][0]
                result = self._activate(action)
                if result == "quit":
                    return 0

    def _draw_home(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        _add(self.stdscr, 1, 3, "NOVEL READER", curses.A_BOLD | _color(1))
        _add(self.stdscr, 2, 3, "Leitura minimalista de novels no Linux", curses.A_DIM)

        box_w = min(70, max(38, w - 8))
        x = max(2, (w - box_w) // 2)
        y = max(5, h // 2 - 8)

        _add(self.stdscr, y, x, "┌" + "─" * (box_w - 2) + "┐")
        _add(self.stdscr, y, x + 2, " INÍCIO ", curses.A_BOLD | _color(1))

        for idx, (_, title, description) in enumerate(self.OPTIONS):
            row = y + 2 + idx * 3
            selected = idx == self.state.selected
            marker = "▶" if selected else " "
            attr = curses.A_REVERSE | curses.A_BOLD if selected else 0
            _add(self.stdscr, row, x + 3, f"{marker} {title}", attr)
            _add(self.stdscr, row + 1, x + 7, description, curses.A_DIM)

        bottom = min(h - 4, y + 2 + len(self.OPTIONS) * 3)
        _add(self.stdscr, bottom, x, "└" + "─" * (box_w - 2) + "┘")
        _add(self.stdscr, h - 2, 3, "↑↓ escolher  •  Enter abrir  •  q sair", curses.A_DIM)

        if self.state.message:
            _add(self.stdscr, h - 1, 3, self.state.message, curses.A_BOLD | _color(3))

        self.stdscr.refresh()

    def _activate(self, action: str):
        if action == "quit":
            return "quit"
        if action == "link":
            url = self._prompt_text(
                "ABRIR POR LINK",
                "URL do livro:",
                "https://www.webnovel.com/book/...",
            )
            if url:
                self._open_book(url)
            return None
        if action == "ranking":
            self._ranking_browser()
            return None
        if action == "library":
            self._library_browser()
            return None
        if action == "search":
            self._unified_search()
            return None
        if action == "cache":
            self._cache_manager_home()
            return None
        if action == "continue":
            last = self.database.last_opened()
            if not last:
                self.state.message = "Ainda não há leitura registrada."
                return None
            book = self.database.book_for_url(last.url)
            if not book or not book.book_url:
                self.state.message = "Não encontrei a URL raiz da última obra."
                return None
            self._open_book(book.book_url)
            return None

    def _open_book(self, url: str):
        # Home, Ranking, Library and Book share exactly one curses session.
        # This avoids terminal mode corruption and raw ESC sequences such as
        # ^[[B becoming visible after returning from a book.
        self._clear_ranking_native()
        try:
            run_book_tui_inplace(
                self.stdscr,
                runtime=self.runtime,
                book_url=url,
                database=self.database,
                reader_settings=self.reader_settings,
            )
        except Exception as exc:
            error = log_exception(exc, context="startup_tui.open_book")
            self._friendly_error_popup(error)
        try:
            curses.flushinp()
        except curses.error:
            pass
        self.stdscr.keypad(True)
        self.stdscr.erase()
        self.stdscr.refresh()

    def _ranking_browser(self):
        period_index = 0
        selected = 0
        offset = 0
        books = []
        message = ""
        loaded_period = None
        exhausted_periods: set[str] = set()

        def maybe_load_more(period: str, books: list, selected: int) -> tuple[list, str]:
            if (
                self.app_config.offline_mode
                or period in exhausted_periods
                or not books
                or len(books) >= 250
                or selected < max(0, len(books) - 3)
            ):
                return books, ""

            before = len(books)
            self._clear_ranking_native()

            def more_status(text: str):
                if text:
                    self._draw_ranking_loading(
                        period_label=RANKING_PERIODS[period_index][1],
                        message=text,
                    )

            try:
                try:
                    updated = self.runtime.load_more_ranking(
                        ranking_url(period),
                        status_callback=more_status,
                    )
                except TypeError:
                    updated = self.runtime.load_more_ranking(ranking_url(period))
            except Exception as exc:
                return books, f"Falha ao carregar mais: {exc}"

            if len(updated) <= before:
                exhausted_periods.add(period)
                return books, f"{before} obras carregadas · fim dos itens disponíveis."

            self._ranking_cache[period] = updated
            return updated, f"{len(updated)} obras carregadas."

        while True:
            period = RANKING_PERIODS[period_index][0]
            if loaded_period != period:
                self._draw_loading(
                    f"Carregando ranking: {RANKING_PERIODS[period_index][1]}…"
                )
                try:
                    if period in self._ranking_cache:
                        books = self._ranking_cache[period]
                        message = f"{len(books)} obras em cache."
                    elif self.app_config.offline_mode:
                        books = []
                        message = "Modo offline: ranking não armazenado nesta sessão."
                    else:
                        def ranking_status(text: str):
                            nonlocal message
                            if text:
                                message = text
                                self._draw_ranking_loading(
                                    period_label=RANKING_PERIODS[period_index][1],
                                    message=message,
                                )

                        try:
                            books = self.runtime.load_ranking(
                                ranking_url(period),
                                status_callback=ranking_status,
                            )
                        except TypeError:
                            books = self.runtime.load_ranking(ranking_url(period))
                        self._ranking_cache[period] = books
                        message = f"{len(books)} obras carregadas · desça para carregar mais."
                    loaded_period = period
                    selected = 0
                    offset = 0
                except Exception as exc:
                    books = []
                    message = f"Falha ao carregar ranking: {exc}"
                    loaded_period = period

            selected, offset = self._draw_ranking(
                books, period_index, selected, offset, message
            )
            key = self.stdscr.getch()

            if key in (ord("q"), 27, curses.KEY_BACKSPACE, 127):
                self._clear_ranking_native()
                return
            if key in (ord("?"), curses.KEY_F2):
                self._clear_ranking_native()
                self._kitty_diagnostics_popup()
                continue
            if key == curses.KEY_LEFT:
                self._clear_ranking_native()
                period_index = (period_index - 1) % len(RANKING_PERIODS)
                loaded_period = None
                continue
            if key == curses.KEY_RIGHT:
                self._clear_ranking_native()
                period_index = (period_index + 1) % len(RANKING_PERIODS)
                loaded_period = None
                continue
            if key in (curses.KEY_UP, ord("k"), ord("K")) and books:
                selected = max(0, selected - 1)
                continue
            if key in (curses.KEY_DOWN, ord("j"), ord("J")) and books:
                selected = min(len(books) - 1, selected + 1)
                books, more_message = maybe_load_more(period, books, selected)
                if more_message:
                    message = more_message
                continue
            if key == curses.KEY_PPAGE and books:
                selected = max(0, selected - 10)
                continue
            if key == curses.KEY_NPAGE and books:
                selected = min(len(books) - 1, selected + 10)
                books, more_message = maybe_load_more(period, books, selected)
                if more_message:
                    message = more_message
                continue
            if key in (10, 13, curses.KEY_ENTER) and books:
                self._clear_ranking_native()
                self._open_book(books[selected].url)
                # Keep ranking list cached when returning.
                continue
            if key in (ord("L"), ord("l")) and books:
                item = books[selected]
                book_id = self.database.ensure_catalog_book(
                    source="WebNovel",
                    title=item.title,
                    url=item.url,
                    author=item.author,
                    cover_url=item.cover_url,
                    synopsis=item.synopsis,
                )
                added = self.database.toggle_book_library(book_id)
                message = "Adicionado à Library (Planejo ler)." if added else "Removido da Library."
                continue
            if key in (ord("F"), ord("f")) and books:
                item = books[selected]
                book_id = self.database.ensure_catalog_book(
                    source="WebNovel",
                    title=item.title,
                    url=item.url,
                    author=item.author,
                    cover_url=item.cover_url,
                    synopsis=item.synopsis,
                )
                value = self.database.toggle_book_favorite(book_id)
                message = "Favoritado ★ no Ranking." if value else "Removido dos favoritos."
                continue
            if key in (ord("/"), ord("s"), ord("S")):
                query = self._prompt_text(
                    "SEARCH",
                    "Título/autor:",
                    "",
                )
                if query:
                    self.search_history.add(query)
                    scored = [
                        (
                            100 if query.strip() == str(item.rank) else fuzzy_score(
                                query,
                                item.title,
                                item.author,
                            ),
                            i,
                        )
                        for i, item in enumerate(books)
                    ]
                    scored = [pair for pair in scored if pair[0] >= 58]
                    scored.sort(reverse=True)
                    if scored:
                        selected = scored[0][1]
                        message = f"Melhor resultado: {scored[0][0]}%."
                    else:
                        message = "Nenhum resultado aproximado."
                continue

    def _draw_ranking_loading(self, *, period_label: str, message: str) -> None:
        self._clear_ranking_native()
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        _add(self.stdscr, 0, 2, " NOVEL READER ", curses.A_BOLD | _color(4))
        _add(
            self.stdscr,
            2,
            2,
            f"Fan-Fic Power Ranking · {period_label}",
            curses.A_BOLD | _color(1),
        )
        _add(self.stdscr, 4, 4, message or "Carregando…", curses.A_BOLD)
        _add(
            self.stdscr,
            6,
            4,
            "O ranking é carregado progressivamente para capturar cards virtualizados.",
            curses.A_DIM,
        )
        self.stdscr.refresh()

    def _draw_ranking(self, books, period_index, selected, offset, message):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        period_key, period_title, period_desc = RANKING_PERIODS[period_index]
        _add(self.stdscr, 0, 2, " NOVEL READER ", curses.A_BOLD | _color(4))
        _add(self.stdscr, 0, 17, "Fan-Fic Power Ranking", curses.A_BOLD | _color(1))

        tabs = []
        for idx, (_, title, _) in enumerate(RANKING_PERIODS):
            tabs.append(f"[{title}]" if idx == period_index else title)
        _add(self.stdscr, 2, 2, "  ".join(tabs), curses.A_BOLD)
        _add(self.stdscr, 3, 2, f"Filtro de lançamento: {period_desc}", curses.A_DIM)

        side_w = min(44, max(32, w // 3)) if w >= 105 else 0
        list_w = w - side_w - 4 if side_w else w - 4
        body_top = 5
        visible = max(3, h - body_top - 4)

        if books:
            selected = max(0, min(selected, len(books) - 1))
            if selected < offset:
                offset = selected
            elif selected >= offset + visible:
                offset = selected - visible + 1
            offset = max(0, min(offset, max(0, len(books) - visible)))

        _add(self.stdscr, body_top, 1, "┌" + "─" * (list_w - 2) + "┐")
        _add(self.stdscr, body_top, 3, " RANKING ")

        for row_index, item in enumerate(
            books[offset:offset + visible],
            start=body_top + 1,
        ):
            absolute = offset + (row_index - body_top - 1)
            is_selected = absolute == selected
            marker = "▶" if is_selected else " "
            score = f" · {item.score_text}" if item.score_text else ""
            title_space = max(12, list_w - 18)
            line = f"{marker} #{item.rank:03d}  {item.title[:title_space]:<{title_space}}{score}"
            attr = curses.A_REVERSE | curses.A_BOLD if is_selected else 0
            _add(self.stdscr, row_index, 2, line, attr)

        selected_cover = None
        cover_rect = None
        if side_w and books:
            x = list_w + 2
            _add(self.stdscr, body_top, x, "┌" + "─" * (side_w - 2) + "┐")
            _add(
                self.stdscr,
                body_top,
                x + 2,
                " SELECIONADO ",
                curses.A_BOLD | _color(1),
            )
            item = books[selected]
            selected_cover = self._ranking_cover_for(item)

            row = body_top + 1
            cover_h = min(14, max(6, h - body_top - 17))
            cover_w = max(10, side_w - 4)
            cover_rect = (x + 2, row, cover_w, cover_h)

            if selected_cover.mode == "kitty" and selected_cover.image_path:
                for blank in range(cover_h):
                    _add(self.stdscr, row + blank, x + 2, " " * cover_w)
                row += cover_h
                label = "Imagem · kitten icat"
                _add(
                    self.stdscr,
                    row,
                    x + max(1, (side_w - len(label)) // 2),
                    label,
                    curses.A_DIM | _color(1),
                )
                row += 2
            elif selected_cover.ascii_text:
                for line in selected_cover.ascii_text.splitlines()[:cover_h]:
                    clipped = line[:cover_w]
                    left = x + max(1, (side_w - len(clipped)) // 2)
                    _add(self.stdscr, row, left, clipped, _color(1))
                    row += 1
                label = selected_cover.label
                _add(
                    self.stdscr,
                    row,
                    x + max(1, (side_w - len(label)) // 2),
                    label,
                    curses.A_DIM,
                )
                row += 2
            else:
                _add(self.stdscr, row, x + 2, "Capa indisponível", curses.A_DIM)
                row += 2

            for line in textwrap.wrap(item.title, side_w - 4)[:3]:
                _add(self.stdscr, row, x + 2, line, curses.A_BOLD)
                row += 1
            if item.author:
                _add(self.stdscr, row, x + 2, f"Autor: {item.author}", curses.A_DIM)
                row += 1
            if item.score_text:
                _add(self.stdscr, row, x + 2, f"Power: {item.score_text}", _color(3))
                row += 1
            if item.synopsis and row < h - 6:
                for line in textwrap.wrap(item.synopsis, side_w - 4)[: max(1, h - row - 6)]:
                    _add(self.stdscr, row, x + 2, line)
                    row += 1

        _add(
            self.stdscr,
            h - 3,
            2,
            "←→ período  ↑↓ selecionar  Enter abrir  L Library  F favorito  / buscar  ? kitty  Esc voltar",
            curses.A_DIM,
        )
        _add(self.stdscr, h - 2, 2, message, curses.A_BOLD | _color(3))
        self.stdscr.refresh()

        if (
            side_w
            and books
            and selected_cover is not None
            and cover_rect is not None
        ):
            self._draw_ranking_native(
                item=books[selected],
                cover=selected_cover,
                rect=cover_rect,
                screen_cols=w,
                screen_rows=h,
            )
        else:
            self._clear_ranking_native()

        return selected, offset

    def _ranking_cover_for(self, item) -> CoverRender:
        key = f"{self.ui_config.cover_mode}|{item.cover_url}"
        cached = self._ranking_cover_cache.get(key)
        if cached is not None:
            return cached

        if not item.cover_url:
            result = CoverRender(mode="off", label="sem capa")
        else:
            try:
                result = self.cover_renderer.prepare(
                    item.cover_url,
                    self.ui_config.cover_mode,
                    ascii_width=30,
                    ascii_height=14,
                )
            except Exception:
                result = CoverRender(mode="off", label="capa indisponível")

        self._ranking_cover_cache[key] = result
        return result

    def _draw_ranking_native(
        self,
        *,
        item,
        cover: CoverRender,
        rect,
        screen_cols: int,
        screen_rows: int,
    ) -> None:
        key = f"{item.url}|{rect}|{screen_cols}x{screen_rows}"

        if cover.mode != "kitty" or not cover.image_path:
            self._clear_ranking_native()
            return

        # Clear old placement when changing selection/geometry.
        if self._ranking_native_drawn and self._ranking_native_key != key:
            self._clear_ranking_native()

        left, top, width, height = rect
        ok = self.cover_renderer.draw_kitty(
            image_path=cover.image_path,
            screen_cols=screen_cols,
            screen_rows=screen_rows,
            left=left,
            top=top,
            width=width,
            height=height,
        )
        self._ranking_native_drawn = bool(ok)
        self._ranking_native_key = key if ok else ""

    def _clear_ranking_native(self) -> None:
        if not self._ranking_native_drawn:
            return
        h, w = self.stdscr.getmaxyx()
        self.cover_renderer.clear_kitty(
            screen_cols=w,
            screen_rows=h,
        )
        self._ranking_native_drawn = False
        self._ranking_native_key = ""

    def _kitty_diagnostics_popup(self) -> None:
        h, w = self.stdscr.getmaxyx()
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

        lines = [
            f"kitten: {diag.kitten_path or 'não encontrado'}",
            f"terminal: {diag.terminal_name or 'desconhecido'}",
            f"KITTY_WINDOW_ID: {diag.kitty_window_id or 'ausente'}",
            f"células: {diag.cols}x{diag.rows}",
            f"pixels: {diag.pixel_width}x{diag.pixel_height}",
            f"tmux: {'sim' if diag.tmux else 'não'}",
            f"screen: {'sim' if diag.screen else 'não'}",
            f"estado: {diag.reason}",
        ]

        while True:
            win.erase()
            win.box()
            _add(
                win,
                0,
                2,
                " DIAGNÓSTICO KITTEN ICAT ",
                curses.A_BOLD | _color(1),
            )
            row = 2
            for text in lines:
                for wrapped in textwrap.wrap(text, max(20, popup_w - 6)):
                    if row >= popup_h - 2:
                        break
                    _add(win, row, 3, wrapped)
                    row += 1

            _add(
                win,
                popup_h - 1,
                2,
                " qualquer tecla fecha · ? = diagnóstico ",
                curses.A_DIM,
            )
            win.refresh()
            win.getch()
            return

    def _library_browser(self):
        selected = 0
        offset = 0
        sort_modes = ("recent", "favorites", "title")
        sort_index = 0
        category_modes = ("all", "reading", "completed", "planned", "favorites")
        category_index = 0
        favorites_only = False
        query = ""
        message = ""

        while True:
            books = self.database.user_library_books(
                favorites_only=favorites_only,
                sort=sort_modes[sort_index],
            )
            if query:
                books = [
                    book for book in books
                    if fuzzy_match(
                        query,
                        book.display_title,
                        book.author or "",
                        book.tags or "",
                        self._category_label(
                            self.database.effective_book_category(book)
                        ),
                        threshold=55,
                    )
                ]
                books.sort(
                    key=lambda book: fuzzy_score(
                        query,
                        book.display_title,
                        book.author or "",
                        book.tags or "",
                    ),
                    reverse=True,
                )

            category_mode = category_modes[category_index]
            if category_mode == "favorites":
                books = [book for book in books if book.favorite]
            elif category_mode != "all":
                books = [
                    book for book in books
                    if self.database.effective_book_category(book) == category_mode
                ]

            selected, offset = self._draw_library(
                books=books,
                selected=selected,
                offset=offset,
                sort_mode=sort_modes[sort_index],
                favorites_only=favorites_only,
                category_mode=category_modes[category_index],
                query=query,
                message=message,
            )
            message = ""
            key = self.stdscr.getch()

            if key in (27, ord("q"), ord("Q"), curses.KEY_BACKSPACE, 127):
                return
            if key in (curses.KEY_UP, ord("k"), ord("K")) and books:
                selected = max(0, selected - 1)
            elif key in (curses.KEY_DOWN, ord("j"), ord("J")) and books:
                selected = min(len(books) - 1, selected + 1)
            elif key == curses.KEY_PPAGE and books:
                selected = max(0, selected - 10)
            elif key == curses.KEY_NPAGE and books:
                selected = min(len(books) - 1, selected + 10)
            elif key in (10, 13, curses.KEY_ENTER) and books:
                if books[selected].book_url:
                    self._open_book(books[selected].book_url)
                else:
                    message = "Essa obra ainda não possui URL raiz salva."
            elif key in (ord("f"), ord("F")) and books:
                value = self.database.toggle_book_favorite(books[selected].id)
                message = "Favoritado ★" if value else "Removido dos favoritos."
            elif key in (ord("P"), ord("p")) and books:
                value = self.database.toggle_book_pinned(books[selected].id)
                message = "Livro fixado no topo." if value else "Livro desafixado."
            elif key in (ord("T"), ord("t")) and books:
                value = self._prompt_text("TAGS", "Tags separadas por vírgula:", books[selected].tags)
                if value or books[selected].tags:
                    self.database.set_book_tags(books[selected].id, value)
                    message = "Tags atualizadas."
            elif key in (ord("N"), ord("n")) and books:
                value = self._prompt_text(
                    "NOTA PESSOAL",
                    "Nota de 0 a 5 (0 remove):",
                    str(books[selected].personal_rating or ""),
                )
                if value.isdigit() and 0 <= int(value) <= 5:
                    self.database.set_book_rating(books[selected].id, int(value))
                    message = "Nota pessoal salva."
            elif key in (ord("C"), ord("c")) and books:
                choices = ("auto", "reading", "completed", "planned")
                labels = ("Automática", "Lendo", "Concluído", "Planejo ler")
                current = books[selected].library_category
                idx = choices.index(current) if current in choices else 0
                idx = self._choice_popup("CATEGORIA", list(labels), idx)
                if idx is not None:
                    self.database.set_book_category(books[selected].id, choices[idx])
                    message = f"Categoria: {labels[idx]}"
            elif key in (ord("d"), ord("D"), curses.KEY_DC) and books:
                book = books[selected]
                if self._confirm(
                    "REMOVER DA LIBRARY",
                    f"Remover '{book.display_title}' da Library?",
                    "O histórico de leitura será preservado.",
                ):
                    self.database.hide_book_from_library(book.id)
                    selected = max(0, selected - 1)
                    message = "Removido da Library. O histórico foi preservado."
            elif key in (ord("v"), ord("V")):
                category_index = (category_index + 1) % len(category_modes)
                favorites_only = category_modes[category_index] == "favorites"
                selected = offset = 0
            elif key in (ord("B"), ord("b")):
                path = self._prompt_text(
                    "EXPORTAR LIBRARY",
                    "Arquivo JSON:",
                    str(Path.home() / "novel-reader-library.json"),
                )
                if path:
                    try:
                        target = self.database.export_library_json(path)
                        message = f"Backup salvo: {target}"
                    except Exception as exc:
                        message = f"Falha no backup: {exc}"
            elif key in (ord("M"), ord("m")):
                path = self._prompt_text(
                    "IMPORTAR LIBRARY",
                    "Arquivo JSON:",
                    str(Path.home() / "novel-reader-library.json"),
                )
                if path:
                    try:
                        count = self.database.import_library_json(path)
                        message = f"{count} livro(s) importado(s)/mesclado(s)."
                    except Exception as exc:
                        message = f"Falha na importação: {exc}"
            elif key in (ord("o"), ord("O")):
                sort_index = (sort_index + 1) % len(sort_modes)
                selected = offset = 0
            elif key in (ord("/"), ord("s"), ord("S")):
                query = self._prompt_text("SEARCH LIBRARY", "Título, autor, tag ou categoria:", query)
                if query:
                    self.search_history.add(query)
                selected = offset = 0
            elif key == ord("x"):
                query = ""
                selected = offset = 0

    def _draw_library(
        self,
        *,
        books,
        selected,
        offset,
        sort_mode,
        favorites_only,
        category_mode,
        query,
        message,
    ):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        _add(self.stdscr, 0, 2, " NOVEL READER ", curses.A_BOLD | _color(4))
        _add(self.stdscr, 0, 17, "Minha Library", curses.A_BOLD | _color(1))

        category_labels = {
            "all": "Todos",
            "reading": "Lendo",
            "completed": "Concluídos",
            "planned": "Planejo ler",
            "favorites": "Favoritos",
        }
        filters = [
            f"Ordem: {sort_mode}",
            f"Categoria: {category_labels.get(category_mode, category_mode)}",
        ]
        if query:
            filters.append(f"Busca: {query}")
        _add(self.stdscr, 2, 2, "  •  ".join(filters), curses.A_DIM)

        side_w = min(46, max(34, w // 3)) if w >= 105 else 0
        list_w = w - side_w - 4 if side_w else w - 4
        top = 4
        visible = max(3, h - top - 5)

        if books:
            selected = max(0, min(selected, len(books) - 1))
            if selected < offset:
                offset = selected
            elif selected >= offset + visible:
                offset = selected - visible + 1
            offset = max(0, min(offset, max(0, len(books) - visible)))
        else:
            selected = offset = 0

        _add(self.stdscr, top, 1, "┌" + "─" * (list_w - 2) + "┐")
        _add(self.stdscr, top, 3, " LIVROS ")

        if not books:
            _add(
                self.stdscr,
                top + 2,
                3,
                "Sua Library está vazia com estes filtros.",
                curses.A_DIM,
            )

        for row, book in enumerate(books[offset:offset + visible], start=top + 1):
            absolute = offset + row - top - 1
            is_selected = absolute == selected
            marker = "▶" if is_selected else " "
            star = "★" if book.favorite else " "
            pin = "◆" if book.pinned else " "
            rating = ("★" * book.personal_rating) if book.personal_rating else ""
            progress = f"{book.last_progress:>3}%"
            title_space = max(12, list_w - 25)
            line = (
                f"{marker} {pin}{star} {book.display_title[:title_space]:<{title_space}} "
                f"{rating:<5} {progress}"
            )
            attr = curses.A_REVERSE | curses.A_BOLD if is_selected else 0
            _add(self.stdscr, row, 2, line, attr)

        library_cover = None
        library_cover_rect = None
        if side_w and books:
            book = books[selected]
            x = list_w + 2
            _add(self.stdscr, top, x, "┌" + "─" * (side_w - 2) + "┐")
            _add(self.stdscr, top, x + 2, " DETALHES ", curses.A_BOLD | _color(1))
            row = top + 1

            library_cover = self._library_cover_for(book)
            cover_h = min(11, max(5, h - top - 20))
            cover_w = max(10, side_w - 4)
            library_cover_rect = (x + 2, row, cover_w, cover_h)
            if library_cover.mode == "kitty" and library_cover.image_path:
                for blank in range(cover_h):
                    _add(self.stdscr, row + blank, x + 2, " " * cover_w)
                row += cover_h + 1
            elif library_cover.ascii_text:
                for line in library_cover.ascii_text.splitlines()[:cover_h]:
                    clipped = line[:cover_w]
                    _add(self.stdscr, row, x + max(1, (side_w - len(clipped)) // 2), clipped, _color(1))
                    row += 1
                row += 1
            else:
                _add(self.stdscr, row, x + 2, "Capa indisponível", curses.A_DIM)
                row += 2
            for line in textwrap.wrap(book.display_title, side_w - 4)[:3]:
                _add(self.stdscr, row, x + 2, line, curses.A_BOLD)
                row += 1
            if book.author:
                _add(self.stdscr, row, x + 2, f"Autor: {book.author}", curses.A_DIM)
                row += 2
            _add(
                self.stdscr,
                row,
                x + 2,
                f"Favorito: {'sim ★' if book.favorite else 'não'}",
                _color(3) if book.favorite else 0,
            )
            row += 1
            _add(self.stdscr, row, x + 2, f"Categoria: {self._category_label(self.database.effective_book_category(book))}")
            row += 1
            _add(self.stdscr, row, x + 2, f"Nota pessoal: {('★' * book.personal_rating) or '—'}")
            row += 1
            _add(self.stdscr, row, x + 2, f"Fixado: {'sim ◆' if book.pinned else 'não'}")
            row += 1
            if book.tags:
                _add(self.stdscr, row, x + 2, f"Tags: {book.tags[:side_w-10]}", curses.A_DIM)
                row += 1
            _add(self.stdscr, row, x + 2, f"Último progresso: {book.last_progress}%")
            row += 1
            _add(self.stdscr, row, x + 2, f"Lido: {self._relative_time(book.last_opened)}")
            row += 1
            _add(self.stdscr, row, x + 2, f"Capítulos conhecidos: {book.chapter_count}")
            row += 2
            if book.last_chapter_title:
                _add(self.stdscr, row, x + 2, "Último capítulo:", curses.A_DIM)
                row += 1
                for line in textwrap.wrap(book.last_chapter_title, side_w - 4)[:3]:
                    _add(self.stdscr, row, x + 2, line)
                    row += 1

        _add(
            self.stdscr,
            h - 3,
            2,
            "↑↓ mover  Enter abrir  F favorito  P fixar  T tags  N nota  C categoria",
            curses.A_DIM,
        )
        _add(
            self.stdscr,
            h - 2,
            2,
            "V categorias  O ordenar  / buscar  B backup  M importar  D remover  Esc voltar",
            curses.A_DIM,
        )
        if message:
            _add(self.stdscr, h - 1, 2, message, curses.A_BOLD | _color(3))

        self.stdscr.refresh()
        if (
            side_w
            and books
            and library_cover is not None
            and library_cover_rect is not None
        ):
            self._draw_library_native(
                book=books[selected],
                cover=library_cover,
                rect=library_cover_rect,
                screen_cols=w,
                screen_rows=h,
            )
        else:
            self._clear_library_native()
        return selected, offset

    def _library_cover_for(self, book) -> CoverRender:
        key = f"library|{self.ui_config.cover_mode}|{book.cover_url}"
        cached = self._ranking_cover_cache.get(key)
        if cached is not None:
            return cached
        if not book.cover_url:
            result = CoverRender(mode="off", label="sem capa")
        else:
            try:
                result = self.cover_renderer.prepare(
                    book.cover_url,
                    self.ui_config.cover_mode,
                    ascii_width=28,
                    ascii_height=11,
                )
            except Exception:
                result = CoverRender(mode="off", label="capa indisponível")
        self._ranking_cover_cache[key] = result
        return result

    def _draw_library_native(self, *, book, cover, rect, screen_cols, screen_rows):
        # Reuse the same native slot as ranking: only one image is visible.
        class Proxy:
            url = f"library:{book.id}"
        self._draw_ranking_native(
            item=Proxy(),
            cover=cover,
            rect=rect,
            screen_cols=screen_cols,
            screen_rows=screen_rows,
        )

    def _clear_library_native(self):
        self._clear_ranking_native()

    @staticmethod
    def _category_label(category: str) -> str:
        return {
            "reading": "Lendo",
            "completed": "Concluído",
            "planned": "Planejo ler",
            "auto": "Automática",
        }.get(category, category)

    @staticmethod
    def _relative_time(value: str) -> str:
        if not value:
            return "nunca"
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            seconds = max(0, int((datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()))
        except Exception:
            return value
        if seconds < 60:
            return "agora"
        if seconds < 3600:
            return f"há {seconds // 60} min"
        if seconds < 86400:
            hours = seconds // 3600
            return f"há {hours} h"
        if seconds < 172800:
            return "ontem"
        days = seconds // 86400
        if days < 30:
            return f"há {days} dias"
        months = days // 30
        if months < 12:
            return f"há {months} meses"
        return f"há {months // 12} anos"

    def _choice_popup(self, title: str, choices: list[str], current: int = 0):
        h, w = self.stdscr.getmaxyx()
        popup_w = min(56, max(34, w - 10))
        popup_h = min(len(choices) + 5, h - 4)
        win = curses.newwin(
            popup_h,
            popup_w,
            max(0, (h - popup_h)//2),
            max(0, (w - popup_w)//2),
        )
        win.keypad(True)
        index = max(0, min(current, len(choices)-1))
        while True:
            win.erase()
            win.box()
            _add(win, 0, 2, f" {title} ", curses.A_BOLD | _color(1))
            for i, label in enumerate(choices):
                attr = curses.A_REVERSE | curses.A_BOLD if i == index else 0
                _add(win, 2+i, 3, f"{'▶' if i == index else ' '} {label}", attr)
            win.refresh()
            key = win.getch()
            if key in (curses.KEY_UP, ord("k"), ord("K")):
                index = (index - 1) % len(choices)
            elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
                index = (index + 1) % len(choices)
            elif key == 27:
                return None
            elif key in (10, 13, curses.KEY_ENTER):
                return index

    def _cache_manager_home(self):
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
            h, w = self.stdscr.getmaxyx()
            popup_w = min(74, max(50, w - 10))
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
            _add(win, 0, 2, " OFFLINE E CACHE ", curses.A_BOLD | _color(1))
            _add(
                win, 2, 3,
                f"Uso: {CacheStats.human_size(stats.total_bytes)} / "
                f"{self.app_config.cache_limit_mb} MB",
                curses.A_BOLD,
            )
            _add(win, 3, 3, f"Capítulos: {CacheStats.human_size(stats.chapters_bytes)}")
            _add(win, 4, 3, f"Capas: {CacheStats.human_size(stats.covers_bytes)}")
            _add(
                win, 5, 3,
                f"Modo offline: {'ATIVO' if self.app_config.offline_mode else 'desativado'}",
                _color(3) if self.app_config.offline_mode else curses.A_DIM,
            )

            row = 7
            for index, label in enumerate(options):
                attr = curses.A_REVERSE | curses.A_BOLD if index == selected else 0
                _add(win, row+index, 3, f"{'▶' if index == selected else ' '} {label}", attr)

            if message:
                _add(win, popup_h-2, 3, message[:popup_w-6], curses.A_DIM)
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
                message = f"{self.cache_manager.clear_chapters()} arquivo(s) removido(s)."
            elif action == "Limpar capas":
                message = f"{self.cache_manager.clear_covers()} arquivo(s) removido(s)."
            elif action == "Limpar tudo":
                message = f"{self.cache_manager.clear_all()} arquivo(s) removido(s)."
            elif action == "Alternar modo offline":
                self.app_config = self.app_config_store.update(
                    offline_mode=not self.app_config.offline_mode
                )
                message = (
                    "Modo offline ativado."
                    if self.app_config.offline_mode
                    else "Modo offline desativado."
                )

    def _unified_search(self):
        query = self._prompt_text(
            "BUSCA UNIFICADA",
            "Título, autor, tag, categoria, URL ou H para histórico:",
            "",
        )
        if not query:
            return

        if query.casefold() == "h":
            history = self.search_history.load()
            if not history:
                self.state.message = "Histórico de buscas vazio."
                return
            chosen = self._choice_popup("HISTÓRICO DE BUSCAS", history, 0)
            if chosen is None:
                return
            query = history[chosen]

        self._run_unified_search(query)

    def _run_unified_search(self, query: str):
        query = str(query).strip()
        if not query:
            return

        self.search_history.add(query)

        if query.startswith("http://") or query.startswith("https://"):
            self._open_book(query)
            return

        self._draw_loading("Buscando na Library…")
        results: list[SearchResult] = []

        for book in self.database.user_library_books(limit=10000):
            category = self._category_label(
                self.database.effective_book_category(book)
            )
            score = fuzzy_score(
                query,
                book.display_title,
                book.author or "",
                book.tags or "",
                category,
            )
            if score >= 55:
                results.append(
                    SearchResult(
                        source="Library",
                        title=book.display_title,
                        author=book.author or "",
                        url=book.book_url or "",
                        score=score,
                        detail=f"{category} · {book.tags or 'sem tags'}",
                        book_id=book.id,
                        favorite=bool(book.favorite),
                        in_library=True,
                    )
                )

        monthly_cached = self._ranking_cache.get("monthly")
        ranking_sets = list(self._ranking_cache.items())
        if not ranking_sets and not self.app_config.offline_mode:
            self._draw_loading("Completando busca com o ranking mensal…")
            try:
                try:
                    monthly = self.runtime.load_ranking(
                        ranking_url("monthly"),
                        status_callback=lambda text: self._draw_loading(
                            text or "Buscando no ranking mensal…"
                        ),
                    )
                except TypeError:
                    monthly = self.runtime.load_ranking(ranking_url("monthly"))
                ranking = monthly
                self._ranking_cache["monthly"] = ranking
                ranking_sets = [("monthly", ranking)]
            except Exception:
                ranking_sets = []

        period_labels = {key: label for key, label, _ in RANKING_PERIODS}
        for period, ranking in ranking_sets:
            for item in ranking:
                score = fuzzy_score(query, item.title, item.author)
                if score < 55:
                    continue
                book = self.database.book_for_url(item.url)
                results.append(
                    SearchResult(
                        source=f"Ranking/{period_labels.get(period, period)}",
                        title=item.title,
                        author=item.author,
                        url=item.url,
                        score=score,
                        detail=f"Rank #{item.rank}",
                        book_id=book.id if book else None,
                        favorite=bool(book.favorite) if book else False,
                        in_library=(
                            self.database.is_book_in_library(book.id)
                            if book else False
                        ),
                    )
                )

        by_url: dict[str, SearchResult] = {}
        for result in results:
            if not result.url:
                continue
            current = by_url.get(result.url)
            if current is None or result.source == "Library" or result.score > current.score:
                by_url[result.url] = result

        deduped = sorted(
            by_url.values(),
            key=lambda item: (
                item.source != "Library",
                -item.score,
                item.title.casefold(),
            ),
        )

        if not deduped:
            self.state.message = "Nenhum resultado aproximado encontrado."
            return

        index = 0
        message = ""
        while True:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()
            _add(self.stdscr, 0, 2, " NOVEL READER ", curses.A_BOLD | _color(4))
            _add(
                self.stdscr,
                0,
                17,
                f"Busca: {query} · {len(deduped)} resultado(s)",
                curses.A_BOLD | _color(1),
            )
            visible = max(3, h - 6)
            start = max(0, min(index - visible + 1, max(0, len(deduped) - visible)))
            for row, item in enumerate(deduped[start:start + visible], start=2):
                absolute = start + row - 2
                attr = curses.A_REVERSE | curses.A_BOLD if absolute == index else 0
                flags = ("★" if item.favorite else " ") + ("L" if item.in_library else " ")
                line = (
                    f"{'▶' if absolute == index else ' '} {flags} "
                    f"[{item.source}] {item.title} — {item.author} ({item.score}%)"
                )
                _add(self.stdscr, row, 2, line[: max(1, w - 4)], attr)

            if message:
                _add(self.stdscr, h - 3, 2, message[: max(1, w - 4)], _color(3))

            _add(
                self.stdscr,
                h - 2,
                2,
                "↑↓ mover  Enter abrir  L Library  F favorito  H histórico  Esc voltar",
                curses.A_DIM,
            )
            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key == 27:
                return
            if key in (curses.KEY_UP, ord("k"), ord("K")):
                index = max(0, index - 1)
            elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
                index = min(len(deduped) - 1, index + 1)
            elif key in (10, 13, curses.KEY_ENTER):
                self._open_book(deduped[index].url)
                return
            elif key in (ord("L"), ord("l")):
                item = deduped[index]
                book_id = item.book_id
                if book_id is None:
                    book_id = self.database.ensure_catalog_book(
                        source="WebNovel",
                        title=item.title,
                        url=item.url,
                        author=item.author,
                    )
                    item.book_id = book_id
                item.in_library = self.database.toggle_book_library(book_id)
                message = "Adicionado à Library." if item.in_library else "Removido da Library."
            elif key in (ord("F"), ord("f")):
                item = deduped[index]
                book_id = item.book_id
                if book_id is None:
                    book_id = self.database.ensure_catalog_book(
                        source="WebNovel",
                        title=item.title,
                        url=item.url,
                        author=item.author,
                    )
                    item.book_id = book_id
                item.favorite = self.database.toggle_book_favorite(book_id)
                item.in_library = self.database.is_book_in_library(book_id)
                message = "Favoritado ★." if item.favorite else "Removido dos favoritos."
            elif key in (ord("H"), ord("h")):
                history = self.search_history.load()
                if history:
                    chosen = self._choice_popup("HISTÓRICO DE BUSCAS", history, 0)
                    if chosen is not None:
                        return self._run_unified_search(history[chosen])
                else:
                    message = "Histórico vazio."

    def _confirm(self, title: str, message: str, detail: str = "") -> bool:
        h, w = self.stdscr.getmaxyx()
        popup_w = min(76, max(42, w - 10))
        popup_h = 8
        win = curses.newwin(
            popup_h,
            popup_w,
            max(0, (h - popup_h)//2),
            max(0, (w - popup_w)//2),
        )
        win.keypad(True)
        while True:
            win.erase()
            win.box()
            _add(win, 0, 2, f" {title} ", curses.A_BOLD | _color(3))
            _add(win, 2, 2, message)
            if detail:
                _add(win, 3, 2, detail, curses.A_DIM)
            _add(win, 5, 2, "y/Enter confirmar  •  n/Esc cancelar", curses.A_DIM)
            win.refresh()
            key = win.getch()
            if key in (ord("y"), ord("Y"), 10, 13, curses.KEY_ENTER):
                return True
            if key in (ord("n"), ord("N"), 27):
                return False

    def _draw_loading(self, message):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        _add(self.stdscr, h // 2 - 1, max(2, w // 2 - 18), "NOVEL READER", curses.A_BOLD | _color(1))
        _add(self.stdscr, h // 2 + 1, max(2, w // 2 - len(message)//2), message, curses.A_BOLD)
        self.stdscr.refresh()

    def _prompt_text(self, title: str, label: str, initial: str):
        h, w = self.stdscr.getmaxyx()
        popup_w = min(88, max(42, w - 8))
        popup_h = 7
        win = curses.newwin(
            popup_h,
            popup_w,
            max(0, (h - popup_h)//2),
            max(0, (w - popup_w)//2),
        )
        win.keypad(True)
        value = initial
        curses.curs_set(1)

        while True:
            win.erase()
            win.box()
            _add(win, 0, 2, f" {title} ", curses.A_BOLD | _color(1))
            _add(win, 2, 2, label)
            display = value[-max(10, popup_w - 6):]
            _add(win, 3, 2, display + "▌", curses.A_BOLD)
            _add(win, 5, 2, "Enter confirmar  •  Esc cancelar", curses.A_DIM)
            win.refresh()

            key = win.getch()
            if key == 27:
                curses.curs_set(0)
                return ""
            if key in (10, 13, curses.KEY_ENTER):
                curses.curs_set(0)
                return value.strip()
            if key in (curses.KEY_BACKSPACE, 127, 8):
                value = value[:-1]
            elif 32 <= key <= 126:
                value += chr(key)
