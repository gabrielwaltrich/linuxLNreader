from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path
import platform
import shutil

from novel_reader.system_diagnostics import detect_distro


@dataclass(slots=True)
class CompatibilityReport:
    distro: str
    distro_id: str
    kernel: str
    python: str
    terminal: str
    term_program: str
    kitty_window_id: bool
    tmux: bool
    screen: bool
    chafa: bool
    kitten: bool

    def as_dict(self) -> dict:
        return asdict(self)


def collect_compatibility_report() -> CompatibilityReport:
    distro = detect_distro()
    term = os.environ.get("TERM", "")
    return CompatibilityReport(
        distro=distro.name,
        distro_id=distro.distro_id,
        kernel=platform.release(),
        python=platform.python_version(),
        terminal=term,
        term_program=os.environ.get("TERM_PROGRAM", ""),
        kitty_window_id=bool(os.environ.get("KITTY_WINDOW_ID")),
        tmux=bool(os.environ.get("TMUX")),
        screen=term.startswith("screen"),
        chafa=bool(shutil.which("chafa")),
        kitten=bool(shutil.which("kitten")),
    )


def format_compatibility_report(report: CompatibilityReport) -> str:
    yn=lambda v: "sim" if v else "não"
    return "\n".join([
        "Novel Reader — Relatório de compatibilidade", "",
        f"Distro: {report.distro}", f"ID: {report.distro_id}",
        f"Kernel: {report.kernel}", f"Python: {report.python}",
        f"TERM: {report.terminal or '—'}", f"TERM_PROGRAM: {report.term_program or '—'}",
        f"KITTY_WINDOW_ID: {yn(report.kitty_window_id)}", f"tmux: {yn(report.tmux)}",
        f"screen: {yn(report.screen)}", f"Chafa: {yn(report.chafa)}", f"kitten: {yn(report.kitten)}",
    ])


def write_compatibility_report(path: str | Path) -> Path:
    path=Path(path).expanduser(); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(collect_compatibility_report().as_dict(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return path
