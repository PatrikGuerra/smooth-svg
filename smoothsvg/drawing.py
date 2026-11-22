import re

import cv2
import numpy as np
import potrace

from .geometry import detect_geometry
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


def _grow(mask: np.ndarray, px: int) -> np.ndarray:
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    return cv2.dilate(mask.astype(np.uint8), k) > 0


def trace_stacked(q: np.ndarray, palette_rgb: np.ndarray, **vt) -> str:
    """Trace every connected piece of color as its own shape, stacked big to small.

    Pieces are sorted by their area with holes filled, so a ring comes before what sits inside it.
    A piece is drawn with its holes filled, because what fills them is drawn later, on top. This
    gives plain blobs (a disc with a chart inside is just a disc), and circles and ellipses can
    be recognized. Holes that show the outside (a letter "o") stay open.
    Each shape also reaches 2 px under the later pieces it touches, so no gap shows between
    them. Near the shape's own border that overlap is pulled back, otherwise the two outlines,
    fitted separately, leave a thin line of the lower color along the edge.
    Returns the SVG elements, in the pixel space of q.
    """
    import vtracer

    ellipses = vt.pop("ellipses", False)
    polygons = vt.pop("polygons", False)
    rings = vt.pop("rings", False)
    tol = vt.pop("shape_tol", 0.03)
    inset, collar, bleed = vt.pop("inset", 3), vt.pop("collar", 2), vt.pop("bleed", 2)
    H, W = q.shape[:2]
    rgb, solid = q[..., :3], q[..., 3] >= 128

    ids = np.zeros((H, W), np.int32)  # connected piece number, 0 = none
    color_of, box_of = [-1], [(0, 0, 0, 0)]
    for i, c in enumerate(palette_rgb):
        m = ((rgb == c).all(axis=2) & solid).astype(np.uint8)
        if not m.any():
            continue
        n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        ids[lab > 0] = lab[lab > 0] + len(color_of) - 1
        color_of += [i] * (n - 1)
        box_of += [tuple(int(v) for v in s[:4]) for s in stats[1:]]
    count = len(color_of)
    filled = np.zeros(count, np.int64)
    for cid in range(1, count):
        x, y, w, h = box_of[cid]
        filled[cid] = _filled_area(ids[y:y + h, x:x + w] == cid)
    order = np.argsort(-filled[1:], kind="stable") + 1  # bottom piece first
    rank = np.full(count, -1, np.int32)
    rank[order] = np.arange(len(order))
    rk = rank[ids]  # per pixel: its piece's place in the stack, -1 outside

    out = []
    pad = inset + bleed + 3
    for r, cid in enumerate(order):
        x, y, w, h = box_of[cid]
        x0, y0, x1, y1 = max(x - pad, 0), max(y - pad, 0), min(x + w + pad, W), min(y + h + pad, H)
        rc = rk[y0:y1, x0:x1]
        own, later = rc == r, rc > r
        cs, _ = cv2.findContours(own.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        inside = np.zeros(own.shape, np.uint8)
        cv2.drawContours(inside, cs, -1, 1, -1)
        shape = own | (inside.astype(bool) & later) | (_grow(own, bleed) & later)
        if later.any():
            near_border = _grow(~shape, inset)
            shape &= ~(near_border & later & ~_grow(own, collar))
        fill = _hex(palette_rgb[color_of[cid]])
        found = []
        if ellipses or polygons:
            shape, found = detect_shapes(shape, fill, ellipses, polygons, tol, ox=x0, oy=y0)
        out.extend(found)
        if rings and shape.any():
            shape, found = detect_geometry(shape, own, later, fill, tol, ox=x0, oy=y0)
            out.extend(found)
        if not shape.any():
            continue
        framed = np.pad(shape, 2)  # a margin, so outlines at the crop edge close properly
        svg = vtracer.convert_raw_image_to_svg(
            _mask_png(framed), img_format="png", colormode="binary", mode="spline", **vt)
        for tag in re.findall(r"<path\b[^>]*>", svg):
            tag = re.sub(r'fill="[^"]*"', f'fill="{fill}"', tag)
            tag = re.sub(
                r'translate\(([-\d.]+),([-\d.]+)\)',
                lambda m, a=x0 - 2, b=y0 - 2: f"translate({float(m[1]) + a:g},{float(m[2]) + b:g})",
                tag)
            out.append(tag)
    return "".join(out)

def _iou(a: np.ndarray, b: np.ndarray) -> float:
    union = int((a | b).sum())
    return int((a & b).sum()) / union if union else 0.0


def detect_shapes(mask: np.ndarray, color: str, ellipses: bool, polygons: bool, tol: float,
                  min_area: int = 60, ox: int = 0, oy: int = 0):
    """Find simple filled blobs in a layer mask that are really circles, ellipses or polygons.

    A blob counts when its outline fits the primitive: the overlap (intersection over union) of
    the blob and the primitive is at least 1 - tol. Blobs with holes are left alone.
    Returns (mask without the found blobs, list of SVG elements). ox, oy move the shapes: they\n    are the position of the mask inside the full image.
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
                    element = (f'<circle cx="{cx + ox:.1f}" cy="{cy + oy:.1f}" r="{(rx + ry) / 2:.1f}" '
                               f'fill="{color}"/>')
                else:
                    element = (f'<ellipse cx="{cx + ox:.1f}" cy="{cy + oy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
                               f'transform="rotate({ang:.1f} {cx + ox:.1f} {cy + oy:.1f})" '
                               f'fill="{color}"/>')
        if element is None and polygons:
            poly = cv2.approxPolyDP(c, max(1.0, 0.004 * cv2.arcLength(c, True)), True)
            if 3 <= len(poly) <= 8:
                canvas = np.zeros(shape, np.uint8)
                cv2.fillPoly(canvas, [poly - [x0, y0]], 1)
                if _iou(blob, canvas.astype(bool)) >= 1 - tol / 2:  # straight edges are exact
                    pts = " ".join(f"{p[0][0] + ox},{p[0][1] + oy}" for p in poly)
                    element = f'<polygon points="{pts}" fill="{color}"/>'
        if element:
            found.append(element)
            rest[y0:y0 + shape[0], x0:x0 + shape[1]] &= ~blob
    return rest, found
