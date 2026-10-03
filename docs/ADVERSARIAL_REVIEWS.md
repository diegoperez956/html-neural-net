# Adversarial reviews

Each checkpoint review is recorded with disposition per finding: FIXED / EXPERIMENTALLY DISPUTED / ACCEPTED-AS-DOCUMENTED (scope).

## Checkpoint 1 — computation model (DeepSeek V4 Pro High, 2026-08-30)

Raw output preserved in git history (`docs/ADVERSARIAL_REVIEWS.md` first version) and session log. Summary with dispositions:

### Release blockers

- **BLOCK-1** no implementation existed at review time; all claims untested prose. → **FIXED (post-review):** `experiments/lead-vertical/proto.html` committed on main: typed custom-property gate netlist, 2-bit ripple adder, 2×2 gate multiplier, 16/16 states correct in Chromium 149 via Playwright. Remaining stages land incrementally with tests.
- **BLOCK-2** "logic primitives implemented in HTML/CSS" is false wording; gates are native min/max/calc arithmetic reinterpreted on the bit domain. → **FIXED:** claim wording changed in `COMPUTATION_MODEL.md` ("native CSS arithmetic primitives + bit-domain logic identities, wired as a build-time netlist").
- **BLOCK-3** integer typing mechanism unspecified. → **FIXED:** decision recorded: all signals are registered `@property { syntax: "<integer>"; inherits: true }` on one common ancestor. Support floor Chromium 85+, Firefox 128+, Safari 16.4+. Confirmed working in Chromium 149 lead experiment.
- **BLOCK-4** fixed-width two's-complement design absent. → **ACCEPTED:** width table added to `COMPUTATION_MODEL.md` (see Numeric formats). Adder width = N+1; multiplier width = 2N; dot/matrix sums width computed per network; XOR MLP uses 3-bit product words and 4-bit signed sums.
- **BLOCK-5** display-path bit→integer composition uses native multiplication by powers of two, silently undermining the "no native multiplication" gate claim. → **FIXED:** display composition now explicitly labeled a native-calc *view* outside the gate circuit; primary gate-mode displays are per-bit LEDs.
- **BLOCK-6** COMPUTATION_MODEL.md untracked at review time. → **FIXED:** committed on main (f2f856a).

### High

- **H-1** XOR emitted as one native equation; no reduction to a smaller basis. → **ACCEPTED:** wording now says "basis primitives" not "reduction". AND/OR/NOT/XOR are four named bit-domain identities over two native primitives (min/max, subtraction).
- **H-2** custom properties are element-scoped; netlist scope unspecified. → **FIXED:** documented + asserted by tests: every signal declared on one `.runtime` ancestor, read by descendants only.
- **H-3** hidden-layer propagation via var() graph unproven. → **EXPERIMENTALLY DISPUTED (post-review):** same mechanism proven by lead experiment carry chain (`--s1` consumes `--c0`; `--c1` consumes `--s1a` and `--c0`). MLP proof pending same verification.
- **H-4** browser support floor unestablished. → **FIXED:** floor documented (see Compatibility).
- **H-5** scalability asserted not measured. → **ACCEPTED:** benchmark plan in `docs/LIMITS.md` once generator lands.

### Medium / Low

- **M-1** "signal ∈ {0,1}" contradicts multi-bit words. → **FIXED:** vocabulary split: *bit signal* vs *word signal*.
- **M-2** "composable" is build-time; runtime is flat netlist. → **FIXED:** claim says "composed at build time".
- **M-3** counter rendering of negatives unverified. → **ACCEPTED:** negative counter rendering added to browser test matrix.
- **M-4** per-signal visibility bloat. → **ACCEPTED:** display subset chosen deliberately; DOM budget measured in LIMITS.md.
- **M-5** prior-art unsubstantiated. → **ACCEPTED:** `experiment/prior-art` worker assigned.
- **M-6** UI pulse animations must not imply clocked computation. → **ACCEPTED:** UI brief mandates "cosmetic highlight" labeling.
- **L-1** Makefile/test stubs fail out of box. → **ACCEPTED:** fixed as milestones land; `make test` will skip-with-message until harness exists.

### Adopted experiment list

The reviewer's 12 experiments become `tests/` acceptance list: (1) zero-script/offline static gate; (2) typing probe both @property and unregistered; (3) exhaustive gate truth tables + bit-invariant assertion; (4) scope invariance between visible intermediate and downstream consumer; (5) structural adder/multiplier static check (no operand-pair lookup selectors); (6) display-path policy; (7) hidden-layer same-named-signal proof; (8) full network vs independent reference; (9) per-stage overflow width table; (10) scalability growth curve; (11) prior-art citations; (12) deterministic rebuild byte-identity.

## Checkpoint 2 — final pre-release review (DeepSeek V4 Pro High, 2026-08-30)

Reviewer reproduced `make build` + `make test` (34 tests green at review time), confirmed zero-JS/offline, genuine composition (no lookup selectors), correct math, deterministic rebuild, honest prior-art framing.

