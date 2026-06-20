"""IdeogramMetadataReader node.

Reads an Ideogram 4 JSON prompt back out of a PNG tEXt metadata chunk.

IMPORTANT LIMITATION: ComfyUI's IMAGE type is a bare pixel tensor that carries
NO metadata. Converting such a tensor to PIL produces an image with an empty
.info dict, so this node can only recover an embedded prompt when the upstream
image somehow still carries it. A standard LoadImage -> IMAGE path strips tEXt
chunks, so to read metadata from a file on disk you generally need to open the
PNG file directly (by path) rather than route it through an IMAGE tensor. This
node is provided for completeness and for graphs where a metadata-carrying PIL
is available; see the README note on metadata persistence.
"""

import numpy as np
from PIL import Image


def _tensor_to_pil(image_tensor) -> Image.Image:
    """Convert a ComfyUI IMAGE tensor (B, H, W, C), float 0-1, to a PIL RGB image (first frame)."""
    img = image_tensor[0].cpu().numpy()
    img = np.clip(img, 0.0, 1.0)
    img = (img * 255.0).astype(np.uint8)
    return Image.fromarray(img, mode="RGB")


def _lookup_metadata(pil_image: Image.Image, embed_key: str):
    """Return (value, status) for embed_key in a PIL image's .info dict."""
    info = getattr(pil_image, "info", {}) or {}
    if embed_key in info:
        value = info[embed_key]
        return value, f"Found: {embed_key} ({len(value)} chars)"
    available = ", ".join(info.keys()) if info else "none"
    return "", f"Key '{embed_key}' not found (available metadata keys: {available})"


class IdeogramMetadataReader:
    """Reads an embedded Ideogram JSON prompt from a PNG tEXt chunk.

    Inputs:
        image: an IMAGE whose underlying PNG metadata may carry the prompt.
        embed_key: the PNG metadata key to read.

    Outputs:
        prompt_json: the recovered JSON string, or "" if not present.
        status: a human-readable result, e.g. "Found: ideogram_prompt (842 chars)".

    Note: an IMAGE tensor carries no metadata, so this only recovers a prompt when
    the image still carries its .info (see the module docstring / README).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "embed_key": ("STRING", {"default": "ideogram_prompt"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt_json", "status")
    FUNCTION = "read"
    CATEGORY = "Ideogram/Palette"

    def read(self, image, embed_key="ideogram_prompt"):
        try:
            pil_image = _tensor_to_pil(image)
            return _lookup_metadata(pil_image, embed_key)
        except Exception as e:
            return ("", f"Error reading metadata: {e}")
