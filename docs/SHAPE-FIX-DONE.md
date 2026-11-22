# Shape fix: g tail and v notch in the logo SVG

PR: https://github.com/PatrikGuerra/smooth-svg/pull/4 (branch `feat/shape-fix-g-v`, base `feat/svg-geometry-fit`). Not merged.

## Causes (both in shared code)

1. **v inner dot and coarse bottom** (`smoothsvg/geometry.py`, `_arcs`/`_arc_ok`). The outline fit accepted a 1.9 px circle at the sharp notch tip as an "arc", which drew the round dot. The same fit turned the rounded bottom into straight facets. Fix: arcs with radius under `4*eps` are refused, so the tip stays sharp. The rounded bottom is now traced by the spline path.
2. **g tail bump and stem step** (`smoothsvg/drawing.py`, `trace_stacked`). The logo is large (2172x724), so `upscale` runs at k=1 and there is no blur. The 1 px stairs of the color mask became kinks after vtracer's spline fit. Fix: new `soften` option, a Gaussian blur (sigma 1.5) plus threshold on each piece mask, passed by `pipeline.convert_array` only when k == 1 and smooth > 0.

## Crops (4x, original left, ours right), in `docs/shape-fix/`

| Spot | Before | After |
|---|---|---|
| g | `before_g.png` | `after_g.png` |
| v | `before_v.png` | `after_v.png` |
| v notch (14x) | `before_v_notch.png` | `after_v_notch.png` |
| g bump, sigma 1.0 / 1.5 / 2.0 / 3.0 | `g_bump_sigma_1.0_1.5_2.0_3.0.png` | |

## Numbers (geometry fit on, `tests/svgfit_cmp.py`)

| Image | SSIM before | SSIM after | KB before | KB after |
|---|---|---|---|---|
| Logo+name | 0.983 | 0.9828 | 16.5 | 18.5 |
| drawing | 0.975 | 0.975 | 6.1 | 6.1 |
| logo | 0.991 | 0.9913 | 3.4 | 4.0 |
| lowres | 0.8688 | 0.8688 | 10.0 | 10.0 |
| photo | 0.7713 | 0.7718 | 31.5 | 31.9 |
| pixelart | 0.8789 | 0.8789 | 0.9 | 0.9 |

Largest SSIM drop: 0.0002 (limit 0.003). Raw output: `out/baseline_cmp.txt`, `out/after_cmp.txt` (not committed).

## Tests

`tests/test_geometry.py`: `test_tiny_circle_is_not_an_arc` (v dot) and `test_soften_drops_stair_bumps_at_1_to_1` (g bump). `pytest`: 70 passed. `ruff`: clean.

## Limits

- The two tests cover the mechanism (`_arc_ok` radius, fewer path commands with soften), not the logo itself. I could not make a small synthetic image that reproduces the facets, so they were not proven to fail on the old code.
- The v notch is not a perfect point: the right side shows a slight S wobble above the tip (see `after_v_notch.png`).
- g: a tiny flat step remains at the top of the stem shoulder (about 3 px at 4x). The original has a cusp there too.
- Sigma 2.0 and above round off real corners (tested on the g tip). 1.5 is the chosen value.
- Logo size grows 2 KB (12%), because the outline now stays as spline curves instead of a few arcs and lines.
- Only images with k == 1 (about 1.25 MP and larger) get `soften`. Smaller images already have the upscale blur.
- Checked by eye on the logo only for g and v. Other letters were compared by SSIM and size, not zoomed one by one.
