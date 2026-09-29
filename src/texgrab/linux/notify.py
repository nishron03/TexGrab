"""notify-send banners. A failure is logged and otherwise ignored."""

from __future__ import annotations

import subprocess

from texgrab.log import get_logger

PERMISSION_MESSAGE = "Screen capture permission is required"


def notify(message: str, *, enabled: bool = True) -> None:
    if not enabled:
        get_logger().info("notification suppressed: %s", message)
        return
    try:
        completed = subprocess.run(
            ["notify-send", "-a", "TexGrab", "TexGrab", message],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        get_logger().exception("notification failed to launch")
        return
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip()
        get_logger().error("notification failed: %s", detail[:300])
        return
    get_logger().info("notification: %s", message)
