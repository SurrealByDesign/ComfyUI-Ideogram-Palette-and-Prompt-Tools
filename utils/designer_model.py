"""Designer state model and translation layer for the Ideogram Visual Prompt Designer.

This is Phase 1 (backend foundation) of the Visual Prompt Designer spec: the
layered architecture (Layer 1 Visual Model, Layer 2 Prompt Model, Layer 3
Serialization) with no custom canvas UI yet. The node built on top of this
module (nodes/visual_prompt_designer.py) exposes standard widgets and is fully
usable and testable today; the drag/resize canvas, scene-graph tree, and
relationship UI described in later spec sections require a custom ComfyUI
frontend extension and are deliberately out of scope here. See README.md's
"Ideogram Visual Prompt Designer" section for the phase boundary.

Layer 1 -- Visual Model ("designer state"): a plain dict carrying both the
fields that map onto the Ideogram prompt schema (description, style, palette,
composition elements) AND designer-only fields that schema has no place for
(subjects, hierarchy, relationships, notes, per-element depth/weight/lock/hide,
designer_version). Round-tripping through a saved image must not lose the
designer-only fields, even though they never appear in the Ideogram prompt
JSON itself -- that's why nodes/visual_prompt_designer.py also accepts a
separate `designer_state_json` input (typically sourced from a second PNG
metadata key via IdeogramMetadataReader) to restore them.

Layer 2 -- Prompt Model: the existing Ideogram 4 prompt schema, unchanged
(`high_level_description` / `style_description` / `compositional_deconstruction`,
per utils/schema_utils.TOP_LEVEL_KEY_ORDER).

Layer 3 -- Serialization: JSON conversion in both directions, in this module's
serialize_state / deserialize_state and the two translation functions below.
The node (UI) layer only ever calls these functions; it never builds or reads
prompt/designer JSON directly, per the spec's "never bind UI directly to JSON
structures" requirement.
"""

import json

try:
    from .schema_utils import STYLE_KEY_ORDER, TOP_LEVEL_KEY_ORDER, reorder_keys, validate_hex
except ImportError:
    from schema_utils import STYLE_KEY_ORDER, TOP_LEVEL_KEY_ORDER, reorder_keys, validate_hex

DESIGNER_SCHEMA_VERSION = 1
MAX_GLOBAL_COLORS = 16
MAX_ELEMENT_COLORS = 5
VALID_ELEMENT_TYPES = ("obj", "text")
VALID_DEPTH_LAYERS = ("foreground", "midground", "background", "overlay")
DEFAULT_DEPTH_LAYER = "midground"
TEXT_PLACEHOLDER = "[text required]"

# Designer-only style fields the spec's Style Editor section calls for. None of
# these exist in the Ideogram prompt schema, so they live only in designer
# state and only survive a round trip via designer_state_json / metadata.
_DESIGNER_ONLY_STYLE_FIELDS = (
    "mood",
    "rendering_style",
    "camera_language",
    "texture_language",
    "era",
    "genre",
    "visual_influences",
)


def new_designer_state():
    """An empty, valid designer state -- the starting point for "create from scratch"."""
    return {
        "designer_version": DESIGNER_SCHEMA_VERSION,
        "high_level_description": "",
        "subjects": [],
        "style": {
            "aesthetics": "",
            "lighting": "",
            **{field: ("" if field != "visual_influences" else []) for field in _DESIGNER_ONLY_STYLE_FIELDS},
        },
        "palette": {"colors": [], "locked": [], "weights": []},
        "composition": {"background": "", "elements": []},
        "hierarchy": {},
        "relationships": [],
        "notes": "",
        "validation": {"is_valid": None, "errors": [], "warnings": [], "report": ""},
    }


def _prompt_element_to_designer(element, position):
    """Translate one Ideogram prompt element into a designer composition element.

    No persistent "id" field is assigned here -- a position-derived id (e.g.
    "el_{position}") would be exactly as position-dependent as matching by
    index directly, so it would not actually solve the cross-reload identity
    problem; see merge_metadata_into_state's docstring for the real
    (position-based) matching limitation. A genuinely persistent id requires
    the future canvas to assign and preserve one across reorders, which
    doesn't exist yet.
    """
    etype = element.get("type") if element.get("type") in VALID_ELEMENT_TYPES else "obj"
    description = element.get("desc") if isinstance(element.get("desc"), str) else ""
    bbox = element.get("bbox")
    if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
        bbox = [0, 0, 500, 500]
    palette_affinity = element.get("color_palette")
    if not isinstance(palette_affinity, list):
        palette_affinity = []

    designer_element = {
        "type": etype,
        "name": description[:40] if description else f"Element {position}",
        "description": description,
        "bbox": list(bbox),
        "palette_affinity": list(palette_affinity),
        "depth_layer": DEFAULT_DEPTH_LAYER,
        "visual_weight": 1.0,
        "notes": "",
        "locked": False,
        "hidden": False,
        "group": None,
    }
    if etype == "text":
        text = element.get("text")
        designer_element["text"] = text if isinstance(text, str) else ""
    return designer_element


