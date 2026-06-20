"""IdeogramLoadImageWithPrompt node.

Loads a PNG from disk by file path and recovers an Ideogram 4 JSON prompt
embedded in its tEXt metadata, outputting both the image and the prompt.

This is the working counterpart to IdeogramMetadataReader: because a ComfyUI
IMAGE tensor carries no metadata, reading an embedded prompt only works when you
read the file itself — which is what this node does. It closes the loop with
IdeogramMetadataEmbedder (embed on save here, recover on load).
"""

import os

import numpy as np
import torch
from PIL import Image

# ComfyUI runtime module — absent when unit-testing outside ComfyUI.
try:
    import folder_paths
    _HAVE_COMFY = True
except ImportError:  # pragma: no cover - exercised only outside ComfyUI
    folder_paths = None
    _HAVE_COMFY = False


def _resolve_path(path):
    """Resolve a file path: try it as given, then relative to ComfyUI's output and
    input directories. Returns an existing file path or None."""
    path = (path or "").strip().strip('"')
    if not path:
        return None
    candidates = [path]
    if _HAVE_COMFY:
        candidates.append(os.path.join(folder_paths.get_output_directory(), path))
        candidates.append(os.path.join(folder_paths.get_input_directory(), path))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def _pil_to_tensor(pil_image):
    """Convert a PIL image to a ComfyUI IMAGE tensor (1, H, W, C), float32 0-1."""
    arr = np.asarray(pil_image.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(arr)[None, ...]


def _blank_image():
    """A small valid black IMAGE tensor, returned so failures never break the graph."""
    return torch.zeros((1, 64, 64, 3), dtype=torch.float32)


class IdeogramLoadImageWithPrompt:
    """Loads a PNG by path and recovers its embedded Ideogram JSON prompt.

    Inputs:
        image_path: path to a PNG file (absolute, or relative to ComfyUI's
            output/input directories).
        embed_key: the PNG metadata key to read the prompt from.

    Outputs:
        image: the loaded image as a ComfyUI IMAGE tensor.
        prompt_json: the recovered JSON string, or "" if not present.
        status: a human-readable result message.

    Always returns a valid IMAGE (a small black tensor on failure) so the graph
    never breaks.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_path": ("STRING", {"default": ""}),
                "embed_key": ("STRING", {"default": "ideogram_prompt"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "prompt_json", "status")
    FUNCTION = "load"
    CATEGORY = "Ideogram/Palette"

    def load(self, image_path, embed_key="ideogram_prompt"):
        try:
            resolved = _resolve_path(image_path)
            if resolved is None:
                return (_blank_image(), "", f"File not found: {image_path!r}")

            img = Image.open(resolved)
            img.load()
            info = getattr(img, "info", {}) or {}
            tensor = _pil_to_tensor(img)
            name = os.path.basename(resolved)

            if embed_key in info:
                value = info[embed_key]
                return (tensor, value, f"Loaded {name}; found '{embed_key}' ({len(value)} chars)")

            available = ", ".join(info.keys()) if info else "none"
            return (tensor, "", f"Loaded {name}; key '{embed_key}' not found (available: {available})")

        except Exception as e:
            return (_blank_image(), "", f"Error: {e}")
