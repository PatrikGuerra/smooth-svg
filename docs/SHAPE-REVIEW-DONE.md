# Shape review of PR #4 (done)

PR: https://github.com/PatrikGuerra/smooth-svg/pull/5. Branch `feat/shape-review`, base `feat/svg-geometry-fit` (PR #3). It replaces PR #4. Not merged.

## What I compared

`branding/Logo+name.png`, UI defaults (same arguments as `/api/convert`), three SVGs: PR #3 head (`af05631`), PR #4 first commit (`91b2539`, with `soften`), PR #4 head (`c66ed4a`, `soften` removed). Each was rendered at 4x and compared with the original (cubic 4x), pixel by pixel, then grouped into regions where two versions differ.

## Findings

| Version | Arcs | Size | Regions worse than PR #3 | Total wrong px (4x) |
|---|---|---|---|---|
| PR #3 | 88 | 16.9 KB | - | 326 631 |
| PR #4 first commit (soften) | 83 | 18.9 KB | about 45, all over the cup and letters | 326 075 |
| PR #4 head (`c66ed4a`) | 89 | 17.9 KB | none | 324 848 |

- **PR #4 head differs from PR #3 in one place only: the v** (x 1782, y 358, 158x168 px). There it is better: the polygon facets are now a smooth curve and the dot is gone. Crop: `docs/shape-review/v_orig_pr3_pr4.png`. All other pixels are identical to PR #3 (the cup, rings, arcs, other letters).
- **The regression the user saw is the first PR #4 commit.** Its `soften` blurred each piece mask after the layer join step. Worst spots: cup rim lines at x 146 y 305 and y 336 (wrong px +35% and +18%), cup lid at x 184 y 61, and many small spots in the cup and the letters (arcs lost: 88 -> 83). Crops: `docs/shape-review/firsttry_cup_rim_orig_pr3_soften.png`, `docs/shape-review/firsttry_cup_top_orig_pr3_soften.png` (columns: original | PR #3 | first try). The total wrong pixels did not move (326 631 -> 326 075), which is why SSIM and the totals were blind to it.
- Commit `c66ed4a` (already on PR #4) removed `soften`. If the user looked at the app before that commit, the worse look is gone. I could not see what the user saw.

## What I changed

- No change to `smoothsvg/`. PR #4 head already has the only code change that is safe: `_arc_ok` refuses arcs with radius under `4*eps`.
- New check that would have caught the regression: `tests/shape_tiles.py` counts wrong pixels per 32 px tile (2x render) and `tests/shape_tiles.json` holds the PR #3 numbers. `test_logo_has_no_tile_worse_than_baseline` (in `tests/test_geometry.py`) fails if any tile grows by more than 15% + 20 px, or if arcs drop below 86.
  - PR #3: 0 tiles over. PR #4 head: 0 tiles over (worst tile +40 px). First commit with soften: 23 tiles over (worst +132 px).
- `pytest`: 70 passed. `ruff`: clean.

## What I tried for the g leg and dropped

Every blur that removed the g bump hurt the cup, so I reverted all of it (nothing of it is in the branch):

- Blur of the color labels at k=1 (sigma x2, x3): cup rim band x134 y304 got 63% more wrong px.
- Blur of piece masks away from layer joins (sigma 1.5): the rim lines at y305 and y336 still got worse (+35%), 83 arcs.
- Open + close with a 3x3 ellipse on the piece mask: same two rim spots worse (+35%).

## Limits

- **The g leg bump is NOT fixed.** PR #4 head does not fix it either (its own DONE file says so). The `g_orig_pr3_pr4.png` crop shows it is identical to PR #3. The cause is that vtracer keeps a 2 px flat run as a corner; a safe fix needs a path-level step (join tiny line segments between two curves), which I did not build.
- The v notch tip still ends in a 1 px flat, with a slight bend on the right side.
- The tile baseline is the PR #3 output on this one logo with default settings. A future change that improves a tile is fine; to accept a new baseline, run `python tests/shape_tiles.py good.svg`.
- Only the logo was checked, not the other samples.
- I judged looks from crops and counts. No lumpiness metric beyond wrong pixels per tile.
