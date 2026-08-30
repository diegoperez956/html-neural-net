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
