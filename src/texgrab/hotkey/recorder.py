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
    NSEventMaskFlagsChanged,
    NSEventMaskKeyDown,
    NSEventTypeFlagsChanged,
    NSEventTypeKeyDown,
    NSFloatingWindowLevel,
    NSTextField,
    NSView,
    NSWindow,
    NSWindowCollectionBehaviorMoveToActiveSpace,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSMakeRect

from texgrab.hotkey.combo import (
    ShortcutCancelled,
    ShortcutRejected,
    choice_from_keycode,
    modifier_state,
)
from texgrab.log import get_logger


def _physical_keycode(event) -> int:
    try:
        cg_event = event.CGEvent()
        if cg_event is not None:
            return int(cg_event.getIntegerValueField_(9))
    except Exception:
        pass
    return int(event.keyCode())


def _characters_ignoring_modifiers(event) -> str:
    try:
        text = event.charactersIgnoringModifiers()
    except Exception:
        return ""
    return "" if text is None else str(text)


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


class _CaptureView(NSView):
    """First responder. Command chords call performKeyEquivalent:; Command+Control+Shift arrives as keyDown:."""

    def acceptsFirstResponder(self) -> bool:
        return True

    def keyDown_(self, event) -> None:
        self.window()._handle(event)

    def performKeyEquivalent_(self, event) -> bool:
        self.window()._handle(event)
        return True

    def flagsChanged_(self, event) -> None:
        self.window()._show_modifiers(event)


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
        self._capture = _CaptureView.alloc().initWithFrame_(NSMakeRect(0, 0, 440, 130))
        content.addSubview_(self._capture)
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
        self.makeFirstResponder_(self._capture)
        app.activateIgnoringOtherApps_(True)
        activate = getattr(app, "activate", None)
        if activate is not None:
            activate()

        def handler(event):
            if event.type() == NSEventTypeFlagsChanged:
                self._show_modifiers(event)
                return event
            self._handle(event)
            return None

        self._key_handler = handler
        self._monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown | NSEventMaskFlagsChanged, handler
        )

    def sendEvent_(self, event) -> None:
        if event.type() == NSEventTypeKeyDown:
            self._handle(event)
            return
        if event.type() == NSEventTypeFlagsChanged:
            self._show_modifiers(event)
        NSWindow.sendEvent_(self, event)

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
        key_code = _physical_keycode(event)
        flags = int(event.modifierFlags())
        characters = _characters_ignoring_modifiers(event)
        get_logger().info(
            "shortcut key code=%s flags=%s characters=%r",
            key_code,
            hex(flags),
            characters,
        )
        try:
            choice = choice_from_keycode(key_code, flags, characters)
        except ShortcutCancelled:
            self._finish(None)
            return
        except ShortcutRejected as exc:
            self._status.setStringValue_(str(exc.reason) + " Escape cancels.")
            return
        self._finish(choice)

    @objc.python_method
    def _show_modifiers(self, event) -> None:
        if self._done:
            return
        command, control, shift, option = modifier_state(int(event.modifierFlags()))
        symbols = []
        if command:
            symbols.append("⌘")
        if control:
            symbols.append("⌃")
        if option:
            symbols.append("⌥")
        if shift:
            symbols.append("⇧")
        held = "".join(symbols) if symbols else "no modifiers"
        self._status.setStringValue_(
            f"Holding {held}. Press a letter, digit, or punctuation key. Escape cancels."
        )

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
