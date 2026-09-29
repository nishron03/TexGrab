"""In-process X11 chord via XGrabKey. The callback returns immediately.

Used only when XDG_SESSION_TYPE is x11. NumLock and CapsLock are grabbed as
well so the chord still fires. The grab is released on shortcut change and quit.
"""

from __future__ import annotations

import queue
import select
import threading

from texgrab.log import get_logger

_KEYSYMS = {
    "-": "minus",
    "=": "equal",
    "[": "bracketleft",
    "]": "bracketright",
    "\\": "backslash",
    ";": "semicolon",
    "'": "apostrophe",
    "`": "grave",
    ",": "comma",
    ".": "period",
    "/": "slash",
}


def modifier_mask(*, command: bool, control: bool, shift: bool, option: bool) -> int:
    """X masks. `command` is Super (Mod4) and `option` is Alt (Mod1)."""
    from Xlib import X

    mask = 0
    if shift:
        mask |= X.ShiftMask
    if control:
        mask |= X.ControlMask
    if option:
        mask |= X.Mod1Mask
    if command:
        mask |= X.Mod4Mask
    return mask


def grab_variants(base: int) -> list[int]:
    """Include CapsLock, NumLock, and Mod5 so the chord is not swallowed by them."""
    from Xlib import X

    extras = [0]
    for bit in (X.LockMask, X.Mod2Mask, X.Mod5Mask):
        extras = extras + [item | bit for item in extras]
    return [base | extra for extra in extras]


class X11Hotkey:
    def __init__(self, callback) -> None:
        self._callback = callback
        self._commands: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._display = None

    def bind(self, config) -> bool:
        self._ensure()
        return bool(self._call("bind", config))

    def unbind(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            return
        self._call("unbind", None)

    def close(self) -> None:
        thread = self._thread
        self._thread = None
        if thread is None or not thread.is_alive():
            return
        self._commands.put(("stop", None, None))
        thread.join(timeout=2)

    def _ensure(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._main, name="texgrab-x11", daemon=True)
        self._thread.start()

    def _call(self, kind: str, payload):
        done = threading.Event()
        box: dict = {}

        def finish(value) -> None:
            box["value"] = value
            done.set()

        self._commands.put((kind, payload, finish))
        if not done.wait(3):
            return False
        return box.get("value")

    def _main(self) -> None:
        try:
            from Xlib import X, XK, display
            from Xlib.error import BadAccess, CatchError
        except Exception:
            get_logger().exception("python-xlib is not installed")
            self._drain_refusing()
            return
        try:
            self._display = display.Display()
        except Exception:
            get_logger().exception("X11 display is not available")
            self._drain_refusing()
            return
        root = self._display.screen().root
        grabbed: list[tuple[int, int]] = []
        while True:
            if not self._pump(grabbed, root, X, XK, CatchError, BadAccess):
                break
            try:
                readable, _, _ = select.select([self._display.fileno()], [], [], 0.2)
            except (OSError, ValueError):
                break
            if not readable:
                continue
            while self._display.pending_events():
                event = self._display.next_event()
                if event.type != X.KeyPress:
                    continue
                if not any(event.detail == code for code, _mask in grabbed):
                    continue
                try:
                    self._callback()
                except Exception:
                    get_logger().exception("shortcut callback failed")
        self._ungrab(grabbed, root, CatchError)
        try:
            self._display.close()
        except Exception:
            pass
        self._display = None

    def _pump(self, grabbed, root, X, XK, CatchError, BadAccess) -> bool:
        while True:
            try:
                kind, payload, finish = self._commands.get_nowait()
            except queue.Empty:
                return True
            if kind == "stop":
                self._ungrab(grabbed, root, CatchError)
                grabbed.clear()
                if finish:
                    finish(True)
                return False
            if kind == "unbind":
                self._ungrab(grabbed, root, CatchError)
                grabbed.clear()
                if finish:
                    finish(True)
                continue
            if kind == "bind":
                self._ungrab(grabbed, root, CatchError)
                grabbed.clear()
                ok = self._grab(payload, grabbed, root, X, XK, CatchError)
                if finish:
                    finish(ok)
                continue
            if finish:
                finish(False)
        return True

    def _grab(self, config, grabbed, root, X, XK, CatchError) -> bool:
        try:
            code = _keycode(self._display, XK, config.shortcut_key)
        except ValueError:
            get_logger().error("no X keycode for %s", config.shortcut_key)
            return False
        base = modifier_mask(
            command=config.shortcut_command,
            control=config.shortcut_control,
            shift=config.shortcut_shift,
            option=config.shortcut_option,
        )
        variants = grab_variants(base)
        owned: list[tuple[int, int]] = []
        for mask in variants:
            error = CatchError()
            root.grab_key(code, mask, False, X.GrabModeAsync, X.GrabModeAsync, onerror=error)
            self._display.sync()
            if error.get_error():
                get_logger().error("XGrabKey failed for %s", config.shortcut_label)
                self._ungrab(owned, root, CatchError)
                return False
            owned.append((code, mask))
        grabbed.extend(owned)
        get_logger().info("shortcut registered %s", config.shortcut_label)
        return True

    def _ungrab(self, grabbed, root, CatchError) -> None:
        if self._display is None:
            grabbed.clear()
            return
        for code, mask in grabbed:
            error = CatchError()
            root.ungrab_key(code, mask, onerror=error)
        try:
            self._display.sync()
        except Exception:
            get_logger().exception("XUngrabKey failed")
        grabbed.clear()

    def _drain_refusing(self) -> None:
        while True:
            try:
                _kind, _payload, finish = self._commands.get(timeout=0.2)
            except queue.Empty:
                if self._commands.empty():
                    return
                continue
            if finish:
                finish(False)


def _keycode(display, XK, key: str) -> int:
    name = _KEYSYMS.get(key, key)
    keysym = XK.string_to_keysym(name)
    if not keysym:
        raise ValueError(key)
    code = display.keysym_to_keycode(keysym)
    if not code:
        raise ValueError(key)
    return code
