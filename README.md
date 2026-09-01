# htmlnet

**A neural network built from logic gates and arithmetic circuits using HTML + CSS. The network computes in pure CSS; the only JavaScript on the page is a ~20-line input shim for drag-to-draw.**

Open `dist/index.html` in any modern browser (offline, `file://` works) and toggle the switches. The page evaluates gates, adders, a multiplier, dot products, a matrix-vector product, a 2-2-1 XOR neural network, a perceptron-trained 3×3 glyph classifier, and a 10-class linear digit classifier — paint a digit on a blank 14×14 canvas (a continuous marker stroke, no visible grid), the stroke is dilated and OR-downsampled in CSS gates and the winner is decoded through gates onto a seven-segment display — with no WASM, no network, no server. Delete the one `<script>` tag and the page still works, one click per cell.

```
HTML checkbox state → bits → logic gates → adders → multiplication
→ dot product → matrix×vector → neurons → XOR MLP
```

The hierarchy is real: every stage is composed from the previous stage's named signals, and every intermediate the tests read is the same signal the next stage consumes.

## Demo

```bash
make build   # trains the classifier + generates dist/index.html
xdg-open dist/index.html
```

or just open the prebuilt `dist/index.html`. Firefox 128+, Chromium 111+.

## Why this is interesting

Two independent curiosities:

1. **Gate-derived mode (the absurd one).** Gates are named bit identities
   over native CSS arithmetic (`NOT=1−a`, `AND=min`, `OR=max`,
   `XOR=max−min`). Half adders, full adders, ripple carries, AND partial
   products, two's-complement negation, signed sums, and threshold
   activations are all composed from those gates at build time — 123 gate
   signals for the XOR network alone, 6,834 for the whole page including a
   perceptron-trained 3×3 glyph classifier and a bit-plane-popcount 10-class
   MNIST digit classifier fed by gate-built stroke dilation and 2×2
   OR-downsample from a 14×14 paint canvas, with a gate argmax and
   seven-segment decode.
2. **Native-CSS mode (the sane baseline).** The *same* XOR network
   computed with direct `calc()`/`min()`/`max()` expressions — ~8
   declarations. The demo shows both modes side by side, producing
   identical outputs.

The comparison teaches the actual constraint: **CSS forbids `var() ×
var()`.** Multiplying two runtime values is impossible natively, so the
interactive multiplier (and everything built on it) *must* be a circuit.
Multiplying by a build-time constant is fine — which is why the fixed
weights of a neural network are natively expressible and the interactive
arithmetic is the interesting half.

## Why XOR

A single linear neuron cannot learn XOR; a two-neuron hidden layer can.
The page ships a 2-2-1 threshold MLP with integer weights:

```
h1 = step(+2x1 − 2x0 − 1)
h2 = step(−2x1 + 2x0 − 1)
out = step(+2h1 + 2h2 − 1)
```

All four input states are verified against an independent Python
reference, including hidden preactivations. Weights ±2 are deliberate: a
power-of-two weight times a bit reduces to wiring (no multiplier circuit
needed), so the network is 100%
gate-built at 4-bit signed width.

## Is HTML actually doing the math?

Precisely: **the browser's style engine is doing the math, on a
dependency graph that the HTML/CSS artifact describes.**

* HTML supplies interactive state (checkbox checkedness) and the DOM tree.
* CSS supplies the computation graph: `@property`-registered integer
  custom properties whose declarations reference each other via
  `var()`. The style engine evaluates `calc()`/`min()`/`max()`,
  propagates values along the dependency DAG, and invalidates/recomputes
  when a checkbox changes.
* We do **not** claim the browser parses, matches selectors, evaluates
  integers, or does style invalidation "from primitives." Those are the
  substrate.
* We do **not** claim "HTML performs matrix multiplication" or that CSS is
  a CPU. The netlist is combinational, feed-forward, and fixed — which is
  exactly what a trained MLP's inference graph is, so the honest
  description is also the accurate one: *neural-network inference
  implemented with HTML and CSS.* The network itself, the display, and
  every readout are computed with zero JavaScript; the page's one
  `<script>` is an input shim that turns pointer drags into checkbox
  toggles and computes nothing.

Build-time Rust (`gen/`, `train/`; never shipped) elaborates the circuit,
generates repetitive CSS, and computes references. The runtime artifact is
flat and deterministic.

## Correctness

```bash
make test    # builds, then 36 Playwright tests × Chromium + Firefox
```

