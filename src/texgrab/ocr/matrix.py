"""Turn a fenced grid into a LaTeX matrix.

pix2tex reads one line. Its input is capped at about 192 pixels tall, so a
matrix is squashed and the row breaks disappear. A parenthesis or bracket on
both sides, with two or more stacked rows inside, is read cell by cell instead.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class MatrixLayout:
    cells: list[list[Image.Image]]
    environment: str


def fit_matrix(image: Image.Image, rows: int) -> Image.Image:
    """Scale a grid so pix2tex can see every row without its single-line resizer.

    The checkpoint only accepts about 192 pixels of height. Around 40 pixels per
    row is the range that kept a 2 by 2 matrix intact; taller copies invented
    extra rows, and the default resizer flattened them.
    """
    target_height = min(160, max(64, 40 * rows))
    scale = target_height / image.height
    if image.width * scale > 640:
        scale = 640 / image.width
    size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    if size == image.size:
        return image
    return image.resize(size, Image.Resampling.LANCZOS)


def detect_matrix(image: Image.Image) -> MatrixLayout | None:
    mask = np.asarray(image.convert("L")) < 200
    if mask.ndim != 2 or int(mask.sum()) < 8:
        return None
    cropped, mask = _trim(image, mask)
    height, width = mask.shape
    if height < 24 or width < 24:
        return None

    # Fences run the full height, so row gaps only show up once they are removed.
    columns = _group(mask.any(axis=0), min_gap=max(2, int(width * 0.015)))
    if len(columns) < 3:
        return None
    if not _is_fence(mask, columns[0], height, width):
        return None
    if not _is_fence(mask, columns[-1], height, width):
        return None
    left_fence, right_fence = columns[0], columns[-1]
    interior = [
        (left, right)
        for left, right in columns[1:-1]
        if left >= left_fence[1] and right <= right_fence[0]
    ]
    if not interior:
        return None

    interior_mask = mask.copy()
    interior_mask[:, : left_fence[1]] = False
    interior_mask[:, right_fence[0] :] = False
    raw_rows = _group(interior_mask.any(axis=1), min_gap=1)
    interior_width = right_fence[0] - left_fence[1]
    rules = [
        band
        for band in raw_rows
        if _is_horizontal_rule(interior_mask, band, left_fence[1], right_fence[0])
    ]
    rule_set = set(rules)
    content_rows = _merge_diacritics([band for band in raw_rows if band not in rule_set])
    if len(content_rows) < 2:
        return None
    if len(interior) == 1 and rules:
        # A bar between two rows inside fences is a fraction, not a column vector.
        return None
    if interior_width < 8:
        return None

    cells: list[list[Image.Image]] = []
    for top, bottom in content_rows:
        row_cells = []
        for left, right in interior:
            row_cells.append(_pad(cropped.crop((left, top, right, bottom))))
        cells.append(row_cells)

    environment = _environment(
        cropped.crop((left_fence[0], 0, left_fence[1], height)),
        cropped.crop((right_fence[0], 0, right_fence[1], height)),
    )
    return MatrixLayout(cells=cells, environment=environment)


def _trim(image: Image.Image, mask: np.ndarray) -> tuple[Image.Image, np.ndarray]:
    ys = np.flatnonzero(mask.any(axis=1))
    xs = np.flatnonzero(mask.any(axis=0))
    top, bottom = int(ys[0]), int(ys[-1]) + 1
    left, right = int(xs[0]), int(xs[-1]) + 1
    rgb = image.convert("RGB")
    return rgb.crop((left, top, right, bottom)), mask[top:bottom, left:right]


def _group(flags: np.ndarray, min_gap: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start = None
    for index, flag in enumerate(flags.tolist()):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(flags)))
    if not runs:
        return []
    merged = [runs[0]]
    for run_start, run_end in runs[1:]:
        prev_start, prev_end = merged[-1]
        if run_start - prev_end <= min_gap:
            merged[-1] = (prev_start, run_end)
        else:
            merged.append((run_start, run_end))
    return merged


def _merge_diacritics(runs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Join a dot to the letter under it. Do not join two rows of similar height."""
    if not runs:
        return []
    merged = [runs[0]]
    for start, end in runs[1:]:
        prev_start, prev_end = merged[-1]
        gap = start - prev_end
        prev_height = prev_end - prev_start
        height = end - start
        small, large = sorted((prev_height, height))
        if small < 0.45 * large and gap <= large:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def _is_horizontal_rule(
    mask: np.ndarray, band: tuple[int, int], x0: int, x1: int
) -> bool:
    start, end = band
    if end - start > 4:
        return False
    span = mask[start:end, x0:x1].any(axis=0)
    return bool(span.sum() >= 0.55 * (x1 - x0))


def _is_fence(mask: np.ndarray, band: tuple[int, int], height: int, width: int) -> bool:
    left, right = band
    if right - left > max(36, int(width * 0.22)):
        return False
    ys = np.flatnonzero(mask[:, left:right].any(axis=1))
    if len(ys) == 0:
        return False
    return int(ys[-1] - ys[0]) >= 0.6 * height


def _environment(left: Image.Image, right: Image.Image) -> str:
    kinds = {_classify_fence(left, "left"), _classify_fence(right, "right")}
    if kinds == {"bar"}:
        return "vmatrix"
    if "paren" in kinds:
        return "pmatrix"
    if "bracket" in kinds:
        return "bmatrix"
    return "pmatrix"


def _classify_fence(crop: Image.Image, side: str) -> str:
    mask = np.asarray(crop.convert("L")) < 200
    height, width = mask.shape
    if height < 8 or width < 1 or not mask.any():
        return "bar"

    def edge(y0: int, y1: int) -> int | None:
        """Outer edge: left side of a left fence, right side of a right fence."""
        region = mask[y0:y1]
        if not region.any():
            return None
        xs = np.flatnonzero(region.any(axis=0))
        if side == "left":
            return int(xs[0])
        return int(xs[-1])

    def span(y0: int, y1: int) -> int:
        region = mask[y0:y1]
        if not region.any():
            return 0
        xs = np.flatnonzero(region.any(axis=0))
        return int(xs[-1] - xs[0] + 1)

    top = edge(0, max(1, height // 5))
    mid = edge(2 * height // 5, 3 * height // 5)
    bot = edge(4 * height // 5, height)
    top_span = span(0, max(1, height // 6))
    mid_span = span(height // 3, max(height // 3 + 1, 2 * height // 3))
    bot_span = span(5 * height // 6, height)
    if top is None or mid is None or bot is None:
        return "bar"
    if side == "left":
        bulges = mid < top - 1 and mid < bot - 1
    else:
        bulges = mid > top + 1 and mid > bot + 1
    serifs = top_span > mid_span + 1 and bot_span > mid_span + 1
    if bulges:
        return "paren"
    if serifs:
        return "bracket"
    if mid_span <= 3 and top_span <= mid_span + 1:
        return "bar"
    return "bracket"


def _pad(image: Image.Image, margin: int = 16) -> Image.Image:
    canvas = Image.new("RGB", (image.width + 2 * margin, image.height + 2 * margin), (255, 255, 255))
    canvas.paste(image.convert("RGB"), (margin, margin))
    return canvas
