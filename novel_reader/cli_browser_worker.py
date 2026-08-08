from __future__ import annotations

import json
import os
import sys
import traceback

# Headless Qt is set before importing Qt modules.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QSocketNotifier, Slot
from PySide6.QtWidgets import QApplication

from novel_reader.browser import BrowserSession
from novel_reader.sources import SourceManager


class BrowserWorker(QObject):
    """JSON-lines RPC server backed by one persistent BrowserSession.

    stdin:
      {"id": 1, "op": "book", "url": "..."}
      {"id": 2, "op": "chapter", "url": "..."}
      {"id": 3, "op": "dom", "url": "..."}
      {"id": 4, "op": "quit"}

    stdout:
      {"id": 1, "ok": true, "data": {...}}
    """

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.manager = SourceManager()
        self.session = BrowserSession(self.manager)
        self.pending: dict | None = None

        self.session.loaded.connect(self._chapter_loaded)
        self.session.book_loaded.connect(self._book_loaded)
        self.session.dom_loaded.connect(self._dom_loaded)
        self.session.ranking_loaded.connect(self._ranking_loaded)
        self.session.failed.connect(self._failed)
        self.session.status_changed.connect(self._status)

        self.notifier = QSocketNotifier(
            sys.stdin.fileno(),
            QSocketNotifier.Type.Read,
            self,
        )
        self.notifier.activated.connect(self._read_command)

    def _emit_status(self, message: str) -> None:
        try:
            request_id = None
            if isinstance(getattr(self, "pending", None), dict):
                request_id = self.pending.get("id")
            sys.stdout.write(
                json.dumps(
                    {
                        "id": request_id,
                        "type": "status",
                        "message": str(message),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            sys.stdout.flush()
        except Exception:
            pass

    def _send(self, payload: dict) -> None:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _status(self, message: str) -> None:
        # Keep stdout strictly machine-readable.
        sys.stderr.write(f"[browser] {message}\n")
        sys.stderr.flush()

    @Slot()
    def _read_command(self) -> None:
        line = sys.stdin.readline()
        if not line:
            self.app.quit()
            return

        try:
            command = json.loads(line)
        except Exception as exc:
            self._send({"id": None, "ok": False, "error": f"JSON inválido: {exc}"})
            return

        op = command.get("op")
        request_id = command.get("id")

        if op == "quit":
            self._send({"id": request_id, "ok": True, "data": {"bye": True}})
            self.app.quit()
            return

        if self.pending is not None or self.session.is_busy:
            self._send({
                "id": request_id,
                "ok": False,
                "error": "O navegador ainda está processando outra solicitação.",
            })
            return

        url = str(command.get("url") or "").strip()
        if not url:
            self._send({"id": request_id, "ok": False, "error": "URL vazia."})
            return

        self.pending = {"id": request_id, "op": op, "url": url}

        try:
            if op == "book":
                self.session.load_book(url)
            elif op == "chapter":
                self.session.load(url)
            elif op == "dom":
                self.session.load_dom(url)
            elif op == "ranking":
                self.session.load_ranking(url)
            else:
                self.pending = None
                self._send({
                    "id": request_id,
                    "ok": False,
                    "error": f"Operação desconhecida: {op}",
                })
        except Exception as exc:
            self.pending = None
            self._send({
                "id": request_id,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            })

    def _finish(self, *, data=None, error: str | None = None) -> None:
        pending = self.pending
        self.pending = None
        if not pending:
            return
        if error is not None:
            self._send({"id": pending["id"], "ok": False, "error": error})
        else:
            self._send({"id": pending["id"], "ok": True, "data": data})

    def _chapter_loaded(self, chapter) -> None:
        self._finish(data={
            "source": chapter.source,
            "url": chapter.url,
            "book_title": chapter.book_title,
            "chapter_title": chapter.chapter_title,
            "text": chapter.text,
            "previous_url": chapter.previous_url,
            "next_url": chapter.next_url,
        })

    def _book_loaded(self, book) -> None:
        self._finish(data={
            "source": book.source,
            "url": book.url,
            "title": book.title,
            "source_id": book.source_id,
            "author": book.author,
            "synopsis": book.synopsis,
            "cover_url": book.cover_url,
            "chapters": [
                {
                    "source": chapter.source,
                    "url": chapter.url,
                    "title": chapter.title,
                    "position": chapter.position,
                    "source_id": chapter.source_id,
                    "accessible": chapter.accessible,
                }
                for chapter in book.chapters
            ],
        })

    def _dom_loaded(self, final_url: str, html: str) -> None:
        self._finish(data={"final_url": final_url, "html": html})

    def _ranking_loaded(self, books) -> None:
        self._finish(data={
            "books": [
                {
                    "rank": item.rank,
                    "title": item.title,
                    "url": item.url,
                    "author": item.author,
                    "synopsis": item.synopsis,
                    "cover_url": item.cover_url,
                    "score_text": item.score_text,
                }
                for item in books
            ]
        })

    def _failed(self, message: str) -> None:
        self._finish(error=message)


def main() -> int:
    app = QApplication(sys.argv)
    worker = BrowserWorker(app)
    app._novel_reader_worker = worker
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
