"""Tests for IdeogramVibrantPaletteExtractor: vibrancy-based ranking vs the base
frequency-based extractor, mode behavior, and graceful fallback."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from nodes.vibrant_palette_extractor import IdeogramVibrantPaletteExtractor
from nodes.palette_extractor import IdeogramPaletteExtractor
from utils.color_utils import rgb_to_hsl, hex_to_rgb

H = W = 64


def _node():
    return IdeogramVibrantPaletteExtractor()


def _light_gray_bg_with_red_patch():
    """Mostly light gray (dominant by frequency) with a small vivid red patch."""
    img = np.full((H, W, 3), 200 / 255.0, dtype=np.float32)  # light gray background
    img[24:40, 24:40, :] = 0.0
    img[24:40, 24:40, 0] = 1.0  # vivid red patch (less frequent)
    return torch.from_numpy(img)[None, ...]


def test_rgb_to_hsl_basics():
    h, s, l = rgb_to_hsl((255, 0, 0))
    assert abs(s - 1.0) < 1e-6 and abs(l - 0.5) < 1e-6
    _, s_gray, _ = rgb_to_hsl((128, 128, 128))
    assert s_gray < 1e-6
    _, _, l_white = rgb_to_hsl((255, 255, 255))
    assert abs(l_white - 1.0) < 1e-6


def test_vibrant_mode_surfaces_accent_over_frequent_background():
    image = _light_gray_bg_with_red_patch()
    colors = json.loads(_node().extract(image, 8, 10.0, "vibrant")[0])
    r, g, b = hex_to_rgb(colors[0])
    # Vibrant mode should rank the vivid red first despite gray being more frequent.
    assert r > 180 and g < 70 and b < 70


def test_differs_from_frequency_extractor():
    image = _light_gray_bg_with_red_patch()
    # Base extractor ranks by frequency -> the gray background comes first.
    base_first = json.loads(IdeogramPaletteExtractor().extract(image, 8, 10.0)[0])[0]
    br, bg, bb = hex_to_rgb(base_first)
    assert abs(br - bg) < 40 and abs(bg - bb) < 40  # base #0 is grayish
    # Vibrant extractor ranks the red first instead.
    vib_first = json.loads(_node().extract(image, 8, 10.0, "vibrant")[0])[0]
    vr, vg, vb = hex_to_rgb(vib_first)
    assert vr > 180 and vg < 70 and vb < 70


def test_muted_mode_deprioritizes_vivid():
    image = _light_gray_bg_with_red_patch()
    colors = json.loads(_node().extract(image, 8, 10.0, "muted")[0])
    r, g, b = hex_to_rgb(colors[0])
    # Muted mode should not put the vivid red first.
    assert not (r > 180 and g < 70 and b < 70)


def test_all_modes_run_without_error():
    image = _light_gray_bg_with_red_patch()
    for mode in ["vibrant", "light_vibrant", "dark_vibrant", "muted", "light_muted", "dark_muted"]:
        palette_json, preview, count = _node().extract(image, 8, 10.0, mode)
        colors = json.loads(palette_json)
        assert len(colors) == count >= 1
        assert preview.shape[0] == 1


def test_output_format():
    image = _light_gray_bg_with_red_patch()
    palette_json, preview, count = _node().extract(image, 8, 10.0, "vibrant")
    for c in json.loads(palette_json):
        hex_to_rgb(c)  # raises if invalid
    assert isinstance(preview, torch.Tensor) and preview.shape[3] == 3


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("All vibrant_palette_extractor tests passed.")
