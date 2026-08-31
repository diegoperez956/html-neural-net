# Decisions

Decision log. Each entry records hypothesis, experiment, evidence, hostile review, and disposition.

## D-001 (lead) — custom-property netlist architecture verified

Hypothesis: gate-built circuit as typed integer custom-property declarations with interdependent named wires (carry chains) resolves correctly in Chromium.
Experiment: `experiments/lead-vertical/proto.html` — 2-bit ripple adder + 2x2 gate multiplier, @property <integer>, counter display.
Evidence: Playwright Chromium 149, all 16 input states correct for sum, both carries, and product.
Disposition: architecture anchored. Gate basis = min/max/subtract. Workers build on this.

## D-002 (lead) — absorbed native-css + verification worker scope

Context: both workers silent ~50min with no commits; lead already delivered Mode B (native CSS comparison, 8 declarations vs 450 gate signals, tested) and the two-engine exhaustive suite (30 tests).
Disposition: kill both sessions; worker slots freed for final adversarial + optimization rounds. Their intended outputs exist on main: scripts/generate.py Mode B, tests/test_runtime.py.

## D-004 (lead) — M10 trained classifier added; optimization swarm folded

M10: perceptron-trained 3×3 glyph classifier (top bar vs left bar), trained at build time by scripts/train.py on 9 exemplars, weights compiled to gates. 34 tests green in 32 s.
Optimization swarm: with DeepSeek-only budget and all measurable targets already at parity (152 KB single file, ~30 ms automation-floor recalc), a parallel swarm adds review latency without clear wins. Decision: lead does a single integrated optimization pass; final DeepSeek review is the gate.

## D-005 (lead) — worker branch integration policy

Worker branches stay on experiment/* unmerged; their validated findings are integrated into main by the lead (css-logic: var-graph over style queries; arithmetic: two's-complement feasibility, var*var illegality; network-demo: XOR proof + alternate ±1 formulation; ui: honest-labeling vocabulary, a11y patterns; prior-art: docs merged). Rationale: main ships one validated architecture; worker artifacts remain inspectable as experiments.

## D-006 (lead) — M11 architecture: bit-plane popcount over per-term neuron sums

Hypothesis: a 10-class drawn-digit classifier (M10's `Net.neuron` pattern, scaled to 49 inputs × 10 classes) would land page scale in territory nobody had measured, and a per-term gate-masked-magnitude sum per class (M10's approach) would cost far more than a popcount-plane decomposition for the same weight range.
Experiment: estimated both encodings' signal counts before building. Per-term neuron sum: 49 AND-masked products per class (each needing sign handling and full ripple-adder summation) ≈ 25k signals for 10 classes. Bit-plane popcount (`Net.weighted_score`): weights in [-3,3] decomposed into two bit-planes per sign, summed by carry-save popcount reduction instead of per-term addition ≈ 4.2k signals for the same 10 classes (measured: 3 284 for the 10 scores, 4 192 including argmax/minterms/seven-seg). Gated the whole M11 addition on `scripts/benchmark_scale.py` first: generated isolated pages at 1k/3k/6k/10k signals, measured load and recalc latency in both engines (`benchmarks/signal_scaling.csv`) before committing to build M11 at all.
Evidence: recalc p95 flat at ~52 ms (Chromium) / ~73 ms (Firefox) from 6k through 10k signals — no measured cliff in the range M11 would land in (page total 4 971 signals). Popcount decomposition ships at ~6x fewer signals than the per-term alternative for the same accuracy.
Preprocessing course-correction, same worker cycle: first training pass (raw 28×28 4x4-block downsample, no bounding-box crop) scored 61% test accuracy and got 1/10 on the canonical drawn-glyph set — thin strokes near the image border were starved by uncropped downsampling. Bounding-box crop + centered-square pad before the 7×7 resample (matching how a user actually fills the grid) fixed both: 79.98% test accuracy, 8/10 glyphs.
Disposition: bit-plane popcount adopted for M11's per-class score; benchmark-gated GO was the actual release gate, not intuition about signal count. Preprocessing redesign (bbox + square-pad) shipped as the only correct version — the uncropped pipeline was not kept as a fallback.
