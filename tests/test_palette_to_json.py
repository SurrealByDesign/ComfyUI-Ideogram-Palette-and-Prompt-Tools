"""Tests for IdeogramPaletteToGlobalJSON: key ordering, schema shape, and fallback handling."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nodes.palette_to_json import IdeogramPaletteToGlobalJSON, MAX_GLOBAL_COLORS

SAMPLE_PALETTE = json.dumps(["#FF5733", "#C70039", "#900C3F", "#581845"])


def _node():
    return IdeogramPaletteToGlobalJSON()


def test_top_level_key_is_style_description():
    (style_json,) = _node().build(SAMPLE_PALETTE)
    parsed = json.loads(style_json)
    assert list(parsed.keys()) == ["style_description"]


def test_key_order_aesthetics_lighting_color_palette():
    (style_json,) = _node().build(SAMPLE_PALETTE, aesthetics="moody", lighting="golden hour")
    parsed = json.loads(style_json)
    assert list(parsed["style_description"].keys()) == ["aesthetics", "lighting", "color_palette"]


def test_values_preserved():
    (style_json,) = _node().build(SAMPLE_PALETTE, aesthetics="moody", lighting="golden hour")
    style = json.loads(style_json)["style_description"]
    assert style["aesthetics"] == "moody"
    assert style["lighting"] == "golden hour"
    assert style["color_palette"] == ["#FF5733", "#C70039", "#900C3F", "#581845"]


def test_defaults_are_empty_strings():
    (style_json,) = _node().build(SAMPLE_PALETTE)
    style = json.loads(style_json)["style_description"]
    assert style["aesthetics"] == ""
    assert style["lighting"] == ""


def test_clamps_to_max_global_colors():
    big_palette = json.dumps([f"#{i:06X}" for i in range(0, MAX_GLOBAL_COLORS + 5)])
    (style_json,) = _node().build(big_palette)
    style = json.loads(style_json)["style_description"]
    assert len(style["color_palette"]) == MAX_GLOBAL_COLORS


def test_malformed_palette_json_falls_back():
    (style_json,) = _node().build("not valid json")
    style = json.loads(style_json)["style_description"]
    assert style["color_palette"] == ["#808080"]
    assert list(style.keys()) == ["aesthetics", "lighting", "color_palette"]


def test_non_list_palette_falls_back():
    (style_json,) = _node().build(json.dumps({"not": "a list"}))
    style = json.loads(style_json)["style_description"]
    assert style["color_palette"] == ["#808080"]


def test_empty_palette_array_falls_back():
    (style_json,) = _node().build("[]")
    style = json.loads(style_json)["style_description"]
    assert style["color_palette"] == ["#808080"]


def test_ensure_ascii_false_for_non_ascii_aesthetics():
    (style_json,) = _node().build(SAMPLE_PALETTE, aesthetics="café façade — naïve", lighting="golden hour")
    assert "façade" in style_json
    assert "\\u" not in style_json
    style = json.loads(style_json)["style_description"]
    assert style["aesthetics"] == "café façade — naïve"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("All palette_to_json tests passed.")
