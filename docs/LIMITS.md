# Limits and recorded measurements

## Current artifact

As rebuilt on 2026-10-03, `dist/index.html` has 6,834 registered signals and
is exactly 1,622,282 UTF-8 bytes (about 1.62 MB). `dist/no-js.html` has the same
signals and is 1,619,905 bytes. The default page contains one optional input
shim (35 source lines after trimming, 2,228 body bytes),
not JavaScript inference. Registrations include inputs, aliases, native
comparison calculations, and decimal views. They are not all gates.

The production XOR network uses 177 gates. Its twelve preactivation aliases
and one decimal view bring its named-signal total to 190.
The old 123-gate count belongs to an earlier experiment.

The 14×14 drawing path adds 1,071 input and preprocessing signals:
196 checkbox inputs, 728 dilation ORs, and 147 downsample ORs.
The digit classifier and its readouts add another 4,995 signals.

Measure file bytes and registration count from the artifact you plan to show:

```bash
wc -c dist/index.html
grep -c '^@property --' dist/index.html
```

## Historical timing data

The CSV files in `benchmarks/` record experiments from 2026-08-30 with Chromium
149 and Firefox 151. They are not a fresh performance run of the revised UI.
The three `scripts/benchmark*.py` entry points depended on the Python circuit
compiler deleted in D-008 and were removed on 2026-10-03. These measurements
can no longer be regenerated with the current toolchain. The CSVs are kept
unchanged as dated historical evidence; see [their record](../benchmarks/README.md).

The old probes measured automation-assisted checkbox changes followed by a
forced style read. Their times include browser automation overhead. They are
not isolated CSS evaluation times, frame rates, or measured gate delays.

The recorded synthetic signal-count results are:

| Signals | Browser | Page bytes | Reported load ms | Median update ms | p95 update ms |
|---|---|---|---|---|---|
| 1,002 | Chromium | 163 KB | 45 | 31 | 43 |
| 1,002 | Firefox | 163 KB | 525 | 48 | 64 |
| 3,002 | Chromium | 497 KB | 68 | 30 | 36 |
| 3,002 | Firefox | 497 KB | 471 | 59 | 70 |
| 6,002 | Chromium | 998 KB | 98 | 31 | 52 |
| 6,002 | Firefox | 998 KB | 551 | 60 | 73 |
| 10,002 | Chromium | 1.67 MB | 111 | 29 | 53 |
| 10,002 | Firefox | 1.67 MB | 566 | 60 | 73 |

These measurements show no clear additional slowdown over that range under
that probe. They do not prove recalculation has constant cost, that every
similar-sized network is fast, or that pointer drawing meets a frame budget.
The recorded load interval also includes page creation and a style flush.

## Structural growth

A full adder uses five gate signals. An N-bit ripple addition has N such
stages at the chosen output width. The demo pads operands to retain the carry,
so its four-bit input adder has five stages.

An N×M unsigned multiplier emits N·M AND partial products. It combines rows
with M-1 additions of width N+M. For equal-width operands, gate count therefore
grows roughly quadratically.

CSS can multiply two numeric variables directly. This growth is a cost of
choosing gate mode, not a mandatory cost of CSS multiplication.

Fixed small weights make the classifier cheaper than a collection of general
multipliers. Popcount groups reduce the weighted sum, and a bit shift doubles
a count without another multiplier.

Very deep dependency graphs and larger generated files may hit browser-specific
limits. No general ceiling was established by this audit.

## Accuracy is a separate limitation

The 3×3 bar classifier has nine training examples and no held-out evaluation.
It demonstrates that learned weights can compile to a circuit.

The digit classifier's saved metadata reports 75.42% MNIST test accuracy.
This is an observed result for these weights, not a mathematical ceiling for
linear models. The current audit checked inference, not the full training run.

The model gets 8/10 canonical upscaled glyphs and 6/10 thin-stroke glyphs.
Development used those sets as acceptance filters, so their results are
acceptance-conditioned. They are too small to establish general drawing
accuracy. Read [the training notes](../train/README.md) before quoting them.

The browser does not crop, center, or normalize your drawing. It dilates and
downsamples checkbox cells. Small and off-center drawings can differ sharply
from the training inputs. Dilation can also merge strokes or close gaps.

The output is always the class with the largest score. There is no "unknown"
class. A blank drawing chooses the largest bias. A score margin is not a
calibrated probability.

## Browser requirements

The full page needs `:has()`, integer `@property` registrations, CSS arithmetic,
CSS counters, and `color-mix()` for the LEDs.
The documented feature floors are Chromium 111+ and Firefox 128+.
The actual verification run used Chromium 149 and Firefox 151.
Older versions at those feature floors were not rerun here.
Safari 16.4+ is expected to support the required features but is not tested.
There is no checked-in CI workflow.

## Test limits

The current suite runs 15 Rust tests and 94 Python tests. Of the latter,
85 are runtime checks (40 per browser and 5 static), with 16 abstract-base
class skips; 9 cover history inventory and video math. The old 67- and 75-test
figures in the decision log describe earlier milestones, not this suite.

Small circuits have exhaustive tests: four gate input states, eight full-adder
states, sixteen two-bit operand pairs, and 256 four-bit adder pairs.
The XOR network's four inputs are tested with hidden activations.

The drawing canvas has 2^196 input states. Its tests cover selected edge
patterns, thin strokes, upscaled examples, and seeded random inputs.
That is not exhaustive testing of the classifier.

The runtime graph has no training, feedback state, batching, or recurrent
layers. Those are limits of this particular graph. They do not establish
what every other CSS program can or cannot compute.
