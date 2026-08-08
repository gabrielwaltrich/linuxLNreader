from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class UrlKind(str, Enum):
    BOOK = "book"
    CHAPTER = "chapter"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class BookChapter:
    source: str
    url: str
    title: str
    position: int | None = None
    source_id: str = ""
    accessible: bool | None = None

    @property
    def display_title(self) -> str:
        if self.title:
            return self.title
        if self.position is not None:
            return f"Capítulo {self.position}"
        return "Capítulo"


@dataclass(slots=True)
class Book:
    source: str
    url: str
    title: str
    source_id: str = ""
    author: str = ""
    synopsis: str = ""
    cover_url: str = ""
    chapters: list[BookChapter] = field(default_factory=list)

    @property
    def display_title(self) -> str:
        return self.title or self.source or "Livro"


@dataclass(slots=True)
class Chapter:
    source: str
    url: str
    book_title: str = ""
    chapter_title: str = ""
    text: str = ""
    previous_url: str | None = None
    next_url: str | None = None

    @property
    def display_book_title(self) -> str:
        return self.book_title or self.source

    @property
    def display_chapter_title(self) -> str:
        return self.chapter_title or "Capítulo"
