import io
from pathlib import Path

import numpy as np
import vtracer
from PIL import Image, ImageOps

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


def convert(path: str | Path, **opts) -> str:
    return trace(load(path), **opts)
