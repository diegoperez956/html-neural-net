# Architecture reference

For the explanation and worked examples, read [how it works](HOW_IT_WORKS.md).
The [computation model](COMPUTATION_MODEL.md) defines the claim boundaries.

## Files and responsibilities

| File | Responsibility |
|---|---|
| `train/src/glyph.rs` | Train the 3×3 bar perceptron |
| `train/src/mnist.rs` | Preprocess MNIST, train and quantize the linear digit model |
| `scripts/weights.json` | Saved glyph weights and bias |
| `scripts/weights_mnist.json` | Saved linear digit weights, biases, pipeline fields, and metrics |
| `gen/src/circuit.rs` | Compose named gates, arithmetic circuits, neurons, and decoders |
| `gen/src/main.rs` | Instantiate circuits, load weights, generate input and display mappings |
| `gen/src/base_css.txt` | Layout, controls, paint blobs, and display geometry |
| `dist/index.html` | Offline runtime with optional drag-input script |
| `dist/no-js.html` | Offline runtime with no script and native click input |
| `dist/how-it-works.html` | Hand-maintained explanation, separate from the generator |
| `tests/test_runtime.py` | Browser checks and independent arithmetic references |

`make build` compiles the generator and writes both variants from saved weights.
The `--no-js` option excludes the input script without changing the circuit.
`make train` explicitly overwrites the saved models. The experimental digit
MLP trainer was removed on 2026-10-03; its unshipped design and negative result
remain in [the historical MLP notes](DESIGN_MLP.md).

## Compiler structures

`Circuit` stores ordered `(name, expression)` pairs and rejects duplicate
names. A named operand becomes a CSS `var(--name)` reference. Literal bits and
existing expression fragments pass through operand normalization.

`gate2` and `gate` emit the bit identities. `half_adder` and `full_adder` return
sum and carry signal names. `ripple_add` accepts two equal-width operand arrays
in least-significant-bit-first order. It returns the chosen width of sum bits.
Callers pad operands when they need to retain an extra carry bit.

`unsigned_mult` creates AND partial-product rows, pads each to the result
width, and folds the rows through ripple adders.

`Net::neuron` masks the magnitude of each weight with its input bit. Negative
weights use bitwise NOT plus increment. Products are sign-extended to the
sum width, then added with each bias. NOT of the result's sign bit is the
nonnegative threshold activation.

The glyph schema fixes nine weights. The digit schema fixes ten classes and
ten biases. `weighted_score` checks each row against its input count, restricts
weights to [-3, 3], and validates plane and score ranges at build time.

## Rendering and scope

`render` emits a single HTML document containing:

1. Embedded font CSS, layout CSS, and input and display mappings.
2. Sorted integer `@property` registrations for every signal.
3. The generated `.rt { --signal: expression; }` declarations.
4. The static controls and readouts inside `body.rt`.
5. The optional pointer-input script supplied by the page generator.

Every signal uses `syntax: "<integer>"`, `inherits: true`, and `initial-value: 0`.
The body is the common computation scope. Input rules such as
`body.rt:has(#x1:checked)` override default zeros through specificity.
Descendants inherit the computed values for display.

The declarations form a dependency graph. Emission order keeps the generated
source readable, but the browser is not executing a sequential instruction list.
No output changes checkbox state or creates a feedback loop.

## Independent demonstration paths

The arithmetic sections instantiate separate circuits with shared builders.
They are not successive layers of the digit model.

The XOR path is:

```text
x1, x0
    → xor_h1 and xor_h2 threshold neurons
    → xor_out threshold neuron
    → output LED and decimal view
```

The hidden equations are `step(2*x1 - 2*x0 - 1)` and
`step(-2*x1 + 2*x0 - 1)`. The output is `step(2*h1 + 2*h2 - 1)`.
Products use three-bit signed words and sums use four-bit signed words.
The production builder emits 177 gates for these three neurons.

The 3×3 glyph path has nine inputs, one trained threshold neuron, and a
five-bit signed preactivation. Its weights are independent of the XOR demo.

Mode B computes XOR and the fixed matrix rows with eight native arithmetic
declarations. Numeric `var()` operands can multiply directly in CSS.
Gate mode is an explicit construction, not a browser compatibility requirement.

## Drawing preprocessing

The drawing area has 196 primary bits named `mc0` through `mc195`.
Each checked cell draws an oversized round blob. The blob is visual feedback,
not an image that the network reads.

For each cell, the generator ORs its own bit with its four orthogonal
neighbors. Edge cells have fewer neighbors. Intermediate `dlo` signals form
the OR trees, and `dl0` through `dl195` hold the dilated result.

Each 2×2 block of dilated bits feeds another OR tree. Its output is one of
`mn0` through `mn48`. These are the classifier's actual inputs and the values
displayed by the "network sees" preview.

The generator requires `canvas == 14`, `dilate_iters == 1`, and
`block_threshold == 1` in the model JSON. It refuses to emit this circuit for
a different preprocessing specification.

The trainer simulates these dilation and downsample stages. Its earlier
MNIST crop, centering, and area-resampling stages do not run in the browser.
See [training](../train/README.md) for the split and selection caveats.

## Digit scores

`Net::weighted_score` groups active inputs by weight sign and magnitude bit.
For each sign, one group contains magnitudes 1 and 3, and another contains
magnitudes 2 and 3.

`Circuit::popcount` reduces equal-weight wires with full and half adders.
A zero bit prepended to the second group's count doubles that count.
Ripple addition combines the two groups for each sign.
The final score is `positive - negative + bias`.

Each class uses a seven-bit signed score. Build-time bounds come from the
actual weights, not from observed drawings. Current scores lie within -49–46
for every possible 49-bit feature vector. Registered aliases
`mnist_score{k}_b{i}` expose the words to tests and displays.

## Argmax and display decoding

`Circuit::argmax` folds over the ten class scores and maintains a winner and
runner-up. Comparisons sign-extend to eight bits before subtraction.
The sign bit selects a mux. Strict greater-than keeps the earlier class on
a tie, so the lowest index wins.

The final winner and runner-up produce an eight-bit margin.
The margin is an integer score difference, not a calibrated confidence value.

`digit_minterms` decodes all sixteen possible values of the four-bit index.
Only digits 0 through 9 are reachable from this classifier.
`sevenseg` ORs the relevant digit minterms for each of seven segments.
The visible segments and digit strip read these gate signals directly.

Decimal views convert bit words with weighted `calc()` sums.
Signed views give the highest bit a negative coefficient.
CSS counters render the values. These `*_dec` signals never feed the gate
inference calculations.

## Input updates and verification

A click changes checkbox state. The matching input rule changes a primary bit,
the browser resolves dependent values, and the displays update.
Dragging uses a script to interpolate pointer positions and toggle cells.
The script does not evaluate the network.

The test suite checks the generated artifact in Chromium and Firefox.
It includes script-disabled and script-deleted runs, rendered bit order,
seven-segment colors, and actual mouse input. Tests inspect the same gate
outputs that subsequent calculations consume, sometimes through named aliases.
Static checks run once without a browser. The generator rebuild comparison
checks that saved weights and current source reproduce identical bytes.
