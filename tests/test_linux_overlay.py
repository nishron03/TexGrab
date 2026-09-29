"""Drag geometry for the Linux region overlay. No window is opened."""

from texgrab.linux.overlay import selection_box


def test_selection_box_maps_a_drag_onto_image_pixels():
    assert selection_box(10, 20, 110, 70, 200, 100, 200, 100) == (10, 20, 110, 70)


def test_selection_box_accepts_a_reversed_drag():
    assert selection_box(110, 70, 10, 20, 200, 100, 200, 100) == (10, 20, 110, 70)


def test_selection_box_rejects_a_click():
    assert selection_box(10, 10, 14, 30, 200, 100, 200, 100) is None


def test_selection_box_letterboxes_a_narrow_view():
    assert selection_box(50, 0, 150, 100, 200, 100, 100, 100) == (0, 0, 100, 100)


def test_selection_box_ignores_a_drag_in_the_margin():
    assert selection_box(0, 0, 40, 40, 300, 100, 100, 100) is None
