# Computation model

This document defines what this project counts as computation. It is deliberately narrower than “anything that can be encoded in CSS.”

## Public claim

> Neural-network inference implemented with HTML and CSS, with zero JavaScript at runtime.

A stronger claim is allowed only for the gate-derived path, and only in this wording:

> A tiny neural network composed at build time from named bit-domain logic gates and adder/multiplier circuits, all hosted on native CSS arithmetic (`min()`/`max()`/`calc()`) as a custom-property netlist.

"HTML performs matrix multiplication," "HTML is a CPU," "logic primitives implemented in HTML/CSS," and unqualified novelty claims are not accurate.

## Runtime boundary

`dist/index.html` is the runtime artifact. Opening it through `file://` must require no JavaScript, WebAssembly, server, network request, extension, experimental browser flag, or runtime code generation.

Python build and test programs may generate repetitive markup/CSS, elaborate a circuit, calculate references, and drive a browser. None of those programs ships as runtime machinery.

## Responsibilities

### HTML

HTML supplies:

- form controls whose browser-managed checkedness is interactive state;
- labels and semantic grouping for accessible input;
- DOM nodes that CSS selectors match and style;
- static structure for exposing wires, gates, arithmetic stages, and network stages.

HTML does not itself evaluate arithmetic. A checkbox’s current checkedness is browser form state; it is not an output bit that CSS writes back into the DOM.

### CSS and the CSS engine

CSS supplies declarations describing a dependency graph. The browser’s selector and style engines perform:

- matching `:checked` and `:has(...)` selectors;
- assigning primary-input custom properties to `0` or `1`;
- resolving custom-property dependencies;
- evaluating `calc()`, `min()`, and `max()`;
- converting integer custom properties to visible digits through CSS counters;
- deriving color, opacity, and geometry from computed values;
- invalidating and recomputing affected style when checkedness changes.

Those are substantial native browser operations. We do not claim to derive parsing, comparison, integer evaluation, selector matching, or style invalidation from lower primitives.

## State and signals

Persistent user-controlled state exists only in checked form controls. Primary bit `x` is represented by a checkbox and mapped to an integer custom property:

```css
.runtime { --x: 0; }
body:has(#x:checked) .runtime { --x: 1; }
```

A derived **bit signal** is a named, registered-integer custom property constrained by construction and by test to `0` or `1`. A derived **word signal** is a named integer custom property holding a fixed-width two's-complement value (width per stage, see Numeric formats). Both are computed style, not mutable HTML state. Derived signals can feed later declarations through `var(--signal)`; they cannot become `:checked`, and selectors cannot in general inspect their computed numeric value.

Visual LEDs and digits are views of signals, not additional state.

## Gate-derived primitive basis

For operands known to be bits, gate mode uses this CSS-math basis:

\[
\begin{aligned}
\operatorname{NOT}(a) &= 1-a \\
\operatorname{AND}(a,b) &= \min(a,b) \\
\operatorname{OR}(a,b) &= \max(a,b) \\
\operatorname{XOR}(a,b) &= \max(a,b)-\min(a,b)
\end{aligned}
\]

These are **basis primitives**: four named bit-domain identities over two native browser operations (integer subtraction, `min()`/`max()` comparison-arithmetic). They are not reduced to a smaller functionally complete set (e.g. NAND), and they are not gates we built from transistors. This is the bottom of the derivation, and the wording of every public claim must keep it that way.

A **logic gate** in this project is a named bit signal declaration generated from one of those equations, with bit-valued inputs and an exhaustively verified truth table.

Gate mode does not use native CSS multiplication or a whole-network weighted-sum expression. Its additions and multiplications are circuit structures made from named gates:

- half adder: one XOR and one AND;
- full adder: two XORs, two ANDs, and one OR;
- N-bit addition: full adders connected by named carry signals;
- unsigned multiplication: AND-generated partial products added by adder stages;
- dot product: multiplier outputs connected to an adder;
- matrix-vector multiplication: multiple dot products sharing vector inputs;
- fixed-weight signed neuron: bit-gated two’s-complement constants, ripple additions, bias addition, then a sign/threshold bit;
- layer/network: neuron outputs used as later neuron input signals.

“Connected” means a later custom-property declaration references earlier named custom properties. It does not mean CSS mutates intermediate checkboxes.

## Native-CSS-math baseline

A second mode intentionally uses direct CSS arithmetic for products and weighted sums. It answers a different question: how compactly can modern CSS evaluate the same fixed network?

Native mode is not evidence that arithmetic was derived from gates. Its presence is labeled as a baseline, and both modes are tested against the same reference outputs.

## Composition versus enumeration

Handwritten or generated runtime selectors enumerate only each primary input’s unchecked/checked mapping. They do not enumerate complete adder, multiplier, matrix, or XOR input truth tables.

The build generator creates a circuit netlist, gives every gate output a stable name, and emits declarations in dependency order. Larger operations invoke smaller circuit-building functions. Constants and repeated presentation markup are generated. Build-time tests may exhaustively enumerate inputs, but expected outputs from those tests are not copied into runtime lookup selectors.

