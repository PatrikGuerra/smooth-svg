# smooth-svg: plan

Turn a PNG or JPG into a **simple** SVG: few colors, few paths, smooth curves
instead of pixel stairs. The target look is the vectorizer.io result in
[this example](https://www.vectorizer.io/images/3cuNlHQuZ5DCfp/canvas-2552x664.html).

Status: P0 to P8 are built and committed. P9 is partly done: `README.md` exists (how to run the
tool and the UI), the automated tests are not written yet. How to run it: see `README.md`.

| Phase | State | Note |
|---|---|---|
| P0 Setup | done | 6 samples, incl. `dinodino.png` and its vectorizer.io SVG in `tests/samples/ref/` |
| P1 Baseline | done | `tests/baseline.json` holds plain vtracer numbers |
| P2 Score | done | `bench`, SSIM, `--compare` |
| P3 UI | done | zoom, wipe, settings. Tested through the API, not by eye |
| P4 Colors | done | k-means in Lab, auto count, color dots. Merge threshold is 10 |
| P5 Smooth | done | per-color mask upscale + blur. Real-ESRGAN was not added (optional) |
| P6 Clean up | done | island removal, scour, remove background |
| P7 Presets | done | auto model, Potrace for drawings. Slider update is about 1 s per 1 MP, not under 1 s |
| P8 Compare | done | DinoDino: SSIM 0.971 vs 0.932, 39 KB vs 78 KB. Goal met |
| P9 Tests and docs | partly | README done. `tests/test_*.py` still to write |

Changes from the plan: zoom is a short custom script, not panzoom. The reference SVG is drawn
through `<img>`. `bench` aligns a cropped reference SVG to the input before scoring.

## 1. What "smart" and "simple" mean here

| Goal | How we measure it |
|---|---|
| Few colors | Output uses N fill colors, N picked automatically (usually 2 to 16) |
| Few paths | Path count and file size (KB) reported after each run |
| Smooth edges | Curves (cubic Bézier), not pixel steps, on edges and corners |
| Sharp where needed | Real corners stay corners (corner angle threshold) |
| Looks like the input | SSIM between the input and the rendered SVG, printed per run |

## 2. What vectorizer.io does (from its options page)

It runs a fixed pipeline. We copy the same idea.

1. **Pick a model**: photo, clipart (few colors), sketch (grays), drawing (black/white).
2. **Palette**: reduce colors first. Fewer colors give a cleaner SVG.
3. **Clean the input**: noise reduction, anti-alias handling, blur, upscaling.
   The upscaling step is the "DLSS-like" part: it makes the image bigger and
   smoother *before* tracing, so the tracer sees soft edges, not stairs.
4. **Trace**: options for roundness, minimum area, blur, overlap, circle detection.
5. **Shrink**: SVG minimization, layer and path splitting.

## 3. Existing projects on GitHub

| Project | What it does | Use it? |
|---|---|---|
| [visioncortex/vtracer](https://github.com/visioncortex/vtracer) | Rust tracer for color and B/W images. Spline mode, corner threshold, speckle filter, layer stacking. Has an official Python wheel (`pip install vtracer`). | **Yes, core tracer** |
| [Potrace](https://potrace.sourceforge.net/) (via `potracer`, pure Python port) | Best smooth curves for 1-color shapes. B/W only. | **Yes, for the "drawing" model** |
| [jerith/depixel](https://github.com/jerith/depixel), [vvanirudh/Pixel-Art](https://github.com/vvanirudh/Pixel-Art), [rsanchezsaez/jkdl-svg](https://github.com/rsanchezsaez/jkdl-svg) | Implementations of the "Depixelizing Pixel Art" paper (Kopf & Lischinski 2011). Turns real pixel art into smooth shapes. | Maybe later, for true pixel art only. Old and slow code. |
| [und3f/vectorize-pixelart](https://github.com/und3f/vectorize-pixelart), [kagof/pixel-perfect-svg](https://github.com/kagof/pixel-perfect-svg) | Pixel art to SVG, but keeps square pixels. | No (opposite of what we want) |
| [Sanderovich2/Pix2Vec](https://github.com/Sanderovich2/Pix2Vec), [ayazmhmd/Image-to-Vector-Converter](https://github.com/ayazmhmd/Image-to-Vector-Converter) | Python CLIs that wrap vtracer with presets. | No, but proof the vtracer route works |
| [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) (ncnn-vulkan binary) | AI upscaler. This is the real "DLSS" option. | Optional step, off by default (heavy) |
| [scour-project/scour](https://github.com/scour-project/scour) | Python SVG minifier. | **Yes, last step** |
| [vtracer discussion #83](https://github.com/visioncortex/vtracer/discussions/83) | Advice: quantize colors before vtracer, set `color_precision=8` so it keeps your palette. | **Yes, we follow it** |

**Decision:** no single repo does the full job. vtracer is the closest one.
We build a small pipeline around it: clean, upscale, reduce colors, trace, shrink.

## 4. Pipeline

```
input.png/jpg
  -> 1. load        (Pillow, flatten alpha or keep it)
  -> 2. classify    (photo / clipart / drawing, by color count and gray check)
  -> 3. denoise     (OpenCV bilateral or median filter, keeps edges)
  -> 4. upscale     (Lanczos x2-x4 + light blur; or Real-ESRGAN if installed)
  -> 5. quantize    (k-means in Lab color, auto N by elbow; merge near colors)
  -> 6. clean areas (drop islands smaller than min area, fill holes)
  -> 7. trace       (vtracer spline mode; potrace for 1-color drawing model)
  -> 8. simplify    (scale coords back down, round to 1-2 decimals, scour)
  -> 9. score       (render SVG with resvg, SSIM vs input, path count, KB)
output.svg + one-line report
```

Why upscale before tracing: on a small image a diagonal edge is a staircase.
After upscale + soft blur, the edge is a smooth ramp. After quantize it is a
clean, smooth boundary. vtracer then fits curves to it, not steps.

Why quantize before tracing: vtracer's own clustering averages colors and
makes many small layers. A fixed palette gives fewer, bigger shapes.

## 5. Models (presets)

| Model | Colors | Upscale | Trace | corner_threshold | filter_speckle |
|---|---|---|---|---|---|
| `drawing` | 1 + bg | x2 | potrace | n/a (alphamax 1.0) | 8 |
| `clipart` (default) | auto, 2-16 | x2-x4 | vtracer spline, stacked | 60 | 8 |
| `pixelart` | exact palette | nearest x8, then blur | vtracer spline | 45 | 4 |
| `photo` | auto, 8-32 | none | vtracer spline | 60 | 16 |

`auto` picks the model from the image: unique color count, gray check, and
whether the image is made of same-size square blocks (pixel art).

## 6. Interface

CLI first. One command:

```
python -m smoothsvg input.png -o output.svg
python -m smoothsvg input.jpg --model clipart --colors 6 --smooth 3
python -m smoothsvg folder/ -o out/            # batch
```

Flags: `--model`, `--colors`, `--smooth` (1-5, maps to upscale + blur + corner
threshold), `--min-area`, `--keep-bg` / `--remove-bg`, `--compare` (writes a
side-by-side PNG: input | SVG render | diff).

### Local UI with real preview and zoom

```
python -m smoothsvg --ui            # opens http://127.0.0.1:8765 in the browser
```

| Part | Choice |
|---|---|
| Server | FastAPI + uvicorn, bound to `127.0.0.1` only |
| Page | One HTML file + one JS file, served by the server. No build step |
| Preview | The browser draws the real SVG output, so zoom stays sharp at any level |
| Zoom | Mouse wheel, drag to pan, double click to reset. [panzoom](https://github.com/timmywil/panzoom) (one vendored file) |
| Compare | Input and SVG side by side. Zoom and pan move both together |
| Wipe mode | Toggle: SVG on top of input, with a slider to wipe between them |
| Input view | `image-rendering: pixelated`, so pixel stairs vs smooth curves are easy to see |
| Settings | Model, colors, smooth, min area, remove background. A change re-runs the pipeline after 300 ms of no input |
| Palette | Color dots. Click one to turn it off (for example, the background) |
| Stats | KB, paths, colors, SSIM, time |
| Actions | Download SVG, copy SVG |
| Theme | Light and dark |

API (all local):

| Route | Does |
|---|---|
| `GET /` | The page |
| `POST /api/convert` | Image file + settings in, `{svg, stats, palette}` out |

The server keeps the last upload and the cached steps in memory, so a slider
change re-runs only from the first changed step. Uploads are size-capped
(20 MB, about 16 megapixels) and only PNG/JPG are accepted.

## 7. Project layout

```
smooth-svg/
  PLAN.md
  README.md
  pyproject.toml
  smoothsvg/
    __main__.py      CLI
    pipeline.py      steps 1-9, one function each
    presets.py       model table above
    classify.py      auto model pick
    score.py         render + SSIM
    server.py        FastAPI app for --ui
    static/
      index.html     UI page
      app.js         upload, settings, synced zoom
      panzoom.min.js vendored
  tests/
    samples/         small PNG/JPG test images (clipart, logo, pixel art, photo)
    test_pipeline.py
```

## 8. Dependencies

All are pip wheels for Windows, Python 3.12. No compiler needed.

- `vtracer` (tracer)
- `potracer` (B/W tracer, pure Python)
- `Pillow`, `numpy`, `opencv-python-headless` (image steps)
- `scikit-learn` (k-means) or OpenCV's own `kmeans` (prefer OpenCV, one less dep)
- `scour` (SVG minify)
- `resvg-py` (render SVG for scoring), `scikit-image` (SSIM)
- `fastapi`, `uvicorn`, `python-multipart` (local UI)
- Optional: `realesrgan-ncnn-vulkan.exe` on PATH for AI upscale

## 9. Build sequence

The order matters. The score comes first and the UI comes second, so every
later step is checked with a number and with your eyes. Each phase ends with
a commit, and the next phase starts only when its "Done when" is true.

```
P0 setup -> P1 baseline -> P2 score -> P3 UI -> P4 quantize -> P5 smooth
        -> P6 cleanup -> P7 presets -> P8 compare -> P9 finish
```

### P0. Setup and inputs

| Task | Output |
|---|---|
| `git init`, `.gitignore`, `pyproject.toml` (Python 3.12, deps from section 8) | Repo |
| `.venv` + `pip install -e .[dev]` (`pytest`, `ruff`, `httpx`) | Working env |
| Collect 6 to 8 samples in `tests/samples/`: logo, clipart, icon, pixel art, line drawing, low-res JPG, photo | Sample set |
| Get the vectorizer.io input and output for 2 or 3 of them into `tests/samples/ref/` | Reference set |

Done when: `python -c "import vtracer, cv2, resvg_py"` works, and the samples are committed.
Needs from you: the samples and the vectorizer.io files.

### P1. Baseline (vtracer only)

| Task | File |
|---|---|
| `load(path) -> RGBA ndarray`: PNG/JPG only, EXIF rotation, size cap | `pipeline.py` |
| `trace(img, opts) -> svg str` with vtracer defaults (spline, stacked) | `pipeline.py` |
| CLI: `python -m smoothsvg in.png -o out.svg`, and a folder for batch | `__main__.py` |

Done when: every sample gives an SVG that opens in the browser. Its KB and path
count are saved as `baseline.json`, the number every later phase must beat.

### P2. Score

| Task | File |
|---|---|
| `render(svg, w, h) -> ndarray` with resvg | `score.py` |
| `score(input, svg) -> {ssim, paths, colors, kb, ms}` | `score.py` |
| `--compare` writes `input | svg | diff` as one PNG | `score.py`, `__main__.py` |
| `python -m smoothsvg bench` runs all samples and prints a table vs `baseline.json` | `__main__.py` |

Done when: `bench` prints one row per sample.

### P3. Local UI (early, to tune by eye)

| Task | File |
|---|---|
| FastAPI app, `127.0.0.1` only, `GET /`, `POST /api/convert` (20 MB cap, PNG/JPG only) | `server.py` |
| Page: drop zone, side-by-side input (pixelated) and SVG | `static/index.html` |
| Synced zoom and pan with panzoom, double click to reset | `static/app.js` |
| Wipe mode slider | `static/app.js` |
| Settings panel that re-runs after 300 ms idle; stats bar; download and copy | `static/app.js` |
| Light and dark theme (follows the system, with a toggle) | `static/index.html` |
| `--ui` flag that starts the server and opens the browser | `__main__.py` |

Done when: you drop a sample, zoom to 800 %, and see the SVG stay sharp, with
both sides moving together.

### P4. Fewer colors

| Task | File |
|---|---|
| k-means in Lab color (OpenCV `kmeans`), fixed N | `pipeline.py` |
| Auto N: smallest N where the color error stops dropping (elbow), 2 to 16 | `pipeline.py` |
| Merge colors closer than a delta-E threshold | `pipeline.py` |
| Pass the palette to vtracer with `color_precision=8` | `pipeline.py` |
| Palette dots in the UI; turning one off removes that layer | `static/app.js`, `server.py` |

Done when: `bench` shows fewer paths than the baseline on clipart and logos,
with SSIM no more than 0.02 lower.

### P5. Smooth edges (the "DLSS" part)

| Task | File |
|---|---|
| Denoise: median 3x3 (clipart), bilateral (photo, JPG) | `pipeline.py` |
| Upscale: Lanczos x2 to x4 + Gaussian blur, before quantize | `pipeline.py` |
| Scale the SVG back to the input size (`viewBox`) | `pipeline.py` |
| `--smooth 1..5` maps to upscale factor, blur radius, `corner_threshold` | `presets.py` |
| Optional: Real-ESRGAN if the exe is on PATH | `pipeline.py` |

Done when: zoomed in the UI, the pixel-art and low-res JPG diagonals are smooth
curves, not stairs, and real corners stay sharp.

### P6. Clean up and shrink

| Task | File |
|---|---|
| Drop color islands under `--min-area` px, fill small holes | `pipeline.py` |
| Round coordinates to 1 or 2 decimals | `pipeline.py` |
| Run scour on the result | `pipeline.py` |
| Remove background: drop the color that touches most of the border | `pipeline.py` |

Done when: `bench` shows a lower KB than P5 on every sample, with the same SSIM (within 0.01).

### P7. Presets, auto mode, B/W tracer

| Task | File |
|---|---|
| The section 5 presets as data | `presets.py` |
| Auto pick: unique colors, gray check, square-block check for pixel art | `classify.py` |
| Potrace for `drawing` (1 color + background) | `pipeline.py` |
| Step cache: keep the output of each step, re-run from the first changed one | `pipeline.py` |
| Model selector in the UI | `static/app.js` |

Done when: `--model auto` picks the expected model for every sample, and a
slider change in the UI updates in under 1 s on a 1 MP clipart.

### P8. Compare with vectorizer.io

| Task | File |
|---|---|
| `bench` adds their KB, paths and SSIM from `tests/samples/ref/` | `__main__.py` |
| Tune the presets until the section 10 goal is met | `presets.py` |
| A UI toggle to show their SVG as the right side | `static/app.js` |

Done when: the section 10 goal is met, or the gap is written down in the README.

### P9. Tests and docs

| Task | File |
|---|---|
| Per sample: SSIM above a floor, paths under a cap, valid XML | `tests/test_pipeline.py` |
| API: `POST /api/convert` returns an SVG; a 25 MB file and a `.gif` are refused | `tests/test_server.py` |
| `classify` picks the expected model per sample | `tests/test_classify.py` |
| README for a first-time reader: install, CLI, UI, models, limits | `README.md` |

Done when: `pytest` and `ruff check` pass.

## 10. How we compare with vectorizer.io

Save the vectorizer.io output for the same input as `tests/samples/ref/*.svg`.
For each sample, print: our KB, their KB, our paths, their paths, our SSIM,
their SSIM. Goal for v1: SSIM within 0.02 of theirs, file size not bigger.

## 11. Risks and open points

- The reference page only shows its options, not the input image. We need the
  original input and their SVG to compare fairly.
- vtracer on large photos is slow and makes big files. The `photo` preset
  caps size first.
- Real-ESRGAN needs a GPU (Vulkan) to be fast. It stays optional.
- True pixel art may need the Kopf-Lischinski method for the best look. We
  try upscale + blur first; add depixel only if results are poor.
- `potracer` is a port of Potrace, which is GPL-2.0. Shipping it makes the
  project GPL. If that is a problem, drop it and use vtracer in B/W mode.
- `potracer` is pure Python and slow on big images. The `drawing` model caps
  the size before tracing.
