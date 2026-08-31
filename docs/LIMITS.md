# Limits

Measured, not asserted. All numbers from `scripts/benchmark.py`,
`scripts/benchmark_scale.py`, and the generated artifacts, Chromium 149 /
Firefox 151 via Playwright.

## Sizes (dist/index.html, the full demo)

| metric | value |
|---|---|
| file size | ~1.18 MB (1 182 392 bytes) |
| signal declarations (custom properties) | 5 669 |
| of which XOR MLP | 123 |
| of which trained 3×3 classifier (M10) | ~260 |
| of which Mode B (native comparison) | 8 + 15 decimal-view signals |
| of which drawn-digit MNIST classifier (M11) | 4 852 |
| `@property` registrations | 5 669 |
| CSS rules | 11 577 |
| DOM elements | 424 |

M11 breakdown: 10 per-class weighted scores (bit-plane popcount) ~318
signals each (3 178 total), argmax tournament (streaming top-2 + margin)
1 545, digit minterms 68, seven-segment decode 49, confidence-meter
decimal-view readouts (score/digit/margin displays) 12.

## Scaling: N-bit ripple adder (generated in isolation)

| bits | signals | file bytes | recalc latency (toggle → computed style, median) |
|---|---|---|---|
| 1 | 12 | 2 148 | ~30 ms |
| 2 | 19 | 3 290 | ~30 ms |
| 4 | 33 | 5 574 | ~30 ms |
| 8 | 61 | 10 142 | ~29 ms |
| 12 | 89 | 14 798 | ~3–30 ms |

Growth is linear: ≈ 7.4 signals and ≈ 1.2 KB per operand bit. The ~30 ms
figure is the automation floor (Playwright round-trip + forced synchronous
style read); real interactive latency is imperceptible — one toggle
recomputes a few hundred custom properties, and the browser does not do
that synchronously per paint.

## Scaling: whole-page signal count (`scripts/benchmark_scale.py`,
`benchmarks/signal_scaling.csv`)

Generated pages at increasing signal count, measured load time (navigate →
DOMContentLoaded) and toggle→computed-style recalc latency, two engines:

| signals | engine | page bytes | load (ms) | recalc median (ms) | recalc p95 (ms) |
|---|---|---|---|---|---|
| 1 002 | Chromium | 163 KB | 45 | 31 | 43 |
| 1 002 | Firefox | 163 KB | 525 | 48 | 64 |
| 3 002 | Chromium | 497 KB | 68 | 30 | 36 |
| 3 002 | Firefox | 497 KB | 471 | 59 | 70 |
| 6 002 | Chromium | 998 KB | 98 | 31 | 52 |
| 6 002 | Firefox | 998 KB | 551 | 60 | 73 |
| 10 002 | Chromium | 1.67 MB | 111 | 29 | 53 |
| 10 002 | Firefox | 1.67 MB | 566 | 60 | 73 |

Recalc p95 flattens at ~52 ms (Chromium) / ~73 ms (Firefox) by 6k signals
and stays flat through 10k — recalc cost does not keep growing with
signal count past that point. Load time scales with page bytes: Firefox
one-time load reaches ~566 ms at 10k signals (1.67 MB); Chromium load
stays ~111 ms at the same size. M11 alone (4 192 signals) sits well inside
this measured, flat-recalc range.

## Structural cost floor

- Full adder: 5 gate signals.
- N-bit adder: 5N signals (+carry wiring).
- N×M unsigned multiplier (AND partial products + ripple adds):
  N·M AND gates + (M−1)·(N+M)-ish adder signals — quadratic-ish in width.
- Neuron (2 inputs, 3-bit products, 4-bit sums): ~41 signals.
- 2-2-1 XOR MLP: 123 signals.

## Why it gets pathological (measured from experiments)

- `var() × var()` is illegal in CSS. Any multiplication of two runtime
  values must be a circuit. Doubling operand width roughly quadruples the
  multiplier netlist.
