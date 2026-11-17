"""Generate synthetic samples into tests/samples. Real images can be dropped there too."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).parent / "samples"
OUT.mkdir(exist_ok=True)


def logo():
    im = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(im)
    d.ellipse((40, 40, 260, 260), fill=(220, 40, 40))
    d.polygon([(200, 60), (360, 120), (300, 260)], fill=(30, 90, 200))
    d.rectangle((150, 150, 330, 200), fill=(250, 200, 30))
    im.save(OUT / "logo.png")


def pixelart():
    heart = [
        "..###...###..",
        ".#####.#####.",
        "#############",
        "#############",
        ".###########.",
        "..#########..",
        "...#######...",
        "....#####....",
        ".....###.....",
        "......#......",
    ]
    im = Image.new("RGB", (13, 10), "white")
    for y, row in enumerate(heart):
        for x, c in enumerate(row):
            if c == "#":
                im.putpixel((x, y), (210, 30, 40))
    for x, y in ((1, 1), (2, 1), (1, 2)):
        im.putpixel((x, y), (255, 154, 162))
    im.save(OUT / "pixelart.png")  # tiny, real pixel art


def lowres_jpg():
    im = Image.new("RGB", (120, 90), (240, 240, 240))
    d = ImageDraw.Draw(im)
    d.ellipse((10, 10, 70, 70), fill=(20, 140, 60))
    d.line((0, 89, 119, 0), fill=(200, 60, 20), width=6)
    im.save(OUT / "lowres.jpg", quality=40)


def drawing():
    im = Image.new("L", (400, 300), 255)
    d = ImageDraw.Draw(im)
    d.ellipse((60, 40, 340, 260), outline=0, width=6)
    d.line((60, 150, 340, 150), fill=0, width=5)
    d.arc((120, 80, 280, 220), 20, 200, fill=0, width=5)
    im.save(OUT / "drawing.png")


def photo():
    rng = np.random.default_rng(2)
    y, x = np.mgrid[0:300, 0:400]
    r = (128 + 100 * np.sin(x / 40)).astype(np.uint8)
    g = (128 + 100 * np.cos(y / 30)).astype(np.uint8)
    b = (rng.normal(128, 25, (300, 400))).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(np.dstack([r, g, b])).filter(ImageFilter.GaussianBlur(2))
    im.save(OUT / "photo.jpg", quality=85)


if __name__ == "__main__":
    for f in (logo, pixelart, lowres_jpg, drawing, photo):
        f()
    print(sorted(p.name for p in OUT.iterdir()))
