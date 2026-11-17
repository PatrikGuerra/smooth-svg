"""Dev helper: count thin slivers of a lower color showing along the outer edge.

Renders the SVG at 3x on magenta. A pixel counts as a sliver if it is a drawing color that the
input does not have at that spot (nearest sample), and it lies within 4 px of the outside.
"""
import io
import sys

import cv2
import numpy as np
from PIL import Image

from smoothsvg.pipeline import convert_array, load
from smoothsvg.score import flatten, resvg_py

name = sys.argv[1] if len(sys.argv) > 1 else "dinodino.png"
img = load(f"tests/samples/{name}")
H, W = img.shape[:2]
ref = flatten(img)
alpha = img[..., 3] >= 128
S = 3
ref_big = np.asarray(Image.fromarray(ref).resize((W * S, H * S), Image.NEAREST)).astype(int)
for tracer in ("vtracer", "layers"):
    svg, _ = convert_array(img, smooth=2, tracer=tracer)
    png = resvg_py.svg_to_bytes(svg_string=svg, width=W * S, height=H * S, background="#ff00ff")
    out = np.asarray(Image.open(io.BytesIO(bytes(png))).convert("RGB")).astype(int)
    outside = (np.abs(out - [255, 0, 255]).sum(axis=2) < 30)
    near = cv2.dilate(outside.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    # input color at that spot is far from the rendered color, in the strip near the outside
    wrong = (np.abs(out - ref_big).sum(axis=2) > 120) & near & ~outside
    # only count spots where the input is dark and the render is green-ish (the reported bug)
    greenish = (out[..., 1] > out[..., 0] + 40) & (out[..., 1] > out[..., 2] + 40)
    dark_in = ref_big.sum(axis=2) < 200
    print(tracer, "slivers (green over dark, near edge):", int((wrong & greenish & dark_in).sum()),
          "| all wrong pixels near edge:", int(wrong.sum()))
