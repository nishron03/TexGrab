"""python -m texgrab"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from texgrab import __version__
from texgrab.config import load_config
from texgrab.log import configure_logging, get_logger
from texgrab.ocr.pix2tex_engine import Pix2TexEngine
from texgrab.pipeline import run_image


def _check() -> int:
    version = sys.version.split()[0]
    print(f"python={version}")
    print(f"prefix={sys.prefix}")
    print(f"executable={sys.executable}")
    print(f"texgrab={__version__}")
    ok = True
    if Path(sys.prefix).name != "latex-snipper":
        print("warning=not running inside the latex-snipper conda env", file=sys.stderr)
        ok = False
    if not version.startswith("3.11"):
        print("warning=Python 3.11 is required", file=sys.stderr)
        ok = False
    if __version__ != "0.1.0":
        print("warning=texgrab 0.1.0 is required", file=sys.stderr)
        ok = False
    return 0 if ok else 1


def _test_ocr(path_str: str, use_clipboard: bool) -> int:
    path = Path(path_str).expanduser()
    if not path.is_file():
        get_logger().error("image not found")
        print("image not found", file=sys.stderr)
        return 1
    with Image.open(path) as image:
        image.load()
        loaded = image.copy()
    engine = Pix2TexEngine()
    if use_clipboard:
        result = run_image(loaded, engine)
    else:
        result = run_image(loaded, engine, write=lambda _text: None)
    if not result.ok:
        get_logger().error("smoke OCR failed: %s", result.error)
        print(f"FAILED:{result.error}", file=sys.stderr)
        return 1
    print(result.latex)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="texgrab")
    parser.add_argument("--check", action="store_true", help="Print the interpreter and exit")
    parser.add_argument("--test-ocr", metavar="IMAGE", help="Convert one image to LaTeX and print it")
    parser.add_argument(
        "--clipboard",
        action="store_true",
        help="With --test-ocr, copy the LaTeX string to the clipboard",
    )
    parser.add_argument(
        "--trigger",
        action="store_true",
        help="Ask the running TexGrab to snip, starting it if it is not running",
    )
    args = parser.parse_args(argv)
    if args.check:
        return _check()
    config = load_config()
    configure_logging(config.debug)
    if args.test_ocr:
        return _test_ocr(args.test_ocr, args.clipboard)
    if sys.platform == "darwin":
        if args.trigger:
            print("--trigger is only available on Linux", file=sys.stderr)
            return 2
        from texgrab.app import run_app

        run_app(config)
        return 0
    from texgrab.linux.trigger import send_snip

    if args.trigger and send_snip():
        get_logger().info("trigger sent")
        return 0
    if args.trigger:
        get_logger().info("no listener; starting TexGrab")
    from texgrab.linux.app import run_app

    run_app(config, snip_when_ready=bool(args.trigger))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
