from texgrab.config import Config
from texgrab.hotkey.keys import (
    CMD_KEY,
    CONTROL_KEY,
    SHIFT_KEY,
    keycode_for,
    modifier_mask,
)


def test_default_shortcut_is_command_control_shift_s():
    config = Config()
    assert config.shortcut_label == "⌘⌃⇧S"
    assert keycode_for(config.shortcut_key) == 0x01
    assert modifier_mask(
        command=config.shortcut_command,
        control=config.shortcut_control,
        shift=config.shortcut_shift,
        option=config.shortcut_option,
    ) == (CMD_KEY | CONTROL_KEY | SHIFT_KEY)


def test_unknown_key_is_rejected():
    try:
        keycode_for("not-a-key")
    except ValueError:
        return
    raise AssertionError("expected ValueError")
