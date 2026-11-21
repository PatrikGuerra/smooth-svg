"""Build packaging/smooth-svg.ico from branding/Logo.svg (generated, not versioned)."""
import io
from pathlib import Path

import resvg_py
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SIZES = [16, 32, 48, 256]


def main() -> Path:
    # The logo is 2:3, so render it by height and center it on a square transparent canvas.
    png = bytes(resvg_py.svg_to_bytes(svg_path=str(ROOT / "branding" / "Logo.svg"), height=1024))
    logo = Image.open(io.BytesIO(png)).convert("RGBA")
    side = max(logo.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(logo, ((side - logo.width) // 2, (side - logo.height) // 2))
    out = Path(__file__).with_name("smooth-svg.ico")
    canvas.save(out, format="ICO", sizes=[(s, s) for s in SIZES])
    return out


if __name__ == "__main__":
    print(main())
