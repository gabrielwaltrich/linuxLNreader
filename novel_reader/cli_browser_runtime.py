from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from novel_reader.errors import NovelReaderError
from novel_reader.models import Book, BookChapter, Chapter
from novel_reader.services.webnovel_ranking import RankingBook


class CliBrowserRuntime:
    """Persistent QtWebEngine worker with timeout-safe JSON RPC.

    The terminal process owns curses. The browser worker never owns or opens a
    terminal; it is only a background child process.
    """

    def __init__(self, *, timeout: float = 45.0):
        env = os.environ.copy()
        env.setdefault("QT_QPA_PLATFORM", "offscreen")

        # QtWebEngine headless mode is more reliable on common desktop Linux
        # installs with the sandbox disabled in this dedicated child process.
        # The worker is only used for pages the user explicitly asks to open.
        env.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

        self.timeout = float(timeout)
        self._closed = False
        self._request_id = 0
        self._lock = threading.Lock()
        self._responses: queue.Queue[str | None] = queue.Queue()

        self.process = subprocess.Popen(
            [sys.executable, "-m", "novel_reader.cli_browser_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
            start_new_session=True,
        )

        self._reader = threading.Thread(
            target=self._reader_loop,
            name="novel-reader-browser-rpc",
            daemon=True,
        )
        self._reader.start()
        atexit.register(self._close_at_exit)

    @property
    def alive(self) -> bool:
        return (
            not self._closed
            and getattr(self, "process", None) is not None
            and self.process.poll() is None
        )

    def _reader_loop(self) -> None:
        stdout = self.process.stdout
        if stdout is None:
            self._responses.put(None)
            return

        try:
            for line in stdout:
                self._responses.put(line)
        finally:
            self._responses.put(None)

    def _request(
        self,
        op: str,
        url: str = "",
        *,
        timeout: float | None = None,
        status_callback=None,
    ) -> dict:
        if self._closed:
            raise NovelReaderError("O navegador já foi encerrado.")

        with self._lock:
            if not self.alive:
                raise NovelReaderError(
                    f"O processo do navegador terminou inesperadamente "
                    f"(código {self.process.returncode})."
                )

            self._request_id += 1
            request_id = self._request_id

            payload = {"id": request_id, "op": op}
            if url:
                payload["url"] = url

            stdin = self.process.stdin
            if stdin is None:
                raise NovelReaderError("stdin do navegador não está disponível.")

            try:
                stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise NovelReaderError(
                    "O processo persistente do navegador foi encerrado."
                ) from exc

            wait = self.timeout if timeout is None else float(timeout)

            while True:
                try:
                    line = self._responses.get(timeout=wait)
                except queue.Empty as exc:
                    self._terminate_worker()
                    raise NovelReaderError(
                        f"O navegador não respondeu em {int(wait)} segundos."
                    ) from exc

                if line is None:
                    raise NovelReaderError(
                        f"O navegador encerrou durante a operação "
                        f"(código {self.process.poll()})."
                    )

                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if response.get("id") != request_id:
                    continue

                if response.get("type") == "status":
                    if status_callback is not None:
                        try:
                            status_callback(str(response.get("message") or ""))
                        except Exception:
                            pass
                    continue

                if not response.get("ok"):
                    raise NovelReaderError(
                        str(response.get("error") or "Falha no navegador.")
                    )

                return response.get("data") or {}

    def load_book(self, url: str, status_callback=None) -> Book:
        data = self._request(
            "book",
            url,
            status_callback=status_callback,
        )
        return Book(
            source=data.get("source", ""),
            url=data.get("url", url),
            title=data.get("title", ""),
            source_id=data.get("source_id", ""),
            author=data.get("author", ""),
            synopsis=data.get("synopsis", ""),
            cover_url=data.get("cover_url", ""),
            chapters=[
                BookChapter(
                    source=item.get("source", ""),
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    position=item.get("position"),
                    source_id=item.get("source_id", ""),
                    accessible=item.get("accessible"),
                )
                for item in data.get("chapters", [])
            ],
        )

    def load_chapter(self, url: str, status_callback=None) -> Chapter:
        data = self._request(
            "chapter",
            url,
            status_callback=status_callback,
        )
        return Chapter(
            source=data.get("source", ""),
            url=data.get("url", url),
            book_title=data.get("book_title", ""),
            chapter_title=data.get("chapter_title", ""),
            text=data.get("text", ""),
            previous_url=data.get("previous_url"),
            next_url=data.get("next_url"),
        )

    def load_dom(self, url: str) -> tuple[str, str]:
        data = self._request("dom", url)
        return data.get("final_url", url), data.get("html", "")

    def load_ranking(self, url: str, status_callback=None) -> list[RankingBook]:
        data = self._request(
            "ranking",
            url,
            timeout=max(self.timeout, 60.0),
            status_callback=status_callback,
        )
        return [
            RankingBook(
                rank=int(item.get("rank", 0)),
                title=item.get("title", ""),
                url=item.get("url", ""),
                author=item.get("author", ""),
                synopsis=item.get("synopsis", ""),
                cover_url=item.get("cover_url", ""),
                score_text=item.get("score_text", ""),
            )
            for item in data.get("books", [])
            if item.get("url")
        ]

    def _terminate_worker(self) -> None:
        if getattr(self, "process", None) is None:
            return
        if self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        if getattr(self, "process", None) is None:
            return

        if self.process.poll() is None:
            # Never call blocking _request("quit") during shutdown. A dead or
            # wedged worker must not be allowed to freeze the user's terminal.
            try:
                stdin = self.process.stdin
                if stdin is not None:
                    self._request_id += 1
                    stdin.write(
                        json.dumps(
                            {"id": self._request_id, "op": "quit"}
                        ) + "\n"
                    )
                    stdin.flush()
            except Exception:
                pass

            try:
                self.process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                self._terminate_worker()

    def _close_at_exit(self) -> None:
        try:
            self.close()
        except BaseException:
            # atexit must never emit a traceback or block terminal restoration.
            pass
