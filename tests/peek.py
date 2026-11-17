"""Dev helper: count wrong-colored pixels that are NOT just edge smoothing.

Renders the result at 4x and compares with the quantized input (nearest sample). Pixels within
a few px of a color boundary are ignored (smoothing moves those on purpose). What is left is
mostly slivers: a lower layer's color showing through where an upper layer should cover it.

python tests/peek.py [sample.png]
"""
import io
import sys

import cv2
import numpy as np
import resvg_py
from PIL import Image

from smoothsvg.pipeline import _quantized, convert_array, load

name = sys.argv[1] if len(sys.argv) > 1 else "dinodino.png"
img = load(f"tests/samples/{name}")
H, W = img.shape[:2]
S = 4
q, _ = _quantized(img, None, True, 10.0)
solid = np.asarray(Image.fromarray(q[..., 3]).resize((W * S, H * S), Image.NEAREST)) >= 128
truth = np.asarray(Image.fromarray(q[..., :3]).resize((W * S, H * S), Image.NEAREST)).astype(int)
lab = (truth * [65536, 256, 1]).sum(axis=2)
edge = np.zeros(lab.shape, bool)
for dy, dx in ((0, 1), (1, 0)):
    edge[:-dy or None, :-dx or None] |= lab[:-dy or None, :-dx or None] != lab[dy:, dx:]
edge |= ~solid  # outside the drawing is not compared
band = cv2.dilate(edge.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
for tracer in ("vtracer", "layers"):
    svg, _ = convert_array(img, smooth=2, tracer=tracer)
    png = resvg_py.svg_to_bytes(svg_string=svg, width=W * S, height=H * S, background="#ff00ff")
    out = np.asarray(Image.open(io.BytesIO(bytes(png))).convert("RGB")).astype(int)
    wrong = (np.abs(out - truth).sum(axis=2) > 90) & ~band & solid
    print(f"{tracer:8} wrong pixels away from color boundaries: {int(wrong.sum())}")
    n, _, st, ce = cv2.connectedComponentsWithStats(wrong.astype(np.uint8), connectivity=8)
    big = sorted((int(st[j, 4]), tuple(int(v) for v in ce[j] / S)) for j in range(1, n))[-6:]
    print("   biggest clusters (pixels, x/y in input):", big)
