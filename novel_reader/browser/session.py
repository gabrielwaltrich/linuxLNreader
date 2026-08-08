from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, QTimer, QUrl, Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

from novel_reader.errors import AccessRestrictedError, NovelReaderError, ParseError
from novel_reader.models import Book, Chapter
from novel_reader.sources.manager import SourceManager
from novel_reader.services.book_sync import merge_books


class BrowserSession(QObject):
    """Renderiza páginas em Chromium/QtWebEngine e entrega o DOM ao Source Engine.

    v0.3.1: em vez de esperar um tempo fixo, captura o DOM progressivamente. Isso
    reduz falhas quando frameworks JavaScript montam o capítulo após loadFinished.
    """

    loaded = Signal(object)
    book_loaded = Signal(object)
    dom_loaded = Signal(str, str)
    failed = Signal(str)
    status_changed = Signal(str)

    # Intervalos entre tentativas após loadFinished. A primeira captura ocorre
    # cedo; as seguintes dão tempo extra para hidratação/renderização dinâmica.
    CAPTURE_DELAYS_MS = (500, 900, 1400, 2000, 2800, 3500, 4500, 5500)
    BOOK_STABLE_CAPTURES = 2

    def __init__(self, manager: SourceManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._requested_url = ""
        self._busy = False
        self._generation = 0
        self._capture_index = 0
        self._last_parse_error = ""
        self._last_restricted_error = ""
        self._mode = "chapter"
        self._book_accumulator: Book | None = None
        self._book_last_count = 0
        self._book_stable_count = 0

        data_root = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        profile_root = Path(data_root) / "browser-profile"
        cache_root = Path(data_root) / "browser-cache"
        profile_root.mkdir(parents=True, exist_ok=True)
        cache_root.mkdir(parents=True, exist_ok=True)

        self.profile = QWebEngineProfile("NovelReader", self)
        self.profile.setPersistentStoragePath(str(profile_root))
        self.profile.setCachePath(str(cache_root))
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )

        self.page = QWebEnginePage(self.profile, self)
        self.page.loadStarted.connect(self._on_load_started)
        self.page.loadProgress.connect(self._on_load_progress)
        self.page.loadFinished.connect(self._on_load_finished)

        self.timeout_timer = QTimer(self)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._on_timeout)

        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self._capture_dom)

    @property
    def is_busy(self) -> bool:
        return self._busy

    def load(self, url: str) -> None:
        """Carrega um capítulo. Mantido compatível com v0.3-v0.5."""
        self._start_load(url, mode="chapter")

    def load_book(self, url: str) -> None:
        """Carrega a página raiz de uma obra para extrair metadados/índice."""
        self._start_load(url, mode="book")

    def load_dom(self, url: str) -> None:
        """Carrega uma página e devolve o DOM renderizado sem interpretá-lo."""
        self._start_load(url, mode="dom")

    def _start_load(self, url: str, *, mode: str) -> None:
        if self._busy:
            return

        self._busy = True
        self._generation += 1
        self._mode = mode
        self._requested_url = url
        self._capture_index = 0
        self._last_parse_error = ""
        self._last_restricted_error = ""
        self._book_accumulator = None
        self._book_last_count = 0
        self._book_stable_count = 0
        if mode == "book":
            self.status_changed.emit("Abrindo índice da obra no navegador embutido…")
        else:
            self.status_changed.emit("Abrindo página no navegador embutido…")
        self.timeout_timer.start(35_000)
        self.page.load(QUrl(url))

    def cancel(self) -> None:
        if not self._busy:
            return
        self.page.triggerAction(QWebEnginePage.WebAction.Stop)
        self._finish()

    def _on_load_started(self) -> None:
        self.status_changed.emit("Navegador: conectando…")

    def _on_load_progress(self, progress: int) -> None:
        self.status_changed.emit(f"Navegador: carregando… {progress}%")

    def _on_load_finished(self, ok: bool) -> None:
        if not self._busy:
            return
        if not ok:
            self._fail(
                "O navegador não conseguiu concluir o carregamento da página. "
                "Ela pode estar indisponível ou ter recusado a navegação."
            )
            return

        self.status_changed.emit("Página carregada; aguardando conteúdo dinâmico…")
        self._schedule_next_capture()

    def _schedule_next_capture(self) -> None:
        if not self._busy:
            return
        if self._capture_index >= len(self.CAPTURE_DELAYS_MS):
            self._fail_after_attempts()
            return

        delay = self.CAPTURE_DELAYS_MS[self._capture_index]
        attempt = self._capture_index + 1
        total = len(self.CAPTURE_DELAYS_MS)
        if self._mode == "book" and self._capture_index > 0:
            self._nudge_book_index()
        self.status_changed.emit(
            f"Aguardando conteúdo dinâmico… tentativa {attempt}/{total}"
        )
        self.render_timer.start(delay)

    def _capture_dom(self) -> None:
        if not self._busy:
            return

        generation = self._generation
        attempt = self._capture_index + 1
        total = len(self.CAPTURE_DELAYS_MS)
        self.status_changed.emit(f"Extraindo texto… tentativa {attempt}/{total}")

        def receive_html(html: str) -> None:
            if not self._busy or generation != self._generation:
                return

            final_url = self.page.url().toString() or self._requested_url
            if self._mode == "dom":
                self._finish()
                self.dom_loaded.emit(final_url, html)
                return

            try:
                if self._mode == "book":
                    result: Book | Chapter = self.manager.parse_rendered_book_html(
                        requested_url=self._requested_url,
                        final_url=final_url,
                        html=html,
                    )
                else:
                    result = self.manager.parse_rendered_html(
                        requested_url=self._requested_url,
                        final_url=final_url,
                        html=html,
                    )
            except AccessRestrictedError as exc:
                # Mesmo um marcador de acesso pode aparecer antes de o conteúdo
                # terminar de montar. Guardamos o diagnóstico e esperamos todas
                # as tentativas antes de apresentá-lo ao usuário.
                self._last_restricted_error = str(exc)
                self._capture_index += 1
                self._schedule_next_capture()
            except ParseError as exc:
                self._last_parse_error = str(exc)
                self._capture_index += 1
                self._schedule_next_capture()
            except NovelReaderError as exc:
                self._fail(str(exc))
            except Exception as exc:
                self._fail(f"Erro inesperado ao interpretar a página: {exc}")
            else:
                if self._mode == "book":
                    self._accept_book_capture(result)
                else:
                    self._finish()
                    self.loaded.emit(result)

        self.page.toHtml(receive_html)


    def _accept_book_capture(self, book: Book) -> None:
        self._book_accumulator = merge_books(self._book_accumulator, book)
        count = len(self._book_accumulator.chapters)

        if count > self._book_last_count:
            self._book_stable_count = 0
        else:
            self._book_stable_count += 1

        self._book_last_count = count
        self.status_changed.emit(
            f"Índice: {count} capítulos encontrados; verificando se há mais…"
        )

        self._capture_index += 1
        if self._book_stable_count >= self.BOOK_STABLE_CAPTURES:
            result = self._book_accumulator
            self._finish()
            self.book_loaded.emit(result)
            return

        if self._capture_index >= len(self.CAPTURE_DELAYS_MS):
            result = self._book_accumulator
            self._finish()
            self.book_loaded.emit(result)
            return

        self._schedule_next_capture()

    def _nudge_book_index(self) -> None:
        """Interage apenas com controles normais da página para revelar o TOC.

        Não contorna login/paywall. Tenta clicar botões visíveis de índice/load
        more e rolar contêineres/página para disparar lazy loading.
        """
        script = r"""
        (() => {
          const wanted = [
            'table of contents', 'contents', 'catalog',
            'load more', 'view more', 'show more', 'more chapters'
          ];
          const nodes = [...document.querySelectorAll('button, a, [role="button"]')];
          for (const node of nodes) {
            const text = (node.innerText || node.textContent || '').trim().toLowerCase();
            if (!text) continue;
            if (wanted.some(label => text === label || text.includes(label))) {
              const rect = node.getBoundingClientRect();
              const style = getComputedStyle(node);
              const visible = rect.width > 0 && rect.height > 0 &&
                              style.visibility !== 'hidden' && style.display !== 'none';
              if (visible) {
                try { node.click(); } catch (_) {}
              }
            }
          }

          const scrollables = [...document.querySelectorAll('*')].filter(el => {
            const style = getComputedStyle(el);
            return /(auto|scroll)/.test(style.overflowY) && el.scrollHeight > el.clientHeight + 100;
          });
          for (const el of scrollables.slice(0, 8)) {
            el.scrollTop = el.scrollHeight;
          }
          window.scrollTo(0, document.body.scrollHeight);
          return true;
        })();
        """
        self.page.runJavaScript(script)

    def _fail_after_attempts(self) -> None:
        if self._mode == "book" and self._book_accumulator is not None:
            result = self._book_accumulator
            self._finish()
            self.book_loaded.emit(result)
            return
        if self._last_restricted_error:
            self._fail(self._last_restricted_error)
            return
        if self._last_parse_error:
            self._fail(self._last_parse_error)
            return
        self._fail("Não foi possível identificar o conteúdo do capítulo.")

    def _on_timeout(self) -> None:
        if self._busy:
            self.page.triggerAction(QWebEnginePage.WebAction.Stop)
            self._fail("A página demorou mais de 35 segundos para carregar.")

    def _fail(self, message: str) -> None:
        self._finish()
        self.failed.emit(message)

    def _finish(self) -> None:
        self.timeout_timer.stop()
        self.render_timer.stop()
        self._busy = False