### Blocker

- **BLOCK-1** decimal readouts silently dead: `dec_css` double-wrapped `var(--var(--…))`, so 10 of 11 gate-mode decimal views rendered "0" always; test suite blind because it read computed custom properties, not rendered text. → **FIXED:** decimal views now materialize as registered `*_dec` signals (single clean `var()` into the counter); signed views use a negative sign-bit coefficient (verified: `−3` renders); new `DisplayTests` assert resolved `::after counter-reset` values (`v 5`, `v −3`, …) plus rendered digits in the accessibility tree; dead view CSS removed.

### High

- **H-1** section 11 (native comparison) showed the gate-mode `d_xor` signal instead of `d_nb_out`. → **FIXED:** now `d_nb_out`, asserted by test.
- **H-2** display layer never end-to-end tested; dead view classes present. → **FIXED:** see BLOCK-1; 7 rendered-display tests added (both engines).

### Medium

- **M-1** "~14 declarations" vs "~8" inconsistency. → **FIXED:** demo says 8.
- **M-2** README floor said Chromium 105+ but `color-mix()` needs 111+. → **FIXED:** floor stated as Chromium 111+.
- **M-3** Safari listed as supported, never tested. → **FIXED:** README + LIMITS now say "should work, not tested here".

### Low

- `negate()` dead variable. → **FIXED.**
- "pure wiring" overstatement for ±2 weight application. → **FIXED:** reworded to "reduces to wiring (no multiplier circuit needed)".

Final state at that checkpoint: 58 tests green across Chromium + Firefox.
The zero-script result describes the 2026-08-30 artifact, not today's optional
input shim.

## Checkpoint 3: accuracy and model selection (2026-10-03)

An independent hostile review examined `main` at `f668921` before publication.
It ran `make test`, rebuilt both runtime pages byte for byte, and reran
`train mnist`, reproducing the checked-in JSON exactly. The baseline had
15 passing Rust tests and 94 passing Python tests, with 16 abstract-base skips.
Headless Chromium and Firefox confirmed native input, reset, script-disabled
inference, and no runtime requests beyond the document. The input shim only
changes checkbox state; CSS computes preprocessing, scores, and display.

The reviewer also shifted and scaled normalized test digits, evaluated all
780 combinations of T, coverage threshold, and seed, and mutated individual
preprocessing gates. Those diagnostics used scratch trainer code, not a
checked-in command. Their findings correct the selection story; they do not
establish accuracy on human canvas drawings. No human drawings were evaluated.

| Finding | Disposition |
|---|---|
| F1: live 75% label hides position and size sensitivity | FIXED. Label now names cropped, centred MNIST. The canvas asks for big, centred input. README and LIMITS record the horizontal-shift results and 30.9% uncropped result. |
| F2: T=1 rationale rests on one winner per T | ACCEPTED-AS-DOCUMENTED. The D-011 addendum records all 260 configurations per T. T=1 remains an arbitrary pick, without retraining or a claim of drawing superiority. Unsupported advance-registration and noise claims were removed. |
| F3: glyph results depend heavily on seed | ACCEPTED-AS-DOCUMENTED. README, LIMITS, training notes, and D-011 report 4–8/10 upscaled and 3–7/10 thin across the 20 seeds at the shipped threshold. The shipped seed is the proxy winner. |
| F4: proxy description and sanity check are unsupported | FIXED. Current descriptions name tighter clipping and varied source thresholds, not source dilation. The comparison print is informational. No claim of proxy validation or evaluated human drawings remains in the current selection account. |
| F5: thin set is seven-segment-shaped | FIXED. Public descriptions call it synthetic and note the right-of-centre '1'. |
| F6: two missing-input preprocessing mutants survive | FIXED. Both engines now check every single-cell input against all 196 dilation and 49 downsample outputs. Pure OR stages are determined by those input sets; classifier coverage is still not exhaustive. |
| F7: source comments contradict acceptance-data use | FIXED. Trainer comments identify test-triggered diagnostics, rejection floors, glyph-conditioned architecture choice, and the current proxy transforms. |
| F8: README metrics are not tied to saved metadata | FIXED. A published-metrics contract test compares the README's three saved-model figures with JSON values. |
| F9: circuit summary implies multipliers feed digit inference | FIXED. The summary names popcount scores and argmax. The XOR and arithmetic examples remain separate. |
| F10: explanation undercounts dilation signals | FIXED. It names 196 outputs built from 728 two-input max signals. |
| F11: headline and review trail are stale; dist-only doc links break | FIXED. The README distinguishes the linear digit model and hand-wired XOR, names this checkpoint's training reproduction, and links this record. The HTML explanation uses repository links that work when only dist is deployed. |

This publication correction changes copy and tests, not weights or network
logic. The Pages workflow builds saved weights without retraining. The updated
suite has 15 Rust tests and 97 Python tests, with 16 abstract-base skips.
Prior-art claims, browser feature floors, Safari, and the video pipeline were
not independently rechecked at this checkpoint.
