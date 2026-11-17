# smooth-svg (browser): plan

This is the browser version of `PLAN.md`. The goal is the same: turn a PNG or JPG
into a **simple** SVG with few colors, few paths, and smooth curves instead of
pixel stairs. Here everything runs in the browser, as one static page. There is
no server, and the image never leaves the user's computer.

Status: plan only. No code yet. `PLAN.md` holds the Python version, the research,
and the vectorizer.io notes. This file covers only what changes for the browser.

## 1. Stack

| Part | Choice | Why |
|---|---|---|
| App | React + Vite + TypeScript | Same stack as the stores-db-farmais site |
| UI | Tailwind + shadcn/ui, light and dark theme | Same as above |
| Heavy work | Web Worker (background thread) | Keeps the page responsive while tracing |
| Color tracer | vtracer built to WebAssembly (`wasm-pack`) from [visioncortex/vtracer](https://github.com/visioncortex/vtracer) `webapp/` | Best open tracer. Its [demo](https://www.visioncortex.org/vtracer/) already runs in the browser |
| B/W tracer | [esm-potrace-wasm](https://github.com/tomayac/esm-potrace-wasm) | Potrace in WebAssembly, used by Google's [SVGcode](https://github.com/GoogleChromeLabs/svgcode) |
| Image steps | Plain canvas + typed arrays | Denoise, blur, k-means and area cleanup are short loops. OpenCV.js is about 8 MB, too heavy for these few steps |
| AI upscale (optional) | [UpscalerJS](https://github.com/thekevinscott/UpscalerJS) | The real "DLSS" option. Loaded only when the user turns it on |
| SVG minify | [SVGO](https://github.com/svg/svgo) (browser build) | Standard minifier |
| Score | Draw the SVG on a canvas, then compute SSIM in JS | Same quality check as the Python plan |
| Hosting | GitHub Pages | Free, static |

## 2. Pipeline (runs in the worker)

```
file drop / paste / pick
  -> 1. decode      (createImageBitmap -> OffscreenCanvas -> ImageData)
  -> 2. classify    (drawing / clipart / pixelart / photo)
  -> 3. denoise     (median 3x3, or bilateral for photos)
  -> 4. upscale     (canvas high-quality smoothing x2-x4 + light blur;
                     UpscalerJS if turned on; nearest x8 + blur for pixel art)
  -> 5. quantize    (k-means in Lab color, auto N, merge near colors)
  -> 6. clean areas (drop islands below min area)
  -> 7. trace       (vtracer wasm, spline mode; potrace wasm for drawing)
  -> 8. simplify    (scale coords back, round to 1-2 decimals, SVGO)
  -> 9. score       (render SVG to canvas, SSIM, path count, KB)
-> SVG string + report back to the UI
```

The steps and presets match `PLAN.md` sections 4 and 5, so both versions give
the same result for the same settings.

## 3. Screens

One page:

| Area | Content |
|---|---|
| Top bar | Logo, light/dark switch, version badge |
| Left | Drop zone, then the input image |
| Right | SVG preview, with a slider to wipe between input and SVG |
| Panel | Model (auto, drawing, clipart, pixelart, photo), colors, smooth (1-5), min area, remove background, AI upscale |
| Palette | Color dots. Click one to turn it off (for example, to remove the background) |
| Footer | KB, paths, colors, SSIM, time. Buttons: download SVG, copy SVG |

When a setting changes, the worker re-runs only from the first changed step.
The steps before it are cached, so the preview updates fast.

## 4. Project layout

```
smooth-svg/
  PLAN.md
  PLAN-BROWSER.md
  web/
    package.json
    vite.config.ts
    index.html
    src/
      main.tsx
      App.tsx
      components/      DropZone, Preview, Settings, Palette, Stats
      worker/
        pipeline.worker.ts   steps 1-9 and the step cache
        steps/               denoise.ts, upscale.ts, quantize.ts, cleanup.ts, score.ts
        presets.ts
        classify.ts
      wasm/
        vtracer/       wasm-pack output (committed, so no Rust needed to build the site)
    tests/
      samples/         same test images as the Python plan
      pipeline.test.ts (Vitest: SSIM floor, path cap per sample)
  .github/workflows/pages.yml
```

## 5. Steps to build

1. Scaffold Vite + React + Tailwind + shadcn, with the light/dark theme.
2. Build vtracer to WebAssembly once, commit the output, and call it from a worker.
   Baseline: drop an image, get an SVG.
3. Add quantize (k-means, auto N). Compare path count against the baseline.
4. Add denoise and upscale. Check the edges on a pixel-art sample.
5. Add area cleanup and SVGO. Check the file size.
6. Add scoring, the stats footer, and the wipe slider.
7. Add auto model pick, presets, and potrace wasm for `drawing`.
8. Add the step cache for live preview.
9. Add AI upscale as a lazy-loaded option.
10. Add Vitest tests on the samples, the Pages workflow, and a README for a first-time reader.

## 6. Limits and risks

- **Memory:** a 4000x4000 image upscaled x4 needs about 1 GB of RGBA data.
  Rule: cap the working size at about 4 megapixels and lower the upscale factor
  to stay under it.
- **Speed:** vtracer in wasm is slower than native. A large clipart may take a few
  seconds. The worker shows progress and can be cancelled.
- **vtracer has no official npm package.** We build it once with `wasm-pack`
  (this needs Rust on the build machine one time) and commit the output.
- **AI upscale:** the model is a large download and is slow without WebGL/WebGPU.
  It stays off by default.
- **Licenses:** vtracer is MIT. Potrace is GPL-2.0, and esm-potrace-wasm inherits
  that. If we ship potrace, the site must be GPL-compatible, so we either open-source
  the site under GPL or drop the `drawing` model and use vtracer in B/W mode.
- **Older browsers:** OffscreenCanvas in workers is needed (Chrome, Edge, Firefox, Safari 16.4+).
