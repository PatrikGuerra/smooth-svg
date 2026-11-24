"""Dev helper: one conversion, then time, peak memory, SSIM and size.

python tests/mem_probe.py IMAGE OUT.svg [--soft] [--cap-mp MP] [--smooth N] [--scale F]
--cap-mp: use a fixed cap in MP (the old one was 2.5) instead of the free memory. --scale: resize the input first, to get more MP.
Peak memory is the Windows peak working set (psutil), so run one conversion per process.
"""
import argparse
import json
import time
from pathlib import Path

import cv2
import psutil

from smoothsvg import smooth as sm
from smoothsvg.pipeline import convert_array, load
from smoothsvg.score import score

ap = argparse.ArgumentParser()
ap.add_argument("image")
ap.add_argument("out")
ap.add_argument("--soft", action="store_true")
ap.add_argument("--cap-mp", type=float)
ap.add_argument("--smooth", type=int, default=2)
ap.add_argument("--scale", type=float, default=1.0)
a = ap.parse_args()
if a.cap_mp:
    sm.max_work_px = lambda: int(a.cap_mp * 1e6)
img = load(a.image)
if a.scale != 1:
    img = cv2.resize(img, None, fx=a.scale, fy=a.scale, interpolation=cv2.INTER_CUBIC)
pre: dict = {}
t = time.perf_counter()
svg, palette = convert_array(img, smooth=a.smooth, soft=a.soft, pre=pre)
sec = time.perf_counter() - t
Path(a.out).write_text(svg, encoding="utf-8")
peak = psutil.Process().memory_info().peak_wset / 2**20
up = pre["upscaled"].shape
s = score(img, svg, sec * 1000)
print(json.dumps({"k": pre["k"], "mp_in": round(img.shape[0] * img.shape[1] / 1e6, 2),
                  "mp_up": round(up[0] * up[1] / 1e6, 2), "sec": round(sec, 1),
                  "peak_mb": round(peak), "mb_per_mp_up": round(peak / (up[0] * up[1] / 1e6)),
                  "ssim": s["ssim"], "kb": s["kb"], "paths": s["paths"]}))
