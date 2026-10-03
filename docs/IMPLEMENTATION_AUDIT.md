# Implementation and claim audit

Scope: the working tree based on `2ae837c`, plus the local Git history available
at review time. The repository had 60 reachable commits across all refs.
This audit distinguishes current behavior, historical shortcuts, and claims
that the evidence does not support. It cannot establish an author's intent.

## Does the current network secretly run in JavaScript?

No such computation was found. The current digit scores, XOR hidden outputs,
argmax, and segment decoder are CSS custom-property calculations.

Both Chromium 149 and Firefox 151 passed these checks against the actual page:

- Disable page JavaScript, click cells, compare the rendered prediction with
  arithmetic over the checked-in weights, then clear the drawing.
- Delete the script tag from a temporary copy and repeat the same test.
- Compare the circuit's scores, intermediate bits, winner, and margin with
  independent Python calculations.
- Follow the output dependencies back to the XOR hidden neurons and the
  drawing inputs.

The optional script interpolates pointer positions and sets checkbox states.
It performs input-coordinate arithmetic. It does not read the weight files,
calculate scores, or write predictions.

The original brief allowed HTML and CSS, so using CSS is not itself a departure
from that brief. A strict "HTML alone" claim would still be wrong. CSS is doing
the calculations. A strict "no JavaScript in the artifact" claim is also wrong
today.

## Was there ever a shortcut instead of a composed network?

Yes, in the unmerged `experiment/ui` branch at `a57ea17`.

That branch's `scripts/logic.py` computes truth tables in Python.
`render_signal_rules` emits a CSS selector for each complete assignment of the
four source bits. Even downstream arithmetic outputs are selected directly
from those inputs. The generated page has rows such as:

```css
#netbus:has(#a1:not(:checked)):has(#a0:not(:checked)):has(#b1:not(:checked)):has(#b0:checked) {
	--xor0: 1;
}
```

Its weight variables are also placeholders. The page itself says changing
them does not recompute the network. Its source describes style queries that
light displays as a "propagation mechanism", but the arithmetic outputs have
already been enumerated from the source inputs.

That is a lookup-based demonstration, not the stronger gate-composition claim.
It still uses CSS at runtime, not hidden JavaScript. Treat it as an experimental
shortcut, not as evidence that the current main implementation is fake.

`a57ea17` is not an ancestor of current `main`. The production generator in
`gen/src/circuit.rs` builds adders and multipliers from named gates instead.
Current tests reject multi-input mappings and check downstream dependencies.

Reproduce the historical check without checking out or overwriting files:

```bash
git show a57ea17:scripts/logic.py
git show a57ea17:dist/index.html
git merge-base --is-ancestor a57ea17 HEAD
```

The last command returns 1 because the branch was not merged.

## The zero-JavaScript promise changed

The original `.agents/PROJECT_BRIEF.md` prohibited JavaScript at runtime.
Commit `4ecfbda`, with a Claude Fable co-author trailer, added a drag-to-draw
script and explicitly described the change as relaxing the zero-JS claim.
Later commit `96ef08d` updated some documentation to reflect the exception.
Other docs remained stale.

This changed the original constraint. The Git record shows the change was
stated, not hidden. The record alone does not establish whether the user had
authorized it in the conversation.

The revised docs say exactly what runs where. Page JavaScript is optional for
input convenience. It is not required for inference.

## Several mathematical and evaluation claims were wrong

### Numeric CSS multiplication was falsely called impossible

`README.md`, architecture docs, and the generated page said CSS forbids
`var() × var()`. Numeric custom properties can multiply in `calc()`.
Both engines passed all sixteen two-bit operand pairs against ordinary
multiplication and the gate-built multiplier.

The circuits are real, but they are not required by that alleged restriction.

### The reported 82.46% accuracy was selected against test data

D-007 in `docs/DECISIONS.md` records a scan of about twenty shuffle seeds
against MNIST test accuracy. The selected 82.46% was therefore not an untouched
estimate of generalization. D-009 replaced that procedure with validation
selection.

The current artifact reports 75.42%, not 82.46%. This audit did not rerun
training or independently reproduce that dataset-level accuracy. The figure
comes from the checked-in weights metadata and the recorded training runs.

### The glyph results are acceptance-conditioned

D-011 compared multiple downsampling thresholds and inspected their glyph
results before fixing the architecture at OR downsampling. Only the chosen
configuration met both glyph acceptance floors.

Calling the final configuration "fixed architecture" does not make those
previous evaluations disappear. The 8/10 and 6/10 figures are conditioned on
that development process. The current trainer also uses glyph accuracy to
decide whether to attempt augmentation, even though validation accuracy gates
acceptance of the augmented model.

