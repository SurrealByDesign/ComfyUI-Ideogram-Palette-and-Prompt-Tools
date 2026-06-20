"""Schema helpers for Ideogram 4 prompt JSON.

Key-ordering constants, a hex-color validator, and a key-reordering helper used
by the JSON validator node. No torch dependency — pure stdlib.
"""

import re

# Ideogram 4 was trained on strictly ordered JSON. These are the canonical orders.
TOP_LEVEL_KEY_ORDER = ["high_level_description", "style_description", "compositional_deconstruction"]
STYLE_KEY_ORDER = ["aesthetics", "lighting", "color_palette"]

# Matches a #RRGGBB hex color (case-insensitive).
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def reorder_keys(d, order):
    """Return a new dict with keys from `order` first (in that order), followed by
    any remaining keys in their original relative order. Non-dict input is
    returned unchanged.
    """
    if not isinstance(d, dict):
        return d
    result = {}
    for key in order:
        if key in d:
            result[key] = d[key]
    for key, value in d.items():
        if key not in result:
            result[key] = value
    return result


def validate_hex(color_string):
    """Return True if color_string is a valid #RRGGBB hex color, else False."""
    return isinstance(color_string, str) and bool(HEX_COLOR_RE.match(color_string))
