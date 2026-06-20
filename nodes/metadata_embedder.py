"""IdeogramMetadataEmbedder node.

Saves the generated image to the ComfyUI output directory with the Ideogram 4
JSON prompt embedded in a PNG tEXt metadata chunk, so the prompt travels with
the file on disk.

Why this is a *save* node rather than a pass-through: ComfyUI's IMAGE type is a
bare tensor and carries no metadata, so a node that outputs IMAGE cannot make a
tEXt chunk survive to the next node. Metadata only persists at the moment the
PNG is written (see ComfyUI's SaveImage), and the stock SaveImage exposes its
extra-metadata channel only as a *hidden* input that can't be wired from
upstream. The only correct place to embed a custom key is therefore at save
time, which is what this node owns.

NOTE: tEXt metadata is a PNG feature. This node writes PNG. If the resulting
file is later re-saved as JPEG (or any non-PNG format), the embedded prompt is
DESTROYED.
"""

import json
import os

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

# ComfyUI runtime modules — absent when unit-testing outside ComfyUI.
try:
    import folder_paths
    from comfy.cli_args import args as _comfy_args
    _HAVE_COMFY = True
except ImportError:  # pragma: no cover - exercised only outside ComfyUI
    folder_paths = None
    _comfy_args = None
    _HAVE_COMFY = False


def _build_pnginfo(prompt_json: str, embed_key: str, prompt=None, extra_pnginfo=None) -> PngInfo:
    """Build a PngInfo carrying the custom Ideogram key plus ComfyUI's standard
    workflow metadata (so the saved file stays reproducible inside ComfyUI)."""
    meta = PngInfo()
    # Custom key first: the dedicated Ideogram prompt.
    meta.add_text(embed_key, prompt_json)
    # Preserve ComfyUI's normal reproducibility metadata when available.
    if prompt is not None:
        meta.add_text("prompt", json.dumps(prompt))
    if extra_pnginfo is not None:
        for key in extra_pnginfo:
            meta.add_text(key, json.dumps(extra_pnginfo[key]))
    return meta


def _tensor_image_to_pil(image) -> Image.Image:
    """Convert a single ComfyUI image tensor (H, W, C), float 0-1, to a PIL RGB image."""
    arr = 255.0 * image.cpu().numpy()
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


class IdeogramMetadataEmbedder:
    """Saves an image to the output directory with the Ideogram JSON prompt embedded
    in a PNG tEXt chunk.

    Inputs:
        image: generated IMAGE (e.g. from the Ideogram sampler).
        prompt_json: the Ideogram 4 JSON prompt string to embed.
        filename_prefix: prefix for the saved PNG file(s).
        embed_key: PNG metadata key the JSON is stored under.

    Output:
        metadata_preview: confirmation string, e.g.
            "Embedded: ideogram_prompt (842 chars) -> ideogram_00001_.png".

    This is a terminal save node (it writes PNGs to the ComfyUI output folder and
    previews them in the node). The embedded metadata only persists for PNG files;
    re-saving the file as JPEG elsewhere discards it.
    """

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory() if _HAVE_COMFY else os.path.abspath("output")
        self.type = "output"
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "prompt_json": ("STRING", {"forceInput": True}),
                "filename_prefix": ("STRING", {"default": "ideogram"}),
                "embed_key": ("STRING", {"default": "ideogram_prompt"}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("metadata_preview",)
    FUNCTION = "embed"
    OUTPUT_NODE = True
    CATEGORY = "Ideogram/Palette"

    def _resolve_save_path(self, filename_prefix, width, height):
        if _HAVE_COMFY:
            return folder_paths.get_save_image_path(filename_prefix, self.output_dir, width, height)
        os.makedirs(self.output_dir, exist_ok=True)
        existing = [f for f in os.listdir(self.output_dir) if f.startswith(filename_prefix) and f.endswith(".png")]
        return self.output_dir, filename_prefix, len(existing) + 1, "", filename_prefix

    def embed(self, image, prompt_json, filename_prefix="ideogram", embed_key="ideogram_prompt",
              prompt=None, extra_pnginfo=None):
        results = []
        saved_names = []
        try:
            full_output_folder, filename, counter, subfolder, _ = self._resolve_save_path(
                filename_prefix, image[0].shape[1], image[0].shape[0]
            )
            disable_meta = bool(getattr(_comfy_args, "disable_metadata", False)) if _HAVE_COMFY else False

            for batch_number, single in enumerate(image):
                img = _tensor_image_to_pil(single)
                metadata = None
                if not disable_meta:
                    try:
                        metadata = _build_pnginfo(prompt_json, embed_key, prompt, extra_pnginfo)
                    except Exception:
                        # Bad metadata must not block the save — write pixels anyway.
                        metadata = None

                file = f"{filename}_{counter:05}_.png"
                img.save(os.path.join(full_output_folder, file), pnginfo=metadata, compress_level=self.compress_level)
                results.append({"filename": file, "subfolder": subfolder, "type": self.type})
                saved_names.append(file)
                counter += 1

            preview = f"Embedded: {embed_key} ({len(prompt_json)} chars) -> {', '.join(saved_names)}"
        except Exception as e:
            # Never crash the workflow.
            preview = f"Warning: metadata save failed ({e})"

        return {"ui": {"images": results}, "result": (preview,)}
