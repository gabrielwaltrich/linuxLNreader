from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, QTimer, QUrl, Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

from novel_reader.errors import AccessRestrictedError, NovelReaderError, ParseError
from novel_reader.models import Chapter
from novel_reader.sources.manager import SourceManager


class BrowserSession(QObject):
    """Renderiza páginas em Chromium/QtWebEngine e entrega o DOM ao Source Engine.

    v0.3.1: em vez de esperar um tempo fixo, captura o DOM progressivamente. Isso
    reduz falhas quando frameworks JavaScript montam o capítulo após loadFinished.
    """

    loaded = Signal(object)
    failed = Signal(str)
    status_changed = Signal(str)

    # Intervalos entre tentativas após loadFinished. A primeira captura ocorre
    # cedo; as seguintes dão tempo extra para hidratação/renderização dinâmica.
    CAPTURE_DELAYS_MS = (500, 1000, 2000, 4000)

    def __init__(self, manager: SourceManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._requested_url = ""
        self._busy = False
        self._generation = 0
        self._capture_index = 0
        self._last_parse_error = ""
        self._last_restricted_error = ""

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
        if self._busy:
            return

        self._busy = True
        self._generation += 1
        self._requested_url = url
        self._capture_index = 0
        self._last_parse_error = ""
        self._last_restricted_error = ""
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
            try:
                chapter: Chapter = self.manager.parse_rendered_html(
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
                self._finish()
                self.loaded.emit(chapter)

        self.page.toHtml(receive_html)

    def _fail_after_attempts(self) -> None:
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
