"""Image to LaTeX to clipboard, plus the background snip worker."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from PIL import Image

from texgrab.capture.region import CaptureError
from texgrab.clipboard import write_text
from texgrab.log import get_logger
from texgrab.ocr.base import OCREngine

SUCCESS_MESSAGE = "LaTeX copied to clipboard"
FAILURE_MESSAGE = "LaTeX OCR failed"


@dataclass
class PipelineResult:
    ok: bool
    latex: str = ""
    error: str = ""


def run_image(image: Image.Image, engine: OCREngine, *, write=None) -> PipelineResult:
    """Run OCR. Write the clipboard only when the result is a non-empty string."""
    log = get_logger()
    width, height = image.size
    log.info("ocr start %sx%s", width, height)
    try:
        latex = engine.recognize(image)
    except Exception:
        log.exception("ocr failed")
        return PipelineResult(ok=False, error="ocr_error")
    latex = "" if latex is None else str(latex).strip()
    if not latex:
        log.error("ocr returned empty text")
        return PipelineResult(ok=False, error="empty")
    log.info("ocr end chars=%s", len(latex))
    if log.isEnabledFor(logging.DEBUG):
        log.debug("ocr text=%s", latex)
    writer = write_text if write is None else write
    try:
        writer(latex)
    except Exception:
        log.exception("clipboard write failed")
        return PipelineResult(ok=False, latex=latex, error="clipboard")
    return PipelineResult(ok=True, latex=latex)


class SnipService:
    """One snip at a time. Cancel is silent. OCR and capture failures notify."""

    def __init__(
        self,
        engine: OCREngine,
        grab,
        write,
        notify,
        set_status,
        idle_status,
        notifications_enabled,
    ) -> None:
        self.engine = engine
        self.grab = grab
        self.write = write
        self._notify = notify
        self.set_status = set_status
        self.idle_status = idle_status
        self.notifications_enabled = notifications_enabled
        self._lock = threading.Lock()
        self._busy = False
        self._thread: threading.Thread | None = None

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    def request_snip(self) -> bool:
        if not self._begin():
            get_logger().info("shortcut ignored; snip already running")
            return False
        self._thread = threading.Thread(
            target=self._capture_and_recognize,
            name="texgrab-snip",
            daemon=True,
        )
        self._thread.start()
        return True

    def request_image(self, image: Image.Image) -> bool:
        if not self._begin():
            get_logger().info("test OCR ignored; snip already running")
            return False
        self._thread = threading.Thread(
            target=lambda: self._recognize_only(image),
            name="texgrab-test",
            daemon=True,
        )
        self._thread.start()
        return True

    def join(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _begin(self) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            return True

    def _end(self) -> None:
        with self._lock:
            self._busy = False

    def _notify_user(self, message: str) -> None:
        try:
            enabled = bool(self.notifications_enabled())
        except Exception:
            get_logger().exception("notification preference lookup failed")
            enabled = True
        if not enabled:
            get_logger().info("notification suppressed: %s", message)
            return
        try:
            self._notify(message)
        except Exception:
            get_logger().exception("notification failed")

    def _finish(self) -> None:
        try:
            self.set_status(self.idle_status())
        except Exception:
            get_logger().exception("status reset failed")
        self._end()

    def _capture_and_recognize(self) -> None:
        try:
            self.set_status("Selecting…")
            try:
                image = self.grab()
            except CaptureError as exc:
                get_logger().error("capture failed: %s", exc)
                self._notify_user(FAILURE_MESSAGE)
                return
            except Exception:
                get_logger().exception("capture failed")
                self._notify_user(FAILURE_MESSAGE)
                return
            if image is None:
                return
            self._recognize_body(image)
        finally:
            self._finish()

    def _recognize_only(self, image: Image.Image) -> None:
        try:
            self._recognize_body(image)
        finally:
            self._finish()

    def _recognize_body(self, image: Image.Image) -> None:
        self.set_status("Recognizing…")
        result = run_image(image, self.engine, write=self.write)
        if result.ok:
            self._notify_user(SUCCESS_MESSAGE)
            return
        get_logger().error("pipeline failed: %s", result.error)
        self._notify_user(FAILURE_MESSAGE)
