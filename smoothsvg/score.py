import io
import re
import time

import cv2
import numpy as np
import resvg_py
from PIL import Image
from skimage.metrics import structural_similarity

SSIM_MAX_PX = 500_000


def render(svg: str, w: int, h: int) -> np.ndarray:
    """Render the SVG to an RGB array of size (h, w) on a white background."""
    png = resvg_py.svg_to_bytes(svg_string=svg, width=w, height=h, background="#ffffff")
    out = np.asarray(Image.open(io.BytesIO(bytes(png))).convert("RGB"))
    if out.shape[:2] != (h, w):  # resvg keeps the aspect ratio, so odd sizes can be 1 px off
        out = cv2.resize(out, (w, h), interpolation=cv2.INTER_AREA)
    return out


def flatten(img: np.ndarray) -> np.ndarray:
    """RGBA to RGB over white, same as the render background."""
    a = img[..., 3:4].astype(np.float32) / 255
    return (img[..., :3] * a + 255 * (1 - a)).astype(np.uint8)


def _bbox(rgb: np.ndarray, tol: int = 12):
    """Box around everything that is not (near) white, as x0, y0, x1, y1."""
    ys, xs = np.nonzero((255 - rgb.astype(int)).max(axis=2) > tol)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def render_aligned(svg: str, ref: np.ndarray) -> np.ndarray:
    """Render an SVG that was cropped to its content, and put it where the content of ref is.

    Other tools (vectorizer.io) crop the SVG to the drawing, so a plain render would not line up.
    """
    h, w = ref.shape[:2]
    x0, y0, x1, y1 = _bbox(ref)
    bw, bh = x1 - x0, y1 - y0
    big = resvg_py.svg_to_bytes(svg_string=svg, width=bw * 2, background="#ffffff")
    big = np.asarray(Image.open(io.BytesIO(bytes(big))).convert("RGB"))
    a, b, c, d = _bbox(big)
    crop = cv2.resize(big[b:d, a:c], (bw, bh), interpolation=cv2.INTER_AREA)
    out = np.full((h, w, 3), 255, np.uint8)
    out[y0:y1, x0:x1] = crop
    return out


def score(img: np.ndarray, svg: str, ms: float = 0.0, aligned: bool = False) -> dict:
    h, w = img.shape[:2]
    # SSIM on images over 0.5 MP is measured at reduced size, to keep the UI fast
    f = min(1.0, (SSIM_MAX_PX / (h * w)) ** 0.5)
    sw, sh = max(1, round(w * f)), max(1, round(h * f))
    ref = flatten(img) if f == 1 else cv2.resize(flatten(img), (sw, sh), interpolation=cv2.INTER_AREA)
    out = render_aligned(svg, ref) if aligned else render(svg, sw, sh)
    tags = re.findall(r"<(?:path|circle|ellipse|polygon)\b[^>]*>", svg)
    fills = set(re.findall(r'fill="(#[0-9a-fA-F]{3,8})"', svg))
    return {
        "ssim": round(float(structural_similarity(ref, out, channel_axis=2)), 4),
        "paths": len(tags),
        "shapes": len(re.findall(r"<(?:circle|ellipse|polygon)\b", svg)),
        "colors": len(fills | ({"#000"} if any("fill=" not in p for p in tags) else set())),
        "kb": round(len(svg.encode()) / 1024, 1),
        "ms": round(ms),
    }


def timed_score(img: np.ndarray, fn) -> tuple[str, dict]:
    t = time.perf_counter()
    svg = fn(img)
    return svg, score(img, svg, (time.perf_counter() - t) * 1000)


def compare_png(img: np.ndarray, svg: str, path) -> None:
    """Write input | svg | diff side by side."""
    h, w = img.shape[:2]
    ref, out = flatten(img), render(svg, w, h)
    diff = 255 - np.abs(ref.astype(int) - out.astype(int)).clip(0, 255).astype(np.uint8)
    Image.fromarray(np.hstack([ref, out, diff])).save(path)
