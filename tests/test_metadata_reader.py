"""Tests for IdeogramMetadataReader: recovering an embedded prompt from PNG tEXt
metadata, and graceful handling of missing metadata / wrong keys."""

import json
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from nodes.metadata_reader import _lookup_metadata

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


if __name__ == "__main__":
    test_recovers_embedded_json()
    print("recovers_embedded_json: OK")
    test_no_metadata_present()
    print("no_metadata_present: OK")
    test_wrong_embed_key()
    print("wrong_embed_key: OK")
    print("All metadata_reader tests passed.")
