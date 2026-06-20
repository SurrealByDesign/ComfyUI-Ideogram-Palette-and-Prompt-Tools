"""Rendering helpers for palette swatch previews.

Output arrays match ComfyUI's IMAGE convention: float32, 0-1 range, shape (H, W, C).
Node code is responsible for adding the batch dimension via torch before returning.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    from .color_utils import hex_to_rgb
except ImportError:
    from color_utils import hex_to_rgb

SWATCH_HEIGHT = 100
SWATCH_WIDTH = 100
LABEL_BAND_HEIGHT = 24
LABEL_BG = (24, 24, 24)


def _load_font(size: int):
    """Load a readable TrueType font, falling back gracefully across environments."""
    for name in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    try:
        # Pillow >= 10 supports a scalable default font via the size kwarg.
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_swatch_strip(hex_colors, swatch_size: int = SWATCH_WIDTH, show_labels: bool = True) -> np.ndarray:
    """Render a horizontal strip of color swatches, each labeled with its hex code
    in a dedicated band below the color block.

    Args:
        hex_colors: list of hex color strings, e.g. ["#FF5733", "#C70039"].
        swatch_size: width (and color-block height) in pixels of each swatch.
        show_labels: if True, draw a label band under each swatch with its exact
            hex code (the same value Ideogram consumes).

    Returns:
        numpy float32 array of shape (H, swatch_size * len(hex_colors), 3),
        values in 0-1 range, where H is swatch_size (+ label band if labels shown).
        Falls back to a single gray swatch if hex_colors is empty or invalid.
    """
    valid = []
    for h in hex_colors or []:
        try:
            valid.append((h, hex_to_rgb(h)))
        except (ValueError, TypeError):
            continue

    if not valid:
        valid = [("#808080", (128, 128, 128))]

    width = swatch_size * len(valid)
    band = LABEL_BAND_HEIGHT if show_labels else 0
    total_height = swatch_size + band

    img = Image.new("RGB", (width, total_height), LABEL_BG)
    draw = ImageDraw.Draw(img)
    hex_font = _load_font(15)

    for i, (hex_str, rgb) in enumerate(valid):
        x0 = i * swatch_size
        draw.rectangle([x0, 0, x0 + swatch_size - 1, swatch_size - 1], fill=rgb)

        if show_labels:
            draw.text((x0 + 6, swatch_size + 5), hex_str.upper(), fill=(235, 235, 235), font=hex_font)

    arr = np.asarray(img, dtype=np.float32) / 255.0
    return arr
