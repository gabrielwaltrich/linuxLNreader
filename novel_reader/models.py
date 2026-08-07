from dataclasses import dataclass


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
