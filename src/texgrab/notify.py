"""A banner, not a dialog. Failures are logged and otherwise ignored."""

from __future__ import annotations

import subprocess

from texgrab.log import get_logger


def notify(message: str, *, enabled: bool = True) -> None:
    if not enabled:
        get_logger().info("notification suppressed: %s", message)
        return
    safe = message.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{safe}" with title "TexGrab"'
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
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
