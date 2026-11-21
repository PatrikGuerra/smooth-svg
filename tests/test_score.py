from pathlib import Path

import numpy as np
from PIL import Image

from smoothsvg.score import ssim

RNG = np.random.default_rng(0)
IMG = RNG.integers(0, 256, (40, 50, 3), dtype=np.uint8)


def test_identical_is_one():
    assert ssim(IMG, IMG) == 1.0


def test_noise_lowers_score():
    noisy = np.clip(IMG + RNG.normal(0, 30, IMG.shape), 0, 255).astype(np.uint8)
    assert ssim(IMG, noisy) < ssim(IMG, np.clip(IMG + 2, 0, 255).astype(np.uint8)) < 1.0


def test_matches_skimage_values():
    # Values computed once with skimage.metrics.structural_similarity(channel_axis=2).
    flat = np.full((40, 50, 3), 128, np.uint8)
    white = np.full((40, 50, 3), 255, np.uint8)
    assert abs(ssim(flat, white) - 0.8018927660613532) < 1e-3


def test_matches_skimage_on_sample():
    im = np.asarray(Image.open(Path(__file__).parent / "samples" / "logo.png").convert("RGB"))
    assert abs(ssim(im, np.roll(im, 3, axis=1)) - 0.9377899288661028) < 1e-3
