# Design: MLP hidden layer in the CSS circuit

Status: design. Backed by measured numbers in `RESEARCH_SCALE.md`.

## Goal

Linear 10-class classifier (~80% MNIST test) -> one hidden layer of
threshold neurons, target 90%+, still pure HTML+CSS at runtime.

## Architecture

Same primitives the page already ships, just stacked:

```
49 input bits (mn0..mn48)
  |
  v
H hidden neurons:  score_h = weighted_score(w_h, bias_h, inputs)   (7-bit signed)
                   h_out   = NOT(score_h[6])                        (threshold: sign bit)
  |
  v
10 output neurons: score_k = weighted_score(v_k, bias_k, h_out bits) (7 or 8-bit)
  |
  v
gate argmax (existing tournament, now also yields top-2 margin)
  |
  v
minterms -> seven-seg + digit strip + confidence meter (existing)
```

No new gate kinds. `weighted_score` (bit-plane popcount, weights in
[-3,3]) and sign-bit thresholding already exist and are test-proven.

## Cost (measured, synthetic-sparse weights)

| config | signals | bytes | recalc |
|---|---|---|---|
| linear 49 (today) | 4.1k | 0.74 MB | floor |
| MLP H=8 | 5.9k | 1.06 MB | floor |
| MLP H=16 | 9.4k | 1.73 MB | floor |
| MLP H=32 | 16.8k | 3.16 MB | floor (p95 creeps) |

Recommendation: H=16.

## Constraints that shape training (the hard part)

1. **Weights must quantize to integers in [-3,3].** Wiring applies weights
   as bit-plane popcounts; magnitude 3 = both planes. No exceptions.
2. **Sparsity is not optional.** Plane sums (pos and neg separately) must
   fit signed-7: |P0| + 2|P1| <= ~60 per neuron. Dense 49-input neurons
   violate this. Zeros are also what keeps H=16 at 1.7 MB instead of ~3 MB.
3. **Output layer width**: with H <= 21 keep 7-bit scores; above that widen
   output scores to 8 bits (argmax is width-generic).
4. **Hidden thresholds are sign bits**, i.e. biases are folded into the
   weighted score; no separate comparator circuit needed.

## Training sketch (replaces the current single-layer trainer stage)

1. Train float MLP (49 -> H -> 10) in the Rust trainer, plain SGD, no
   frameworks (project rule: no Python at build, nothing shipped).
2. Prune: magnitude-threshold smallest |w| per neuron until plane-fit
   constraint satisfied with slack; retrain remaining weights (1-2 rounds).
3. Quantize [-3,3] by scale-search (same approach as today's trainer, just
   per-neuron), snapping zeros to zero.
4. Evaluate on the 10k test set; accept only if >= linear baseline.
5. Emit weights JSON: hidden weights H x 49, hidden biases H, output
   weights 10 x H, output biases 10, exemplars, accuracy.

Accuracy expectation: quantized-sparse MLP at H=16 on 7x7 MNIST typically
lands 88-93%; if pruning hurts, H=32 headroom exists (3.2 MB page).

## Generator changes

- `generate.py` (or its Rust successor): build H `weighted_score` neurons,
  threshold each, feed `NOT`-ed bits into 10 output `weighted_score`
  neurons, then the EXISTING argmax/minterm/seven-seg/margin path unchanged.
- Tests: extend `MnistClassifierTests.ref` to the MLP forward pass (float
  reference in Python test-side), keep the exhaustive exemplar + random
  battery, assert margin as today.

## Non-goals

- Multiple hidden layers (signal budget says one is plenty).
- 12x12 canvas simultaneously (pick one upgrade first; revisit after).
