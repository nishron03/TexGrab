"""A small window that records the next key combination.

A menu-bar app is not the active application, so a window it opens does not
receive keystrokes. The status menu then closes and gives focus back to the
previous app. Showing the recorder on the next turn, and briefly becoming a
normal foreground app, is what lets the key and Escape arrive.
"""

from __future__ import annotations

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSEvent,
    NSEventMaskKeyDown,
    NSFloatingWindowLevel,
    NSTextField,
    NSWindow,
    NSWindowCollectionBehaviorMoveToActiveSpace,
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
    # Wait until the status menu has closed. Otherwise it resigns key afterwards.
    recorder.performSelector_withObject_afterDelay_("orderFrontAndActivate:", None, 0.15)


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
        self._monitor = None
        self._previous_policy = None
        self.setTitle_("Change TexGrab shortcut")
        self.setLevel_(NSFloatingWindowLevel)
        self.setHidesOnDeactivate_(False)
        self.setCollectionBehavior_(NSWindowCollectionBehaviorMoveToActiveSpace)
        self.setDelegate_(self)
        content = self.contentView()
        self._status = NSTextField.wrappingLabelWithString_(
            f"Press the new shortcut. Current: {current_label}. Escape cancels."
        )
        self._status.setFrame_(((20, 36), (400, 64)))
        self._status.setEditable_(False)
        self._status.setSelectable_(False)
        self._status.setRefusesFirstResponder_(True)
        content.addSubview_(self._status)
        return self

    def canBecomeKeyWindow(self) -> bool:
        return True

    def canBecomeMainWindow(self) -> bool:
        return True

    def orderFrontAndActivate_(self, _sender) -> None:
        if self._done:
            return
        app = NSApplication.sharedApplication()
        self._previous_policy = app.activationPolicy()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        self.center()
        self.makeKeyAndOrderFront_(None)
        self.makeFirstResponder_(self)
        app.activateIgnoringOtherApps_(True)
        activate = getattr(app, "activate", None)
        if activate is not None:
            activate()

        def handler(event):
            self._handle(event)
            return None

        self._key_handler = handler
        self._monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, handler
        )

    def keyDown_(self, event) -> None:
        self._handle(event)

    def performKeyEquivalent_(self, event) -> bool:
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
            self._status.setStringValue_(str(exc.reason) + " Escape cancels.")
            return
        self._finish(choice)

    @objc.python_method
    def _finish(self, choice) -> None:
        if self._done:
            return
        self._done = True
        if self._monitor is not None:
            NSEvent.removeMonitor_(self._monitor)
            self._monitor = None
        callback = self._callback
        self.orderOut_(None)
        if self._previous_policy is not None:
            NSApplication.sharedApplication().setActivationPolicy_(self._previous_policy)
        callback(choice)
