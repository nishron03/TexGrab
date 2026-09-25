"""Local pix2tex engine.

The upstream LatexOCR call writes the prediction to the clipboard itself.
That write is disabled here so this process is the only clipboard owner and
an empty or failed result cannot clear what the user already copied.
"""

from __future__ import annotations

import logging
import os
import threading
import warnings
from pathlib import Path

os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")

from PIL import Image

from texgrab.log import get_logger
from texgrab.ocr.matrix import detect_matrix, fit_matrix
from texgrab.ocr.preprocess import prepare_image


def sample_equation_path() -> Path:
    return Path(__file__).resolve().parents[1] / "resources" / "sample_equation.png"


def _ignore_clipboard(*_args, **_kwargs) -> None:
    return None


class Pix2TexEngine:
    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            root = logging.getLogger()
            previous = root.level
            try:
                warnings.filterwarnings("ignore", category=UserWarning, module=r"pydantic(\..*)?")
                warnings.filterwarnings("ignore", category=FutureWarning, module=r"torch(\..*)?")
                from pix2tex.cli import LatexOCR

                get_logger().info("loading pix2tex model")
                # LatexOCR sets the root logger to FATAL while it loads.
                self._model = LatexOCR()
                checkpoint = getattr(getattr(self._model, "args", None), "checkpoint", "")
                get_logger().info("pix2tex model ready checkpoint=%s", checkpoint)
            finally:
                root.setLevel(previous)

    def recognize(self, image: Image.Image) -> str:
        self.load()
        prepared = prepare_image(image)
        import pix2tex.cli as cli

        original = cli.clipboard.copy
        cli.clipboard.copy = _ignore_clipboard
        try:
            return self._predict(prepared)
        finally:
            cli.clipboard.copy = original

    def _predict(self, prepared: Image.Image) -> str:
        layout = detect_matrix(prepared)
        if layout is None:
            return self._one(prepared)
        fitted = fit_matrix(prepared, len(layout.cells))
        get_logger().info(
            "matrix %sx%s %s scaled=%sx%s",
            len(layout.cells),
            len(layout.cells[0]) if layout.cells else 0,
            layout.environment,
            fitted.width,
            fitted.height,
        )
        # resize=False keeps the grid. The default resizer is for one line.
        return self._one(fitted, resize=False)

    def _one(self, image: Image.Image, resize: bool = True) -> str:
        text = self._model(image, resize=resize)
        if text is None:
            return ""
        return str(text).strip()
