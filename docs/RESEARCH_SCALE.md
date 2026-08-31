# Scale research: bigger circuits in pure CSS

Measured, not asserted. Method: standalone probe pages with the real circuit
shapes (bit-plane popcount scores, threshold hidden neurons, gate argmax,
minterm + seven-seg decode), synthetic sparse quantized weights ([-3,3],
plane-fit guarded) except `linear49-real` which uses the shipped trained
weights. Toggle an input checkbox → force computed style → time it.
20 iters, Chromium + Firefox headless via Playwright (same pattern as
`benchmark_scale.py`; ~30 ms Chromium figures are the automation floor).

Tool: `scripts/benchmark_clf_scale.py` (+ `--selftest`), raw pages in
`benchmarks/raw/clf-*.html`, data in `benchmarks/clf_scaling.csv`.

## Results

| config | signals | bytes | Cr load | Cr recalc med/p95 | Ff load | Ff recalc med/p95 |
|---|---|---|---|---|---|---|
| linear49-real (shipped M11) | 4 102 | 0.74 MB | 78 ms | 31/38 ms | 508 ms | 59/70 ms |
| linear49 (synthetic) | 4 834 | 0.89 MB | 78 ms | 30/53 ms | 569 ms | 58/75 ms |
| mlp49-H8 | 5 856 | 1.06 MB | 88 ms | 30/51 ms | 534 ms | 61/73 ms |
| mlp49-H16 | 9 378 | 1.73 MB | 106 ms | 31/53 ms | 580 ms | 63/76 ms |
| mlp49-H32 | 16 819 | 3.16 MB | 174 ms | 31/68 ms | 629 ms | 81/101 ms |
| linear144 | 5 177 | 0.95 MB | 83 ms | 30/38 ms | 552 ms | 58/73 ms |
| mlp144-H8 | 6 024 | 1.08 MB | 100 ms | 31/50 ms | 540 ms | 59/76 ms |
| mlp144-H16 | 9 716 | 1.80 MB | 114 ms | 30/53 ms | 555 ms | 61/69 ms |

## Findings

1. **No cliff up to 16.8k signals / 3.2 MB.** Chromium median recalc is flat
   at the automation floor (~30 ms) across a 4× signal range; p95 creeps
   38→68 ms. Firefox median creeps 58→81 ms. Interactive use stays
   imperceptible; the automation floor, not the engine, dominates.
2. **Cost model (per measured points):** MLP over 49 inputs ≈ 4.1k +
   ~330/neuron + ~0.9k output/argmax overhead. 144-input linear ≈ same cost
   as 49-input MLP-H8 — input width and hidden width trade off nearly 1:1.
3. **Binding constraint = file weight, not recalc.** 3.2 MB page is the
   only user-visible regression (load 174 ms Chromium / 629 ms Firefox).
4. **Weight sparsity drives MLP cost.** Cost per hidden neuron assumes
   quantized-sparse weights (zeros are free — unweighted inputs drop out of
   popcount planes). Training must quantize to [-3,3] AND prune; dense
   weights would violate the signed-7 plane fit (measured guard: pos/neg
   plane sums ≤ 60) and inflate the netlist.
5. Untested beyond the table: mlp144-H32 (~28k signals / ~5+ MB est.).
   Extrapolation says recalc survives, page weight does not deserve it.

## Verdicts

- **MLP hidden layer @ 49 inputs, H=16: GO.** 9.4k signals, 1.7 MB,
  recalc unchanged. Sweet spot for accuracy-per-byte.
- **H=32: GO with caveat** (3.2 MB page; only if accuracy demands it).
- **12×12 canvas, linear: GO** (5.2k signals, ~1 MB) — but accuracy gain
  from more pixels is small for a linear model; prefer MLP first.
- **12×12 + MLP: GO at H≤16** (1.8 MB). Pick ONE of canvas-size or
  hidden-width as the upgrade if page weight matters; both only if it
  doesn't.
- **Confidence meter (top-2 margin): GO** — O(1) extra tournament state,
  noise at these scales.

Recommended build order: confidence meter → MLP H=16 @ 7×7 → (optional)
12×12. Quantization-aware training (float train → prune → [-3,3] quantize →
re-measure) is the accuracy-critical path; see docs/DESIGN_MLP.md in the
features worktree.
