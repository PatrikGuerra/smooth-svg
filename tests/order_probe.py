"""Dev helper: layer order and holes per layer for a sample."""
import sys

import cv2
import numpy as np

from smoothsvg.drawing import _filled_area
from smoothsvg.pipeline import _quantized, load

path = sys.argv[1] if len(sys.argv) > 1 else "branding/Logo+name.png"
img = load(path)
q, pal = _quantized(img, None, True, 10.0)
rgb = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h, _ in pal], np.uint8)
solid = q[..., 3] >= 128
rows = []
for i, (hx, share) in enumerate(pal):
    m = (q[..., :3] == rgb[i]).all(axis=2) & solid
    cs, hier = cv2.findContours(m.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    holes = sum(1 for h in hier[0] if h[3] != -1) if hier is not None else 0
    outers = len(cs) - holes
    rows.append((_filled_area(m), hx, int(m.sum()), outers, holes))
for filled, hx, area, outers, holes in sorted(rows, reverse=True):
    print(f"{hx} filled {filled:>8} own {area:>8} components {outers:>3} holes {holes:>3}")
