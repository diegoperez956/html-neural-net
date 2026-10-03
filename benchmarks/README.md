# Historical benchmark records

These CSVs were recorded on **2026-08-30** and are retained unchanged as
historical evidence, not measurements of the current D-011 page or UI.

| CSV | Original probe (removed) | Scope |
|---|---|---|
| `adder_scaling.csv` | `scripts/benchmark.py` | Operand-width scaling, Chromium |
| `signal_scaling.csv` | `scripts/benchmark_scale.py` | Synthetic signal counts, Chromium and Firefox |
| `clf_scaling.csv` | `scripts/benchmark_clf_scale.py` | Linear/MLP circuit shapes, Chromium and Firefox |

The probes depended on `scripts/circuit.py`, deleted in D-008. All three were
removed on 2026-10-03 rather than ported. **These results can no longer be
regenerated with the current toolchain.** Original code remains in Git history;
using it would require restoring the historical compiler and environment,
not merely running a current build. Generated raw pages were ignored and are
not part of this record.

The timings include browser automation and forced style reads. They are not
isolated CSS evaluation times or guarantees about live drawing latency.
The classifier probes used synthetic sparse weights except `linear49-real`,
which used that date's M11 weights, not today's D-011 model.

See [current limits](../docs/LIMITS.md),
[historical scale research](../docs/RESEARCH_SCALE.md), and
[the rejected MLP design](../docs/DESIGN_MLP.md) for interpretation.
