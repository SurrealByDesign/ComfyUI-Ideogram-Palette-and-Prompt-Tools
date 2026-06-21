"""Tests for IdeogramMetadataReader: recovering an embedded prompt from PNG tEXt
metadata, and graceful handling of missing metadata / wrong keys.

Requires torch: IdeogramMetadataReader.read() takes a real ComfyUI IMAGE
tensor and calls _tensor_to_pil(), which uses tensor.cpu() -- a torch-only
method. The _lookup_metadata tests below exercise that helper directly with
a plain PIL image (no torch needed for those), but the read() tests need a
real tensor to demonstrate the actual node-level behavior."""

import json
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from nodes.metadata_reader import IdeogramMetadataReader, _lookup_metadata

SAMPLE_JSON = json.dumps({"high_level_description": "a test scene"})


def _pil_with_metadata(key, value):
    """Build a PIL image whose .info carries a tEXt chunk (via a save/reload round-trip)."""
    img = Image.new("RGB", (8, 8), (10, 20, 30))
    meta = PngInfo()
    meta.add_text(key, value)
    buf = BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    buf.seek(0)
    loaded = Image.open(buf)
    loaded.load()
    return loaded


def test_recovers_embedded_json():
    pil = _pil_with_metadata("ideogram_prompt", SAMPLE_JSON)
    value, status = _lookup_metadata(pil, "ideogram_prompt")
    assert value == SAMPLE_JSON
    assert "Found: ideogram_prompt" in status
    assert str(len(SAMPLE_JSON)) in status


def test_no_metadata_present():
    plain = Image.new("RGB", (8, 8))  # no .info tEXt chunks
    value, status = _lookup_metadata(plain, "ideogram_prompt")
    assert value == ""
    assert "not found" in status


def test_wrong_embed_key():
    pil = _pil_with_metadata("ideogram_prompt", SAMPLE_JSON)
    value, status = _lookup_metadata(pil, "some_other_key")
    assert value == ""
    assert "not found" in status
    # the available key should be surfaced in the status for debugging
    assert "ideogram_prompt" in status


def _fake_image_tensor():
    """A (1, H, W, 3) float32 0-1 tensor, matching a real ComfyUI IMAGE."""
    return torch.rand(1, 8, 8, 3)


def test_read_with_real_tensor_loses_metadata():
    """The actual node-level behavior the README documents as a limitation:
    a real IMAGE tensor carries no PNG metadata, so even though the prompt
    was "embedded" conceptually, converting the tensor to PIL via
    _tensor_to_pil() always produces an empty .info -- read() can never
    recover anything from a tensor alone, regardless of embed_key."""
    node = IdeogramMetadataReader()
    prompt_json, status = node.read(_fake_image_tensor(), "ideogram_prompt")
    assert prompt_json == ""
    assert "not found" in status


def test_read_handles_bad_input_gracefully():
    """read() must never raise -- a malformed image input should produce the
    node's own error status string instead of propagating an exception."""
    node = IdeogramMetadataReader()
    prompt_json, status = node.read("not a tensor", "ideogram_prompt")
    assert prompt_json == ""
    assert "Error reading metadata" in status


if __name__ == "__main__":
    test_recovers_embedded_json()
    print("recovers_embedded_json: OK")
    test_no_metadata_present()
    print("no_metadata_present: OK")
    test_wrong_embed_key()
    print("wrong_embed_key: OK")
    test_read_with_real_tensor_loses_metadata()
    print("read_with_real_tensor_loses_metadata: OK")
    test_read_handles_bad_input_gracefully()
    print("read_handles_bad_input_gracefully: OK")
    print("All metadata_reader tests passed.")
