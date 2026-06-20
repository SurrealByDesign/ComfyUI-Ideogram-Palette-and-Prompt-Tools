"""Tests for IdeogramLoadImageWithPrompt: loads a PNG from disk and recovers an
embedded prompt, with graceful handling of missing files / metadata / wrong keys."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from nodes.metadata_file_reader import IdeogramLoadImageWithPrompt

SAMPLE_JSON = json.dumps({"high_level_description": "a test scene", "style_description": {"color_palette": ["#FF5733"]}})


def _node():
    return IdeogramLoadImageWithPrompt()


def _write_png(dir_path, name, key=None, value=None, size=(32, 24)):
    img = Image.new("RGB", size, (40, 80, 120))
    meta = None
    if key is not None:
        meta = PngInfo()
        meta.add_text(key, value)
    path = Path(dir_path) / name
    img.save(path, format="PNG", pnginfo=meta)
    return str(path)


def test_loads_image_and_recovers_prompt():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_png(tmp, "embedded.png", "ideogram_prompt", SAMPLE_JSON, size=(32, 24))
        image, prompt_json, status = _node().load(path, "ideogram_prompt")
        assert prompt_json == SAMPLE_JSON
        assert isinstance(image, torch.Tensor)
        assert image.shape == (1, 24, 32, 3)  # (B, H, W, C)
        assert image.dtype == torch.float32
        assert "found 'ideogram_prompt'" in status


def test_missing_file_returns_blank_and_status():
    image, prompt_json, status = _node().load("does_not_exist_12345.png", "ideogram_prompt")
    assert prompt_json == ""
    assert image.shape == (1, 64, 64, 3)  # blank fallback
    assert "File not found" in status


def test_png_without_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_png(tmp, "plain.png")  # no tEXt chunk
        image, prompt_json, status = _node().load(path, "ideogram_prompt")
        assert prompt_json == ""
        assert image.shape[0] == 1  # still a valid loaded image
        assert "not found" in status


def test_wrong_embed_key_reports_available():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_png(tmp, "embedded.png", "ideogram_prompt", SAMPLE_JSON)
        image, prompt_json, status = _node().load(path, "some_other_key")
        assert prompt_json == ""
        assert "not found" in status
        assert "ideogram_prompt" in status  # surfaces the available key


def test_empty_path_is_graceful():
    image, prompt_json, status = _node().load("", "ideogram_prompt")
    assert prompt_json == ""
    assert image.shape == (1, 64, 64, 3)
    assert "File not found" in status


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("All metadata_file_reader tests passed.")
