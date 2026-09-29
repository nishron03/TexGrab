"""Linux chords, the GNOME binding plan, and which grab is chosen."""

import sys
from pathlib import Path

import pytest

from texgrab.config import Config, load_config, save_config
from texgrab.hotkey.combo import (
    ShortcutCancelled,
    ShortcutRejected,
    choice_from_held,
    default_choice,
)
from texgrab.linux.desktop_bind import (
    CommandResult,
    DesktopShortcuts,
    binding_taken,
    gtk_binding,
    gvariant_literal,
    hyprland_line,
    plan_gnome_remove,
    plan_gnome_update,
    sway_line,
    system_which,
)
from texgrab.linux.portal import preferred_trigger


def test_default_chord_is_accepted_and_super_is_command():
    if sys.platform == "darwin":
        choice = default_choice()
        assert (choice.key, choice.command, choice.control, choice.shift, choice.option) == (
            "s",
            True,
            True,
            True,
            False,
        )
        return
    choice = default_choice()
    assert (choice.key, choice.command, choice.control, choice.shift, choice.option) == (
        "s",
        False,
        True,
        True,
        True,
    )
    accepted = choice_from_held("S", command=False, control=True, shift=True, option=True)
    assert accepted == choice
    super_only = choice_from_held("e", command=True, control=False, shift=False, option=False)
    assert super_only.command is True
    assert super_only.key == "e"


def test_bare_letter_and_alt_shift_are_rejected():
    with pytest.raises(ShortcutRejected):
        choice_from_held("s", command=False, control=False, shift=False, option=False)
    with pytest.raises(ShortcutRejected) as exc:
        choice_from_held("s", command=False, control=False, shift=True, option=True)
    if sys.platform != "darwin":
        assert "Ctrl or Super" in exc.value.reason


def test_escape_cancels():
    with pytest.raises(ShortcutCancelled):
        choice_from_held("s", command=True, control=False, shift=False, option=False, escape=True)
    with pytest.raises(ShortcutCancelled):
        choice_from_held("Escape", command=False, control=True, shift=False, option=False)


def test_trigger_strings_for_the_linux_default():
    config = Config()
    if sys.platform == "darwin":
        config.shortcut_command = False
        config.shortcut_control = True
        config.shortcut_shift = True
        config.shortcut_option = True
        config.shortcut_key = "s"
    assert gtk_binding(config) == "<Control><Alt><Shift>s"
    assert preferred_trigger(config) == "CTRL+ALT+SHIFT+s"
    assert sway_line(config, "texgrab --trigger") == "bindsym Ctrl+Alt+Shift+s exec texgrab --trigger"
    assert hyprland_line(config, "texgrab --trigger") == "bind = CTRL ALT SHIFT, S, exec, texgrab --trigger"


def test_gnome_plan_keeps_other_shortcuts_and_quotes_strings():
    other = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"
    paths, slot = plan_gnome_update(
        [other],
        [{"path": other, "name": "User", "command": "true"}],
    )
    assert other in paths
    assert slot != other
    assert paths == [other, slot]
    kept = plan_gnome_remove(
        paths,
        [
            {"path": other, "name": "User", "command": "true"},
            {"path": slot, "name": "TexGrab", "command": "python -m texgrab --trigger"},
        ],
    )
    assert kept == [other]
    assert gvariant_literal("TexGrab") == "'TexGrab'"
    assert gvariant_literal("['/keep/']") == "['/keep/']"
    rows = [("org.gnome.shell.keybindings", "show-screenshot-ui", "['Print']")]
    assert binding_taken("Print", rows, "")
    assert not binding_taken("<Control><Alt><Shift>s", rows, "")


