import re

import cv2
import numpy as np

# smooth level -> (upscale factor, blur sigma in upscaled px, vtracer corner_threshold)
LEVELS = {
    0: (1, 0.0, 60),
    1: (2, 1.0, 60),
    2: (3, 1.5, 75),
    3: (4, 2.0, 90),
    4: (4, 3.0, 110),
    5: (4, 4.0, 130),
}
MAX_WORK_PX = 16_000_000  # upscaled image cap, keeps memory bounded


def level(smooth: int) -> tuple[int, float, int]:
    if smooth not in LEVELS:
        raise ValueError(f"smooth must be 0-5, got {smooth}")
    return LEVELS[smooth]


def denoise(img: np.ndarray) -> np.ndarray:
    """Edge-keeping blur of the colors, so JPG noise does not become extra colors."""
    rgb = cv2.bilateralFilter(np.ascontiguousarray(img[..., :3]), 5, 40, 5)
    return np.dstack([rgb, img[..., 3]])


def upscale(q: np.ndarray, palette_rgb: np.ndarray, smooth: int) -> tuple[np.ndarray, int]:
    """Upscale a flat-color image so its edges are smooth curves, with the same palette.

    Each palette color gets a 0/1 mask. A mask is upscaled and blurred, which turns stair
    edges into soft ramps. Each pixel takes the color whose mask is highest, so the edge is
    the 50% contour: smooth, and no in-between color (halo) can appear.
    """
    k, sigma, _ = level(smooth)
    h, w = q.shape[:2]
    k = max(1, min(k, int((MAX_WORK_PX / (h * w)) ** 0.5)))
    if k == 1 and not sigma:
        return q, 1
    size = (w * k, h * k)
    best = np.full(size[::-1], -1.0, np.float32)
    idx = np.zeros(size[::-1], np.uint8)
    for i, c in enumerate(palette_rgb):
        mask = (q[..., :3] == c).all(axis=2).astype(np.float32)
        m = cv2.resize(mask, size, interpolation=cv2.INTER_LINEAR)
        if sigma:
            m = cv2.GaussianBlur(m, (0, 0), sigma * k / 2)
        better = m > best
        best[better], idx[better] = m[better], i
    alpha = cv2.resize(q[..., 3], size, interpolation=cv2.INTER_LINEAR)
    out = np.dstack([palette_rgb[idx], np.where(alpha >= 128, 255, 0).astype(np.uint8)])
    return out, k

def fit_viewbox(svg: str, w: int, h: int, big_w: int, big_h: int) -> str:
    """Show an SVG traced at the upscaled size at the original size."""
    return re.sub(
        r'width="\d+" height="\d+"',
        f'width="{w}" height="{h}" viewBox="0 0 {big_w} {big_h}"',
        svg, count=1,
    )
