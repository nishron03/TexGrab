#!/usr/bin/env python3
"""Run pix2tex on one image. Usage: smoke_ocr.py IMAGE [--clipboard]"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from texgrab.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["--test-ocr", *sys.argv[1:]]))
