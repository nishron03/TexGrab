"""Turn a key press into a shortcut TexGrab can register.

Carbon hotkeys swallow the key, so a combination needs Command or Control.
Shift+S alone would stop capital S from reaching other apps.
"""

from __future__ import annotations

from dataclasses import dataclass

from texgrab.hotkey.keys import name_for_keycode

NS_SHIFT = 1 << 17
NS_CONTROL = 1 << 18
NS_OPTION = 1 << 19
NS_COMMAND = 1 << 20
ESCAPE_KEYCODE = 0x35


class ShortcutCancelled(Exception):
    pass


class ShortcutRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ShortcutChoice:
    key: str
    command: bool
    control: bool
    shift: bool
    option: bool


def choice_from_keycode(key_code: int, modifier_flags: int) -> ShortcutChoice:
    if key_code == ESCAPE_KEYCODE:
        raise ShortcutCancelled()
    name = name_for_keycode(key_code)
    if name is None:
        raise ShortcutRejected("Use a letter, digit, or punctuation key.")
    command = bool(modifier_flags & NS_COMMAND)
    control = bool(modifier_flags & NS_CONTROL)
    shift = bool(modifier_flags & NS_SHIFT)
    option = bool(modifier_flags & NS_OPTION)
    if not (command or control):
        raise ShortcutRejected("Include ⌘ or ⌃ so the shortcut does not block normal typing.")
    return ShortcutChoice(
        key=name,
        command=command,
        control=control,
        shift=shift,
        option=option,
    )


def apply_shortcut(config, choice: ShortcutChoice) -> None:
    config.shortcut_key = choice.key
    config.shortcut_command = choice.command
    config.shortcut_control = choice.control
    config.shortcut_shift = choice.shift
    config.shortcut_option = choice.option
