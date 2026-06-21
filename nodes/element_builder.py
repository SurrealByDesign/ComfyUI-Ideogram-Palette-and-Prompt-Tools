"""IdeogramElementBuilder and IdeogramElementCollector nodes.

Two tightly coupled nodes that assemble Ideogram 4 `compositional_deconstruction`
elements:

  - IdeogramElementBuilder turns a bounding box + description + type + optional
    per-element palette into a single valid element JSON object.
  - IdeogramElementCollector gathers up to eight of those into a complete
    `compositional_deconstruction` block (with a background description),
    skipping empty inputs and warning when text element boxes overlap.

Wiring several builders in parallel into one collector lets each region of a
generation carry its own spatial placement and its own reference palette
(extracted from a different source image), all assembled into one valid prompt.

bbox convention: element bounding boxes are emitted as `[ymin, xmin, ymax, xmax]`,
integers in 0-1000, matching the official Ideogram 4 element schema. (Note this
differs from the inline `bbox=[x_min,y_min,x_max,y_max]` text convention parsed by
json_validator.py; that validator only range-checks coordinates, so the ordering
chosen here is the one the structured element schema specifies.)

No torch dependency — pure stdlib plus the package's hex validator.
"""

import json
import sys

try:
    from ..utils.schema_utils import validate_hex
except ImportError:
    from utils.schema_utils import validate_hex

VALID_TYPES = ["obj", "text"]
BBOX_MIN = 0
BBOX_MAX = 1000
MAX_ELEMENT_COLORS = 5
TEXT_PLACEHOLDER = "[text required]"


def _warn(message):
    """Surface a non-fatal warning to the console without breaking the graph."""
    print(f"[IdeogramElement] {message}", file=sys.stderr)


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _parse_palette(palette_str):
    """Parse an optional JSON palette array string.

    Returns (colors, warnings): up to MAX_ELEMENT_COLORS uppercase #RRGGBB strings,
    plus any warning messages. An empty/blank input yields ([], []) (no palette,
    no warning). Malformed input yields ([], [warning]) rather than raising.
    """
    warnings = []
    text = (palette_str or "").strip()
    if not text:
        return [], warnings

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return [], ["color_palette was not valid JSON; omitted"]
    if not isinstance(parsed, list):
        return [], ["color_palette was not a JSON array; omitted"]

    colors = []
    dropped = 0
    for entry in parsed:
        if validate_hex(entry):
            colors.append(entry.upper())
        else:
            dropped += 1
    if dropped:
        warnings.append(f"dropped {dropped} invalid color(s) from color_palette")
    if len(colors) > MAX_ELEMENT_COLORS:
        warnings.append(f"color_palette had {len(colors)} colors; trimmed to {MAX_ELEMENT_COLORS}")
        colors = colors[:MAX_ELEMENT_COLORS]
    return colors, warnings