def prompt_to_designer_state(prompt):
    """Layer 2 -> Layer 1: reconstruct a designer state from an Ideogram prompt dict.

    Fields the Ideogram schema has no place for (subjects, hierarchy,
    relationships, notes, per-element depth/weight/lock/hide/group, the
    designer-only style fields) start empty/default -- restoring them is what
    `merge_metadata_into_state` is for. Malformed/missing sections degrade to
    sensible empty defaults rather than raising.
    """
    if not isinstance(prompt, dict):
        prompt = {}

    state = new_designer_state()
    hld = prompt.get("high_level_description")
    state["high_level_description"] = hld if isinstance(hld, str) else ""

    style = prompt.get("style_description")
    if isinstance(style, dict):
        state["style"]["aesthetics"] = style.get("aesthetics", "") if isinstance(style.get("aesthetics"), str) else ""
        state["style"]["lighting"] = style.get("lighting", "") if isinstance(style.get("lighting"), str) else ""
        colors = style.get("color_palette")
        if isinstance(colors, list):
            state["palette"]["colors"] = list(colors)

    comp = prompt.get("compositional_deconstruction")
    if isinstance(comp, dict):
        background = comp.get("background")
        state["composition"]["background"] = background if isinstance(background, str) else ""
        elements = comp.get("elements")
        if isinstance(elements, list):
            state["composition"]["elements"] = [
                _prompt_element_to_designer(el, idx)
                for idx, el in enumerate(elements, start=1)
                if isinstance(el, dict)
            ]

    return state


def _designer_element_to_prompt(element):
    """Translate one designer composition element back into an Ideogram prompt element."""
    etype = element.get("type") if element.get("type") in VALID_ELEMENT_TYPES else "obj"
    item = {"type": etype}
    if etype == "text":
        text = element.get("text")
        item["text"] = text if isinstance(text, str) and text.strip() else TEXT_PLACEHOLDER

    bbox = element.get("bbox")
    item["bbox"] = list(bbox) if isinstance(bbox, (list, tuple)) and len(bbox) == 4 else [0, 0, 500, 500]
    item["desc"] = element.get("description", "") if isinstance(element.get("description"), str) else ""

    palette = element.get("palette_affinity")
    if isinstance(palette, list):
        colors = [c.upper() for c in palette if validate_hex(c)][:MAX_ELEMENT_COLORS]
        if colors:
            item["color_palette"] = colors
    return item


def designer_state_to_prompt(state):
    """Layer 1 -> Layer 2: generate an Ideogram prompt dict from a designer state.

    Hidden elements are excluded from the generated prompt (they stay in the
    designer state, so un-hiding them later doesn't require recreating them).
    Designer-only fields (subjects, hierarchy, relationships, notes, the
    designer-only style fields) are intentionally not emitted -- the schema has
    no place for them.
    """
    if not isinstance(state, dict):
        state = new_designer_state()

    prompt = {}
    hld = state.get("high_level_description")
    if isinstance(hld, str) and hld:
        prompt["high_level_description"] = hld

    style = state.get("style") if isinstance(state.get("style"), dict) else {}
    colors = state.get("palette", {}).get("colors") if isinstance(state.get("palette"), dict) else []
    if not isinstance(colors, list):
        colors = []
    valid_colors = [c.upper() for c in colors if validate_hex(c)][:MAX_GLOBAL_COLORS]
    prompt["style_description"] = {
        "aesthetics": style.get("aesthetics", "") if isinstance(style.get("aesthetics"), str) else "",
        "lighting": style.get("lighting", "") if isinstance(style.get("lighting"), str) else "",
        "color_palette": valid_colors,
    }

    comp = state.get("composition") if isinstance(state.get("composition"), dict) else {}
    background = comp.get("background", "") if isinstance(comp.get("background"), str) else ""
    raw_elements = comp.get("elements") if isinstance(comp.get("elements"), list) else []
    elements_out = [
        _designer_element_to_prompt(el)
        for el in raw_elements
        if isinstance(el, dict) and not el.get("hidden")
    ]
    prompt["compositional_deconstruction"] = {"background": background, "elements": elements_out}

    prompt = reorder_keys(prompt, TOP_LEVEL_KEY_ORDER)
    prompt["style_description"] = reorder_keys(prompt["style_description"], STYLE_KEY_ORDER)
    return prompt


