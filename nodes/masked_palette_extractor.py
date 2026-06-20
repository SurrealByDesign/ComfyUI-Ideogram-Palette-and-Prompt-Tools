"""IdeogramMaskedPaletteExtractor node.

Extracts a color palette from only the masked region of an image, so you can get
the palette of a specific subject or area rather than the whole frame. Pairs
naturally with IdeogramElementPalette to build region-accurate per-element
palettes. Same k-means + Delta-E pipeline as the full extractor, restricted to
the selected pixels.
"""

import json

import numpy as np
import torch
from PIL import Image

try:
    from ..utils.extract import palette_from_pixels
    from ..utils.preview_utils import render_swatch_strip
except ImportError:
    from utils.extract import palette_from_pixels
    from utils.preview_utils import render_swatch_strip

WORK_DIM = 256
FALLBACK_HEX = "#808080"


def _masked_pixels(image, mask, threshold):
    """Return an (N, 3) array of the image's RGB pixels (0-255) where mask >= threshold.

    Image and mask are resized to a common working resolution for speed; the mask
    is matched to the image regardless of its incoming size.
    """
    img = image[0].cpu().numpy()
    if img.ndim == 3 and img.shape[2] > 3:
        img = img[:, :, :3]

    m = mask
    if hasattr(m, "dim") and m.dim() == 3:
        m = m[0]
    m = m.cpu().numpy()

    img_pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), mode="RGB").resize((WORK_DIM, WORK_DIM))
    mask_pil = Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).resize((WORK_DIM, WORK_DIM))

    img_small = np.asarray(img_pil, dtype=np.float64)
    mask_small = np.asarray(mask_pil, dtype=np.float32) / 255.0

    selection = mask_small >= threshold
    return img_small[selection]


class IdeogramMaskedPaletteExtractor:
    """Extracts a palette from only the masked region of an image.

    Inputs:
        image: the reference IMAGE.
        mask: a MASK selecting the region to extract from (values >= mask_threshold).
        num_colors: target palette size (k-means cluster count).
        min_delta_e: minimum perceptual (LAB) distance required between kept colors.
        mask_threshold: pixels with mask value at or above this are included.

    Outputs:
        palette_json: JSON array of hex strings, dominant color first.
        palette_preview: horizontal swatch strip IMAGE of the extracted colors.
        color_count: number of colors returned after deduplication.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "mask": ("MASK",),
                "num_colors": ("INT", {"default": 8, "min": 2, "max": 16}),
                "min_delta_e": ("FLOAT", {"default": 10.0, "min": 0.0, "max": 100.0, "step": 0.5}),
                "mask_threshold": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05}),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE", "INT")
    RETURN_NAMES = ("palette_json", "palette_preview", "color_count")
    FUNCTION = "extract"
    CATEGORY = "Ideogram/Palette"

    def extract(self, image, mask, num_colors, min_delta_e, mask_threshold=0.5):
        try:
            pixels = _masked_pixels(image, mask, mask_threshold)
            hex_colors = palette_from_pixels(pixels, num_colors, min_delta_e)
            if not hex_colors:
                # Empty / below-threshold mask selects nothing — fall back gracefully.
                hex_colors = [FALLBACK_HEX]
        except Exception:
            hex_colors = [FALLBACK_HEX]

        palette_json = json.dumps(hex_colors)
        swatch = render_swatch_strip(hex_colors)
        preview_tensor = torch.from_numpy(swatch).unsqueeze(0)

        return (palette_json, preview_tensor, len(hex_colors))
