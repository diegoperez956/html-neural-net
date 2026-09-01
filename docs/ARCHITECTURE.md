# Architecture

How a browser evaluates a neural network with no JavaScript, and where the honesty boundaries are.

## Layer model

```
checkbox state (browser form machinery)
        │  body.rt:has(#x:checked) { --x: 1 }
        ▼
primary bits — registered integer custom properties on one .rt ancestor
        │  var(--x) consumed by gate declarations
        ▼
gate netlist — named bit signals (basis identities below)
        │  half/full adders, ripple carries as named wires
        ▼
arithmetic — adders, structural multipliers, two's-complement words
        │  ripple adder chains
        ▼
neurons — signed products (gate-masked magnitudes + negation),
        │  signed sums + bias, threshold = sign bit
        ▼
MLP — hidden-neuron outputs consumed as var(--h) inputs of the output neuron
        │
        ▼
views — per-bit LEDs read gate signals; decimal counters are native-calc
        views labeled as such
```

## Primitive basis (bottom of the derivation)

For operands constrained to bits:

| gate | identity | native CSS used |
|------|----------|-----------------|
| NOT a | `1 − a` | `calc()` subtraction |
| a AND b | `min(a, b)` | `min()` |
| a OR b | `max(a, b)` | `max()` |
| a XOR b | `max(a,b) − min(a,b)` | `min()/max()/calc()` |

These are the project's atoms. They are native browser arithmetic re-read as
logic on the bit domain — not gates built from anything smaller. The demo
says this explicitly.

## Signal mechanics

* Every signal is `@property { syntax: "<integer>"; inherits: true }` on one
  common `.rt` ancestor (the body). Engine-enforced integer typing; one
  canonical scope; descendants read by inheritance.
* Interdependent wires (carry chains, hidden→output) are plain
  `var(--name)` references between declarations. Computed values propagate
  *down* the dependency graph: `--c1` reads `--c0`; the output neuron reads
  `--xor_h1_out`.
* Computed styles can never become selector state (CSS cannot write
  `:checked` or classes), so there is no feedback and no sequential state
  machine — the netlist is a pure combinational DAG. That is exactly what a
  feed-forward MLP is, which is why this works and why nothing deeper is
  claimed.
* Style queries (`@container style(...)`) were prototyped by the css-logic
  worker (committed under `experiments/css-logic/`) and rejected for the
  final demo: comparison operators are silently dropped in Firefox 151,
  and they add a per-depth container element per stage. The var() graph
  needs none of that and works in Chromium 85+ / Firefox 128+ / Safari
  16.4+ (`:has()` and `@property` only).

## Structure of the generated artifact

`gen/src/circuit.rs` is the circuit compiler (build time, Rust; originally
`scripts/circuit.py`, deleted after the port — see D-008 in
`docs/DECISIONS.md`):

* `Circuit` — ordered named-signal declarations; gates, half/full adders,
  ripple adders, structural unsigned multiplication (AND partial products
  shifted and added by ripple adders), two's-complement negation.
* `Net` — neuron builder: for each weight `w` and bit input `x`, the
  product `w·x` is `|w|` bit-masked by `x` (AND gates) then conditionally
  negated (NOT gates + increment) — real gate machinery, no multiplier
  shortcut. Products and bias are summed by ripple adders at 4-bit signed
  width. Threshold = sign bit.
* `gen/src/main.rs` (originally `scripts/generate.py`) — wires the demo:
  gates, half/full adder, 2-bit adder, 2×2 multiplier, 4-bit adder, dot
  product, matrix-vector, neuron, 2-2-1 XOR MLP, Mode B (native CSS
  arithmetic comparison), and the M13 canvas pipeline (14×14 dilation +
  OR-downsample gates feeding the drawn-digit classifier).

The generated `dist/index.html` contains, in order: base CSS, `@property`
registrations, primary-input `:has()` mappings, then the netlist as flat
`.rt { --sig: expr; }` declarations in dependency order.

## XOR network (exact)

```
h1 = step(+2x₁ − 2x₀ − 1)     = x1 AND NOT x0
h2 = step(−2x₁ + 2x₀ − 1)     = NOT x1 AND x0
out = step(+2h1 + 2h2 − 1)    = XOR
```

Weights ±2 are chosen so that `w·x` is pure wiring (bit replication): a
power-of-two constant weight never exercises a multiplier. That keeps the
network 100% gate-built at 4-bit signed width. `experiments/network-demo/`
(worker D) shows an equivalent ±1-weight formulation with biases −1/−2;
both are legitimate, this repo ships the ±2 one.

