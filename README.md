<p align="center">
  <img src="branding/Logo%2Bname.svg" alt="smooth-svg" width="640">
</p>

<p align="center">
  <b>Turn a PNG or JPG into a small, smooth SVG.</b><br>
  Few colors. Few paths. Round curves instead of pixel stairs. Exact circles where the picture has circles.
</p>

<p align="center">
  <img alt="License: GPL-3.0-or-later" src="https://img.shields.io/badge/license-GPL--3.0--or--later-green">
  <img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-blue">
  <img alt="Runs on your computer" src="https://img.shields.io/badge/runs-on%20your%20computer-lightgrey">
</p>

> The logo above is a good test. It started as a 558 KB PNG. It was converted to SVG **by this tool**
> (`branding/Logo+name.svg`, 25 KB, 36 paths, 9 colors).

![The web page: the PNG on the left, the SVG on the right](docs/screenshots/ui-overview.png)

## Why this exists

Tracing tools usually give you one of two things. Either thousands of tiny paths in hundreds of
colors, or a rough shape with lumpy edges. smooth-svg aims for what a designer would draw by hand:
a handful of flat colors, smooth outlines, and real circles.

Same picture, three results. The logo of this project (2172 x 724 px):

| Tool | Paths | Colors | Size | Similarity to the PNG (SSIM, 1.0 = identical) |
|---|---|---|---|---|
| The original PNG | n/a | n/a | 558 KB | 1.000 |
| vtracer with its defaults | 2144 | 305 | 610 KB | 0.897 |
| **smooth-svg** | **36** | **9** | **25 KB** | **0.985** |

## Try it in 30 seconds

```powershell
git clone https://github.com/PatrikGuerra/smooth-svg.git
cd smooth-svg
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m smoothsvg --ui
```

Your browser opens at <http://127.0.0.1:8765>. Drop a PNG or JPG on the page. That is all.
The server listens on this computer only, and nothing is uploaded. Press `Ctrl+C` to stop it.

Windows with Python 3.12 is what it was built and tested on. Every dependency installs as a
ready-made wheel, so no compiler is needed.

## See the difference

The web page puts the input and the SVG side by side. Both move together when you zoom. The input is
drawn with square pixels, so you can see the stairs. The SVG stays sharp at any zoom.

![Zoomed in: pixel stairs on the left, smooth curves on the right](docs/screenshots/ui-zoom.png)

*Zoomed to the lid of the cup. Left: the PNG, with its pixel edges. Right: the SVG.*

Wipe mode puts the SVG over the input, with a slider to sweep between them.

![Wipe mode: the PNG on the left of the line, the SVG on the right](docs/screenshots/ui-wipe.png)

## What you can do

- **Pick a model** (`auto`, `clipart`, `drawing`, `pixelart`, `photo`) or let the tool choose.
- **Change colors, smoothness, corners and small details** and see the result in about a second.
- **Click a color dot** to remove that color layer. Or remove the background in one click.
- **Swap circles and ellipses for exact shapes**, and polygons for exact straight edges.
- **Compare with another tool**: load its SVG and flip between the two.
- **Download or copy the SVG.** Or use the command line for a whole folder.

## Contents

