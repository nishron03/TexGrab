"""Register one global hotkey with Carbon RegisterEventHotKey.

This is the API that fires while another application is focused and does not
ask for Accessibility permission. The callback runs on the main thread and
must return immediately.
"""

from __future__ import annotations

import ctypes
from ctypes import CFUNCTYPE, POINTER, c_int32, c_uint32, c_void_p

from texgrab.config import Config
from texgrab.hotkey.keys import (
    EVENT_CLASS_KEYBOARD,
    EVENT_HOTKEY_PRESSED,
    keycode_for,
    modifier_mask,
)
from texgrab.log import get_logger

_HIToolbox = "/System/Library/Frameworks/Carbon.framework/Frameworks/HIToolbox.framework/HIToolbox"
_HANDLER = CFUNCTYPE(c_int32, c_void_p, c_void_p, c_void_p)
_library = None


class EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", c_uint32), ("eventKind", c_uint32)]


class EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", c_uint32), ("id", c_uint32)]


class HotKeyError(RuntimeError):
    pass


def _fourcc(text: str) -> int:
    return int.from_bytes(text.encode("ascii"), "big")


def _load_library():
    global _library
    if _library is not None:
        return _library
    library = ctypes.CDLL(_HIToolbox)
    library.GetApplicationEventTarget.argtypes = []
    library.GetApplicationEventTarget.restype = c_void_p
    library.InstallEventHandler.argtypes = [
        c_void_p,
        c_void_p,
        c_uint32,
        POINTER(EventTypeSpec),
        c_void_p,
        c_void_p,
    ]
    library.InstallEventHandler.restype = c_int32
    library.RegisterEventHotKey.argtypes = [
        c_uint32,
        c_uint32,
        EventHotKeyID,
        c_void_p,
        c_uint32,
        POINTER(c_void_p),
    ]
    library.RegisterEventHotKey.restype = c_int32
    library.UnregisterEventHotKey.argtypes = [c_void_p]
    library.UnregisterEventHotKey.restype = c_int32
    _library = library
    return library


class HotKeyManager:
    def __init__(self, config: Config, callback) -> None:
        self._config = config
        self._callback = callback
        self._upp = None
        self._hotkey = None
        self._installed = False

    def register(self) -> None:
        library = _load_library()
        if self._upp is None:
            def handle(_next, _event, _userdata):
                try:
                    self._callback()
                except Exception:
                    get_logger().exception("hotkey callback failed")
                return 0

            self._upp = _HANDLER(handle)
        target = library.GetApplicationEventTarget()
        if not target:
            raise HotKeyError("GetApplicationEventTarget returned NULL")
        if not self._installed:
            spec = EventTypeSpec(EVENT_CLASS_KEYBOARD, EVENT_HOTKEY_PRESSED)
            status = library.InstallEventHandler(
                target,
                ctypes.cast(self._upp, c_void_p),
                1,
                ctypes.byref(spec),
                None,
                None,
            )
            if status != 0:
                raise HotKeyError(f"InstallEventHandler failed ({status})")
            self._installed = True
        if self._hotkey is not None:
            self.unregister()
        ref = c_void_p()
        status = library.RegisterEventHotKey(
            keycode_for(self._config.shortcut_key),
            modifier_mask(
                command=self._config.shortcut_command,
                control=self._config.shortcut_control,
                shift=self._config.shortcut_shift,
                option=self._config.shortcut_option,
            ),
            EventHotKeyID(_fourcc("TxGb"), 1),
            target,
            0,
            ctypes.byref(ref),
        )
        if status != 0:
            raise HotKeyError(f"RegisterEventHotKey failed ({status})")
        self._hotkey = ref.value
        get_logger().info("shortcut registered %s", self._config.shortcut_label)

    def unregister(self) -> None:
        if not self._hotkey:
            return
        status = _load_library().UnregisterEventHotKey(self._hotkey)
        self._hotkey = None
        if status != 0:
            get_logger().error("UnregisterEventHotKey failed (%s)", status)
        else:
            get_logger().info("shortcut unregistered")
