# train

Originally a Rust port of `scripts/train.py` and `scripts/train_mnist.py`;
those Python trainers were deleted once this port was validated (D-008 in
`docs/DECISIONS.md`), and `train/` is now the only trainer. Build-time
only — writes `scripts/weights.json` and `scripts/weights_mnist.json`, same
schema as the Python originals. `gen/` and `tests/` don't know or care
which trainer produced the JSON.

## Usage

```
cd train
cargo run --release -- glyph   # -> ../scripts/weights.json
cargo run --release -- mnist   # -> ../scripts/weights_mnist.json
```

Paths are resolved from `CARGO_MANIFEST_DIR` (compile-time), so it doesn't
matter what directory you run from. MNIST needs `data/mnist/*.gz` (the four
IDX files); if missing, it tries to download them the same way
`train_mnist.py` does (same mirrors).

## Schema contract

Unchanged from Python. `glyph` writes `{"bias": int, "weights": [int; 9]}`.
`mnist` writes `{"weights": [[int;49];10], "bias": [int;10], "test_accuracy":
float, "glyph_accuracy": float, "threshold": float, "exemplars": {"0".."9":
[int;49]}}`. Weights are clipped to `[-3, 3]` (circuit.py's `weighted_score`
asserts this).

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

## Seed choice (fixed: D-007 -> D-009 honest re-selection)

The perceptron is shuffle-order-sensitive: final accuracy (after
quantization, and after glyph-triggered augmentation if it fires) swings by
several points across seeds even with the *same* algorithm — this is
inherent to averaged-perceptron training, not a bug.

D-007 originally picked `SHUFFLE_SEED = 8` by scanning ~20 seeds against
**test-set** accuracy — a max-of-20 draw against the number that's supposed
to be the honest, unbiased estimate. That's a real integrity problem, not
just a style nit: it reports the best of a distribution, not a draw from it.

Fixed: the last 10k of the 60k training images are held out as a
validation split (never trained on). Cell threshold `t`, shuffle seed, and
quantization scale are all grid-searched and selected purely against this
validation split — `SEED_GRID` in `src/mnist.rs` (0..20, kept at the same
size as before for continuity). The 10k official test set is read exactly
once, after every hyperparameter is already locked in, purely to report the
final number. Glyph-triggered augmentation (see below) is likewise accepted
only if it improves validation accuracy — otherwise it's discarded and
logged.

Current result: `t=0.2`, `seed=10`, val accuracy 0.8301, **test accuracy
0.8189**. This is lower than the old 0.8246 — expected, since 0.8246 was a
seed-optimized test-set figure, not an apples-to-apples number. 0.8189 is
the honest baseline the MLP (`docs/DESIGN_MLP.md`) must clear.

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
- **End-to-end**: `python3 scripts/generate.py dist/index.html` then
  `python3 -m unittest discover -s tests` — 68 tests, all pass (16 skipped,
  pre-existing webkit-engine skips unrelated to this change).

## Accuracy result

| | Python baseline | Rust, seed-scanned vs test (D-007, retired) | Rust, honest val-selected (current) |
|---|---|---|---|
| test_accuracy | 0.7998 | 0.8246 | **0.8189** |
| val_accuracy (selection) | n/a | n/a | 0.8301 |
| glyph_accuracy | 0.8 | 0.8 | 0.7 |
| threshold | 0.3 | 0.3 | 0.2 |
| seed | n/a (42, unselected) | 8 (test-scanned) | 10 (val-selected) |

The middle column is what shipped under D-007's flawed methodology; it's
kept here for the record, not as a target. 0.8189 is the number this
codebase now stands behind, and the bar `docs/DESIGN_MLP.md`'s MLP must
clear.
