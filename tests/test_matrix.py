from PIL import Image, ImageDraw

from texgrab.ocr.matrix import detect_matrix, fit_matrix
from texgrab.ocr.pix2tex_engine import sample_equation_path
from texgrab.ocr.preprocess import prepare_image


def _canvas(width, height):
    image = Image.new("RGB", (width, height), "white")
    return image, ImageDraw.Draw(image)


def _cell(draw, box):
    draw.rectangle(box, fill="black")


def _brackets(draw, width, height, inset=8, thick=4):
    draw.rectangle((inset, 8, inset + thick, height - 8), fill="black")
    draw.rectangle((inset, 8, inset + 14, 8 + thick), fill="black")
    draw.rectangle((inset, height - 8 - thick, inset + 14, height - 8), fill="black")
    right = width - inset - thick
    draw.rectangle((right, 8, right + thick, height - 8), fill="black")
    draw.rectangle((right - 10, 8, right + thick, 8 + thick), fill="black")
    draw.rectangle((right - 10, height - 8 - thick, right + thick, height - 8), fill="black")


def _parens(draw, width, height):
    draw.arc((6, 8, 36, height - 8), start=90, end=270, fill="black", width=4)
    draw.arc((width - 36, 8, width - 6, height - 8), start=270, end=90, fill="black", width=4)


def test_bracket_matrix_splits_into_cells():
    image, draw = _canvas(220, 120)
    _brackets(draw, 220, 120)
    _cell(draw, (50, 24, 80, 44))
    _cell(draw, (130, 24, 170, 44))
    _cell(draw, (50, 72, 80, 96))
    _cell(draw, (130, 72, 160, 96))
    layout = detect_matrix(image)
    assert layout is not None
    assert layout.environment == "bmatrix"
    assert len(layout.cells) == 2
    assert [len(row) for row in layout.cells] == [2, 2]


def test_paren_matrix_uses_pmatrix():
    image, draw = _canvas(220, 130)
    _parens(draw, 220, 130)
    _cell(draw, (55, 28, 85, 48))
    _cell(draw, (140, 28, 175, 48))
    _cell(draw, (55, 82, 85, 104))
    _cell(draw, (140, 82, 170, 104))
    layout = detect_matrix(image)
    assert layout is not None
    assert layout.environment == "pmatrix"
    assert len(layout.cells) == 2
    assert len(layout.cells[0]) == 2


def test_column_vector_is_one_column():
    image, draw = _canvas(80, 140)
    _brackets(draw, 80, 140, inset=6)
    _cell(draw, (32, 24, 52, 44))
    _cell(draw, (32, 90, 55, 112))
    layout = detect_matrix(image)
    assert layout is not None
    assert len(layout.cells) == 2
    assert [len(row) for row in layout.cells] == [1, 1]


def test_parenthesized_fraction_is_not_a_matrix():
    image, draw = _canvas(120, 140)
    _parens(draw, 120, 140)
    _cell(draw, (48, 28, 78, 48))
    draw.rectangle((40, 66, 90, 69), fill="black")
    _cell(draw, (48, 88, 78, 110))
    assert detect_matrix(image) is None


def test_unfenced_stack_is_not_a_matrix():
    image, draw = _canvas(180, 100)
    _cell(draw, (20, 15, 70, 35))
    _cell(draw, (110, 15, 160, 35))
    _cell(draw, (20, 65, 70, 85))
    _cell(draw, (110, 65, 160, 85))
    assert detect_matrix(image) is None


def test_single_line_sample_is_not_a_matrix():
    image = prepare_image(Image.open(sample_equation_path()))
    assert detect_matrix(image) is None


def test_fit_matrix_scales_two_rows_near_eighty_pixels():
    image = Image.new("RGB", (400, 300), "white")
    fitted = fit_matrix(image, rows=2)
    assert fitted.size == (106, 80)
