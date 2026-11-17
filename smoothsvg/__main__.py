import argparse
import json
import sys
from pathlib import Path

from .pipeline import ALLOWED, convert_image, load
from .presets import MODELS
from .score import compare_png, score, timed_score

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
    p.add_argument("--model", default="auto", choices=MODELS)
    p.add_argument("--smooth", type=int, choices=range(6), help="0 off, 5 most (default: by model)")
    p.add_argument("--colors", type=int, help="number of colors (default: auto)")
    p.add_argument("--min-area", type=int, help="drop color islands under N pixels")
    p.add_argument("--remove-bg", action="store_true", help="make the background transparent")
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
        svg, _, used = convert_image(img, a.model, colors=a.colors, smooth=a.smooth,
                                     min_area=a.min_area, remove_bg=a.remove_bg)
        dst.write_text(svg, encoding="utf-8")
        print(f"{src.name} [{used['model']}] -> {dst} ({dst.stat().st_size / 1024:.1f} KB)")
        if a.compare:
            compare_png(img, svg, dst.with_suffix(".compare.png"))
    return 0


def _vs_reference(img, mine: dict, ref_file: Path) -> str:
    """Compare with a saved vectorizer.io SVG. Goal: ssim within 0.02 and KB not bigger."""
    if not ref_file.exists():
        return "no reference file"
    r = score(img, ref_file.read_text(encoding="utf-8"), aligned=True)
    ok = mine["ssim"] >= r["ssim"] - 0.02 and mine["kb"] <= r["kb"]
    return (f"theirs ssim {r['ssim']}, {r['paths']} paths, {r['kb']} KB -> "
            f"{'GOAL MET' if ok else 'goal missed'}")


def bench(folder: Path) -> int:
    """Convert every sample, print a table, and flag changes vs baseline.json."""
    base_file = folder.parent / "baseline.json"
    base = json.loads(base_file.read_text()) if base_file.exists() else {}
    rows, cur = [], {}
    for f in sorted(f for f in folder.iterdir() if f.suffix.lower() in ALLOWED):
        img = load(f)
        _, s = timed_score(img, lambda i: convert_image(i)[0])
        cur[f.name] = s
        b = base.get(f.name)
        d = f"{s['kb'] - b['kb']:+.1f} KB, {s['ssim'] - b['ssim']:+.3f} ssim" if b else "-"
        rows.append((f.name, s, d, _vs_reference(img, s, folder / "ref" / f"{f.stem}.svg")))
    print(f"{'sample':<18}{'ssim':>7}{'paths':>7}{'colors':>7}{'KB':>8}{'ms':>7}  "
          f"{'vs baseline':<22}vs vectorizer.io (ref/<name>.svg)")
    for n, s, d, r in rows:
        print(f"{n:<18}{s['ssim']:>7}{s['paths']:>7}{s['colors']:>7}{s['kb']:>8}{s['ms']:>7}  "
              f"{d:<22}{r}")
    if not base:
        base_file.write_text(json.dumps(cur, indent=1))
        print(f"saved {base_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
