from __future__ import annotations

from dataclasses import dataclass
import ctypes.util
import importlib.util
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import sys
import tempfile

from novel_reader import __version__


@dataclass(slots=True)
class CheckResult:
    key: str
    label: str
    ok: bool
    detail: str = ""
    required: bool = True
    suggestion: str = ""


@dataclass(slots=True)
class DistroInfo:
    distro_id: str = "unknown"
    name: str = "Linux"
    version_id: str = ""
    package_manager: str = ""


def detect_distro() -> DistroInfo:
    values: dict[str, str] = {}
    path = Path("/etc/os-release")
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')

    distro_id = values.get("ID", "unknown").casefold()
    name = values.get("PRETTY_NAME") or values.get("NAME") or platform.system()
    version = values.get("VERSION_ID", "")

    manager = ""
    for candidate in ("apt", "dnf", "pacman", "zypper"):
        if shutil.which(candidate):
            manager = candidate
            break

    return DistroInfo(
        distro_id=distro_id,
        name=name,
        version_id=version,
        package_manager=manager,
    )


def install_hint(package: str, distro: DistroInfo) -> str:
    manager = distro.package_manager
    mapping = {
        "apt": {
            "python": "sudo apt install python3 python3-venv python3-pip",
            "xcb": "sudo apt install libxcb-cursor0",
            "chafa": "sudo apt install chafa",
            "kitty": "sudo apt install kitty",
        },
        "dnf": {
            "python": "sudo dnf install python3 python3-pip",
            "xcb": "sudo dnf install xcb-util-cursor",
            "chafa": "sudo dnf install chafa",
            "kitty": "sudo dnf install kitty",
        },
        "pacman": {
            "python": "sudo pacman -S python python-pip",
            "xcb": "sudo pacman -S xcb-util-cursor",
            "chafa": "sudo pacman -S chafa",
            "kitty": "sudo pacman -S kitty",
        },
        "zypper": {
            "python": "sudo zypper install python3 python3-pip",
            "xcb": "sudo zypper install libxcb-cursor0",
            "chafa": "sudo zypper install chafa",
            "kitty": "sudo zypper install kitty",
        },
    }
    return mapping.get(manager, {}).get(package, "")


def _module_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _writable_dir(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".novel-reader-", delete=True):
            pass
        return True, str(path)
    except Exception as exc:
        return False, f"{path}: {exc}"


def _database_check(path: Path) -> tuple[bool, str]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path)
        try:
            db.execute("CREATE TABLE IF NOT EXISTS _doctor_check (id INTEGER)")
            db.commit()
        finally:
            db.close()
        return True, str(path)
    except Exception as exc:
        return False, f"{path}: {exc}"


def terminal_graphics_detail() -> tuple[bool, str]:
    terminal = " / ".join(
        value for value in (
            os.environ.get("TERM_PROGRAM", ""),
            os.environ.get("TERM", ""),
            os.environ.get("LC_TERMINAL", ""),
        ) if value
    ) or "desconhecido"

    kitty = bool(os.environ.get("KITTY_WINDOW_ID")) or "kitty" in terminal.casefold()
    compatible = kitty or any(
        name in terminal.casefold()
        for name in ("wezterm", "ghostty")
    )
    if compatible:
        return True, terminal
    return False, terminal


