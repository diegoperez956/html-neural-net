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

`scripts/circuit.py` is the circuit compiler (build time, plain Python):

* `Circuit` — ordered named-signal declarations; gates, half/full adders,
  ripple adders, structural unsigned multiplication (AND partial products
  shifted and added by ripple adders), two's-complement negation.
* `Net` — neuron builder: for each weight `w` and bit input `x`, the
  product `w·x` is `|w|` bit-masked by `x` (AND gates) then conditionally
  negated (NOT gates + increment) — real gate machinery, no multiplier
  shortcut. Products and bias are summed by ripple adders at 4-bit signed
  width. Threshold = sign bit.
* `scripts/generate.py` — wires the demo: gates, half/full adder, 2-bit
  adder, 2×2 multiplier, 4-bit adder, dot product, matrix-vector, neuron,
  2-2-1 XOR MLP, and Mode B (native CSS arithmetic comparison).

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

The only learned part of the demo. `scripts/train.py` runs a plain
perceptron (deterministic, stdlib-only) on 9 exemplars of two 3×3 glyph
classes — top bar vs left bar — and writes `scripts/weights.json`.
`scripts/generate.py` compiles those weights into the gate netlist:
products of weight × pixel are gate-masked magnitudes (wiring for ±1/±2),
summed with the trained bias at 5-bit signed width; threshold = sign bit.
Training happens at build time; inference happens in CSS.

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

* static: no `<script`, handlers, `javascript:`, WASM, external resources,
  network URLs;
* deterministic rebuild (byte-identical);
* gates: exhaustive truth tables; half adder 4 states; full adder 8;
* 2-bit adder + 2×2 multiplier: 16 states; 4-bit adder: 256 states;
* dot product: 16 states; matrix-vector: 4; neuron preactivation+activation;
* XOR MLP: all 4 states including hidden preactivations and hidden outputs;
* Mode B: same XOR/matvec against the same reference;
* trained classifier: 9 exemplars + 32 seeded-random states vs an
  independent reference recomputed from `scripts/weights.json`.

Every intermediate the tests read is the same named signal the next stage
consumes — the "genuine composition" acceptance check from
`docs/COMPUTATION_MODEL.md`.
