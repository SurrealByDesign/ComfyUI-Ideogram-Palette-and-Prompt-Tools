"""Tests for IdeogramPaletteOverride: add/remove/clamp behavior and fallback handling."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nodes.palette_override import IdeogramPaletteOverride
from utils.preview_utils import SWATCH_WIDTH, SWATCH_HEIGHT, LABEL_BAND_HEIGHT

SAMPLE_PALETTE = json.dumps(["#E63946", "#457B9D", "#1D3557", "#F1FAEE"])
STRIP_H = SWATCH_HEIGHT + LABEL_BAND_HEIGHT


def _node():
    return IdeogramPaletteOverride()


def test_passthrough_no_changes():
    out_json, preview = _node().override(SAMPLE_PALETTE, max_colors=16)
    assert json.loads(out_json) == ["#E63946", "#457B9D", "#1D3557", "#F1FAEE"]
    assert preview.shape == (1, STRIP_H, SWATCH_WIDTH * 4, 3)


def test_remove_index():
    out_json, _ = _node().override(SAMPLE_PALETTE, max_colors=16, remove_index="0,2")
    assert json.loads(out_json) == ["#457B9D", "#F1FAEE"]


def test_remove_index_out_of_range_ignored():
    out_json, _ = _node().override(SAMPLE_PALETTE, max_colors=16, remove_index="99")
    assert json.loads(out_json) == ["#E63946", "#457B9D", "#1D3557", "#F1FAEE"]


def test_add_colors_appends_valid_only():
    out_json, _ = _node().override(SAMPLE_PALETTE, max_colors=16, add_colors="#FFFFFF,not-a-color,#000000")
    colors = json.loads(out_json)
    assert colors[-2:] == ["#FFFFFF", "#000000"]
    assert len(colors) == 6


def test_add_colors_without_hash_prefix():
    out_json, _ = _node().override(SAMPLE_PALETTE, max_colors=16, add_colors="ABCDEF")
    colors = json.loads(out_json)
    assert colors[-1] == "#ABCDEF"


def test_max_colors_clamp():
    out_json, _ = _node().override(SAMPLE_PALETTE, max_colors=2)
    assert json.loads(out_json) == ["#E63946", "#457B9D"]


def test_remove_and_add_and_clamp_combined():
    out_json, _ = _node().override(
        SAMPLE_PALETTE, max_colors=3, add_colors="#FFFFFF,#000000", remove_index="0"
    )
    colors = json.loads(out_json)
    assert len(colors) == 3
    assert colors == ["#457B9D", "#1D3557", "#F1FAEE"]


def test_malformed_palette_json_falls_back():
    out_json, preview = _node().override("not valid json", max_colors=16)
    assert json.loads(out_json) == ["#808080"]
    assert preview.shape == (1, STRIP_H, SWATCH_WIDTH, 3)


def test_removing_everything_falls_back_to_gray():
    out_json, _ = _node().override(SAMPLE_PALETTE, max_colors=16, remove_index="0,1,2,3")
    assert json.loads(out_json) == ["#808080"]


def test_empty_palette_array_falls_back():
    out_json, _ = _node().override("[]", max_colors=16)
    assert json.loads(out_json) == ["#808080"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("All palette_override tests passed.")
