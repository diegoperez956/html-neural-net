# Record the htmlnet explanation

Use this as a recording checklist, not a word-for-word script. It targets a
technical YouTube audience without assuming a machine-learning course.
Read [how it works](HOW_IT_WORKS.md) before recording.

## Prepare the demo

1. Open `dist/index.html` directly in Chromium or Firefox.
2. Keep the drawing area and the "network sees" preview visible.
3. Draw a large, centered seven. Clear it and rehearse the same stroke.
4. Open **under the hood** and rehearse the XOR checkboxes in section 1.
5. Run `make test` before recording. Do not retrain just to prepare footage.

`make build` regenerates HTML from the checked-in weights. It does not train.
`make train` changes the weight files and can download MNIST, so treat it as a
separate experiment.

## Start with the result

Show a digit appearing as you draw. Then show the 7×7 preview.
Explain that the classifier receives those bits, not a screenshot of the
orange stroke.

State the boundary early. The browser computes inference in CSS. A small
JavaScript script makes dragging convenient. Clicking still works without it.
Do not make "zero JavaScript" the reveal if the script is still on the page.

## Show the proof before the detailed math

1. Disable page JavaScript in browser developer tools.
2. Reload the page.
3. Click individual cells to draw a shape.
4. Show the prediction and clear button still working.
5. Re-enable JavaScript and reload before returning to drag drawing.

The automated equivalent runs in both browser engines:

```bash
PYTHONPATH=tests python3 -m unittest \
  test_runtime.NoScriptTests_chromium \
  test_runtime.NoScriptTests_firefox -v
```

The test driver reads computed styles. It does not calculate an answer and
write that answer into the page.

## Explain one neuron with numbers

Use section 9. Turn `x1` on and `x0` off in section 1.
The displayed sum is 1 and the activation lights up.

Put this on screen:

```text
2(1) - 2(0) - 1 = 1
1 >= 0, so the neuron outputs 1
```

Swap the inputs. The sum becomes -3 and the activation turns off.
Introduce weights and bias here. Save two's complement for an optional cutaway.

## Explain layers with XOR

Use section 10. Show all four input combinations.
Point to the hidden LEDs before the output LED.
One hidden neuron detects each of the two mismatched input cases.
The output accepts either detection.

The important point is that the hidden results feed the output calculation.
"Layer" means more connected calculations, not another image pasted on screen.

Mention that these weights are hand-picked. They demonstrate a multilayer
network, not a training session.

## Connect the math to CSS

Show only a few declarations at first:

```css
body.rt:has(#a:checked) { --a: 1; }
.rt { --g_and: min(var(--a), var(--b)); }
```

Explain that checkboxes supply bits and later declarations read earlier values.
Then show the half-adder idea, `sum = XOR` and `carry = AND`.
Use `1 + 1 = 10` in binary as the example.

Open section 11 for the native comparison. CSS can calculate the same network
with far fewer declarations. Do not repeat the old claim that numeric
`var() × var()` is forbidden.

If time is tight, skip the full multiplier and popcount construction.
Link the written guide for viewers who want those details.

## Return to the digit recognizer

Describe ten weighted sums, one for each possible digit. The largest score
wins. The recognizer has no learned hidden layer.

For an exact reproducible example, use the thin seven in
`tests/test_runtime.py`. Its class-7 score is 24 and its margin is 19 with the
checked-in weights. Freehand strokes may not produce the same bits or scores.

Show a failed drawing too. The model gets the canonical thin one wrong,
predicting 4 with a zero margin. Explain the loss of detail and the mismatch
between training images and arbitrary drawings.

The current MNIST figure is 75.42%. It is not a promise about live drawings.
The empty canvas chooses 1 because of the biases. That is useful footage for
showing what the equation does when every input is zero.

## End on what was demonstrated

The browser can evaluate a fixed network because CSS already supports
arithmetic and value dependencies. This project builds a much larger binary
circuit to expose the operations behind that math.

Do not claim a new way to train AI, a browser LLM, or the first CSS neural
network. The prior-art survey and implementation audit belong in the video
links.

## Keep these distinctions in your notes

- HTML provides state and structure. CSS computes the network.
- Rust trains models and generates the artifact before runtime.
- The optional JavaScript computes pointer geometry, not predictions.
- The XOR demo has hidden neurons. The digit model does not.
- A margin is a score difference, not a confidence percentage.
- Gates are an educational choice. Numeric CSS multiplication already works.
- A passing test suite checks covered behavior. It does not prove accuracy
  on every possible drawing.
