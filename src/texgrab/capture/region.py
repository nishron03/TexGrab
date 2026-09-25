"""Native macOS region selection via the screencapture tool.

The command is interactive (`-i`) and writes a private temporary PNG. It does
not pass `-c`, so the pasteboard is left alone. The file is removed before the
image is returned to the caller.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from texgrab.log import get_logger


class CaptureError(RuntimeError):
    pass


def grab_region(runner=None) -> Image.Image | None:
    """Return the selected image, or None if the user cancelled.

    `runner`, when set, is called with the argument list and must return an
    object with `returncode` and `stderr`. Tests use it so the real selection
    UI is not opened.
    """
    directory = Path(tempfile.mkdtemp(prefix="texgrab-"))
    os.chmod(directory, 0o700)
    path = directory / "capture.png"
    command = ["screencapture", "-i", "-x", "-t", "png", str(path)]
    get_logger().info("capture start")
    try:
        if runner is None:
            completed = subprocess.run(command, check=False, capture_output=True)
        else:
            completed = runner(command)
        stderr = getattr(completed, "stderr", b"") or b""
        if isinstance(stderr, bytes):
            stderr_text = stderr.decode("utf-8", "replace").strip()
        else:
            stderr_text = str(stderr).strip()
        if path.is_file() and path.stat().st_size > 0:
            with Image.open(path) as image:
                image.load()
                copied = image.copy()
            get_logger().info("capture ok %sx%s", copied.width, copied.height)
            return copied
        if completed.returncode != 0 and stderr_text:
            get_logger().error("screencapture failed: %s", stderr_text[:500])
            raise CaptureError(stderr_text[:500])
        get_logger().info("capture cancelled")
        return None
    finally:
        shutil.rmtree(directory, ignore_errors=True)
