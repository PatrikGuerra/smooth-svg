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

    ellipses = vt.pop("ellipses", False)
    polygons = vt.pop("polygons", False)
    tol = vt.pop("shape_tol", 0.03)
    inset = vt.pop("inset", 3)
    keep_collar = vt.pop("collar", 2)  # keep this much of the upper layer around its neighbour
    out = []
    for r, i in enumerate(order):
        mask = rk >= r
        if r < len(order) - 1:
            upper = rk > r
            # pixels of the upper layers that lie close to the border of this layer
            near_edge = grow(~mask, inset)
            mask = mask & ~(near_edge & upper & ~grow(rk == r, keep_collar))
        own = rk == r
        # Drop pieces made only of upper colors: the layers above already draw them.
        _, lab = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
        mask = np.isin(lab, np.unique(lab[own & mask])) & (lab > 0)
        fill = _hex(palette_rgb[i])
        shapes = []
        if ellipses or polygons:
            mask, shapes = detect_shapes(mask, fill, ellipses, polygons, tol)
        svg = vtracer.convert_raw_image_to_svg(
            _mask_png(mask), img_format="png", colormode="binary", mode="spline", **vt)
        out.extend(shapes)
        for tag in re.findall(r"<path\b[^>]*>", svg):
            out.append(re.sub(r'fill="[^"]*"', f'fill="{fill}"', tag))
    return "".join(out)


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    union = int((a | b).sum())
    return int((a & b).sum()) / union if union else 0.0


def detect_shapes(mask: np.ndarray, color: str, ellipses: bool, polygons: bool, tol: float,
                  min_area: int = 60):
    """Find simple filled blobs in a layer mask that are really circles, ellipses or polygons.

    A blob counts when its outline fits the primitive: the overlap (intersection over union) of
    the blob and the primitive is at least 1 - tol. Blobs with holes are left alone.
    Returns (mask without the found blobs, list of SVG elements).
    """
    m8 = mask.astype(np.uint8)
    contours, hier = cv2.findContours(m8, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        return mask, []
    rest, found = mask.copy(), []
    for i, c in enumerate(contours):
        if hier[0][i][3] != -1 or hier[0][i][2] != -1:  # a hole itself, or has holes
            continue
        area = cv2.contourArea(c)
        if area < min_area or len(c) < 8:
            continue
        x, y, w, h = cv2.boundingRect(c)
        x0, y0 = max(x - 2, 0), max(y - 2, 0)
        shape = (min(y + h + 2, mask.shape[0]) - y0, min(x + w + 2, mask.shape[1]) - x0)
        shifted = c - [x0, y0]
        blob = np.zeros(shape, np.uint8)
        cv2.drawContours(blob, [shifted], -1, 1, -1)
        blob = blob.astype(bool)
        element = None
        if ellipses:
            (cx, cy), (dw, dh), ang = cv2.fitEllipse(c)
            canvas = np.zeros(shape, np.uint8)
            q = 16  # sub-pixel precision for the test raster
            cv2.ellipse(canvas, (round((cx - x0) * q), round((cy - y0) * q)),
                        (round(dw / 2 * q), round(dh / 2 * q)), ang, 0, 360, 1, -1,
                        shift=4)
            if _iou(blob, canvas.astype(bool)) >= 1 - tol:
                rx, ry = dw / 2, dh / 2
                if abs(rx - ry) <= 0.04 * max(rx, ry):
                    element = (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{(rx + ry) / 2:.1f}" '
                               f'fill="{color}"/>')
                else:
                    element = (f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
                               f'transform="rotate({ang:.1f} {cx:.1f} {cy:.1f})" fill="{color}"/>')
        if element is None and polygons:
            poly = cv2.approxPolyDP(c, max(1.0, 0.004 * cv2.arcLength(c, True)), True)
            if 3 <= len(poly) <= 8:
                canvas = np.zeros(shape, np.uint8)
                cv2.fillPoly(canvas, [poly - [x0, y0]], 1)
                if _iou(blob, canvas.astype(bool)) >= 1 - tol / 2:  # straight edges are exact
                    pts = " ".join(f"{p[0][0]},{p[0][1]}" for p in poly)
                    element = f'<polygon points="{pts}" fill="{color}"/>'
        if element:
            found.append(element)
            rest[y0:y0 + shape[0], x0:x0 + shape[1]] &= ~blob
    return rest, found
