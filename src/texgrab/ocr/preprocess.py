"""Make a screen capture something pix2tex can consume.

pix2tex does its own resize and padding. This only flattens transparency onto
white and converts to RGB so a selection that includes a translucent window
does not become black.
"""

from __future__ import annotations

from PIL import Image


def prepare_image(image: Image.Image) -> Image.Image:
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        return background
    if image.mode == "RGB":
        return image.copy()
    return image.convert("RGB")
