"""File and stderr logging. Captured pixels are never written to the log."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False


def log_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "TexGrab"
    raw = os.environ.get("XDG_STATE_HOME", "").strip()
    base = Path(raw).expanduser() if raw else Path.home() / ".local" / "state"
    return base / "texgrab"


def log_path() -> Path:
    return log_dir() / "texgrab.log"


def get_logger() -> logging.Logger:
    return logging.getLogger("texgrab")


def configure_logging(debug: bool) -> logging.Logger:
    """Attach handlers once. Later calls only change the level."""
    global _configured
    logger = get_logger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False
    if _configured:
        return logger
    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(log_path(), maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream)
    _configured = True
    return logger


def set_debug(debug: bool) -> None:
    get_logger().setLevel(logging.DEBUG if debug else logging.INFO)
