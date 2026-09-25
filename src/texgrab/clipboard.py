"""Write a string to the general pasteboard and nothing else."""

from __future__ import annotations

from texgrab.log import get_logger

PASTEBOARD_TYPE = "public.utf8-plain-text"


class ClipboardError(RuntimeError):
    pass


def _pasteboard():
    from AppKit import NSPasteboard

    return NSPasteboard.generalPasteboard()


def read_text() -> str:
    value = _pasteboard().stringForType_(PASTEBOARD_TYPE)
    if value is None:
        return ""
    return str(value)


def change_count() -> int:
    return int(_pasteboard().changeCount())


def write_text(text: str) -> None:
    if not isinstance(text, str):
        raise ClipboardError("clipboard text must be a string")
    pasteboard = _pasteboard()
    pasteboard.clearContents()
    if text == "":
        get_logger().info("clipboard cleared")
        return
    ok = pasteboard.setString_forType_(text, PASTEBOARD_TYPE)
    if not ok:
        raise ClipboardError("NSPasteboard rejected the string")
    get_logger().info("clipboard wrote chars=%s", len(text))
