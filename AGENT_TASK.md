# Task: port the circuit compiler + page generator from Python to Rust

You are an autonomous agent working in a git worktree of `htmlnet`.
Hard constraints (violating any = task failed):

1. The shipped artifact `dist/index.html` is pure HTML+CSS: no JS, no WASM,
   no external resources, works from file://. This never changes.
2. Rust is BUILD-TIME ONLY. Nothing Rust touches the browser.
3. Do not modify Python behavior. Python stays until integration removes it.

## Read first

- README.md, docs/ARCHITECTURE.md, docs/COMPUTATION_MODEL.md
- scripts/circuit.py  (Circuit/Net compiler: gates, adders, popcount, argmax,
  minterms, seven-seg, neurons, weighted_score)
- scripts/generate.py (page generator: BASE_CSS + body assembly)
- tests/test_runtime.py (what the artifact must satisfy)
- Skill refs (follow their discipline): /home/diego/.pi/agent/vendor/mattpocock-skills/skills/engineering/tdd/SKILL.md
  and .../implement/SKILL.md

## Deliverable

A Rust crate `gen/` (cargo, std-only if humanly possible; no heavy deps)
containing a faithful port of circuit.py + generate.py.

Success criterion, in order:
1. `cargo run --release -- dist/index.html` writes a file byte-identical
   (sha256) to `python3 scripts/generate.py dist/index.html` output from the
   same weights JSONs. Byte-identity is the spec — the existing
   test_deterministic_rebuild pattern extends to cross-language parity.
   Add `make build-rust` target and a parity script/check.
2. Full existing test suite passes against the Rust-built artifact
   (`python3 -m unittest discover -s tests` after building with Rust).
3. Port notes in gen/README.md: every Python construct mapped to Rust,
   anything that could not be ported 1:1 and why.

## Method

- TDD-ish: after each compiler stage ported (gates → adders → multiplier →
  popcount → argmax → minterms/sevenseg → neuron/weighted_score → page
  assembly), run parity diff vs Python on the real weights, not toy inputs.
- Do NOT port trainers (train.py/train_mnist.py). Read weights JSON files.
- Determinism: no HashMap iteration order anywhere near output string
  building; Python dict = insertion order, preserve ordering semantics.
- Commit incrementally with clear conventional messages.

When done: `git commit` everything, leave branch agent/rust-compiler clean,
and write final summary to WORKTREE_SUMMARY.md.
