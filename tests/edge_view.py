"""Dev helper: find green slivers squeezed between dark and the outside, old vs layered tracer.

python tests/edge_view.py            # the transparent PNG, outside = magenta
python tests/edge_view.py opaque     # same logo flattened on white, outside = white
"""
import io
import sys

import cv2
import numpy as np
import resvg_py
from PIL import Image

from smoothsvg.pipeline import convert_array, load
from smoothsvg.score import flatten

opaque = len(sys.argv) > 1 and sys.argv[1] == "opaque"
img = load("tests/samples/dinodino.png")
if opaque:
    rgb = flatten(img)
    img = np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])
H, W = img.shape[:2]
S = 4
outside_rgb = [255, 255, 255] if opaque else [255, 0, 255]
for tracer in ("vtracer", "layers"):
    svg, _ = convert_array(img, smooth=2, tracer=tracer)
    bg = "#ffffff" if opaque else "#ff00ff"
    png = resvg_py.svg_to_bytes(svg_string=svg, width=W * S, height=H * S, background=bg)
    a = np.asarray(Image.open(io.BytesIO(bytes(png))).convert("RGB")).astype(int)
    outside = np.abs(a - outside_rgb).sum(axis=2) < 60
    dark = np.abs(a - [36, 46, 46]).sum(axis=2) < 60
    k = np.ones((7, 7), np.uint8)
    near = (cv2.dilate(outside.astype(np.uint8), k) > 0) & (cv2.dilate(dark.astype(np.uint8), k) > 0)
    green = (a[..., 1] > a[..., 0] + 30) & (a[..., 1] > a[..., 2] + 30)
    hit = (green & near).astype(np.uint8)  # green with both the outside and dark right beside it
    n, cc, stats, cent = cv2.connectedComponentsWithStats(hit, connectivity=8)
    thin = [(int(stats[j, 4]), tuple(int(v) for v in cent[j] / S)) for j in range(1, n)
            if stats[j, 4] >= 6 and stats[j, 4] < 0.25 * stats[j, 2] * stats[j, 3]]
    print(tracer, "thin green pieces next to the outside:", len(thin), sorted(thin)[-6:])
    Image.fromarray(a.astype(np.uint8)).save(f"out/edge_{tracer}{'_opaque' if opaque else ''}.png")
