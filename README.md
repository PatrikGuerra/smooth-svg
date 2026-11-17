# smooth-svg

Converts a PNG or JPG into a **simple, smooth SVG**: a few flat colors, a few paths, and curves
instead of pixel stairs. It runs on your computer. Nothing is uploaded.

It picks a model for your image (clipart, drawing, pixel art, photo), cuts it to a small palette,
smooths the edges, and traces vector shapes.

## Install (Windows, Python 3.12)

```powershell
cd c:\projetos\smooth-svg
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

If `python` is not found, use the full path of your Python 3.12 `python.exe` for the first command.
The `.venv` folder already exists on this machine, so you can skip the install.

## Run the UI (zoom and live preview)

```powershell
cd c:\projetos\smooth-svg
.\.venv\Scripts\python.exe -m smoothsvg --ui
```

Your browser opens at <http://127.0.0.1:8765>. The server listens on this computer only.
Press `Ctrl+C` in the terminal to stop it.

| In the page | What it does |
|---|---|
| Open image, or drop a file | PNG or JPG, up to 20 MB |
| Mouse wheel | Zoom (input and SVG move together) |
| Drag | Pan |
| Double click | Fit to window |
| Wipe mode | SVG over the input, with a slider to sweep between them |
| Model | `auto` (default), `clipart`, `drawing`, `pixelart`, `photo` |
| Colors | Number of colors. `auto` lets the tool decide |
| Smooth | 0 to 5. Higher means rounder edges and fewer small details |
| Min speckle | Drops tiny blobs |
| Min area (px) | Merges color islands smaller than this into their surroundings. `auto` scales with the image |
| Merge similar colors | Colors closer than this become one. Higher gives fewer colors (10 keeps two greens apart) |
| Corners | Angle above which a point stays a sharp corner. `auto` follows Smooth |
| Curve simplify | Higher gives fewer curve points and smaller files. Matters most on big images |
| Circles & ellipses | Blobs that are really circles or ellipses become exact `<circle>` / `<ellipse>` shapes. On by default |
| Straight-edge polygons | Blobs with straight edges (3 to 8 corners) become `<polygon>`. Off by default. It can flatten curvy pixel art |
| Shape tolerance | How far a blob may differ from the shape and still be swapped, in percent of its area. 1 is strict, 15 is loose. Default 3 |
| Clean noise | Edge-keeping filter before the colors are cut. Turn it off for crisp pixel art |
| Color dots | Click a dot to remove that color layer |
| Remove background | Makes the border color transparent |
| Load reference SVG | Loads an SVG from another tool. "Show: mine / reference" swaps it in |
| Download / Copy SVG | Saves or copies the result |

A spinner shows over the preview and in the status bar while the server works. Only the newest\nrequest ends it, so dragging a slider fast does not flicker.\n\nThe `drawing` model uses Potrace and ignores Colors, Merge, Corners, Curve simplify and Min area.\n\nThe input is drawn with square pixels, so you can see stairs against curves when you zoom in.
The first conversion of an image uses the model's own colors and smoothness and shows them in the
controls. After that, the controls are yours.

## Run from the command line

```powershell
.\.venv\Scripts\python.exe -m smoothsvg input.png -o output.svg
.\.venv\Scripts\python.exe -m smoothsvg input.jpg --model clipart --colors 6 --smooth 3
.\.venv\Scripts\python.exe -m smoothsvg folder\ -o out\          # every PNG/JPG in a folder
.\.venv\Scripts\python.exe -m smoothsvg logo.png --remove-bg --compare
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

## Check the quality

```powershell
.\.venv\Scripts\python.exe -m smoothsvg bench
```

Converts every image in `tests\samples\` and prints one row each: SSIM (similarity to the
input, 0 to 1), paths, colors, KB, time, the change against `tests\baseline.json` (plain
vtracer), and the comparison with a reference SVG if `tests\samples\ref\<name>.svg` exists.

## Results so far

Plain vtracer against this tool, with the vectorizer.io result for the DinoDino logo.

| Sample | Model | Paths | KB | SSIM |
|---|---|---|---|---|
| DinoDino logo | clipart | 48 (vectorizer.io: 51) | 39 (78) | 0.971 (0.932) |
| Simple logo | clipart | 5 | 7.9 → 8.2 | 0.981 → 0.991 |
| Line drawing | drawing | 4 → 1 | 7.3 → 6.1 | 0.975 |
| Low-res JPG | clipart | 78 → 18 | 50.1 → 9.3 | 0.860 → 0.866 |
| Pixel art heart | pixelart | 4 → 6 | 0.8 → 0.7 | 0.756 → 0.877 |
| Photo | photo | 1 → 50 | 0.3 → 41.6 | 0.738 → 0.773 |

Speed: about 1 s for a 1 megapixel clipart when only a control changes, 2.5 s for the DinoDino
logo (1.5 megapixels).

## How it works

```
load -> classify -> denoise -> k-means colors (Lab) -> drop tiny islands
     -> upscale each color mask + blur, pick the strongest -> trace (vtracer, or Potrace for drawings)
     -> shrink with scour -> score (SSIM)
```

- Upscaling each color mask and blurring it turns stair edges into soft ramps, so the traced edge
  is a smooth curve. Picking the strongest mask per pixel adds no in-between colors (no halos).
- `smoothsvg/pipeline.py` has the steps, `presets.py` has the model table, `classify.py` picks the
  model, `drawing.py` is the Potrace path, `server.py` and `static/` are the UI.

## Layers

Each color is traced as its own stacked layer (`trace_stacked` in `drawing.py`). Where an upper layer
reaches the outer edge, the layer under it is pulled back a few pixels, so a thin line of the lower
color does not peek out along the edge. The older vtracer color mode had this flaw (a green line
along the dark spikes of the DinoDino logo). The cost: on noisy JPGs the result is a little rougher
and the files a little bigger (low-res JPG SSIM 0.866 to 0.818; DinoDino 39 KB to 52 KB).

## Shape detection

After each layer is cut, blobs that fit a circle, ellipse or polygon (overlap of at least 100 minus the
tolerance, in percent) are written as exact SVG shapes and left out of the traced path. The status bar
shows how many were found. Only simple blobs without holes are tested, so a circle that is partly
covered by another shape, or a ring, stays a normal path. Pieces that only repeat what a layer above
already draws are dropped, which also cut the DinoDino file from 52 KB to 33 KB.

## Limits

- Smooth gradients and photos become color bands. A photo is not the target of this tool.
- Very small details can vanish at high Smooth levels or below `--min-area`.
- Images over 16 megapixels are refused. Upscaling is capped at about 2.5 megapixels of work.
- **License:** the `drawing` model uses `potracer`, which is GPLv2+. Fine for personal use. If you
  publish this project, it must be GPL, or you must remove the `drawing` model.
- Real-ESRGAN (AI upscale) is not built in. Your GPU supports Vulkan, so it can be added later.
- There are no automated tests yet (`pytest` is installed, test files are not written).

## Plans

`PLAN.md` is the design and the build log. `PLAN-BROWSER.md` is an unbuilt idea for a version that
runs fully inside the browser.
