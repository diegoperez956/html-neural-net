# Next-chat study handoff

## What Diego requested

Diego wants to understand how this project's HTML and CSS evaluate a neural
network, then test that understanding in a new chat. The study material is a
silent, animation-led Manim video with short on-screen explanations.
There is no voice or music. The earlier YouTube goal informs the explanations,
but this video is for personal understanding rather than a finished presentation.

Diego recognized that the drawing consists of individual inputs and initially
called them textboxes. The correct term is checkboxes. Do not assume that
watching the video establishes mastery. No knowledge test has happened yet.

## Material to read before testing

- `video/README.md` has playback, chapter, and reproduction instructions.
- `video/output/htmlnet-study.mp4` is the completed 50:05 study video.
- `video/output/follow-along.md` contains its timestamped on-screen explanations.
- `docs/HOW_IT_WORKS.md` explains the math with worked examples.
- `docs/COMPUTATION_MODEL.md` defines the implementation boundaries.
- `docs/IMPLEMENTATION_AUDIT.md` separates verified behavior from historical claims.
- `gen/src/circuit.rs` and `gen/src/main.rs` contain the actual circuit builders.
- `tests/test_runtime.py` and `tests/test_video_math.py` contain checked examples.

The rendered MP4 and caches are ignored by Git but exist in this workspace.
Do not rerender or retrain merely to start the knowledge test.

## How to conduct the next chat

Ask one question at a time and wait for the answer. Do not begin with a recap
that gives the answers away. Use free-response explanations and small numeric
examples rather than multiple choice. Adapt depth to the actual answers.

When an answer is wrong, identify the specific misconception. Give one hint
before supplying the solution unless Diego asks for the answer. After an
explanation, use a different example to check transfer rather than repeat the
same numbers. Keep a distinction between recognizing a phrase and calculating
or tracing an unfamiliar case.

Do not repeat the old false claim that CSS cannot multiply numeric variables.
Do not confuse the hidden-layer XOR demonstration with the linear digit model.
Do not treat CSS-calculated intermediate bits as additional editable checkboxes.

Record only demonstrated understanding. If recording progress, distinguish
correct unaided answers, correct answers after a hint, and material not tested.
Ask before turning this repository into a larger teaching-workspace system.

## Suggested question progression

These are prompts for the teacher, not a test to dump into the conversation.
Use the source files as the answer key and vary the numeric examples.

1. What changes in the browser when a drawing checkbox is clicked with all
   page JavaScript disabled? Separate HTML state, CSS declarations, and the
   browser's evaluation work.
2. Read one `:has()` input mapping and a `var()` dependency. Identify which
   value is input state and which is calculated.
3. Explain why `min(a,b)` behaves like AND for bits. Explain what integer
   registration alone does not guarantee.
4. Calculate a half adder's sum and carry. Explain why two active input bits
   can give a zero sum bit without producing the number zero.
5. Trace one full-adder column and a short multi-column carry chain.
6. Construct a small unsigned product from AND partial products and shifts.
7. Decode a four-bit signed word and sign-extend it. Distinguish display order
   from the compiler's least-significant-bit-first arrays.
8. Calculate a dot product of binary vectors. Do not interpret the vector as
   one packed binary integer.
9. Work a matrix row, then a weighted sum with a bias and threshold.
10. Explain why one linear threshold cannot implement XOR. Trace the two
    hidden neurons and output for an input not used in the previous question.
11. Explain why native CSS arithmetic can replace the gate construction for
    these small calculations, and what gate mode adds educationally.
12. Follow one input cell through neighbor dilation and a 2×2 OR block.
13. State the dimensions of the digit model's matrix, input, bias, and output.
14. Explain a positive and a negative weight's contribution. Explain how a
    magnitude-three weight participates in two popcount planes.
15. Choose an argmax with ties, calculate the top-two margin, and explain why
    the margin is not a confidence percentage.
16. Explain how a four-bit winning index controls seven segments and why
    decimal views do not feed back into inference.
17. Distinguish training, quantization, code generation, and browser inference.
18. Explain a blank canvas's nonzero prediction, an off-center drawing failure,
    and what the audit does not establish about dataset-level accuracy.

## Verified facts to keep straight

The drawing has 196 checkbox inputs. The full page also has controls for the
smaller demonstrations. Derived calculations live in CSS custom properties.
The complete artifact has 6,834 registered signals, not 6,834 logic gates.

The XOR demonstration has two hidden threshold neurons and hand-picked weights.
The digit classifier has ten linear scores over 49 processed binary features.
It has no learned hidden layer. The larger digit MLP is an unshipped experiment.

`dist/no-js.html` contains no script and supports native click input.
`dist/index.html` retains the optional drag-input script. Both contain the same
calculation declarations. The script handles pointer geometry, not inference.

The saved thin-seven example has scores
`[-12, 1, 1, 5, 3, 4, -27, 24, -9, 5]`. Seven wins with margin 19.
The canonical thin one is misclassified as four with a zero margin.
A blank input picks class one because its bias is highest.
These are checked examples for the saved weights, not universal accuracy claims.

Current browser behavior was tested in Chromium and Firefox. Historical code
was inspected, not every old artifact executed. MNIST training and test-set
accuracy were not rerun during this revision. Acceptance-conditioned glyph
figures must not be described as untouched held-out estimates.

## Prompt Diego can paste into a new chat

> Read docs/STUDY_HANDOFF.md. Test my understanding of htmlnet one question at
> a time. Don't recap the answers first. Start with how a checkbox becomes a
> CSS calculation, then adapt based on my answers.
