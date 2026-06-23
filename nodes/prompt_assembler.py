"""IdeogramPromptAssembler node.

Merges a partial Ideogram 4 JSON fragment into a base prompt JSON — the missing
link between palette extraction and a full generation prompt. The typical use is
overlaying the `style_description` fragment from IdeogramPaletteToGlobalJSON
(which carries the extracted color_palette) onto a complete prompt JSON produced
elsewhere, without disturbing the prompt's other content.

The merge is a field-by-field deep merge for nested objects, so injecting a
palette replaces only `style_description.color_palette` and leaves sibling fields
like `aesthetics`, `lighting`, `photo`, and `medium` untouched. A base of "{}"
lets the node assemble a prompt from scratch.
"""

import json

try:
    from ..utils.schema_utils import (
        TOP_LEVEL_KEY_ORDER,
        STYLE_KEY_ORDER,
        reorder_keys,
    )
except ImportError:
    from utils.schema_utils import (
        TOP_LEVEL_KEY_ORDER,
        STYLE_KEY_ORDER,
        reorder_keys,
    )


def _deep_merge(base, overlay):
    """Recursively merge overlay into base. Nested dicts merge field-by-field;
    lists and scalars overwrite. Returns a new dict (inputs are not mutated)."""
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _parse_object(json_str):
    """Parse a JSON string expected to be an object. Returns (dict_or_None, error_or_None)."""
    try:
        parsed = json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        return None, str(e)
    if not isinstance(parsed, dict):
        return None, "not a JSON object"
    return parsed, None


class IdeogramPromptAssembler:
    """Merges an Ideogram 4 JSON fragment into a base prompt JSON.

    Inputs:
        base_json: the base prompt JSON to merge into ("{}" to build from scratch).
        merge_json: a fragment to overlay, e.g. a `style_description` fragment from
            IdeogramPaletteToGlobalJSON.
        fix_key_order: if True, reorder the result's top-level and
            style_description keys to the canonical Ideogram 4 order.

    Outputs:
        prompt_json: the merged JSON string.
        report: a human-readable summary of what was merged.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_json": ("STRING", {"default": "{}", "multiline": True}),
                "merge_json": ("STRING", {"default": "", "multiline": True}),
                "fix_key_order": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt_json", "report")
    FUNCTION = "assemble"
    CATEGORY = "Ideogram/Palette"

    def assemble(self, base_json, merge_json, fix_key_order=True):
        try:
            notes = []
            base, base_err = _parse_object(base_json)
            if base is None:
                base = {}
                notes.append(f"base_json invalid ({base_err}); treated as empty object")

            overlay, overlay_err = _parse_object(merge_json)
            if overlay is None:
                # Nothing valid to merge: return the base unchanged.
                notes.append(f"merge_json invalid ({overlay_err}); base returned unchanged")
                out_json = json.dumps(base, ensure_ascii=False) if base_err is None and base else base_json
                report = "Merged keys: none\n" + "\n".join(notes)
                return (out_json, report)

            added = [k for k in overlay if k not in base]
            updated = [k for k in overlay if k in base]

            result = _deep_merge(base, overlay)

            if fix_key_order:
                result = reorder_keys(result, TOP_LEVEL_KEY_ORDER)
                if isinstance(result.get("style_description"), dict):
                    result["style_description"] = reorder_keys(result["style_description"], STYLE_KEY_ORDER)

            lines = [f"Merged keys: {', '.join(overlay.keys()) if overlay else 'none'}"]
            if added:
                lines.append(f"  added: {', '.join(added)}")
            if updated:
                lines.append(f"  updated: {', '.join(updated)}")
            lines.extend(notes)
            return (json.dumps(result, ensure_ascii=False), "\n".join(lines))

        except Exception as e:
            # Never crash: return the base untouched.
            return (base_json, f"Error during merge: {e}")
