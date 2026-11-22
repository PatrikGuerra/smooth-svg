import hashlib
import io
from pathlib import Path

import numpy as np
import vtracer
from PIL import Image, ImageOps

from .classify import classify
from .drawing import trace_drawing, trace_layers, trace_stacked
from .presets import MODELS, PRESETS
from .quantize import merge_groups, quantize
from .smooth import border_color, denoise, fit_viewbox, level, remove_islands, shrink, upscale

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


_QCACHE: dict = {}  # last few quantize results, so slider moves skip the slowest early steps


def _quantized(img: np.ndarray, colors: int | None, clean: bool, merge_de: float):
    key = (hashlib.blake2b(img.tobytes(), digest_size=16).digest(), img.shape, colors, clean,
           merge_de)
    if key not in _QCACHE:
        if len(_QCACHE) >= 4:
            _QCACHE.pop(next(iter(_QCACHE)))
        _QCACHE[key] = quantize(denoise(img) if clean else img, colors, merge_de=merge_de)
    q, palette = _QCACHE[key]
    return q.copy(), palette  # callers edit q in place


def convert_array(img: np.ndarray, colors: int | None = None, disabled=(), smooth: int = 2,
                  min_area: int | None = None, remove_bg: bool = False, merge_de: float = 10.0,
                  corner: int | None = None, detail: int | None = None, clean: bool = True,
                  tracer: str = "layers", ellipses: bool = True, polygons: bool = False, rings: bool = True,
                  shape_tol: float = 3.0, groups=(), base=None, **opts):
    """Smooth, quantize to a flat palette, clean, drop disabled colors, trace, shrink.

    Returns (svg, palette). min_area and filter_speckle are in original pixels.
    merge_de: colors closer than this (Lab distance) become one. corner: vtracer corner angle,
    default from smooth. detail: curve simplify, higher = fewer points; default from smooth.
    clean: edge-keeping noise filter before the colors are cut (skipped when smooth is 0).
    ellipses, polygons: swap blobs that really are circles/ellipses or straight-edged polygons
    for exact SVG shapes. shape_tol: percent of mismatch allowed (3 means 97% overlap).
    groups: manual merges [([hex, ...], hex)] from quantize.parse_groups, applied after merge_de.
    base: optional list that receives the palette before the groups, so a UI can list the colors to join.
    """
    h, w = img.shape[:2]
    q, palette = _quantized(img, colors, bool(smooth) and clean, merge_de)
    if base is not None:
        base.extend(palette)
    q, palette = merge_groups(q, palette, groups)  # after the cache, so the cache key needs no groups
    pal_rgb = np.array([[int(hx[i:i + 2], 16) for i in (1, 3, 5)] for hx, _ in palette], np.uint8)
    if min_area is None:
        min_area = max(8, round(0.0001 * h * w))  # pixel art sets min_area=1 in its preset
    q = remove_islands(q, pal_rgb, min_area)
    disabled = set(disabled)
    if remove_bg and (bg := border_color(q, palette)):
        disabled.add(bg)
    q, k = upscale(q, pal_rgb, smooth) if len(pal_rgb) else (q, 1)
    for hx in disabled:
        q[(q[..., :3] == [int(hx[i:i + 2], 16) for i in (1, 3, 5)]).all(axis=2), 3] = 0
    # color_precision=8 and layer_difference=0 keep the palette exact (vtracer discussion #83).
    # Coordinates are in upscaled px, so length_threshold grows with k; 1 decimal is enough.
    opts = {
        "color_precision": 8, "layer_difference": 0,
        "corner_threshold": corner or level(smooth)[2], "path_precision": 1,
        "length_threshold": max(4.0, (detail or 3) * float(k)), **opts,
    }
    opts["filter_speckle"] = opts.get("filter_speckle", 1) * k
    if tracer == "potrace":  # experimental: Potrace curves, one stacked layer per color
        body = trace_layers(q, pal_rgb, alphamax=opts.get("alphamax", 1.0))
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{q.shape[1]}" '
               f'height="{q.shape[0]}">{body}</svg>')
    elif tracer == "layers":  # own layering: avoids the lower color peeking out at edges
        vt = {key: opts[key] for key in ("filter_speckle", "corner_threshold", "length_threshold",
                                         "path_precision") if key in opts}
        vt.update(ellipses=ellipses, polygons=polygons, rings=rings, shape_tol=shape_tol / 100)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{q.shape[1]}" '
               f'height="{q.shape[0]}">{trace_stacked(q, pal_rgb, **vt)}</svg>')
    else:
        svg = trace(q, **opts)
    return shrink(fit_viewbox(svg, w, h, q.shape[1], q.shape[0])), palette


def convert_image(img: np.ndarray, model: str = "auto", colors: int | None = None,
                  smooth: int | None = None, **opts):
    """Pick a model (or use the given one), apply its preset, trace.

    Explicit colors/smooth/min_area win over the preset. Returns (svg, palette, used) where
    used = {"model", "smooth", "colors"}, so a UI can show what was chosen.
    """
    if model not in MODELS:
        raise ValueError(f"model must be one of {MODELS}, got {model!r}")
    model = classify(img) if model == "auto" else model
    pre = PRESETS[model]
    smooth = pre["smooth"] if smooth is None else smooth
    colors = pre["colors"] if colors is None else colors
    used = {"model": model, "smooth": smooth, "colors": colors}
    if pre["tracer"] == "potrace":
        svg, palette = trace_drawing(img, smooth, opts.get("disabled", ()),
                                     opts.get("remove_bg", False))
        return svg, palette, used
    if opts.get("min_area") is None and "min_area" in pre:
        opts["min_area"] = pre["min_area"]
    svg, palette = convert_array(img, colors=colors, smooth=smooth, **opts)
    return svg, palette, used


def convert(path: str | Path, **opts) -> str:
    return convert_image(load(path), **opts)[0]