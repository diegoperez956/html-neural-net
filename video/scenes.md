# CSS neural networks, a visual study

## Overview

A Manim lesson for understanding this repository. The viewer knows that the
drawing area consists of switches but wants to see how their state becomes
arithmetic.

This file documents the full 28-chapter design below. Two builds render from
it: the primary **14-chapter narrated cut** (`htmlnet-study-15.mp4`, about 15
minutes, `am_michael` Kokoro voice reading each on-screen caption) keeps
chapters 01, 02, 04, 05, 07, 14, 15, 16, 18, 20, 21, 22, 24, 26 — inputs,
css-state, gates, half-adder, binary, neuron, xor-proof, xor-network, canvas,
downsample, ten-scores, score-trace, argmax, training — renumbered 01-14 in
that order. Every other chapter below (dependencies, full-adder, ripple,
multiply, signed, fixed-weight, dot-product, matrix, native-css, dilation,
popcount, segments, limits, complete-path) is dropped from that cut. The
original **28-chapter silent cut** (`htmlnet-study.mp4`, about 50 minutes, no
audio) still renders all of them via `render.py --silent`.

Target roughly 35–45 minutes for the full silent lesson; the narrated cut
targets 14–15.5 minutes. The final duration comes from the rendered chapters,
not a padded end frame. The text explains the picture on screen and, in the
narrated cut, is also the spoken narration. Detailed code and a follow-along
file remain available outside the video.

The visual method uses progressive construction, algebraic substitution,
spatial comparison, and animated examples. It does not copy existing footage.
The colors and type come from this project's warm dark palette.

## Narrative

Start with a checked cell and the CSS value it changes. Build gates, binary
arithmetic, and a threshold neuron. Show why XOR needs hidden neurons, then
follow a real drawing through the separate linear digit classifier.
End by distinguishing browser inference, build-time training, and audit evidence.

## Scene specifications

Every chapter has a title, short on-screen explanations, source references,
and moving mathematical objects. Approximate durations are design estimates.

### 01. Inputs are not the calculations. About 90 seconds.
Show a drawn seven, reveal its grid, and isolate a single checkbox.
Move its state into a numeric signal. Add a calculation only after this mapping
is visible. Distinguish the 196 drawing inputs from thousands of derived values.

### 02. A checkbox becomes a CSS number. About 90 seconds.
Animate checkedness beside the actual `:has()` mapping and integer registration.
Show both 0 and 1, then explain the shared body scope and inherited readouts.

### 03. A graph of dependent values. About 90 seconds.
Start with two input nodes, add AND, then add a dependent NOT.
Recompute the highlighted values after several input changes. Keep a notice
that animation order is explanatory, not a browser clock or measured timing.

### 04. Four gates from CSS arithmetic. About 110 seconds.
Use truth tables and number comparisons to build NOT, AND, OR, and XOR.
Show the corresponding generated CSS beside changing numeric inputs.

### 05. One plus one needs a carry. About 90 seconds.
Build a half adder from XOR and AND. Animate all four inputs and gather
`sum + 2*carry` into the decimal result. Show the actual `ha` declarations.

### 06. Adding the previous carry. About 100 seconds.
Expand a full adder one gate at a time. Trace all eight combinations through
its two XORs, two ANDs, and final OR. Show actual named dependencies.

### 07. Binary place values. About 85 seconds.
Animate bit flips while weights 1, 2, 4, and 8 stay fixed. Count through a
four-bit word, distinguish MSB-first display from LSB-first compiler arrays.

### 08. Ripple addition. About 110 seconds.
Trace 7+1, 5+3, 10+5, and 15+1 by columns. Move each carry into the next
column and keep the final carry. Show `ripple_add`'s real loop.

### 09. Multiplication from partial products. About 100 seconds.
Construct 3×2 and 3×3 from AND products. Shift partial-product rows, align
place values, and add. Contrast binary vectors with packed scalar words.

### 10. Negative numbers are bit patterns. About 110 seconds.
Change the most significant coefficient from +8 to -8. Decode 1101 as -3,
then animate NOT plus one and sign extension. Show a signed number line.

### 11. A fixed weight times one bit. About 100 seconds.
Mask +2 and -2 by 0 and 1. Animate positive magnitude, structural negation,
and extension to the accumulator width. Link these steps to `Net::neuron`.

### 12. A dot product. About 90 seconds.
Pair two binary vector components, multiply corresponding entries, and add.
Work each example spatially. The demo's components are bits, not two-bit integers.

