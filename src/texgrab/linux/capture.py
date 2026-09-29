"""Region capture. The first working backend is used. Nothing is copied.

Order: xdg-desktop-portal Screenshot, grim/slurp, spectacle, gnome-screenshot, maim.
A private temp PNG (directory mode 0700) is deleted before the image is returned.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from texgrab.capture.region import CaptureError
from texgrab.log import get_logger

CLIPBOARD_FLAGS = {"-c", "--clipboard", "--copy"}


class CapturePermissionError(CaptureError):
    """The desktop refused screen capture."""


@dataclass
class PortalShot:
    response: int
    results: dict
    error: str = ""


def command_for(backend: str, path: Path) -> list[str]:
    target = str(path)
    if backend == "grim":
        command = ["grim", "-g", "-", target]
    elif backend == "spectacle":
        command = ["spectacle", "-b", "-r", "-n", "-o", target]
    elif backend == "gnome-screenshot":
        command = ["gnome-screenshot", "-a", "-f", target]
    elif backend == "maim":
        command = ["maim", "-s", target]
    else:
        raise CaptureError(f"unknown capture backend {backend}")
    reject_clipboard_flags(command)
    return command


def reject_clipboard_flags(command: list[str]) -> None:
    found = CLIPBOARD_FLAGS.intersection(command)
    if found:
        raise CaptureError("refusing clipboard flag " + " ".join(sorted(found)))


def select_backend(probe_portal, which) -> str:
    if probe_portal():
        return "portal"
    if which("slurp") and which("grim"):
        return "grim"
    if which("spectacle"):
        return "spectacle"
    if which("gnome-screenshot"):
        return "gnome-screenshot"
    if which("maim"):
        return "maim"
    raise CaptureError("no screen capture tool is available")


def grab_region(runner=None, backend=None, portal=None) -> Image.Image | None:
    """Return the selected image, or None if the user cancelled."""
    if backend is None:
        from texgrab.linux.portal import screenshot_available

        backend = select_backend(
            (lambda: False) if portal is not None else screenshot_available,
            _which,
        )
    directory = Path(tempfile.mkdtemp(prefix="texgrab-"))
    os.chmod(directory, 0o700)
    path = directory / "capture.png"
    get_logger().info("capture start backend=%s", backend)
    try:
        if backend == "portal":
            _fill_from_portal(path, portal)
        elif backend == "grim":
            _fill_from_grim(path, runner)
        else:
            command = command_for(backend, path)
            completed = _invoke(command, runner)
            _raise_if_failed(path, completed)
        if not path.is_file() or path.stat().st_size == 0:
            get_logger().info("capture cancelled")
            return None
        with Image.open(path) as image:
            image.load()
            copied = image.copy()
        get_logger().info("capture ok %sx%s", copied.width, copied.height)
        return copied
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def _which(name: str) -> str | None:
    return shutil.which(name)


def _invoke(command: list[str], runner, data: bytes | None = None):
    if runner is not None:
        return runner(command)
    return subprocess.run(command, input=data, check=False, capture_output=True)


def _stderr_text(completed) -> str:
    stderr = getattr(completed, "stderr", b"") or b""
    if isinstance(stderr, bytes):
        return stderr.decode("utf-8", "replace").strip()
    return str(stderr).strip()


def _stdout_bytes(completed) -> bytes:
    stdout = getattr(completed, "stdout", b"") or b""
    if isinstance(stdout, str):
        return stdout.encode("utf-8")
    return bytes(stdout)


def _raise_if_failed(path: Path, completed) -> None:
    if path.is_file() and path.stat().st_size > 0:
        return
    text = _stderr_text(completed)
    code = getattr(completed, "returncode", 0)
    if code not in (0, None) and text:
        get_logger().error("capture failed: %s", text[:500])
        raise CaptureError(text[:500])


def _fill_from_grim(path: Path, runner) -> None:
    slurp = _invoke(["slurp"], runner)
    geometry = _stdout_bytes(slurp).strip()
    text = _stderr_text(slurp)
    if not geometry:
        if getattr(slurp, "returncode", 0) not in (0, None) and text:
            get_logger().error("capture failed: %s", text[:500])
            raise CaptureError(text[:500])
        return
    command = command_for("grim", path)
    reject_clipboard_flags(command)
    if runner is None:
        completed = subprocess.run(command, input=geometry + b"\n", check=False, capture_output=True)
    else:
        completed = runner(command)
    _raise_if_failed(path, completed)


def _fill_from_portal(path: Path, portal) -> None:
    client = portal if portal is not None else _LivePortal()
    shot = client.capture()
    if not isinstance(shot, PortalShot):
        response = int(shot[0])
        results = shot[1] if len(shot) > 1 else {}
        error = shot[2] if len(shot) > 2 else ""
        shot = PortalShot(response, results or {}, error or "")
    uri = _result_uri(shot.results)
    error = (shot.error or _result_error(shot.results)).strip()
    get_logger().info("capture portal response=%s", shot.response)
    if _is_permission(shot.response, error):
        raise CapturePermissionError(error or "permission denied")
    if shot.response != 0 or not uri:
        if error and shot.response not in (0, 1):
            get_logger().error("capture failed: %s", error[:500])
            raise CaptureError(error[:500])
        return
    source = _uri_to_path(uri)
    try:
        if source.is_file() and source.stat().st_size > 0:
            shutil.copyfile(source, path)
    finally:
        try:
            source.unlink(missing_ok=True)
        except OSError:
            get_logger().exception("could not delete portal capture file")


def _result_uri(results: dict) -> str:
    value = results.get("uri") if isinstance(results, dict) else None
    return str(value) if value else ""


def _result_error(results: dict) -> str:
    if not isinstance(results, dict):
        return ""
    for key in ("error", "message", "stderr"):
        value = results.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _is_permission(response: int, error: str) -> bool:
    text = error.lower().replace(".", "")
    if any(word in text for word in ("permission", "notallowed", "not allowed", "access denied", "denied")):
        return True
    return False


def _uri_to_path(uri: str) -> Path:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "file":
        raise CaptureError("capture uri is not a file")
    return Path(urllib.parse.unquote(parsed.path))


class _LivePortal:
    def capture(self) -> PortalShot:
        from texgrab.linux.portal import interactive_screenshot

        return interactive_screenshot()
