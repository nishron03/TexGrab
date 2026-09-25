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
# Device-dependent bits. AppKit usually sets the bits above as well, but a
# shifted chord can arrive with only these set.
_LEFT_CONTROL = 0x00000001
_LEFT_SHIFT = 0x00000002
_RIGHT_SHIFT = 0x00000004
_LEFT_COMMAND = 0x00000008
_RIGHT_COMMAND = 0x00000010
_LEFT_OPTION = 0x00000020
_RIGHT_OPTION = 0x00000040
_RIGHT_CONTROL = 0x00002000
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


def modifier_state(modifier_flags: int) -> tuple[bool, bool, bool, bool]:
    """Return command, control, shift, option."""
    command = bool(modifier_flags & (NS_COMMAND | _LEFT_COMMAND | _RIGHT_COMMAND))
    control = bool(modifier_flags & (NS_CONTROL | _LEFT_CONTROL | _RIGHT_CONTROL))
    shift = bool(modifier_flags & (NS_SHIFT | _LEFT_SHIFT | _RIGHT_SHIFT))
    option = bool(modifier_flags & (NS_OPTION | _LEFT_OPTION | _RIGHT_OPTION))
    return command, control, shift, option


def choice_from_keycode(
    key_code: int,
    modifier_flags: int,
    characters: str | None = None,
) -> ShortcutChoice:
    if key_code == ESCAPE_KEYCODE:
        raise ShortcutCancelled()
    name = name_for_keycode(key_code)
    if name is None and characters:
        text = characters.lower()
        if len(text) == 1 and name_for_keycode_safe(text):
            name = text
    if name is None:
        raise ShortcutRejected("Use a letter, digit, or punctuation key.")
    command, control, shift, option = modifier_state(modifier_flags)
    if not (command or control):
        raise ShortcutRejected("Include ⌘ or ⌃. Shift and ⌥ can be added on top.")
    return ShortcutChoice(
        key=name,
        command=command,
        control=control,
        shift=shift,
        option=option,
    )


def name_for_keycode_safe(key: str) -> bool:
    from texgrab.hotkey.keys import keycode_for

    try:
        keycode_for(key)
    except ValueError:
        return False
    return True


def apply_shortcut(config, choice: ShortcutChoice) -> None:
    config.shortcut_key = choice.key
    config.shortcut_command = choice.command
    config.shortcut_control = choice.control
    config.shortcut_shift = choice.shift
    config.shortcut_option = choice.option
