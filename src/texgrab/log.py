"""File and stderr logging. Captured pixels are never written to the log."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path.home() / "Library" / "Logs" / "TexGrab"
LOG_PATH = LOG_DIR / "texgrab.log"

_configured = False


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
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream)
    _configured = True
    return logger


def set_debug(debug: bool) -> None:
    get_logger().setLevel(logging.DEBUG if debug else logging.INFO)
