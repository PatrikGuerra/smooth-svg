import io
from pathlib import Path

import numpy as np
import vtracer
from PIL import Image, ImageOps

from .quantize import quantize

ALLOWED = {".png", ".jpg", ".jpeg"}
MAX_PIXELS = 16_000_000


def _decode(im: Image.Image) -> np.ndarray:
    if im.width * im.height > MAX_PIXELS:
        raise ValueError(f"image too large ({im.width}x{im.height}), max {MAX_PIXELS} px")
    return np.asarray(ImageOps.exif_transpose(im).convert("RGBA"))


def load(path: str | Path) -> np.ndarray:
    """Read a PNG/JPG as an RGBA array. Flattens nothing; honors EXIF rotation."""
    path = Path(path)
    if path.suffix.lower() not in ALLOWED:
        raise ValueError(f"only PNG/JPG accepted, got {path.suffix!r}")
    with Image.open(path) as im:
        return _decode(im)


def load_bytes(data: bytes) -> np.ndarray:
    """Same as load, for uploads. Checks the real format, not the file name."""
    with Image.open(io.BytesIO(data)) as im:
        if im.format not in ("PNG", "JPEG"):
            raise ValueError(f"only PNG/JPG accepted, got {im.format}")
        return _decode(im)


def trace(img: np.ndarray, **opts) -> str:
    """Trace an RGBA array to an SVG string with vtracer (spline, stacked)."""
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="PNG")
    return vtracer.convert_raw_image_to_svg(
        buf.getvalue(), img_format="png", colormode="color",
        hierarchical="stacked", mode="spline", **opts,
    )


def convert_array(img: np.ndarray, colors: int | None = None, disabled=(), **opts):
    """Quantize to a flat palette, drop disabled colors, trace. Returns (svg, palette)."""
    q, palette = quantize(img, colors)
    for hx, _ in palette:
        if hx in disabled:
            q[(q[..., :3] == [int(hx[i:i + 2], 16) for i in (1, 3, 5)]).all(axis=2), 3] = 0
    # color_precision=8 and layer_difference=0 keep the palette exact (vtracer discussion #83)
    opts = {"color_precision": 8, "layer_difference": 0, **opts}
    return trace(q, **opts), palette


def convert(path: str | Path, **opts) -> str:
    return convert_array(load(path), **opts)[0]
