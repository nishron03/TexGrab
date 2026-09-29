"""Register one desktop shortcut that runs `texgrab --trigger`.

GNOME: append a single custom keybinding. KDE: one kglobalaccel entry.
Sway and Hyprland: print the line for the user to paste. Other bindings are
left alone, and quit removes only the TexGrab entry.
"""

from __future__ import annotations

import ast
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from texgrab.log import get_logger

MEDIA_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
CUSTOM_ROOT = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
TEXGRAB_NAME = "TexGrab"
SHELL_SCHEMAS = (
    "org.gnome.shell.keybindings",
    "org.gnome.desktop.wm.keybindings",
    "org.gnome.settings-daemon.plugins.media-keys",
)

_GTK_KEYS = {
    "-": "minus",
    "=": "equal",
    "[": "bracketleft",
    "]": "bracketright",
    "\\": "backslash",
    ";": "semicolon",
    "'": "apostrophe",
    "`": "grave",
    ",": "comma",
    ".": "period",
    "/": "slash",
}


@dataclass
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def system_which(name: str) -> str | None:
    """Prefer /usr/bin. A conda glib ships its own gsettings and a private dconf."""
    for directory in ("/usr/bin", "/bin"):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(name)


def detect_desktop() -> str:
    raw = (
        os.environ.get("XDG_CURRENT_DESKTOP", "")
        + " "
        + os.environ.get("DESKTOP_SESSION", "")
    ).lower()
    if "gnome" in raw:
        return "gnome"
    if "kde" in raw or "plasma" in raw:
        return "kde"
    if "hyprland" in raw:
        return "hyprland"
    if "sway" in raw:
        return "sway"
    return "other"


def trigger_argv() -> list[str]:
    return [str(Path(sys.executable).resolve()), "-m", "texgrab", "--trigger"]


def trigger_command() -> str:
    return " ".join(shlex.quote(part) for part in trigger_argv())


def gtk_binding(config) -> str:
    parts: list[str] = []
    if config.shortcut_control:
        parts.append("<Control>")
    if config.shortcut_option:
        parts.append("<Alt>")
    if config.shortcut_shift:
        parts.append("<Shift>")
    if config.shortcut_command:
        parts.append("<Super>")
    parts.append(_GTK_KEYS.get(config.shortcut_key, config.shortcut_key))
    return "".join(parts)


def sway_line(config, command: str | None = None) -> str:
    mods: list[str] = []
    if config.shortcut_command:
        mods.append("Mod4")
    if config.shortcut_control:
        mods.append("Ctrl")
    if config.shortcut_option:
        mods.append("Alt")
    if config.shortcut_shift:
        mods.append("Shift")
    mods.append(config.shortcut_key)
    return "bindsym " + "+".join(mods) + " exec " + (command or trigger_command())


def hyprland_line(config, command: str | None = None) -> str:
    mods: list[str] = []
    if config.shortcut_command:
        mods.append("SUPER")
    if config.shortcut_control:
        mods.append("CTRL")
    if config.shortcut_option:
        mods.append("ALT")
    if config.shortcut_shift:
        mods.append("SHIFT")
    key = config.shortcut_key.upper()
    return f"bind = {' '.join(mods)}, {key}, exec, {command or trigger_command()}"


def parse_strv(text: str) -> list[str]:
    raw = text.strip()
    if raw.startswith("@as"):
        raw = raw[3:].strip()
    if raw in {"", "[]"}:
        return []
    value = ast.literal_eval(raw)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(text)
    return value


def format_strv(paths: list[str]) -> str:
    return "[" + ", ".join("'" + item.replace("'", "") + "'" for item in paths) + "]"


def gvariant_literal(value: str) -> str:
    """Quote a string for ``gsettings set``. Arrays are already GVariant text."""
    if value.startswith("["):
        return value
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return "'" + escaped + "'"


def unquote(text: str) -> str:
    raw = text.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        return raw[1:-1]
    return raw


def is_texgrab_entry(name: str, command: str) -> bool:
    if name == TEXGRAB_NAME:
        return True
    lowered = command.lower()
    return "texgrab" in lowered and "--trigger" in lowered


def plan_gnome_update(paths: list[str], entries: list[dict]) -> tuple[list[str], str]:
    """Keep every existing path. Reuse the TexGrab slot or append a new one."""
    for entry in entries:
        if is_texgrab_entry(entry.get("name", ""), entry.get("command", "")):
            return list(paths), entry["path"]
    used = set(paths)
    for index in range(100):
        path = f"{CUSTOM_ROOT}/custom{index}/"
        if path not in used:
            return [*paths, path], path
    raise RuntimeError("no free custom keybinding slot")


def plan_gnome_remove(paths: list[str], entries: list[dict]) -> list[str]:
    drop = {
        entry["path"]
        for entry in entries
        if is_texgrab_entry(entry.get("name", ""), entry.get("command", ""))
    }
    return [path for path in paths if path not in drop]


def binding_taken(binding: str, rows: list[tuple[str, str, str]], own_path: str) -> bool:
    for schema, key, value in rows:
        if own_path and own_path in schema:
            continue
        if key == "custom-keybindings":
            continue
        for item in _binding_items(value):
            if item == binding:
                return True
    return False


def _binding_items(value: str) -> list[str]:
    raw = value.strip()
    if raw.startswith("[") or raw.startswith("@as"):
        try:
            return parse_strv(raw)
        except (SyntaxError, ValueError):
            return []
    if not raw or raw in {"@as []", "false", "true"}:
        return []
    return [unquote(raw)]


