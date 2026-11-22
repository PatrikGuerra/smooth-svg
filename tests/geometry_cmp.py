"""Dev helper: rings and arcs on/off on the logo and every sample.

python tests/geometry_cmp.py [tolerance_percent]
"""
import re
import sys
from pathlib import Path

from smoothsvg.pipeline import convert_image, load
from smoothsvg.score import score

tol = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
files = [Path("branding/Logo+name.png"), *sorted(Path("tests/samples").glob("*.[pj]*g"))]
for f in files:
    img = load(f)
    row = [f"{f.name:<14}"]
    for rings in (False, True):
        svg, _, _ = convert_image(img, shape_tol=tol, rings=rings)
        s = score(img, svg)
        arcs = len(re.findall(r"[Aa]\d", svg))
        row.append(f"ssim {s['ssim']} paths {s['paths']:>3} {s['kb']:>5}KB shapes {s['shapes']:>2} arcs {arcs:>3} |")
    print(" ".join(row))
