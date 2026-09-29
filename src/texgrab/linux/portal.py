"""xdg-desktop-portal Screenshot and GlobalShortcuts.

GlobalShortcuts is optional. This GNOME 46 session does not export it; the
caller falls back to a desktop shortcut plus the trigger socket. Screenshot
grabs one full frame and does not open the desktop's region tool. The first
call can show a permission dialog — allow screenshots for this process.
"""

from __future__ import annotations

import os
import secrets
import threading
from collections import deque

from texgrab.linux.capture import PortalShot
from texgrab.log import get_logger

PORTAL_NAME = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
SHORTCUT_ID = "snip"


def preferred_trigger(config) -> str:
    """XDG shortcuts-spec trigger. Super is LOGO."""
    parts: list[str] = []
    if config.shortcut_command:
        parts.append("LOGO")
    if config.shortcut_control:
        parts.append("CTRL")
    if config.shortcut_option:
        parts.append("ALT")
    if config.shortcut_shift:
        parts.append("SHIFT")
    parts.append(config.shortcut_key.lower())
    return "+".join(parts)


def screenshot_available() -> bool:
    return _interface_available("org.freedesktop.portal.Screenshot")


def global_shortcuts_available() -> bool:
    return _interface_available("org.freedesktop.portal.GlobalShortcuts")


def response_rule(path: str):
    """Match one portal Request.Response.

    The sender is omitted on purpose. The signal header carries the bus
    connection's unique name, and comparing that to
    ``org.freedesktop.portal.Desktop`` drops the message, so the snip waits
    until the timeout. The object path belongs to this call only.
    """
    from jeepney.bus_messages import MatchRule

    return MatchRule(
        type="signal",
        interface="org.freedesktop.portal.Request",
        member="Response",
        path=path,
    )


def capture_screenshot(timeout: float = 120) -> PortalShot:
    """Grab one full frame. The desktop region selector is not opened."""
    try:
        from jeepney import DBusAddress, MessageType, new_method_call
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import open_dbus_connection
        from jeepney.wrappers import DBusErrorResponse, unwrap_msg
    except ImportError as exc:
        return PortalShot(2, {}, f"jeepney is not installed: {exc}")
    try:
        conn = open_dbus_connection(bus="SESSION")
    except Exception as exc:
        return PortalShot(2, {}, f"session bus unavailable: {exc}")
    request = ""
    try:
        token = _token("shot")
        request = _request_path(conn.unique_name, token)
        options = {
            "handle_token": ("s", token),
            "interactive": ("b", False),
            "modal": ("b", False),
        }
        call = new_method_call(
            DBusAddress(PORTAL_PATH, PORTAL_NAME, "org.freedesktop.portal.Screenshot"),
            "Screenshot",
            "sa{sv}",
            ("", options),
        )
        rule = response_rule(request)
        conn.send_and_get_reply(message_bus.AddMatch(rule))
        with conn.filter(rule, bufsize=4) as queue:
            try:
                unwrap_msg(conn.send_and_get_reply(call, timeout=5))
            except DBusErrorResponse as exc:
                return PortalShot(2, {}, str(exc))
            try:
                signal = conn.recv_until_filtered(queue, timeout=timeout)
            except TimeoutError:
                _close_request(conn, request, new_method_call, DBusAddress, unwrap_msg)
                return PortalShot(2, {}, "screenshot portal timed out")
        if signal.header.message_type != MessageType.signal:
            return PortalShot(2, {}, "screenshot portal returned no response")
        response, results = signal.body
        return PortalShot(int(response), _unwrap_vardict(results), "")
    finally:
        conn.close()


def _close_request(conn, request: str, new_method_call, DBusAddress, unwrap_msg) -> None:
    if not request:
        return
    call = new_method_call(
        DBusAddress(request, PORTAL_NAME, "org.freedesktop.portal.Request"),
        "Close",
    )
    try:
        unwrap_msg(conn.send_and_get_reply(call, timeout=2))
    except Exception:
        get_logger().info("screenshot portal request already finished")


