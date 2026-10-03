# The page generator

This Rust crate writes `dist/index.html`. It does not execute in the browser.
The page's network calculations run in CSS. An optional script handles
pointer input.

```bash
make build
# Or choose an output path without changing dist/index.html:
cargo run --release --manifest-path gen/Cargo.toml -- /tmp/htmlnet.html
# No script in the artifact, with native click input:
cargo run --release --manifest-path gen/Cargo.toml -- /tmp/htmlnet-no-js.html --no-js
```

`make build` writes both `dist/index.html` and `dist/no-js.html`.
The `--no-js` version omits the input script and updates its input instructions.
It retains byte-identical calculation declarations.

The generator reads `scripts/weights.json` and `scripts/weights_mnist.json`
relative to `CARGO_MANIFEST_DIR`. It does not train or download models.
Run `make train` only when you intend to replace the saved weights.

## Files

- `src/circuit.rs` contains `Circuit`, `Net`, and the HTML renderer.
- `src/main.rs` instantiates the demonstrations and drawing classifier.
  It also emits the optional drawing script.
- `src/base_css.txt` contains the layout and visual styles.
- `assets/fonts/*.b64` supplies embedded font data at generation time.

Edit these sources and rebuild. Do not patch generated `dist/index.html` alone.
`dist/how-it-works.html` is a separate hand-maintained explanation.

## Determinism

`Circuit::signals` is an ordered vector. A hash set checks names but never
sets emission order. Popcount's hash map is accessed by explicit column index.
Registrations are sorted before rendering. No random input affects generation.

`StaticChecks.test_deterministic_rebuild` generates a temporary page and checks
its SHA-256 against `dist/index.html`. Generator unit tests check malformed
model dimensions. Browser tests check arithmetic and rendered output.

```bash
make test
```

## Historical port

The crate began as a byte-identical port of Python's `scripts/circuit.py` and
`scripts/generate.py`. D-007 records that comparison. D-008 removed the Python
compiler after validation. Rust is now authoritative; there is no remaining
requirement to update a second generator.

The old `scripts/benchmark*.py` programs depended on the retired compiler and
were removed on 2026-10-03. Their saved measurements from 2026-08-30 remain in
`benchmarks/*.csv` as dated historical evidence. They cannot be regenerated
with the current toolchain; see [the measurement record](../benchmarks/README.md).

The generator's stdout reports UTF-8 bytes with `html.len()`, not Unicode
character count. `wc -c dist/index.html` measures the same quantity.
