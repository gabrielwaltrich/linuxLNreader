import argparse
import sys

from PySide6.QtWidgets import QApplication

from novel_reader.browser import BrowserSession
from novel_reader.database import LibraryDatabase
from novel_reader.models import UrlKind
from novel_reader.sources import SourceManager


def run(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Testa a extração da página/índice de uma obra."
    )
    parser.add_argument("url", help="URL raiz da obra")
    parser.add_argument(
        "--save",
        action="store_true",
        help="Salvar metadados e índice no SQLite da aplicação",
    )
    args = parser.parse_args(argv)

    manager = SourceManager()
    if manager.classify_url(args.url) is not UrlKind.BOOK:
        print("Erro: a URL informada não foi reconhecida como página de livro.", file=sys.stderr)
        return 2

    app = QApplication.instance() or QApplication(sys.argv)
    session = BrowserSession(manager)
    result = {"code": 1}

    def status(message):
        print(f"[browser] {message}", file=sys.stderr)

    def failed(message):
        print(f"Erro: {message}", file=sys.stderr)
        result["code"] = 1
        app.quit()

    def loaded(book):
        print(f"Título: {book.title}")
        print(f"Autor: {book.author or '(não identificado)'}")
        print(f"Book ID: {book.source_id}")
        print(f"URL: {book.url}")
        print(f"Capítulos encontrados: {len(book.chapters)}")
        print()

        for chapter in book.chapters:
            number = (
                f"{chapter.position:>4}"
                if chapter.position is not None
                else "   -"
            )
            lock = " [bloqueado]" if chapter.accessible is False else ""
            print(f"{number}  {chapter.title}{lock}")
            print(f"      {chapter.url}")

        if args.save:
            database = LibraryDatabase()
            book_id = database.save_book_index(book)
            print()
            print(f"Índice salvo na biblioteca local (book_id={book_id}).")

        result["code"] = 0
        app.quit()

    session.status_changed.connect(status)
    session.failed.connect(failed)
    session.book_loaded.connect(loaded)
    session.load_book(args.url)

    app.exec()
    return int(result["code"])


if __name__ == "__main__":
    raise SystemExit(run())