- Multiplier depth: a 4×4 multiplier chains ripple adders to depth ~41
  nested `calc()`; Chromium 149 parses it fine, but every added bit grows
  expression text superlinearly (see arithmetic worker's
  `experiments/arithmetic/dist/complexity.json`: signed 8×8 multiply =
  323 wires / 18.6 KB for the multiply alone).
- 256-state exhaustive testing of the 4-bit adder takes ~30 s in Playwright
  (two engines). An 8-bit multiplier (65 536 states) is testable in Python
  but browser-exhaustive testing stops being practical around 2^16.

## Practical ceiling (honest estimate)

Gate-built arithmetic stays tractable through 8–12 bit adders (≈ 60–90
signals, ≈ 10–15 KB) and 4×4 multipliers. The XOR MLP at 123 signals and
the 3×3 classifier at ~260 signals are far below the pain point. The M11
drawn-digit classifier (4 192 signals: 10 popcount-decomposed scores,
argmax tournament, minterms, seven-segment decode) is the first M-series
piece large enough to need the scaling question answered rather than
assumed — `benchmarks/signal_scaling.csv` answers it: recalc p95 is flat
from 6k through 10k signals, and the whole page at 5 669 signals sits
comfortably below that flat region. A per-term neuron-sum encoding of the
same 10-class classifier (no bit-plane popcount) was estimated at ~25k
signals — the popcount decomposition is what kept M11 inside the
benchmarked range instead of past it (see `docs/DECISIONS.md` D-006).

## Classifier accuracy limits (honest, not asserted)

* M10 (3×3 glyph, two classes): trained on 9 hand-built exemplars, no held-out
  test set — a toy proof that gate-composed weighted sums work, not an
  accuracy claim.
* M11 (7×7 drawn digit, ten classes): 82.46% on the full 10k MNIST test set;
  a single-layer linear classifier over a 7×7 binary grid, so this is the
  ceiling for that model class, not a bug to chase. On the canonical
  drawn-glyph fidelity set it gets 8/10, with known misses at 6 (predicted
  5) and 9 (predicted 3) — both digits whose 7×7 binary silhouette is close
  to a neighboring digit's. The runtime page performs no input
  normalization; the accuracy figures assume a drawing that is large and
  roughly centered on the grid, matching the training preprocessing
  (bounding-box crop + centered-square pad before the 7×7 resample). A
  small, off-center, or corner-drawn digit is out of distribution for the
  trained weights and not covered by either accuracy number.

## Browser support

| feature | Chromium | Firefox | Safari |
|---|---|---|---|
| `:has()` | 105+ | 121+ | 15.4+ |
| `@property` | 85+ | 128+ | 16.4+ |
| `color-mix()` (LED styling only) | 111+ | 113+ | 16.2+ |

Floor = Chromium 111+ / Firefox 128+ for the full experience (LED styling
needs `color-mix()`; math needs `@property` + `:has()`). Safari 16.4+
should support the mechanics but is **not tested in this repo**. No
experimental flags. Style queries are *not* used (Firefox
comparison-operator gap found in experiments; see ARCHITECTURE).

## What breaks first

1. **Selector size:** more checkboxes = more `:has()` mappings; fine.
2. **Netlist size:** multiplier width grows quadratically.
3. **Depth:** very deep `calc()` nesting; Chromium tolerated depth 41;
   engine limits are unpublished and browser-specific.
4. **Test time:** exhaustive in-browser verification stops being pleasant
   past 2^12 states.
5. **Update cost:** one toggle invalidates the whole DAG. Measured flat
   through 10 000 signals (recalc p95 ~52 ms Chromium / ~73 ms Firefox,
   `benchmarks/signal_scaling.csv`); the 5 669-signal page is well inside
   that range. Past whatever point recalc stops being flat, per-section
   isolation (containment) is the fix — the architecture supports it, the
   demo hasn't needed it yet.
