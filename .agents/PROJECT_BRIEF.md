# htmlnet agent brief (historical, 2026-08-30)

The initial constraints below are a historical record, not current build or
runtime instructions. D-011/D-012 supersede the no-script constraint: the
default page has one optional drawing-input shim; `dist/no-js.html` is
script-free. Rust is the sole generator/trainer build path; Python runs tests
and the separate study-video pipeline.

Original goal: single offline `dist/index.html`; HTML + CSS only at runtime; no JS/WASM/network/runtime generation. Build-time Python and browser tests allowed.

Honesty is mandatory. Distinguish HTML state, CSS selector/style/math work, generated enumeration, and structural composition. Do not call visualization signal propagation when computed styles cannot become selector state. Prefer measured prototypes over prose. Keep assigned files isolated. Commit findings/code to your branch.

Target hierarchy: checked form state -> bits -> gates -> adders -> 2-bit unsigned multiplication -> dot product -> 2x2 matrix-vector -> signed 4-bit threshold neuron -> 2-2-1 XOR MLP. Compare gate-derived custom-property netlist against direct CSS arithmetic. Modern `:has()` and registered custom properties allowed if documented. Runtime must remain useful offline under `file://`.
