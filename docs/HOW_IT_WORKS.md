# How a neural network runs in CSS

This guide explains the shipped code. Read sections 1–5 for the story.
The later sections connect that story to the circuit builders and the math.
For the audit of earlier claims, read [the implementation audit](IMPLEMENTATION_AUDIT.md).

## 1. The browser already knows how to calculate

CSS can do arithmetic. It can also make one value depend on another and
recalculate when a checkbox changes. Those abilities are enough to evaluate
a small, fixed neural network.

HTML provides the checkboxes. CSS describes the calculations. The browser's
style engine executes them. Rust generates the repeated declarations before
you open the page.

The drawing script is optional. It converts a pointer path into checked cells.
It does coordinate math, but it never calculates a neuron or chooses a digit.
Without that script, you click cells individually and get the same prediction.

The useful claim is **neural-network inference in HTML and CSS**.
It is not arithmetic performed by HTML tags alone.

## 2. A neuron is a weighted sum followed by a decision

The neuron in section 9 of the demo calculates:

```text
z = 2x1 - 2x0 - 1
y = 1 when z >= 0, otherwise 0
```

Each input is either 0 or 1. A weight tells us how much an active input changes
the sum. The bias is the fixed offset, here -1. The activation turns that sum
into the output bit.

With `x1 = 1` and `x0 = 0`:

```text
z = 2(1) - 2(0) - 1 = 1
y = 1
```

With `x1 = 0` and `x0 = 1`, the sum is -3 and the output is 0.
Nothing in that calculation requires a machine-learning library.

In general notation, the same calculation is:

```text
z = w1*x1 + w2*x2 + ... + wn*xn + b
y = step(z)
```

Here `step(z)` is 1 at zero and above. Other networks use different
activations, often continuous functions. This project uses threshold neurons
because their outputs are bits.

## 3. Hidden layers mean one calculation feeds another

A single threshold neuron cannot separate the two positive XOR cases from the
two negative cases with one straight line. Two hidden neurons can each detect
one of the positive cases.

The shipped XOR network has two inputs, two hidden neurons, and one output:

```text
h1  = step( 2x1 - 2x0 - 1)    detects x1=1, x0=0
h2  = step(-2x1 + 2x0 - 1)    detects x1=0, x0=1
out = step( 2h1 + 2h2 - 1)   accepts either hidden detection
```

For `x1 = 1, x0 = 0`, the hidden sums are 1 and -3. Their activations are
1 and 0. The output sum is `2(1) + 2(0) - 1 = 1`, so XOR returns 1.

The full truth table is small enough to inspect:

| x1 | x0 | h1 | h2 | out |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 |
| 0 | 1 | 0 | 1 | 1 |
| 1 | 0 | 1 | 0 | 1 |
| 1 | 1 | 0 | 0 | 0 |

These are connected calculations, not a pre-recorded animation. The output
circuit references `--xor_h1_out` and `--xor_h2_out` through `var()`.
The tests check the hidden values as well as the final answer.

The XOR weights are hand-picked. This network is not trained by the page.

## 4. The digit recognizer is a separate, simpler network

Do not describe the drawing demo as the XOR network scaled up with hidden
layers. The shipped digit model has no learned hidden layer. It is a linear
classifier after a fixed image-processing step.

Its actual path is:

```text
196 checkbox bits on a 14×14 canvas
    → thicken strokes with neighbor ORs
    → combine each 2×2 block with OR
    → 49 input bits
    → 10 weighted sums, one per digit
    → choose the largest score
    → light the winning digit's segments
```

For digit class `k`, the score is:

```text
score[k] = bias[k] + sum(weight[k][i] * pixel[i], i=0..48)
```

The matrix form is `s = Wx + b`. `W` has 10 rows and 49 columns. `x` has 49
entries, and the result `s` has 10 entries. Each row asks the same question
with different weights.

The answer is `argmax(s)`, the index of the largest score. Ties go to the
lowest digit. These scores are not probabilities. A negative score can win
if every other score is lower.