The docs now state these caveats. Ten examples cannot establish arbitrary
handwriting accuracy.

### The larger digit MLP never shipped

Commit `88d567b` wrote weights for a 49→16→10 network while the page generator
still expected linear weights. Its own commit message reports stale output,
a broken rebuild, and eight failing browser tests. Commit `22797bc` restored
the linear digit model.

`train/src/mlp.rs` remains an experiment. The browser's digit recognizer has
no learned hidden layer. The separate 2→2→1 XOR network does have hidden neurons.

### Other explanations did not match the source

The 123-gate XOR count described an earlier experiment. The production XOR
builder emits 177 gates, twelve preactivation aliases, and one decimal view.
The complete page has 6,834 signals, not 6,834 gates.

The dot-product example uses two binary components per vector, not two-bit
scalar entries. Neuron activation is NOT the sign bit. Digit scores add the
bias. The smaller glyph classifier is not the only model with learned weights.

## Bugs fixed in this revision

The numeric LED rows were least-significant-bit first, while the captions
were most-significant-bit first. For `1 + 2`, the decimal result was 3 but the
LEDs read `110` against `4·2·1`. A rendered regression test failed in both
engines before the fix and passed after reversing the generated LED order.

The generator accepted wrong model dimensions. A short glyph weight list
could silently drop inputs through `zip`, and extra digit classes could be
ignored. Fixed-size deserialization now rejects invalid glyph and class counts.
Rust regression tests failed before the change and pass afterward.

The test loader exposed loop variables as test classes, so the final Firefox
class ran twice. Static checks also ran once per browser despite needing none.
The loader now removes those aliases and runs static checks once. Browser
launch failures now fail instead of making the runtime checks look green
through skips.

`make build` and `make test` used to retrain the model. They now use the
checked-in weights. `make train` remains the explicit, potentially expensive
operation that changes model files.

## Script-free export and study-video follow-up

`make build` now also writes `dist/no-js.html`. Its generator option `--no-js`
omits the script and updates the input instructions. Static tests compare its
calculation declarations with the default page, and both browsers test native
click input against the saved script-free artifact. The drag-enabled default
is retained rather than silently discarding the existing input changes.

The silent Manim study video is separate teaching material, rendered in Python.
It is not presented as the browser implementation. Its independent math model
has tests for carry chains, signed words, XOR, image preprocessing, the saved
seven, the thin-one failure, and weighted-score bit planes. Video verification
checks the MP4, chapter markers, absence of audio, layout bounds, and caption OCR.
See `video/README.md` for the files and commands.

## New verification

`make test` runs Rust tests and the Playwright suite. New checks cover:

- The displayed binary bit order and seven-segment colors.
- Actual mouse clicks and a captured pointer drag, beyond synthetic events.
- Inference with page JavaScript disabled and with the script removed.
- A pinned hash of the reviewed input script, in addition to token checks.
- Native numeric multiplication and the XOR's hidden-output dependencies.
- Rejection of malformed model dimensions.

The pin detects changes to the script. It does not prove an arbitrary program
contains no inference. That conclusion also depends on source review and the
scriptless behavior checks.

Small arithmetic circuits have exhaustive input tests. The 196-cell drawing
space has 2^196 possible inputs and is not exhaustively tested.

## Historical inventory and remaining limits

Run the history inventory with:

```bash
python3 scripts/audit_history.py > /tmp/htmlnet-audit.json
```

At the reviewed HEAD, it finds sixteen commits touching `dist/index.html`
across all refs, representing fourteen distinct artifacts. Nine have no script.
Five have one script, with two distinct historical drawing-script versions.
Source inspection found input handling in both versions, not model inference.
The working-tree script has newer pointer handling and is reported separately.
The inventory also reports multi-`:has()` rules to expose lookup-style artifacts.

This is a static inventory, not execution of every old version. Raw downloaded
prior-art pages and unrelated experiment artifacts are not audited as shipped
runtime code. No deleted branches, private conversations, or external deployments
were available for review.

The old `scripts/benchmark*.py` files still import the deleted Python circuit
compiler. Running `scripts/benchmark.py` reproduces `ModuleNotFoundError`.
They are historical research tools, not a working current benchmark command.
Their CSV timings include browser automation overhead and do not establish
current drawing latency. Porting those generators is deferred; see
[limits](LIMITS.md).

The revised work does not retrain or change either shipped weight file. It
preserves the existing drawing-input changes and does not commit or push them.