class DesktopShortcuts:
    def __init__(self, runner=None, kind: str | None = None, which=None) -> None:
        self.runner = runner or _run
        self.kind = kind or detect_desktop()
        self._which = which or system_which
        self._gnome_path = ""

    def bind(self, config) -> bool:
        command = trigger_command()
        if self.kind == "gnome":
            return self._bind_gnome(config, command)
        if self.kind == "kde":
            return self._bind_kde(config, command)
        if self.kind == "sway":
            line = sway_line(config, command)
        elif self.kind == "hyprland":
            line = hyprland_line(config, command)
        else:
            line = sway_line(config, command)
        print(line)
        get_logger().info("paste this shortcut into the compositor config: %s", line)
        return True

    def unbind(self) -> None:
        if self.kind == "gnome":
            self._unbind_gnome()
            return
        if self.kind == "kde":
            self._unbind_kde()
            return
        get_logger().info("compositor config was not edited; remove the TexGrab bindsym if you pasted one")

    def _bind_gnome(self, config, command: str) -> bool:
        if not self._which("gsettings"):
            get_logger().error("gsettings is not installed")
            return False
        binding = gtk_binding(config)
        try:
            paths = parse_strv(self._get(MEDIA_SCHEMA, "custom-keybindings"))
            entries = [self._read_entry(path) for path in paths]
            new_paths, path = plan_gnome_update(paths, entries)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
            get_logger().error("could not read GNOME custom shortcuts: %s", exc)
            return False
        rows = self._shortcut_rows()
        if binding_taken(binding, rows, path) or self._other_custom_uses(entries, path, binding):
            get_logger().error("shortcut %s is already taken", binding)
            return False
        schema = f"{CUSTOM_SCHEMA}:{path}"
        if not self._set(schema, "name", TEXGRAB_NAME):
            return False
        if not self._set(schema, "command", command):
            return False
        if not self._set(schema, "binding", binding):
            return False
        if not self._set(MEDIA_SCHEMA, "custom-keybindings", format_strv(new_paths)):
            return False
        self._gnome_path = path
        get_logger().info("shortcut registered %s via gsettings", config.shortcut_label)
        return True

    def _unbind_gnome(self) -> None:
        if not self._which("gsettings"):
            return
        try:
            paths = parse_strv(self._get(MEDIA_SCHEMA, "custom-keybindings"))
            entries = [self._read_entry(path) for path in paths]
            kept = plan_gnome_remove(paths, entries)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            get_logger().error("could not remove GNOME shortcut: %s", exc)
            return
        self._set(MEDIA_SCHEMA, "custom-keybindings", format_strv(kept))
        self._gnome_path = ""
        get_logger().info("shortcut unregistered")

    def _other_custom_uses(self, entries: list[dict], own_path: str, binding: str) -> bool:
        for entry in entries:
            if entry.get("path") == own_path:
                continue
            if entry.get("binding") == binding:
                return True
        return False

    def _read_entry(self, path: str) -> dict:
        schema = f"{CUSTOM_SCHEMA}:{path}"
        return {
            "path": path,
            "name": unquote(self._get(schema, "name")),
            "command": unquote(self._get(schema, "command")),
            "binding": unquote(self._get(schema, "binding")),
        }

    def _shortcut_rows(self) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []
        gsettings = self._which("gsettings") or "gsettings"
        for schema in SHELL_SCHEMAS:
            completed = self.runner([gsettings, "list-recursively", schema])
            if completed.returncode != 0:
                continue
            for line in completed.stdout.splitlines():
                parts = line.split(None, 2)
                if len(parts) == 3:
                    rows.append((parts[0], parts[1], parts[2]))
        return rows

    def _gsettings(self) -> str:
        # Absolute path. `gsettings` on PATH may be conda's keyfile backend,
        # which GNOME Shell does not read.
        return self._which("gsettings") or "gsettings"

    def _get(self, schema: str, key: str) -> str:
        completed = self.runner([self._gsettings(), "get", schema, key])
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or f"gsettings get {key} failed").strip())
        return completed.stdout.strip()

    def _set(self, schema: str, key: str, value: str) -> bool:
        completed = self.runner([self._gsettings(), "set", schema, key, gvariant_literal(value)])
        if completed.returncode != 0:
            get_logger().error("gsettings set %s failed: %s", key, (completed.stderr or "").strip()[:300])
            return False
        return True

    def _bind_kde(self, config, command: str) -> bool:
        tool = self._which("kwriteconfig6") or self._which("kwriteconfig5")
        if not tool:
            print(hyprland_line(config, command))
            get_logger().error("kwriteconfig is not installed; shortcut was not registered")
            return False
        desktop = Path.home() / ".local" / "share" / "applications" / "texgrab-trigger.desktop"
        desktop.parent.mkdir(parents=True, exist_ok=True)
        desktop.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    "Name=TexGrab",
                    "Comment=Snip an equation to LaTeX",
                    f"Exec={command}",
                    "NoDisplay=true",
                    "Terminal=false",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        value = f"{config.shortcut_label},none,TexGrab"
        completed = self.runner(
            [
                tool,
                "--file",
                "kglobalshortcutsrc",
                "--group",
                "texgrab-trigger.desktop",
                "--key",
                "_launch",
                value,
            ]
        )
        if completed.returncode != 0:
            get_logger().error("kwriteconfig failed: %s", (completed.stderr or "").strip()[:300])
            return False
        get_logger().info("shortcut registered %s via kglobalaccel", config.shortcut_label)
        return True

    def _unbind_kde(self) -> None:
        tool = self._which("kwriteconfig6") or self._which("kwriteconfig5")
        if not tool:
            return
        self.runner(
            [
                tool,
                "--file",
                "kglobalshortcutsrc",
                "--group",
                "texgrab-trigger.desktop",
                "--key",
                "_launch",
                "none,none,TexGrab",
            ]
        )
        get_logger().info("shortcut unregistered")


def _run(args: list[str]) -> CommandResult:
    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)
