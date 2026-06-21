"""Tests for IdeogramElementBuilder and IdeogramElementCollector.

Exercises element JSON assembly (key order, type/text handling, bbox clamping
and inversion fixes, per-element palette parsing/trimming) and the collector's
parsing, malformed-input skipping, text-box overlap detection, and UTF-8
serialization. Pure stdlib + schema_utils, so no torch/ComfyUI needed.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nodes.element_builder import IdeogramElementBuilder, IdeogramElementCollector

B = IdeogramElementBuilder()
C = IdeogramElementCollector()


def test_obj_element_builds():
    element_json, preview = B.build("obj", "a red mug", 100, 200, 800, 600, "", "")
    el = json.loads(element_json)
    assert el["type"] == "obj"
    assert el["bbox"] == [100, 200, 800, 600]  # [ymin, xmin, ymax, xmax]
    assert el["desc"] == "a red mug"
    assert "text" not in el
    assert "color_palette" not in el
    assert list(el.keys()) == ["type", "bbox", "desc"]
    assert preview.startswith("obj @ [y:100-800, x:200-600]")


def test_text_includes_text_obj_omits():
    text_json, _ = B.build("text", "bold white sans-serif", 10, 20, 100, 400, "", "SALE")
    et = json.loads(text_json)
    assert et["type"] == "text"
    assert et["text"] == "SALE"
    assert list(et.keys()) == ["type", "text", "bbox", "desc"]

    obj_json, _ = B.build("obj", "a tree", 0, 0, 100, 100, "", "ignored for obj")
    eo = json.loads(obj_json)
    assert "text" not in eo


def test_text_empty_uses_placeholder():
    text_json, preview = B.build("text", "styling", 0, 0, 100, 100, "", "")
    et = json.loads(text_json)
    assert et["text"] == "[text required]"
    assert "placeholder" in preview


def test_bbox_clamp_and_warn():
    element_json, preview = B.build("obj", "x", -50, 200, 1500, 600, "", "")
    el = json.loads(element_json)
    assert el["bbox"] == [0, 200, 1000, 600]
    assert "clamped" in preview


def test_inverted_bbox_corrected():
    element_json, preview = B.build("obj", "x", 800, 600, 100, 200, "", "")
    el = json.loads(element_json)
    assert el["bbox"] == [100, 200, 800, 600]
    assert "swapped" in preview


def test_palette_uppercased():
    element_json, _ = B.build("obj", "x", 0, 0, 100, 100, json.dumps(["#abcdef", "#123ABC"]), "")
    el = json.loads(element_json)
    assert el["color_palette"] == ["#ABCDEF", "#123ABC"]


def test_palette_trimmed_to_five():
    palette = json.dumps(["#111111", "#222222", "#333333", "#444444", "#555555", "#666666", "#777777"])
    element_json, preview = B.build("obj", "x", 0, 0, 100, 100, palette, "")
    el = json.loads(element_json)
    assert el["color_palette"] == ["#111111", "#222222", "#333333", "#444444", "#555555"]
    assert "trimmed" in preview


def test_malformed_palette_omitted():
    element_json, preview = B.build("obj", "x", 0, 0, 100, 100, "not valid json", "")
    el = json.loads(element_json)
    assert "color_palette" not in el
    assert "omitted" in preview


def test_collector_assembles_three():
    e1, _ = B.build("obj", "sky", 0, 0, 300, 1000, "", "")
    e2, _ = B.build("obj", "subject", 300, 400, 800, 600, "", "")
    e3, _ = B.build("text", "title styling", 10, 10, 80, 500, "", "TITLE")
    comp_json, count, overlap = C.collect("a wide landscape", e1, e2, e3)
    block = json.loads(comp_json)
    assert list(block.keys()) == ["background", "elements"]
    assert block["background"] == "a wide landscape"
    assert len(block["elements"]) == 3
    assert count == 3
    assert overlap == ""


def test_collector_skips_malformed():
    good, _ = B.build("obj", "ok", 0, 0, 100, 100, "", "")
    comp_json, count, _ = C.collect(
        "bg",
        good,
        "{not json",
        '{"type": "banana", "bbox": [0,0,1,1], "desc": "bad type"}',
        '{"type": "obj", "desc": "no bbox"}',
    )
    block = json.loads(comp_json)
    assert count == 1
    assert len(block["elements"]) == 1
    assert block["elements"][0]["desc"] == "ok"


def test_collector_detects_overlap():
    t1, _ = B.build("text", "A", 100, 100, 300, 300, "", "AAA")
    t2, _ = B.build("text", "B", 200, 200, 400, 400, "", "BBB")  # intersects t1
    comp_json, count, overlap = C.collect("bg", t1, t2)
    assert count == 2
    assert overlap != ""
    assert "overlap" in overlap.lower()


def test_collector_overlap_only_text():
    # Non-overlapping text pair reports nothing.
    t1, _ = B.build("text", "A", 0, 0, 100, 100, "", "AAA")
    t2, _ = B.build("text", "B", 200, 200, 300, 300, "", "BBB")
    _, _, overlap = C.collect("bg", t1, t2)
    assert overlap == ""

    # An obj overlapping a text must NOT be flagged (text-vs-text only).
    obj, _ = B.build("obj", "box", 100, 100, 300, 300, "", "")
    txt, _ = B.build("text", "T", 100, 100, 300, 300, "", "T")
    _, _, overlap2 = C.collect("bg", obj, txt)
    assert overlap2 == ""


def test_collector_skips_empty_inputs():
    good, _ = B.build("obj", "ok", 0, 0, 100, 100, "", "")
    comp_json, count, _ = C.collect("bg", good, "", "   ", "")
    block = json.loads(comp_json)
    assert count == 1
    assert len(block["elements"]) == 1


def test_ensure_ascii_false_literal_utf8():
    element_json, _ = B.build("obj", "café façade — naïve", 0, 0, 100, 100, "", "")
    assert "façade" in element_json          # literal characters present
    assert "\\u" not in element_json               # no escaped \uXXXX sequences
    el = json.loads(element_json)
    assert el["desc"] == "café façade — naïve"

    comp_json, _, _ = C.collect("背景", element_json)
    assert "背景" in comp_json
    assert "\\u" not in comp_json


if __name__ == "__main__":
    test_obj_element_builds()
    print("obj_element_builds: OK")
    test_text_includes_text_obj_omits()
    print("text_includes_text_obj_omits: OK")
    test_text_empty_uses_placeholder()
    print("text_empty_uses_placeholder: OK")
    test_bbox_clamp_and_warn()
    print("bbox_clamp_and_warn: OK")
    test_inverted_bbox_corrected()
    print("inverted_bbox_corrected: OK")
    test_palette_uppercased()
    print("palette_uppercased: OK")
    test_palette_trimmed_to_five()
    print("palette_trimmed_to_five: OK")
    test_malformed_palette_omitted()
    print("malformed_palette_omitted: OK")
    test_collector_assembles_three()
    print("collector_assembles_three: OK")
    test_collector_skips_malformed()
    print("collector_skips_malformed: OK")
    test_collector_detects_overlap()
    print("collector_detects_overlap: OK")
    test_collector_overlap_only_text()
    print("collector_overlap_only_text: OK")
    test_collector_skips_empty_inputs()
    print("collector_skips_empty_inputs: OK")
    test_ensure_ascii_false_literal_utf8()
    print("ensure_ascii_false_literal_utf8: OK")
    print("All element_builder tests passed.")