### 13. A matrix is several dot products. About 100 seconds.
Keep the vector fixed while highlighting each row of [[2,1],[1,2]].
Move each row's sum into its output slot, then change the input vector.

### 14. A neuron adds a decision. About 110 seconds.
Animate weights, inputs, products, bias, and threshold separately.
Work all four inputs to z=2*x1-2*x0-1. Connect the result to NOT of the sign bit.

### 15. Why one line cannot solve XOR. About 120 seconds.
Plot the four labeled corners. Try candidate separating lines, then build
the contradiction from the four required inequalities. Add the proof gradually.

### 16. Hidden neurons solve the two cases. About 125 seconds.
Build the two hidden neurons before the output neuron. Show their equations,
weighted edges, and all four complete forward passes. Hidden results are values,
not more checkboxes, and the weights here are hand-picked.

### 17. Native CSS can do the same arithmetic. About 95 seconds.
Substitute inputs in the real native XOR declarations. Demonstrate numeric
variable multiplication. Compare constructions without implying gates are required.

### 18. The drawing is 196 bits. About 90 seconds.
Draw the exact thin-seven fixture cell by cell. Reveal row-major indices and
distinguish the visible round ink blobs from the binary input cells.

### 19. Dilation grows a stroke. About 105 seconds.
Expand a center cell into its orthogonal neighbors, repeat at a corner,
then apply the operation to the actual seven. Animate the OR neighborhood.

### 20. Four cells become one feature. About 125 seconds.
Highlight each 2×2 block and move its OR result into the 7×7 preview.
Show empty and partly filled blocks. The final preview must match the code.

### 21. Forty-nine inputs, ten scores. About 105 seconds.
Flatten the 7×7 grid, reveal ten weight rows, and attach one score per digit.
Show the dimensions of W*x+b and the actual ten scores for the saved seven.

### 22. Follow every term of a real score. About 135 seconds.
For digit 7, highlight all 49 input positions and their saved weights.
Animate each product into a running total initialized with the actual bias.
Finish at the independently calculated score, not a hard-coded visual result.

### 23. Small weights become popcount groups. About 120 seconds.
Split active weighted inputs into positive and negative low/high bit planes.
Show why magnitude 3 participates twice, how counting uses adders, and how
shifting doubles the high plane. Reconstruct the same class score.

### 24. Choose the winner and measure the gap. About 115 seconds.
Animate the tournament over all ten scores. Keep the incumbent on ties,
track the runner-up score, and subtract for the margin. Use a real zero-margin
case to show that a margin is not a probability.

### 25. An index lights seven segments. About 100 seconds.
Decode the winning four-bit index into a minterm, then light the correct
segment ORs. Animate all digit patterns as decoder examples, not invented
classifier predictions. Separate bit-driven segments from decimal views.

### 26. Learning happens before the page opens. About 120 seconds.
Animate a labeled toy perceptron update, then quantization. Separate the Rust
training/build path from the browser path. Show the actual data split and
explain that the experimental digit MLP does not ship.

### 27. What the audit does and does not prove. About 115 seconds.
Show the blank canvas's bias output and a real misclassified thin one.
Distinguish tested arithmetic, script-disabled operation, historical inspection,
and dataset-level accuracy not rerun. Show the pure no-JavaScript export.

### 28. Reassemble the complete path. About 120 seconds.
Redraw the drawing path a stage at a time and replay the seven through it.
Pair each transition with its equation or real source location. Finish with
links to the code, follow-along notes, and the new-chat study handoff.

## Visual conventions

- Warm dark background `#282828`, ink `#ebdbb2`, inactive bits `#3c3836`.
- Blue `#83a598` for inputs, orange `#fe8019` for active drawing cells.
- Green `#b8bb26` for positive contributions, red `#fb4934` for negative ones.
- Yellow `#fabd2f` for the currently inspected value or operation.
- Noto Sans for prose and JetBrains Mono for code and bit words.
- Stable locations for captions and source labels. No decorative camera motion.
- Use Pango text and explicit mathematical layouts, so rendering needs no TeX install.

## Grounding and verification

Read `gen/src/circuit.rs`, `gen/src/main.rs`, `train/src/mnist.rs`, and the
checked-in weight files. Load the actual canvas fixtures from the test source.
Verify the independent animation model against known arithmetic and browser
signals. Treat illustrative gate pulses as teaching graphics, never clock timing.
The Manim video is Python-rendered teaching material, not the runtime artifact.

Inspect rendered keyframes, verify text fits, and use ffprobe to check duration,
resolution, chapter markers, and the absence of audio. Keep a resumable renderer
and individual chapter files. Do not claim a full render from source alone.
