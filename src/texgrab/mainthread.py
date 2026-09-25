"""Hop back to the AppKit main thread. The snip worker must not touch the menu."""

from __future__ import annotations

import threading

from texgrab.log import get_logger


def call_on_main(fn) -> None:
    from Foundation import NSOperationQueue

    NSOperationQueue.mainQueue().addOperationWithBlock_(fn)


def call_on_main_sync(fn, timeout: float = 60):
    from Foundation import NSThread

    if NSThread.isMainThread():
        return fn()
    box: dict = {}
    done = threading.Event()

    def wrapped() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:
            box["error"] = exc
        finally:
            done.set()

    call_on_main(wrapped)
    if not done.wait(timeout):
        get_logger().error("timed out waiting for the main thread")
        raise TimeoutError("timed out waiting for the main thread")
    if "error" in box:
        raise box["error"]
    return box.get("value")
