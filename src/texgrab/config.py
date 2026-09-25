"""One JSON file. Unknown keys are ignored so older builds keep starting."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from texgrab.hotkey.keys import keycode_for
from texgrab.log import get_logger

CONFIG_DIR = Path.home() / "Library" / "Application Support" / "TexGrab"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class Config:
    shortcut_key: str = "s"
    shortcut_command: bool = True
    shortcut_control: bool = True
    shortcut_shift: bool = True
    shortcut_option: bool = False
    notifications: bool = True
    debug: bool = False

    @property
    def shortcut_label(self) -> str:
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


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        return Config()
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
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
        config.shortcut_command = True
        config.shortcut_control = True
        config.shortcut_shift = True
    return config


def save_config(config: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