If any implementation later uses full-state enumeration, it must be labeled a lookup table and cannot support the stronger compositional claim.

## Multiplication definition

Gate-mode multiplication means binary long multiplication:

1. each partial-product bit is an AND of one multiplicand bit and one multiplier bit;
2. shifted partial-product rows are added with the same half/full-adder construction used by integer addition;
3. visible product bits are outputs of that circuit.

A selector listing every operand pair, or direct `calc(a * b)`, is not gate-mode multiplication.

## Typing and scope invariants

Every signal (bit or word) is registered via `@property { syntax: "<integer>"; inherits: true }` and declared on one common `.runtime` ancestor element; UI elements read signals as descendants. This gives engine-enforced integer typing, one canonical scope, and computed values readable by tests through `getComputedStyle`.

Support floor for this mechanism: Chromium 85+, Firefox 128+, Safari 16.4+. No experimental flags. The floor is a deliberate trade: unregistered custom properties would widen support but leave typing unenforced and computed-value probing engine-dependent.

## Numeric formats

Stage widths (two's complement where signed):

- bit signal: width 1;
- N-bit unsigned adder: width N+1 (carry included);
- N×N unsigned multiplier: width 2N;
- dot product of two 2-bit unsigned operands: products width 2, sum width 5 (max 18);
- 2×2 matrix × 1-bit vector: each entry is a gate-masked constant weight; row sums fit 4 bits;
- XOR MLP neuron: weight ±2 needs 3-bit signed product words (−4..7); neuron preactivation is sum of two 3-bit products plus bias (−1): width 4 signed (−8..7); threshold = sign bit;
- trained 3×3 classifier: nine weights in {−1,0,1,2}, bias −2; preactivation is the sum of nine bit products plus bias: width 5 signed (−16..15); threshold = sign bit;
- trained 7×7 drawn-digit classifier (M11), per-class score: weights in
  [−3,3] decomposed into two popcount bit-planes per sign; each plane's
  popcount is width 5-6 unsigned (ceil(log2(n+1)) for up to 49 lit
  inputs); `pos`/`neg` (plane-count sum, one plane pre-shifted) and the
  final signed score are all width 7 (build-time-asserted per class from
  its actual weights/bias, not a hardcoded ceiling; max observed
  `|score|` = 58);
- M11 argmax tournament: 8-bit signed comparator diff per round
  (sign-extended 7-bit scores, one extra bit for the subtraction), 4-bit
  index;
- overflow is impossible for these maxima by construction, and exhaustive tests assert it.

## Display path policy

Gate-mode primary displays are per-bit LEDs reading individual bit signals. Where a composite decimal number is shown, it is computed by a native-calc expression such as `calc(b0 + 2*b1 + 4*b2)` — native multiplication by powers of two. That expression is a **view** for human readability, outside the gate circuit, and is labeled as such in the demo. It never feeds back into gate logic.

## Runtime sequence

When a user toggles a control:

1. browser changes form-control checkedness;
2. selector matching changes a primary bit declaration;
3. style engine recomputes dependent custom properties;
4. gate, arithmetic, neuron, and network computed values change;
5. counters and visual encodings repaint.

There is no script callback and no persisted sequence of clocked operations. This numbered description explains dependencies; browser may optimize or evaluate them in another internal order.

## Difference from a CPU

This is a static combinational dataflow graph hosted in computed style. It has no instruction set, program counter, clock, general memory, writable intermediate registers, branch instruction, or claim of efficient universality. The browser is the real general-purpose computer and CSS style evaluation is the execution substrate.

The visual carry chain describes circuit dependency, not measured gate timing. Browser style recalculation may evaluate or cache the graph as a whole.

## Difference from normal neural inference

The network is tiny, fixed, low-precision, and inference-only. Weights are embedded at build time. There is no training, batching, tensor runtime, floating-point accelerator, automatic differentiation, or production-relevant performance. Gate mode uses fixed-width two’s-complement arithmetic and threshold activations; overflow behavior is explicit and tested.

The mathematical graph can still be a genuine multilayer threshold network: each neuron computes an embedded weighted sum plus bias and activation, hidden outputs feed a later neuron, and all input combinations match an independent reference model.

## Honest acceptance tests

The stronger gate-derived claim is accepted only if all are true:

1. final artifact passes static zero-script/offline checks;
2. primary bits come from browser form state;
3. each visible intermediate reads the same named signal consumed downstream;
4. gate truth tables pass exhaustively;
5. adders and multiplier are generated by structural circuit composition, not result lookup;
6. matrix rows are dot-product circuit instances;
7. network output depends on hidden-neuron signals through a later neuron circuit;
8. browser-rendered intermediates and outputs match an independent model for every supported input;
9. documentation states browser primitives and build-time generation without euphemism.

If browser tests disprove any item, public wording falls back to the narrower claim at the top of this file.
