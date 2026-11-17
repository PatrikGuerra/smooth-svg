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
MAX_WORK_PX = 2_500_000  # upscaled image cap: bounds memory and time; big images need less upscale


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

def remove_islands(q: np.ndarray, palette_rgb: np.ndarray, min_area: int) -> np.ndarray:
    """Give color islands smaller than min_area px to the color around them (JPG noise)."""
    if min_area <= 1 or not len(palette_rgb):
        return q
    idx = np.zeros(q.shape[:2], np.int32)
    for i, c in enumerate(palette_rgb):
        idx[(q[..., :3] == c).all(axis=2)] = i
    ring = np.ones((3, 3), np.uint8)
    for i in range(len(palette_rgb)):
        n, cc, stats, _ = cv2.connectedComponentsWithStats(
            (idx == i).astype(np.uint8), connectivity=4)
        for j in range(1, n):
            x, y, bw, bh, area = stats[j]
            if area >= min_area:
                continue
            ys, xs = slice(max(y - 1, 0), y + bh + 1), slice(max(x - 1, 0), x + bw + 1)
            comp = (cc[ys, xs] == j).astype(np.uint8)
            around = cv2.dilate(comp, ring) - comp
            nb = idx[ys, xs][around > 0]
            if len(nb):
                idx[ys, xs][comp > 0] = np.bincount(nb).argmax()
    out = q.copy()
    out[..., :3] = palette_rgb[idx]
    return out


def border_color(q: np.ndarray, palette: list) -> str | None:
    """Hex of the palette color that covers most of the image border (the background)."""
    if not palette:
        return None
    edge = np.concatenate([q[0, :, :3], q[-1, :, :3], q[:, 0, :3], q[:, -1, :3]])
    vals, counts = np.unique(edge, axis=0, return_counts=True)
    r, g, b = vals[counts.argmax()]
    return f"#{r:02X}{g:02X}{b:02X}"


def shrink(svg: str) -> str:
    """Minify with scour: relative coordinates, shorter numbers, no metadata."""
    from scour import scour

    o = scour.sanitizeOptions()
    o.strip_xml_prolog = True
    o.remove_metadata = True
    o.strip_comments = True
    o.digits = 5
    return scour.scourString(svg, o)