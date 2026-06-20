"""Tests for IdeogramMaskedPaletteExtractor: extraction restricted to the masked
region, threshold handling, and graceful fallback on an empty mask."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from nodes.masked_palette_extractor import IdeogramMaskedPaletteExtractor

H = W = 64


def _node():
    return IdeogramMaskedPaletteExtractor()


def _red_left_blue_right():
    """64x64 image: left half pure red, right half pure blue, as a (1, H, W, 3) tensor."""
    img = np.zeros((H, W, 3), dtype=np.float32)
    img[:, : W // 2, 0] = 1.0  # left half red
    img[:, W // 2 :, 2] = 1.0  # right half blue
    return torch.from_numpy(img)[None, ...]


def _mask(cols_on):
    """(1, H, W) mask with the first `cols_on` columns set to 1.0, rest 0.0."""
    m = np.zeros((H, W), dtype=np.float32)
    m[:, :cols_on] = 1.0
    return torch.from_numpy(m)[None, ...]


def test_extracts_only_masked_region():
    image = _red_left_blue_right()
    mask = _mask(20)  # well inside the red half, away from the blend boundary
    palette_json, _, count = _node().extract(image, mask, 8, 10.0, 0.5)
    colors = json.loads(palette_json)
    assert "#FF0000" in colors
    assert "#0000FF" not in colors


def test_full_mask_sees_both_colors():
    image = _red_left_blue_right()
    mask = _mask(W)  # whole image selected
    palette_json, _, count = _node().extract(image, mask, 8, 10.0, 0.5)
    colors = json.loads(palette_json)
    assert "#FF0000" in colors
    assert "#0000FF" in colors


def test_empty_mask_falls_back_to_gray():
    image = _red_left_blue_right()
    mask = _mask(0)  # nothing selected
    palette_json, preview, count = _node().extract(image, mask, 8, 10.0, 0.5)
    assert json.loads(palette_json) == ["#808080"]
    assert count == 1


def test_threshold_excludes_low_mask_values():
    image = _red_left_blue_right()
    half_mask = torch.full((1, H, W), 0.3, dtype=torch.float32)  # below 0.5 everywhere
    palette_json, _, _ = _node().extract(image, half_mask, 8, 10.0, 0.5)
    assert json.loads(palette_json) == ["#808080"]


def test_output_format():
    image = _red_left_blue_right()
    mask = _mask(W)
    palette_json, preview, count = _node().extract(image, mask, 8, 10.0, 0.5)
    colors = json.loads(palette_json)
    assert isinstance(preview, torch.Tensor)
    assert preview.shape[0] == 1 and preview.shape[3] == 3
    assert count == len(colors)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("All masked_palette_extractor tests passed.")
