"""Pick the first shortcut mechanism that works on this session."""

from __future__ import annotations

import os

from texgrab.linux.desktop_bind import DesktopShortcuts
from texgrab.linux.portal import GlobalShortcutPortal
from texgrab.linux.x11_hotkey import X11Hotkey
from texgrab.log import get_logger


class BindingManager:
    def __init__(self, on_activate, *, desktop=None, portal_factory=None, x11_factory=None) -> None:
        self._on_activate = on_activate
        self._desktop = desktop if desktop is not None else DesktopShortcuts()
        self._portal_factory = portal_factory or (lambda: GlobalShortcutPortal(on_activate))
        self._x11_factory = x11_factory or (lambda: X11Hotkey(on_activate))
        self._x11 = None
        self._portal = None
        self.method = "socket"

    def start(self, config) -> str:
        session = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()
        if session == "x11":
            self._x11 = self._x11_factory()
            try:
                if self._x11.bind(config):
                    self.method = "x11"
                    get_logger().info("shortcut bound x11 %s", config.shortcut_label)
                    return self.method
            except Exception:
                get_logger().exception("X11 shortcut grab failed")
            get_logger().error("X11 shortcut grab failed")
        else:
            self._portal = self._portal_factory()
            try:
                if self._portal.bind(config):
                    self.method = "portal"
                    get_logger().info(
                        "shortcut bound portal %s; if a permission dialog is open, allow TexGrab",
                        config.shortcut_label,
                    )
                    return self.method
            except Exception:
                get_logger().exception("GlobalShortcuts portal failed")
            get_logger().info("GlobalShortcuts portal is not available; using a desktop shortcut")
        try:
            if self._desktop.bind(config):
                self.method = "desktop"
                get_logger().info("shortcut bound desktop %s %s", self._desktop.kind, config.shortcut_label)
                return self.method
        except Exception:
            get_logger().exception("desktop shortcut registration failed")
        self.method = "socket"
        get_logger().error("no global shortcut registered; texgrab --trigger still works")
        return self.method

    def rebind(self, config) -> bool:
        try:
            if self.method == "x11" and self._x11 is not None:
                return bool(self._x11.bind(config))
            if self.method == "portal" and self._portal is not None:
                return bool(self._portal.bind(config))
            if self.method == "desktop":
                return bool(self._desktop.bind(config))
        except Exception:
            get_logger().exception("shortcut rebind failed")
            return False
        return self.start(config) != "socket"

    def unregister(self) -> None:
        if self._x11 is not None:
            try:
                self._x11.unbind()
                self._x11.close()
            except Exception:
                get_logger().exception("X11 ungrab failed")
        if self._portal is not None:
            try:
                self._portal.close()
            except Exception:
                get_logger().exception("portal session close failed")
        if self.method == "desktop":
            try:
                self._desktop.unbind()
            except Exception:
                get_logger().exception("desktop shortcut removal failed")