def run_diagnostics() -> tuple[DistroInfo, list[CheckResult]]:
    distro = detect_distro()

    state_dir = Path.home() / ".local" / "state" / "novel-reader"
    cache_dir = Path.home() / ".cache" / "novel-reader"
    data_dir = Path.home() / ".local" / "share" / "novel-reader"
    db_path = data_dir / "library.sqlite3"

    py_ok = sys.version_info >= (3, 10)
    py_detail = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    sqlite_ok = sqlite3.sqlite_version_info >= (3, 24, 0)
    graphics_ok, graphics_detail = terminal_graphics_detail()

    xcb = ctypes.util.find_library("xcb")
    xcb_cursor = ctypes.util.find_library("xcb-cursor") or ctypes.util.find_library("xcb_cursor")

    cache_ok, cache_detail = _writable_dir(cache_dir)
    state_ok, state_detail = _writable_dir(state_dir)
    db_ok, db_detail = _database_check(db_path)

    results = [
        CheckResult(
            "version",
            "Novel Reader",
            True,
            __version__,
            required=True,
        ),
        CheckResult(
            "python",
            "Python >= 3.10",
            py_ok,
            py_detail,
            required=True,
            suggestion=install_hint("python", distro),
        ),
        CheckResult(
            "sqlite",
            "SQLite",
            sqlite_ok,
            sqlite3.sqlite_version,
            required=True,
        ),
        CheckResult(
            "pyside6",
            "PySide6",
            _module_exists("PySide6"),
            "módulo Python",
            required=True,
            suggestion="python -m pip install PySide6",
        ),
        CheckResult(
            "qtwebengine",
            "QtWebEngine",
            _module_exists("PySide6.QtWebEngineWidgets"),
            "PySide6.QtWebEngineWidgets",
            required=True,
            suggestion="python -m pip install PySide6",
        ),
        CheckResult(
            "pillow",
            "Pillow",
            _module_exists("PIL"),
            "módulo PIL",
            required=True,
            suggestion="python -m pip install Pillow",
        ),
        CheckResult(
            "xcb",
            "libxcb",
            bool(xcb),
            xcb or "não encontrada",
            required=True,
            suggestion=install_hint("xcb", distro),
        ),
        CheckResult(
            "xcb_cursor",
            "xcb-cursor",
            bool(xcb_cursor),
            xcb_cursor or "não encontrada",
            required=True,
            suggestion=install_hint("xcb", distro),
        ),
        CheckResult(
            "chafa",
            "Chafa",
            bool(shutil.which("chafa")),
            shutil.which("chafa") or "não instalado",
            required=False,
            suggestion=install_hint("chafa", distro),
        ),
        CheckResult(
            "kitten",
            "Kitten icat",
            bool(shutil.which("kitten")),
            shutil.which("kitten") or "não instalado",
            required=False,
            suggestion=install_hint("kitty", distro),
        ),
        CheckResult(
            "terminal_graphics",
            "Terminal graphics",
            graphics_ok,
            graphics_detail,
            required=False,
            suggestion="Use Kitty/WezTerm/Ghostty ou selecione Chafa no Reader.",
        ),
        CheckResult(
            "database",
            "Database",
            db_ok,
            db_detail,
            required=True,
        ),
        CheckResult(
            "cache",
            "Cache writable",
            cache_ok,
            cache_detail,
            required=True,
        ),
        CheckResult(
            "state",
            "State/log dir",
            state_ok,
            state_detail,
            required=True,
        ),
    ]
    return distro, results


def overall_ok(results: list[CheckResult]) -> bool:
    return all(item.ok for item in results if item.required)


def format_doctor_report(
    distro: DistroInfo,
    results: list[CheckResult],
    *,
    ansi: bool = True,
) -> str:
    green = "\033[32m" if ansi else ""
    yellow = "\033[33m" if ansi else ""
    red = "\033[31m" if ansi else ""
    bold = "\033[1m" if ansi else ""
    reset = "\033[0m" if ansi else ""

    lines = [
        f"{bold}Novel Reader Doctor{reset}",
        f"Sistema: {distro.name}",
        f"Gerenciador: {distro.package_manager or 'não detectado'}",
        "",
    ]

    width = max(len(item.label) for item in results) + 2

    for item in results:
        if item.ok:
            icon = f"{green}✓{reset}"
        elif item.required:
            icon = f"{red}✗{reset}"
        else:
            icon = f"{yellow}!{reset}"

        required_text = "" if item.required else " (opcional)"
        detail = f" — {item.detail}" if item.detail else ""
        lines.append(
            f"{item.label + required_text:<{width + 11}} {icon}{detail}"
        )

    missing = [item for item in results if not item.ok and item.suggestion]
    if missing:
        lines += ["", f"{bold}Sugestões{reset}"]
        seen = set()
        for item in missing:
            if item.suggestion in seen:
                continue
            seen.add(item.suggestion)
            lines.append(f"- {item.label}: {item.suggestion}")

    lines += [
        "",
        (
            f"{green}Ambiente pronto para o Novel Reader.{reset}"
            if overall_ok(results)
            else f"{red}Há dependências obrigatórias pendentes.{reset}"
        ),
    ]
    return "\n".join(lines)