1. [The web page](#the-web-page)
2. [The command line](#the-command-line)
3. [Models](#models)
4. [How it works](#how-it-works)
5. [What was changed and why](#what-was-changed-and-why)
6. [Results](#results)
7. [Project layout](#project-layout)
8. [Developer tools](#developer-tools)
9. [Limits](#limits)
10. [Not done yet](#not-done-yet)
11. [License](#license)

## The web page

Run `python -m smoothsvg --ui`. Open an image or drop a PNG/JPG on the page (up to 20 MB).

| Control | What it does |
|---|---|
| Mouse wheel, drag, double click | Zoom, move, fit. Both sides move together |
| Wipe mode | The SVG over the input, with a slider to sweep between them |
| Model | `auto` (default), `clipart`, `drawing`, `pixelart`, `photo` |
| Remove background | Makes the color on the border transparent |
| Clean noise | Edge-keeping filter before the colors are cut. Turn it off for crisp pixel art |
| Colors | Number of colors. `auto` lets the tool decide |
| Merge similar colors | Colors closer than this become one. Higher gives fewer colors. 10 keeps two greens apart |
| Color dots | Click a dot to remove that color layer |
| Smooth (0 to 5) | Rounder edges and fewer small details when higher |
| Corners | Angle above which a point stays a sharp corner. `auto` follows Smooth |
| Curve simplify | Higher gives fewer curve points and smaller files. Matters most on big images |
| Min speckle | Drops tiny blobs, in input pixels |
| Min area (px) | Merges color islands smaller than this into their surroundings. `auto` scales with the image |
| Circles & ellipses | Blobs that are circles or ellipses become exact `<circle>` and `<ellipse>`. On by default |
| Straight-edge polygons | Blobs with 3 to 8 straight edges become `<polygon>`. Off by default |
| Shape tolerance (1 to 15 %) | How far a blob may differ from the shape and still be swapped. Default 3 |
| Load reference SVG | Loads an SVG from another tool. "Show: mine / reference" swaps it into the right side |
| Download / Copy SVG | Saves or copies the result |

The first conversion of an image uses the model's own colors and smoothness and shows them in the
controls. After that, the controls are yours. A spinner shows over the preview and in the status bar
while the server works. Only the newest request ends it, so dragging a slider fast does not flicker.
The status bar shows size, paths, colors, shapes found, SSIM and time.

The `drawing` model uses Potrace and ignores Colors, Merge, Corners, Curve simplify, Min area and
the shape controls.

## The command line

```powershell
.\.venv\Scripts\python.exe -m smoothsvg input.png -o output.svg
.\.venv\Scripts\python.exe -m smoothsvg input.jpg --model clipart --colors 6 --smooth 3
.\.venv\Scripts\python.exe -m smoothsvg folder\ -o out\          # every PNG/JPG in a folder
.\.venv\Scripts\python.exe -m smoothsvg logo.png --remove-bg --compare
.\.venv\Scripts\python.exe -m smoothsvg bench                    # quality table, see below
```

| Option | Meaning |
|---|---|
| `-o` | Output SVG, or an output folder |
| `--model` | `auto`, `clipart`, `drawing`, `pixelart`, `photo` |
| `--colors N` | Number of colors (default: auto) |
| `--smooth 0..5` | Edge smoothing (default: by model) |
| `--min-area N` | Merge color islands smaller than N pixels |
| `--remove-bg` | Transparent background |
| `--compare` | Also writes `<name>.compare.png`: input, SVG, difference |

`bench` converts every image in `tests\samples\` and prints one row each: SSIM, paths, colors, KB,
time, the change against `tests\baseline.json` (plain vtracer), and the comparison with a reference
SVG when `tests\samples\ref\<name>.svg` exists. The goal against a reference is SSIM within 0.02 and
a file that is not bigger.

## Models

`auto` looks at the pixels and picks one. You can force any of them.

| Model | Picked when | Tracer | Defaults |
|---|---|---|---|
| `drawing` | Gray image, 90 % of pixels very dark or very light | Potrace, one ink shape | 2 colors, smooth 3 |
| `pixelart` | At most 128 px on a side and at most 32 exact colors | vtracer layers | smooth 3, keeps every pixel |
| `photo` | More than 25 color bins hold the first 80 % of pixels | vtracer layers | 8 colors, smooth 1 |
| `clipart` | Everything else | vtracer layers | auto colors, smooth 2 |

The table is in `smoothsvg/presets.py`. The pick is in `smoothsvg/classify.py`.

## How it works

```
load -> classify -> clean noise -> cut to a few colors (k-means, Lab) -> drop tiny islands
     -> upscale each color mask and blur it -> pick the strongest mask per pixel
     -> cut into connected pieces, stack big to small -> find circles and ellipses
     -> trace each piece (vtracer) -> shrink with scour -> score (SSIM)
```

1. **Cut to a few colors.** k-means in Lab color finds the palette. The number of colors is the
   smallest one where one more color barely helps. Colors closer than the merge threshold become one.
2. **Smooth.** Each color becomes a 0/1 mask. The mask is upscaled and blurred, which turns stair
   edges into soft ramps. Each pixel takes the color with the highest value. The edge is the 50 %
   line of the ramp, so it is a smooth curve, and no in-between color can appear.
3. **Stack.** Every connected piece of color is its own shape. Pieces are sorted by their area with
   holes filled, biggest first. A piece is drawn with its holes filled, because what sits in the
   holes is drawn later, on top. A disc with a chart inside it is just a disc.
4. **Overlap without lines.** Each shape reaches 2 px under the pieces drawn after it, so no gap
   shows between touching colors. Near the shape's own border that overlap is pulled back, otherwise
   the two outlines, fitted separately, leave a thin line of the lower color along the edge.
5. **Shapes.** A piece that fits a circle, an ellipse or a polygon (overlap of at least 100 minus
   the tolerance, in percent) is written as an exact SVG shape.
6. **Trace and shrink.** vtracer's binary mode traces each piece into spline curves. scour writes
   the SVG with relative coordinates and short numbers.

## What was changed and why

The project was built in phases (`PLAN.md` holds the plan and the status). These are the code
changes, in order, with the reason for each.

| Change | Why | Effect |
|---|---|---|
| Start with plain vtracer and a scoring tool (`bench`, SSIM) | Every later step needed a number, not an opinion | A baseline in `tests/baseline.json` |
| Local web page before any tuning | Smoothness has to be judged by eye, zoomed in | Synced zoom, wipe mode, live settings |
| k-means palette in Lab, automatic color count | vtracer made 77 colors and 78 paths from a 3-color low-res JPG | 78 paths became about 20, 50 KB became about 10 KB |
| Fixed seed for k-means | OpenCV picks random starts, so the same image gave different results | Repeatable output |
| Merge threshold 16, then 10 | At 16 two close greens of a test logo became one | The darker green stays |
| Upscale first, then snap to the nearest palette color | First try. It made a pink halo around a red/white edge, because pink lay between them | Replaced, see next row |
| Upscale and blur one mask per color, take the strongest | Same smoothing, but no color that is not in the palette can appear | Smooth edges, no halo |
| `path_precision=1`, curve length scaled by upscale, scour | Smooth curves made files 2 to 5 times bigger | 30 to 50 % smaller files, same SSIM |
| Remove islands under a minimum area, default max(8, 0.01 % of the pixels) | JPG noise left many tiny blobs. At 0.05 % two small dots of a test logo disappeared | Fewer paths, small details kept |
| Potrace for the `drawing` model | A black-and-white drawing needs one ink shape, not layers | 4 paths became 1, 7.3 KB became 6.1 KB |
| Otsu threshold computed after the blur | On a pure black-and-white image Otsu returns 0, which left only the cores of the lines | Correct line width |
| Size test before counting exact colors in `classify` | `np.unique` took 1.3 s per megapixel | Picking the model is no longer the slowest step |
| Upscale capped at 2.5 megapixels of work, k-means result cached | A 1 megapixel clipart took 5 s per slider move | About 1 s per move |
| SSIM measured at reduced size above 0.5 megapixel | The score cost 0.7 s per request on a 1 megapixel image | 0.2 s |
| Reference SVG aligned to the input before scoring | Some tools crop their SVG to the drawing, so a plain render does not line up | A fair comparison |
| Own layering with vtracer's binary mode instead of its color mode | vtracer's color mode left a thin green line along the dark edges of a test logo: the green layer under them was fitted separately from the dark layer over them | No line, on transparent and on white backgrounds |
| Pieces ordered by area with holes filled | Ordering by color put a thin halo ring on top of the disc it surrounds, with ragged edges | Smoother rings and halos |
| One shape per connected piece, holes filled | A color used twice (dark green for text and for a chart) could not be placed once in the stack, so a disc had a hole | A disc with a chart inside is a plain disc |
| Shape detection (circles, ellipses, polygons) | Blobs that are really round were traced with small bumps | Exact `<circle>` and `<ellipse>`. A round disc became an exact ellipse |
| Potrace per color layer (kept, off) | Tried to make round shapes rounder. It was 2 times slower and no rounder, and it left a notch on one dot | Left in the code as `tracer="potrace"`, not exposed |
| Reference SVG shown through `<img>` in the page | An SVG file from outside could carry a script | The script can not run |
| Upload checks: real image format, 20 MB, 16 megapixels, colors as `#RRGGBB` only | Anything the page sends is untrusted input | Bad input gets HTTP 400 or 413 |
| Render size forced to the exact size in `score.py` | resvg keeps the aspect ratio, so a 2172 x 724 image came back 1 px off and the score crashed. Found while converting the project logo | Wide images score and convert in the page |
| Panel grouped in sections, name and value on one row, drop hint hidden after loading | The drop hint stayed on top of the picture, and the long panel hid the palette dots | All controls and the color dots fit on one screen |

Findings that shaped the design: smoothing has to happen before tracing, because the tracer copies
whatever edge it is given. The round bumps on small dots came from the cut to flat colors, not from
the tracer. Several settings (Potrace tolerance, curve length) changed nothing visible for that
reason.

## Results

Plain vtracer against this tool, both through `bench` (the logo rows were measured the same way):

| Sample | Model | Paths | KB | SSIM |
|---|---|---|---|---|
| Project logo (2172 x 724) | clipart | 2144 → 36 | 610 → 25 | 0.897 → 0.985 |
| Simple logo | clipart | 5 | 7.9 → 7.7 | 0.981 → 0.993 |
| Line drawing | drawing | 4 → 1 | 7.3 → 6.1 | 0.975 |
| Low-res JPG (quality 40) | clipart | 78 → 20 | 50.1 → 10.4 | 0.860 → 0.869 |
| Pixel art heart (13 x 10) | pixelart | 3 → 6 | 0.8 → 0.9 | 0.756 → 0.879 |
| Photo (synthetic) | photo | 1 → 50 | 0.3 → 40.8 | 0.738 → 0.774 |

The simple logo, drawing, JPG, photo and pixel art samples are made by `tests/make_samples.py`. The
project logo is in `branding/`. To compare with another
tool, put your image in `tests/samples/` and that tool's SVG in `tests/samples/ref/<same name>.svg`,
then run `bench`. Both paths are ignored by git, so they stay on your computer.

Speed: about 3 s for a 1.5 megapixel logo, about 1 s for a 1 megapixel clipart when only a control
changes.

## Project layout

```
smoothsvg/
  __main__.py     command line, bench, --ui
  pipeline.py     the steps, convert_array and convert_image
  presets.py      the model table
  classify.py     picks the model
  quantize.py     k-means palette
  smooth.py       denoise, mask upscale, islands, scour
  drawing.py      Potrace for drawings, layered tracer, shape detection
  score.py        render, SSIM, paths and colors, compare image
  server.py       FastAPI app for the web page
  static/         index.html and app.js, no build step
branding/         the project logo (PNG) and its SVG, made by this tool
docs/screenshots/ the pictures used in this README
tests/
  samples/        test images made by make_samples.py. ref/ is for SVGs from other tools (not tracked)
  baseline.json   plain vtracer numbers for bench
  make_samples.py builds the synthetic samples
PLAN.md           the plan and status of each phase
PLAN-BROWSER.md   an idea for a version that runs fully in the browser (not built)
```

## Developer tools

Small scripts in `tests/` used while tuning. They are not automated tests. `peek.py` and
`order_probe.py` take an image path as an argument and default to `branding/Logo+name.png`.

| Script | What it shows |
|---|---|
| `screenshots.py` | Retakes the README pictures with Edge or Chrome. Needs `pip install -e ".[docs]"` |
| `sweep.py` | Every sample at one Smooth level |
| `probe.py` | Effect of Min area on the low-res JPG |
| `shapes_cmp.py` | Shape detection off, circles, circles and polygons |
| `layers_cmp.py` | Tracers and cleanup settings on one sample |
| `order_probe.py` | Color order and holes per color |
| `peek.py` | Wrong-colored pixels away from color borders |

## Limits

- Smooth gradients and photos become color bands. A photo is not the target of this tool.
- Very small details can vanish at high Smooth levels or below Min area.
- Images over 16 megapixels are refused. Upscaling stops at about 2.5 megapixels of work.
- A circle that another shape partly covers is not recognized, because its visible outline is not
  a circle. A ring that is joined to a handle is not recognized either.
- Removing the background on an image that has no clear border color removes the wrong color.
- Polygon detection can flatten curvy pixel art. That is why it is off by default.
- The `drawing` model ignores the color and shape controls.
- The page was checked through its API and with browser screenshots, not with an automated test suite.

## Not done yet

- Automated tests (`pytest` is installed, there are no `test_*.py` files yet).
- Real-ESRGAN (AI upscale) as an option. A GPU with Vulkan can run it.
- Rings and arcs as exact shapes.
- Switching off the controls that the `drawing` model ignores.
- Batch conversion of many images with a ZIP download in the page.

## License

smooth-svg is free software under the **GNU General Public License v3.0 or later**
(`GPL-3.0-or-later`). The full text is in `LICENSE`.

The `drawing` model imports [`potracer`](https://pypi.org/project/potracer/), a Python port of
Potrace, which is GPL-2.0-or-later. Two other dependencies, `opencv-python-headless` and `scour`, are
Apache-2.0, which is not compatible with GPL-2.0-only but is compatible with GPL-3.0. GPL-3.0-or-later
is the license that fits all three, so any program that includes this code must be released under the
same terms.

Other dependencies keep their own licenses: `vtracer`, `resvg-py`, `scikit-image`, `Pillow`, `numpy`,
`fastapi`, `uvicorn` and (for the screenshots only) `playwright`. Check each package before you
redistribute a bundle.
