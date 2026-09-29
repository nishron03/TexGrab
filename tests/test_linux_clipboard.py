"""Wayland clipboard round-trip. The previous text is restored."""

import subprocess

from texgrab.clipboard import change_count, read_text, write_text
from texgrab.linux.clipboard import tool_path


def _raw_write(text: str) -> None:
    exe = tool_path("wl-copy")
    assert exe
    subprocess.run([exe, "-t", "text/plain"], input=text.encode("utf-8"), check=True)


def test_round_trip_saves_and_restores_previous_text():
    previous = read_text()
    marker = r"\int_0^1 x^{2}\,dx"
    before = change_count()
    try:
        write_text(marker)
        assert read_text() == marker
        assert change_count() != before
        write_text("")
        assert read_text() == marker
    finally:
        if previous:
            write_text(previous)
        else:
            _raw_write("")
        assert read_text() == previous
