import argparse
import json
import sys
from pathlib import Path

from .pipeline import ALLOWED, convert_array, load
from .score import compare_png, timed_score

SAMPLES = Path(__file__).parent.parent / "tests" / "samples"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["bench"]:
        return bench(Path(argv[1]) if len(argv) > 1 else SAMPLES)
    if argv[:1] == ["--ui"]:
        import threading
        import webbrowser

        import uvicorn

        url = "http://127.0.0.1:8765"
        threading.Timer(1.0, webbrowser.open, args=[url]).start()
        uvicorn.run("smoothsvg.server:app", host="127.0.0.1", port=8765)
        return 0
    p = argparse.ArgumentParser(prog="smoothsvg", description="PNG/JPG to simple SVG")
    p.add_argument("input", type=Path, help="image file or folder (or: bench [folder])")
    p.add_argument("-o", "--output", type=Path, help="svg file, or folder for batch")
    p.add_argument("--compare", action="store_true", help="also write <name>.compare.png")
    a = p.parse_args(argv)

    if a.input.is_dir():
        out = a.output or a.input / "out"
        out.mkdir(parents=True, exist_ok=True)
        files = sorted(f for f in a.input.iterdir() if f.suffix.lower() in ALLOWED)
        pairs = [(f, out / f"{f.stem}.svg") for f in files]
    else:
        pairs = [(a.input, a.output or a.input.with_suffix(".svg"))]

    for src, dst in pairs:
        img = load(src)
        svg = convert_array(img)[0]
        dst.write_text(svg, encoding="utf-8")
        print(f"{src.name} -> {dst} ({dst.stat().st_size / 1024:.1f} KB)")
        if a.compare:
            compare_png(img, svg, dst.with_suffix(".compare.png"))
    return 0


def bench(folder: Path) -> int:
    """Convert every sample, print a table, and flag changes vs baseline.json."""
    base_file = folder.parent / "baseline.json"
    base = json.loads(base_file.read_text()) if base_file.exists() else {}
    rows, cur = [], {}
    for f in sorted(f for f in folder.iterdir() if f.suffix.lower() in ALLOWED):
        _, s = timed_score(load(f), lambda i: convert_array(i)[0])
        cur[f.name] = s
        b = base.get(f.name)
        rows.append((f.name, s, f"{s['kb'] - b['kb']:+.1f} KB, {s['ssim'] - b['ssim']:+.3f} ssim"
                     if b else "(no baseline)"))
    print(f"{'sample':<18}{'ssim':>7}{'paths':>7}{'colors':>7}{'KB':>8}{'ms':>7}  vs baseline")
    for n, s, d in rows:
        print(f"{n:<18}{s['ssim']:>7}{s['paths']:>7}{s['colors']:>7}{s['kb']:>8}{s['ms']:>7}  {d}")
    if not base:
        base_file.write_text(json.dumps(cur, indent=1))
        print(f"saved {base_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
