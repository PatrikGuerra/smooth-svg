import re

import cv2
import numpy as np
import psutil

# smooth level -> (upscale factor, blur sigma in upscaled px, vtracer corner_threshold)
LEVELS = {
    0: (1, 0.0, 60),
    1: (2, 1.0, 60),
    2: (3, 1.5, 75),
    3: (4, 2.0, 90),
    4: (4, 3.0, 110),
    5: (4, 4.0, 130),
}
# Peak memory of a conversion is about 55 bytes per upscaled pixel with soft edges, 30 without
# (measured with tests/mem_probe.py, 1.6 to 25 MP). 100 leaves a 2x margin for the server's
# preview and score. A big image gets a smaller k instead of filling the RAM.
BYTES_PER_PX = 100
FREE_SHARE = 0.6  # share of the free memory one conversion may use


def max_work_px() -> int:
    """Largest upscaled image (px) that fits in the memory that is free now."""
    return int(psutil.virtual_memory().available * FREE_SHARE / BYTES_PER_PX)


def level(smooth: int) -> tuple[int, float, int]:
    if smooth not in LEVELS:
        raise ValueError(f"smooth must be 0-5, got {smooth}")
    return LEVELS[smooth]


def denoise(img: np.ndarray) -> np.ndarray:
    """Edge-keeping blur of the colors, so JPG noise does not become extra colors."""
    rgb = cv2.bilateralFilter(np.ascontiguousarray(img[..., :3]), 5, 40, 5)
    return np.dstack([rgb, img[..., 3]])


def _soft_labels(src: np.ndarray, q: np.ndarray, palette_rgb: np.ndarray, k: int):
    """Palette index and alpha of the original `src` enlarged k times (Lanczos), no blend colors.

    A pixel may only take a palette color that sits in the 3x3 around its original pixel in q,
    and of those the one closest in Lab. A red/white fade so becomes red or white, never pink,
    and the cut falls where the fade really crosses half way. Alpha is enlarged the same way.
    """
    h, w = q.shape[:2]
    size = (w * k, h * k)
    how = cv2.INTER_LANCZOS4 if k > 1 else cv2.INTER_LINEAR
    a = src[..., 3].astype(np.float32) / 255
    big_a = cv2.resize(a, size, interpolation=how).clip(0, 1)
    rgb = cv2.resize(src[..., :3].astype(np.float32) * a[..., None], size, interpolation=how)
    rgb = (rgb / np.maximum(big_a, 1e-3)[..., None]).clip(0, 255) / 255  # undo the alpha weight
    del a
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    del rgb
    pal_lab = cv2.cvtColor(palette_rgb[None].astype(np.float32) / 255, cv2.COLOR_RGB2LAB)[0]
    solid = q[..., 3] >= 128
    best = np.full(size[::-1], np.inf, np.float32)
    idx = np.zeros(size[::-1], np.uint8)
    for i, (c, cl) in enumerate(zip(palette_rgb, pal_lab)):
        near = cv2.dilate(((q[..., :3] == c).all(axis=2) & solid).astype(np.uint8),
                          np.ones((3, 3), np.uint8))
        d = np.square(lab - cl).sum(axis=2)
        d[cv2.resize(near, size, interpolation=cv2.INTER_NEAREST) == 0] = np.inf
        better = d < best
        best[better], idx[better] = d[better], i
    return idx, np.where(big_a >= 0.5, 255, 0).astype(np.uint8)


def upscale(q: np.ndarray, palette_rgb: np.ndarray, smooth: int, src: np.ndarray | None = None,
            ) -> tuple[np.ndarray, int]:
    """Upscale a flat-color image so its edges are smooth curves, with the same palette.

    Each palette color gets a 0/1 mask. A mask is upscaled and blurred, which turns stair
    edges into soft ramps. Each pixel takes the color whose mask is highest, so the edge is
    the 50% contour: smooth, and no in-between color (halo) can appear.
    With src (the original RGBA, soft edges), the masks come from the enlarged original instead
    of q, so the soft antialiased pixels still place the edge. See _soft_labels.
    k is lowered when the enlarged image would not fit in the free memory.
    """
    k, sigma, _ = level(smooth)
    h, w = q.shape[:2]
    k = max(1, min(k, int((max_work_px() / (h * w)) ** 0.5)))
    if k == 1 and not sigma:
        return q, 1
    size = (w * k, h * k)
    if src is not None:
        lab_idx, alpha = _soft_labels(src, q, palette_rgb, k)
    else:
        alpha = np.where(cv2.resize(q[..., 3], size, interpolation=cv2.INTER_LINEAR) >= 128,
                         255, 0).astype(np.uint8)
    best = np.full(size[::-1], -1.0, np.float32)
    idx = np.zeros(size[::-1], np.uint8)
    for i, c in enumerate(palette_rgb):
        if src is not None:
            m = (lab_idx == i).astype(np.float32)
        else:
            m = cv2.resize((q[..., :3] == c).all(axis=2).astype(np.float32), size,
                           interpolation=cv2.INTER_LINEAR)
        if sigma:
            m = cv2.GaussianBlur(m, (0, 0), sigma * k / 2)
        better = m > best
        best[better], idx[better] = m[better], i
    return np.dstack([palette_rgb[idx], alpha]), k

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