from __future__ import annotations
from dataclasses import dataclass
import os
import shutil
import textwrap


@dataclass(slots=True)
class TerminalReaderSettings:
    width: int = 82
    lines_per_page: int = 24
    margin: int = 2
    paragraph_spacing: int = 1
    text_size: str = "normal"

    def normalized(self) -> "TerminalReaderSettings":
        width = max(30, min(int(self.width), 160))
        lines = max(5, min(int(self.lines_per_page), 80))
        margin = max(0, min(int(self.margin), 12))
        spacing = max(0, min(int(self.paragraph_spacing), 3))
        preset = self.text_size if self.text_size in {"small","normal","large"} else "normal"
        # "text_size" is density, because actual terminal font size belongs to terminal emulator.
        if preset == "small":
            width = max(width, 100); lines = max(lines, 32)
        elif preset == "large":
            width = min(width, 68); lines = min(lines, 20)
        return TerminalReaderSettings(width, lines, margin, spacing, preset)


def format_chapter_text(title: str, text: str, settings: TerminalReaderSettings) -> list[str]:
    s = settings.normalized()
    usable = max(20, s.width - 2*s.margin)
    prefix = " " * s.margin
    lines: list[str] = []
    if title:
        lines.extend([prefix + line for line in textwrap.wrap(title, usable) or [title]])
        lines.append("")
    paragraphs = re_split_paragraphs(text)
    for i, paragraph in enumerate(paragraphs):
        wrapped = textwrap.wrap(paragraph, usable, replace_whitespace=True, drop_whitespace=True) or [""]
        lines.extend(prefix + line for line in wrapped)
        if i < len(paragraphs)-1:
            lines.extend([""] * s.paragraph_spacing)
    return lines


def re_split_paragraphs(text: str) -> list[str]:
    text = (text or "").replace("\r\n","\n").replace("\r","\n")
    parts = [p.strip().replace("\n"," ") for p in text.split("\n\n") if p.strip()]
    return parts or [""]


def paginate_lines(lines: list[str], lines_per_page: int) -> list[list[str]]:
    n = max(1, int(lines_per_page))
    return [lines[i:i+n] for i in range(0, len(lines), n)] or [[]]


def paginate_chapter(title: str, text: str, settings: TerminalReaderSettings) -> list[str]:
    s = settings.normalized()
    lines = format_chapter_text(title, text, s)
    return ["\n".join(page) for page in paginate_lines(lines, s.lines_per_page)]


def interactive_read(title: str, text: str, settings: TerminalReaderSettings, *, input_fn=input, output_fn=print, clear=True, start_page: int = 0) -> int:
    pages = paginate_chapter(title, text, settings)
    index = max(0, min(int(start_page), len(pages) - 1))
    while True:
        if clear:
            os.system("cls" if os.name == "nt" else "clear")
        output_fn(pages[index])
        output_fn(f"\n── página {index+1}/{len(pages)} ──  [n] próxima  [p] anterior  [q] sair  [g N] ir")
        try:
            command = input_fn("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return index
        if command in {"q","quit","s","sair"}:
            return index
        if command in {"","n","next"} and index < len(pages)-1:
            index += 1
        elif command in {"p","prev","previous"} and index > 0:
            index -= 1
        elif command.startswith("g "):
            try:
                target = int(command.split(maxsplit=1)[1]) - 1
                if 0 <= target < len(pages):
                    index = target
            except ValueError:
                pass


def page_index_from_progress(progress: int, page_count: int) -> int:
    if page_count <= 1:
        return 0
    progress = max(0, min(int(progress), 100))
    return min(page_count - 1, int((progress / 100) * page_count))


def progress_from_page(page_index: int, page_count: int) -> int:
    if page_count <= 0:
        return 0
    page_index = max(0, min(int(page_index), page_count - 1))
    return max(1, min(100, round(((page_index + 1) / page_count) * 100)))
