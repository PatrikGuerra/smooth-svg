"""Dev helper: how min_area affects the low-res JPG, and what scour does to fills."""
import re

from smoothsvg.pipeline import convert_array, load
from smoothsvg.score import score

img = load("tests/samples/lowres.jpg")
for m in (1, 5, 15, 30, 60):
    svg, p = convert_array(img, min_area=m)
    s = score(img, svg)
    print(m, len(p), s["paths"], s["kb"], s["ssim"])

svg, _ = convert_array(load("tests/samples/drawing.png"))
print(re.findall(r"fill[=:][^ ;>]+", svg)[:6])
print(svg[:300])
