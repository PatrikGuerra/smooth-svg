"""Dev helper: compare tracers (and cleanup settings) on one sample.

python tests/layers_cmp.py lowres.jpg
"""
import sys

from smoothsvg.pipeline import convert_array, load
from smoothsvg.score import score

name = sys.argv[1] if len(sys.argv) > 1 else "lowres.jpg"
img = load(f"tests/samples/{name}")
cases = [
    ("vtracer", {}),
    ("layers", {}),
    ("layers", {"min_area": 6}),
    ("layers", {"min_area": 15}),
    ("layers", {"min_area": 6, "filter_speckle": 3}),
    ("layers", {"min_area": 15, "filter_speckle": 3}),
]
for tracer, kw in cases:
    svg, _ = convert_array(img, smooth=2, tracer=tracer, **kw)
    s = score(img, svg)
    print(f"{tracer:8}{kw!s:40} ssim {s['ssim']}  paths {s['paths']:3}  {s['kb']} KB")
