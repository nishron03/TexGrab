"""Drag a rectangle on a frozen frame, the way macOS `screencapture -i` does.

Mouse release crops the frame. Escape cancels. Nothing is copied here.
The desktop's own screenshot tool is not used as the selector.
"""

from __future__ import annotations

import threading

from PIL import Image

from texgrab.capture.region import CaptureError
from texgrab.linux.recorder import prepare_typelib_path
from texgrab.log import get_logger

MIN_SELECTION = 8
_HINT = "Drag around the equation. Release to copy LaTeX. Esc cancels."


def ensure_gtk() -> bool:
    prepare_typelib_path()
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gtk  # noqa: F401
    except Exception:
        get_logger().exception("GTK is unavailable")
        return False
    return True


def view_transform(view_w: float, view_h: float, image_w: float, image_h: float):
    """Uniform scale that fits the image inside the view, plus the origin."""
    if view_w <= 0 or view_h <= 0 or image_w <= 0 or image_h <= 0:
        return 0.0, 0.0, 0.0
    scale = min(view_w / image_w, view_h / image_h)
    drawn_w = image_w * scale
    drawn_h = image_h * scale
    return scale, (view_w - drawn_w) / 2, (view_h - drawn_h) / 2


def _map_point(x: float, y: float, view_w: float, view_h: float, image_w: float, image_h: float):
    scale, origin_x, origin_y = view_transform(view_w, view_h, image_w, image_h)
    if scale <= 0:
        return None
    return (
        min(max((x - origin_x) / scale, 0), image_w),
        min(max((y - origin_y) / scale, 0), image_h),
    )


def selection_box(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    view_w: float,
    view_h: float,
    image_w: float,
    image_h: float,
    min_edge: int = MIN_SELECTION,
):
    """Image crop box for a drag, or None when the drag is too small to keep."""
    start = _map_point(x0, y0, view_w, view_h, image_w, image_h)
    end = _map_point(x1, y1, view_w, view_h, image_w, image_h)
    if start is None or end is None:
        return None
    left = int(round(min(start[0], end[0])))
    right = int(round(max(start[0], end[0])))
    top = int(round(min(start[1], end[1])))
    bottom = int(round(max(start[1], end[1])))
    left = min(max(left, 0), int(image_w))
    right = min(max(right, 0), int(image_w))
    top = min(max(top, 0), int(image_h))
    bottom = min(max(bottom, 0), int(image_h))
    if right - left < min_edge or bottom - top < min_edge:
        return None
    return (left, top, right, bottom)


def select_region(image: Image.Image, *, drive=None) -> Image.Image | None:
    """Show `image` fullscreen and block until a drag or a cancel.

    `drive`, when set, is called on the GTK thread with a small pointer
    stand-in. The running app leaves it unset.
    """
    if not ensure_gtk():
        raise CaptureError("GTK is unavailable")
    from gi.repository import GLib

    holder: dict = {"image": None, "error": None}
    done = threading.Event()

    def finish(chosen, error=None) -> None:
        holder["image"] = chosen
        holder["error"] = error
        done.set()

    context = GLib.MainContext.default()
    if context.is_owner():
        loop = GLib.MainLoop()

        def finish_here(chosen, error=None) -> None:
            finish(chosen, error)
            if loop.is_running():
                loop.quit()

        _open(image, finish_here, drive, GLib)
        loop.run()
    else:
        def present() -> bool:
            try:
                _open(image, finish, drive, GLib)
            except Exception as exc:
                finish(None, exc)
            return False

        GLib.idle_add(present)
        done.wait()
    if holder["error"] is not None:
        raise CaptureError(str(holder["error"])[:500])
    return holder["image"]


