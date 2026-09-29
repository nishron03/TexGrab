"""One JSON file. Unknown keys are ignored so older builds keep starting."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from texgrab.hotkey.keys import keycode_for
from texgrab.log import get_logger


def config_dir() -> Path:
    """Darwin keeps the Application Support path. Linux follows XDG."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "TexGrab"
    raw = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(raw).expanduser() if raw else Path.home() / ".config"
    return base / "texgrab"


def config_path() -> Path:
    return config_dir() / "config.json"


_LINUX = sys.platform != "darwin"


@dataclass
class Config:
    shortcut_key: str = "s"
    shortcut_command: bool = not _LINUX
    shortcut_control: bool = True
    shortcut_shift: bool = True
    shortcut_option: bool = _LINUX
    notifications: bool = True
    debug: bool = False

    @property
    def shortcut_label(self) -> str:
        if sys.platform == "darwin":
            parts: list[str] = []
            if self.shortcut_command:
                parts.append("⌘")
            if self.shortcut_control:
                parts.append("⌃")
            if self.shortcut_option:
                parts.append("⌥")
            if self.shortcut_shift:
                parts.append("⇧")
            return "".join(parts) + self.shortcut_key.upper()
        words: list[str] = []
        if self.shortcut_command:
            words.append("Super")
        if self.shortcut_control:
            words.append("Ctrl")
        if self.shortcut_option:
            words.append("Alt")
        if self.shortcut_shift:
            words.append("Shift")
        words.append(self.shortcut_key.upper())
        return "+".join(words)


def load_config() -> Config:
    path = config_path()
    if not path.exists():
        return Config()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        get_logger().warning("config unreadable, using defaults: %s", exc)
        return Config()
    if not isinstance(raw, dict):
        get_logger().warning("config is not an object, using defaults")
        return Config()
    config = Config()
    for name in (
        "shortcut_command",
        "shortcut_control",
        "shortcut_shift",
        "shortcut_option",
        "notifications",
        "debug",
    ):
        value = raw.get(name)
        if isinstance(value, bool):
            setattr(config, name, value)
    key = raw.get("shortcut_key")
    if isinstance(key, str) and key.strip():
        config.shortcut_key = key.strip().lower()
    try:
        keycode_for(config.shortcut_key)
    except ValueError:
        get_logger().error("unknown shortcut key %r, using s", config.shortcut_key)
        config.shortcut_key = "s"
    if not (
        config.shortcut_command
        or config.shortcut_control
        or config.shortcut_shift
        or config.shortcut_option
    ):
        _apply_platform_default(config)
    return config


def _apply_platform_default(config: Config) -> None:
    """A chord with no modifiers cannot be registered. Use the platform default."""
    if sys.platform == "darwin":
        config.shortcut_command = True
        config.shortcut_control = True
        config.shortcut_shift = True
        config.shortcut_option = False
        return
    config.shortcut_command = False
    config.shortcut_control = True
    config.shortcut_shift = True
    config.shortcut_option = True


def save_config(config: Config) -> None:
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