# Keys restored from saved metadata that the current element doesn't already
# get from the freshly loaded prompt. Most of these (depth_layer/visual_weight/
# notes/locked/hidden/group) have no prompt-schema source at all. "name" is the
# exception -- prompt_to_designer_state gives it a default derived from the
# loaded description, but a restored metadata value (e.g. a name a future
# canvas let the user type) takes precedence over that default.
_ELEMENT_DESIGNER_ONLY_KEYS = ("depth_layer", "visual_weight", "notes", "locked", "hidden", "group", "name")


def merge_metadata_into_state(state, metadata):
    """Restore designer-only fields from a previously saved designer state.

    `state` is typically fresh from `prompt_to_designer_state` (so its
    prompt-visible content -- description, palette, per-element type/desc/
    bbox/palette_affinity/text -- reflects the just-loaded prompt). `metadata`
    is a previously serialized designer state (e.g. read back from a second
    PNG metadata key via IdeogramMetadataReader). This layers metadata's
    designer-only fields on top without touching the freshly loaded content.

    Composition elements are matched by position (1st loaded element gets the
    1st saved element's designer-only fields, and so on) since this phase has
    no persistent per-element identity from a canvas yet -- documented
    limitation: reordering or adding/removing elements between saves can
    misalign restored depth/weight/notes/lock/hide/group.

    Returns (new_state, warnings): a new dict (does not mutate either input)
    plus a list of warning strings (e.g. an invalid restored `depth_layer`).
    """
    if not isinstance(metadata, dict):
        return state, []

    warnings = []
    result = dict(state)
    for key in ("subjects", "hierarchy", "relationships", "notes", "designer_version"):
        if key in metadata:
            result[key] = metadata[key]

    meta_style = metadata.get("style")
    if isinstance(meta_style, dict):
        merged_style = dict(result.get("style", {}))
        for field in _DESIGNER_ONLY_STYLE_FIELDS:
            if field in meta_style:
                merged_style[field] = meta_style[field]
        result["style"] = merged_style

    meta_palette = metadata.get("palette")
    if isinstance(meta_palette, dict):
        merged_palette = dict(result.get("palette", {}))
        for field in ("locked", "weights"):
            if field in meta_palette:
                merged_palette[field] = meta_palette[field]
        result["palette"] = merged_palette

    meta_comp = metadata.get("composition")
    if isinstance(meta_comp, dict):
        meta_elements = meta_comp.get("elements")
        current_elements = result.get("composition", {}).get("elements", [])
        if isinstance(meta_elements, list) and isinstance(current_elements, list):
            merged_elements = []
            for idx, element in enumerate(current_elements):
                merged = dict(element)
                if idx < len(meta_elements) and isinstance(meta_elements[idx], dict):
                    saved = meta_elements[idx]
                    for key in _ELEMENT_DESIGNER_ONLY_KEYS:
                        if key not in saved:
                            continue
                        if key == "depth_layer" and saved[key] not in VALID_DEPTH_LAYERS:
                            warnings.append(
                                f"element {idx + 1}: saved depth_layer {saved[key]!r} is not one of "
                                f"{VALID_DEPTH_LAYERS}; kept {merged.get('depth_layer', DEFAULT_DEPTH_LAYER)!r}"
                            )
                            continue
                        merged[key] = saved[key]
                merged_elements.append(merged)
            result["composition"] = dict(result["composition"])
            result["composition"]["elements"] = merged_elements

    return result, warnings


def serialize_state(state):
    """Layer 3: designer state dict -> JSON string (ensure_ascii=False, per house style)."""
    return json.dumps(state, ensure_ascii=False)


def deserialize_state(state_json):
    """Layer 3: JSON string -> (state_dict_or_None, error_or_None). Never raises."""
    text = (state_json or "").strip()
    if not text:
        return None, None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"designer_state_json was not valid JSON: {e}"
    if not isinstance(parsed, dict):
        return None, "designer_state_json was not a JSON object"
    return parsed, None


def parse_palette_override(palette_json):
    """Parse an optional JSON array of hex colors (e.g. from a palette extractor node).

    Returns (colors, warnings). Empty/blank input yields ([], []) -- meaning
    "no override", not "clear the palette". Malformed input yields ([],
    [warning]) so the caller can leave any existing palette untouched.
    """
    warnings = []
    text = (palette_json or "").strip()
    if not text:
        return [], warnings
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return [], ["palette_json was not valid JSON; palette override skipped"]
    if not isinstance(parsed, list):
        return [], ["palette_json was not a JSON array; palette override skipped"]

    colors = []
    dropped = 0
    for entry in parsed:
        if validate_hex(entry):
            colors.append(entry.upper())
        else:
            dropped += 1
    if dropped:
        warnings.append(f"dropped {dropped} invalid color(s) from palette_json")
    if len(colors) > MAX_GLOBAL_COLORS:
        warnings.append(f"palette_json had {len(colors)} colors; trimmed to {MAX_GLOBAL_COLORS}")
        colors = colors[:MAX_GLOBAL_COLORS]
    return colors, warnings
