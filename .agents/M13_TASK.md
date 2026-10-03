# M13 fix batch — adversarial review findings (historical task spec)

This task was implemented in snapshot `c12a1ad` (2026-10-03). The counts and
constraints below refer to that assignment, not today's suite. Current counts
and artifact sizes are in `docs/LIMITS.md`.

You are the builder for this repo (`/home/diego/html-neural-net`, branch `main`, clean at
`2ae837c`). An external adversarial review of commit `2ae837c` produced the findings below.
Fix all five, then run the full verification. Read `docs/DECISIONS.md` (D-009..D-011),
`train/README.md`, `tests/test_runtime.py` first.

## Findings to fix

1. **Medium — docs/DECISIONS.md D-011 overstates methodology purity.** T=1 was selected after
   inspecting per-T glyph results; only T=1 passed the glyph floor. Rewrite the relevant D-011
   wording to state this honestly: the acceptance floors filtered configurations (one pass/fail
   bit per config across the 3 T values), so the final 8/10 and 6/10 glyph figures are
   acceptance-conditioned, and "test set and both glyph sets touched once" is NOT true across
   the milestone's documented runs — say so explicitly instead of claiming otherwise. Keep the
   rest of the rationale (proxy-noise gap, OR semantics, demo-over-benchmark) — the decision
   stands; only the purity claim changes. Match the file's existing tone: this project records
   its own methodology caveats plainly (see D-007's seed-shopping caveat as the model).

2. **Low — train/README.md is stale (two sections).** It still describes D-010: claims glyphs
   never influence selection, calls 0.7854 the current test accuracy, and says 67 tests.
   Update to D-011 reality: shipped JSON reports 0.7542, 75 tests, and selection methodology
   as per the corrected D-011 (including the acceptance-floor caveat).

3. **Low — the "no JavaScript computation" static test is only a token blacklist**
   (tests/test_runtime.py ~151-179). Strengthen: in addition to the existing blacklist, pin the
   shim — assert the script's exact normalized content (or sha256 of whitespace-normalized
   text) against a constant in the test with a comment saying any deliberate shim change must
   update the pin. This makes smuggled computation impossible to pass, not just unlikely.

4. **Low — the deletability claim is never tested end-to-end** (~683-689). Add a test (both
   engines, following the existing per-engine base-class pattern): load a copy of
   dist/index.html with the script tag stripped, click cells to draw a known exemplar,
   assert the classifier's rendered output (digit-strip highlight and/or statusbar counter)
   matches the JSON-derived expected digit. This automates the manual audit already performed.

5. **Low — seven-segment RENDERING is unasserted** (~424-440, ~558-632). Circuit bits are
   checked, but a broken signal→segment styling mapping would pass. Add a rendered check: for
   at least one known input, assert the computed background-color of each of the 7 segment
   elements matches lit/unlit expectations derived from the digit's segment pattern (normalize
   color serialization across engines as the existing tests do).

## Rules

- No behavior changes to the shipped circuit, trainer, or UI — this is docs + tests only,
  except nothing: do not retrain, do not regenerate weights. If `make build` is run it must
  reproduce dist/index.html byte-identically (verify with sha256 vs git HEAD).
- Full suite green in both engines when done (expect 75 + the new tests, 17 abstract-base
  skips).
- ONE commit, conventional style per `git log`, no AI attribution footer, do NOT push, do NOT
  commit `.agents/M13_TASK.md`.

## Report

Print: per-finding disposition (what changed, file:line), new test count per engine, the
dist sha256 check result, and the commit hash.
