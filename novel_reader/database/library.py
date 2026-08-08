from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime, timezone
import re
import sqlite3
from urllib.parse import urlparse

from novel_reader.models import Book, BookChapter, Chapter


@dataclass(slots=True)
class LibraryEntry:
    url: str
    source: str
    book_title: str
    chapter_title: str
    progress: int
    favorite: bool
    last_opened: str
    book_id: int | None = None

    @property
    def display_title(self) -> str:
        return self.book_title or self.source or "Livro"

    @property
    def display_chapter(self) -> str:
        return self.chapter_title or "Capítulo"


@dataclass(slots=True)
class BookEntry:
    id: int
    book_key: str
    source: str
    title: str
    favorite: bool
    last_chapter_url: str
    last_chapter_title: str
    last_progress: int
    last_opened: str
    chapter_count: int
    book_url: str = ""
    author: str = ""
    synopsis: str = ""
    cover_url: str = ""
    source_id: str = ""
    index_updated_at: str | None = None
    library_category: str = "auto"
    tags: str = ""
    personal_rating: int = 0
    pinned: bool = False
    manual_library: bool = False

    @property
    def display_title(self) -> str:
        return self.title or self.source or "Livro"



@dataclass(slots=True)
class BookIndexEntry:
    book_id: int
    url: str
    title: str
    position: int | None
    source_id: str
    accessible: bool | None
    progress: int
    read: bool
    last_opened: str | None



@dataclass(slots=True)
class BookStats:
    book_id: int
    total: int
    read: int
    completed: int
    in_progress: int
    unread: int
    last_url: str
    last_title: str
    last_progress: int

    @property
    def completion_percent(self) -> int:
        if self.total <= 0:
            return 0
        return int(round((self.completed / self.total) * 100))


