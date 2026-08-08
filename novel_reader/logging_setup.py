from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import tempfile


LOGGER_NAME = "novel_reader"


@dataclass(slots=True)
class LoggingContext:
    state_dir: Path
    log_file: Path
    debug: bool


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base).expanduser() / "novel-reader"
    return Path.home() / ".local" / "state" / "novel-reader"


def _fallback_state_dir() -> Path:
    uid = getattr(os, "getuid", lambda: 0)()
    return Path(tempfile.gettempdir()) / f"novel-reader-{uid}"


def configure_logging(*, debug: bool = False) -> LoggingContext:
    directory = state_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except (OSError, PermissionError):
        directory = _fallback_state_dir()
        directory.mkdir(parents=True, exist_ok=True)

    log_file = directory / "novel-reader.log"

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    # Idempotent: avoid duplicate handlers when CLI/GUI/bootstrap all call it.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
    )
    logger.addHandler(file_handler)

    if debug:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.DEBUG)
        stderr_handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(message)s")
        )
        logger.addHandler(stderr_handler)

    logger.info(
        "Logging iniciado | debug=%s | pid=%s",
        debug,
        os.getpid(),
    )

    return LoggingContext(
        state_dir=directory,
        log_file=log_file,
        debug=debug,
    )


def get_logger(name: str | None = None) -> logging.Logger:
    if not name:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def current_log_file() -> Path:
    return state_dir() / "novel-reader.log"
