"""Tests for IdeogramJSONValidator: parsing, key-order correction, schema-size
limits, hex validation, bbox bounds, structured errors_json/warnings_json
outputs, and graceful failure."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nodes.json_validator import IdeogramJSONValidator


def _node():
    return IdeogramJSONValidator()


def _well_ordered(color_palette=None, elements=None):
    style = {"aesthetics": "a", "lighting": "l", "color_palette": color_palette if color_palette is not None else ["#FF5733"]}
    comp = {"background": "bg", "elements": elements if elements is not None else []}
    return {
        "high_level_description": "desc",
        "style_description": style,
        "compositional_deconstruction": comp,
    }


def test_valid_well_ordered_passes():
    out_json, is_valid, report, *_ = _node().validate(json.dumps(_well_ordered()), True, False)
    assert is_valid is True
    assert "PASS" in report
    parsed = json.loads(out_json)
    assert list(parsed.keys()) == ["high_level_description", "style_description", "compositional_deconstruction"]


def test_wrong_key_order_is_corrected():
    # Deliberately scrambled key order at both levels.
    scrambled = {
        "compositional_deconstruction": {"elements": []},
        "style_description": {"color_palette": ["#FF5733"], "lighting": "l", "aesthetics": "a"},
        "high_level_description": "desc",
    }
    out_json, is_valid, *_ = _node().validate(json.dumps(scrambled), True, False)
    parsed = json.loads(out_json)
    assert list(parsed.keys()) == ["high_level_description", "style_description", "compositional_deconstruction"]
    assert list(parsed["style_description"].keys()) == ["aesthetics", "lighting", "color_palette"]
    assert is_valid is True


def test_key_order_preserved_when_fix_disabled():
    scrambled = {"style_description": {"color_palette": []}, "high_level_description": "d"}
    out_json, *_ = _node().validate(json.dumps(scrambled), False, False)
    # With fixing off, the original string is returned unchanged.
    assert json.loads(out_json) == scrambled


def test_invalid_json_does_not_crash():
    out_json, is_valid, report, *_ = _node().validate("{not valid json", True, False)
    assert is_valid is False
    assert out_json == "{not valid json"  # original returned untouched
    assert "invalid JSON" in report


def test_global_palette_over_16_fails():
    palette = [f"#{i:06X}" for i in range(17)]  # 17 colors
    out_json, is_valid, report, *_ = _node().validate(json.dumps(_well_ordered(color_palette=palette)), True, False)
    assert is_valid is False
    assert "max 16" in report


def test_element_palette_over_5_fails():
    elements = [{"type": "obj", "desc": "x", "color_palette": [f"#{i:06X}" for i in range(6)]}]
    out_json, is_valid, report, *_ = _node().validate(json.dumps(_well_ordered(elements=elements)), True, False)
    assert is_valid is False
    assert "max 5" in report


def test_malformed_hex_is_reported():
    out_json, is_valid, report, *_ = _node().validate(
        json.dumps(_well_ordered(color_palette=["#FF5733", "not-a-color", "#GGGGGG"])), True, False
    )
    # Bad hex is a warning, not an error -> still valid in non-strict mode.
    assert is_valid is True
    assert "malformed hex" in report


def test_malformed_hex_fails_in_strict_mode():
    out_json, is_valid, report, *_ = _node().validate(
        json.dumps(_well_ordered(color_palette=["bad"])), True, True
    )
    assert is_valid is False


def test_bbox_out_of_range_fails():
    elements = [{"type": "obj", "desc": "TEXT: 'HI' bbox=[250,120,1200,220]"}]
    out_json, is_valid, report, *_ = _node().validate(json.dumps(_well_ordered(elements=elements)), True, False)
    assert is_valid is False
    assert "bbox" in report and "out of range" in report


def test_missing_top_level_key_warns_but_can_pass():
    minimal = {"style_description": {"color_palette": ["#FF5733"]}}
    out_json, is_valid, report, *_ = _node().validate(json.dumps(minimal), True, False)
    assert "missing top-level key" in report
    assert is_valid is True  # missing keys are warnings, not errors


def test_content_values_unchanged():
    original = _well_ordered(color_palette=["#FF5733", "#C70039"])
    out_json, *_ = _node().validate(json.dumps(original), True, False)
    parsed = json.loads(out_json)
    assert parsed["high_level_description"] == "desc"
    assert parsed["style_description"]["color_palette"] == ["#FF5733", "#C70039"]


def test_errors_json_and_warnings_json_are_valid_json_arrays_when_clean():
    _, is_valid, _, errors_json, warnings_json = _node().validate(json.dumps(_well_ordered()), True, False)
    assert is_valid is True
    assert json.loads(errors_json) == []
    assert json.loads(warnings_json) == []


def test_errors_json_contains_structured_error_messages():
    palette = [f"#{i:06X}" for i in range(17)]
    _, is_valid, report, errors_json, warnings_json = _node().validate(
        json.dumps(_well_ordered(color_palette=palette)), True, False
    )
    errors = json.loads(errors_json)
    assert is_valid is False
    assert len(errors) == 1
    assert "max 16" in errors[0]
    # same content as the prose report, just structured instead of text
    assert errors[0] in report
    assert json.loads(warnings_json) == []


def test_warnings_json_contains_structured_warning_messages():
    _, is_valid, report, errors_json, warnings_json = _node().validate(
        json.dumps(_well_ordered(color_palette=["not-a-color"])), True, False
    )
    warnings = json.loads(warnings_json)
    assert is_valid is True
    assert json.loads(errors_json) == []
    assert len(warnings) == 1
    assert "malformed hex" in warnings[0]
    assert warnings[0] in report


def test_errors_json_present_even_on_invalid_json_input():
    _, is_valid, _, errors_json, warnings_json = _node().validate("{not valid json", True, False)
    assert is_valid is False
    errors = json.loads(errors_json)
    assert len(errors) == 1
    assert "invalid JSON" in errors[0]
    assert json.loads(warnings_json) == []


def test_errors_json_and_warnings_json_preserve_non_ascii_literally():
    # A malformed hex entry containing non-ASCII text ends up quoted (via
    # !r) inside the warning message itself -- confirm it survives into
    # errors_json/warnings_json as literal UTF-8, not \uXXXX escapes.
    _, is_valid, _, errors_json, warnings_json = _node().validate(
        json.dumps(_well_ordered(color_palette=["café"])), True, False
    )
    assert is_valid is True
    assert "café" in warnings_json
    assert "\\u" not in warnings_json
    assert json.loads(errors_json) == []


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("All json_validator tests passed.")