class LibraryDatabase:
    def __init__(self, path: str | Path | None = None):
        if path is None:
            from PySide6.QtCore import QStandardPaths
            data_dir = Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.AppDataLocation
                )
            )
            data_dir.mkdir(parents=True, exist_ok=True)
            path = data_dir / "library.sqlite3"

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            # Original v0.4 table is intentionally retained so upgrades do not
            # destroy existing reading history.
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS reading_history (
                    url TEXT PRIMARY KEY,
                    source TEXT NOT NULL DEFAULT '',
                    book_title TEXT NOT NULL DEFAULT '',
                    chapter_title TEXT NOT NULL DEFAULT '',
                    progress INTEGER NOT NULL DEFAULT 0,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    last_opened TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            columns = {
                row["name"]
                for row in db.execute("PRAGMA table_info(reading_history)").fetchall()
            }
            if "book_id" not in columns:
                db.execute("ALTER TABLE reading_history ADD COLUMN book_id INTEGER")

            db.execute(
                """
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_key TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    favorite INTEGER NOT NULL DEFAULT 0,
                    last_opened TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            book_columns = {
                row["name"]
                for row in db.execute("PRAGMA table_info(books)").fetchall()
            }
            for name, sql_type, default in (
                ("book_url", "TEXT", "''"),
                ("author", "TEXT", "''"),
                ("synopsis", "TEXT", "''"),
                ("cover_url", "TEXT", "''"),
                ("source_id", "TEXT", "''"),
                ("index_updated_at", "TEXT", "NULL"),
                ("library_hidden", "INTEGER", "0"),
                ("library_category", "TEXT", "'auto'"),
                ("tags", "TEXT", "''"),
                ("personal_rating", "INTEGER", "0"),
                ("pinned", "INTEGER", "0"),
                ("manual_library", "INTEGER", "0"),
            ):
                if name not in book_columns:
                    db.execute(
                        f"ALTER TABLE books ADD COLUMN {name} {sql_type} "
                        f"DEFAULT {default}"
                    )

            db.execute(
                """
                CREATE TABLE IF NOT EXISTS book_index (
                    book_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    position INTEGER,
                    source_id TEXT NOT NULL DEFAULT '',
                    accessible INTEGER,
                    discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (book_id, url),
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                )
                """
            )

            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_book_index_position "
                "ON book_index(book_id, position)"
            )

            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_last_opened "
                "ON reading_history(last_opened DESC)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_book_id "
                "ON reading_history(book_id)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_books_last_opened "
                "ON books(last_opened DESC)"
            )

            self._migrate_history_to_books(db)

    def _migrate_history_to_books(self, db: sqlite3.Connection) -> None:
        rows = db.execute(
            """
            SELECT url, source, book_title, last_opened
            FROM reading_history
            WHERE book_id IS NULL
            ORDER BY last_opened ASC
            """
        ).fetchall()

        for row in rows:
            key = self._book_key(
                source=row["source"],
                title=row["book_title"],
                url=row["url"],
            )
            book_id = self._ensure_book(
                db,
                book_key=key,
                source=row["source"],
                title=row["book_title"],
                last_opened=row["last_opened"],
            )
            db.execute(
                "UPDATE reading_history SET book_id = ? WHERE url = ?",
                (book_id, row["url"]),
            )

    @staticmethod
    def _book_key(source: str, title: str, url: str) -> str:
        parsed = urlparse(url)

        # WebNovel URLs use /book/<book-id-or-slug>/<chapter-id>.
        # Using the book segment means title changes do not create duplicates.
        if "webnovel.com" in parsed.netloc.casefold():
            parts = [part for part in parsed.path.split("/") if part]
            if "book" in parts:
                index = parts.index("book")
                if index + 1 < len(parts):
                    return f"webnovel:{parts[index + 1].casefold()}"

        if parsed.scheme == "file":
            # Local TXT files are currently individual books.
            return f"file:{parsed.path}"

        normalized_title = re.sub(r"\s+", " ", (title or "").strip().casefold())
        normalized_source = (source or parsed.netloc or "unknown").strip().casefold()
        if normalized_title:
            return f"{normalized_source}:{normalized_title}"

        # Last-resort stable key.
        return f"{normalized_source}:{parsed.netloc}{parsed.path}"

    def _ensure_book(
        self,
        db: sqlite3.Connection,
        *,
        book_key: str,
        source: str,
        title: str,
        last_opened: str | None = None,
    ) -> int:
        row = db.execute(
            "SELECT id FROM books WHERE book_key = ?",
            (book_key,),
        ).fetchone()

        if row:
            if last_opened:
                db.execute(
                    """
                    UPDATE books
                    SET source = ?, title = ?, last_opened =
                        CASE WHEN last_opened < ? THEN ? ELSE last_opened END
                    WHERE id = ?
                    """,
                    (source, title, last_opened, last_opened, row["id"]),
                )
            else:
                db.execute(
                    """
                    UPDATE books
                    SET source = ?, title = ?, last_opened = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (source, title, row["id"]),
                )
            return int(row["id"])

        cursor = db.execute(
            """
            INSERT INTO books (book_key, source, title, favorite, last_opened)
            VALUES (?, ?, ?, 0, COALESCE(?, CURRENT_TIMESTAMP))
            """,
            (book_key, source, title, last_opened),
        )
        return int(cursor.lastrowid)

    # -----------------------------------------------------------------
    # Chapter-level compatibility API from v0.4
    # -----------------------------------------------------------------
    def record_chapter(self, chapter: Chapter, progress: int | None = None) -> None:
        if not chapter.url:
            return

        progress_value = (
            self.progress_for(chapter.url)
            if progress is None
            else max(0, min(int(progress), 100))
        )

        with self._connect() as db:
            book_key = self._book_key(
                source=chapter.source,
                title=chapter.book_title,
                url=chapter.url,
            )
            book_id = self._ensure_book(
                db,
                book_key=book_key,
                source=chapter.source,
                title=chapter.book_title,
            )

            db.execute(
                """
                INSERT INTO reading_history (
                    url, source, book_title, chapter_title,
                    progress, favorite, last_opened, book_id
                ) VALUES (?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(url) DO UPDATE SET
                    source = excluded.source,
                    book_title = excluded.book_title,
                    chapter_title = excluded.chapter_title,
                    progress = excluded.progress,
                    last_opened = CURRENT_TIMESTAMP,
                    book_id = excluded.book_id
                """,
                (
                    chapter.url,
                    chapter.source,
                    chapter.book_title,
                    chapter.chapter_title,
                    progress_value,
                    book_id,
                ),
            )
            db.execute(
                """
                UPDATE books
                SET source = ?, title = ?, last_opened = CURRENT_TIMESTAMP,
                    library_hidden = 0
                WHERE id = ?
                """,
                (chapter.source, chapter.book_title, book_id),
            )

    def save_progress(self, url: str, progress: int) -> None:
        if not url:
            return
        value = max(0, min(int(progress), 100))
        with self._connect() as db:
            row = db.execute(
                "SELECT book_id FROM reading_history WHERE url = ?",
                (url,),
            ).fetchone()
            db.execute(
                """
                UPDATE reading_history
                SET progress = ?, last_opened = CURRENT_TIMESTAMP
                WHERE url = ?
                """,
                (value, url),
            )
            if row and row["book_id"]:
                db.execute(
                    "UPDATE books SET last_opened = CURRENT_TIMESTAMP WHERE id = ?",
                    (row["book_id"],),
                )

    def progress_for(self, url: str) -> int:
        if not url:
            return 0
        with self._connect() as db:
            row = db.execute(
                "SELECT progress FROM reading_history WHERE url = ?",
                (url,),
            ).fetchone()
        return int(row["progress"]) if row else 0

    def set_favorite(self, url: str, favorite: bool) -> None:
        if not url:
            return
        with self._connect() as db:
            db.execute(
                "UPDATE reading_history SET favorite = ? WHERE url = ?",
                (1 if favorite else 0, url),
            )

    def toggle_favorite(self, url: str) -> bool:
        entry = self.get(url)
        if not entry:
            return False
        new_value = not entry.favorite
        self.set_favorite(url, new_value)
        return new_value

    def get(self, url: str) -> LibraryEntry | None:
        if not url:
            return None
        with self._connect() as db:
            row = db.execute(
                """
                SELECT url, source, book_title, chapter_title, progress,
                       favorite, last_opened, book_id
                FROM reading_history
                WHERE url = ?
                """,
                (url,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def recent(self, limit: int = 100) -> list[LibraryEntry]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT url, source, book_title, chapter_title, progress,
                       favorite, last_opened, book_id
                FROM reading_history
                ORDER BY favorite DESC, last_opened DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def last_opened(self) -> LibraryEntry | None:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT url, source, book_title, chapter_title, progress,
                       favorite, last_opened, book_id
                FROM reading_history
                ORDER BY last_opened DESC
                LIMIT 1
                """
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def remove(self, url: str) -> None:
        with self._connect() as db:
            row = db.execute(
                "SELECT book_id FROM reading_history WHERE url = ?",
                (url,),
            ).fetchone()
            db.execute("DELETE FROM reading_history WHERE url = ?", (url,))
            if row and row["book_id"]:
                count = db.execute(
                    "SELECT COUNT(*) AS n FROM reading_history WHERE book_id = ?",
                    (row["book_id"],),
                ).fetchone()["n"]
                if int(count) == 0:
                    db.execute("DELETE FROM books WHERE id = ?", (row["book_id"],))

    # -----------------------------------------------------------------
    # v0.5 book-level API
    # -----------------------------------------------------------------
    def books(self, limit: int = 200) -> list[BookEntry]:
        """Retorna livros lidos ou apenas sincronizados pelo índice."""
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT
                    b.id,
                    b.book_key,
                    b.source,
                    b.title,
                    b.favorite,
                    b.last_opened,
                    b.book_url,
                    b.author,
                    b.synopsis,
                    b.cover_url,
                    b.source_id,
                    b.index_updated_at,
                    b.library_category,
                    b.tags,
                    b.personal_rating,
                    b.pinned,
                    b.manual_library,
                    CASE
                        WHEN (
                            SELECT COUNT(*)
                            FROM book_index bi
                            WHERE bi.book_id = b.id
                        ) > 0
                        THEN (
                            SELECT COUNT(*)
                            FROM book_index bi
                            WHERE bi.book_id = b.id
                        )
                        ELSE (
                            SELECT COUNT(*)
                            FROM reading_history hx
                            WHERE hx.book_id = b.id
                        )
                    END AS chapter_count,
                    COALESCE(
                        (
                            SELECT h2.url
                            FROM reading_history h2
                            WHERE h2.book_id = b.id
                            ORDER BY h2.last_opened DESC, h2.rowid DESC
                            LIMIT 1
                        ),
                        (
                            SELECT bi2.url
                            FROM book_index bi2
                            WHERE bi2.book_id = b.id
                            ORDER BY
                                CASE WHEN bi2.position IS NULL THEN 1 ELSE 0 END,
                                bi2.position ASC,
                                bi2.rowid ASC
                            LIMIT 1
                        ),
                        ''
                    ) AS last_chapter_url,
                    COALESCE(
                        (
                            SELECT h2.chapter_title
                            FROM reading_history h2
                            WHERE h2.book_id = b.id
                            ORDER BY h2.last_opened DESC, h2.rowid DESC
                            LIMIT 1
                        ),
                        (
                            SELECT bi2.title
                            FROM book_index bi2
                            WHERE bi2.book_id = b.id
                            ORDER BY
                                CASE WHEN bi2.position IS NULL THEN 1 ELSE 0 END,
                                bi2.position ASC,
                                bi2.rowid ASC
                            LIMIT 1
                        ),
                        'Nenhum capítulo'
                    ) AS last_chapter_title,
                    COALESCE(
                        (
                            SELECT h2.progress
                            FROM reading_history h2
                            WHERE h2.book_id = b.id
                            ORDER BY h2.last_opened DESC, h2.rowid DESC
                            LIMIT 1
                        ),
                        0
                    ) AS last_progress
                FROM books b
                WHERE
                    EXISTS (
                        SELECT 1 FROM reading_history h WHERE h.book_id = b.id
                    )
                    OR EXISTS (
                        SELECT 1 FROM book_index bi WHERE bi.book_id = b.id
                    )
                    OR COALESCE(b.manual_library, 0) = 1
                    OR b.favorite = 1
                ORDER BY b.favorite DESC, b.last_opened DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_book(row) for row in rows]

    def get_book(self, book_id: int) -> BookEntry | None:
        for book in self.books(limit=10000):
            if book.id == int(book_id):
                return book
        return None

    def book_for_url(self, url: str) -> BookEntry | None:
        if not url:
            return None
        with self._connect() as db:
            row = db.execute(
                """
                SELECT book_id
                FROM reading_history
                WHERE url = ?
                UNION
                SELECT book_id
                FROM book_index
                WHERE url = ?
                LIMIT 1
                """,
                (url, url),
            ).fetchone()

            if not row:
                root = db.execute(
                    "SELECT id AS book_id FROM books WHERE book_url = ? LIMIT 1",
                    (url,),
                ).fetchone()
                row = root

        if not row or not row["book_id"]:
            return None
        return self.get_book(int(row["book_id"]))

    def chapters_for_book(self, book_id: int) -> list[LibraryEntry]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT url, source, book_title, chapter_title, progress,
                       favorite, last_opened, book_id
                FROM reading_history
                WHERE book_id = ?
                ORDER BY last_opened DESC
                """,
                (int(book_id),),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def set_book_favorite(self, book_id: int, favorite: bool) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE books SET favorite = ?, library_hidden = 0 WHERE id = ?",
                (1 if favorite else 0, int(book_id)),
            )

    def toggle_book_favorite(self, book_id: int) -> bool:
        book = self.get_book(int(book_id))
        if not book:
            return False
        value = not book.favorite
        self.set_book_favorite(book.id, value)
        return value

    def user_library_books(
        self,
        *,
        limit: int = 500,
        favorites_only: bool = False,
        sort: str = "recent",
    ) -> list[BookEntry]:
        """Books the user actually read or explicitly favorited.

        Merely browsing/syncing a book index does not put it in the user's
        library unless it is favorited.
        """
        books = self.books(limit=max(limit * 3, 500))
        result = []
        with self._connect() as db:
            for book in books:
                row = db.execute(
                    """
                    SELECT
                        COALESCE(b.library_hidden, 0) AS hidden,
                        EXISTS(
                            SELECT 1 FROM reading_history h
                            WHERE h.book_id = b.id
                        ) AS has_history,
                        COALESCE(b.manual_library, 0) AS manual_library
                    FROM books b
                    WHERE b.id = ?
                    """,
                    (book.id,),
                ).fetchone()
                if not row or bool(row["hidden"]):
                    continue
                if favorites_only and not book.favorite:
                    continue
                if bool(row["has_history"]) or book.favorite or bool(row["manual_library"]):
                    result.append(book)

        if sort == "title":
            result.sort(key=lambda item: (not item.pinned, item.display_title.casefold()))
        elif sort == "favorites":
            result.sort(
                key=lambda item: (
                    not item.pinned,
                    not item.favorite,
                    item.display_title.casefold(),
                )
            )
        else:
            # `books()` already returns favorite/recent order. We want true
            # recent here while still keeping favorites visible.
            result.sort(
                key=lambda item: (item.pinned, item.last_opened or ""),
                reverse=True,
            )
        return result[:limit]


    def is_book_in_library(self, book_id: int) -> bool:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT
                    COALESCE(library_hidden, 0) AS hidden,
                    COALESCE(manual_library, 0) AS manual_library,
                    favorite,
                    EXISTS(
                        SELECT 1 FROM reading_history h WHERE h.book_id = books.id
                    ) AS has_history
                FROM books WHERE id = ?
                """,
                (int(book_id),),
            ).fetchone()
        return bool(
            row
            and not row["hidden"]
            and (row["manual_library"] or row["favorite"] or row["has_history"])
        )

    def add_book_to_library(self, book_id: int, category: str = "planned") -> None:
        category = category if category in {"auto", "reading", "completed", "planned"} else "planned"
        with self._connect() as db:
            db.execute(
                """
                UPDATE books
                SET manual_library = 1,
                    library_hidden = 0,
                    library_category = ?
                WHERE id = ?
                """,
                (category, int(book_id)),
            )

    def toggle_book_library(self, book_id: int) -> bool:
        if self.is_book_in_library(book_id):
            self.hide_book_from_library(book_id)
            return False
        self.add_book_to_library(book_id, "planned")
        return True

    def set_book_category(self, book_id: int, category: str) -> None:
        if category not in {"auto", "reading", "completed", "planned"}:
            raise ValueError("categoria inválida")
        with self._connect() as db:
            db.execute(
                """
                UPDATE books
                SET library_category = ?, manual_library = 1, library_hidden = 0
                WHERE id = ?
                """,
                (category, int(book_id)),
            )

    def effective_book_category(self, book: BookEntry) -> str:
        if book.library_category in {"reading", "completed", "planned"}:
            return book.library_category
        stats = self.book_stats(book.id)
        if stats.total > 0 and stats.completed >= stats.total:
            return "completed"
        if stats.read > 0:
            return "reading"
        return "planned"

    def set_book_tags(self, book_id: int, tags: str) -> None:
        normalized = ", ".join(
            dict.fromkeys(
                part.strip()
                for part in str(tags).replace(";", ",").split(",")
                if part.strip()
            )
        )
        with self._connect() as db:
            db.execute(
                "UPDATE books SET tags = ?, manual_library = 1, library_hidden = 0 WHERE id = ?",
                (normalized, int(book_id)),
            )

    def set_book_rating(self, book_id: int, rating: int) -> None:
        rating = max(0, min(int(rating), 5))
        with self._connect() as db:
            db.execute(
                "UPDATE books SET personal_rating = ?, manual_library = 1, library_hidden = 0 WHERE id = ?",
                (rating, int(book_id)),
            )

    def toggle_book_pinned(self, book_id: int) -> bool:
        book = self.get_book(book_id)
        if not book:
            return False
        value = not book.pinned
        with self._connect() as db:
            db.execute(
                "UPDATE books SET pinned = ?, manual_library = 1, library_hidden = 0 WHERE id = ?",
                (1 if value else 0, int(book_id)),
            )
        return value

    def ensure_catalog_book(
        self,
        *,
        source: str,
        title: str,
        url: str,
        author: str = "",
        cover_url: str = "",
        synopsis: str = "",
    ) -> int:
        with self._connect() as db:
            key = self._book_key(source=source, title=title, url=url)
            book_id = self._ensure_book(
                db,
                book_key=key,
                source=source,
                title=title,
            )
            db.execute(
                """
                UPDATE books
                SET book_url = ?, author = ?, cover_url = ?, synopsis = ?
                WHERE id = ?
                """,
                (url, author, cover_url, synopsis, book_id),
            )
        return book_id

    def export_library_json(self, path: str | Path) -> Path:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": "novel-reader-library",
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "books": [],
        }
        for book in self.user_library_books(limit=10000):
            payload["books"].append({
                "book_key": book.book_key,
                "source": book.source,
                "title": book.title,
                "book_url": book.book_url,
                "author": book.author,
                "synopsis": book.synopsis,
                "cover_url": book.cover_url,
                "source_id": book.source_id,
                "favorite": book.favorite,
                "category": book.library_category,
                "tags": book.tags,
                "rating": book.personal_rating,
                "pinned": book.pinned,
                "chapters": [
                    {
                        "url": ch.url,
                        "source": ch.source,
                        "book_title": ch.book_title,
                        "chapter_title": ch.chapter_title,
                        "progress": ch.progress,
                        "favorite": ch.favorite,
                        "last_opened": ch.last_opened,
                    }
                    for ch in self.chapters_for_book(book.id)
                ],
            })
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target

    def import_library_json(self, path: str | Path) -> int:
        source_path = Path(path).expanduser()
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        if payload.get("format") != "novel-reader-library":
            raise ValueError("arquivo não é um backup do Novel Reader")
        imported = 0
        with self._connect() as db:
            for item in payload.get("books", []):
                title = str(item.get("title") or "").strip()
                url = str(item.get("book_url") or "").strip()
                if not title and not url:
                    continue
                source = str(item.get("source") or "WebNovel")
                key = str(item.get("book_key") or self._book_key(
                    source=source, title=title, url=url
                ))
                book_id = self._ensure_book(
                    db,
                    book_key=key,
                    source=source,
                    title=title,
                )
                db.execute(
                    """
                    UPDATE books SET
                        book_url = ?, author = ?, synopsis = ?, cover_url = ?,
                        source_id = ?, favorite = ?, library_hidden = 0,
                        manual_library = 1, library_category = ?, tags = ?,
                        personal_rating = ?, pinned = ?
                    WHERE id = ?
                    """,
                    (
                        url,
                        item.get("author", ""),
                        item.get("synopsis", ""),
                        item.get("cover_url", ""),
                        item.get("source_id", ""),
                        1 if item.get("favorite") else 0,
                        item.get("category", "auto"),
                        item.get("tags", ""),
                        max(0, min(int(item.get("rating", 0)), 5)),
                        1 if item.get("pinned") else 0,
                        book_id,
                    ),
                )
                for chapter in item.get("chapters", []):
                    ch_url = str(chapter.get("url") or "")
                    if not ch_url:
                        continue
                    db.execute(
                        """
                        INSERT INTO reading_history (
                            url, source, book_title, chapter_title, progress,
                            favorite, last_opened, book_id
                        ) VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)
                        ON CONFLICT(url) DO UPDATE SET
                            source = excluded.source,
                            book_title = excluded.book_title,
                            chapter_title = excluded.chapter_title,
                            progress = MAX(reading_history.progress, excluded.progress),
                            favorite = MAX(reading_history.favorite, excluded.favorite),
                            book_id = excluded.book_id
                        """,
                        (
                            ch_url,
                            chapter.get("source", source),
                            chapter.get("book_title", title),
                            chapter.get("chapter_title", ""),
                            max(0, min(int(chapter.get("progress", 0)), 100)),
                            1 if chapter.get("favorite") else 0,
                            chapter.get("last_opened"),
                            book_id,
                        ),
                    )
                imported += 1
        return imported

    def hide_book_from_library(self, book_id: int) -> None:
        """Remove from the user-facing library without destroying history."""
        with self._connect() as db:
            db.execute(
                "UPDATE books SET library_hidden = 1, favorite = 0, manual_library = 0 WHERE id = ?",
                (int(book_id),),
            )

    def restore_book_to_library(self, book_id: int) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE books SET library_hidden = 0 WHERE id = ?",
                (int(book_id),),
            )

    def remove_book(self, book_id: int) -> None:
        with self._connect() as db:
            db.execute(
                "DELETE FROM reading_history WHERE book_id = ?",
                (int(book_id),),
            )
            db.execute("DELETE FROM books WHERE id = ?", (int(book_id),))

    def save_book_index(self, book: Book) -> int:
        """Salva metadados + índice sem baixar o texto dos capítulos.

        Não substitui reading_history: um capítulo conhecido pode nunca ter
        sido aberto. Quando ele já foi lido, seu progresso é associado na
        consulta do índice.
        """
        with self._connect() as db:
            key = self._book_key(
                source=book.source,
                title=book.title,
                url=book.url,
            )
            book_id = self._ensure_book(
                db,
                book_key=key,
                source=book.source,
                title=book.title,
            )

            db.execute(
                """
                UPDATE books
                SET book_url = ?,
                    author = ?,
                    synopsis = ?,
                    cover_url = ?,
                    source_id = ?,
                    index_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    book.url,
                    book.author,
                    book.synopsis,
                    book.cover_url,
                    book.source_id,
                    book_id,
                ),
            )

            for chapter in book.chapters:
                accessible = (
                    None
                    if chapter.accessible is None
                    else (1 if chapter.accessible else 0)
                )
                db.execute(
                    """
                    INSERT INTO book_index (
                        book_id, url, title, position, source_id,
                        accessible, discovered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(book_id, url) DO UPDATE SET
                        title = excluded.title,
                        position = excluded.position,
                        source_id = excluded.source_id,
                        accessible = excluded.accessible
                    """,
                    (
                        book_id,
                        chapter.url,
                        chapter.title,
                        chapter.position,
                        chapter.source_id,
                        accessible,
                    ),
                )

            return book_id

    def index_count(self, book_id: int) -> int:
        with self._connect() as db:
            row = db.execute(
                "SELECT COUNT(*) AS n FROM book_index WHERE book_id = ?",
                (int(book_id),),
            ).fetchone()
        return int(row["n"] if row else 0)

    def known_index(self, book_id: int) -> list[BookIndexEntry]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT
                    i.book_id,
                    i.url,
                    i.title,
                    i.position,
                    i.source_id,
                    i.accessible,
                    h.progress,
                    h.last_opened
                FROM book_index i
                LEFT JOIN reading_history h ON h.url = i.url
                WHERE i.book_id = ?
                ORDER BY
                    CASE WHEN i.position IS NULL THEN 1 ELSE 0 END,
                    i.position ASC,
                    i.rowid ASC
                """,
                (int(book_id),),
            ).fetchall()

        result = []
        for row in rows:
            accessible = row["accessible"]
            result.append(
                BookIndexEntry(
                    book_id=int(row["book_id"]),
                    url=row["url"],
                    title=row["title"] or "Capítulo",
                    position=(
                        int(row["position"])
                        if row["position"] is not None
                        else None
                    ),
                    source_id=row["source_id"] or "",
                    accessible=(
                        None
                        if accessible is None
                        else bool(accessible)
                    ),
                    progress=int(row["progress"] or 0),
                    read=bool(row["last_opened"]),
                    last_opened=row["last_opened"],
                )
            )
        return result

    def book_index_for_url(self, url: str) -> list[BookIndexEntry]:
        book = self.book_for_url(url)
        if not book:
            return []
        return self.known_index(book.id)

    def index_neighbors(self, url: str) -> tuple[str | None, str | None]:
        """Retorna anterior/próximo conforme a ordem do índice salvo."""
        book = self.book_for_url(url)
        if not book:
            return None, None

        index = self.known_index(book.id)
        for position, chapter in enumerate(index):
            if chapter.url != url:
                continue
            previous_url = index[position - 1].url if position > 0 else None
            next_url = (
                index[position + 1].url
                if position + 1 < len(index)
                else None
            )
            return previous_url, next_url
        return None, None

    def first_index_url(self, book_id: int) -> str | None:
        index = self.known_index(book_id)
        return index[0].url if index else None

    def book_stats(self, book_id: int) -> BookStats:
        index = self.known_index(book_id)
        if index:
            total = len(index)
            read = sum(1 for item in index if item.read)
            completed = sum(1 for item in index if item.progress >= 95)
            in_progress = sum(
                1 for item in index if item.read and item.progress < 95
            )
        else:
            history = self.chapters_for_book(book_id)
            total = len(history)
            read = total
            completed = sum(1 for item in history if item.progress >= 95)
            in_progress = sum(1 for item in history if item.progress < 95)

        unread = max(0, total - read)
        book = self.get_book(book_id)
        return BookStats(
            book_id=int(book_id),
            total=total,
            read=read,
            completed=completed,
            in_progress=in_progress,
            unread=unread,
            last_url=book.last_chapter_url if book else "",
            last_title=book.last_chapter_title if book else "",
            last_progress=book.last_progress if book else 0,
        )

    def chapter_url_by_number(self, book_id: int, number: int) -> str | None:
        number = int(number)
        with self._connect() as db:
            row = db.execute(
                """
                SELECT url
                FROM book_index
                WHERE book_id = ? AND position = ?
                ORDER BY rowid ASC
                LIMIT 1
                """,
                (int(book_id), number),
            ).fetchone()
        return row["url"] if row else None

    def continue_url_for_book(self, book_id: int) -> str | None:
        book = self.get_book(book_id)
        if book and book.last_chapter_url:
            return book.last_chapter_url
        return self.first_index_url(book_id)

    def first_unread_url(self, book_id: int) -> str | None:
        for item in self.known_index(book_id):
            if not item.read:
                return item.url
        return None

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> LibraryEntry:
        return LibraryEntry(
            url=row["url"],
            source=row["source"],
            book_title=row["book_title"],
            chapter_title=row["chapter_title"],
            progress=int(row["progress"]),
            favorite=bool(row["favorite"]),
            last_opened=row["last_opened"],
            book_id=int(row["book_id"]) if row["book_id"] is not None else None,
        )

    @staticmethod
    def _row_to_book(row: sqlite3.Row) -> BookEntry:
        return BookEntry(
            id=int(row["id"]),
            book_key=row["book_key"],
            source=row["source"],
            title=row["title"],
            favorite=bool(row["favorite"]),
            last_chapter_url=row["last_chapter_url"] or "",
            last_chapter_title=row["last_chapter_title"] or "Capítulo",
            last_progress=int(row["last_progress"] or 0),
            last_opened=row["last_opened"],
            chapter_count=int(row["chapter_count"]),
            book_url=row["book_url"] or "",
            author=row["author"] or "",
            synopsis=row["synopsis"] or "",
            cover_url=row["cover_url"] or "",
            source_id=row["source_id"] or "",
            index_updated_at=row["index_updated_at"],
            library_category=(row["library_category"] or "auto") if "library_category" in row.keys() else "auto",
            tags=(row["tags"] or "") if "tags" in row.keys() else "",
            personal_rating=int(row["personal_rating"] or 0) if "personal_rating" in row.keys() else 0,
            pinned=bool(row["pinned"]) if "pinned" in row.keys() else False,
            manual_library=bool(row["manual_library"]) if "manual_library" in row.keys() else False,
        )
