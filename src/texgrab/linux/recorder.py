"""GTK window that records the next chord.

A tray menu does not leave this process focused. The window is presented after
the menu closes and ignores keys until it is focused. Escape keeps the old
shortcut. A chord is accepted only when it includes Ctrl or Super.
"""

from __future__ import annotations

import os
from pathlib import Path

from texgrab.hotkey.combo import ShortcutCancelled, ShortcutRejected, choice_from_held
from texgrab.log import get_logger

_MODIFIER_KEYS = {
    "Control_L",
    "Control_R",
    "Shift_L",
    "Shift_R",
    "Alt_L",
    "Alt_R",
    "Super_L",
    "Super_R",
    "Meta_L",
    "Meta_R",
    "Hyper_L",
    "Hyper_R",
    "ISO_Level3_Shift",
    "Caps_Lock",
    "Num_Lock",
}

_KEY_NAMES = {
    "minus": "-",
    "equal": "=",
    "bracketleft": "[",
    "bracketright": "]",
    "backslash": "\\",
    "semicolon": ";",
    "apostrophe": "'",
    "grave": "`",
    "comma": ",",
    "period": ".",
    "slash": "/",
}


def prepare_typelib_path() -> None:
    extra = [
        "/usr/lib/girepository-1.0",
        "/usr/lib/x86_64-linux-gnu/girepository-1.0",
    ]
    current = [part for part in os.environ.get("GI_TYPELIB_PATH", "").split(":") if part]
    for item in extra:
        if item not in current and Path(item).is_dir():
            current.append(item)
    if current:
        os.environ["GI_TYPELIB_PATH"] = ":".join(current)


def describe_modifiers(*, command: bool, control: bool, shift: bool, option: bool) -> str:
    parts: list[str] = []
    if command:
        parts.append("Super")
    if control:
        parts.append("Ctrl")
    if option:
        parts.append("Alt")
    if shift:
        parts.append("Shift")
    return "+".join(parts) if parts else "none"


def key_from_name(name: str | None) -> str | None:
    if not name or name in _MODIFIER_KEYS:
        return None
    mapped = _KEY_NAMES.get(name)
    if mapped:
        return mapped
    if len(name) == 1:
        return name.lower()
    return None


def prompt_for_shortcut(current_label: str, callback) -> None:
    """Show the recorder. `callback` receives a ShortcutChoice, or None if cancelled."""
    prepare_typelib_path()
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import GLib, Gtk
    except Exception:
        get_logger().exception("GTK shortcut recorder is unavailable")
        callback(None)
        return

    owns_loop = bool(GLib.MainContext.default().is_owner() or Gtk.main_level() > 0)
    loop = None if owns_loop else GLib.MainLoop()

    def finished(choice) -> None:
        try:
            callback(choice)
        finally:
            if loop is not None and loop.is_running():
                loop.quit()

    def fire() -> bool:
        _present(current_label, finished, Gtk, GLib)
        return False

    GLib.timeout_add(350, fire)
    if loop is not None:
        loop.run()


def _present(current_label: str, callback, Gtk, GLib) -> None:
    from gi.repository import Gdk

    window = Gtk.Window(title="TexGrab shortcut")
    window.set_default_size(460, 170)
    window.set_keep_above(True)
    window.set_type_hint(Gdk.WindowTypeHint.DIALOG)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.set_margin_top(16)
    box.set_margin_bottom(16)
    box.set_margin_start(16)
    box.set_margin_end(16)
    hint = Gtk.Label(label="Click this window, then press the shortcut.")
    hint.set_line_wrap(True)
    current = Gtk.Label(label=f"Current: {current_label}")
    mods = Gtk.Label(label="Modifiers: none")
    box.pack_start(hint, False, False, 0)
    box.pack_start(current, False, False, 0)
    box.pack_start(mods, False, False, 0)
    window.add(box)
    state = {"ready": False, "done": False}

    def finish(choice) -> None:
        if state["done"]:
            return
        state["done"] = True
        window.destroy()
        callback(choice)

    def held(event):
        mask = event.state
        super_mask = getattr(Gdk.ModifierType, "SUPER_MASK", 0)
        return (
            bool(mask & Gdk.ModifierType.CONTROL_MASK),
            bool(mask & Gdk.ModifierType.MOD1_MASK),
            bool(mask & Gdk.ModifierType.SHIFT_MASK),
            bool(mask & super_mask) or bool(mask & Gdk.ModifierType.MOD4_MASK),
        )

    def show_held(event) -> None:
        control, option, shift, command = held(event)
        mods.set_text(
            "Modifiers: "
            + describe_modifiers(command=command, control=control, shift=shift, option=option)
        )

    def on_focus(_widget, _event) -> bool:
        state["ready"] = True
        hint.set_text("Press Ctrl or Super, plus a key. Escape cancels.")
        return False

    def on_key(_widget, event) -> bool:
        show_held(event)
        if not state["ready"]:
            return True
        name = Gdk.keyval_name(event.keyval) or ""
        control, option, shift, command = held(event)
        escape = event.keyval == Gdk.KEY_Escape or name == "Escape"
        if escape:
            finish(None)
            return True
        key = key_from_name(name)
        if key is None:
            return True
        try:
            choice = choice_from_held(
                key,
                command=command,
                control=control,
                shift=shift,
                option=option,
            )
        except ShortcutCancelled:
            finish(None)
            return True
        except ShortcutRejected as exc:
            hint.set_text(exc.reason)
            return True
        finish(choice)
        return True

    def on_delete(_widget, _event) -> bool:
        finish(None)
        return False

    window.connect("focus-in-event", on_focus)
    window.connect("key-press-event", on_key)
    window.connect("key-release-event", lambda _widget, event: show_held(event) or True)
    window.connect("delete-event", on_delete)
    window.show_all()
    window.present()
    window.grab_focus()

    def check_focus() -> bool:
        if window.is_active():
            state["ready"] = True
            hint.set_text("Press Ctrl or Super, plus a key. Escape cancels.")
            return False
        return not state["done"]

    GLib.timeout_add(100, check_focus)
