"""IdeogramPaletteOverride node.

Manually adds, removes, or replaces individual colors in an extracted
palette before final JSON is built, and re-renders the swatch preview.
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


def _parse_palette(palette_json: str):
    try:
        colors = json.loads(palette_json)
        if not isinstance(colors, list) or not all(isinstance(c, str) for c in colors):
            return list(FALLBACK_PALETTE)
        return colors
    except (json.JSONDecodeError, TypeError):
        return list(FALLBACK_PALETTE)


def _parse_indices(indices_str: str):
    indices = set()
    for part in (indices_str or "").split(","):
        part = part.strip()
        if part.isdigit():
            indices.add(int(part))
    return indices


def _parse_add_colors(add_colors_str: str):
    valid = []
    for part in (add_colors_str or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            hex_to_rgb(part)
            valid.append(part if part.startswith("#") else f"#{part}")
        except ValueError:
            continue
    return valid


class IdeogramPaletteOverride:
    """Manually edits an extracted palette: remove indices, append colors, clamp size.

    Inputs:
        palette_json: palette JSON string from IdeogramPaletteExtractor.
        add_colors: comma-separated hex values to append, e.g. "#FFFFFF,#000000".
        remove_index: comma-separated indices to remove, e.g. "0,3".
        max_colors: clamp final output to this many colors.

    Outputs:
        palette_json: modified palette JSON string.
        palette_preview: updated swatch strip IMAGE.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "palette_json": ("STRING", {"forceInput": True}),
                "max_colors": ("INT", {"default": 16, "min": 1, "max": 16}),
            },
            "optional": {
                "add_colors": ("STRING", {"default": ""}),
                "remove_index": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("palette_json", "palette_preview")
    FUNCTION = "override"
    CATEGORY = "Ideogram/Palette"

    def override(self, palette_json, max_colors, add_colors="", remove_index=""):
        try:
            colors = _parse_palette(palette_json)
            remove_set = _parse_indices(remove_index)
            colors = [c for i, c in enumerate(colors) if i not in remove_set]
            colors.extend(_parse_add_colors(add_colors))

            if not colors:
                colors = list(FALLBACK_PALETTE)

            colors = colors[:max_colors]
        except Exception:
            colors = list(FALLBACK_PALETTE)

        palette_json_out = json.dumps(colors)
        swatch = render_swatch_strip(colors)
        preview_tensor = torch.from_numpy(swatch).unsqueeze(0)

        return (palette_json_out, preview_tensor)
