"""Tests for IdeogramMetadataEmbedder: it saves a PNG to disk with the Ideogram
JSON prompt embedded in a tEXt chunk, preserves ComfyUI's standard metadata, and
never crashes the workflow on failure."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch
from PIL import Image

from nodes.metadata_embedder import IdeogramMetadataEmbedder, _build_pnginfo

SAMPLE_JSON = json.dumps({"high_level_description": "a test scene", "style_description": {"color_palette": ["#FF5733"]}})


def _dummy_batch(b=1, h=16, w=16):
    arr = np.random.rand(b, h, w, 3).astype(np.float32)
    return torch.from_numpy(arr)


def _saved_path(node, ret):
    img_info = ret["ui"]["images"][0]
    return Path(node.output_dir) / img_info["subfolder"] / img_info["filename"]


def test_written_png_contains_embedded_prompt():
    node = IdeogramMetadataEmbedder()
    with tempfile.TemporaryDirectory() as tmp:
        node.output_dir = tmp
        ret = node.embed(_dummy_batch(), SAMPLE_JSON, "ideogram", "ideogram_prompt")
        path = _saved_path(node, ret)
        assert path.exists()
        with Image.open(path) as im:
            assert im.info.get("ideogram_prompt") == SAMPLE_JSON


def test_custom_embed_key_and_preview_string():
    node = IdeogramMetadataEmbedder()
    with tempfile.TemporaryDirectory() as tmp:
        node.output_dir = tmp
        ret = node.embed(_dummy_batch(), SAMPLE_JSON, "ideogram", "my_key")
        preview = ret["result"][0]
        assert preview.startswith(f"Embedded: my_key ({len(SAMPLE_JSON)} chars)")
        with Image.open(_saved_path(node, ret)) as im:
            assert im.info.get("my_key") == SAMPLE_JSON


def test_preserves_standard_comfy_metadata():
    # When ComfyUI passes the hidden prompt graph, it should still be embedded.
    meta_img = Image.fromarray((np.random.rand(8, 8, 3) * 255).astype("uint8"), "RGB")
    from io import BytesIO
    pnginfo = _build_pnginfo(SAMPLE_JSON, "ideogram_prompt", prompt={"3": {"class_type": "KSampler"}})
    buf = BytesIO()
    meta_img.save(buf, format="PNG", pnginfo=pnginfo)
    buf.seek(0)
    with Image.open(buf) as im:
        assert im.info.get("ideogram_prompt") == SAMPLE_JSON
        assert json.loads(im.info.get("prompt")) == {"3": {"class_type": "KSampler"}}


def test_batch_saves_multiple_files():
    node = IdeogramMetadataEmbedder()
    with tempfile.TemporaryDirectory() as tmp:
        node.output_dir = tmp
        ret = node.embed(_dummy_batch(b=3), SAMPLE_JSON, "ideogram", "ideogram_prompt")
        assert len(ret["ui"]["images"]) == 3
        for info in ret["ui"]["images"]:
            assert (Path(tmp) / info["subfolder"] / info["filename"]).exists()


def test_graceful_failure_does_not_crash():
    node = IdeogramMetadataEmbedder()
    # None image triggers an exception inside embed() -> warning, no raise.
    ret = node.embed(None, SAMPLE_JSON, "ideogram", "ideogram_prompt")
    assert ret["result"][0].startswith("Warning:")
    assert ret["ui"]["images"] == []


if __name__ == "__main__":
    test_written_png_contains_embedded_prompt()
    print("written_png_contains_embedded_prompt: OK")
    test_custom_embed_key_and_preview_string()
    print("custom_embed_key_and_preview_string: OK")
    test_preserves_standard_comfy_metadata()
    print("preserves_standard_comfy_metadata: OK")
    test_batch_saves_multiple_files()
    print("batch_saves_multiple_files: OK")
    test_graceful_failure_does_not_crash()
    print("graceful_failure_does_not_crash: OK")
    print("All metadata_embedder tests passed.")
