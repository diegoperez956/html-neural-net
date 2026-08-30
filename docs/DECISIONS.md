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