class GlobalShortcutPortal:
    """Keep one GlobalShortcuts session open and call back when it activates."""

    def __init__(self, callback) -> None:
        self._callback = callback
        self._commands: deque = deque()
        self._wake = threading.Event()
        self._replies: dict[int, tuple] = {}
        self._reply_events: dict[int, threading.Event] = {}
        self._seq = 0
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._running = False

    def bind(self, config) -> bool:
        self._ensure()
        if not self._started.wait(5):
            return False
        return bool(self._request("bind", config))

    def close(self) -> None:
        if self._thread is None:
            return
        try:
            self._request("close", None)
        except Exception:
            get_logger().exception("portal shortcut close failed")
        self._running = False
        self._wake.set()
        self._thread.join(timeout=2)
        self._thread = None

    def _ensure(self) -> None:
        if self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._main, name="texgrab-portal", daemon=True)
        self._thread.start()

    def _request(self, kind: str, payload):
        with self._lock:
            self._seq += 1
            token = self._seq
            event = threading.Event()
            self._reply_events[token] = event
            self._commands.append((token, kind, payload))
        self._wake.set()
        if not event.wait(600):
            return False
        with self._lock:
            return self._replies.pop(token, False)

    def _reply(self, token: int, value) -> None:
        with self._lock:
            self._replies[token] = value
            event = self._reply_events.pop(token, None)
        if event is not None:
            event.set()

    def _main(self) -> None:
        try:
            from jeepney import DBusAddress, MessageType, new_method_call
            from jeepney.bus_messages import MatchRule, message_bus
            from jeepney.io.blocking import open_dbus_connection
            from jeepney.wrappers import DBusErrorResponse, unwrap_msg
        except ImportError:
            get_logger().exception("jeepney is not installed")
            self._started.set()
            self._fail_pending(False)
            return
        try:
            conn = open_dbus_connection(bus="SESSION")
        except Exception:
            get_logger().exception("session bus unavailable")
            self._started.set()
            self._fail_pending(False)
            return
        activated = MatchRule(
            type="signal",
            sender=PORTAL_NAME,
            interface="org.freedesktop.portal.GlobalShortcuts",
            member="Activated",
        )
        session = None
        try:
            conn.send_and_get_reply(message_bus.AddMatch(activated))
            with conn.filter(activated, bufsize=20) as activated_q:
                self._started.set()
                while self._running:
                    self._drain(conn, activated_q, new_method_call, DBusAddress, unwrap_msg, DBusErrorResponse, message_bus, MatchRule)
                    session = getattr(self, "_session", session)
                    if not self._commands and not self._wake.is_set():
                        try:
                            conn.recv_messages(timeout=0.2)
                        except TimeoutError:
                            continue
                        self._emit_activated(activated_q)
                    else:
                        self._wake.wait(0.2)
                        self._wake.clear()
        finally:
            if session or getattr(self, "_session", None):
                _close_session(conn, getattr(self, "_session", None), new_method_call, DBusAddress, unwrap_msg)
            conn.close()
            self._fail_pending(False)

    def _drain(self, conn, activated_q, new_method_call, DBusAddress, unwrap_msg, DBusErrorResponse, message_bus, MatchRule) -> None:
        while True:
            with self._lock:
                if not self._commands:
                    return
                token, kind, payload = self._commands.popleft()
            try:
                if kind == "bind":
                    # BindShortcuts is once per session. Close the old one first.
                    old = getattr(self, "_session", None)
                    if old:
                        _close_session(conn, old, new_method_call, DBusAddress, unwrap_msg)
                        self._session = None
                    ok, session = _bind_session(
                        conn, payload, new_method_call, DBusAddress, unwrap_msg, DBusErrorResponse, message_bus, MatchRule
                    )
                    self._session = session
                    self._reply(token, ok)
                elif kind == "close":
                    _close_session(conn, getattr(self, "_session", None), new_method_call, DBusAddress, unwrap_msg)
                    self._session = None
                    self._reply(token, True)
                else:
                    self._reply(token, False)
            except Exception:
                get_logger().exception("portal shortcut command failed")
                self._reply(token, False)
            self._emit_activated(activated_q)

    def _emit_activated(self, queue) -> None:
        while queue:
            message = queue.popleft()
            try:
                shortcut_id = message.body[1]
            except (IndexError, TypeError):
                shortcut_id = ""
            if shortcut_id != SHORTCUT_ID:
                continue
            try:
                self._callback()
            except Exception:
                get_logger().exception("shortcut callback failed")

    def _fail_pending(self, value) -> None:
        with self._lock:
            pending = list(self._commands)
            self._commands.clear()
            tokens = list(self._reply_events)
        for token, _kind, _payload in pending:
            self._reply(token, value)
        for token in tokens:
            self._reply(token, value)


