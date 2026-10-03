# Computation model

This document defines the implementation's claims and boundaries.
For a less technical explanation, read [how it works](HOW_IT_WORKS.md).

## Public claim

> Neural-network inference implemented with HTML and CSS. JavaScript is
> optional for drawing input and is not required for inference.

The stronger gate-mode claim is:

> A fixed network composed at build time from named bit signals, adders, and
> threshold neurons. The browser evaluates the generated CSS calculations.

"HTML alone does arithmetic", "no JavaScript in the page", and "CSS cannot
multiply two runtime numbers" are not accurate.

## Runtime and build boundaries

`dist/index.html` opens through `file://` without a server or network access.
Its embedded fonts use data URLs. It contains one optional pointer-input script.
Deleting the script, or disabling page JavaScript, leaves native checkbox input,
network inference, and the output displays operational.

`dist/no-js.html` is the fully script-free export. `make build` generates both
versions. The `--no-js` generator option omits the script and changes the input
instructions; its calculation declarations are identical to the default page.
Native-click inference in this saved export is tested in both engines.

The default page's script interpolates pointer positions and sets checkbox checkedness.
It does not calculate image preprocessing, neuron sums, activations, scores,
argmax, margins, or segment states.

Rust in `train/` learns weights before runtime. Rust in `gen/` composes the
circuit and emits HTML and CSS. Python drives tests and calculates independent
references. None of those programs executes as browser inference code.

## What HTML and CSS each supply

HTML supplies form controls, labels, semantic groups, and the element tree.
Checkbox checkedness is browser-managed state. CSS does not write computed
results back into those checkboxes.

The browser's style engine matches selectors, resolves `var()` dependencies,
evaluates arithmetic, and updates displayed values when inputs change.
The project relies on those native browser operations. It does not construct
a browser's arithmetic or selector engine from logic gates.

## Signal representation

Every signal is a registered integer custom property on `body.rt`:

```css
@property --a {
	syntax: "<integer>";
	inherits: true;
	initial-value: 0;
}
.rt { --a: 0; }
body.rt:has(#a:checked) { --a: 1; }
```

The default gives an unchecked input value 0. Selector specificity gives the
checked mapping priority over that default.

A bit signal takes values 0 or 1 by construction. Integer registration alone
does not enforce that range. A word is an array of bit signals, least
significant bit first in the compiler. Signed words use two's complement.
Decimal view signals contain decoded integers.

All dependent declarations share the body scope. Descendant displays inherit
computed values. A child changing an input variable does not recalculate a
word already computed on the parent.

The dependency graph is acyclic. Declaration order is not a clock, and CSS
custom-property cycles do not provide recurrent network state in this design.
These limits describe this implementation, not every possible use of CSS.

## Gate basis

For operands that are bits:

| Gate | CSS arithmetic identity |
|---|---|
| NOT a | `1 - a` |
| a AND b | `min(a, b)` |
| a OR b | `max(a, b)` |
| a XOR b | `max(a, b) - min(a, b)` |

A generated gate is a named signal containing one such expression.
These identities rely on native subtraction, minimum, and maximum. They are
not transistor-level implementations or a reduction to NAND alone.

Gate mode builds larger operations through named dependencies:

- A half adder uses one XOR and one AND.
- A full adder uses two XORs, two ANDs, and one OR.
- A ripple adder connects carry signals between full-adder stages.
- An unsigned multiplier ANDs operand bits into shifted partial products,
  then adds those rows with ripple adders.
- A fixed-weight neuron masks weight magnitudes with input bits, negates
  negative products, adds the products and bias, and inverts the sign bit.
- The output XOR neuron consumes the two hidden-neuron output signals.
- Digit scores use popcount bit planes, then subtraction and bias addition.

The compiler emits repetitive structure. It does not enumerate the complete
input space into result selectors. The unmerged historical UI experiment
that did use enumeration is covered in [the audit](IMPLEMENTATION_AUDIT.md).

## Separate examples, shared builders

The numbered sections are not one serial network. Arithmetic examples use
separate inputs and instances of shared builders. Matrix rows mask constant
weights and add them. The XOR network and digit classifier are separate.

The digit path is 196 canvas bits, neighbor-OR dilation, 2×2 block-OR
reduction, 49 features, ten linear scores, argmax, and segment decoding.
It has no learned hidden layer.

## Native arithmetic mode

Native mode computes the XOR network and two matrix rows with eight direct
arithmetic declarations, excluding display views. It is a labeled comparison,
not evidence of arithmetic built from gates.

`calc(var(--a) * var(--b))` works when the variables resolve to numbers.
Both engines test it against the structural two-bit multiplier.
Gate construction is an educational constraint, not a CSS requirement.

For integer `z`, `max(0, min(1, z + 1))` implements the chosen activation,
which returns 1 exactly when `z >= 0`. This equality is not a general
continuous step-function identity for fractional inputs.

## Numeric formats

| Stage | Representation and range |
|---|---|
| Primary and gate bits | 0 or 1 |
| Two-bit unsigned adder | Three output bits, sum 0–6 |
| Two-bit unsigned multiplier | Four output bits, product 0–9 |
| Four-bit unsigned adder | Five output bits, sum 0–30 |
| Two-component binary dot product | Sum 0–2. The current generator overallocates six accumulator bits and shows five LEDs. |
| Matrix rows | Four unsigned bits, each row 0–3 |
| XOR neuron products | Three signed bits, representable range -4–3 |
| XOR preactivations | Four signed bits, representable range -8–7 |
| 3×3 glyph preactivation | Five signed bits, representable range -16–15 |
| Digit class scores | Seven signed bits, representable range -64–63 |
| Digit comparator differences | Eight signed bits after sign extension |
| Winning digit index | Four unsigned bits |
| Winner-to-runner-up margin | Eight bits interpreted as unsigned |

`weighted_score` checks positive and negative plane totals and final score
bounds against the selected width. The shipped class bounds are within
-49–46. Small arithmetic examples have exhaustive browser tests.
The drawing classifier has structured and random cases, not exhaustive
coverage of its 196 input bits.

## Display policy

Per-bit LEDs and seven-segment elements read gate signals directly.
LED word rows display the most significant bit on the left.

Decimal numbers use expressions such as `b0 + 2*b1 + 4*b2` in registered
`*_dec` properties. Signed views give the sign bit a negative coefficient.
CSS counters render those integers. These are display-only native arithmetic
calculations and do not feed back into gate logic.

The rounded paint blobs are visual feedback. They are not sampled as images.
The "network sees" preview reads the actual post-downsample feature bits.

## Verification contract

The stronger claim depends on several checks, not one slogan:

1. The artifact contains only the reviewed input script, no event-handler
   attributes or external runtime resources.
2. Real native clicks produce matching predictions with page JavaScript
   disabled and with the script deleted.
3. Primary inputs come from checkbox state.
4. Gate truth tables and the small arithmetic input spaces match independent
   arithmetic exhaustively.
5. The output XOR circuit depends on both hidden-neuron signals.
6. Digit scores, preprocessing, argmax, margin, and decoder bits match an
   independent reference on the covered drawings.
7. Rendered bit order, counters, preview colors, and segment colors match
   their signals.
8. Rebuilding from the same sources and weights produces identical bytes.

The script hash catches changes to reviewed code. Static scans alone do not
prove that arbitrary code cannot hide computation. Source review and runtime
checks are also required.