A single linear neuron cannot solve XOR (proof + brute force in
`experiments/network-demo/XOR_LINEAR_PROOF.md`, worker D). Two hidden
threshold neurons can. That is the demo's mathematical point.

## Trained classifier (M10)

The only learned part of the demo. `train/src/glyph.rs` runs a plain
perceptron (deterministic) on 9 exemplars of two 3×3 glyph
classes — top bar vs left bar — and writes `scripts/weights.json`.
`gen/src/main.rs` compiles those weights into the gate netlist:
products of weight × pixel are gate-masked magnitudes (wiring for ±1/±2),
summed with the trained bias at 5-bit signed width; threshold = sign bit.
Training happens at build time; inference happens in CSS.

## Drawn-digit classifier (M11, resurfaced as M13's paint canvas)

A 10-class linear classifier over what a visitor *draws*: a 14×14
paint-feel canvas of invisible checkbox cells (196 inputs `mc0..mc195`,)
zero-JS `<input type="reset">` to clear), reduced to the 49 bits the
classifier trains on entirely inside the CSS gates:

1. **Dilation** — each cell's effective bit is the OR of itself and its
   4-neighbors (edge cells OR fewer): 196 named signals `dl0..dl195`,
   built as nested `max()` OR gates. A 1-cell-wide human stroke lights a
   3-cell-wide band, which is what the downsample and the classifier
   expect.
2. **Block downsample** — a pure OR over each 2×2 block of dilated bits
   (`mn0..mn48`): any ink in the block lights the bit. T=1 is fixed
   architecture (D-011), not a hyperparameter; the generator refuses to
   build anything else.
3. The EXISTING 49-input linear classifier — per-class bit-plane popcount
   weighted scores, argmax tournament, digit minterms, seven-segment decode
   — unchanged from M11.

The surface shows ink, not abstraction: cells are invisible gap-free
hit-targets; each checked cell renders an oversized rounded orange blob
(`border-radius:50%`, ~1.7× the cell pitch, `pointer-events:none`) so a
dragged path reads as one continuous marker stroke. The "network sees"
7×7 preview reads the post-downsample `mn` gate bits — deliberately
pixelated, because it shows the abstraction the classifier actually
receives. Trained at build time by `train/src/mnist.rs` on real MNIST
(see below); compiled by `gen/src/circuit.rs` and wired in
`gen/src/main.rs` §13.

* **Per-class weighted score** (`Net.weighted_score`, one per digit, 10
  total). Weights are constrained to `[-3,3]` so each is pure wiring: a
  weight's magnitude is decomposed into two bit-planes, P0 (`|w|` ∈ {1,3})
  and P1 (`|w|` ∈ {2,3}) — separately for positive and negative weights.
  `Circuit.popcount` (carry-save reduction: repeatedly fold 3 equal-weight
  wires into a full adder, 2 into a half adder) counts each plane's lit
  inputs directly; P1's count is doubled by a zero-wire shift-left, no gate
  needed. `pos = popcount(P0pos) + 2·popcount(P1pos)`, `neg` likewise,
  `score = pos − neg + bias` via one ripple add with carry-in 1 (NOT-and-add
  subtraction) then a second ripple add for the bias constant. Width is
  7-bit signed, asserted at build time from the actual weights/bias for
  that class (not a hardcoded ceiling) — max observed `|score|` is 58.
* **Argmax tournament** (`Circuit.argmax`). A left-fold over the 10 scores:
  incumbent starts at class 0; each round subtracts the sign-extended
  challenger from the incumbent (8-bit width, NOT gates + one ripple add
  with carry-in 1), and the sign bit of that diff selects strict-greater.
  A mux (`OR(AND(s,challenger), AND(NOT s,incumbent))`) updates both the
  running score and the running 4-bit index; ties keep the incumbent, so
  the lowest-index digit wins ties. 9 rounds for 10 classes.
* **Digit minterms** (`Circuit.digit_minterms`). The winning 4-bit index is
  decoded into 10 AND-tree minterm signals (one per digit 0-9), NOT gates
  on the index bits emitted once and reused across all ten.
* **Seven-segment decode** (`Circuit.sevenseg`). Each of the 7 segments is
  an OR-tree over the minterms of the digits that light it (standard
  seven-segment digit-to-segment map). Segment and lit-digit-strip signals
  drive the visible display directly — gate signals, not views.

Per-class score, argmax, and predicted-digit decimal readouts are
native-calc **views** of the registered `*_dec`/`mnist_score{k}_dec`
signals, same display-only convention as every other decimal readout on
the page (`docs/COMPUTATION_MODEL.md` display path policy) — they read
gate outputs, they do not feed back into them.

### Training (build time, outside the runtime artifact)

