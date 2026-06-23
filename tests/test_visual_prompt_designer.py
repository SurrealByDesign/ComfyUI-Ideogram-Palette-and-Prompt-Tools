"""Tests for IdeogramVisualPromptDesigner (Phase 1: model, validation, round-trip).

Exercises designer-state translation in both directions, the validator
integration, palette override precedence, the high_level_description
non-destructive-override rule, malformed-input recovery, designer-only field
round-tripping via designer_state_json (including the position-based element
matching limitation), hidden-element exclusion from the generated prompt, and
UTF-8 serialization. Pure stdlib + schema_utils/json_validator, so no torch/
ComfyUI needed.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nodes.visual_prompt_designer import IdeogramVisualPromptDesigner
from utils.designer_model import designer_state_to_prompt, new_designer_state, serialize_state

D = IdeogramVisualPromptDesigner()

EXISTING_PROMPT = json.dumps({
    "high_level_description": "a lone traveler at dusk",
    "style_description": {
        "aesthetics": "cinematic",
        "lighting": "golden hour",
        "color_palette": ["#FF8800", "#222244"],
    },
    "compositional_deconstruction": {
        "background": "a wide valley",
        "elements": [
            {"type": "obj", "bbox": [400, 100, 900, 500], "desc": "a traveler"},
            {"type": "text", "text": "DUSK", "bbox": [10, 10, 100, 300], "desc": "bold serif title"},
        ],
    },
})


def test_create_from_scratch_is_valid():
    ideogram_prompt, json_string, designer_state, is_valid, report = D.design(
        "a quiet harbor at sunrise", strict_mode=False
    )
    assert ideogram_prompt == json_string
    prompt = json.loads(ideogram_prompt)
    assert prompt["high_level_description"] == "a quiet harbor at sunrise"
    assert prompt["style_description"]["color_palette"] == []
    assert prompt["compositional_deconstruction"]["elements"] == []
    assert is_valid is True
    state = json.loads(designer_state)
    assert state["designer_version"] == 1


def test_loading_existing_prompt_reconstructs_state():
    _, _, designer_state, is_valid, _ = D.design("", strict_mode=False, prompt_json=EXISTING_PROMPT)
    state = json.loads(designer_state)
    assert state["high_level_description"] == "a lone traveler at dusk"
    assert state["style"]["aesthetics"] == "cinematic"
    assert state["palette"]["colors"] == ["#FF8800", "#222244"]
    assert state["composition"]["background"] == "a wide valley"
    assert len(state["composition"]["elements"]) == 2
    assert state["composition"]["elements"][1]["type"] == "text"
    assert state["composition"]["elements"][1]["text"] == "DUSK"
    assert is_valid is True


def test_blank_description_does_not_overwrite_loaded_prompt():
    ideogram_prompt, _, _, _, _ = D.design("", strict_mode=False, prompt_json=EXISTING_PROMPT)
    prompt = json.loads(ideogram_prompt)
    assert prompt["high_level_description"] == "a lone traveler at dusk"


def test_nonempty_description_overrides_loaded_prompt():
    ideogram_prompt, _, _, _, _ = D.design(
        "a brand new description", strict_mode=False, prompt_json=EXISTING_PROMPT
    )
    prompt = json.loads(ideogram_prompt)
    assert prompt["high_level_description"] == "a brand new description"


def test_palette_override_wins_over_loaded_palette():
    palette_json = json.dumps(["#00ff00", "#0000ff"])
    ideogram_prompt, _, _, _, report = D.design(
        "", strict_mode=False, prompt_json=EXISTING_PROMPT, palette_json=palette_json
    )
    prompt = json.loads(ideogram_prompt)
    assert prompt["style_description"]["color_palette"] == ["#00FF00", "#0000FF"]
    assert "override" in report.lower()


def test_malformed_palette_json_is_skipped_not_crashed():
    ideogram_prompt, _, _, _, report = D.design(
        "", strict_mode=False, prompt_json=EXISTING_PROMPT, palette_json="not json"
    )
    prompt = json.loads(ideogram_prompt)
    # original loaded palette survives untouched
    assert prompt["style_description"]["color_palette"] == ["#FF8800", "#222244"]
    assert "skipped" in report.lower()


def test_malformed_prompt_json_falls_back_to_empty_prompt():
    ideogram_prompt, _, _, is_valid, report = D.design(
        "a fresh start", strict_mode=False, prompt_json="{not valid json"
    )
    prompt = json.loads(ideogram_prompt)
    assert prompt["high_level_description"] == "a fresh start"
    assert prompt["compositional_deconstruction"]["elements"] == []
    assert "prompt_json was not valid json" in report.lower()


def test_malformed_designer_state_json_does_not_crash():
    _, _, _, is_valid, report = D.design(
        "", strict_mode=False, prompt_json=EXISTING_PROMPT, designer_state_json="{broken"
    )
    assert is_valid is True
    assert "not restored" in report.lower() or "designer_state_json" in report.lower()


def test_designer_only_fields_round_trip_via_designer_state_json():
    # First pass: load the prompt, then hand-edit the resulting designer state
    # the way a future canvas (or a manual JSON tweak) would -- set notes,
    # subjects, and per-element designer-only fields.
    _, _, designer_state_1, _, _ = D.design("", strict_mode=False, prompt_json=EXISTING_PROMPT)
    state = json.loads(designer_state_1)
    state["notes"] = "client wants warmer tones"
    state["subjects"] = [{"description": "the traveler", "importance": "hero"}]
    state["composition"]["elements"][0]["depth_layer"] = "foreground"
    state["composition"]["elements"][0]["visual_weight"] = 2.5
    state["composition"]["elements"][0]["locked"] = True
    state["composition"]["elements"][1]["hidden"] = True
    saved_metadata = serialize_state(state)

    # Second pass: reload the same prompt fresh, restoring the designer-only
    # fields from the saved metadata -- simulating the round-trip workflow.
    _, _, designer_state_2, _, report = D.design(
        "", strict_mode=False, prompt_json=EXISTING_PROMPT, designer_state_json=saved_metadata
    )
    restored = json.loads(designer_state_2)
    assert restored["notes"] == "client wants warmer tones"
    assert restored["subjects"] == [{"description": "the traveler", "importance": "hero"}]
    assert restored["composition"]["elements"][0]["depth_layer"] == "foreground"
    assert restored["composition"]["elements"][0]["visual_weight"] == 2.5
    assert restored["composition"]["elements"][0]["locked"] is True
    assert restored["composition"]["elements"][1]["hidden"] is True
    # prompt-visible content still comes from the freshly loaded prompt, not the snapshot
    assert restored["composition"]["elements"][1]["text"] == "DUSK"
    assert "restored" in report.lower()


def test_invalid_saved_depth_layer_is_rejected_with_warning():
    _, _, designer_state_1, _, _ = D.design("", strict_mode=False, prompt_json=EXISTING_PROMPT)
    state = json.loads(designer_state_1)
    state["composition"]["elements"][0]["depth_layer"] = "not_a_real_layer"
    saved_metadata = serialize_state(state)

    _, _, designer_state_2, _, report = D.design(
        "", strict_mode=False, prompt_json=EXISTING_PROMPT, designer_state_json=saved_metadata
    )
    restored = json.loads(designer_state_2)
    # invalid value rejected; default depth layer kept instead of the bogus saved one
    assert restored["composition"]["elements"][0]["depth_layer"] == "midground"
    assert "not_a_real_layer" in report
    assert "midground" in report


def test_composition_elements_have_no_id_field():
    # A position-derived "id" would be exactly as position-dependent as the
    # index itself and would misleadingly imply persistent per-element
    # identity that doesn't exist yet -- see merge_metadata_into_state's
    # docstring. Elements must not carry one.
    _, _, designer_state, _, _ = D.design("", strict_mode=False, prompt_json=EXISTING_PROMPT)
    state = json.loads(designer_state)
    for element in state["composition"]["elements"]:
        assert "id" not in element


def test_designer_state_validation_is_structured_not_just_prose():
    _, _, designer_state, is_valid, _ = D.design("", strict_mode=False)
    state = json.loads(designer_state)
    assert state["validation"]["is_valid"] is True
    assert state["validation"]["errors"] == []
    assert isinstance(state["validation"]["warnings"], list)
    # the missing-top-level-keys warning should show up structurally too,
    # not just buried in the prose report
    assert any("high_level_description" in w for w in state["validation"]["warnings"])


def test_hidden_elements_excluded_from_generated_prompt_but_kept_in_state():
    state = new_designer_state()
    state["composition"]["elements"] = [
        {"type": "obj", "bbox": [0, 0, 100, 100], "description": "visible", "palette_affinity": [],
         "hidden": False},
        {"type": "obj", "bbox": [0, 0, 100, 100], "description": "hidden one", "palette_affinity": [],
         "hidden": True},
    ]
    prompt = designer_state_to_prompt(state)
    descs = [el["desc"] for el in prompt["compositional_deconstruction"]["elements"]]
    assert descs == ["visible"]


def test_strict_mode_fails_on_missing_top_level_keys_warning():
    _, _, _, is_valid_lenient, _ = D.design("", strict_mode=False)
    _, _, _, is_valid_strict, report = D.design("", strict_mode=True)
    assert is_valid_lenient is True
    assert is_valid_strict is False
    assert "warning" in report.lower()


def test_ensure_ascii_false_literal_utf8():
    ideogram_prompt, _, designer_state, _, _ = D.design("café façade — naïve scene")
    assert "façade" in ideogram_prompt
    assert "\\u" not in ideogram_prompt
    assert "façade" in designer_state
    assert "\\u" not in designer_state


def test_reference_image_is_not_accepted():
    # Deliberately not implemented yet -- see the module docstring. This is a
    # regression guard against silently re-adding a no-op input.
    try:
        D.design("a scene", strict_mode=False, reference_image=object())
        assert False, "expected a TypeError for the unexpected reference_image kwarg"
    except TypeError:
        pass


if __name__ == "__main__":
    test_create_from_scratch_is_valid()
    print("create_from_scratch_is_valid: OK")
    test_loading_existing_prompt_reconstructs_state()
    print("loading_existing_prompt_reconstructs_state: OK")
    test_blank_description_does_not_overwrite_loaded_prompt()
    print("blank_description_does_not_overwrite_loaded_prompt: OK")
    test_nonempty_description_overrides_loaded_prompt()
    print("nonempty_description_overrides_loaded_prompt: OK")
    test_palette_override_wins_over_loaded_palette()
    print("palette_override_wins_over_loaded_palette: OK")
    test_malformed_palette_json_is_skipped_not_crashed()
    print("malformed_palette_json_is_skipped_not_crashed: OK")
    test_malformed_prompt_json_falls_back_to_empty_prompt()
    print("malformed_prompt_json_falls_back_to_empty_prompt: OK")
    test_malformed_designer_state_json_does_not_crash()
    print("malformed_designer_state_json_does_not_crash: OK")
    test_designer_only_fields_round_trip_via_designer_state_json()
    print("designer_only_fields_round_trip_via_designer_state_json: OK")
    test_invalid_saved_depth_layer_is_rejected_with_warning()
    print("invalid_saved_depth_layer_is_rejected_with_warning: OK")
    test_composition_elements_have_no_id_field()
    print("composition_elements_have_no_id_field: OK")
    test_designer_state_validation_is_structured_not_just_prose()
    print("designer_state_validation_is_structured_not_just_prose: OK")
    test_hidden_elements_excluded_from_generated_prompt_but_kept_in_state()
    print("hidden_elements_excluded_from_generated_prompt_but_kept_in_state: OK")
    test_strict_mode_fails_on_missing_top_level_keys_warning()
    print("strict_mode_fails_on_missing_top_level_keys_warning: OK")
    test_ensure_ascii_false_literal_utf8()
    print("ensure_ascii_false_literal_utf8: OK")
    test_reference_image_is_not_accepted()
    print("reference_image_is_not_accepted: OK")
    print("All visual_prompt_designer tests passed.")
