"""A private socket so `texgrab --trigger` can ask the running instance to snip."""

from __future__ import annotations

import os
import socket
import threading
from pathlib import Path

from texgrab.log import get_logger


class AlreadyRunning(RuntimeError):
    pass


def socket_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if not runtime:
        runtime = f"/run/user/{os.getuid()}"
    return Path(runtime) / "texgrab.sock"


def send_snip(path: Path | None = None, timeout: float = 0.5) -> bool:
    target = path or socket_path()
    if not target.exists():
        return False
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(target))
        sock.sendall(b"snip\n")
    except OSError:
        return False
    finally:
        sock.close()
    return True


class TriggerServer:
    def __init__(self, on_snip) -> None:
        self._on_snip = on_snip
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        path = socket_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if send_snip(path):
                raise AlreadyRunning(str(path))
            path.unlink()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(path))
        os.chmod(path, 0o600)
        sock.listen(8)
        sock.settimeout(0.5)
        self._sock = sock
        self._running = True
        self._thread = threading.Thread(target=self._serve, name="texgrab-socket", daemon=True)
        self._thread.start()
        get_logger().info("trigger socket %s", path)

    def close(self) -> None:
        self._running = False
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        path = socket_path()
        if path.exists():
            try:
                path.unlink()
            except OSError:
                get_logger().exception("could not remove trigger socket")
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None

    def _serve(self) -> None:
        while self._running and self._sock is not None:
            try:
                conn, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                data = b""
                conn.settimeout(1)
                while b"\n" not in data and len(data) < 64:
                    chunk = conn.recv(64)
                    if not chunk:
                        break
                    data += chunk
                if data.strip() == b"snip":
                    try:
                        self._on_snip()
                    except Exception:
                        get_logger().exception("trigger snip failed")
            finally:
                conn.close()
