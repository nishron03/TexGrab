"""Menu-bar application. The menu is the whole interface."""

from __future__ import annotations

import sys
import threading

import rumps
from PIL import Image

from texgrab.capture.region import grab_region
from texgrab.clipboard import write_text
from texgrab.config import Config, save_config
from texgrab.hotkey.carbon import HotKeyManager
from texgrab.log import get_logger, set_debug
from texgrab.mainthread import call_on_main, call_on_main_sync
from texgrab.notify import notify
from texgrab.ocr.pix2tex_engine import Pix2TexEngine, sample_equation_path
from texgrab.permissions import request_screen_recording, screen_recording_granted
from texgrab.pipeline import FAILURE_MESSAGE, SnipService


class TexGrabApp(rumps.App):
    def __init__(self, config: Config) -> None:
        super().__init__("TexGrab", title="TexGrab", quit_button=None)
        self.config = config
        self.engine = Pix2TexEngine()
        self._model_failed = False
        self._model_ready = False
        self._perm_ok = True

        self.title_item = rumps.MenuItem("TexGrab")
        self.title_item.set_callback(None)
        self.status_item = rumps.MenuItem("Status: Loading model…")
        self.status_item.set_callback(None)
        self.shortcut_item = rumps.MenuItem(f"Shortcut: {config.shortcut_label}")
        self.shortcut_item.set_callback(None)
        self.notify_item = rumps.MenuItem(
            "Show notifications", callback=self._toggle_notifications
        )
        self.debug_item = rumps.MenuItem("Debug logging", callback=self._toggle_debug)
        self.notify_item.state = 1 if config.notifications else 0
        self.debug_item.state = 1 if config.debug else 0
        self.test_item = rumps.MenuItem("Test OCR", callback=self._test_ocr)
        self.quit_item = rumps.MenuItem("Quit", callback=self._quit)
        self.menu = [
            self.title_item,
            self.status_item,
            self.shortcut_item,
            self.test_item,
            [rumps.MenuItem("Preferences"), [self.notify_item, self.debug_item]],
            None,
            self.quit_item,
        ]

        self.service = SnipService(
            engine=self.engine,
            grab=grab_region,
            write=self._write_clipboard,
            notify=self._deliver_notification,
            set_status=self._set_transient_status,
            idle_status=self._idle_label,
            notifications_enabled=lambda: self.config.notifications,
        )
        self._hotkey = HotKeyManager(config, self._on_hotkey)
        try:
            self._hotkey.register()
        except Exception:
            get_logger().exception("shortcut registration failed")
            self.shortcut_item.title = "Shortcut: failed to register"

        threading.Thread(target=self._warm_model, name="texgrab-model", daemon=True).start()
        call_on_main(self._check_permission)

    def _idle_label(self) -> str:
        if not self._perm_ok:
            return "Needs Screen Recording"
        if self._model_failed:
            return "Model failed to load"
        if not self._model_ready:
            return "Loading model…"
        return "Ready"

    def _apply_status(self, text: str) -> None:
        self.status_item.title = f"Status: {text}"
        self.title = "TexGrab" if text == "Ready" else "TexGrab…"

    def _set_transient_status(self, text: str) -> None:
        call_on_main(lambda: self._apply_status(text))

    def _write_clipboard(self, text: str) -> None:
        call_on_main_sync(lambda: write_text(text))

    def _deliver_notification(self, message: str) -> None:
        notify(message, enabled=True)

    def _check_permission(self) -> None:
        self._perm_ok = screen_recording_granted()
        if not self._perm_ok:
            get_logger().error(
                "Screen Recording is not granted. System Settings > Privacy & Security > "
                "Screen Recording, then enable the app that launched TexGrab "
                "(Terminal, iTerm, Cursor, or TexGrab.app). Remove it and add it again "
                "if it is already listed but capture still fails."
            )
            request_screen_recording()
            self._perm_ok = screen_recording_granted()
            if not self._perm_ok:
                notify(
                    "Screen Recording permission is required",
                    enabled=self.config.notifications,
                )
        if not self.service.busy:
            self._apply_status(self._idle_label())

    def _on_hotkey(self) -> None:
        get_logger().info("shortcut activated")
        granted = screen_recording_granted()
        self._perm_ok = granted
        if not granted:
            get_logger().error("screen recording permission missing")
            call_on_main(lambda: self._apply_status("Needs Screen Recording"))
            notify(
                "Screen Recording permission is required",
                enabled=self.config.notifications,
            )
            return
        self.service.request_snip()

    def _test_ocr(self, _sender) -> None:
        path = sample_equation_path()
        if not path.is_file():
            get_logger().error("sample equation image is missing")
            notify(FAILURE_MESSAGE, enabled=self.config.notifications)
            return
        with Image.open(path) as image:
            image.load()
            copy = image.copy()
        if not self.service.request_image(copy):
            return

    def _toggle_notifications(self, sender) -> None:
        self.config.notifications = not self.config.notifications
        sender.state = 1 if self.config.notifications else 0
        save_config(self.config)
        get_logger().info("notifications=%s", self.config.notifications)

    def _toggle_debug(self, sender) -> None:
        self.config.debug = not self.config.debug
        sender.state = 1 if self.config.debug else 0
        save_config(self.config)
        set_debug(self.config.debug)
        get_logger().info("debug=%s", self.config.debug)

    def _quit(self, _sender) -> None:
        try:
            self._hotkey.unregister()
        except Exception:
            get_logger().exception("shortcut unregister failed")
        rumps.quit_application()

    def _warm_model(self) -> None:
        try:
            self.engine.load()
        except Exception:
            get_logger().exception("model load failed")
            self._model_failed = True
            self._model_ready = False
        else:
            self._model_ready = True
            self._model_failed = False
        if not self.service.busy:
            call_on_main(lambda: self._apply_status(self._idle_label()))


def run_app(config: Config) -> None:
    get_logger().info(
        "TexGrab starting python=%s prefix=%s",
        sys.version.split()[0],
        sys.prefix,
    )
    TexGrabApp(config).run()