* static: exactly one `<script>` (the input shim, checked for size and for
  absence of computation/network APIs), no handlers, no `javascript:`, no
  WASM, no external resource;
* deterministic rebuilds (byte-identical);
* gates exhaustively; half adder 4 states; full adder 8;
* 2-bit adder & 2×2 multiplier 16 states; 4-bit adder **256 states**;
* dot product 16 states; matrix-vector 4; neuron preactivation+activation;
* XOR MLP: 4 states, hidden preactivations and hidden outputs included;
* Mode B: same outputs from native arithmetic;
* trained classifier: 9 training exemplars + 32 random states against an
  independent reference computed from `scripts/weights.json`;
* drawn-digit classifier: gate-level dilation + OR-downsample vs a Python
  pipeline reference for hand-picked 14×14 patterns, then gate argmax +
  seven-segment decode checked against an independent reference computed
  from `scripts/weights_mnist.json`, plus registered-view spot checks and
  rendered-output checks (paint canvas shows no idle grid and draws rounded
  ink blobs; the pixelated "network sees" preview reads the post-downsample
  gate bits).

M11's classifier is trained on real MNIST (`train/src/mnist.rs`,
deterministic): pixels binarize, crop to the digit's bounding box,
pad to a centered square, area-resample to a 14×14 coverage grid (the
canvas resolution), dilate one round, and OR-reduce each 2×2 block to the
7×7 grid the classifier consumes — the trainer simulates the exact gate
pipeline the browser runs. Hyperparameters (cell threshold, shuffle seed,
quantization scale, glyph-augmentation accept/reject) are selected against
a drawn-style validation proxy — held-out MNIST images with thickened
strokes and a tighter, canvas-filling crop, standing in for how a person
actually drags a stroke — not against downsampled-MNIST accuracy directly
(see D-010/D-011 in `docs/DECISIONS.md`; the block-OR threshold T=1 is
fixed architecture, never selected). An 8-epoch perceptron quantized to
weights in [-3,3] scores 75.42% on the full 10k MNIST test set, 8/10
2×-upscaled canonical drawn glyphs (misses 6 and 9), and 6/10 thin-stroke
canvases (what a 1-cell-wide drag looks like; misses 1, 2, 6, 9). That's a
linear model over a lossy 7×7 binary grid selected for drawn-digit
fidelity rather than MNIST accuracy, and the runtime page does no
normalization — draw large and centered, matching the training
preprocessing, or accuracy drops.

## Browser support

Chromium 111+ / Firefox 128+ (needs `:has()`, `@property`, and
`color-mix()` for LED styling). Safari 16.4+ should work but is **not
tested in this repo** — only Chromium 149 and Firefox 151 run in CI. The
full demo is ~1.62 MB, 6,834 registered signals. See `docs/LIMITS.md` for
the measured scaling story.

## Prior art (and what this adds)

We did the homework; see `docs/PRIOR_ART.md` for the dated, cited survey.

* CSS-only logic gates and adders exist since 2011 (SLaks, Amit Sheen,
  checkbox hacks). CSS Turing completeness was settled (Cherlin 2022).
* GrahamTheDev (2023) shipped a CSS-only *single-layer* dot-product
  classifier. The closest real predecessor.
* A full 8086 in CSS exists (Lyra Rebane 2026) on newer CSS features.

The honest distinctives, stated as absence-of-evidence: no prior project
found builds multiplication/dot-products from a **gate-only netlist**, and
none runs a **hidden-layer (2-2-1) network** whose hidden activations are
consumed downstream inside CSS. We don't claim more than that.

## Repository

```text
gen/                    Rust circuit compiler + demo generator -> dist/index.html
train/                  Rust trainer -> scripts/weights*.json
scripts/benchmark.py    scaling benchmarks
tests/test_runtime.py   exhaustive two-engine Playwright suite
experiments/            prototypes, per-worktree findings
docs/                   COMPUTATION_MODEL, ARCHITECTURE, PRIOR_ART,
                        DECISIONS, LIMITS, ADVERSARIAL_REVIEWS
```

## Limitations

Fixed, tiny, low-precision, inference-only. No training, no feedback, no
recurrence (computed styles cannot become selector state). Multiplication
of two runtime values must be a circuit, so scaling is roughly quadratic
in multiplier width — the demo stays where the math is clearest. Every
honesty boundary is spelled out in `docs/COMPUTATION_MODEL.md`.

## License

MIT
