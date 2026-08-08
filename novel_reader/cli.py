import argparse
import os
import sys
from pathlib import Path

from novel_reader.errors import NovelReaderError
from novel_reader.models import UrlKind
from novel_reader.database import LibraryDatabase
from novel_reader.services.media_ascii import MediaAsciiError, MediaAsciiService
from novel_reader.services.paragraph_comments import ParagraphCommentsInspector
from novel_reader.sources import SourceManager
from novel_reader.terminal_reader import TerminalReaderSettings, interactive_read, paginate_chapter
from novel_reader.cli_browser_runtime import CliBrowserRuntime
from novel_reader.terminal_tui import run_book_tui
from novel_reader.startup_tui import run_startup_tui


def _load_with_browser(url: str, manager: SourceManager):
    # O CLI não abre uma janela; QtWebEngine ainda precisa de uma
    # QApplication para processar a página.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    from PySide6.QtWidgets import QApplication
    from novel_reader.browser import BrowserSession

    app = QApplication.instance() or QApplication(sys.argv)
    session = BrowserSession(manager)
    result = {}

    def on_loaded(chapter):
        result["chapter"] = chapter
        app.quit()

    def on_failed(message):
        result["error"] = message
        app.quit()

    session.loaded.connect(on_loaded)
    session.failed.connect(on_failed)
    session.status_changed.connect(lambda message: print(message, file=sys.stderr))
    session.load(url)

    app.exec()

    if "error" in result:
        raise NovelReaderError(result["error"])

    chapter = result.get("chapter")
    if chapter is None:
        raise NovelReaderError("O navegador terminou sem retornar um capítulo.")

    return chapter



def _load_book_with_browser(url: str, manager: SourceManager):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    from PySide6.QtWidgets import QApplication
    from novel_reader.browser import BrowserSession

    app = QApplication.instance() or QApplication(sys.argv)
    session = BrowserSession(manager)
    result = {}

    def on_loaded(book):
        result["book"] = book
        app.quit()

    def on_failed(message):
        result["error"] = message
        app.quit()

    session.book_loaded.connect(on_loaded)
    session.failed.connect(on_failed)
    session.status_changed.connect(lambda message: print(message, file=sys.stderr))
    session.load_book(url)

    app.exec()

    if "error" in result:
        raise NovelReaderError(result["error"])

    book = result.get("book")
    if book is None:
        raise NovelReaderError("O navegador terminou sem retornar a obra.")

    return book



def _load_dom_with_browser(url: str, manager: SourceManager):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    from PySide6.QtWidgets import QApplication
    from novel_reader.browser import BrowserSession

    app = QApplication.instance() or QApplication(sys.argv)
    session = BrowserSession(manager)
    result = {}

    def on_loaded(final_url, html):
        result["final_url"] = final_url
        result["html"] = html
        app.quit()

    def on_failed(message):
        result["error"] = message
        app.quit()

    session.dom_loaded.connect(on_loaded)
    session.failed.connect(on_failed)
    session.status_changed.connect(lambda message: print(message, file=sys.stderr))
    session.load_dom(url)
    app.exec()

    if "error" in result:
        raise NovelReaderError(result["error"])
    return result.get("final_url", url), result.get("html", "")



