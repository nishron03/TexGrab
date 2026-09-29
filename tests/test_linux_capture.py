"""Linux region capture. The temp PNG is private and never copied to the clipboard."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from texgrab.capture.region import CaptureError
from texgrab.linux.capture import (
    CapturePermissionError,
    PortalShot,
    command_for,
    grab_region,
    reject_clipboard_flags,
)


def _png(path, size=(4, 3), color=(1, 2, 3)):
    from PIL import Image

    Image.new("RGB", size, color).save(path)


def test_commands_have_no_clipboard_flag(tmp_path):
    path = tmp_path / "capture.png"
    for backend in ("grim", "spectacle", "gnome-screenshot", "maim"):
        command = command_for(backend, path)
        assert "-c" not in command
        assert "--clipboard" not in command
        assert "--copy" not in command
        assert str(path) in command
    assert command_for("gnome-screenshot", path)[:3] == ["gnome-screenshot", "-a", "-f"]
    assert "-c" not in command_for("spectacle", path)
    with pytest.raises(CaptureError):
        reject_clipboard_flags(["tool", "-c"])


def _patch_temp(monkeypatch, tmp_path, created):
    real = tempfile.mkdtemp

    def fake_mkdtemp(*_args, **kwargs):
        path = real(dir=tmp_path, prefix=kwargs.get("prefix", "texgrab-"))
        created["dir"] = path
        return path

    monkeypatch.setattr("texgrab.linux.capture.tempfile.mkdtemp", fake_mkdtemp)


def test_capture_writes_temp_png_and_deletes_it(tmp_path, monkeypatch):
    created = {}
    _patch_temp(monkeypatch, tmp_path, created)

    def runner(command):
        assert "-c" not in command
        _png(command[-1])
        return subprocess.CompletedProcess(command, 0, stderr=b"")

    image = grab_region(runner=runner, backend="gnome-screenshot")
    assert image is not None
    assert image.size == (4, 3)
    assert image.getpixel((0, 0)) == (1, 2, 3)
    assert not Path(created["dir"]).exists()


def test_cancel_returns_none_and_deletes_temp_dir(tmp_path, monkeypatch):
    created = {}
    _patch_temp(monkeypatch, tmp_path, created)

    def runner(command):
        return subprocess.CompletedProcess(command, 1, stderr=b"")

    assert grab_region(runner=runner, backend="maim") is None
    assert not Path(created["dir"]).exists()


def test_failure_raises_and_deletes_temp_dir(tmp_path, monkeypatch):
    created = {}
    _patch_temp(monkeypatch, tmp_path, created)

    def runner(command):
        return subprocess.CompletedProcess(command, 1, stderr=b"could not capture")

    with pytest.raises(CaptureError) as exc:
        grab_region(runner=runner, backend="spectacle")
    assert "could not capture" in str(exc.value)
    assert not Path(created["dir"]).exists()


def test_portal_cancel_is_silent(tmp_path, monkeypatch):
    created = {}
    _patch_temp(monkeypatch, tmp_path, created)

    class Portal:
        def capture(self):
            return PortalShot(1, {})

    assert grab_region(backend="portal", portal=Portal()) is None
    assert not Path(created["dir"]).exists()


def test_portal_permission_raises_and_deletes_temp_dir(tmp_path, monkeypatch):
    created = {}
    _patch_temp(monkeypatch, tmp_path, created)

    class Portal:
        def capture(self):
            return PortalShot(2, {}, "org.freedesktop.portal.Error.NotAllowed: permission denied")

    with pytest.raises(CapturePermissionError):
        grab_region(backend="portal", portal=Portal())
    assert not Path(created["dir"]).exists()


def test_portal_file_uri_is_copied_and_removed(tmp_path, monkeypatch):
    source = tmp_path / "portal.png"
    _png(source, size=(5, 2), color=(9, 8, 7))
    created = {}
    _patch_temp(monkeypatch, tmp_path, created)

    class Portal:
        def capture(self):
            return PortalShot(0, {"uri": source.as_uri()})

    image = grab_region(backend="portal", portal=Portal())
    assert image is not None
    assert image.size == (5, 2)
    assert not source.exists()
    assert not Path(created["dir"]).exists()
