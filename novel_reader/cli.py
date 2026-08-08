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
from novel_reader import __version__
from novel_reader.system_diagnostics import format_doctor_report, overall_ok, run_diagnostics
from novel_reader.setup_assistant import run_setup
from novel_reader.logging_setup import configure_logging, get_logger
from novel_reader.error_handling import format_friendly_error, log_exception, write_crash_report
from novel_reader.app_config import AppConfigStore, migrate_legacy_terminal_config
from novel_reader.services.chapter_cache import ChapterCache
from novel_reader.services.cache_manager import CacheManager, CacheStats
from novel_reader.services.data_safety import DataSafetyManager
from novel_reader.services.instance_lock import InstanceLock, InstanceAlreadyRunningError
from novel_reader.services.self_test import run_self_test, self_test_ok, format_self_test
from novel_reader.services.compatibility_report import collect_compatibility_report, format_compatibility_report, write_compatibility_report


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
        "--version",
        action="version",
        version=f"Novel Reader {__version__}",
        help="Mostrar a versão instalada e sair",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Verificar dependências, terminal, banco e cache",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Mostrar um plano assistido para corrigir dependências",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Ativar logs detalhados também no stderr",
    )
    parser.add_argument(
        "--config-show",
        action="store_true",
        help="Mostrar a configuração centralizada atual e sair",
    )
    parser.add_argument(
        "--config-set",
        action="append",
        default=[],
        metavar="CHAVE=VALOR",
        help="Alterar uma preferência centralizada; pode ser repetido",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Executar esta sessão sem tentar acessar a rede",
    )
    parser.add_argument(
        "--cache-status",
        action="store_true",
        help="Mostrar uso atual do cache e sair",
    )
    parser.add_argument(
        "--cache-clear",
        choices=["chapters", "covers", "all"],
        help="Limpar uma parte do cache e sair",
    )
    parser.add_argument(
        "--db-check",
        action="store_true",
        help="Executar PRAGMA integrity_check no banco e sair",
    )
    parser.add_argument(
        "--backup-now",
        action="store_true",
        help="Criar backup consistente do SQLite + JSON e sair",
    )
    parser.add_argument(
        "--backup-list",
        action="store_true",
        help="Listar backups automáticos disponíveis e sair",
    )
    parser.add_argument(
        "--restore-backup",
        metavar="ARQUIVO.sqlite3",
        help="Restaurar a Library a partir de um backup SQLite validado",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Executar smoke tests locais do Reader e sair",
    )
    parser.add_argument(
        "--compat-report",
        nargs="?",
        const="-",
        metavar="ARQUIVO.json",
        help="Mostrar ou salvar relatório de compatibilidade da máquina",
    )
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
    parser.add_argument("--width", type=int, default=None, help="Largura do texto em caracteres")
    parser.add_argument("--lines", type=int, default=None, help="Linhas por página")
    parser.add_argument("--margin", type=int, default=None, help="Margem lateral em espaços")
    parser.add_argument("--paragraph-spacing", type=int, default=None, help="Linhas vazias entre parágrafos")
    parser.add_argument("--text-size", choices=["small","normal","large"], default="normal",
                        help="Densidade da leitura: small/normal/large (não altera a fonte do terminal)")
    parser.add_argument("--page", type=int, help="Imprimir apenas uma página específica e sair")
    parser.add_argument("--no-clear", action="store_true", help="Não limpar o terminal entre páginas")
    parser.add_argument("--menu", action="store_true", help="Abrir interface TUI em tela cheia para uma URL de livro")
    parser.add_argument("--index-lines", type=int, default=18, help="Capítulos mostrados por página no menu")
    parser.add_argument("--comments-probe", action="store_true", help="Diagnosticar disponibilidade de comentários por parágrafo no DOM")
    args = parser.parse_args(argv)
    log_ctx = configure_logging(debug=args.debug)
    logger = get_logger("cli")
    logger.debug("Argumentos CLI: %r", vars(args))
    config_store = AppConfigStore()
    migrate_legacy_terminal_config(config_store)
    app_config = config_store.load()

    if args.config_set:
        updates = {}
        field_types = {
            "font_size": int,
            "content_width": int,
            "line_height": float,
            "theme": str,
            "terminal_width": int,
            "lines_per_page": int,
            "terminal_margin": int,
            "paragraph_spacing": int,
            "text_size": str,
            "cover_mode": str,
            "ascii_width": int,
            "ascii_height": int,
            "prefetch_count": int,
            "cache_limit_mb": int,
            "cache_policy": str,
            "offline_mode": lambda v: v.casefold() in {"1", "true", "yes", "sim", "on"},
            "index_refresh_minutes": int,
            "automatic_backups": lambda v: v.casefold() in {"1", "true", "yes", "sim", "on"},
            "backup_retention": int,
            "backup_interval_hours": int,
        }
        for entry in args.config_set:
            if "=" not in entry:
                parser.error(f"--config-set exige CHAVE=VALOR: {entry}")
            key, raw = entry.split("=", 1)
            key = key.strip()
            if key not in field_types:
                parser.error(f"configuração desconhecida: {key}")
            try:
                updates[key] = field_types[key](raw.strip())
            except Exception as exc:
                parser.error(f"valor inválido para {key}: {raw} ({exc})")
        app_config = config_store.update(**updates)

    if args.config_show or args.config_set:
        import json as _json
        from dataclasses import asdict as _asdict
        print(_json.dumps(_asdict(app_config), ensure_ascii=False, indent=2, sort_keys=True))
        if args.config_show or not args.url:
            return 0
    if args.offline:
        app_config.offline_mode = True

    database_path = LibraryDatabase.default_path()
    safety_manager = DataSafetyManager(
        database_path,
        retention=app_config.backup_retention,
        min_interval_hours=app_config.backup_interval_hours,
    )

    if args.self_test:
        items = run_self_test()
        print(format_self_test(items))
        return 0 if self_test_ok(items) else 5

    if args.compat_report is not None:
        if args.compat_report == "-":
            print(format_compatibility_report(collect_compatibility_report()))
        else:
            path = write_compatibility_report(args.compat_report)
            print(f"Relatório salvo em: {path}")
        return 0

    if args.db_check:
        health = safety_manager.check_database()
        print(f"Banco: {health.path}")
        print(f"Integrity check: {health.integrity}")
        return 0 if health.ok else 3

    if args.backup_list:
        backups = safety_manager.list_backups()
        if not backups:
            print("Nenhum backup automático encontrado.")
        for record in backups:
            print(record.sqlite_path)
            if record.json_path:
                print(f"  JSON: {record.json_path}")
        return 0

    if args.backup_now:
        with InstanceLock():
            record = safety_manager.backup_now(include_json=True)
        if record is None:
            print("A Library ainda não possui banco para backup.")
            return 0
        print(f"Backup SQLite: {record.sqlite_path}")
        if record.json_path:
            print(f"Backup JSON: {record.json_path}")
        return 0

    if args.restore_backup:
        try:
            with InstanceLock():
                restored = safety_manager.restore_database(args.restore_backup)
        except InstanceAlreadyRunningError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 4
        print(f"Library restaurada: {restored}")
        return 0

    chapter_cache = ChapterCache()
    cache_manager = CacheManager(chapter_cache.cache_root)

    if args.cache_status:
        stats = cache_manager.stats()
        print(f"Cache total: {CacheStats.human_size(stats.total_bytes)}")
        print(f"Capítulos: {CacheStats.human_size(stats.chapters_bytes)}")
        print(f"Capas: {CacheStats.human_size(stats.covers_bytes)}")
        print(f"Arquivos: {stats.files}")
        print(f"Limite: {app_config.cache_limit_mb} MB")
        print(f"Offline: {'sim' if app_config.offline_mode else 'não'}")
        return 0

    if args.cache_clear:
        if args.cache_clear == "chapters":
            count = cache_manager.clear_chapters()
        elif args.cache_clear == "covers":
            count = cache_manager.clear_covers()
        else:
            count = cache_manager.clear_all()
        print(f"{count} arquivo(s) removido(s) do cache.")
        return 0

    cache_manager.enforce_limit(app_config.cache_limit_mb)

    args.width = args.width if args.width is not None else app_config.terminal_width
    args.lines = args.lines if args.lines is not None else app_config.lines_per_page
    args.margin = args.margin if args.margin is not None else app_config.terminal_margin
    args.paragraph_spacing = (
        args.paragraph_spacing
        if args.paragraph_spacing is not None
        else app_config.paragraph_spacing
    )
    args.text_size = args.text_size or app_config.text_size
    args.ascii_width = args.ascii_width if args.ascii_width is not None else app_config.ascii_width

    if args.doctor:
        distro, results = run_diagnostics()
        print(
            format_doctor_report(
                distro,
                results,
                ansi=sys.stdout.isatty(),
            )
        )
        return 0 if overall_ok(results) else 2

    if args.setup:
        return run_setup(ansi=sys.stdout.isatty())

    try:
        instance_lock = InstanceLock()
        instance_lock.acquire()
    except InstanceAlreadyRunningError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 4

    import atexit as _atexit
    _atexit.register(instance_lock.release)

    if app_config.automatic_backups:
        try:
            record = safety_manager.auto_backup_if_due()
            if record:
                logger.info("Backup automático criado: %s", record.sqlite_path)
        except Exception:
            logger.exception("Falha no backup automático; execução continuará")

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