class IdeogramElementBuilder:
    """Builds one Ideogram 4 `compositional_deconstruction` element JSON object.

    Inputs:
        element_type: "obj" or "text".
        description: the element's `desc` field.
        bbox_ymin / bbox_xmin / bbox_ymax / bbox_xmax: bounding box edges
            (integers 0-1000); emitted in the order [ymin, xmin, ymax, xmax].
        color_palette: optional JSON array string of hex colors (e.g. from
            IdeogramElementPalette); empty means no palette on this element.
        text_content: literal text to render; used only when element_type is "text".

    Outputs:
        element_json: a single valid element JSON object as a string.
        bbox_preview: a human-readable summary plus any validation warnings.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "element_type": (VALID_TYPES, {"default": "obj"}),
                "description": ("STRING", {"default": "", "multiline": True}),
                "bbox_ymin": ("INT", {"default": 0, "min": BBOX_MIN, "max": BBOX_MAX}),
                "bbox_xmin": ("INT", {"default": 0, "min": BBOX_MIN, "max": BBOX_MAX}),
                "bbox_ymax": ("INT", {"default": 500, "min": BBOX_MIN, "max": BBOX_MAX}),
                "bbox_xmax": ("INT", {"default": 500, "min": BBOX_MIN, "max": BBOX_MAX}),
            },
            "optional": {
                "color_palette": ("STRING", {"default": ""}),
                "text_content": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("element_json", "bbox_preview")
    FUNCTION = "build"
    CATEGORY = "Ideogram/Palette"

    def build(self, element_type, description, bbox_ymin, bbox_xmin, bbox_ymax, bbox_xmax,
              color_palette="", text_content=""):
        warnings = []
        try:
            etype = element_type if element_type in VALID_TYPES else "obj"
            if etype != element_type:
                warnings.append(f"unknown element_type {element_type!r}; defaulted to 'obj'")

            # 1. Clamp each bbox edge to the 0-1000 range.
            edges = {"ymin": bbox_ymin, "xmin": bbox_xmin, "ymax": bbox_ymax, "xmax": bbox_xmax}
            clamped = {}
            for name, raw in edges.items():
                try:
                    value = int(raw)
                except (TypeError, ValueError):
                    value = 0
                    warnings.append(f"{name} was not an integer; defaulted to 0")
                limited = _clamp(value, BBOX_MIN, BBOX_MAX)
                if limited != value:
                    warnings.append(f"{name} {value} out of range; clamped to {limited}")
                clamped[name] = limited
            ymin, xmin, ymax, xmax = clamped["ymin"], clamped["xmin"], clamped["ymax"], clamped["xmax"]

            # 2. Correct inverted bounds by swapping.
            if ymax <= ymin:
                ymin, ymax = ymax, ymin
                warnings.append("ymax was not greater than ymin; values swapped")
            if xmax <= xmin:
                xmin, xmax = xmax, xmin
                warnings.append("xmax was not greater than xmin; values swapped")

            # 3-9. Assemble the element with the schema's exact key order:
            #   type -> (text) -> bbox -> desc -> (color_palette).
            element = {"type": etype}
            if etype == "text":
                content = text_content if isinstance(text_content, str) else ""
                if not content.strip():
                    content = TEXT_PLACEHOLDER
                    warnings.append("element_type is 'text' but text_content was empty; using placeholder")
                element["text"] = content

            element["bbox"] = [ymin, xmin, ymax, xmax]
            element["desc"] = description if isinstance(description, str) else ""

            colors, palette_warnings = _parse_palette(color_palette)
            warnings.extend(palette_warnings)
            if colors:
                element["color_palette"] = colors

            element_json = json.dumps(element, ensure_ascii=False)
        except Exception as e:
            # Never crash the graph; emit an empty element (the collector skips it).
            return ("", f"Error building element: {e}")

        preview = f"{etype} @ [y:{ymin}-{ymax}, x:{xmin}-{xmax}]"
        if warnings:
            for message in warnings:
                _warn(message)
            preview += "  |  " + "; ".join(warnings)
        return (element_json, preview)


def _boxes_overlap(box_a, box_b):
    """True if two [ymin, xmin, ymax, xmax] boxes intersect."""
    ay_min, ax_min, ay_max, ax_max = box_a
    by_min, bx_min, by_max, bx_max = box_b
    return ay_min < by_max and ay_max > by_min and ax_min < bx_max and ax_max > bx_min


def _text_label(element, position):
    """A short human-readable label for a text element, by position and content."""
    text = element.get("text")
    if isinstance(text, str) and text.strip():
        snippet = text.strip()
        if len(snippet) > 20:
            snippet = snippet[:20] + "..."
        return f'element {position} ("{snippet}")'
    return f"element {position}"


def _detect_text_overlaps(elements):
    """Return a warning string listing overlapping text-element box pairs, or ""."""
    text_boxes = []
    for position, element in enumerate(elements, start=1):
        if element.get("type") != "text":
            continue
        bbox = element.get("bbox")
        if (isinstance(bbox, (list, tuple)) and len(bbox) == 4
                and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in bbox)):
            text_boxes.append((position, element, list(bbox)))

    overlaps = []
    for i in range(len(text_boxes)):
        for j in range(i + 1, len(text_boxes)):
            pos_a, el_a, box_a = text_boxes[i]
            pos_b, el_b, box_b = text_boxes[j]
            if _boxes_overlap(box_a, box_b):
                overlaps.append(f"{_text_label(el_a, pos_a)} overlaps {_text_label(el_b, pos_b)}")

    if not overlaps:
        return ""
    return "Overlapping text elements: " + "; ".join(overlaps)


class IdeogramElementCollector:
    """Assembles up to eight element JSON strings into a `compositional_deconstruction` block.

    Inputs:
        background: description of the background scene (required by the schema).
        element_1 .. element_8: element JSON strings from IdeogramElementBuilder
            (element_1 required, the rest optional); empty inputs are skipped.

    Outputs:
        compositional_json: the complete `compositional_deconstruction` block string.
        element_count: how many elements were successfully parsed and included.
        overlap_warning: a message listing overlapping text element boxes, or "".

    Malformed element inputs are skipped (with a console warning) rather than
    crashing, so a valid block is always produced.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "background": ("STRING", {"default": "", "multiline": True}),
                "element_1": ("STRING", {"forceInput": True}),
            },
            "optional": {
                "element_2": ("STRING", {"forceInput": True}),
                "element_3": ("STRING", {"forceInput": True}),
                "element_4": ("STRING", {"forceInput": True}),
                "element_5": ("STRING", {"forceInput": True}),
                "element_6": ("STRING", {"forceInput": True}),
                "element_7": ("STRING", {"forceInput": True}),
                "element_8": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("compositional_json", "element_count", "overlap_warning")
    FUNCTION = "collect"
    CATEGORY = "Ideogram/Palette"

    def collect(self, background, element_1="", element_2="", element_3="", element_4="",
                element_5="", element_6="", element_7="", element_8=""):
        raw_inputs = [element_1, element_2, element_3, element_4,
                      element_5, element_6, element_7, element_8]
        elements = []
        try:
            for idx, raw in enumerate(raw_inputs, start=1):
                if not raw or not str(raw).strip():
                    continue
                try:
                    parsed = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    _warn(f"element_{idx}: not valid JSON; skipped")
                    continue
                if not isinstance(parsed, dict):
                    _warn(f"element_{idx}: not a JSON object; skipped")
                    continue
                if parsed.get("type") not in VALID_TYPES:
                    _warn(f"element_{idx}: missing or invalid 'type'; skipped")
                    continue
                if "bbox" not in parsed or "desc" not in parsed:
                    _warn(f"element_{idx}: missing required field (bbox/desc); skipped")
                    continue
                elements.append(parsed)

            overlap_warning = _detect_text_overlaps(elements)
            block = {
                "background": background if isinstance(background, str) else "",
                "elements": elements,
            }
            compositional_json = json.dumps(block, ensure_ascii=False)
        except Exception as e:
            # Never crash; emit a valid-but-empty block.
            _warn(f"collector error: {e}")
            empty = json.dumps(
                {"background": background if isinstance(background, str) else "", "elements": []},
                ensure_ascii=False,
            )
            return (empty, 0, "")

        return (compositional_json, len(elements), overlap_warning)
