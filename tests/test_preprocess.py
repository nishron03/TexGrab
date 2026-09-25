from PIL import Image

from texgrab.ocr.preprocess import prepare_image


def test_rgba_flattens_onto_white():
    image = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    image.putpixel((0, 0), (10, 20, 30, 255))
    prepared = prepare_image(image)
    assert prepared.mode == "RGB"
    assert prepared.getpixel((0, 0)) == (10, 20, 30)
    assert prepared.getpixel((1, 1)) == (255, 255, 255)


def test_grayscale_becomes_rgb():
    image = Image.new("L", (4, 3), 200)
    prepared = prepare_image(image)
    assert prepared.mode == "RGB"
    assert prepared.size == (4, 3)


def test_rgb_is_copied():
    image = Image.new("RGB", (2, 2), (1, 2, 3))
    prepared = prepare_image(image)
    assert prepared is not image
    assert prepared.getpixel((0, 0)) == (1, 2, 3)
