"""Sanity checks for color_utils.py — RGB/LAB conversion, Delta-E, hex helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.color_utils import hex_to_rgb, rgb_to_hex, rgb_to_lab, delta_e


def test_hex_rgb_roundtrip():
    assert hex_to_rgb("#FF5733") == (255, 87, 51)
    assert rgb_to_hex((255, 87, 51)) == "#FF5733"
    assert hex_to_rgb("000000") == (0, 0, 0)
    assert rgb_to_hex((0, 0, 0)) == "#000000"


def test_lab_known_points():
    # Pure white should be ~L=100, a=0, b=0
    lab_white = rgb_to_lab((255, 255, 255))
    assert abs(lab_white[0] - 100.0) < 0.5
    assert abs(lab_white[1]) < 0.5
    assert abs(lab_white[2]) < 0.5

    # Pure black should be ~L=0, a=0, b=0
    lab_black = rgb_to_lab((0, 0, 0))
    assert abs(lab_black[0]) < 0.5


def test_delta_e_identical_is_zero():
    lab1 = rgb_to_lab((100, 150, 200))
    lab2 = rgb_to_lab((100, 150, 200))
    assert delta_e(lab1, lab2) == 0.0


def test_delta_e_distinct_colors_large():
    lab_red = rgb_to_lab((255, 0, 0))
    lab_blue = rgb_to_lab((0, 0, 255))
    d = delta_e(lab_red, lab_blue)
    assert d > 50.0  # red vs blue should be perceptually far apart


def test_delta_e_similar_colors_small():
    lab_a = rgb_to_lab((100, 100, 100))
    lab_b = rgb_to_lab((102, 101, 99))
    d = delta_e(lab_a, lab_b)
    assert d < 5.0  # near-identical grays should be perceptually close


if __name__ == "__main__":
    test_hex_rgb_roundtrip()
    test_lab_known_points()
    test_delta_e_identical_is_zero()
    test_delta_e_distinct_colors_large()
    test_delta_e_similar_colors_small()
    print("All color_utils sanity checks passed.")
