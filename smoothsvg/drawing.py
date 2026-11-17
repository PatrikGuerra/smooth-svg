import re

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


def _filled_area(mask: np.ndarray) -> int:
    """Pixels inside the outer outlines of a mask, holes included."""
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    canvas = np.zeros(mask.shape, np.uint8)
    cv2.drawContours(canvas, cs, -1, 1, -1)
    return int(canvas.sum())


def _mask_png(mask: np.ndarray) -> bytes:
    """Black shape on white, as PNG bytes, for vtracer's binary mode."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).convert("RGBA").save(buf, "PNG")
    return buf.getvalue()


def trace_stacked(q: np.ndarray, palette_rgb: np.ndarray, **vt) -> str:
    """Trace each color as its own stacked layer with vtracer, and own the layering here.

    Layer r covers every pixel with color rank >= r, so upper layers sit on top and nothing shows
    between touching colors. Any order draws the right picture; colors are sorted by their area
    with holes filled, so a ring (like a halo) goes under the shape it surrounds and stays smooth. Where an upper layer reaches the outer
    edge of the drawing, the lower layer is pulled back a few pixels under it. Without that, the
    two outlines are fitted separately and a thin line of the lower color peeks out.
    Returns the <path> elements, in the pixel space of q.
    """
    import vtracer

    rgb = q[..., :3]
    solid = q[..., 3] >= 128
    idx = np.full(q.shape[:2], -1, np.int32)
    counts = []
    for i, c in enumerate(palette_rgb):
        m = (rgb == c).all(axis=2) & solid
        idx[m] = i
        counts.append(int(m.sum()))
    filled = [_filled_area(idx == i) if counts[i] else 0 for i in range(len(palette_rgb))]
    order = [int(i) for i in np.argsort(filled, kind="stable")[::-1] if counts[i] > 0]
    rank = np.zeros(len(palette_rgb), np.int32)
    for r, i in enumerate(order):
        rank[i] = r
    rk = np.where(idx >= 0, rank[idx.clip(0)], -1)

    def grow(mask, px):
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
        return cv2.dilate(mask.astype(np.uint8), k) > 0

    near_edge = grow(~solid, vt.pop("inset", 3))  # pixels close to the outside
    keep_collar = vt.pop("collar", 2)  # keep this much of the upper layer around its neighbour
    out = []
    for r, i in enumerate(order):
        mask = rk >= r
        if r < len(order) - 1:
            upper = rk > r
            mask = mask & ~(near_edge & upper & ~grow(rk == r, keep_collar))
        svg = vtracer.convert_raw_image_to_svg(
            _mask_png(mask), img_format="png", colormode="binary", mode="spline", **vt)
        fill = _hex(palette_rgb[i])
        for tag in re.findall(r"<path\b[^>]*>", svg):
            out.append(re.sub(r'fill="[^"]*"', f'fill="{fill}"', tag))
    return "".join(out)
