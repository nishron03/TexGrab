from texgrab.config import Config
from texgrab.hotkey.combo import (
    ESCAPE_KEYCODE,
    NS_COMMAND,
    NS_CONTROL,
    NS_OPTION,
    NS_SHIFT,
    ShortcutCancelled,
    ShortcutRejected,
    apply_shortcut,
    choice_from_keycode,
)
from texgrab.hotkey.keys import (
    CMD_KEY,
    CONTROL_KEY,
    SHIFT_KEY,
    keycode_for,
    modifier_mask,
    name_for_keycode,
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


def test_keycode_roundtrip_for_default_key():
    assert name_for_keycode(keycode_for("s")) == "s"


def test_recorded_default_chord():
    choice = choice_from_keycode(0x01, NS_COMMAND | NS_CONTROL | NS_SHIFT)
    assert choice.key == "s"
    assert (choice.command, choice.control, choice.shift, choice.option) == (True, True, True, False)
    config = Config()
    apply_shortcut(config, choice)
    assert config.shortcut_label == "⌘⌃⇧S"


def test_command_letter_is_accepted():
    choice = choice_from_keycode(keycode_for("e"), NS_COMMAND)
    config = Config()
    apply_shortcut(config, choice)
    assert config.shortcut_label == "⌘E"


def test_shift_alone_is_rejected():
    try:
        choice_from_keycode(keycode_for("s"), NS_SHIFT)
    except ShortcutRejected as exc:
        assert "⌘" in exc.reason
        return
    raise AssertionError("expected ShortcutRejected")


def test_option_shift_without_command_or_control_is_rejected():
    try:
        choice_from_keycode(keycode_for("s"), NS_OPTION | NS_SHIFT)
    except ShortcutRejected:
        return
    raise AssertionError("expected ShortcutRejected")


def test_unknown_keycode_is_rejected():
    try:
        choice_from_keycode(0x24, NS_COMMAND)
    except ShortcutRejected as exc:
        assert "letter" in exc.reason
        return
    raise AssertionError("expected ShortcutRejected")


def test_escape_cancels():
    try:
        choice_from_keycode(ESCAPE_KEYCODE, NS_COMMAND)
    except ShortcutCancelled:
        return
    raise AssertionError("expected ShortcutCancelled")