The margin is the highest score minus the second-highest score. It measures
separation between two scores, not the probability that the answer is right.

### A real example from the shipped weights

These numbers use the weights shipped at `2ae837c`. Retraining may change them.

The thin seven in `tests/test_runtime.py`, under `THIN_CANVASES["seven"]`,
contains 18 checked cells. Dilation turns them into 56 active cells.
Downsampling produces these 20 active features:

```text
.#####.
.#####.
....##.
....##.
....##.
....##.
....##.
```

The scores, in digit order 0 through 9, are:

```text
[-12, 1, 1, 5, 3, 4, -27, 24, -9, 5]
```

Digit 7 wins with 24. The next-highest score is 5, so the margin is 19.
The segment decoder lights the top, upper-right, and lower-right segments.

On a blank canvas, every pixel term is zero. The bias for class 1 is 19,
which is the largest bias, so the page displays 1. That is the model's bias
output, not evidence that it recognized an invisible digit.

## 5. Why this is feasible, and why it stays small

A trained network's forward pass is a fixed set of arithmetic operations.
This project writes that set as CSS declarations. The browser already resolves
such dependencies when it calculates styles.

The page does not search for a model, update weights, or generate a circuit
while you draw. Its 6,834 registered signals already exist in the HTML file.
Changing a checkbox changes their inputs.

CSS can also multiply two runtime numbers directly:

```css
--product: calc(var(--a) * var(--b));
```

Earlier docs said this was impossible. That was wrong for numeric custom
properties. Tests now compare native multiplication with the gate multiplier
for all sixteen pairs of two-bit numbers, in Chromium and Firefox.

The gate implementation is a teaching choice. It shows how weighted sums can
be built out of binary arithmetic. The native comparison calculates XOR and
the two matrix rows in eight declarations, excluding displays. The gate-built
XOR alone uses 177 gates, plus twelve preactivation aliases and a decimal view.

The cost is the point of the comparison. About 1.62 MB of generated HTML and
CSS implements a very small model. This is not a practical way to run an LLM.

## 6. How checkbox state becomes a calculation

The generator emits this pattern on the `body.rt` element:

```css
@property --a {
	syntax: "<integer>";
	inherits: true;
	initial-value: 0;
}

.rt { --a: 0; }
body.rt:has(#a:checked) { --a: 1; }
```

`:has()` makes the body match when its checkbox is checked. The more specific
rule changes `--a` to 1. Other declarations reference `var(--a)`.

Every circuit signal has an integer registration. That makes computed values
readable as integers and allows descendants to inherit them. Registration
does not enforce the bit range. The gate equations preserve 0 and 1 when
their inputs are bits.

All dependent declarations live on the same body element. A value calculated
on the body does not recalculate with different input variables on a child.
That is why the common scope matters.

Declaration order is not a clock. Dependencies determine the result.
CSS custom-property cycles do not create recurrent neurons in this design.

## 7. How gates become arithmetic

For bit inputs, the generator uses these identities:

```text
NOT(a)   = 1 - a
AND(a,b) = min(a,b)
OR(a,b)  = max(a,b)
XOR(a,b) = max(a,b) - min(a,b)
```

For example, `min(1, 0)` is 0, exactly the result of AND.
The browser supplies subtraction, `min()`, and `max()`. We did not build those
operations from transistors.

A half adder has a sum bit and a carry bit:

```text
sum   = XOR(a,b)
carry = AND(a,b)
value = sum + 2*carry
```

When both inputs are 1, the sum bit is 0 and the carry bit is 1.
That is binary `10`, which means 2.

A full adder also accepts the previous carry:

```text
t        = XOR(a,b)
sum      = XOR(t,carry_in)
carry_out = OR(AND(a,b), AND(t,carry_in))
```

Connecting full adders produces a ripple adder. An unsigned multiplier
creates AND partial products and adds shifted rows, just like binary long
multiplication. For `3 × 2`, the rows are `0000` and `0110`, and the sum is
`0110`, or 6.

Circuit arrays store the least significant bit first. The visible LED rows
show the most significant bit first, matching their place-value captions.