def test_gnome_bind_appends_and_does_not_drop_existing(monkeypatch):
    calls = []
    other = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"

    def runner(args):
        calls.append(args)
        if args[1] == "get" and args[-1] == "custom-keybindings":
            return CommandResult(0, f"['{other}']")
        if args[1] == "get" and args[-1] == "name":
            return CommandResult(0, "'User'")
        if args[1] == "get" and args[-1] == "command":
            return CommandResult(0, "'true'")
        if args[1] == "get" and args[-1] == "binding":
            return CommandResult(0, "'<Super>e'")
        if args[1] == "list-recursively":
            return CommandResult(0, "org.gnome.shell.keybindings screenshot ['<Shift>Print']\n")
        return CommandResult(0, "")

    desk = DesktopShortcuts(runner=runner, kind="gnome", which=lambda _name: "/usr/bin/gsettings")
    assert desk.bind(Config())
    updates = [item for item in calls if item[1] == "set" and item[3] == "custom-keybindings"]
    assert other in updates[-1][4]
    assert "custom1/" in updates[-1][4]
    command = [item for item in calls if item[1] == "set" and item[3] == "command"][0][4]
    assert command.startswith("'")
    assert "--trigger" in command
    assert "<Control><Alt><Shift>s" in [
        item[4] for item in calls if item[1] == "set" and item[3] == "binding"
    ][0]


def test_gsettings_comes_from_usr_bin():
    found = system_which("gsettings")
    if Path("/usr/bin/gsettings").is_file():
        assert found == "/usr/bin/gsettings"


def test_sway_prints_a_line_and_does_not_edit_files(capsys):
    desk = DesktopShortcuts(kind="sway")
    assert desk.bind(Config())
    line = capsys.readouterr().out.strip()
    assert line.startswith("bindsym Ctrl+Alt+Shift+s exec ")
    assert "--trigger" in line


def test_no_modifier_config_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_config(Config())
    path = tmp_path / "texgrab" / "config.json"
    path.write_text(
        '{"shortcut_key": "e", "shortcut_command": false, "shortcut_control": false,'
        ' "shortcut_shift": false, "shortcut_option": false, "unknown": 1}\n',
        encoding="utf-8",
    )
    config = load_config()
    assert config.shortcut_key == "e"
    if sys.platform == "darwin":
        assert config.shortcut_command and config.shortcut_control and config.shortcut_shift
        assert config.shortcut_option is False
    else:
        assert config.shortcut_command is False
        assert config.shortcut_control and config.shortcut_shift and config.shortcut_option


def test_super_mask_is_mod4():
    from Xlib import X

    from texgrab.linux.x11_hotkey import grab_variants, modifier_mask

    super_mask = modifier_mask(command=True, control=False, shift=False, option=False)
    assert super_mask & X.Mod4Mask
    chord = modifier_mask(command=False, control=True, shift=True, option=True)
    assert not (chord & X.Mod4Mask)
    assert chord & X.ControlMask and chord & X.ShiftMask and chord & X.Mod1Mask
    variants = grab_variants(chord)
    assert chord in variants
    assert chord | X.LockMask in variants
    assert len(variants) == 8


def test_binding_manager_uses_x11_only_for_an_x11_session(monkeypatch):
    from texgrab.linux.binding import BindingManager

    class Desk:
        def __init__(self):
            self.bound = 0
            self.kind = "gnome"

        def bind(self, _config):
            self.bound += 1
            return True

        def unbind(self):
            return None

    class Grab:
        def __init__(self, ok):
            self.ok = ok
            self.binds = 0

        def bind(self, _config):
            self.binds += 1
            return self.ok

        def unbind(self):
            return None

        def close(self):
            return None

    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    desk = Desk()
    portals = Grab(False)
    x11 = Grab(True)
    manager = BindingManager(
        lambda: None,
        desktop=desk,
        portal_factory=lambda: portals,
        x11_factory=lambda: x11,
    )
    assert manager.start(Config()) == "desktop"
    assert x11.binds == 0
    assert portals.binds == 1
    assert desk.bound == 1

    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    desk2 = Desk()
    x11_ok = Grab(True)
    manager = BindingManager(
        lambda: None,
        desktop=desk2,
        portal_factory=lambda: (_ for _ in ()).throw(AssertionError("portal on x11")),
        x11_factory=lambda: x11_ok,
    )
    assert manager.start(Config()) == "x11"
    assert desk2.bound == 0
