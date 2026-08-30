# Limits

Measured, not asserted. All numbers from `scripts/benchmark.py` and the
generated artifacts, Chromium 149 / Firefox 151 via Playwright.

## Sizes (dist/index.html, the full demo)

| metric | value |
|---|---|
| file size | ~153 KB |
| signal declarations (custom properties) | 768 |
| of which XOR MLP | 123 |
| of which trained 3×3 classifier | ~260 |
| of which Mode B (native comparison) | 8 + 15 decimal-view signals |
| `@property` registrations | 768 |
| CSS rules | 1 659 |
| DOM elements | 264 |

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
the 3×3 classifier at ~260 signals are far below the pain point. A larger
learned classifier (say 16 inputs × 8 hidden × 2 outputs at 3-bit signed
weights) would cost on the order of a few thousand signals and a few
hundred KB — possible, but the demo gets worse, not better, past this
point. That is why XOR plus one trained classifier is the shippable demo
and the README says so.

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
5. **Update cost:** one toggle invalidates the whole DAG. Browsers do
   fine at ~450 signals; thousands would need per-section isolation
   (containment), which the architecture supports but the demo doesn't
   need.
