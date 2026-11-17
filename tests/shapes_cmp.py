"""Dev helper: effect of shape detection on every sample.

python tests/shapes_cmp.py [tolerance_percent]
"""
import sys
from pathlib import Path

from smoothsvg.pipeline import convert_image, load
from smoothsvg.score import score

tol = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
for f in sorted(Path("tests/samples").glob("*.[pj]*g")):
    img = load(f)
    row = [f"{f.name:<14}"]
    for kw in ({"ellipses": False}, {"ellipses": True}, {"ellipses": True, "polygons": True}):
        svg, _, _ = convert_image(img, shape_tol=tol, **kw)
        s = score(img, svg)
        row.append(f"ssim {s['ssim']} {s['kb']:>5}KB shapes {s['shapes']:>2} |")
    print(" ".join(row))
