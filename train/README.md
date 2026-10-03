# Training the models

Training happens in Rust before the page opens. The browser only evaluates
the saved model. `make build` and `make test` use checked-in weights and do
not retrain.

## Commands

These commands overwrite model files. MNIST training runs a grid search and
can download data when the cache is missing.

```bash
make train
# Or run one trainer:
cargo run --release --manifest-path train/Cargo.toml -- glyph
cargo run --release --manifest-path train/Cargo.toml -- mnist
```

`glyph` writes `scripts/weights.json`. `mnist` writes
`scripts/weights_mnist.json`. The experimental `mlp` verb and module were
removed on 2026-10-03: after the 14×14 pipeline change they silently used only
49 of 196 coverage cells. The negative result remains in
[the historical design](../docs/DESIGN_MLP.md); it cannot be regenerated with
the current trainer. Paths resolve relative to the crate location, not the
shell's working directory.

## The shipped models

The 3×3 glyph classifier trains a perceptron on nine hand-built examples.
Its schema is `{"bias": int, "weights": [int; 9]}`.
It has no held-out accuracy estimate.

The digit model is a ten-class linear perceptron with 49 binary features.
It is not the hidden-layer model described in `docs/DESIGN_MLP.md`.
Its JSON contains:

- `weights`, ten rows of 49 integers in [-3, 3].
- `bias`, ten integers.
- `test_accuracy`, `val_accuracy`, and `drawn_val_accuracy`.
- `glyph_accuracy` and `thin_glyph_accuracy`.
- `threshold` and `seed` from model selection.
- `canvas: 14`, `dilate_iters: 1`, and `block_threshold: 1`.
- `exemplars`, ten saved 49-bit examples indexed by string digits.

The generator validates the class counts and each row's input count.
It rejects a different canvas size, dilation count, or block threshold.
It also checks that weights and all possible score bounds fit its circuit.

Stored exemplars are already post-processed 49-bit features. Upscaling one
onto the drawing canvas and processing it again can change it. Browser tests
recompute the full path rather than assume that operation is an identity.

## Preprocessing and training

`src/mnist.rs` caches the four compressed MNIST IDX files in `data/mnist/`.
Missing files are downloaded with a `curl` subprocess. The normal image path is:

1. Binarize the 28×28 pixels above 128.
2. Crop to the digit's bounding box and make a centered square crop.
3. Area-resample to 14×14 coverage fractions.
4. Threshold coverage into binary cells.
5. Dilate once with the four orthogonal neighbors.
6. OR each 2×2 block into one of 49 features.

Only steps 5 and 6 also run on the drawing canvas. The browser does not crop,
center, or threshold a screenshot. Its checkboxes are already binary inputs.

Training uses the first 50,000 images of MNIST's 60,000-image training set.
The remaining 10,000 form validation data. The official 10,000 test images
are separate.

The multiclass perceptron makes eight passes through the training set.
On a wrong prediction, it adds the active input bits to the correct class's
weights and subtracts them from the predicted class's weights. Biases change
by +1 and -1 respectively. This is a plain perceptron, not an averaged one.

The quantizer divides by a candidate scale, rounds ties to even, and clips
weights to [-3, 3]. The grid search chooses the coverage threshold, shuffle
seed, and quantization scale against a drawn-style validation proxy.
The proxy thickens the source strokes, uses a tighter crop, and varies source
pixel thresholds. Ordinary MNIST validation accuracy is also reported.

## Current recorded results

The checked-in `scripts/weights_mnist.json` is the source for these values:

| Field | Value |
|---|---|
| MNIST test accuracy | 0.7542 |
| MNIST validation accuracy | 0.7716 |
| Drawn-style validation accuracy | 0.6880 |
| Canonical upscaled glyph accuracy | 8/10 |
| Thin-stroke glyph accuracy | 6/10 |
| Coverage threshold | 0.65 |
| Shuffle seed | 16 |
| Block threshold | 1 |

The canonical glyph misses are 6→5 and 9→3. The thin-stroke misses are
1→4, 2→7, 6→5, and 9→8. These figures are not accuracy estimates for arbitrary
user drawings. The current revision verifies browser inference from the saved
weights; it does not rerun the MNIST experiment.

## Selection caveats

D-007 selected a seed after scanning about twenty candidates against test
accuracy. Its 82.46% result is a retired, test-selected figure.
D-009 moved selection to validation and recorded 81.89% test accuracy.
D-010 selected against drawn-style validation and recorded 78.54% on the old
7×7 drawing pipeline. That is not the current model.

D-011 added the 14×14 canvas and runtime dilation. Development compared
multiple block thresholds and inspected their glyph results. Only OR
downsampling met both glyph acceptance floors. Fixing OR as architecture
for the final search does not erase that earlier selection.

The final 8/10 and 6/10 glyph scores are therefore acceptance-conditioned.
The milestone did not touch the test set and glyph sets only once across all
runs. The current trainer also checks glyph accuracy before deciding whether
to attempt synthetic-glyph augmentation. It accepts augmented weights only
if drawn-style validation improves. No augmentation was needed for the saved
configuration.

The 0.60 test-accuracy floor and glyph floors can reject a run before it writes
weights. A test-triggered [-7, 7] diagnostic is reported but never written.
These checks are another reason not to describe the entire training procedure
as completely independent of acceptance data.

See [D-007 through D-011](../docs/DECISIONS.md) for the historical experiments.
A new evaluation claim needs fresh held-out drawings and a selection procedure
fixed before their results are inspected.

## Reproducibility and tests

The trainer uses seeded SplitMix64 and Fisher-Yates shuffling.
It does not reproduce CPython's Mersenne Twister stream.
`python_round` implements round-half-to-even for quantization.
D-011 records byte-identical JSON across repeated training runs.

```bash
make test-unit
make test-runtime
```

The trainer has 13 Rust tests covering glyph separation, rounding, image
transforms, and deterministic shuffling. The ignored comparison test that
required a dump from the deleted Python trainer was removed on 2026-10-03;
D-007 retains the historical parity result, not a runnable parity check.

The runtime suite has 85 tests: 40 per browser engine and 5 static checks.
It checks inference against the current JSON, including script-disabled and
script-deleted operation, preprocessing, score arithmetic, argmax, margin,
and rendered displays. The 16 abstract base-class skips are expected.
`make test` also runs 2 generator Rust tests and 9 history/video Python tests.
