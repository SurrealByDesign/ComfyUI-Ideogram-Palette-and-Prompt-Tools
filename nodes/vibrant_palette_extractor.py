"""IdeogramVibrantPaletteExtractor node.

Extracts a palette ranked by *vibrancy* rather than raw frequency, so a small but
striking accent color isn't buried under a dull dominant background. Inspired by
Android's Palette API / Vibrant.js: each clustered color is scored against a
target saturation + lightness (weighted with population), and the palette is
ordered by that score. A `mode` selects which target to emphasize (vibrant,
muted, and their light/dark variants).
"""

import json

import numpy as np
import torch

try:
    from ..utils.extract import clusters_from_pixels, RESIZE_DIM
    from ..utils.color_utils import rgb_to_hex, rgb_to_lab, delta_e, rgb_to_hsl
    from ..utils.preview_utils import render_swatch_strip
    from .palette_extractor import _tensor_to_pil
except ImportError:
    from utils.extract import clusters_from_pixels, RESIZE_DIM
    from utils.color_utils import rgb_to_hex, rgb_to_lab, delta_e, rgb_to_hsl
    from utils.preview_utils import render_swatch_strip
    from nodes.palette_extractor import _tensor_to_pil

# Target (saturation, lightness) per mode — the Android Palette target values.
TARGETS = {
    "vibrant": (1.0, 0.5),
    "light_vibrant": (1.0, 0.74),
    "dark_vibrant": (1.0, 0.26),
    "muted": (0.3, 0.5),
    "light_muted": (0.3, 0.74),
    "dark_muted": (0.3, 0.26),
}
MODES = list(TARGETS.keys())

# Scoring weights (Android Palette: saturation 0.24, luma 0.52, population 0.24).
W_SAT, W_LIGHT, W_POP = 0.24, 0.52, 0.24
FALLBACK_HEX = "#808080"


def _vibrancy_ordered_hex(centroids, counts, mode, min_delta_e):
    """Score each cluster against the mode's target, order by score, Delta-E dedup."""
    if len(centroids) == 0:
        return []
    target_s, target_l = TARGETS.get(mode, TARGETS["vibrant"])
    max_count = float(max(counts)) if len(counts) else 1.0

    scored = []
    for rgb, count in zip(centroids, counts):
        _, s, lightness = rgb_to_hsl(rgb)
        score = (
            W_SAT * (1.0 - abs(s - target_s))
            + W_LIGHT * (1.0 - abs(lightness - target_l))
            + W_POP * (count / max_count if max_count else 0.0)
        )
        scored.append((score, rgb))
    scored.sort(key=lambda item: -item[0])

    survivors_rgb, survivors_lab = [], []
    for _score, rgb in scored:
        lab = rgb_to_lab(rgb)
        if any(delta_e(lab, kept) < min_delta_e for kept in survivors_lab):
            continue
        survivors_rgb.append(rgb)
        survivors_lab.append(lab)
    return [rgb_to_hex(rgb) for rgb in survivors_rgb]


class IdeogramVibrantPaletteExtractor:
    """Extracts a palette ranked by vibrancy (not frequency), Android Palette-style.

    Inputs:
        image: the reference IMAGE.
        num_colors: number of clusters to consider.
        min_delta_e: minimum perceptual (LAB) distance required between kept colors.
        mode: which target to emphasize — vibrant / muted / light_* / dark_*.

    Outputs:
        palette_json: JSON array of hex strings, most-vibrant (for the mode) first.
        palette_preview: horizontal swatch strip IMAGE.
        color_count: number of colors returned after deduplication.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "num_colors": ("INT", {"default": 8, "min": 2, "max": 16}),
                "min_delta_e": ("FLOAT", {"default": 10.0, "min": 0.0, "max": 100.0, "step": 0.5}),
                "mode": (MODES, {"default": "vibrant"}),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE", "INT")
    RETURN_NAMES = ("palette_json", "palette_preview", "color_count")
    FUNCTION = "extract"
    CATEGORY = "Ideogram/Palette"

    def extract(self, image, num_colors, min_delta_e, mode="vibrant"):
        try:
            pil_image = _tensor_to_pil(image).resize((RESIZE_DIM, RESIZE_DIM))
            pixels = np.asarray(pil_image, dtype=np.float64).reshape(-1, 3)
            centroids, counts = clusters_from_pixels(pixels, num_colors)
            hex_colors = _vibrancy_ordered_hex(centroids, counts, mode, min_delta_e)
            if not hex_colors:
                hex_colors = [FALLBACK_HEX]
        except Exception:
            hex_colors = [FALLBACK_HEX]

        palette_json = json.dumps(hex_colors)
        swatch = render_swatch_strip(hex_colors)
        preview_tensor = torch.from_numpy(swatch).unsqueeze(0)

        return (palette_json, preview_tensor, len(hex_colors))
