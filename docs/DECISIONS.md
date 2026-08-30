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