`train/src/mnist.rs`: deterministic, downloads and caches real MNIST in
`data/mnist/` (gitignored). Preprocessing: binarize each 28×28 image at
>128, crop to the tight bounding box of lit pixels, pad to a centered
square (aspect preserved), area-resample to **14×14** coverage fractions
(the runtime canvas resolution), threshold at `t=0.65` (grid-searched)
into bits, apply one round of 4-neighbor dilation, then reduce each 2×2
block by pure OR (`block_threshold: 1`, fixed architecture — D-011) to
the 49 classifier bits. That simulation is gate-for-gate identical to the
runtime CSS circuit (dilation `dl` gates, OR downsample `mn` gates) —
matching them exactly is the whole point of D-011. An 8-epoch multiclass
perceptron trains on the full 60k training set, then weights are
quantized to `[-3,3]` (scale factor grid-searched) with bias in
`[-13,19]`. Hyperparameter selection (threshold, shuffle seed,
quantization scale, and the glyph-augmentation accept/reject gate) runs
against a drawn-style validation proxy built from the held-out validation
split — thickened strokes, a tighter canvas-filling crop, and varied
binarization threshold, approximating how a person drags a thin stroke on
the 14×14 canvas rather than downsampled MNIST's distribution (D-010,
D-011 in `docs/DECISIONS.md`). Result: 75.42% accuracy on the full 10k
MNIST test set (down from 78.54% under the 7×7 canvas — the cost of the
OR-downsample's forgiving mapping plus the redrawn-proxy selection), 8/10
on the 2×-upscaled canonical drawn-glyph set (misses: 6→5, 9→3), and 6/10
on the thin-stroke 14×14 set (misses: 1→4, 2→7, 6→5, 9→8). Unlike the
retired Python trainer, `train/src/mnist.rs` has no fast path — `make
train` always retrains and overwrites `scripts/weights_mnist.json`.
The runtime page does no input normalization, so the accuracy figure
assumes drawings are large and roughly centered on the canvas — the glyph
sets are demo-fidelity proxies, not claims about arbitrary user drawings.

## Mode B — native CSS arithmetic

The same XOR and matrix rows computed with direct `calc()`/`min()`/`max()`
expressions, ~8 declarations total. Why it cannot replace Mode A for
interactive arithmetic: CSS forbids `var() × var()`. Multiplication of two
runtime values must be built structurally. Multiplication by a build-time
constant is native — which is why the neural network (fixed weights) is
expressible natively but the interactive multiplier is the interesting
part. The demo shows both and labels both.

## Runtime update path

User toggles a checkbox → browser changes form state → `:has()` selector
mapping updates a primary bit → style engine recomputes dependent custom
properties (the whole DAG; no ordering or clock is implied) → LEDs/views
repaint. No script, no event handler, no network. Works from `file://`.

## Where the hard lines are

1. CSS does parsing, selector matching, integer evaluation, style
   invalidation — we did not build those.
2. Build-time Python does composition, elaboration, and reference math —
   the shipped artifact is a flat, unrolled netlist ("composed at build
   time" is the accurate phrase).
3. Decimal readouts use native `calc()` with `×2ⁿ` coefficients — display
   only, outside the gate circuit, labeled in the UI.
4. Computed styles are not selector state; anything that would require
   feedback (recurrent nets, training) is out of scope by construction.

## Verification

`tests/test_runtime.py` (Playwright, Chromium + Firefox):

* static: exactly one `<script>` (the input shim — checked for size and
  absence of computation/network APIs), no handlers, `javascript:`, WASM,
  external resources, network URLs;
* deterministic rebuild (byte-identical);
* gates: exhaustive truth tables; half adder 4 states; full adder 8;
* 2-bit adder + 2×2 multiplier: 16 states; 4-bit adder: 256 states;
* dot product: 16 states; matrix-vector: 4; neuron preactivation+activation;
* XOR MLP: all 4 states including hidden preactivations and hidden outputs;
* Mode B: same XOR/matvec against the same reference;
* trained classifier: 9 exemplars + 32 seeded-random states vs an
  independent reference recomputed from `scripts/weights.json`;
* drawn-digit classifier (M11/M13): dilation and OR-downsample gate
  signals vs a Python reference for hand-picked 14×14 patterns; argmax
  winner, minterms, and seven-segment output vs an independent reference
  recomputed from `scripts/weights_mnist.json` through the same pipeline
  reference; registered-view spot checks; rendered-output checks for the
  "network sees" preview and the paint canvas (no idle border/grid, blob
  rendering); drag-shim behavior on the 196-cell canvas.

Every intermediate the tests read is the same named signal the next stage
consumes — the "genuine composition" acceptance check from
`docs/COMPUTATION_MODEL.md`.
