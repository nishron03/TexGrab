import threading

from PIL import Image

from texgrab.capture.region import CaptureError
from texgrab.pipeline import FAILURE_MESSAGE, SUCCESS_MESSAGE, SnipService, run_image


class _Engine:
    def __init__(self, text="E = mc^2", error=None):
        self.text = text
        self.error = error
        self.seen = None

    def recognize(self, image):
        self.seen = image
        if self.error is not None:
            raise self.error
        return self.text


def _image():
    return Image.new("RGB", (8, 4), "white")


def test_pipeline_writes_latex():
    written = []
    result = run_image(_image(), _Engine(r"\alpha"), write=written.append)
    assert result.ok
    assert result.latex == r"\alpha"
    assert written == [r"\alpha"]


def test_pipeline_ocr_error_does_not_write():
    written = []
    result = run_image(_image(), _Engine(error=RuntimeError("boom")), write=written.append)
    assert not result.ok
    assert result.error == "ocr_error"
    assert written == []


def test_pipeline_empty_result_does_not_write():
    written = []
    result = run_image(_image(), _Engine(text="   "), write=written.append)
    assert not result.ok
    assert result.error == "empty"
    assert written == []


def test_pipeline_clipboard_error_is_reported():
    def fail(_text):
        raise RuntimeError("pasteboard")

    result = run_image(_image(), _Engine("x"), write=fail)
    assert not result.ok
    assert result.error == "clipboard"
    assert result.latex == "x"


def test_cancel_does_not_notify_or_write():
    notes = []
    written = []
    service = SnipService(
        engine=_Engine(),
        grab=lambda: None,
        write=written.append,
        notify=notes.append,
        set_status=lambda _status: None,
        idle_status=lambda: "Ready",
        notifications_enabled=lambda: True,
    )
    assert service.request_snip()
    service.join(timeout=2)
    assert notes == []
    assert written == []
    assert not service.busy


def test_capture_error_notifies_failure():
    notes = []

    def grab():
        raise CaptureError("permission")

    service = SnipService(
        engine=_Engine(),
        grab=grab,
        write=lambda _text: None,
        notify=notes.append,
        set_status=lambda _status: None,
        idle_status=lambda: "Ready",
        notifications_enabled=lambda: True,
    )
    assert service.request_snip()
    service.join(timeout=2)
    assert notes == [FAILURE_MESSAGE]


def test_success_notifies_and_writes():
    notes = []
    written = []
    service = SnipService(
        engine=_Engine(r"\beta"),
        grab=lambda: _image(),
        write=written.append,
        notify=notes.append,
        set_status=lambda _status: None,
        idle_status=lambda: "Ready",
        notifications_enabled=lambda: True,
    )
    assert service.request_image(_image())
    service.join(timeout=2)
    assert written == [r"\beta"]
    assert notes == [SUCCESS_MESSAGE]


def test_second_snip_is_ignored_while_busy():
    started = threading.Event()
    release = threading.Event()

    def grab():
        started.set()
        assert release.wait(2)
        return None

    service = SnipService(
        engine=_Engine(),
        grab=grab,
        write=lambda _text: None,
        notify=lambda _message: None,
        set_status=lambda _status: None,
        idle_status=lambda: "Ready",
        notifications_enabled=lambda: True,
    )
    assert service.request_snip()
    assert started.wait(2)
    assert service.request_snip() is False
    release.set()
    service.join(timeout=2)
    assert service.request_snip()
    service.join(timeout=2)


def test_notifications_can_be_suppressed():
    notes = []
    service = SnipService(
        engine=_Engine("y"),
        grab=lambda: _image(),
        write=lambda _text: None,
        notify=notes.append,
        set_status=lambda _status: None,
        idle_status=lambda: "Ready",
        notifications_enabled=lambda: False,
    )
    assert service.request_image(_image())
    service.join(timeout=2)
    assert notes == []
