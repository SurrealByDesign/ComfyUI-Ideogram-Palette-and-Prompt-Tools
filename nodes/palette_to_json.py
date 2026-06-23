"""IdeogramPaletteToGlobalJSON node.

Wraps a palette JSON string into a partial Ideogram 4 `style_description`
JSON fragment, with strict key ordering: aesthetics, lighting, color_palette.
"""

import json

MAX_GLOBAL_COLORS = 16
FALLBACK_PALETTE = ["#808080"]


def _parse_palette(palette_json: str):
    try:
        colors = json.loads(palette_json)
        if not isinstance(colors, list) or not all(isinstance(c, str) for c in colors):
            return list(FALLBACK_PALETTE)
        return colors[:MAX_GLOBAL_COLORS] if colors else list(FALLBACK_PALETTE)
    except (json.JSONDecodeError, TypeError):
        return list(FALLBACK_PALETTE)


class IdeogramPaletteToGlobalJSON:
    """Wraps an extracted palette into an Ideogram 4 `style_description` JSON fragment.

    Inputs:
        palette_json: palette JSON string, typically from IdeogramPaletteExtractor.
        aesthetics: optional aesthetics description text.
        lighting: optional lighting description text.

    Outputs:
        style_json: a `style_description` JSON object string with keys ordered
            aesthetics -> lighting -> color_palette, per Ideogram 4 schema rules.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "palette_json": ("STRING", {"forceInput": True}),
            },
            "optional": {
                "aesthetics": ("STRING", {"default": ""}),
                "lighting": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("style_json",)
    FUNCTION = "build"
    CATEGORY = "Ideogram/Palette"

    def build(self, palette_json, aesthetics="", lighting=""):
        try:
            colors = _parse_palette(palette_json)
            style_description = {
                "aesthetics": aesthetics or "",
                "lighting": lighting or "",
                "color_palette": colors,
            }
        except Exception:
            style_description = {
                "aesthetics": "",
                "lighting": "",
                "color_palette": list(FALLBACK_PALETTE),
            }

        return (json.dumps({"style_description": style_description}, ensure_ascii=False),)
