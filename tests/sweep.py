"""Dev helper: python tests/sweep.py <smooth> "<dict of extra vtracer opts>" """
import sys
from pathlib import Path

from smoothsvg.pipeline import convert_array, load
from smoothsvg.score import timed_score

smooth = int(sys.argv[1])
extra = eval(sys.argv[2]) if len(sys.argv) > 2 else {}
for f in sorted((Path(__file__).parent / "samples").iterdir()):
    _, s = timed_score(load(f), lambda i: convert_array(i, smooth=smooth, **extra)[0])
    print(f"{f.name:<17}", s)
