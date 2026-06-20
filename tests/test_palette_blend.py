"""Tests for IdeogramPaletteBlend: ratio weighting, dedup, clamping, and fallbacks."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nodes.palette_blend import IdeogramPaletteBlend
from utils.color_utils import hex_to_rgb

A_LIST = ["#FF0000", "#E10000", "#C30000", "#A50000", "#870000", "#690000", "#4B0000", "#2D0000"]  # reds
B_LIST = ["#0000FF", "#0000E1", "#0000C3", "#0000A5", "#000087", "#000069", "#00004B", "#00002D"]  # blues
PALETTE_A = json.dumps(A_LIST)
PALETTE_B = json.dumps(B_LIST)
A_SET, B_SET = set(A_LIST), set(B_LIST)


def _node():
    return IdeogramPaletteBlend()


def _colors(palette_a, palette_b, ratio, max_colors):
    out_json, _ = _node().blend(palette_a, palette_b, ratio, max_colors)
    return json.loads(out_json)


def test_ratio_zero_is_pure_a():
    colors = _colors(PALETTE_A, PALETTE_B, 0.0, 8)
    assert all(c in A_SET for c in colors)
    assert colors == A_LIST


def test_ratio_one_is_pure_b():
    colors = _colors(PALETTE_A, PALETTE_B, 1.0, 8)
    assert all(c in B_SET for c in colors)
    assert colors == B_LIST


def test_ratio_half_mixes_evenly():
    colors = _colors(PALETTE_A, PALETTE_B, 0.5, 8)
    assert sum(c in A_SET for c in colors) == 4
    assert sum(c in B_SET for c in colors) == 4
    # interleaved by rank: most dominant of each appears first
    assert colors[0] in A_SET
    assert colors[1] in B_SET


def test_ratio_quarter_weights_toward_a():
    colors = _colors(PALETTE_A, PALETTE_B, 0.25, 8)
    assert sum(c in A_SET for c in colors) == 6
    assert sum(c in B_SET for c in colors) == 2


def test_max_colors_clamp():
    colors = _colors(PALETTE_A, PALETTE_B, 0.5, 4)
    assert len(colors) == 4


def test_exact_duplicate_removed():
    a = json.dumps(["#FFFFFF", "#000000"])
    b = json.dumps(["#ffffff", "#123456"])  # shares white (case-insensitive)
    colors = _colors(a, b, 0.5, 8)
    assert colors.count("#FFFFFF") == 1


def test_output_is_valid_uppercase_hex():
    colors = _colors(PALETTE_A, PALETTE_B, 0.5, 8)
    for c in colors:
        assert c == c.upper()
        hex_to_rgb(c)  # raises if invalid


def test_malformed_input_falls_back():
    colors = _colors("not json", "also not json", 0.5, 8)
    assert colors == ["#808080"]


def test_short_side_yields_only_its_allocation():
    # A empty, ratio 0.5 -> B contributes only its n_b=4 share (no cross-fill).
    colors = _colors("[]", PALETTE_B, 0.5, 8)
    assert all(c in B_SET for c in colors)
    assert len(colors) == 4


def test_preview_shape_matches_color_count():
    out_json, preview = _node().blend(PALETTE_A, PALETTE_B, 0.5, 6)
    colors = json.loads(out_json)
    assert preview.shape[0] == 1
    assert preview.shape[2] == 100 * len(colors)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("All palette_blend tests passed.")
