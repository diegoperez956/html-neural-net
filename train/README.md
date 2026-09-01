# train

Originally a Rust port of `scripts/train.py` and `scripts/train_mnist.py`;
those Python trainers were deleted once this port was validated (D-008 in
`docs/DECISIONS.md`), and `train/` is now the only trainer. Build-time
only — `glyph` and `mnist` write `scripts/weights.json` and
`scripts/weights_mnist.json`, the files `gen/` and `tests/` actually
consume. `mlp` (M12's hidden-layer experiment, not shipped — see D-010 in
`docs/DECISIONS.md`) writes its own `scripts/weights_mlp.json` and is not
part of `make build`.

## Usage

```
cd train
cargo run --release -- glyph   # -> ../scripts/weights.json
cargo run --release -- mnist   # -> ../scripts/weights_mnist.json (shipped, linear)
cargo run --release -- mlp     # -> ../scripts/weights_mlp.json (experimental, not shipped)
```

Paths are resolved from `CARGO_MANIFEST_DIR` (compile-time), so it doesn't
matter what directory you run from. MNIST needs `data/mnist/*.gz` (the four
IDX files); if missing, it tries to download them the same way
`train_mnist.py` does (same mirrors).

## Schema contract

`glyph` writes `{"bias": int, "weights": [int; 9]}` (unchanged from
Python). `mnist` writes `{"weights": [[int;49];10], "bias": [int;10],
"test_accuracy": float, "val_accuracy": float, "drawn_val_accuracy":
float, "glyph_accuracy": float, "thin_glyph_accuracy": float,
"threshold": float, "block_threshold": int, "canvas": int,
"dilate_iters": int, "seed": int, "exemplars": {"0".."9": [int;49]}}` —
the same linear schema as the Python original plus a few transparency
fields D-009/D-010 added and the M13 pipeline fields (`gen/` reads
`weights`, `bias`, `test_accuracy`, `block_threshold`, `canvas`, and
`dilate_iters`; it asserts `block_threshold == 1` — the runtime downsample
is a pure OR, fixed architecture per D-011 — and refuses to build
otherwise). Weights are clipped to `[-3, 3]` (`gen/src/circuit.rs`'s
`weighted_score` assumes this).
`mlp` writes its own separate schema (`hidden_weights`/`hidden_biases`/
`output_weights`/`output_biases`, see `docs/DESIGN_MLP.md`) to
`scripts/weights_mlp.json` — `gen/` never reads this file.

## RNG: divergence from CPython

Python's `random` module is Mersenne Twister (MT19937) with its own
`shuffle`/`random()`/`choice()` semantics on top. This port does **not**
reproduce that — it uses a small seeded SplitMix64 generator
(`src/rng.rs`), which the task spec explicitly allows ("if not, use your
own seeded RNG and document the divergence"). Reproducing MT19937 bit-for-bit
buys weight-for-weight parity with Python, which is explicitly a
nice-to-have, not the contract (schema + accuracy are).

Used in two places, both ported structurally from the Python (same
Fisher-Yates shuffle shape, same call sites) but drawing from the divergent
stream:
- `train_perceptron`'s per-epoch `shuffle(order)`.
- `jitter_variants`'s per-cell shift/flip sampling (only exercised if glyph
  accuracy < 8/10 after the base quantization pass, same as Python).

`python_round()` in `src/mnist.rs` *does* replicate Python 3's round-half-
to-even exactly (not naive round-half-away-from-zero) — that one is cheap to
get exactly right and it affects which quantization scale wins the accuracy
comparison in `pick_best_quantization`.

## Seed choice (D-007 -> D-009 honest re-selection -> D-010 drawn-style retarget)

The perceptron is shuffle-order-sensitive: final accuracy (after
quantization, and after glyph-triggered augmentation if it fires) swings by
several points across seeds even with the *same* algorithm — this is
inherent to averaged-perceptron training, not a bug.

D-007 originally picked `SHUFFLE_SEED = 8` by scanning ~20 seeds against
**test-set** accuracy — a max-of-20 draw against the number that's supposed
to be the honest, unbiased estimate. D-009 fixed that: the last 10k of the
60k training images are held out as a validation split (never trained on),
and `t`/seed/scale were grid-searched against it, with the 10k test set
read exactly once at the end.

D-010 went one step further: downsampled MNIST validation accuracy is
itself a poor proxy for what a visitor draws on the 7×7 grid (thin
anti-aliased pen strokes with real bbox margin vs. thick, canvas-filling,
blockily-filled cells). Selection now runs against a **drawn-style
validation proxy** instead — the same held-out validation images, with
their raw pixels transformed to look more like grid-drawn input before the
usual bbox+crop pipeline:

1. **Stroke dilation** (one round of 4-neighbor binary dilation) — thickens
   the binarized digit before cropping.
2. The existing **bbox + centered-square-pad crop** (D-006) — reused as-is.
3. **Full-canvas zoom** (`DRAWN_ZOOM = 0.82`) — shrinks that square crop
   toward its center, since a grid-filled digit fills more of its bounding
   square than a MNIST digit does.
