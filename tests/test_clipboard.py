import sys

import pytest

if sys.platform != "darwin":
    pytest.skip("AppKit pasteboard tests run on macOS", allow_module_level=True)

from AppKit import NSPasteboard, NSPasteboardItem

from texgrab.clipboard import change_count, read_text, write_text


def save_pasteboard():
    pasteboard = NSPasteboard.generalPasteboard()
    saved = []
    for item in pasteboard.pasteboardItems() or []:
        entry = []
        for kind in item.types():
            data = item.dataForType_(kind)
            if data is not None:
                entry.append((str(kind), data))
        saved.append(entry)
    return saved


def restore_pasteboard(saved) -> None:
    pasteboard = NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    objects = []
    for entry in saved:
        item = NSPasteboardItem.alloc().init()
        for kind, data in entry:
            item.setData_forType_(data, kind)
        objects.append(item)
    if objects:
        pasteboard.writeObjects_(objects)


def test_write_and_restore_previous_text():
    saved = save_pasteboard()
    before = change_count()
    try:
        write_text(r"\int_0^1 x^{2}\,dx")
        assert read_text() == r"\int_0^1 x^{2}\,dx"
        assert change_count() > before
    finally:
        restore_pasteboard(saved)
