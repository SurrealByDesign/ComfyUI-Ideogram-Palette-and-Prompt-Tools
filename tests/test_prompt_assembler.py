"""Tests for IdeogramPromptAssembler: deep merge, palette injection without
clobbering siblings, assemble-from-scratch, key ordering, and graceful failure."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nodes.prompt_assembler import IdeogramPromptAssembler


def _node():
    return IdeogramPromptAssembler()


def _full_base():
    return {
        "high_level_description": "a scene",
        "style_description": {
            "aesthetics": "moody",
            "lighting": "golden hour",
            "photo": "35mm",
            "medium": "photograph",
            "color_palette": ["#000000"],
        },
        "compositional_deconstruction": {"background": "bg", "elements": []},
    }


def test_inject_palette_preserves_sibling_style_fields():
    base = json.dumps(_full_base())
    merge = json.dumps({"style_description": {"color_palette": ["#FF5733", "#C70039"]}})
    out_json, report = _node().assemble(base, merge, True)
    style = json.loads(out_json)["style_description"]
    # color_palette replaced...
    assert style["color_palette"] == ["#FF5733", "#C70039"]
    # ...but photo/medium/aesthetics/lighting preserved
    assert style["photo"] == "35mm"
    assert style["medium"] == "photograph"
    assert style["aesthetics"] == "moody"
    assert style["lighting"] == "golden hour"


def test_assemble_from_empty_base():
    merge = json.dumps({"style_description": {"aesthetics": "a", "lighting": "l", "color_palette": ["#FF5733"]}})
    out_json, _ = _node().assemble("{}", merge, True)
    result = json.loads(out_json)
    assert result["style_description"]["color_palette"] == ["#FF5733"]


def test_key_order_fixed_after_merge():
    scrambled = json.dumps({
        "compositional_deconstruction": {"elements": []},
        "style_description": {"color_palette": ["#FF5733"], "lighting": "l", "aesthetics": "a"},
        "high_level_description": "d",
    })
    merge = json.dumps({"style_description": {"color_palette": ["#111111"]}})
    out_json, _ = _node().assemble(scrambled, merge, True)
    result = json.loads(out_json)
    assert list(result.keys()) == ["high_level_description", "style_description", "compositional_deconstruction"]
    assert list(result["style_description"].keys()) == ["aesthetics", "lighting", "color_palette"]


def test_scalar_overwrite():
    base = json.dumps({"high_level_description": "old"})
    merge = json.dumps({"high_level_description": "new"})
    out_json, _ = _node().assemble(base, merge, True)
    assert json.loads(out_json)["high_level_description"] == "new"


def test_adds_new_top_level_key():
    base = json.dumps({"high_level_description": "d"})
    merge = json.dumps({"style_description": {"color_palette": ["#FF5733"]}})
    out_json, report = _node().assemble(base, merge, True)
    result = json.loads(out_json)
    assert "style_description" in result
    assert "added: style_description" in report


def test_invalid_base_treated_as_empty():
    merge = json.dumps({"style_description": {"color_palette": ["#FF5733"]}})
    out_json, report = _node().assemble("not valid json", merge, True)
    result = json.loads(out_json)
    assert result["style_description"]["color_palette"] == ["#FF5733"]
    assert "base_json invalid" in report


def test_invalid_merge_returns_base_unchanged():
    base = json.dumps(_full_base())
    out_json, report = _node().assemble(base, "not valid json", True)
    assert json.loads(out_json) == _full_base()
    assert "merge_json invalid" in report


def test_does_not_mutate_unrelated_content():
    base = _full_base()
    base["compositional_deconstruction"]["elements"] = [{"type": "obj", "desc": "x", "color_palette": ["#ABCDEF"]}]
    merge = json.dumps({"style_description": {"color_palette": ["#FF5733"]}})
    out_json, _ = _node().assemble(json.dumps(base), merge, True)
    result = json.loads(out_json)
    assert result["compositional_deconstruction"]["elements"][0]["color_palette"] == ["#ABCDEF"]


def test_ensure_ascii_false_on_normal_merge():
    base = json.dumps({"high_level_description": "café façade"})
    merge = json.dumps({"style_description": {"color_palette": ["#FF5733"]}})
    out_json, _ = _node().assemble(base, merge, True)
    assert "façade" in out_json
    assert "\\u" not in out_json


def test_ensure_ascii_false_when_merge_invalid():
    # Exercises the other json.dumps call site (merge_json invalid -> base
    # returned via the base_err is None and base branch, not base_json itself).
    base = json.dumps({"high_level_description": "café façade"})
    out_json, report = _node().assemble(base, "not valid json", True)
    assert "façade" in out_json
    assert "\\u" not in out_json
    assert "merge_json invalid" in report


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("All prompt_assembler tests passed.")

