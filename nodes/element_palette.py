"""IdeogramElementPalette node.

Same extraction pipeline as IdeogramPaletteExtractor, clamped to a maximum
of 5 colors for use with Ideogram 4's per-element compositional_deconstruction
color_palette field.
"""

import json

import torch

try:
    from .palette_extractor import _tensor_to_pil, _extract_palette
    from ..utils.preview_utils import render_swatch_strip
except ImportError:
    from nodes.palette_extractor import _tensor_to_pil, _extract_palette
    from utils.preview_utils import render_swatch_strip

MAX_ELEMENT_COLORS = 5
FALLBACK_HEX = "#808080"


class IdeogramElementPalette:
    """Extracts a small color palette (max 5) for a single compositional element.

    Inputs:
        image: reference IMAGE for this element (e.g. a cropped product/object region).
        num_colors: target palette size (1-5, k-means cluster count).
        min_delta_e: minimum perceptual (LAB) distance required between kept colors.

    Outputs:
        element_palette_json: JSON array of max 5 hex strings, dominant color first.
        palette_preview: horizontal swatch strip IMAGE of the extracted colors.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "num_colors": ("INT", {"default": 5, "min": 1, "max": MAX_ELEMENT_COLORS}),
                "min_delta_e": ("FLOAT", {"default": 10.0, "min": 0.0, "max": 100.0, "step": 0.5}),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("element_palette_json", "palette_preview")
    FUNCTION = "extract"
    CATEGORY = "Ideogram/Palette"

    def extract(self, image, num_colors, min_delta_e):
        try:
            pil_image = _tensor_to_pil(image)
            num_colors = min(num_colors, MAX_ELEMENT_COLORS)
            hex_colors = _extract_palette(pil_image, num_colors, min_delta_e)
            hex_colors = hex_colors[:MAX_ELEMENT_COLORS]
            if not hex_colors:
                hex_colors = [FALLBACK_HEX]
        except Exception:
            hex_colors = [FALLBACK_HEX]

        element_palette_json = json.dumps(hex_colors)
        swatch = render_swatch_strip(hex_colors)
        preview_tensor = torch.from_numpy(swatch).unsqueeze(0)

        return (element_palette_json, preview_tensor)
