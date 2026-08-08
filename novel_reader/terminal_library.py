from __future__ import annotations

from dataclasses import dataclass
import math
import os

from novel_reader.database import LibraryDatabase
from novel_reader.services.chapter_cache import ChapterCache
from novel_reader.terminal_reader import (
    TerminalReaderSettings,
    interactive_read,
    page_index_from_progress,
    paginate_chapter,
    progress_from_page,
)


@dataclass(slots=True)
class TerminalMenuSettings:
    chapters_per_page: int = 18
    clear: bool = True


def chapter_marker(item) -> str:
    if item.progress >= 95:
        return "✓"
    if item.read:
        return "◐"
    if item.accessible is False:
        return "🔒"
    return "·"


def chapter_status(item) -> str:
    if item.progress >= 95:
        return "lido"
    if item.read:
        return f"{item.progress}%"
    if item.accessible is False:
        return "bloqueado"
    return "não lido"


def render_index_page(book, entries, *, page=0, per_page=18, query="") -> str:
    query_cf = query.casefold().strip()
    filtered = [
        entry for entry in entries
        if not query_cf or query_cf in entry.title.casefold()
        or (entry.position is not None and query_cf == str(entry.position))
    ]
    total_pages = max(1, math.ceil(len(filtered) / per_page))
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    subset = filtered[start:start + per_page]

    lines = [
        f"{book.display_title}",
        f"Autor: {book.author or '—'}",
        f"Capítulos conhecidos: {len(entries)}",
        "",
    ]

    for local_index, item in enumerate(subset, start=start + 1):
        position = f"{item.position:>4}" if item.position is not None else "   -"
        lines.append(
            f"{local_index:>4}. {chapter_marker(item)} {position}  "
            f"{item.title}  [{chapter_status(item)}]"
        )

    lines.extend([
        "",
        f"── índice {page + 1}/{total_pages} ──",
        "[n] próxima lista  [p] anterior  [c] continuar  [u] próximo não lido",
        "[/texto] buscar  [r] atualizar índice  [q] sair",
        "Digite o número da linha para abrir um capítulo.",
    ])
    return "\n".join(lines)


def run_book_menu(
    *,
    book,
    database: LibraryDatabase,
    load_chapter,
    refresh_book,
    reader_settings: TerminalReaderSettings,
    menu_settings: TerminalMenuSettings | None = None,
    input_fn=input,
    output_fn=print,
) -> int:
    menu_settings = menu_settings or TerminalMenuSettings()
    book_id = database.save_book_index(book)
    page = 0
    query = ""
    cache = ChapterCache()

    while True:
        entries = database.known_index(book_id)
        if menu_settings.clear:
            os.system("cls" if os.name == "nt" else "clear")
        output_fn(render_index_page(
            database.get_book(book_id),
            entries,
            page=page,
            per_page=menu_settings.chapters_per_page,
            query=query,
        ))

        try:
            command = input_fn("> ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0

        low = command.casefold()
        if low in {"q", "quit", "sair"}:
            return 0
        if low == "n":
            page += 1
            continue
        if low == "p":
            page = max(0, page - 1)
            continue
        if low.startswith("/"):
            query = command[1:].strip()
            page = 0
            continue
        if low == "c":
            target = database.continue_url_for_book(book_id)
            if target:
                _read_one(target, database, load_chapter, cache, reader_settings, input_fn, output_fn)
            continue
        if low == "u":
            target = database.first_unread_url(book_id)
            if target:
                _read_one(target, database, load_chapter, cache, reader_settings, input_fn, output_fn)
            continue
        if low == "r":
            refreshed = refresh_book(book.book_url or book.url)
            if refreshed:
                book = refreshed
                book_id = database.save_book_index(book)
            continue

        try:
            selected = int(command)
        except ValueError:
            continue

        filtered = [
            entry for entry in entries
            if not query or query.casefold() in entry.title.casefold()
            or (entry.position is not None and query == str(entry.position))
        ]
        if 1 <= selected <= len(filtered):
            _read_one(
                filtered[selected - 1].url,
                database,
                load_chapter,
                cache,
                reader_settings,
                input_fn,
                output_fn,
            )


def _read_one(url, database, load_chapter, cache, settings, input_fn, output_fn):
    try:
        chapter = load_chapter(url)
        cache.save(chapter)
    except Exception:
        chapter = cache.load(url)
        if chapter is None:
            output_fn("Não foi possível abrir o capítulo e não há cópia em cache.")
            return

    old_progress = database.progress_for(url)
    title = f"{chapter.display_book_title} — {chapter.display_chapter_title}"
    pages = paginate_chapter(title, chapter.text, settings)
    start = page_index_from_progress(old_progress, len(pages))

    database.record_chapter(chapter, old_progress)
    final_index = interactive_read(
        title,
        chapter.text,
        settings,
        input_fn=input_fn,
        output_fn=output_fn,
        clear=False,
        start_page=start,
    )
    progress = progress_from_page(final_index, len(pages))
    database.save_progress(url, progress)
