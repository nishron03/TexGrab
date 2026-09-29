"""Linux tray process. pystray is imported only when the tray is started."""

from __future__ import annotations

import os
import signal
import sys
import threading
from pathlib import Path

from PIL import Image

from texgrab.clipboard import write_text
from texgrab.config import Config, save_config
from texgrab.hotkey.combo import ShortcutChoice, apply_shortcut, default_choice
from texgrab.linux.binding import BindingManager
from texgrab.linux.capture import CapturePermissionError, grab_region
from texgrab.linux.notify import PERMISSION_MESSAGE, notify
from texgrab.linux.overlay import ensure_gtk
from texgrab.linux.recorder import prepare_typelib_path, prompt_for_shortcut
from texgrab.linux.trigger import AlreadyRunning, TriggerServer
from texgrab.log import get_logger, set_debug
from texgrab.ocr.pix2tex_engine import Pix2TexEngine, sample_equation_path
from texgrab.pipeline import FAILURE_MESSAGE, SnipService

_BUSY = {"Selecting…", "Recognizing…"}


def _default_label() -> str:
    scratch = Config()
    apply_shortcut(scratch, default_choice())
    return scratch.shortcut_label


class LinuxApp:
    def __init__(self, config: Config, *, snip_when_ready: bool = False) -> None:
        self.config = config
        self._snip_when_ready = snip_when_ready
        self.engine = Pix2TexEngine()
        self._model_failed = False
        self._model_ready = False
        self._needs_capture = False
        self._status = "Loading model…"
        self._recording = False
        self._shutting_down = False
        self._stopped = threading.Event()
        self._icon = None
        self._loop = None
        self._bindings: BindingManager | None = None
        self._server: TriggerServer | None = None
        self.service = SnipService(
            engine=self.engine,
            grab=self._grab,
            write=write_text,
            notify=self._deliver_notification,
            set_status=self._set_transient_status,
            idle_status=self._idle_label,
            notifications_enabled=lambda: self.config.notifications,
        )

    def run(self) -> None:
        get_logger().info(
            "TexGrab starting python=%s prefix=%s session=%s desktop=%s",
            sys.version.split()[0],
            sys.prefix,
            os.environ.get("XDG_SESSION_TYPE", ""),
            os.environ.get("XDG_CURRENT_DESKTOP", ""),
        )
        threading.Thread(target=self._warm_model, name="texgrab-model", daemon=True).start()
        prepare_typelib_path()
        ensure_gtk()
        self._server = TriggerServer(self._on_activate)
        self._server.start()
        self._bindings = BindingManager(self._on_activate)
        self._bindings.start(self.config)
        if self._snip_when_ready:
            self._on_activate()
        try:
            self._run_tray()
        finally:
            self.shutdown()

    def shutdown(self) -> bool:
        """Unregister the shortcut, remove the socket, and drop the icon."""
        if self._shutting_down:
            return False
        self._shutting_down = True
        get_logger().info("TexGrab quitting")
        if self._bindings is not None:
            try:
                self._bindings.unregister()
            except Exception:
                get_logger().exception("shortcut unregister failed")
        if self._server is not None:
            try:
                self._server.close()
            except Exception:
                get_logger().exception("trigger socket close failed")
        icon = self._icon
        self._icon = None
        if icon is not None:
            try:
                icon.visible = False
            except Exception:
                get_logger().exception("tray hide failed")
            try:
                icon.stop()
            except Exception:
                get_logger().exception("tray stop failed")
        loop = self._loop
        if loop is not None:
            try:
                loop.quit()
            except Exception:
                get_logger().exception("main loop quit failed")
        self._stopped.set()
        return False

    def _on_activate(self) -> None:
        get_logger().info("shortcut activated")
        self.service.request_snip()

    def _grab(self):
        try:
            image = grab_region()
        except CapturePermissionError:
            self._needs_capture = True
            get_logger().error("screen capture permission missing")
            notify(PERMISSION_MESSAGE, enabled=self.config.notifications)
            return None
        if image is not None:
            self._needs_capture = False
        return image

    def _idle_label(self) -> str:
        if self._needs_capture:
            return "Needs screen capture"
        if self._model_failed:
            return "Model failed to load"
        if not self._model_ready:
            return "Loading model…"
        return "Ready"

    def _set_transient_status(self, text: str) -> None:
        self._status = text
        get_logger().info("status %s", text)
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        icon = self._icon
        if icon is None:
            return
        try:
            icon.title = "TexGrab…" if self._status in _BUSY else "TexGrab"
            icon.update_menu()
        except Exception:
            get_logger().exception("menu update failed")

    def _deliver_notification(self, message: str) -> None:
        notify(message, enabled=True)

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
            self._set_transient_status(self._idle_label())

    def _menu(self, pystray):
        return pystray.Menu(
            pystray.MenuItem("TexGrab", None, enabled=False),
            pystray.MenuItem(lambda _item: f"Status: {self._status}", None, enabled=False),
            pystray.MenuItem(
                lambda _item: f"Shortcut: {self.config.shortcut_label}",
                None,
                enabled=False,
            ),
            pystray.MenuItem("Test OCR", self._test_ocr),
            pystray.MenuItem(
                "Preferences",
                pystray.Menu(
                    pystray.MenuItem(
                        "Show notifications",
                        self._toggle_notifications,
                        checked=lambda _item: self.config.notifications,
                    ),
                    pystray.MenuItem(
                        "Debug logging",
                        self._toggle_debug,
                        checked=lambda _item: self.config.debug,
                    ),
                    pystray.MenuItem("Change shortcut…", self._change_shortcut),
                    pystray.MenuItem(
                        lambda _item: f"Reset shortcut to {_default_label()}",
                        self._reset_shortcut,
                    ),
                ),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

    def _test_ocr(self, _icon=None, _item=None) -> None:
        path = sample_equation_path()
        if not path.is_file():
            get_logger().error("sample equation image is missing")
            notify(FAILURE_MESSAGE, enabled=self.config.notifications)
            return
        with Image.open(path) as image:
            image.load()
            copy = image.copy()
        self.service.request_image(copy)

    def _toggle_notifications(self, _icon=None, _item=None) -> None:
        self.config.notifications = not self.config.notifications
        save_config(self.config)
        get_logger().info("notifications=%s", self.config.notifications)
        self._refresh_icon()

    def _toggle_debug(self, _icon=None, _item=None) -> None:
        self.config.debug = not self.config.debug
        save_config(self.config)
        set_debug(self.config.debug)
        get_logger().info("debug=%s", self.config.debug)
        self._refresh_icon()

    def _reset_shortcut(self, _icon=None, _item=None) -> None:
        if self._recording:
            return
        self._install_shortcut(default_choice())

    def _change_shortcut(self, _icon=None, _item=None) -> None:
        if self._recording:
            return
        self._recording = True
        if self._bindings is not None:
            self._bindings.unregister()
        prompt_for_shortcut(self.config.shortcut_label, self._shortcut_chosen)

    def _shortcut_chosen(self, choice: ShortcutChoice | None) -> None:
        self._recording = False
        if choice is None:
            self._rebind_current()
            get_logger().info("shortcut change cancelled")
            self._refresh_icon()
            return
        self._install_shortcut(choice)

    def _install_shortcut(self, choice: ShortcutChoice) -> None:
        previous = self._snapshot()
        apply_shortcut(self.config, choice)
        if self._rebind_current():
            save_config(self.config)
            get_logger().info("shortcut changed to %s", self.config.shortcut_label)
            self._refresh_icon()
            return
        get_logger().error("That shortcut could not be registered. It may already be in use.")
        self._restore(previous)
        self._rebind_current()
        self._refresh_icon()
        notify(
            "That shortcut could not be registered. It may already be in use.",
            enabled=self.config.notifications,
        )

    def _rebind_current(self) -> bool:
        if self._bindings is None:
            return False
        try:
            return bool(self._bindings.rebind(self.config))
        except Exception:
            get_logger().exception("shortcut rebind failed")
            return False

    def _snapshot(self):
        config = self.config
        return (
            config.shortcut_key,
            config.shortcut_command,
            config.shortcut_control,
            config.shortcut_shift,
            config.shortcut_option,
        )

    def _restore(self, snapshot) -> None:
        (
            self.config.shortcut_key,
            self.config.shortcut_command,
            self.config.shortcut_control,
            self.config.shortcut_shift,
            self.config.shortcut_option,
        ) = snapshot

    def _quit(self, _icon=None, _item=None) -> None:
        self.shutdown()

    def _run_tray(self) -> None:
        prepare_typelib_path()
        try:
            import pystray
        except Exception:
            get_logger().exception("tray icon could not be shown; texgrab --trigger still works")
            self._run_headless()
            return
        path = _tray_path()
        try:
            with Image.open(path) as image:
                image.load()
                icon_image = image.copy()
        except Exception:
            get_logger().exception("tray icon could not be shown; texgrab --trigger still works")
            self._run_headless()
            return
        try:
            icon = pystray.Icon("texgrab", icon_image, "TexGrab", self._menu(pystray))
        except Exception:
            get_logger().exception("tray icon could not be shown; texgrab --trigger still works")
            self._run_headless()
            return
        self._icon = icon
        try:
            icon.run(setup=self._on_tray_ready)
        except Exception:
            get_logger().exception("tray icon could not be shown; texgrab --trigger still works")
            self._icon = None
            if not self._shutting_down:
                self._run_headless()

    def _on_tray_ready(self, icon) -> None:
        icon.visible = True
        try:
            from gi.repository import GLib

            GLib.idle_add(self._install_signals)
        except Exception:
            get_logger().exception("could not schedule quit signals")

    def _install_signals(self) -> bool:
        try:
            from gi.repository import GLib

            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.shutdown)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.shutdown)
        except Exception:
            get_logger().exception("could not install quit signals")
        return False

    def _run_headless(self) -> None:
        get_logger().error("no tray icon; waiting for texgrab --trigger")
        prepare_typelib_path()
        try:
            from gi.repository import GLib
        except Exception:
            get_logger().exception("GTK main loop is unavailable")
            self._stopped.wait()
            return
        self._install_signals()
        self._loop = GLib.MainLoop()
        self._loop.run()


def _tray_path() -> Path:
    return Path(__file__).resolve().parents[1] / "resources" / "tray.png"


def run_app(config: Config, *, snip_when_ready: bool = False) -> None:
    try:
        LinuxApp(config, snip_when_ready=snip_when_ready).run()
    except AlreadyRunning as exc:
        get_logger().info("TexGrab is already running (%s)", exc)
        if snip_when_ready:
            from texgrab.linux.trigger import send_snip

            if send_snip():
                get_logger().info("trigger sent")
            else:
                get_logger().error("trigger failed")
