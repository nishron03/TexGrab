"""The only thing the pipeline needs from an OCR engine."""

from __future__ import annotations

from typing import Protocol

from PIL import Image


class OCREngine(Protocol):
    def recognize(self, image: Image.Image) -> str:
        """Return a LaTeX string. Raise on failure. Empty string means no result."""
