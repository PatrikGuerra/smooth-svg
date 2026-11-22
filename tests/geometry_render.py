"""Dev helper: render base vs rings SVG in Edge and save the O, enlarged, to out/.

python tests/geometry_render.py
"""
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from smoothsvg.pipeline import convert_image, load

out = Path("out")
out.mkdir(exist_ok=True)
img = load("branding/Logo+name.png")
svgs = {n: convert_image(img, rings=r)[0] for n, r in (("base", False), ("rings", True))}
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    page = b.new_page(viewport={"width": 1200, "height": 420})
    for name, svg in svgs.items():
        for tag, (x, y, w, h) in {"o": (960, 345, 360, 200), "all": (0, 0, 2172, 724)}.items():
            vb = re.sub(r'viewBox="[^"]*"', "", svg, 1)
            vb = vb.replace("<svg ", f'<svg viewBox="{x} {y} {w} {h}" ', 1)
            vb = re.sub(r'(<svg[^>]*?) width="[^"]*" height="[^"]*"', r'\1 width="100%" height="100%"', vb, 1)
            page.set_content(f'<body style="margin:0;background:#fff">{vb}</body>')
            page.set_viewport_size({"width": 1200, "height": int(1200 * h / w)})
            page.screenshot(path=str(out / f"{tag}_{name}.png"))
    b.close()