def _book_output(book, *, cover_ascii: bool, ascii_width: int) -> str:
    pieces: list[str] = []

    if cover_ascii and book.cover_url:
        try:
            rendered = MediaAsciiService().render_url(
                book.cover_url,
                width=ascii_width,
                height=max(8, ascii_width // 2),
            )
            pieces.append(rendered.text)
            pieces.append(f"[capa ASCII: {rendered.backend}]")
        except MediaAsciiError as exc:
            pieces.append(f"[capa ASCII indisponível: {exc}]")

    pieces.append(book.title)
    if book.author:
        pieces.append(f"Autor: {book.author}")
    pieces.append(f"Capítulos encontrados: {len(book.chapters)}")

    if book.synopsis:
        pieces.append("")
        pieces.append(book.synopsis)

    return "\n".join(pieces)


def run(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Novel Reader — modo terminal"
    )
    parser.add_argument("url", nargs="?", help="URL pública de livro ou capítulo")
    parser.add_argument(
        "-o",
        "--output",
        help="Salvar a saída em um arquivo em vez de imprimir",
    )
    parser.add_argument(
        "--cover-ascii",
        action="store_true",
        help="Mostrar a capa do livro em ASCII (URLs raiz de obra)",
    )
    parser.add_argument(
        "--ascii-width",
        type=int,
        default=40,
        help="Largura da capa ASCII em caracteres (padrão: 40)",
    )
    parser.add_argument("--read", action="store_true", help="Abrir capítulo no leitor paginado interativo")
    parser.add_argument("--width", type=int, default=82, help="Largura do texto em caracteres")
    parser.add_argument("--lines", type=int, default=24, help="Linhas por página")
    parser.add_argument("--margin", type=int, default=2, help="Margem lateral em espaços")
    parser.add_argument("--paragraph-spacing", type=int, default=1, help="Linhas vazias entre parágrafos")
    parser.add_argument("--text-size", choices=["small","normal","large"], default="normal",
                        help="Densidade da leitura: small/normal/large (não altera a fonte do terminal)")
    parser.add_argument("--page", type=int, help="Imprimir apenas uma página específica e sair")
    parser.add_argument("--no-clear", action="store_true", help="Não limpar o terminal entre páginas")
    parser.add_argument("--menu", action="store_true", help="Abrir interface TUI em tela cheia para uma URL de livro")
    parser.add_argument("--index-lines", type=int, default=18, help="Capítulos mostrados por página no menu")
    parser.add_argument("--comments-probe", action="store_true", help="Diagnosticar disponibilidade de comentários por parágrafo no DOM")
    args = parser.parse_args(argv)

    manager = SourceManager()

    # No URL: launch the Reader home screen when running interactively.
    if not args.url:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            parser.error("informe uma URL quando o CLI não estiver em um terminal interativo")
        runtime = CliBrowserRuntime()
        try:
            reader_settings = TerminalReaderSettings(
                width=args.width,
                lines_per_page=args.lines,
                margin=args.margin,
                paragraph_spacing=args.paragraph_spacing,
                text_size=args.text_size,
            )
            return run_startup_tui(
                runtime=runtime,
                database=LibraryDatabase(),
                reader_settings=reader_settings,
            )
        finally:
            runtime.close()

    try:
        kind = (
            manager.classify_url(args.url)
            if hasattr(manager, "classify_url")
            else UrlKind.CHAPTER
        )

        if args.comments_probe:
            runtime = CliBrowserRuntime()
            try:
                final_url, html = runtime.load_dom(args.url)
            finally:
                runtime.close()
            probe = ParagraphCommentsInspector().inspect(html)
            print(f"URL final: {final_url}")
            print(f"UI de comentários por parágrafo: {'sim' if probe.ui_present else 'não'}")
            print(f"Login indicado no DOM: {'sim' if probe.login_required else 'não'}")
            print(f"Marcadores de contagem detectados: {probe.paragraph_count_markers}")
            print(f"Candidatos de comentários visíveis: {probe.visible_comment_candidates}")
            for note in probe.notes:
                print(f"- {note}")
            return 0

        if kind is UrlKind.BOOK:
            # Full-screen TUI is the default for a book URL when attached to a
            # terminal. This keeps the terminal "owned" by Novel Reader until
            # the user explicitly exits.
            use_tui = args.menu or args.read or (
                sys.stdin.isatty()
                and sys.stdout.isatty()
                and not args.output
                and not args.cover_ascii
            )

            if use_tui:
                runtime = CliBrowserRuntime()
                try:
                    reader_settings = TerminalReaderSettings(
                        width=args.width,
                        lines_per_page=args.lines,
                        margin=args.margin,
                        paragraph_spacing=args.paragraph_spacing,
                        text_size=args.text_size,
                    )
                    return run_book_tui(
                        runtime=runtime,
                        book_url=args.url,
                        database=LibraryDatabase(),
                        reader_settings=reader_settings,
                    )
                finally:
                    runtime.close()

            book = _load_book_with_browser(args.url, manager)
            body = _book_output(
                book,
                cover_ascii=args.cover_ascii,
                ascii_width=max(12, min(args.ascii_width, 120)),
            )
        else:
            if manager.requires_browser(args.url):
                chapter = _load_with_browser(args.url, manager)
            else:
                chapter = manager.load_chapter(args.url)

            body = (
                f"{chapter.display_book_title} — "
                f"{chapter.display_chapter_title}\n\n"
                f"{chapter.text}"
            )

    except NovelReaderError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130

    if kind is not UrlKind.BOOK and not args.output and (args.read or args.page):
        settings = TerminalReaderSettings(
            width=args.width,
            lines_per_page=args.lines,
            margin=args.margin,
            paragraph_spacing=args.paragraph_spacing,
            text_size=args.text_size,
        )
        title = f"{chapter.display_book_title} — {chapter.display_chapter_title}"
        if args.page:
            pages = paginate_chapter(title, chapter.text, settings)
            index = max(1, args.page) - 1
            if index >= len(pages):
                print(f"Erro: página {args.page} não existe; capítulo possui {len(pages)} páginas.", file=sys.stderr)
                return 2
            print(pages[index])
            print(f"\n── página {index+1}/{len(pages)} ──")
            return 0
        interactive_read(title, chapter.text, settings, clear=not args.no_clear)
        return 0

    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(body, encoding="utf-8")
        print(f"Salvo em {output}")
    else:
        print(body)

    return 0
