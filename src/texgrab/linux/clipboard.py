"""Clipboard via wl-copy on Wayland and xclip or xsel on X11.

An empty string is not written, so a failed recognition cannot clear what the
user already copied. The text itself is not logged.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

from texgrab.clipboard import ClipboardError
from texgrab.log import get_logger


def session_kind() -> str:
    kind = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()
    if kind in {"wayland", "x11"}:
        return kind
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "wayland"


def tool_path(name: str) -> str | None:
    """Resolve a helper binary.

    On Wayland, GNU wl-clipboard is required. The conda-forge package
    wl-clipboard-rs speaks only wlr-data-control, which GNOME does not
    implement, so a binary whose version string is ``wl-clipboard`` wins.
    """
    candidates = _candidates(name)
    if name in {"wl-copy", "wl-paste"}:
        for path in candidates:
            if "wl-clipboard" in _version_text(path):
                return str(path)
    if candidates:
        return str(candidates[0])
    return None


def _candidates(name: str) -> list[Path]:
    raw = [
        Path(sys.executable).resolve().parent / name,
        Path.home() / ".local" / "bin" / name,
        Path("/usr/bin") / name,
    ]
    found = shutil.which(name)
    if found:
        raw.append(Path(found))
    seen: set[str] = set()
    out: list[Path] = []
    for path in raw:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.is_file() and os.access(path, os.X_OK):
            out.append(path)
    return out


def _version_text(path: Path) -> str:
    try:
        completed = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (completed.stdout or "") + (completed.stderr or "")


def read_text() -> str:
    if session_kind() == "x11":
        return _read_x11()
    return _read_wayland()


def write_text(text: str) -> None:
    if not isinstance(text, str):
        raise ClipboardError("clipboard text must be a string")
    if text == "":
        get_logger().info("clipboard skipped empty")
        return
    if session_kind() == "x11":
        _write_x11(text)
    else:
        _write_wayland(text)
    get_logger().info("clipboard wrote chars=%s", len(text))


def change_count() -> int:
    """Content hash. Equal values mean the clipboard text did not change."""
    try:
        text = read_text()
    except ClipboardError:
        return 0
    return zlib.adler32(text.encode("utf-8")) & 0xFFFFFFFF


def _run(command: list[str], data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    """Run a clipboard helper.

    ``wl-copy`` forks a process that keeps serving the selection. That child
    inherits stdout and stderr, so a pipe would stay open and ``subprocess``
    would wait forever. The error text is collected from a file instead.
    """
    try:
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            completed = subprocess.run(
                command,
                input=data,
                stdout=out,
                stderr=err,
                check=False,
                start_new_session=True,
            )
            out.seek(0)
            err.seek(0)
            stdout = out.read()
            stderr = err.read()
    except OSError as exc:
        raise ClipboardError(str(exc)) from exc
    return subprocess.CompletedProcess(command, completed.returncode, stdout, stderr)


def _read_wayland() -> str:
    exe = tool_path("wl-paste")
    if not exe:
        raise ClipboardError("wl-paste is not installed")
    completed = _run([exe, "-n", "-t", "text/plain"])
    if completed.returncode != 0:
        return ""
    return completed.stdout.decode("utf-8", "replace")


def _write_wayland(text: str) -> None:
    exe = tool_path("wl-copy")
    if not exe:
        raise ClipboardError("wl-copy is not installed")
    completed = _run([exe, "-t", "text/plain"], text.encode("utf-8"))
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise ClipboardError(detail[:300] or "wl-copy failed")


def _read_x11() -> str:
    command = _x11_read_command()
    completed = _run(command)
    if completed.returncode != 0:
        return ""
    return completed.stdout.decode("utf-8", "replace")


def _write_x11(text: str) -> None:
    command = _x11_write_command()
    completed = _run(command, text.encode("utf-8"))
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise ClipboardError(detail[:300] or "clipboard write failed")


def _x11_write_command() -> list[str]:
    xclip = tool_path("xclip")
    if xclip:
        return [xclip, "-selection", "clipboard", "-t", "text/plain"]
    xsel = tool_path("xsel")
    if xsel:
        return [xsel, "--clipboard", "--input"]
    raise ClipboardError("xclip or xsel is not installed")


def _x11_read_command() -> list[str]:
    xclip = tool_path("xclip")
    if xclip:
        return [xclip, "-o", "-selection", "clipboard"]
    xsel = tool_path("xsel")
    if xsel:
        return [xsel, "--clipboard", "--output"]
    raise ClipboardError("xclip or xsel is not installed")
