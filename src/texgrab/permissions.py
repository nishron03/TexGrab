"""Screen Recording permission.

Carbon hotkeys do not need Accessibility. Capturing pixels does need Screen
Recording, and macOS grants that to the process that launches TexGrab: Terminal
or iTerm during development, TexGrab.app once it is packaged.
"""

from __future__ import annotations

import ctypes

from texgrab.log import get_logger

_CORE_GRAPHICS = (
    "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
)


def _core_graphics():
    library = ctypes.CDLL(_CORE_GRAPHICS)
    library.CGPreflightScreenCaptureAccess.argtypes = []
    library.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
    library.CGRequestScreenCaptureAccess.argtypes = []
    library.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
    return library


def screen_recording_granted() -> bool:
    try:
        granted = bool(_core_graphics().CGPreflightScreenCaptureAccess())
    except (OSError, AttributeError):
        get_logger().exception("could not query Screen Recording permission")
        return False
    get_logger().info("screen recording permission granted=%s", granted)
    return granted


def request_screen_recording() -> bool:
    """Ask macOS to prompt. Returns the current grant; a prior denial will not re-prompt."""
    try:
        get_logger().info("requesting screen recording permission")
        return bool(_core_graphics().CGRequestScreenCaptureAccess())
    except (OSError, AttributeError):
        get_logger().exception("could not request Screen Recording permission")
        return False
