import argparse
import sys
from pathlib import Path

from novel_reader.errors import NovelReaderError
from novel_reader.sources import SourceManager


def _load_with_browser(url: str, manager: SourceManager):
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    from PySide6.QtWidgets import QApplication

    from novel_reader.browser import BrowserSession

    app = QApplication(sys.argv)
    session = BrowserSession(manager)
    result = {}

    session.loaded.connect(lambda chapter: (result.update(chapter=chapter), app.quit()))
    session.failed.connect(lambda message: (result.update(error=message), app.quit()))
    session.status_changed.connect(lambda message: print(message, file=sys.stderr))

    session.load(url)
    app.exec()

    if "error" in result:
        raise NovelReaderError(result["error"])
    return result["chapter"]


def run() -> int:
    parser = argparse.ArgumentParser(description="Novel Reader — modo terminal")
    parser.add_argument("url", help="URL pública do capítulo")
    parser.add_argument("-o", "--output", help="Salvar o texto em um arquivo em vez de imprimir")
    args = parser.parse_args()

    manager = SourceManager()
    try:
        if manager.requires_browser(args.url):
            chapter = _load_with_browser(args.url, manager)
        else:
            chapter = manager.load_chapter(args.url)
    except NovelReaderError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    body = f"{chapter.display_book_title} — {chapter.display_chapter_title}\n\n{chapter.text}"

    if args.output:
        Path(args.output).write_text(body, encoding="utf-8")
        print(f"Salvo em {args.output}")
    else:
        print(body)

    return 0
