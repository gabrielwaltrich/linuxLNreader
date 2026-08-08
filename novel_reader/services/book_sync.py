from __future__ import annotations

from dataclasses import replace

from novel_reader.models import Book, BookChapter


def merge_books(current: Book | None, incoming: Book) -> Book:
    """Mescla capturas sucessivas da mesma página de obra.

    O DOM pode revelar capítulos progressivamente. Mantemos a melhor versão de
    cada entrada e nunca removemos um capítulo que apareceu numa captura anterior.
    """
    if current is None:
        return Book(
            source=incoming.source,
            url=incoming.url,
            title=incoming.title,
            source_id=incoming.source_id,
            author=incoming.author,
            synopsis=incoming.synopsis,
            cover_url=incoming.cover_url,
            chapters=[replace(chapter) for chapter in incoming.chapters],
        )

    by_url = {chapter.url: replace(chapter) for chapter in current.chapters}
    order = [chapter.url for chapter in current.chapters]

    for chapter in incoming.chapters:
        if chapter.url not in by_url:
            by_url[chapter.url] = replace(chapter)
            order.append(chapter.url)
            continue

        existing = by_url[chapter.url]
        # Prefer informative titles/positions discovered later.
        if _title_score(chapter.title) > _title_score(existing.title):
            existing.title = chapter.title
        if existing.position is None and chapter.position is not None:
            existing.position = chapter.position
        if not existing.source_id and chapter.source_id:
            existing.source_id = chapter.source_id
        if chapter.accessible is not None:
            existing.accessible = chapter.accessible

    chapters = [by_url[url] for url in order]
    numbered = [c for c in chapters if c.position is not None]
    auxiliary = [c for c in chapters if c.position is None]
    if len(numbered) >= 2:
        numbered.sort(key=lambda c: c.position or 0)
        chapters = auxiliary + numbered

    return Book(
        source=incoming.source or current.source,
        url=incoming.url or current.url,
        title=incoming.title or current.title,
        source_id=incoming.source_id or current.source_id,
        author=incoming.author or current.author,
        synopsis=incoming.synopsis or current.synopsis,
        cover_url=incoming.cover_url or current.cover_url,
        chapters=chapters,
    )


def _title_score(title: str) -> int:
    value = (title or '').strip().casefold()
    if value in {'', 'chapter', 'read', 'latest release', 'continue reading'}:
        return 0
    return len(value)
