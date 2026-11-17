import cv2
import numpy as np
import potrace

from .score import flatten
from .smooth import level, shrink

MAX_K = 3  # potracer is pure Python; more than x3 gets slow on big images
MAX_WORK_PX = 4_000_000


def _hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(int(v) for v in rgb))


def _d(plist) -> str:
    parts = []
    for curve in plist:
        s = curve.start_point
        parts.append(f"M{s.x:.1f} {s.y:.1f}")
        for seg in curve.segments:
            if seg.is_corner:
                parts.append(f"L{seg.c.x:.1f} {seg.c.y:.1f}L{seg.end_point.x:.1f} {seg.end_point.y:.1f}")
            else:
                parts.append(
                    f"C{seg.c1.x:.1f} {seg.c1.y:.1f} {seg.c2.x:.1f} {seg.c2.y:.1f} "
                    f"{seg.end_point.x:.1f} {seg.end_point.y:.1f}")
        parts.append("Z")
    return "".join(parts)


def otsu(gray: np.ndarray) -> float:
    """Dark/light split. Ink is gray <= result (Otsu can return 0 on a pure black/white image)."""
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0]


def trace_drawing(img: np.ndarray, smooth: int = 3, disabled=(), remove_bg: bool = False):
    """Black-on-light drawings: threshold, upscale softly, trace one ink shape with Potrace.

    Returns (svg, palette) with palette = [(color, share), ...] for the UI dots.
    """
    h, w = img.shape[:2]
    rgb = flatten(img)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    k, sigma, _ = level(smooth)
    k = max(1, min(k, MAX_K, int((MAX_WORK_PX / (h * w)) ** 0.5)))
    if k > 1:
        gray = cv2.resize(gray, (w * k, h * k), interpolation=cv2.INTER_CUBIC)
        gray = cv2.GaussianBlur(gray, (0, 0), sigma * k / 2)
    ink_small = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY) <= otsu(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
    ink = gray <= otsu(gray)
    ink_c = _hex(rgb[ink_small].mean(axis=0)) if ink_small.any() else "#000000"
    bg_c = _hex(rgb[~ink_small].mean(axis=0)) if (~ink_small).any() else "#FFFFFF"
    plist = potrace.Bitmap(~ink).trace(turdsize=k * k + 1, alphamax=1.0, opttolerance=0.4)

    body = ""
    if bg_c not in disabled and not remove_bg:
        body += f'<rect width="{w * k}" height="{h * k}" fill="{bg_c}"/>'
    if ink_c not in disabled:
        body += f'<path fill="{ink_c}" fill-rule="evenodd" d="{_d(plist)}"/>'
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w * k} {h * k}">{body}</svg>')
    share = float(ink_small.mean())
    return shrink(svg), [(ink_c, round(share, 4)), (bg_c, round(1 - share, 4))]


def trace_layers(q: np.ndarray, palette_rgb: np.ndarray, alphamax: float = 1.0,
                 opttolerance: float = 0.4, turdsize: int = 2) -> str:
    """Trace a flat-color RGBA image with Potrace, one stacked layer per color.

    Colors are sorted by area. Layer r covers every pixel whose color has rank >= r, so a
    later layer paints over the earlier ones and no gaps show between touching colors.
    Returns the <path> elements, in the pixel space of q.
    """
    rgb = q[..., :3]
    solid = q[..., 3] >= 128
    idx = np.full(q.shape[:2], -1, np.int32)
    counts = []
    for i, c in enumerate(palette_rgb):
        m = (rgb == c).all(axis=2) & solid
        idx[m] = i
        counts.append(int(m.sum()))
    order = [int(i) for i in np.argsort(counts)[::-1] if counts[i] > 0]
    rank = np.zeros(len(palette_rgb), np.int32)
    for r, i in enumerate(order):
        rank[i] = r
    rk = np.where(idx >= 0, rank[idx.clip(0)], -1)
    out = []
    for r, i in enumerate(order):
        plist = potrace.Bitmap(~(rk >= r)).trace(
            turdsize=turdsize, alphamax=alphamax, opttolerance=opttolerance)
        d = _d(plist)
        if d:
            out.append(f'<path fill="{_hex(palette_rgb[i])}" fill-rule="evenodd" d="{d}"/>')
    return "".join(out)
