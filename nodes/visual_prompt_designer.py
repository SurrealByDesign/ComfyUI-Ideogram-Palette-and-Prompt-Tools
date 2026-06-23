"""IdeogramVisualPromptDesigner node.

Phase 1 (backend foundation) of the Ideogram Visual Prompt Designer spec: the
model-translation, validation, and round-trip plumbing the future drag/resize
canvas UI will sit on top of. See README.md's "Ideogram Visual Prompt
Designer" section for what's in this phase versus deferred to the (separate,
custom-frontend) canvas phase.

What this node does today, with standard widgets, no canvas required:
  - Builds a prompt from scratch, or loads an existing one (`prompt_json`)
    and reconstructs an editable designer state from it.
  - Restores the designer-only fields a plain Ideogram prompt has no place
    for (subjects, hierarchy, relationships, notes, per-element depth/weight/
    lock/hide/group) from a previously saved designer state
    (`designer_state_json` -- typically read back from a second PNG metadata
    key via IdeogramMetadataReader), so round-tripping through a saved image
    loses as little as this phase's element-matching-by-position allows.
  - Applies an optional palette override (`palette_json`, the same plain hex
    array format every palette node in this repo emits).
  - Re-validates the result with the existing IdeogramJSONValidator (reused,
    not reimplemented) so invalid output never reaches downstream nodes
    silently.

There is deliberately no `reference_image` input here. The original spec
calls for one as a hook for future composition-assisted editing, but an
input that does nothing yet is the same "implies a capability that doesn't
exist" problem as the position-derived `id` field this module used to have
(see utils/designer_model.py's history) -- it will be added when the
composition-assisted-editing canvas actually consumes it, not before.

Never raises: any unexpected failure falls back to a fresh, valid empty state
rather than breaking the graph.
"""

try:
    from ..utils.designer_model import (
        designer_state_to_prompt,
        deserialize_state,
        merge_metadata_into_state,
        new_designer_state,
        parse_palette_override,
        prompt_to_designer_state,
        serialize_state,
    )
    from .json_validator import IdeogramJSONValidator
except ImportError:
    # Reached when this module is imported as `nodes.visual_prompt_designer`
    # with the repo root on sys.path (e.g. from a test script) rather than as
    # part of the installed custom-node package, where ".." has no parent
    # package to resolve to. `nodes.json_validator` (not a bare
    # `json_validator`) is needed here because json_validator.py lives in
    # nodes/, not the repo root, unlike utils/.
    from nodes.json_validator import IdeogramJSONValidator
    from utils.designer_model import (
        designer_state_to_prompt,
        deserialize_state,
        merge_metadata_into_state,
        new_designer_state,
        parse_palette_override,
        prompt_to_designer_state,
        serialize_state,
    )

import json
import sys


def _warn(message):
    """Surface a non-fatal warning to the console, matching IdeogramElementBuilder's
    pattern in nodes/element_builder.py. Centralized here (rather than in
    utils/designer_model.py) so the model layer stays pure/IO-free and every
    console-visible warning funnels through one place."""
    print(f"[IdeogramVisualPromptDesigner] {message}", file=sys.stderr)


def _parse_prompt_json(prompt_json):
    """Returns (dict_or_None, error_or_None). Empty/blank input is not an error."""
    text = (prompt_json or "").strip()
    if not text:
        return None, None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"prompt_json was not valid JSON: {e}"
    if not isinstance(parsed, dict):
        return None, "prompt_json was not a JSON object"
    return parsed, None


