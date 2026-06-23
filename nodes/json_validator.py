"""IdeogramJSONValidator node.

Validates an Ideogram 4 prompt JSON string against the schema's structural rules
(key ordering, palette sizes, hex validity, bbox bounds) and optionally corrects
key ordering. It never edits content values — only reorders keys and reports.
"""

import json
import re

try:
    from ..utils.schema_utils import (
        TOP_LEVEL_KEY_ORDER,
        STYLE_KEY_ORDER,
        reorder_keys,
        validate_hex,
    )
except ImportError:
    from utils.schema_utils import (
        TOP_LEVEL_KEY_ORDER,
        STYLE_KEY_ORDER,
        reorder_keys,
        validate_hex,
    )

MAX_GLOBAL_COLORS = 16
MAX_ELEMENT_COLORS = 5
BBOX_MIN = 0
BBOX_MAX = 1000

_BBOX_RE = re.compile(r"bbox\s*=\s*\[([^\]]*)\]", re.IGNORECASE)


def _extract_bbox_coords(element):
    """Collect numeric bbox coordinates from an element.

    An element's bounding box may be expressed in one of two equivalent forms:
      - a structured `bbox` field: a 4-item list `[ymin, xmin, ymax, xmax]`
        (the order the official Ideogram 4 element schema specifies).
      - an inline token embedded in the free-text `desc` field, written as
        `bbox=[ymin, xmin, ymax, xmax]` (e.g.
        `desc="a red mug bbox=[100,200,300,400]"`).

    Both forms are accepted because Ideogram 4 prompts are sometimes authored by
    hand, where the inline `desc` form is faster to type than adding a separate
    structured field. This function checks whichever form a given element
    actually uses, so hand-written and machine-generated prompts validate the
    same way. The coordinate order does not affect this check itself — it only
    range-tests each coordinate against 0-1000 regardless of position.
    """
    coords = []
    bbox_field = element.get("bbox")
    if isinstance(bbox_field, (list, tuple)):
        for c in bbox_field:
            if isinstance(c, (int, float)) and not isinstance(c, bool):
                coords.append(float(c))

    desc = element.get("desc")
    if isinstance(desc, str):
        for match in _BBOX_RE.finditer(desc):
            for part in match.group(1).split(","):
                part = part.strip()
                try:
                    coords.append(float(part))
                except ValueError:
                    continue
    return coords


def _build_report(is_valid, errors, warnings):
    lines = [f"Validation: {'PASS' if is_valid else 'FAIL'}"]
    if errors:
        lines.append(f"Errors ({len(errors)}):")
        lines.extend(f"  - {e}" for e in errors)
    else:
        lines.append("Errors: none")
    if warnings:
        lines.append(f"Warnings ({len(warnings)}):")
        lines.extend(f"  - {w}" for w in warnings)
    else:
        lines.append("Warnings: none")
    return "\n".join(lines)