def _interface_available(interface: str) -> bool:
    try:
        from jeepney import DBusAddress, new_method_call
        from jeepney.io.blocking import open_dbus_connection
        from jeepney.wrappers import DBusErrorResponse, unwrap_msg
    except ImportError:
        return False
    try:
        conn = open_dbus_connection(bus="SESSION")
    except Exception:
        return False
    try:
        call = new_method_call(
            DBusAddress(PORTAL_PATH, PORTAL_NAME, "org.freedesktop.DBus.Properties"),
            "Get",
            "ss",
            (interface, "version"),
        )
        try:
            unwrap_msg(conn.send_and_get_reply(call, timeout=2))
        except DBusErrorResponse:
            return False
        return True
    except Exception:
        get_logger().exception("portal probe failed for %s", interface)
        return False
    finally:
        conn.close()


def _token(prefix: str) -> str:
    return prefix + secrets.token_hex(8)


def _sender_token(unique_name: str) -> str:
    return unique_name.lstrip(":").replace(".", "_")


def _request_path(unique_name: str, token: str) -> str:
    return f"/org/freedesktop/portal/desktop/request/{_sender_token(unique_name)}/{token}"


def _session_path(unique_name: str, token: str) -> str:
    return f"/org/freedesktop/portal/desktop/session/{_sender_token(unique_name)}/{token}"


def _unwrap_vardict(raw) -> dict:
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
            out[key] = value[1]
        else:
            out[key] = value
    return out


def _call_request(conn, method, signature, body, token, new_method_call, DBusAddress, unwrap_msg, DBusErrorResponse, message_bus, MatchRule):
    request = _request_path(conn.unique_name, token)
    rule = MatchRule(
        type="signal",
        sender=PORTAL_NAME,
        interface="org.freedesktop.portal.Request",
        member="Response",
        path=request,
    )
    conn.send_and_get_reply(message_bus.AddMatch(rule))
    call = new_method_call(
        DBusAddress(PORTAL_PATH, PORTAL_NAME, "org.freedesktop.portal.GlobalShortcuts"),
        method,
        signature,
        body,
    )
    with conn.filter(rule, bufsize=4) as queue:
        try:
            unwrap_msg(conn.send_and_get_reply(call, timeout=30))
        except DBusErrorResponse as exc:
            get_logger().error("portal %s failed: %s", method, exc)
            return None
        try:
            signal = conn.recv_until_filtered(queue, timeout=600)
        except TimeoutError:
            get_logger().error("portal %s timed out", method)
            return None
    response, results = signal.body
    return int(response), _unwrap_vardict(results)


def _bind_session(conn, config, new_method_call, DBusAddress, unwrap_msg, DBusErrorResponse, message_bus, MatchRule):
    if not _interface_available("org.freedesktop.portal.GlobalShortcuts"):
        return False, None
    handle = _token("bind")
    session_token = _token("sess")
    created = _call_request(
        conn,
        "CreateSession",
        "a{sv}",
        (
            {
                "handle_token": ("s", handle),
                "session_handle_token": ("s", session_token),
            },
        ),
        handle,
        new_method_call,
        DBusAddress,
        unwrap_msg,
        DBusErrorResponse,
        message_bus,
        MatchRule,
    )
    if not created or created[0] != 0:
        return False, None
    session = created[1].get("session_handle") or _session_path(conn.unique_name, session_token)
    bind_token = _token("shortcuts")
    shortcuts = [
        (
            SHORTCUT_ID,
            {
                "description": ("s", "Snip an equation and copy its LaTeX"),
                "preferred_trigger": ("s", preferred_trigger(config)),
            },
        )
    ]
    bound = _call_request(
        conn,
        "BindShortcuts",
        "oa(sa{sv})sa{sv}",
        (session, shortcuts, "", {"handle_token": ("s", bind_token)}),
        bind_token,
        new_method_call,
        DBusAddress,
        unwrap_msg,
        DBusErrorResponse,
        message_bus,
        MatchRule,
    )
    if not bound or bound[0] != 0:
        _close_session(conn, session, new_method_call, DBusAddress, unwrap_msg)
        return False, None
    get_logger().info(
        "portal shortcuts bound trigger=%s; allow the desktop dialog if it is still open",
        preferred_trigger(config),
    )
    return True, session


def _close_session(conn, session, new_method_call, DBusAddress, unwrap_msg) -> None:
    if not session:
        return
    try:
        from jeepney.wrappers import DBusErrorResponse
    except ImportError:
        return
    call = new_method_call(
        DBusAddress(session, PORTAL_NAME, "org.freedesktop.portal.Session"),
        "Close",
    )
    try:
        unwrap_msg(conn.send_and_get_reply(call, timeout=5))
    except (DBusErrorResponse, TimeoutError, OSError):
        get_logger().info("portal session close returned no success")
