"""IdeogramPaletteBlend node.

Blends two palette JSON strings into one, useful for mixing a content-reference
palette with a style-reference palette. `blend_ratio` controls the proportion:
0.0 = entirely palette A, 1.0 = entirely palette B. Colors are drawn from each
palette in dominance order, interleaved, with exact-duplicate hexes removed and
the result clamped to `max_colors`.
"""

import json

import torch

try:
    from ..utils.color_utils import hex_to_rgb
    from ..utils.preview_utils import render_swatch_strip
except ImportError:
    from utils.color_utils import hex_to_rgb
    from utils.preview_utils import render_swatch_strip

FALLBACK_PALETTE = ["#808080"]


def _parse_hex_list(palette_json: str):
    """Parse a JSON array string into a list of valid uppercase hex strings.

    Invalid entries are dropped; an unparseable input yields an empty list.
    """
    try:
        colors = json.loads(palette_json)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(colors, list):
        return []
    out = []
    for c in colors:
        if not isinstance(c, str):
            continue
        try:
            hex_to_rgb(c)
        except (ValueError, TypeError):
            continue
        out.append(c.upper() if c.startswith("#") else f"#{c.upper()}")
    return out


def _blend_palettes(a, b, blend_ratio, max_colors):
    """Blend two dominance-ordered hex lists by proportion.

    n_b colors are taken from B and (max_colors - n_b) from A, where n_b scales
    with blend_ratio. Picks are interleaved by rank so the most dominant of each
    appears early, exact-duplicate hexes are removed, and the result is capped at
    max_colors. The ratio governs the split: 0.0 yields only A, 1.0 only B. If a
    palette is shorter than its allocation the result simply has fewer colors
    (the ratio is honored over filling max_colors), consistent with how the
    extractor returns fewer colors than requested for simple images.
    """
    ratio = min(1.0, max(0.0, blend_ratio))
    max_colors = max(1, int(max_colors))

    n_b = int(ratio * max_colors + 0.5)
    n_a = max_colors - n_b

    pick_a, pick_b = a[:n_a], b[:n_b]

    # Interleave the primary picks by rank so the most dominant of each appear early.
    primary = []
    for i in range(max(len(pick_a), len(pick_b))):
        if i < len(pick_a):
            primary.append(pick_a[i])
        if i < len(pick_b):
            primary.append(pick_b[i])

    seen, out = set(), []
    for c in primary:
        if c not in seen:
            seen.add(c)
            out.append(c)
        if len(out) >= max_colors:
            break
    return out


class IdeogramPaletteBlend:
    """Blends two palettes into one, weighted by blend_ratio.

    Inputs:
        palette_a: first palette JSON string (e.g. a content reference).
        palette_b: second palette JSON string (e.g. a style reference).
        blend_ratio: 0.0 = all A, 1.0 = all B; values between mix proportionally.
        max_colors: clamp the blended result to this many colors.

    Outputs:
        palette_json: the blended palette as a JSON hex array string.
        palette_preview: swatch strip IMAGE of the blended palette.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "palette_a": ("STRING", {"forceInput": True}),
                "palette_b": ("STRING", {"forceInput": True}),
                "blend_ratio": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05}),
                "max_colors": ("INT", {"default": 8, "min": 1, "max": 16}),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("palette_json", "palette_preview")
    FUNCTION = "blend"
    CATEGORY = "Ideogram/Palette"

    def blend(self, palette_a, palette_b, blend_ratio=0.5, max_colors=8):
        try:
            a = _parse_hex_list(palette_a)
            b = _parse_hex_list(palette_b)
            colors = _blend_palettes(a, b, blend_ratio, max_colors)
            if not colors:
                colors = list(FALLBACK_PALETTE)
        except Exception:
            colors = list(FALLBACK_PALETTE)

        palette_json = json.dumps(colors)
        swatch = render_swatch_strip(colors)
        preview_tensor = torch.from_numpy(swatch).unsqueeze(0)

        return (palette_json, preview_tensor)
