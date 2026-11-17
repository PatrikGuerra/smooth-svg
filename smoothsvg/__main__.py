import argparse
import sys
from pathlib import Path

from .pipeline import ALLOWED, convert


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="smoothsvg", description="PNG/JPG to simple SVG")
    p.add_argument("input", type=Path, help="image file or folder")
    p.add_argument("-o", "--output", type=Path, help="svg file, or folder for batch")
    a = p.parse_args(argv)

    if a.input.is_dir():
        out = a.output or a.input / "out"
        out.mkdir(parents=True, exist_ok=True)
        files = sorted(f for f in a.input.iterdir() if f.suffix.lower() in ALLOWED)
        pairs = [(f, out / f"{f.stem}.svg") for f in files]
    else:
        pairs = [(a.input, a.output or a.input.with_suffix(".svg"))]

    for src, dst in pairs:
        dst.write_text(convert(src), encoding="utf-8")
        print(f"{src.name} -> {dst} ({dst.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
