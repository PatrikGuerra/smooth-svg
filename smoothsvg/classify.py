import numpy as np

from .score import flatten


def classify(img: np.ndarray) -> str:
    """Guess drawing / pixelart / photo / clipart from the pixels alone."""
    rgb = flatten(img)
    h, w = rgb.shape[:2]
    flat = rgb.reshape(-1, 3)

    gray = flat.astype(int).max(axis=1) - flat.astype(int).min(axis=1) < 16
    lum = flat.mean(axis=1)
    extreme = (lum < 60) | (lum > 195)
    if gray.mean() > 0.97 and extreme.mean() > 0.9:
        return "drawing"

    # size test first: np.unique over a big image is slow (1.3 s per megapixel)
    if max(h, w) <= 128 and len(np.unique(flat, axis=0)) <= 32:
        return "pixelart"

    # 3 bits per channel: how many of the 512 color bins hold 80% of the pixels.
    # Clipart (even as noisy JPG) needs a handful; a photo needs dozens.
    bins = np.bincount(((flat >> 5) * [64, 8, 1]).sum(axis=1), minlength=512)
    covered = np.cumsum(np.sort(bins)[::-1]) / len(flat)
    if np.searchsorted(covered, 0.8) + 1 > 25:
        return "photo"
    return "clipart"