def _open(image: Image.Image, finish, drive, GLib) -> None:
    import math

    import gi

    gi.require_version("GdkPixbuf", "2.0")
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Gdk, GdkPixbuf, Gtk, Pango, PangoCairo

    frame = image.convert("RGBA")
    width, height = frame.size
    pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(frame.tobytes()),
        GdkPixbuf.Colorspace.RGB,
        True,
        8,
        width,
        height,
        width * 4,
    )
    window = Gtk.Window(title="TexGrab")
    window.set_decorated(False)
    window.set_app_paintable(True)
    window.set_keep_above(True)
    window.set_skip_taskbar_hint(True)
    window.set_skip_pager_hint(True)
    window.set_accept_focus(True)
    window.set_can_focus(True)
    drawing = Gtk.DrawingArea()
    drawing.set_can_focus(True)
    drawing.add_events(
        Gdk.EventMask.BUTTON_PRESS_MASK
        | Gdk.EventMask.BUTTON_RELEASE_MASK
        | Gdk.EventMask.POINTER_MOTION_MASK
        | Gdk.EventMask.BUTTON_MOTION_MASK
    )
    window.add(drawing)
    state = {
        "done": False,
        "dragging": False,
        "x0": 0.0,
        "y0": 0.0,
        "x1": 0.0,
        "y1": 0.0,
    }

    def allocation():
        rect = drawing.get_allocation()
        return rect.width, rect.height

    def close_with(chosen) -> None:
        if state["done"]:
            return
        state["done"] = True
        _release_seat(window, Gdk)
        window.destroy()
        finish(chosen)

    def current_box(min_edge=MIN_SELECTION):
        view_w, view_h = allocation()
        return selection_box(
            state["x0"],
            state["y0"],
            state["x1"],
            state["y1"],
            view_w,
            view_h,
            width,
            height,
            min_edge=min_edge,
        )

    def on_press(x, y, button) -> None:
        if button == 3:
            close_with(None)
            return
        if button != 1:
            return
        state["dragging"] = True
        state["x0"] = state["x1"] = x
        state["y0"] = state["y1"] = y
        drawing.queue_draw()

    def on_move(x, y) -> None:
        if not state["dragging"]:
            return
        state["x1"] = x
        state["y1"] = y
        drawing.queue_draw()

    def on_release(x, y, button) -> None:
        if button != 1 or not state["dragging"]:
            return
        state["dragging"] = False
        state["x1"] = x
        state["y1"] = y
        box = current_box()
        if box is None:
            close_with(None)
            return
        close_with(frame.crop(box).convert("RGB"))

    def on_escape() -> None:
        close_with(None)

    def on_button(_widget, event) -> bool:
        on_press(event.x, event.y, int(event.button))
        return True

    def on_release_event(_widget, event) -> bool:
        on_release(event.x, event.y, int(event.button))
        return True

    def on_motion(_widget, event) -> bool:
        on_move(event.x, event.y)
        return True

    def on_key(_widget, event) -> bool:
        name = Gdk.keyval_name(event.keyval) or ""
        if event.keyval == Gdk.KEY_Escape or name == "Escape":
            on_escape()
            return True
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) or name in ("Return", "KP_Enter"):
            return True
        return True

    def on_draw(_widget, cr) -> bool:
        view_w, view_h = allocation()
        scale, origin_x, origin_y = view_transform(view_w, view_h, width, height)
        cr.set_source_rgb(0, 0, 0)
        cr.paint()
        if scale > 0:
            cr.save()
            cr.translate(origin_x, origin_y)
            cr.scale(scale, scale)
            Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
            cr.paint()
            cr.restore()
            cr.set_source_rgba(0, 0, 0, 0.42)
            cr.rectangle(origin_x, origin_y, width * scale, height * scale)
            cr.fill()
        if state["dragging"]:
            box = current_box(min_edge=1)
            if box is not None and scale > 0:
                left, top, right, bottom = box
                vx = origin_x + left * scale
                vy = origin_y + top * scale
                vw = (right - left) * scale
                vh = (bottom - top) * scale
                cr.save()
                cr.rectangle(vx, vy, vw, vh)
                cr.clip()
                cr.translate(origin_x, origin_y)
                cr.scale(scale, scale)
                Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
                cr.paint()
                cr.restore()
                cr.set_source_rgba(0.45, 0.78, 1, 1)
                cr.set_line_width(2)
                cr.rectangle(vx + 1, vy + 1, max(vw - 2, 1), max(vh - 2, 1))
                cr.stroke()
                _paint_size(cr, Pango, PangoCairo, vx, vy, vw, vh, view_w, view_h, right - left, bottom - top)
        _paint_hint(cr, Pango, PangoCairo, math, view_w)
        return False

    drawing.connect("button-press-event", on_button)
    drawing.connect("button-release-event", on_release_event)
    drawing.connect("motion-notify-event", on_motion)
    window.connect("key-press-event", on_key)
    window.connect("delete-event", lambda *_args: close_with(None) or True)
    drawing.connect("draw", on_draw)
    window.connect("map", lambda *_args: _grab_seat(window, drawing, Gdk))
    window.show_all()
    window.fullscreen()
    window.present()
    drawing.grab_focus()
    if drive is not None:
        pointer = _Pointer(drawing, on_press, on_move, on_release, on_escape)
        GLib.idle_add(lambda: drive(pointer) or False)


