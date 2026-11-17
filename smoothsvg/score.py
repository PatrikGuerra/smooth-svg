import io
import re
import time

import numpy as np
import resvg_py
from PIL import Image
from skimage.metrics import structural_similarity


def render(svg: str, w: int, h: int) -> np.ndarray:
    """Render the SVG to an RGB array of size (h, w) on a white background."""
    png = resvg_py.svg_to_bytes(svg_string=svg, width=w, height=h, background="#ffffff")
    return np.asarray(Image.open(io.BytesIO(bytes(png))).convert("RGB"))


def flatten(img: np.ndarray) -> np.ndarray:
    """RGBA to RGB over white, same as the render background."""
    a = img[..., 3:4].astype(np.float32) / 255
    return (img[..., :3] * a + 255 * (1 - a)).astype(np.uint8)


def score(img: np.ndarray, svg: str, ms: float = 0.0) -> dict:
    h, w = img.shape[:2]
    ref, out = flatten(img), render(svg, w, h)
    tags = re.findall(r"<path\b[^>]*>", svg)
    fills = set(re.findall(r'fill="(#[0-9a-fA-F]{3,8})"', svg))
    return {
        "ssim": round(float(structural_similarity(ref, out, channel_axis=2)), 4),
        "paths": len(tags),
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
