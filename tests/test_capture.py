import subprocess
from pathlib import Path

from PIL import Image

from texgrab.capture.region import CaptureError, grab_region
from texgrab.clipboard import change_count


def test_capture_command_does_not_touch_clipboard(tmp_path):
    seen = {}

    def runner(command):
        seen["command"] = command
        Image.new("RGB", (3, 2), (8, 9, 10)).save(command[-1])
        return subprocess.CompletedProcess(command, 0, stderr=b"")

    before = change_count()
    image = grab_region(runner=runner)
    assert change_count() == before
    assert image is not None
    assert image.size == (3, 2)
    assert image.getpixel((0, 0)) == (8, 9, 10)
    command = seen["command"]
    assert command[0] == "screencapture"
    assert "-i" in command
    assert "-c" not in command
    assert not Path(command[-1]).exists()
    assert not Path(command[-1]).parent.exists()


def test_cancel_returns_none_and_deletes_temp_dir():
    seen = {}

    def runner(command):
        seen["command"] = command
        return subprocess.CompletedProcess(command, 1, stderr=b"")

    assert grab_region(runner=runner) is None
    assert not Path(seen["command"][-1]).parent.exists()


def test_screencapture_error_raises_and_deletes_temp_dir():
    seen = {}

    def runner(command):
        seen["command"] = command
        return subprocess.CompletedProcess(command, 1, stderr=b"could not create image from display")

    try:
        grab_region(runner=runner)
    except CaptureError as exc:
        assert "could not create image" in str(exc)
    else:
        raise AssertionError("expected CaptureError")
    assert not Path(seen["command"][-1]).parent.exists()