class _Pointer:
    def __init__(self, widget, press, move, release, escape) -> None:
        self._widget = widget
        self._press = press
        self._move = move
        self._release = release
        self._escape = escape

    def allocation(self):
        rect = self._widget.get_allocation()
        return rect.width, rect.height

    def press(self, x, y) -> None:
        self._press(x, y, 1)

    def move(self, x, y) -> None:
        self._move(x, y)

    def release(self, x, y) -> None:
        self._release(x, y, 1)

    def escape(self) -> None:
        self._escape()


def _grab_seat(window, drawing, Gdk) -> bool:
    gdk_window = window.get_window()
    if gdk_window is None:
        return False
    display = window.get_display()
    seat = display.get_default_seat()
    cursor = Gdk.Cursor.new_from_name(display, "crosshair")
    try:
        gdk_window.set_cursor(cursor)
    except Exception:
        get_logger().info("overlay cursor was not set")
    capabilities = getattr(Gdk.SeatCapabilities, "ALL", None)
    if capabilities is None:
        return False
    try:
        status = seat.grab(gdk_window, capabilities, True, cursor, None, None, None)
    except Exception:
        get_logger().info("overlay seat grab failed")
        return False
    success = getattr(Gdk.GrabStatus, "SUCCESS", 0)
    if int(status) != int(success):
        get_logger().info("overlay seat grab status=%s", int(status))
    drawing.grab_focus()
    return False


def _release_seat(window, Gdk) -> None:
    try:
        display = window.get_display()
        display.get_default_seat().ungrab()
    except Exception:
        get_logger().info("overlay seat ungrab skipped")


def _rounded(cr, math, x, y, w, h, radius) -> None:
    r = min(radius, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _paint_hint(cr, Pango, PangoCairo, math, view_w) -> None:
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription("Sans 13"))
    layout.set_text(_HINT, -1)
    text_w, text_h = layout.get_pixel_size()
    pad_x, pad_y = 16, 8
    box_w = text_w + pad_x * 2
    box_h = text_h + pad_y * 2
    x = max((view_w - box_w) / 2, 8)
    y = 24
    cr.set_source_rgba(0.07, 0.08, 0.10, 0.90)
    _rounded(cr, math, x, y, box_w, box_h, 8)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.96)
    cr.move_to(x + pad_x, y + pad_y)
    PangoCairo.show_layout(cr, layout)


def _paint_size(cr, Pango, PangoCairo, vx, vy, vw, vh, view_w, view_h, pixels_w, pixels_h) -> None:
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription("Sans 12"))
    layout.set_text(f"{pixels_w} × {pixels_h}", -1)
    text_w, text_h = layout.get_pixel_size()
    pad = 6
    box_w = text_w + pad * 2
    box_h = text_h + pad * 2
    x = vx + vw - box_w
    y = vy + vh + 6
    if y + box_h > view_h - 4:
        y = vy - box_h - 6
    x = min(max(x, 4), max(view_w - box_w - 4, 4))
    y = min(max(y, 4), max(view_h - box_h - 4, 4))
    cr.set_source_rgba(0.07, 0.08, 0.10, 0.90)
    cr.rectangle(x, y, box_w, box_h)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.96)
    cr.move_to(x + pad, y + pad)
    PangoCairo.show_layout(cr, layout)