class IdeogramJSONValidator:
    """Validates (and optionally key-order-corrects) an Ideogram 4 prompt JSON string.

    Inputs:
        prompt_json: the Ideogram 4 JSON prompt string.
        fix_key_order: if True, reorder top-level and style_description keys to the
            canonical schema order (content values are never changed).
        strict_mode: if True, warnings also fail validation (is_valid=False).

    Outputs:
        prompt_json: the validated and optionally key-reordered JSON string.
        is_valid: False if any errors (or, in strict_mode, any warnings) were found.
        report: a human-readable validation summary (same content as before --
            unchanged for backward compatibility with anything parsing it).
        errors_json: a JSON array of error message strings (possibly empty),
            for consumers that need structured data instead of re-parsing
            `report`'s prose.
        warnings_json: a JSON array of warning message strings (possibly empty).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_json": ("STRING", {"forceInput": True}),
                "fix_key_order": ("BOOLEAN", {"default": True}),
                "strict_mode": ("BOOLEAN", {"default": False}),
            }
        }

    # errors_json/warnings_json were added after prompt_json/is_valid/report
    # shipped in v1.0.0 -- appended at the end, not inserted, so existing
    # saved workflows' connections to the original three outputs (which
    # ComfyUI resolves by index) keep working unchanged.
    RETURN_TYPES = ("STRING", "BOOLEAN", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompt_json", "is_valid", "report", "errors_json", "warnings_json")
    FUNCTION = "validate"
    CATEGORY = "Ideogram/Palette"

    def validate(self, prompt_json, fix_key_order=True, strict_mode=False):
        errors = []
        warnings = []
        try:
            # 1. Parse — bail out cleanly on invalid JSON.
            try:
                data = json.loads(prompt_json)
            except (json.JSONDecodeError, TypeError) as e:
                errors = [f"invalid JSON: {e}"]
                report = _build_report(False, errors, [])
                return (prompt_json, False, report, json.dumps(errors, ensure_ascii=False), "[]")

            if not isinstance(data, dict):
                errors = ["top-level JSON is not an object"]
                report = _build_report(False, errors, [])
                return (prompt_json, False, report, json.dumps(errors, ensure_ascii=False), "[]")

            # 2. Presence of the three top-level keys (missing -> warning).
            for key in TOP_LEVEL_KEY_ORDER:
                if key not in data:
                    warnings.append(f"missing top-level key '{key}'")

            # 3-4. Reorder keys (top level + style_description) without touching values.
            if fix_key_order:
                data = reorder_keys(data, TOP_LEVEL_KEY_ORDER)
                if isinstance(data.get("style_description"), dict):
                    data["style_description"] = reorder_keys(data["style_description"], STYLE_KEY_ORDER)

            # 5-6. Global color_palette: hex validity (warn) + size cap (error).
            style = data.get("style_description")
            if isinstance(style, dict):
                cp = style.get("color_palette")
                if isinstance(cp, list):
                    for c in cp:
                        if not validate_hex(c):
                            warnings.append(f"malformed hex in style_description.color_palette: {c!r}")
                    if len(cp) > MAX_GLOBAL_COLORS:
                        errors.append(
                            f"style_description.color_palette has {len(cp)} colors (max {MAX_GLOBAL_COLORS})"
                        )

            # 7-8. Per-element palettes (size cap) + bounding box bounds.
            comp = data.get("compositional_deconstruction")
            if isinstance(comp, dict):
                elements = comp.get("elements")
                if isinstance(elements, list):
                    for i, element in enumerate(elements):
                        if not isinstance(element, dict):
                            continue
                        ecp = element.get("color_palette")
                        if isinstance(ecp, list):
                            for c in ecp:
                                if not validate_hex(c):
                                    warnings.append(f"malformed hex in element {i} color_palette: {c!r}")
                            if len(ecp) > MAX_ELEMENT_COLORS:
                                errors.append(
                                    f"element {i} color_palette has {len(ecp)} colors (max {MAX_ELEMENT_COLORS})"
                                )
                        for coord in _extract_bbox_coords(element):
                            if coord < BBOX_MIN or coord > BBOX_MAX:
                                errors.append(
                                    f"element {i} bbox coordinate {coord:g} out of range [{BBOX_MIN}-{BBOX_MAX}]"
                                )

            # 9. Decide validity. Errors always fail; strict_mode also fails on warnings.
            is_valid = len(errors) == 0 and (not strict_mode or len(warnings) == 0)

            # 10. Output: reordered JSON when fixing, otherwise the untouched original.
            out_json = json.dumps(data, ensure_ascii=False) if fix_key_order else prompt_json
            report = _build_report(is_valid, errors, warnings)
            return (out_json, is_valid, report, json.dumps(errors, ensure_ascii=False), json.dumps(warnings, ensure_ascii=False))

        except Exception as e:
            # 11. Never crash.
            errors = [f"unexpected error: {e}"]
            report = _build_report(False, errors, [])
            return (prompt_json, False, report, json.dumps(errors), "[]")
