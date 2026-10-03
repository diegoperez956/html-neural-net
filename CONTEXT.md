# htmlnet language

htmlnet demonstrates fixed neural-network inference and the binary arithmetic
behind it. These terms distinguish the demonstrations and their claims.

## Language

**Gate mode**:
The demonstration that constructs arithmetic from named bit operations and
connects the results into neurons.
_Avoid_: Required workaround for CSS multiplication

**Native mode**:
The comparison that expresses the same XOR and matrix calculations as direct
arithmetic rather than bit circuits.

**XOR demonstration**:
The hand-configured network with two inputs, two hidden neurons, and one
output. It is separate from the digit classifier.
_Avoid_: Trained digit network

**Digit classifier**:
The learned model that chooses one of ten digits from processed drawing
features. It has no learned hidden layer.
_Avoid_: Shipped digit MLP, handwriting accuracy guarantee

**Glyph classifier**:
The smaller learned model that distinguishes a top bar from a left bar or
other input in a 3×3 drawing.
_Avoid_: The only learned model

**Paint canvas**:
The drawing input, before stroke dilation and block reduction.

**Network sees preview**:
The view of the processed drawing features the digit classifier receives.
It is not a reduced screenshot of the visible paint blobs.

**Input shim**:
The optional helper that turns a drag gesture into changes to drawing cells.
It does not evaluate either network.

**Score margin**:
The difference between the highest and second-highest class scores.
_Avoid_: Confidence percentage, probability of correctness

**Glyph fidelity**:
The number of correct predictions on one of the small canonical glyph sets.
Those sets are development acceptance checks, not untouched generalization tests.

**Drawn-style validation proxy**:
Held-out MNIST training examples cropped 18% tighter, clipping digit edges,
with varied source binarization thresholds. The proxy does not thicken source
strokes. It has no demonstrated advantage for predicting drawing accuracy.
No human drawings were evaluated.