4. **Coverage-threshold variation** — the 28×28 binarization threshold
   (`DRAWN_PIXEL_THRESHOLDS = [90, 128, 166]`, cycled by image index) varies
   how much of MNIST's anti-aliased stroke edge counts as ink before
   dilation, standing in for different drawing "pressure."

`t`, shuffle seed, quantization scale, and the glyph-augmentation
accept/reject gate are all now selected against this proxy
(`build_drawn_style_val` in `src/mnist.rs`); plain MNIST validation
accuracy is still computed and reported as a secondary number. The 10
canonical glyphs are never touched during selection — only afterward, as a
sanity check that the proxy isn't off in the weeds (see the accuracy table
below: proxy 0.7756 vs. glyph accuracy 0.8000, a 0.024 gap, which is close
enough to trust the proxy).

`THRESHOLD_GRID` was widened from the original `0.10..0.35` to `0.10..0.70`
for this search — the old range's max (`0.35`) was where drawn-style
accuracy peaked, i.e. the old grid's edge, not an interior optimum. The
wider grid finds a real peak at `t=0.45` instead.

Current result: `t=0.45`, `seed=19`, drawn-style val accuracy 0.7756, MNIST
val accuracy 0.7876, **test accuracy 0.7854**. This trades ~3.4 points of
MNIST test accuracy (down from D-009's honest 0.8189) for canonical
drawn-glyph fidelity: 8/10, up from 7/10. See D-010 in
`docs/DECISIONS.md` for the full evaluation, including the MLP's negative
result that motivated this retarget.

No `TRAIN_SEED` env override anymore — seed is chosen by the grid search on
every run, not read from an env var, so the result is deterministic without
extra configuration.

## Download: curl subprocess, not an HTTP client crate

`data/mnist/` is cached in every environment this has been asked to run in
(offline-first, per the task). Download is a fallback that essentially never
executes. Given that, shelling out to `curl` (already on the box, same
mirrors and `User-Agent` as the Python version) beats adding `ureq`+`rustls`
or `reqwest` as a dependency for a code path that doesn't run.

## Verification performed

- **Glyph**: exact weight parity with Python (`{"bias": -2, "weights": [1,
  0, 2, -1, 0, 0, -1, 0, 0]}`) — expected, since `train.py` has no RNG at
  all, it's a pure integer perceptron.
- **Bbox-normalize pipeline**: `src/mnist.rs`'s `preprocess_matches_python_intermediates`
  test (`#[ignore]`d by default, needs `data/mnist/` + a Python-side dump)
  diffs the 49 coverage fractions for the first 20 MNIST train images
  against `preprocess_image()` from `train_mnist.py`, cell by cell, to
  1e-9. Bit-identical. Dump command used:
  ```
  python3 -c "
  import sys; sys.path.insert(0, 'scripts')
  from train_mnist import preprocess_image, read_idx_images, read_idx_labels
  import json
  imgs, *_ = read_idx_images('data/mnist/train-images-idx3-ubyte.gz')
  labels = read_idx_labels('data/mnist/train-labels-idx1-ubyte.gz')
  json.dump([{'label': labels[i], 'fracs': preprocess_image(imgs[i])} for i in range(20)],
            open('/tmp/py_intermediates.json', 'w'))
  "
  ```
  then `cargo test --release -- --ignored --nocapture`.
- **Determinism**: two consecutive `mnist` runs produce byte-identical
  `weights_mnist.json`.
- **Schema**: keys, nesting, and value types checked against the Python
  output (same key set, `weights` is `[[int;49];10]`, `bias` is `[int;10]`,
  `exemplars` has all 10 string keys each mapping to `[int;49]`).
- **End-to-end**: `make build` then `python3 -m unittest discover -s tests`
  — 67 tests, all pass (17 skipped, pre-existing abstract-base/webkit
  skips unrelated to this change).

## Accuracy result

| | Python baseline | Rust, seed-scanned vs test (D-007, retired) | Rust, honest MNIST-val-selected (D-009, retired) | Rust, drawn-style-val-selected (current, D-010) |
|---|---|---|---|---|
| test_accuracy | 0.7998 | 0.8246 | 0.8189 | **0.7854** |
| val_accuracy (MNIST) | n/a | n/a | 0.8301 | 0.7876 |
| drawn_val_accuracy (proxy) | n/a | n/a | n/a | 0.7756 |
| glyph_accuracy | 0.8 | 0.8 | 0.7 | **0.8** |
| threshold | 0.3 | 0.3 | 0.2 | 0.45 |
| seed | n/a (42, unselected) | 8 (test-scanned) | 10 (val-selected) | 19 (drawn-val-selected) |

D-007's and D-009's columns are kept here for the record, not as targets.
0.7854 test accuracy / 8/10 glyph fidelity is what this codebase ships
now: a deliberate trade of MNIST accuracy for the metric that reflects
what a visitor actually draws (D-010 in `docs/DECISIONS.md`). The MLP
(`docs/DESIGN_MLP.md`) cleared 0.8189 on MNIST but not glyph fidelity
(also 7/10, unmoved) and was not shipped for it.
