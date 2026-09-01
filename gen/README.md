# gen — the htmlnet build-time generator (Rust)

Build-time only. This crate never touches the shipped artifact at runtime —
it just writes `dist/index.html`, the sole build path for the demo (the
original Python generator, `scripts/generate.py`, was deleted after this
port was validated byte-identical to it — see D-008 in `docs/DECISIONS.md`).

```
cargo run --release --manifest-path gen/Cargo.toml -- dist/index.html
# or: make build
```

Weights are read from `../scripts/weights.json` and
`../scripts/weights_mnist.json`, resolved relative to the crate
(`CARGO_MANIFEST_DIR`), not the process's cwd. Those files are produced by
`train/` (`make train`); this crate only *reads* them (trainers were
explicitly out of scope for this port — see AGENT_TASK.md).

Parity: byte-parity with the now-deleted Python generator was this port's
acceptance contract, verified via `make parity` before Python was removed
(D-007/D-008 in `docs/DECISIONS.md`). There is nothing left to compare
against — this crate's output is authoritative.

## Layout

- `src/circuit.rs` — 1:1 port of `scripts/circuit.py`: gate primitives,
  `Circuit` (signal table + adders/multiplier/popcount/argmax/minterms/
  seven-seg), `Net` (neuron/weighted_score), `render()`.
- `src/main.rs` — 1:1 port of `scripts/generate.py`'s `main()`: builds the
  same circuit in the same order, assembles the same CSS/body strings.
- `src/base_css.txt` — `BASE_CSS`, extracted byte-for-byte from
  `generate.py`'s triple-quoted string via `include_str!` rather than
  retyped, to rule out transcription drift in a 5KB CSS blob.

## Construct mapping

| Python | Rust |
|---|---|
| `dict[str, str]` (`Circuit.signals`, insertion-ordered) | `Vec<(String, String)>` + a `HashSet<String>` "seen" guard for the `assert name not in self.signals` dup check. Iteration is always over the `Vec`, so insertion order is preserved into the output — no `HashMap` ever sits between a signal and the rendered string. |
| `_op()` operand normalizer | `op()` (crate-visible, used by both `circuit` and `Net`) |
| `NOT/AND/OR/XOR` free functions | `not_e/and_e/or_e/xor_e` |
| `Circuit.gate(kind, a, b=None, name=None)` (kind as `str`, optional args, optional name defaulting to `f"{kind}_{len(signals)}"`) | Split into `gate` (unary) and `gate2` (binary, explicit `Option<&str>` name — the code path with `name=None` is dead in `generate.py` since every call site names its signal, so the auto-name fallback is ported but never exercised) |
| `half_adder` / `full_adder` / `ripple_add` | direct method ports, same signal-name scheme |
| `unsigned_mult` (partial products via `list` slicing/concat) | `Vec<Vec<String>>` rows, same `"0"`-padding by index |
| `popcount` (dict of column -> wires, `while w <= max_w` fold) | `HashMap<usize, Vec<String>>` for the column table — safe here because iteration is always by explicit `w` index (`0, 1, 2, ...`), never `.keys()`/`.values()` order, so no Python-dict-order assumption leaks through a Rust `HashMap`. |
| `argmax` (tournament fold with streaming runner-up + margin, 3-tuple return) | ported to match the **current** `circuit.py` exactly (this superseded an earlier 2-tuple version an earlier port attempt was based on — re-derived from the checked-out Python, including the `mux`/`mux_if` gate-naming and evaluation order: `run_up` fully computed before `new_run`, before the incumbent score, before the incumbent index, each round). Python's arbitrary-precision two's-complement bit extraction (`(v >> i) & 1` on a negative int) is replicated with `i64` arithmetic shift, which is exactly two's-complement for values this small (≤ 8 bits). |
| `digit_minterms` / `SEVENSEG_MAP` / `sevenseg` | direct ports; `SEVENSEG_MAP` as a `const` array of `(&str, &[u8])` instead of a `dict[str, set[int]]` — order doesn't matter here (sets in Python have no defined iteration order either; the code always does `sorted(self.SEVENSEG_MAP[seg])`), so a plain sorted-in-source array is the identical construct. |
| `Net.const_bits` | masks with `value & ((1i64<<width)-1)`, same two's-complement masking Python does on arbitrary-precision ints |
| `Net.neuron` | direct port. `f"{name}_add{len(c.signals)}"` / `_bias{len(c.signals)}` (a *dynamic* name depending on signal count at call time) ported as `self.c.signals.len()` read at the same point in the method |
| `Net.weighted_score` | direct port, including the build-time `assert`s (weight magnitude ≤ 3, plane/score width sufficiency) as Rust `assert!` — these are compiler-time invariants, not something a caller works around, so panicking is the right failure mode in both languages |
| `render()` (`sorted(c.signals)` for `@property` blocks, insertion order for `.rt` decls) | `names.sort_unstable()` (byte/codepoint order, identical to Python's default string `sorted()` for this ASCII identifier set) for the properties block; `c.signals` iteration order for the decls block |
| `generate.py`'s big body f-string | `format!` with named captures (Rust 2021 supports `{var}` referring to an in-scope binding, the closest analogue to an f-string) built from precomputed `String`s for every loop/join Python does inline (`"".join(...)`, `range()`, `i // 7`/`i % 7`, etc.) |
| `f"{cls_weights}"` (Python `list.__repr__`) | `py_int_list()` — `"[" + values.join(", ") + "]"` |
| `f"{mnist_test_acc:.0%}"` | `pct0()` — `value * 100.0` formatted with `{:.0}` + `"%"`, same order of operations CPython's `%`-format type does internally |

## What could not be ported 1:1

Nothing semantic. Two cosmetic, non-artifact differences were found and
closed:

- **stdout byte count.** Python's `print(f"... {len(html)} bytes")` counts
  `str` codepoints; Rust's `String::len()` counts UTF-8 bytes (the page has
  non-ASCII characters: em dashes, arrows, `×`, `∈`, …). Fixed by printing
  `html.chars().count()` instead, to match Python's number exactly. This is
  only a diagnostic line, never part of the artifact.
- Everything else — every signal name, gate expression, CSS declaration, and
  the full HTML body — matched sha256-identical to the Python generator's
  output (verified via `make parity`, now retired) on the real weights JSON.

## Determinism

No `HashMap` iteration order ever reaches an output string. The one
`HashMap` in the port (`popcount`'s column table) is always walked by
explicit increasing index, never by key/value iteration. Signal declaration
order is carried entirely by `Circuit.signals: Vec<(String, String)>`,
appended in the same call order `circuit.py`/`generate.py` emit them in.
