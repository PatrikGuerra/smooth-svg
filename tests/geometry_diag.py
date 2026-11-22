"""Dev helper: why each blob of the logo is or is not an exact shape. Writes out/geometry_diag.*

python tests/geometry_diag.py [image]
"""
import sys
from pathlib import Path

import cv2
import numpy as np

import smoothsvg.drawing as d
from smoothsvg import geometry as g
from smoothsvg.pipeline import convert_image, load

img = load(sys.argv[1] if len(sys.argv) > 1 else "branding/Logo+name.png")
rows, boxes = [], []
old = d.detect_shapes


def spy(mask, color, e, p, tol, min_area=60, ox=0, oy=0):
    cs, h = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    shape, found = old(mask, color, e, p, tol, min_area, ox, oy)
    for i, c in enumerate(cs):
        if h[0][i][3] != -1 or cv2.contourArea(c) < min_area:
            continue
        x, y, w, hh = cv2.boundingRect(c)
        holes = 0
        k = h[0][i][2]
        while k != -1:
            holes, k = holes + 1, h[0][k][0]
        (cx, cy), (dw, dh), ang = cv2.fitEllipse(c)
        m = g._ell_mask(mask.shape, ((cx, cy), (dw / 2 + .5, dh / 2 + .5), ang))
        iou = g._iou(g._filled(c, mask.shape), m)
        _, f2 = g.detect_geometry(mask, mask, np.zeros_like(mask), color, tol, ox, oy)
        before = any(f"{cx + ox:.1f}" in t for t in found)
        after = bool(f2)
        why = ("ring: " if holes else "") + f"{holes} hole(s), outer ellipse overlap {iou:.3f}"
        if not holes and not before and iou < 1 - tol:
            why = f"outline is not an ellipse (overlap {iou:.3f}); arcs: {'yes' if after else 'no'}"
        rows.append((color, x + ox, y + oy, w, hh, before, after, why))
        boxes.append((x + ox, y + oy, w, hh, before, after))
    return shape, found


d.detect_shapes = spy
svg, _, _ = convert_image(img, ellipses=True, rings=False)
Path("out").mkdir(exist_ok=True)
lines = ["color    x    y    w    h  before after reason"]
lines += [f"{c} {x:4} {y:4} {w:4} {h:4}  {'yes' if b else 'no':<5}  {'yes' if a else 'no':<5} {r}"
          for c, x, y, w, h, b, a, r in rows]
Path("out/geometry_diag.txt").write_text("\n".join(lines), encoding="utf-8")
vis = cv2.cvtColor(np.where(img[..., 3:] > 0, img[..., :3], 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
vis = (vis * 0.5 + 127).astype(np.uint8)
for x, y, w, h, b, a in boxes:
    col = (0, 160, 0) if b else (0, 140, 255) if a else (0, 0, 220)
    cv2.rectangle(vis, (x, y), (x + w, y + h), col, 3)
cv2.imwrite("out/geometry_diag.png", vis)
print("\n".join(lines))
