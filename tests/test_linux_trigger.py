"""The trigger socket accepts one snip line and refuses a second listener."""

import time

import pytest

from texgrab.linux.trigger import AlreadyRunning, TriggerServer, send_snip, socket_path


def test_snip_round_trip_and_stale_socket(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert not send_snip()
    seen = []
    server = TriggerServer(lambda: seen.append("snip"))
    server.start()
    try:
        assert socket_path().stat().st_mode & 0o777 == 0o600
        assert send_snip()
        for _ in range(50):
            if seen:
                break
            time.sleep(0.02)
        assert seen == ["snip"]
        with pytest.raises(AlreadyRunning):
            TriggerServer(lambda: None).start()
    finally:
        server.close()
    assert not socket_path().exists()
    assert not send_snip()