### Negative numbers and the activation

Four-bit two's complement gives the leftmost bit a weight of -8:

```text
1101 = -8 + 4 + 0 + 1 = -3
```

Negation flips every bit and adds 1. The neuron builder masks the magnitude
of a weight with the input bit, negates negative products, and adds the terms
and bias with ripple adders.

The most significant bit is 1 for a negative sum. The activation is therefore
**NOT the sign bit**, so nonnegative sums produce 1. This depends on choosing
enough bits to avoid a wrapped result with the wrong sign.

## 8. How the larger scores avoid hundreds of tiny multipliers

Every digit weight is an integer between -3 and 3. A magnitude of 3 is
`1 + 2`, so each weight needs at most two binary places.

`Net::weighted_score` groups inputs by the sign and binary places of their
weights. `popcount` means count the active bits in a group.

```text
positive = count(positive weights 1 or 3)
         + 2 * count(positive weights 2 or 3)

negative = count(negative weights -1 or -3)
         + 2 * count(negative weights -2 or -3)

score = positive - negative + bias
```

Each count includes only active input pixels. A pixel with weight 3 enters
both positive groups, contributing 1 plus 2 when active. A pixel with weight
-2 enters only the second negative group.

The generator builds the counts with adders. Multiplication by 2 is a bit
shift, represented by adding a zero bit at the low end. Subtraction is
NOT-and-add with a carry-in of 1.

Scores use seven-bit signed words. The generator checks each class's possible
score bounds. Comparisons use an extra bit, so subtracting two valid scores
does not overflow. A sequence of comparisons keeps the winner and runner-up.

This section is useful for answering questions after reading. You do not
need to explain every carry wire on screen.

## 9. Training happens before the browser opens

`train/src/glyph.rs` trains the small 3×3 bar classifier on nine examples.
`train/src/mnist.rs` trains the digit classifier on MNIST, a dataset of labeled
handwritten digits. Rust writes the learned numbers into `scripts/weights*.json`.
The generator reads those numbers and builds the fixed CSS circuit.

The digit trainer uses 50,000 MNIST training images. It reserves the other
10,000 training images for validation. The official 10,000-image test set is
separate.

On a mistake, the multiclass perceptron adds the input to the correct class's
weights and subtracts it from the mistaken class's weights. It also raises
the correct bias and lowers the mistaken bias. It repeats this for eight epochs.
Then it scales, rounds, and clips the weights to the small integer range.

The training pipeline crops and centers MNIST images before resampling.
The browser does not crop or center a drawing. It only dilates and downsamples
the cells you checked. Small or off-center drawings can therefore fail even
when they look clear to you.

The shipped JSON reports 75.42% MNIST test accuracy. It gets 8 of 10 canonical
upscaled glyphs and 6 of 10 thin-stroke glyphs. Those tiny glyph sets helped
filter earlier configurations, so they are acceptance-conditioned results,
not untouched estimates of accuracy on new drawings. See
[training methodology](../train/README.md) for the details.

## 10. Where to look in the code

- [`gen/src/circuit.rs`](../gen/src/circuit.rs) contains `half_adder`,
  `full_adder`, `ripple_add`, and `unsigned_mult`.
- The same file contains `Net::neuron`, `Net::weighted_score`, `argmax`,
  `digit_minterms`, `sevenseg`, and `render`.
- [`gen/src/main.rs`](../gen/src/main.rs) chooses the example circuits,
  builds dilation and downsampling, and maps signals to visible elements.
- [`gen/src/base_css.txt`](../gen/src/base_css.txt) styles the drawing area
  and readouts. It does not contain the learned model.
- [`train/src/mnist.rs`](../train/src/mnist.rs) owns preprocessing,
  perceptron training, and quantization.
- [`tests/test_runtime.py`](../tests/test_runtime.py) compares the actual
  browser signals and rendered outputs with independent arithmetic.

The numbered UI sections are examples built with shared circuit functions.
They are not one long signal path. In particular, XOR does not feed the digit
classifier, and neither classifier trains while you use the page.
