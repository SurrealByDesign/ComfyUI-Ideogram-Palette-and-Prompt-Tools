"""Tests for IdeogramPaletteExtractor's core extraction logic against the four
required image types from the bible's Section 8 testing checklist:
photograph, logo/graphic, painting, near-monochrome.

These tests exercise `_extract_palette` directly (PIL in, hex list out) since
the full node's `extract()` requires torch, which is only present inside a
ComfyUI environment.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from nodes.palette_extractor import _extract_palette
from utils.color_utils import hex_to_rgb, rgb_to_lab, delta_e

IMG_DIR = Path(__file__).resolve().parent / "test_images"


def _load(name):
    return Image.open(IMG_DIR / name)


def _assert_min_delta_e(hex_colors, min_delta_e):
    labs = [rgb_to_lab(hex_to_rgb(h)) for h in hex_colors]
    for i in range(len(labs)):
        for j in range(i + 1, len(labs)):
            d = delta_e(labs[i], labs[j])
            assert d >= min_delta_e - 1e-6, f"{hex_colors[i]} vs {hex_colors[j]} delta_e={d}"


def test_photograph():
    img = _load("photograph.png")
    colors = _extract_palette(img, num_colors=8, min_delta_e=10.0)
    assert 4 <= len(colors) <= 8
    _assert_min_delta_e(colors, 10.0)


def test_logo():
    img = _load("logo.png")
    colors = _extract_palette(img, num_colors=8, min_delta_e=10.0)
    # flat 4-color logo should yield close to 4 distinct colors, not 8
    assert 3 <= len(colors) <= 5
    _assert_min_delta_e(colors, 10.0)


def test_painting():
    img = _load("painting.png")
    colors = _extract_palette(img, num_colors=8, min_delta_e=10.0)
    assert len(colors) >= 4
    _assert_min_delta_e(colors, 10.0)


def test_monochrome_fallback():
    img = _load("monochrome.png")
    colors = _extract_palette(img, num_colors=8, min_delta_e=10.0)
    # near-uniform gray should collapse to very few colors, never crash, never empty
    assert 1 <= len(colors) <= 3
    _assert_min_delta_e(colors, 10.0)


def test_json_serializable():
    img = _load("logo.png")
    colors = _extract_palette(img, num_colors=8, min_delta_e=10.0)
    s = json.dumps(colors)
    assert json.loads(s) == colors


def test_element_palette_clamps_to_five():
    img = _load("painting.png")
    colors = _extract_palette(img, num_colors=5, min_delta_e=10.0)[:5]
    assert 1 <= len(colors) <= 5
    _assert_min_delta_e(colors, 10.0)


def test_element_palette_monochrome_fallback():
    img = _load("monochrome.png")
    colors = _extract_palette(img, num_colors=5, min_delta_e=10.0)[:5]
    assert 1 <= len(colors) <= 5


if __name__ == "__main__":
    test_photograph()
    print("photograph: OK")
    test_logo()
    print("logo: OK")
    test_painting()
    print("painting: OK")
    test_monochrome_fallback()
    print("monochrome: OK")
    test_json_serializable()
    print("json_serializable: OK")
    test_element_palette_clamps_to_five()
    print("element_palette_clamps_to_five: OK")
    test_element_palette_monochrome_fallback()
    print("element_palette_monochrome_fallback: OK")
    print("All extractor tests passed.")