class IdeogramVisualPromptDesigner:
    """Phase 1 of the Ideogram Visual Prompt Designer: model, validation, and round-trip.

    Inputs:
        high_level_description: top-level prompt description. Only applied
            when non-empty, so loading an existing prompt without typing
            anything here doesn't blank out its description.
        strict_mode: passed through to IdeogramJSONValidator (warnings also
            fail validation when True).
        prompt_json (optional): an existing Ideogram prompt JSON string to
            load and reconstruct a designer state from.
        designer_state_json (optional): a previously saved designer state
            JSON string (e.g. from this node's own `designer_state` output, by
            way of a second PNG metadata key) to restore designer-only fields.
        palette_json (optional): a JSON array of hex colors to override the
            palette with (same format every palette node in this repo emits).

    Outputs:
        ideogram_prompt: the validated, key-ordered Ideogram prompt JSON
            string -- ready to feed into generation, IdeogramMetadataEmbedder,
            or further IdeogramJSONValidator/IdeogramPromptAssembler chaining.
        json_string: identical content to ideogram_prompt in this phase (see
            README for why these are intentionally the same value today).
        designer_state: the internal designer state JSON string, for round-
            tripping into another Designer node or persisting via metadata.
        is_valid: whether ideogram_prompt passed validation.
        report: a human-readable summary of what was loaded/restored/skipped,
            plus the validation report.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "high_level_description": ("STRING", {"default": "", "multiline": True}),
                "strict_mode": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "prompt_json": ("STRING", {"forceInput": True}),
                "designer_state_json": ("STRING", {"forceInput": True}),
                "palette_json": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "BOOLEAN", "STRING")
    RETURN_NAMES = ("ideogram_prompt", "json_string", "designer_state", "is_valid", "report")
    FUNCTION = "design"
    CATEGORY = "Ideogram/Palette"

    def design(self, high_level_description, strict_mode=False, prompt_json="",
               designer_state_json="", palette_json=""):
        notes = []
        try:
            base_prompt, prompt_err = _parse_prompt_json(prompt_json)
            if prompt_err:
                notes.append(prompt_err + "; starting from an empty prompt")
            state = prompt_to_designer_state(base_prompt if base_prompt is not None else {})
            if base_prompt is not None:
                notes.append("Loaded prompt_json and reconstructed a designer state from it.")

            saved_state, meta_err = deserialize_state(designer_state_json)
            if meta_err:
                notes.append(meta_err + "; designer-only fields not restored")
            elif saved_state is not None:
                state, merge_warnings = merge_metadata_into_state(state, saved_state)
                notes.extend(merge_warnings)
                notes.append("Restored designer-only fields (subjects/hierarchy/relationships/notes/"
                             "per-element depth/weight/lock/hide/group) from designer_state_json.")

            if isinstance(high_level_description, str) and high_level_description:
                state["high_level_description"] = high_level_description

            palette_colors, palette_warnings = parse_palette_override(palette_json)
            notes.extend(palette_warnings)
            if palette_colors:
                state["palette"]["colors"] = palette_colors
                notes.append(f"Applied palette_json override ({len(palette_colors)} color(s)).")

            prompt = designer_state_to_prompt(state)
            prompt_json_str = json.dumps(prompt, ensure_ascii=False)

            validated_json, is_valid, validation_report, errors_json, warnings_json = IdeogramJSONValidator().validate(
                prompt_json_str, fix_key_order=True, strict_mode=strict_mode
            )

            state["validation"] = {
                "is_valid": is_valid,
                "errors": json.loads(errors_json),
                "warnings": json.loads(warnings_json),
                "report": validation_report,
            }
            designer_state_json_out = serialize_state(state)

            for note in notes:
                _warn(note)

            report = "\n".join(notes + [validation_report]) if notes else validation_report
            return (validated_json, validated_json, designer_state_json_out, is_valid, report)

        except Exception as e:
            # Never crash the graph: fall back to a fresh, valid empty state.
            fallback_state = new_designer_state()
            fallback_prompt = designer_state_to_prompt(fallback_state)
            fallback_json = json.dumps(fallback_prompt, ensure_ascii=False)
            report = f"Unexpected error in Visual Prompt Designer: {e}; returned an empty prompt"
            _warn(report)
            return (fallback_json, fallback_json, serialize_state(fallback_state), False, report)
