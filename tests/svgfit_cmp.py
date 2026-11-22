"""Dev helper: geometry fit off/on on the logo and every sample.

python tests/svgfit_cmp.py [tolerance_px]
"""
import re
import sys
import time
from pathlib import Path

from smoothsvg.pipeline import convert_image, load
from smoothsvg.score import score

tol = float(sys.argv[1]) if len(sys.argv) > 1 else 0.35
files = [Path("branding/Logo+name.png"), *sorted(Path("tests/samples").glob("*.[pj]*g"))]
for f in files:
    img = load(f)
    row = [f"{f.name:<14}"]
    for on in (False, True):
        t = time.perf_counter()
        svg, _, _ = convert_image(img, geometry_fit=on, fit_tol=tol)
        ms = (time.perf_counter() - t) * 1000
        s = score(img, svg)
        arcs = len(re.findall(r"[Aa]\d", svg))
        row.append(f"ssim {s['ssim']} paths {s['paths']:>3} {s['kb']:>5}KB shapes {s['shapes']:>2} "
                   f"arcs {arcs:>3} {ms:>5.0f}ms |")
    print(" ".join(row))
