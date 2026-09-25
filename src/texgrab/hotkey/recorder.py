"""A small window that records the next key combination."""

from __future__ import annotations

import objc
from AppKit import (
    NSBackingStoreBuffered,
    NSFloatingWindowLevel,
    NSTextField,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSMakeRect

from texgrab.hotkey.combo import ShortcutCancelled, ShortcutRejected, choice_from_keycode

_active = None


def prompt_for_shortcut(current_label: str, callback) -> None:
    """Show the recorder. `callback` receives a ShortcutChoice, or None if cancelled."""
    global _active

    def finished(choice) -> None:
        global _active
        _active = None
        callback(choice)

    recorder = _ShortcutWindow.alloc().initWithCallback_currentLabel_(finished, current_label)
    _active = recorder
    recorder.center()
    recorder.makeKeyAndOrderFront_(None)


class _ShortcutWindow(NSWindow):
    def initWithCallback_currentLabel_(self, callback, current_label: str):
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
        self = NSWindow.initWithContentRect_styleMask_backing_defer_(
            self,
            NSMakeRect(0, 0, 440, 130),
            style,
            NSBackingStoreBuffered,
            False,
        )
        if self is None:
            return None
        self._callback = callback
        self._done = False
        self.setTitle_("Change TexGrab shortcut")
        self.setLevel_(NSFloatingWindowLevel)
        self.setDelegate_(self)
        content = self.contentView()
        self._status = NSTextField.wrappingLabelWithString_(
            f"Press the new shortcut. Current: {current_label}. Escape cancels."
        )
        self._status.setFrame_(((20, 36), (400, 64)))
        content.addSubview_(self._status)
        return self

    def canBecomeKeyWindow(self) -> bool:
        return True

    def keyDown_(self, event) -> None:
        self._handle(event)

    def performKeyEquivalent_(self, event) -> bool:
        # Command combinations are delivered here, not to keyDown:.
        self._handle(event)
        return True

    def windowShouldClose_(self, _window) -> bool:
        self._finish(None)
        return True

    @objc.python_method
    def _handle(self, event) -> None:
        if self._done or event.isARepeat():
            return
        try:
            choice = choice_from_keycode(event.keyCode(), int(event.modifierFlags()))
        except ShortcutCancelled:
            self._finish(None)
            return
        except ShortcutRejected as exc:
            self._status.setStringValue_(exc.reason)
            return
        self._finish(choice)

    @objc.python_method
    def _finish(self, choice) -> None:
        if self._done:
            return
        self._done = True
        callback = self._callback
        self.orderOut_(None)
        callback(choice)
