from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess

from novel_reader.services.media_ascii import (
    ChafaBackend,
    MediaAsciiService,
    PillowAsciiBackend,
)


@dataclass(slots=True)
class CoverRender:
    mode: str
    label: str
    ascii_text: str = ""
    image_path: Path | None = None


class TerminalCoverRenderer:
    """Render book covers for a curses TUI.

    `kitty` uses kitten icat placement.
    `chafa` and `pillow` return text to be drawn by curses.
    """

    def __init__(self):
        self.media = MediaAsciiService()
        self._tty_fd: int | None = None

    @staticmethod
    def kitty_available() -> bool:
        if not shutil.which("kitten"):
            return False
        term = os.environ.get("TERM", "").casefold()
        return bool(os.environ.get("KITTY_WINDOW_ID")) or "kitty" in term

    @staticmethod
    def chafa_available() -> bool:
        return ChafaBackend.available()

    def resolve_mode(self, requested: str) -> str:
        requested = (requested or "auto").casefold()
        if requested == "off":
            return "off"
        if requested == "kitty":
            return "kitty" if self.kitty_available() else "chafa" if self.chafa_available() else "pillow"
        if requested == "chafa":
            return "chafa" if self.chafa_available() else "pillow"
        if requested == "pillow":
            return "pillow"
        # Auto
        if self.kitty_available():
            return "kitty"
        if self.chafa_available():
            return "chafa"
        return "pillow"

    def prepare(
        self,
        cover_url: str,
        requested: str,
        *,
        ascii_width: int = 34,
        ascii_height: int = 17,
    ) -> CoverRender:
        if not cover_url or requested == "off":
            return CoverRender(mode="off", label="sem capa")

        path = self.media.fetch(cover_url)
        mode = self.resolve_mode(requested)

        if mode == "kitty":
            return CoverRender(
                mode="kitty",
                label="Kitten icat",
                image_path=path,
            )

        if mode == "chafa":
            try:
                text = ChafaBackend().render(
                    path,
                    width=ascii_width,
                    height=ascii_height,
                )
                return CoverRender(
                    mode="chafa",
                    label="Chafa ASCII",
                    ascii_text=text,
                    image_path=path,
                )
            except Exception:
                mode = "pillow"

        text = PillowAsciiBackend().render(
            path,
            width=ascii_width,
            height=ascii_height,
        )
        return CoverRender(
            mode="pillow",
            label="Pillow ASCII",
            ascii_text=text,
            image_path=path,
        )

    def draw_kitty(
        self,
        *,
        image_path: Path,
        screen_cols: int,
        screen_rows: int,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> bool:
        executable = shutil.which("kitten")
        if not executable or not image_path:
            return False

        # We do not allow icat to read from the TTY. Kitty documents this
        # integration form for host applications: --stdin=no, explicit
        # --use-window-size, --place and --transfer-mode.
        command = [
            executable,
            "icat",
            "--stdin=no",
            "--use-window-size",
            f"{screen_cols},{screen_rows},1200,800",
            "--transfer-mode=stream",
            "--place",
            f"{max(1,width)}x{max(1,height)}@{max(0,left)}x{max(0,top)}",
            "--scale-up",
            "--align=center",
            str(image_path),
        ]

        try:
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
                start_new_session=True,
            )
            if proc.returncode != 0 or not proc.stdout:
                return False
            self._write_tty(proc.stdout)
            return True
        except Exception:
            return False

    def clear_kitty(self, *, screen_cols: int, screen_rows: int) -> None:
        executable = shutil.which("kitten")
        if not executable:
            return
        # --clear is emitted without interactive stdin access.
        command = [
            executable,
            "icat",
            "--stdin=no",
            "--use-window-size",
            f"{screen_cols},{screen_rows},1200,800",
            "--transfer-mode=stream",
            "--clear",
        ]
        try:
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=4,
                check=False,
                start_new_session=True,
            )
            if proc.stdout:
                self._write_tty(proc.stdout)
        except Exception:
            pass

    def _write_tty(self, data: bytes) -> None:
        if self._tty_fd is None:
            self._tty_fd = os.open("/dev/tty", os.O_WRONLY | os.O_NOCTTY)
        os.write(self._tty_fd, data)

    def close(self) -> None:
        if self._tty_fd is not None:
            try:
                os.close(self._tty_fd)
            except OSError:
                pass
            self._tty_fd = None
