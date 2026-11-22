"""Local error check: the logo SVG may not get worse in any tile than the stored baseline.

SSIM and total error average over the whole image, so a lump in one corner of the cup hides
behind small gains elsewhere. This counts wrong pixels per 32 px tile (render at 2x, compared
with the original) and fails on any tile that grew past its baseline.

Rewrite the baseline from a known good SVG:  python tests/shape_tiles.py path/to/good.svg
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

from smoothsvg.pipeline import load
from smoothsvg.score import flatten, render

LOGO = Path(__file__).parent.parent / "branding" / "Logo+name.png"
BASE = Path(__file__).parent / "shape_tiles.json"
K, TILE, DIFF = 2, 32, 25  # render scale, tile size in source px, gray-level difference that counts


def tile_errors(svg: str, img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    ref = cv2.resize(flatten(img), (w * K, h * K), interpolation=cv2.INTER_CUBIC)
    bad = (np.abs(render(svg, w * K, h * K).astype(np.int16) - ref).max(axis=2) > DIFF)
    t = TILE * K
    bad = np.pad(bad, ((0, -bad.shape[0] % t), (0, -bad.shape[1] % t)))
    return bad.reshape(bad.shape[0] // t, t, bad.shape[1] // t, t).sum(axis=(1, 3))


if __name__ == "__main__":
    BASE.write_text(json.dumps(tile_errors(Path(sys.argv[1]).read_text(), load(LOGO)).tolist()))
