"""Virtual key codes from HIToolbox Events.h (ANSI US positions)."""

from __future__ import annotations

CMD_KEY = 1 << 8
SHIFT_KEY = 1 << 9
OPTION_KEY = 1 << 11
CONTROL_KEY = 1 << 12

# kEventClassKeyboard / kEventHotKeyPressed
EVENT_CLASS_KEYBOARD = int.from_bytes(b"keyb", "big")
EVENT_HOTKEY_PRESSED = 5

# Physical key positions, not the character produced with modifiers.
_KEYCODES = {
    "a": 0x00,
    "s": 0x01,
    "d": 0x02,
    "f": 0x03,
    "h": 0x04,
    "g": 0x05,
    "z": 0x06,
    "x": 0x07,
    "c": 0x08,
    "v": 0x09,
    "b": 0x0B,
    "q": 0x0C,
    "w": 0x0D,
    "e": 0x0E,
    "r": 0x0F,
    "y": 0x10,
    "t": 0x11,
    "1": 0x12,
    "2": 0x13,
    "3": 0x14,
    "4": 0x15,
    "6": 0x16,
    "5": 0x17,
    "=": 0x18,
    "9": 0x19,
    "7": 0x1A,
    "-": 0x1B,
    "8": 0x1C,
    "0": 0x1D,
    "]": 0x1E,
    "o": 0x1F,
    "u": 0x20,
    "[": 0x21,
    "i": 0x22,
    "p": 0x23,
    "l": 0x25,
    "j": 0x26,
    "'": 0x27,
    "k": 0x28,
    ";": 0x29,
    "\\": 0x2A,
    ",": 0x2B,
    "/": 0x2C,
    "n": 0x2D,
    "m": 0x2E,
    ".": 0x2F,
    "`": 0x32,
}


def keycode_for(key: str) -> int:
    code = _KEYCODES.get(key.lower())
    if code is None:
        known = ", ".join(sorted(_KEYCODES))
        raise ValueError(f"unsupported shortcut key {key!r}; expected one of: {known}")
    return code


def name_for_keycode(code: int) -> str | None:
    for name, value in _KEYCODES.items():
        if value == code:
            return name
    return None


def modifier_mask(
    *,
    command: bool,
    control: bool,
    shift: bool,
    option: bool,
) -> int:
    mask = 0
    if command:
        mask |= CMD_KEY
    if shift:
        mask |= SHIFT_KEY
    if option:
        mask |= OPTION_KEY
    if control:
        mask |= CONTROL_KEY
    return mask
