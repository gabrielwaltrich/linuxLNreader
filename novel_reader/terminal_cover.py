from __future__ import annotations

from dataclasses import dataclass
import array
import fcntl
import os
from pathlib import Path
import shutil
import struct
import subprocess
import termios

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


@dataclass(slots=True)
class KittyDiagnostics:
    kitten_path: str = ""
    terminal_name: str = ""
    kitty_window_id: str = ""
    tmux: bool = False
    screen: bool = False
    cols: int = 0
    rows: int = 0
    pixel_width: int = 0
    pixel_height: int = 0
    usable: bool = False
    reason: str = ""


class TerminalCoverRenderer:
    """Render covers for curses.

    Kitty mode uses kitten icat as a pure escape-code backend:
    --stdin=no + --use-window-size + --place + --transfer-mode=file.
    """

    def __init__(self):
        self.media = MediaAsciiService()
        self._tty_fd: int | None = None

    @staticmethod
    def _kitten_path() -> str:
        return shutil.which("kitten") or ""

    @staticmethod
    def _terminal_name() -> str:
        values = (
            os.environ.get("TERM_PROGRAM", ""),
            os.environ.get("TERM", ""),
            os.environ.get("LC_TERMINAL", ""),
        )
        return " / ".join(value for value in values if value)

    @classmethod
    def kitty_available(cls) -> bool:
        """Conservative but not Kitty-only detection.

        The graphics protocol is also implemented by some non-Kitty terminals.
        If `kitten` exists, explicit Kitty variables are accepted immediately.
        For other terminals, the user can still force the `kitty` backend from
        the menu; draw_kitty() will report whether escape generation succeeded.
        """
        if not cls._kitten_path():
            return False

        if os.environ.get("KITTY_WINDOW_ID"):
            return True

        terminal = cls._terminal_name().casefold()
        known_protocol_terms = (
            "kitty",
            "wezterm",
            "ghostty",
        )
        return any(name in terminal for name in known_protocol_terms)

    @staticmethod
    def chafa_available() -> bool:
        return ChafaBackend.available()

    def window_size(self) -> tuple[int, int, int, int]:
        """Return cols, rows, pixel_width, pixel_height from the real TTY."""
        fd = None
        try:
            fd = os.open("/dev/tty", os.O_RDONLY | os.O_NOCTTY)
            buf = array.array("H", [0, 0, 0, 0])
            fcntl.ioctl(fd, termios.TIOCGWINSZ, buf, True)
            rows, cols, pixel_width, pixel_height = map(int, buf)
        except Exception:
            rows = cols = pixel_width = pixel_height = 0
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

        # Curses callers also pass cell dimensions. Some terminals return 0
        # pixels. In that case use a sane cell estimate rather than the old
        # fixed 1200x800 window.
        return cols, rows, pixel_width, pixel_height

    def diagnostics(
        self,
        *,
        screen_cols: int = 0,
        screen_rows: int = 0,
    ) -> KittyDiagnostics:
        kitten = self._kitten_path()
        cols, rows, px_w, px_h = self.window_size()

        cols = cols or int(screen_cols or 0)
        rows = rows or int(screen_rows or 0)

        if cols and not px_w:
            px_w = cols * 10
        if rows and not px_h:
            px_h = rows * 20

        terminal = self._terminal_name()
        tmux = bool(os.environ.get("TMUX"))
        screen = (os.environ.get("TERM", "").casefold().startswith("screen"))

        usable = bool(kitten and cols and rows and px_w and px_h)
        reason = ""
        if not kitten:
            reason = "executável 'kitten' não encontrado no PATH"
        elif not cols or not rows:
            reason = "não foi possível determinar o tamanho do terminal"
        elif tmux:
            reason = (
                "tmux detectado; o protocolo gráfico depende do passthrough "
                "suportado pela versão/configuração do tmux"
            )
        elif screen:
            reason = (
                "GNU screen detectado; suporte ao protocolo gráfico pode ser "
                "indisponível"
            )
        elif not self.kitty_available():
            reason = (
                "terminal não identificado automaticamente como compatível; "
                "o modo Kitten pode ser forçado manualmente"
            )
        else:
            reason = "pronto"

        return KittyDiagnostics(
            kitten_path=kitten,
            terminal_name=terminal,
            kitty_window_id=os.environ.get("KITTY_WINDOW_ID", ""),
            tmux=tmux,
            screen=screen,
            cols=cols,
            rows=rows,
            pixel_width=px_w,
            pixel_height=px_h,
            usable=usable,
            reason=reason,
        )

    def resolve_mode(self, requested: str) -> str:
        requested = (requested or "auto").casefold()
        if requested == "off":
            return "off"

        # Explicit kitty is allowed whenever `kitten` exists. This makes the
        # feature usable on terminals implementing Kitty graphics without
        # advertising themselves as Kitty.
        if requested == "kitty":
            if self._kitten_path():
                return "kitty"
            return "chafa" if self.chafa_available() else "pillow"

        if requested == "chafa":
            return "chafa" if self.chafa_available() else "pillow"
        if requested == "pillow":
            return "pillow"

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

    def _window_size_for_icat(
        self,
        *,
        screen_cols: int,
        screen_rows: int,
    ) -> tuple[int, int, int, int]:
        cols, rows, px_w, px_h = self.window_size()
        cols = cols or max(1, int(screen_cols))
        rows = rows or max(1, int(screen_rows))

        # The graphics protocol needs real pixel dimensions for correct cell
        # geometry. Fall back to per-cell estimates only when ioctl returned 0.
        px_w = px_w or cols * 10
        px_h = px_h or rows * 20
        return cols, rows, px_w, px_h

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
        executable = self._kitten_path()
        if not executable or not image_path:
            return False

        cols, rows, px_w, px_h = self._window_size_for_icat(
            screen_cols=screen_cols,
            screen_rows=screen_rows,
        )

        command = [
            executable,
            "icat",
            "--stdin=no",
            "--use-window-size",
            f"{cols},{rows},{px_w},{px_h}",
            "--transfer-mode=file",
            "--place",
            f"{max(1,width)}x{max(1,height)}@{max(0,left)}x{max(0,top)}",
            "--scale-up",
            "--align=center",
            str(image_path),
        ]

        try:
            proc = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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

    def clear_kitty(
        self,
        *,
        screen_cols: int,
        screen_rows: int,
    ) -> None:
        executable = self._kitten_path()
        if not executable:
            return

        cols, rows, px_w, px_h = self._window_size_for_icat(
            screen_cols=screen_cols,
            screen_rows=screen_rows,
        )
        command = [
            executable,
            "icat",
            "--stdin=no",
            "--use-window-size",
            f"{cols},{rows},{px_w},{px_h}",
            "--transfer-mode=file",
            "--clear",
        ]
        try:
            proc = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
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
            self._tty_fd = os.open(
                "/dev/tty",
                os.O_WRONLY | os.O_NOCTTY,
            )
        os.write(self._tty_fd, data)

    def close(self) -> None:
        if self._tty_fd is not None:
            try:
                os.close(self._tty_fd)
            except OSError:
                pass
            self._tty_fd = None
