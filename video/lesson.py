"""Silent, source-grounded Manim study of htmlnet. Run through video/render.py."""

import json
from itertools import combinations
from pathlib import Path
import textwrap

import numpy as np
from manim import (
    Arrow,
    Axes,
    Circumscribe,
    Create,
    Dot,
    DOWN,
    FadeIn,
    FadeOut,
    GrowArrow,
    Indicate,
    LaggedStart,
    LEFT,
    Line,
    NumberLine,
    ReplacementTransform,
    RIGHT,
    Scene,
    ShowPassingFlash,
    SurroundingRectangle,
    Transform,
    TransformFromCopy,
    UP,
    VGroup,
    Write,
    config,
)
from PIL import Image

from video import model, voice
from video.visuals import (
    BG,
    BLUE,
    EDGE,
    GREEN,
    INK,
    MUTED,
    ORANGE,
    PANEL,
    PURPLE,
    RED,
    YELLOW,
    Bit,
    PixelGrid,
    SevenSegment,
    Signal,
    bit_word,
    code_panel,
    equation,
    matrix,
    score_chart,
    text,
    wire,
)

ALL_CHAPTERS = [
    ("inputs", "The inputs are not the calculations"),
    ("css-state", "A checkbox becomes a CSS number"),
    ("dependencies", "Values form a dependency graph"),
    ("gates", "Four gates from arithmetic"),
    ("half-adder", "One plus one needs a carry"),
    ("full-adder", "Add the previous carry"),
    ("binary", "Binary place values"),
    ("ripple", "Follow a carry across a word"),
    ("multiply", "Multiplication from partial products"),
    ("signed", "Negative numbers are bit patterns"),
    ("fixed-weight", "A fixed weight times one bit"),
    ("dot-product", "A dot product pairs and adds"),
    ("matrix", "A matrix is several dot products"),
    ("neuron", "A neuron adds a decision"),
    ("xor-proof", "Why one line cannot solve XOR"),
    ("xor-network", "Hidden neurons detect the two cases"),
    ("native-css", "Native CSS can calculate this too"),
    ("canvas", "A drawing becomes 196 bits"),
    ("dilation", "Dilation grows the stroke"),
    ("downsample", "Four cells become one feature"),
    ("ten-scores", "Forty-nine inputs, ten scores"),
    ("score-trace", "Follow every term of a real score"),
    ("popcount", "Small weights become popcount groups"),
    ("argmax", "Choose the winner and measure the gap"),
    ("segments", "An index lights seven segments"),
    ("training", "Learning happens before the page opens"),
    ("limits", "What the result and audit actually prove"),
    ("complete-path", "Reassemble the complete path"),
]

# 14-chapter voiced cut for htmlnet-study-15.mp4. Order matches ALL_CHAPTERS;
# each chapter_NN method renders standalone, so dropping neighbours is safe.
KEEP = {
    "inputs",
    "css-state",
    "gates",
    "half-adder",
    "binary",
    "neuron",
    "xor-proof",
    "xor-network",
    "canvas",
    "downsample",
    "ten-scores",
    "score-trace",
    "argmax",
    "training",
}
CHAPTERS = [c for c in ALL_CHAPTERS if c[0] in KEEP]


class CSSStudy(Scene):
    def __init__(self, chapter=1, pace=1.0, notes_dir=None, voice=True, **kwargs):
        self.chapter = chapter
        self.pace = pace
        self.notes_dir = Path(notes_dir) if notes_dir else None
        self.notes = []
        self.layout_warnings = []
        self._warning_keys = set()
        self.caption = None
        self.voice = voice
        self.audio_end = 0.0
        super().__init__(**kwargs)

    def construct(self):
        slug, title = CHAPTERS[self.chapter - 1]
        original_index = ALL_CHAPTERS.index((slug, title)) + 1
        self.camera.background_color = BG
        kicker = text(f"HTMLNET   /   {self.chapter:02d} OF {len(CHAPTERS)}", 16, MUTED)
        kicker.move_to([-7.25, 4.18, 0], aligned_edge=LEFT)
        heading = text(title, 34, INK, width=14.4).move_to(
            [-7.25, 3.62, 0], aligned_edge=LEFT
        )
        rule = Line([-7.25, 3.2, 0], [7.25, 3.2, 0], color=EDGE, stroke_width=1)
        disclaimer = text(
            "Conceptual animation. The browser does not clock signals through these steps.",
            13,
            MUTED,
        )
        disclaimer.move_to([0, -4.23, 0])
        self.chrome = [kicker, heading, rule, disclaimer]
        self.add(*self.chrome)
        getattr(self, f"chapter_{original_index:02d}")()
        if self.voice and self.time < self.audio_end:
            self.hold_raw(self.audio_end - self.time)
        self.hold(1.0)
        self.snapshot("end")
        if self.notes:
            self.notes[-1]["end"] = round(self.time, 4)
        if self.notes_dir:
            self.notes_dir.mkdir(parents=True, exist_ok=True)
            (self.notes_dir / f"{self.chapter:02d}-{slug}.json").write_text(
                json.dumps(
                    {
                        "chapter": self.chapter,
                        "slug": slug,
                        "title": title,
                        "duration": self.time,
                        "notes": self.notes,
                        "layout_warnings": self.layout_warnings,
                        "source_digest": model.source_digest(),
                    },
                    indent=2,
                )
            )

    def move(self, *animations, seconds=1.6):
        if animations:
            self.play(
                *animations, run_time=max(1 / config.frame_rate, seconds * self.pace)
            )

    def hold(self, seconds):
        self.wait(max(1 / config.frame_rate, seconds * self.pace), frozen_frame=True)

    def hold_raw(self, seconds):
        """Hold for a narration-derived duration, never scaled by pace."""
        self.wait(max(1 / config.frame_rate, seconds), frozen_frame=True)

    def note(self, message):
        if self.notes:
            self.notes[-1]["end"] = round(self.time, 4)
        self.notes.append({"start": round(self.time, 4), "end": None, "text": message})
        if self.voice and self.time < self.audio_end:
            self.hold_raw(self.audio_end - self.time)
        lines = textwrap.wrap(message, width=96)
        caption = text("\n".join(lines), size=25, color=INK, width=14.45).move_to(
            [0, -3.48, 0]
        )
        if caption.height > 1.1:
            caption.scale_to_fit_height(1.1)
        if self.caption is None:
            self.move(FadeIn(caption), seconds=0.3)
        else:
            self.move(FadeOut(self.caption), FadeIn(caption), seconds=0.3)
        self.caption = caption
        if self.voice:
            wav_path, duration = voice.synth(message)
            self.add_sound(str(wav_path))
            self.audio_end = self.time + duration

    def step(self, message, *animations, read=None, run=1.8):
        self.note(message)
        self.move(*animations, seconds=run)
        if self.voice:
            self.hold_raw(max(0.5, self.audio_end - self.time) + 0.2)
        else:
            self.hold(max(7, len(message.split()) / 2.25) if read is None else read)
        self.check_layout()
        if len(self.notes) in (3, 7):
            self.snapshot(f"step-{len(self.notes):02d}")

    def check_layout(self):
        def bounds(obj):
            return (
                obj.get_left()[0],
                obj.get_right()[0],
                obj.get_bottom()[1],
                obj.get_top()[1],
            )

        def warn(kind, details):
            key = (kind, json.dumps(details, sort_keys=True))
            if key not in self._warning_keys:
                self._warning_keys.add(key)
                self.layout_warnings.append(
                    {"time": round(self.time, 2), "type": kind, **details}
                )

        for obj in self.mobjects:
            if not obj.has_points() and not obj.submobjects:
                continue
            box = bounds(obj)
            if box[0] < -7.9 or box[1] > 7.9 or box[2] < -4.46 or box[3] > 4.46:
                warn(
                    "outside_frame",
                    {
                        "object": type(obj).__name__,
                        "bounds": [round(float(v), 3) for v in box],
                    },
                )
        from manim import Text

        texts = [
            obj
            for obj in self.get_mobject_family_members()
            if isinstance(obj, Text) and obj.width > 0.02 and obj.height > 0.02
        ]
        for a, b in combinations(texts, 2):
            aa, bb = bounds(a), bounds(b)
            x = min(aa[1], bb[1]) - max(aa[0], bb[0])
            y = min(aa[3], bb[3]) - max(aa[2], bb[2])
            if (
                x > 0.04
                and y > 0.04
                and x * y > 0.2 * min(a.width * a.height, b.width * b.height)
            ):
                warn(
                    "text_overlap",
                    {
                        "texts": [a.text, b.text],
                        "centers": [
                            [round(float(v), 2) for v in obj.get_center()[:2]]
                            for obj in (a, b)
                        ],
                    },
                )

    def snapshot(self, label):
        if self.notes_dir:
            directory = self.notes_dir / "frames"
            directory.mkdir(parents=True, exist_ok=True)
            self.renderer.update_frame(self, ignore_skipping=True)
            Image.fromarray(self.renderer.get_frame()).save(
                directory / f"{self.chapter:02d}-{label}.png"
            )

    def clear_stage(self):
        keep = self.chrome + ([self.caption] if self.caption is not None else [])
        objects = [obj for obj in self.mobjects if obj not in keep]
        self.move(*[FadeOut(obj) for obj in objects], seconds=0.6)

    def flow(self, *arrows, seconds=2.3):
        self.move(
            LaggedStart(
                *[
                    ShowPassingFlash(
                        a.copy().set_color(YELLOW).set_stroke(width=5), time_width=0.45
                    )
                    for a in arrows
                ],
                lag_ratio=0.35,
            ),
            seconds=seconds,
        )

    def replace_formula(self, old, value, color=INK, size=35):
        new = equation(value, old.get_center(), size, color, width=14)
        self.move(Transform(old, new), seconds=1.4)

    def chapter_01(self):
        p = model.predict(model.canvases()["seven"])
        grid = PixelGrid(values=[0] * 196, size=4.1).move_to([-3.7, 0.4, 0])
        display = SevenSegment(size=2.8).move_to([4.2, 0.4, 0])
        self.step(
            "The drawing supplies inputs. A separate calculation chooses which digit to display.",
            Create(grid),
            FadeIn(display),
        )
        self.note(
            "A thin seven switches on 18 cells. Each cell stores only zero or one."
        )
        for i in np.flatnonzero(p.canvas):
            self.move(grid.cells[int(i)].animate.set_fill(ORANGE), seconds=0.18)
        self.hold(7)
        self.step(
            "The prediction is not stored in a checkbox. It is a result of the model's calculations.",
            display.change(p.winner),
        )
        self.clear_stage()
        bit = Bit(0, "checkbox a", side=1.3).move_to([-5.1, 0.8, 0])
        value = Signal("--a", 0, BLUE, radius=0.6).move_to([-1.8, 0.8, 0])
        edge = Arrow(bit.box.get_right(), value.ring.get_left(), buff=0.2, color=EDGE)
        self.step(
            "Isolate one input. Unchecked is zero. Checked is one. This mapping does not yet perform any neural-network math.",
            FadeIn(bit),
            FadeIn(value),
            GrowArrow(edge),
        )
        self.step(
            "Checking the box changes the input value that CSS calculations can read.",
            bit.change(1),
            value.change(1),
        )
        other = Signal("calculation", "?", GREEN, radius=0.6).move_to([3.4, 0.8, 0])
        next_edge = wire(value, other)
        self.step(
            "A later CSS declaration reads that number with var(). Derived values do not need their own checkboxes.",
            FadeIn(other),
            GrowArrow(next_edge),
        )
        self.flow(edge, next_edge)
        counts = equation(
            "196 drawing inputs   ≠   6,834 registered signals",
            [0, -1.6, 0],
            29,
            YELLOW,
        )
        self.step(
            "Most registered signals are intermediate bits, aliases, or display values. The whole circuit is not a field of input controls.",
            Write(counts),
        )
        self.step(
            "We will build the calculation from one bit upward, then follow the exact saved seven through the digit classifier.",
            Indicate(other, color=GREEN),
        )

    def chapter_02(self):
        bit = Bit(0, 'input id="a"', side=1.2).move_to([-4.2, 1.0, 0])
        signal = Signal("--a", 0).move_to([-4.2, -1.1, 0])
        panel = code_panel(
            '<input type="checkbox" id="a">\n\n.rt { --a: 0; }\nbody.rt:has(#a:checked) {\n  --a: 1;\n}',
            "HTML + generated CSS",
        )
        self.step(
            "HTML creates the checkbox. The CSS rule matches its checked state.",
            FadeIn(bit),
            FadeIn(signal),
            FadeIn(panel),
        )
        self.step(
            "The default value is zero. The checked selector is more specific, so it overrides the default when the box is checked.",
            bit.change(1),
            signal.change(1),
            Indicate(panel.lines[3], color=YELLOW),
        )
        for value in (0, 1, 0):
            self.move(bit.change(value), signal.change(value), seconds=1)
            self.hold(2)
        self.step(
            "No event handler is needed for this mapping. Native checkbox state and CSS selector matching already exist in the browser.",
            Circumscribe(panel, color=BLUE),
        )
        registration = code_panel(
            '@property --a {\n  syntax: "<integer>";\n  inherits: true;\n  initial-value: 0;\n}',
            "gen/src/circuit.rs · render",
        )
        self.step(
            "Registration gives this custom property an integer type and a default. It does not automatically restrict the value to a bit.",
            ReplacementTransform(panel, registration),
        )
        self.step(
            "Our input mapping uses only zero and one. The gate equations preserve that range when their inputs are bits.",
            bit.change(1),
            signal.change(1),
        )
        body = text("body.rt", 32, BLUE).move_to([-4.2, 1.6, 0])
        child = text("descendant display", 23, GREEN).move_to([-4.2, -0.6, 0])
        self.move(FadeOut(bit), FadeOut(signal))
        arrow = Arrow(body.get_bottom(), child.get_top(), buff=0.15, color=EDGE)
        self.step(
            "The body is the common calculation scope. Descendant displays inherit its computed values.",
            FadeIn(body),
            GrowArrow(arrow),
            FadeIn(child),
        )
        self.step(
            "Changing a variable on a child does not recalculate an expression that the parent already computed. Scope matters.",
            Indicate(body, color=YELLOW),
        )

    def chapter_03(self):
        a = Signal("a", 0).move_to([-5.5, 1.3, 0])
        b = Signal("b", 0).move_to([-5.5, -1.0, 0])
        both = Signal("min(a,b)", 0, GREEN).move_to([-0.9, 0.2, 0])
        neg = Signal("1 - min(a,b)", 1, PURPLE).move_to([4.2, 0.2, 0])
        ab, bb, bn = wire(a, both), wire(b, both), wire(both, neg)
        self.step("Start with two independent input values.", FadeIn(a), FadeIn(b))
        self.step(
            "This derived value reads both inputs. For bits, their minimum is one only when both are one.",
            GrowArrow(ab),
            GrowArrow(bb),
            FadeIn(both),
        )
        self.step(
            "A further calculation can read the first result. This is a dependency, not another user-controlled state.",
            GrowArrow(bn),
            FadeIn(neg),
        )
        for aa, bbv in ((1, 0), (1, 1), (0, 1), (0, 0)):
            self.note(
                f"Inputs a={aa}, b={bbv}. The minimum is {min(aa, bbv)}. Subtracting it from one gives {1 - min(aa, bbv)}."
            )
            self.move(a.change(aa), b.change(bbv))
            self.flow(ab, bb)
            self.move(both.change(min(aa, bbv), GREEN))
            self.flow(bn)
            self.move(neg.change(1 - min(aa, bbv), PURPLE))
            self.hold(4)
        self.step(
            "The arrows show which values are needed. Declaration order is not a clock, and these moving highlights are not browser timing.",
            Circumscribe(both, color=YELLOW),
        )
        self.step(
            "The shipped graph is acyclic. Feeding a result back into its own custom-property definition does not create a recurrent neuron.",
            Circumscribe(neg, color=PURPLE),
        )
        self.step(
            "A feed-forward network also connects calculated values without requiring them to become editable controls.",
            Indicate(bn, color=GREEN),
        )

    def chapter_04(self):
        formulas = [
            ("NOT", "1 - a", lambda a, b: 1 - a, "g_not"),
            ("AND", "min(a,b)", min, "g_and"),
            ("OR", "max(a,b)", max, "g_or"),
            ("XOR", "max(a,b) - min(a,b)", lambda a, b: max(a, b) - min(a, b), "g_xor"),
        ]
        for name, formula, fn, signal_name in formulas:
            a = Bit(0, "a", side=0.95).move_to([-5.2, 1.3, 0])
            b = Bit(0, "b", side=0.95).move_to([-3.0, 1.3, 0])
            rule = equation(formula, [-4.1, -0.2, 0], 29, YELLOW, width=6)
            output = Signal(name, fn(0, 0), GREEN).move_to([-4.1, -1.7, 0])
            panel = code_panel(
                model.css(signal_name), "Actual declaration · dist/index.html"
            )
            explanations = {
                "NOT": "NOT reverses one bit. One minus zero is one. One minus one is zero.",
                "AND": "AND keeps the smaller bit. Either zero forces the result to zero.",
                "OR": "OR keeps the larger bit. Either one makes the result one.",
                "XOR": "XOR measures the difference between the larger and smaller bits. Equal inputs give zero; different inputs give one.",
            }
            self.step(
                explanations[name],
                FadeIn(a),
                FadeIn(b),
                Write(rule),
                FadeIn(output),
                FadeIn(panel),
            )
            for aa, bb in ((0, 0), (0, 1), (1, 0), (1, 1)):
                self.move(
                    a.change(aa),
                    b.change(bb),
                    output.change(fn(aa, bb), GREEN),
                    seconds=0.6,
                )
                self.hold(1.0)
            self.step(
                f"The {name} result is another numeric custom property. The next gate can read it with var().",
                Circumscribe(panel, color=YELLOW),
            )
            self.clear_stage()
        summary = equation(
            "bits + min/max/subtraction → Boolean gates", [0, 0.5, 0], 35, GREEN
        )
        self.step(
            "The browser supplies these arithmetic operations. The project interprets them as logic on the bit domain.",
            Write(summary),
        )

    def chapter_05(self):
        a = Signal("a", 0).move_to([-5.8, 1.3, 0])
        b = Signal("b", 0).move_to([-5.8, -1.0, 0])
        s = Signal("sum = XOR", 0, GREEN).move_to([-2.4, 1.3, 0])
        c = Signal("carry = AND", 0, YELLOW).move_to([-2.4, -1.0, 0])
        edges = [wire(a, s), wire(b, s), wire(a, c), wire(b, c)]
        panel = code_panel(
            model.css("ha_sum", "ha_carry"), "Circuit::half_adder · emitted CSS"
        )
        self.step(
            "A half adder has two output bits. One records the units place. The other records an extra two.",
            FadeIn(a),
            FadeIn(b),
            FadeIn(s),
            FadeIn(c),
        )
        self.step(
            "XOR gives the units bit. AND gives the carry because two active inputs need the next binary place.",
            *[GrowArrow(e) for e in edges],
            FadeIn(panel),
        )
        result = equation("0 + 2×0 = 0", [-3.9, -2.35, 0], 28)
        self.move(Write(result))
        for aa, bb in ((0, 0), (0, 1), (1, 0), (1, 1)):
            self.note(
                f"Add {aa} and {bb}. The sum bit is {aa ^ bb}; the carry bit is {aa & bb}. Their place values reconstruct {aa + bb}."
            )
            self.move(a.change(aa), b.change(bb))
            self.flow(*edges, seconds=2.4)
            self.move(
                s.change(aa ^ bb, GREEN),
                c.change(aa & bb, YELLOW),
                Transform(
                    result,
                    equation(
                        f"{aa ^ bb} + 2×{aa & bb} = {aa + bb}", result.get_center(), 28
                    ),
                ),
            )
            self.hold(6)
        self.step(
            "For one plus one, carry-first order is 10. The zero is not a wrong answer; it is the units bit of two.",
            Circumscribe(c, color=YELLOW),
        )
        self.step(
            "These declarations calculate the outputs for the current inputs. They do not list a selector for every complete input pair.",
            Indicate(panel, color=BLUE),
        )

    def chapter_06(self):
        a = Signal("a", 0).move_to([-6, 1.7, 0])
        b = Signal("b", 0).move_to([-6, -0.2, 0])
        ci = Signal("carry in", 0, YELLOW).move_to([-6, -2.0, 0])
        t = Signal("a XOR b", 0).move_to([-2.8, 1.1, 0])
        ab = Signal("a AND b", 0).move_to([-2.8, -1.2, 0])
        s = Signal("sum", 0, GREEN).move_to([1.0, 1.7, 0])
        tc = Signal("t AND carry", 0).move_to([1.0, -0.7, 0])
        co = Signal("carry out", 0, YELLOW).move_to([5.1, -0.7, 0])
        edges = [
            wire(a, t),
            wire(b, t),
            wire(a, ab),
            wire(b, ab),
            wire(t, s),
            wire(ci, s),
            wire(t, tc),
            wire(ci, tc),
            wire(ab, co),
            wire(tc, co),
        ]
        self.step(
            "A full adder accepts a third input: the carry from the previous column.",
            FadeIn(a),
            FadeIn(b),
            FadeIn(ci),
        )
        self.step(
            "First calculate a XOR b and a AND b. These are the same two operations used by a half adder.",
            FadeIn(t),
            FadeIn(ab),
            *[GrowArrow(e) for e in edges[:4]],
        )
        self.step(
            "The sum is a second XOR. A second AND checks whether the intermediate bit and carry-in produce another carry.",
            FadeIn(s),
            FadeIn(tc),
            *[GrowArrow(e) for e in edges[4:8]],
        )
        self.step(
            "The output carry is the OR of the two carry possibilities. Five gates represent one binary addition column.",
            FadeIn(co),
            *[GrowArrow(e) for e in edges[8:]],
        )
        for aa, bb, cc in (
            (0, 0, 0),
            (0, 0, 1),
            (0, 1, 0),
            (0, 1, 1),
            (1, 0, 0),
            (1, 0, 1),
            (1, 1, 0),
            (1, 1, 1),
        ):
            ss, cout = model.full_adder(aa, bb, cc)
            self.note(
                f"{aa} + {bb} + carry {cc} = {aa + bb + cc}. The outputs satisfy sum {ss} + 2×carry {cout} = {aa + bb + cc}."
            )
            self.move(a.change(aa), b.change(bb), ci.change(cc, YELLOW), seconds=0.6)
            self.move(t.change(aa ^ bb), ab.change(aa & bb), seconds=0.6)
            self.move(
                s.change(ss, GREEN),
                tc.change((aa ^ bb) & cc),
                co.change(cout, YELLOW),
                seconds=0.7,
            )
            self.hold(4)
        self.clear_stage()
        panel = code_panel(
            model.css("fa_s1", "fa_c1", "fa_sum", "fa_c2", "fa_carry"),
            "Actual full-adder declarations",
            center=(0, 0.2, 0),
            width=12,
        )
        self.step(
            "The generated code preserves the intermediate names. fa_sum reads fa_s1; fa_carry reads both carry-producing gates.",
            FadeIn(panel),
        )
        self.step(
            "Reading these var() references is how you inspect the circuit in code. The dependencies are the wires.",
            Indicate(panel.lines[-1], color=YELLOW),
        )

    def chapter_07(self):
        row = bit_word([0] * 4).move_to([0, 1.1, 0])
        dec = equation("0", [0, -1.0, 0], 52, GREEN)
        self.step(
            "A bit's position determines its weight. From right to left, the places are one, two, four, and eight.",
            FadeIn(row),
            Write(dec),
        )
        for i in reversed(range(4)):
            bits = [int(j == i) for j in range(4)]
            self.note(
                f"Only the bit in the {1 << (3 - i)} place is active, so the value is {1 << (3 - i)}."
            )
            self.move(
                *[cell.change(bit) for cell, bit in zip(row, bits)],
                Transform(
                    dec, equation(str(1 << (3 - i)), dec.get_center(), 52, GREEN)
                ),
            )
            self.hold(4)
        formula = equation("8b3 + 4b2 + 2b1 + b0", [0, 2.55, 0], 32, YELLOW)
        self.step(
            "Several active bits add their place values. The word does not mean the number of active boxes.",
            Write(formula),
        )
        self.note(
            "Watch the lower places reset as the next place turns on. This is counting from zero through fifteen."
        )
        for value in range(16):
            self.move(
                *[cell.change(bit) for cell, bit in zip(row, model.word(value, 4))],
                Transform(dec, equation(str(value), dec.get_center(), 52, GREEN)),
                seconds=0.5,
            )
            self.hold(0.7)
        self.step(
            "The LED display writes the most significant bit on the left, matching the place-value labels.",
            Circumscribe(row[0], color=YELLOW),
        )
        self.clear_stage()
        displayed = equation("display:        1  0  1  0", [0, 1.2, 0], 34, BLUE)
        stored = equation("compiler array: 0  1  0  1", [0, -0.3, 0], 34, YELLOW)
        self.step(
            "The Rust compiler stores the least significant bit first, the reverse of the displayed word.",
            Write(displayed),
            Write(stored),
        )
        self.step(
            "Changing the display order does not change the circuit's arithmetic. The earlier LED-order bug mixed these two conventions.",
            Indicate(displayed, color=GREEN),
        )

    def chapter_08(self):
        ar = bit_word([0] * 4).move_to([-0.4, 1.65, 0])
        br = bit_word([0] * 4).move_to([-0.4, 0.25, 0])
        out = bit_word([0] * 5, color=GREEN).move_to([-0.85, -1.4, 0])
        carry = equation("carry = 0", [4.1, 1.5, 0], 30, YELLOW)
        self.step(
            "Now add words one column at a time, starting at the rightmost bit.",
            FadeIn(ar),
            FadeIn(br),
            FadeIn(out),
            Write(carry),
        )
        self.step(
            "Each column is one full adder. Its carry-out becomes the next column's carry-in.",
            Circumscribe(ar[-1], color=YELLOW),
        )
        for a, b in ((7, 1), (5, 3), (10, 5), (15, 1)):
            self.note(
                f"Work {a} + {b}. The fifth output bit keeps a carry that no longer fits in four bits."
            )
            self.move(
                *[c.change(v) for c, v in zip(ar, model.word(a, 4))],
                *[c.change(v) for c, v in zip(br, model.word(b, 4))],
                *[c.change(0) for c in out],
            )
            for step in model.addition_trace(a, b):
                index = 3 - step["column"]
                marker = SurroundingRectangle(
                    VGroup(ar[index], br[index]), color=YELLOW, buff=0.08
                )
                self.move(
                    Create(marker),
                    Transform(
                        carry,
                        equation(
                            f"{step['a']} + {step['b']} + {step['carry_in']} = {step['sum'] + 2 * step['carry_out']}",
                            carry.get_center(),
                            25,
                            YELLOW,
                        ),
                    ),
                    seconds=0.7,
                )
                self.move(out[index + 1].change(step["sum"]), seconds=0.6)
                token = text(step["carry_out"], 25, YELLOW, mono=True).move_to(
                    ar[index].get_top() + UP * 0.42
                )
                destination = (
                    ar[index - 1].get_top() + UP * 0.42
                    if index > 0
                    else out[0].number.get_center()
                )
                self.move(FadeIn(token), seconds=0.25)
                self.move(token.animate.move_to(destination), seconds=0.8)
                self.move(FadeOut(token), seconds=0.25)
                self.hold(0.8)
                self.move(FadeOut(marker), seconds=0.2)
            self.move(
                out[0].change(model.addition_trace(a, b)[-1]["carry_out"]), seconds=0.6
            )
            self.hold(4)
        self.step(
            "Fifteen plus one is 10000, not 0000. Dropping the final carry would silently wrap the result.",
            Circumscribe(out[0], color=YELLOW),
        )
        self.clear_stage()
        panel = code_panel(
            'for (i, (ab, bb)) in\n    a_bits.iter().zip(b_bits).enumerate()\n{\n  let (s, c) = self.full_adder(\n    &format!("{name}_b{i}"),\n    ab, bb, &carry);\n  outs.push(s);\n  carry = ref(&c);\n}',
            "Circuit::ripple_add · excerpt, ref spelling shortened",
            center=(0, 0.2, 0),
            width=12,
        )
        self.step(
            "The loop runs in Rust at build time. It emits full-adder declarations whose carry names reference the previous stage.",
            FadeIn(panel),
        )
        self.step(
            "There is no Rust loop running in the page. The browser receives the expanded, fixed CSS graph.",
            Circumscribe(panel, color=BLUE),
        )

    def chapter_09(self):
        a = bit_word([1, 1]).move_to([-3, 1.7, 0])
        b = bit_word([1, 0]).move_to([3, 1.7, 0])
        row0 = bit_word([0] * 4).move_to([0, 0.15, 0])
        row1 = bit_word([0, 0, 1, 1]).move_to([0, -1.35, 0])
        self.step(
            "Multiply two two-bit integers. Each multiplier bit selects a copy of the first number or a row of zeros.",
            FadeIn(a),
            FadeIn(b),
        )
        self.step(
            "For three times two, the low multiplier bit is zero. Every partial product in the first row is zero.",
            FadeIn(row0),
            Circumscribe(b[1], color=YELLOW),
        )
        self.step(
            "The high multiplier bit is one. It selects a copy of three before we align the row with its place value.",
            FadeIn(row1),
            Circumscribe(b[0], color=YELLOW),
        )
        self.step(
            "This multiplier bit has weight two. Shift the selected row one place left, turning 0011 into 0110.",
            *[c.change(v) for c, v in zip(row1, [0, 1, 1, 0])],
        )
        self.clear_stage()
        lines = VGroup(
            equation("0011 × 0010", [0, 2.0, 0], 40, BLUE),
            equation("0000", [0, 0.9, 0], 40),
            equation("+ 0110", [0, -0.1, 0], 40),
            equation("= 0110 = 6", [0, -1.4, 0], 40, GREEN),
        )
        self.step(
            "Align the partial products by place value and add them with the same ripple-adder construction.",
            *[Write(o) for o in lines],
        )
        self.step(
            "Each copied product bit is an AND gate. The larger operation is binary long multiplication, not an input-pair lookup.",
            Indicate(lines[-1], color=GREEN),
        )
        for target in ("0011 × 0011", "0011", "+ 0110", "= 1001 = 9"):
            i = ("0011 × 0011", "0011", "+ 0110", "= 1001 = 9").index(target)
            self.move(
                Transform(
                    lines[i],
                    equation(
                        target, lines[i].get_center(), 40, GREEN if i == 3 else INK
                    ),
                )
            )
            self.hold(2)
        self.step(
            "Three times three activates both rows. Their sum is nine, written 1001.",
            Circumscribe(lines[-1], color=YELLOW),
        )
        self.clear_stage()
        panel = code_panel(
            model.css("mul2_pp0_0", "mul2_pp1_0", "mul2_pp0_1", "mul2_pp1_1"),
            "Actual partial products · dist/index.html",
            center=(0, 0.4, 0),
            width=12,
        )
        self.step(
            "These four AND declarations are the start of the shipped multiplier. Later declarations add the shifted rows.",
            FadeIn(panel),
        )
        self.step(
            "The bit-circuit construction is a teaching choice. Native CSS can also multiply two numeric variables directly.",
            Indicate(panel, color=BLUE),
        )

    def chapter_10(self):
        row = bit_word([1, 1, 0, 1]).move_to([0, 1.4, 0])
        value = equation("8 + 4 + 0 + 1 = 13", [0, -0.2, 0], 36)
        self.step(
            "The same bits can represent different numbers under different conventions. This unsigned word means thirteen.",
            FadeIn(row),
            Write(value),
        )
        signed_row = bit_word([1, 1, 0, 1], signed=True).move_to(row)
        self.step(
            "Two's complement makes the leftmost coefficient negative. Now 1101 means minus three.",
            ReplacementTransform(row, signed_row),
            Transform(
                value, equation("−8 + 4 + 0 + 1 = −3", value.get_center(), 36, RED)
            ),
        )
        self.step(
            "Four signed bits represent minus eight through seven. A leading one marks a negative value in this format.",
            Circumscribe(signed_row[0], color=RED),
        )
        line = NumberLine(
            x_range=[-8, 7, 1], length=11.8, include_numbers=False, color=EDGE
        ).move_to([0, -1.5, 0])
        labels = VGroup(
            *[
                text(v, 20, MUTED).next_to(line.n2p(v), DOWN, buff=0.15)
                for v in (-8, -4, 0, 4, 7)
            ]
        )
        dot = Dot(line.n2p(-3), color=YELLOW, radius=0.09)
        self.step(
            "Follow the signed value along a number line. Negative values have a leading one; zero and positive values have a leading zero.",
            Create(line),
            FadeIn(labels),
            FadeIn(dot),
        )
        for v in (-8, -7, -4, -1, 0, 3, 7):
            bits = model.word(v, 4)
            self.move(
                *[cell.change(bit) for cell, bit in zip(signed_row, bits)],
                dot.animate.move_to(line.n2p(v)),
                Transform(
                    value,
                    equation(
                        "".join(map(str, bits)) + f" = {v}",
                        value.get_center(),
                        36,
                        RED if v < 0 else GREEN,
                    ),
                ),
            )
            self.hold(2)
        self.clear_stage()
        positive = bit_word([0, 0, 1, 1], signed=True).move_to([0, 1.5, 0])
        caption = equation("start with +3", [0, -0.3, 0], 36, GREEN)
        self.step(
            "To negate three, begin with its four-bit representation.",
            FadeIn(positive),
            Write(caption),
        )
        self.step(
            "Flip every bit. This alone is not negation; it produces minus four.",
            *[c.change(v) for c, v in zip(positive, [1, 1, 0, 0])],
            Transform(
                caption, equation("NOT 0011 = 1100 = −4", caption.get_center(), 34, RED)
            ),
        )
        self.step(
            "Then add one. NOT plus one gives the representation of minus three.",
            positive[-1].change(1),
            Transform(
                caption,
                equation("1100 + 0001 = 1101 = −3", caption.get_center(), 34, RED),
            ),
        )
        self.clear_stage()
        short = bit_word([1, 0, 1], signed=True).move_to([-3.5, 0.6, 0])
        long = bit_word([1, 1, 0, 1], signed=True).move_to([3.0, 0.6, 0])
        arrow = Arrow([-1.2, 0.8, 0], [0.8, 0.8, 0], buff=0.12, color=YELLOW)
        self.step(
            "Widening a signed word repeats the sign bit. Both 101 and 1101 mean minus three at their respective widths.",
            FadeIn(short),
            GrowArrow(arrow),
            FadeIn(long),
        )
        self.step(
            "Zero-extending a negative word changes its value. Neuron products must be sign-extended before they join a wider sum.",
            Circumscribe(long[0], color=YELLOW),
        )

    def chapter_11(self):
        x = Bit(0, "x", side=1).move_to([-4.7, 1.0, 0])
        magnitude = bit_word([0, 1, 0]).move_to([-0.5, 1.0, 0])
        product = bit_word([0, 0, 0], signed=True, color=GREEN).move_to([4.0, 1.0, 0])
        formula = equation("2 × 0 = 0", [0, -1.1, 0], 40)
        self.step(
            "A fixed integer weight multiplied by one bit is either zero or the weight itself.",
            FadeIn(x),
            FadeIn(magnitude),
            FadeIn(product),
            Write(formula),
        )
        self.step(
            "The magnitude of two is 010. AND each magnitude bit with x.",
            Circumscribe(magnitude, color=YELLOW),
        )
        self.step(
            "When x is one, the mask passes the weight's bits through.",
            x.change(1),
            *[c.change(v) for c, v in zip(product, [0, 1, 0])],
            Transform(formula, equation("2 × 1 = 2", formula.get_center(), 40, GREEN)),
        )
        self.step(
            "When x is zero, all product bits are zero. No general multiplier is needed for this special input domain.",
            x.change(0),
            *[c.change(0) for c in product],
            Transform(formula, equation("2 × 0 = 0", formula.get_center(), 40)),
        )
        self.step(
            "For a negative weight, form the masked magnitude first, then apply NOT plus one.",
            x.change(1),
            *[c.change(v) for c, v in zip(product, [0, 1, 0])],
        )
        self.step(
            "Negating 010 at three-bit width gives 110, which represents minus two.",
            *[c.change(v) for c, v in zip(product, [1, 1, 0])],
            Transform(formula, equation("−2 × 1 = −2", formula.get_center(), 40, RED)),
        )
        self.clear_stage()
        panel = code_panel(
            model.css("n1_t0_m0", "n1_t0_m1", "n1_t0_m2", "n1_t1_n0"),
            "Net::neuron · emitted masking and NOT gates",
            center=(0, 0.4, 0),
            width=12,
        )
        self.step(
            "The generated code still contains real mask and negation gates. A power-of-two weight is not evidence that all this code vanishes.",
            FadeIn(panel),
        )
        self.step(
            "The signed product is widened before addition. Its numerical value must survive that change of width.",
            Indicate(panel, color=BLUE),
        )

    def chapter_12(self):
        u = matrix([[1, 0]], BLUE).move_to([-3.8, 1.5, 0])
        v = matrix([[1, 1]], BLUE).move_to([3.8, 1.5, 0])
        terms = equation("1×1  +  0×1", [0, 0.1, 0], 42, YELLOW)
        total = equation("1", [0, -1.5, 0], 54, GREEN)
        self.step(
            "A dot product pairs corresponding components, multiplies each pair, then adds the products.",
            FadeIn(u),
            FadeIn(v),
        )
        self.step(
            "These vectors each have two binary components. They are not scalar words whose entries range from zero to three.",
            Circumscribe(u, color=BLUE),
        )
        self.step(
            "The first pair contributes one. The second pair contributes zero.",
            Write(terms),
        )
        self.step(
            "Add the contributions. This example's dot product is one.",
            TransformFromCopy(terms, total),
        )
        for uu, vv in (
            ([1, 1], [1, 1]),
            ([0, 1], [1, 0]),
            ([1, 0], [0, 1]),
            ([0, 1], [0, 1]),
        ):
            expect = sum(a * b for a, b in zip(uu, vv))
            self.note(
                f"Pair {uu} with {vv}. Only positions active in both vectors contribute, giving a dot product of {expect}."
            )
            self.move(
                Transform(u, matrix([uu], BLUE).move_to(u)),
                Transform(v, matrix([vv], BLUE).move_to(v)),
                Transform(
                    terms,
                    equation(
                        f"{uu[0]}×{vv[0]}  +  {uu[1]}×{vv[1]}",
                        terms.get_center(),
                        42,
                        YELLOW,
                    ),
                ),
                Transform(total, equation(str(expect), total.get_center(), 54, GREEN)),
            )
            self.hold(4)
        self.step(
            "Two binary components can produce a dot product of zero, one, or two. Wider output storage does not enlarge that mathematical range.",
            Circumscribe(total, color=GREEN),
        )
        self.clear_stage()
        panel = code_panel(
            model.css("d_u0v0_pp0_0", "d_u1v1_pp0_0", "dot_sum_b0_sum"),
            "Actual dot-product signals",
            center=(0, 0.3, 0),
            width=12,
        )
        self.step(
            "The demo connects the two bit-product circuits to a ripple sum. The long names identify intermediate signals, not different kinds of math.",
            FadeIn(panel),
        )

    def chapter_13(self):
        w = matrix(
            [[2, 1], [1, 2]], INK, cell_width=1.1, cell_height=0.9, size=37
        ).move_to([-3.8, 0.6, 0])
        x = matrix([[1], [0]], BLUE, cell_height=0.9, size=37).move_to([0, 0.6, 0])
        out = matrix([["?"], ["?"]], GREEN, cell_height=0.9, size=37).move_to(
            [4, 0.6, 0]
        )
        times = equation("×", [-1.65, 0.6, 0], 40)
        equals = equation("=", [1.85, 0.6, 0], 40)
        self.step(
            "Matrix times vector means one dot product for each output row. Both rows read the same input vector.",
            FadeIn(w),
            FadeIn(x),
            FadeIn(out),
            Write(times),
            Write(equals),
        )
        self.step(
            "The first row has weights two and one. With input [1,0], its sum is two.",
            Circumscribe(VGroup(w.entries[0], w.entries[1]), color=YELLOW),
            Transform(
                out.entries[0], text(2, 37, GREEN, mono=True).move_to(out.entries[0])
            ),
        )
        self.step(
            "The second row has weights one and two. The same input now gives one.",
            Circumscribe(VGroup(w.entries[2], w.entries[3]), color=YELLOW),
            Transform(
                out.entries[1], text(1, 37, GREEN, mono=True).move_to(out.entries[1])
            ),
        )
        formula = equation(
            "[ 2×1 + 1×0,  1×1 + 2×0 ] = [2,1]", [0, -1.55, 0], 28, YELLOW
        )
        self.step(
            "The output vector collects those row results. A matrix is not a separate mysterious operation added on top of the sums.",
            Write(formula),
        )
        for xx in ([0, 1], [1, 1], [0, 0], [1, 0]):
            yy = [2 * xx[0] + xx[1], xx[0] + 2 * xx[1]]
            self.note(
                f"Change the input to {xx}. The two row sums change to {yy} while the weights remain fixed."
            )
            self.move(
                Transform(
                    x,
                    matrix([[xx[0]], [xx[1]]], BLUE, cell_height=0.9, size=37).move_to(
                        x
                    ),
                ),
                Transform(
                    out,
                    matrix([[yy[0]], [yy[1]]], GREEN, cell_height=0.9, size=37).move_to(
                        out
                    ),
                ),
                Transform(
                    formula,
                    equation(
                        f"[ 2×{xx[0]} + 1×{xx[1]},  1×{xx[0]} + 2×{xx[1]} ] = {yy}",
                        formula.get_center(),
                        28,
                        YELLOW,
                    ),
                ),
            )
            self.hold(4)
        self.step(
            "A layer with many outputs repeats this row calculation. The digit model will use ten rows instead of two.",
            Circumscribe(w, color=GREEN),
        )
        self.step(
            "Because these weights are constants and inputs are bits, the gate implementation masks constants and adds their products.",
            Indicate(x, color=BLUE),
        )

    def chapter_14(self):
        x1 = Bit(0, "x1", side=0.9).move_to([-5.1, 1.8, 0])
        x0 = Bit(0, "x0", side=0.9).move_to([-2.6, 1.8, 0])
        formula = equation(
            "z = 2×0 − 2×0 − 1 = −1", [-3.8, -0.2, 0], 28, YELLOW, width=6.7
        )
        output = Signal("step(z)", 0, GREEN, radius=0.6).move_to([-3.8, -1.7, 0])
        panel = code_panel(
            "z = 2*x1 - 2*x0 - 1\ny = 1 if z >= 0 else 0\n\n" + model.css("n1_out"),
            "Math + actual activation CSS",
        )
        self.step(
            "A threshold neuron first computes a weighted sum plus a bias. Here the bias is minus one.",
            FadeIn(x1),
            FadeIn(x0),
            Write(formula),
            FadeIn(output),
            FadeIn(panel),
        )
        self.step(
            "The activation returns one at zero and above, otherwise zero. It converts a signed number back into a bit.",
            Circumscribe(output, color=GREEN),
        )
        for a, b in ((0, 0), (1, 0), (0, 1), (1, 1)):
            z = 2 * a - 2 * b - 1
            y = int(z >= 0)
            self.note(
                f"For x1={a}, x0={b}, the products and bias sum to {z}. The threshold therefore returns {y}."
            )
            self.move(
                x1.change(a),
                x0.change(b),
                Transform(
                    formula,
                    equation(
                        f"z = 2×{a} − 2×{b} − 1 = {z}",
                        formula.get_center(),
                        28,
                        YELLOW,
                        width=6.7,
                    ),
                ),
                seconds=0.8,
            )
            self.hold(1.0)
            self.move(output.change(y, GREEN), seconds=0.8)
            self.hold(2.0)
        self.step(
            "In two's complement, a negative sum has sign bit one. Inverting that bit implements this nonnegative threshold.",
            Indicate(panel.lines[-1], color=YELLOW),
        )
        self.step(
            "This relies on enough bits to represent the sum. Overflow could change the sign and therefore the neuron's answer.",
            Circumscribe(formula, color=RED),
        )
        self.step(
            "Weights scale the evidence; the bias offsets the sum; the activation makes the decision. Each part has a different job.",
            Indicate(x1, color=BLUE),
            Indicate(output, color=GREEN),
        )

    def chapter_15(self):
        axes = Axes(
            x_range=[-0.3, 1.4, 0.5],
            y_range=[-0.3, 1.4, 0.5],
            x_length=4.8,
            y_length=4.8,
            axis_config={"color": EDGE, "include_ticks": False},
        ).move_to([-3.6, 0.3, 0])
        labels = VGroup(
            text("x1", 22, BLUE).next_to(axes.x_axis, RIGHT),
            text("x0", 22, BLUE).next_to(axes.y_axis, UP),
        )
        points = VGroup()
        for a, b in ((0, 0), (1, 0), (0, 1), (1, 1)):
            dot = Dot(axes.c2p(a, b), radius=0.11, color=GREEN if a ^ b else RED)
            label = text(f"{a},{b} → {a ^ b}", 19, GREEN if a ^ b else RED).next_to(
                dot, DOWN, buff=0.17
            )
            points.add(VGroup(dot, label))
        self.step(
            "XOR assigns one to opposite off-diagonal corners. The other two corners must produce zero.",
            Create(axes),
            FadeIn(labels),
            FadeIn(points),
        )
        f = equation("z = w1*x1 + w0*x0 + b", [3.6, 2.0, 0], 25, YELLOW, width=6.6)
        self.step(
            "One threshold neuron makes a linear boundary. One side must contain both green points without including a red point.",
            Write(f),
        )
        line = Line(axes.c2p(-0.2, 0.7), axes.c2p(1.3, 0.7), color=YELLOW)
        self.step(
            "A horizontal boundary cannot separate the diagonal labels. Neither can a vertical boundary.",
            Create(line),
        )
        self.move(
            Transform(line, Line(axes.c2p(0.7, -0.2), axes.c2p(0.7, 1.3), color=YELLOW))
        )
        self.hold(5)
        self.step(
            "A tilted line also runs into the conflicting corners. Trying a few lines illustrates the issue; the inequalities prove it.",
            Transform(
                line, Line(axes.c2p(-0.2, 0.7), axes.c2p(0.7, -0.2), color=YELLOW)
            ),
        )
        proof = (
            VGroup(
                text("positive corners require:", 22, GREEN),
                text("w1 + b ≥ 0", 26, GREEN, mono=True),
                text("w0 + b ≥ 0", 26, GREEN, mono=True),
            )
            .arrange(DOWN, buff=0.25)
            .move_to([3.6, 0.2, 0])
        )
        self.step(
            "Each positive corner must have a nonnegative score. Add those two requirements.",
            FadeIn(proof),
        )
        pos = equation("w1 + w0 + 2b ≥ 0", [3.6, -1.7, 0], 27, GREEN, width=6.5)
        self.step(
            "The positive examples force this combined expression to be at least zero.",
            Write(pos),
        )
        self.clear_stage()
        pos = equation("positive cases:  w1 + w0 + 2b ≥ 0", [0, 2.0, 0], 32, GREEN)
        neg = (
            VGroup(
                text("negative cases require:", 26, RED),
                text("b < 0", 31, RED, mono=True),
                text("w1 + w0 + b < 0", 31, RED, mono=True),
            )
            .arrange(DOWN, buff=0.25)
            .move_to([0, 0.1, 0])
        )
        self.step(
            "Now use the two negative corners. Their scores must both be strictly below zero under this threshold convention.",
            Write(pos),
            FadeIn(neg),
        )
        bad = equation("negative cases:  w1 + w0 + 2b < 0", [0, -1.9, 0], 32, RED)
        self.step(
            "Adding the negative requirements gives the same expression strictly below zero. Both demands cannot hold.",
            Write(bad),
        )
        self.step(
            "No choice of weights and bias fixes that contradiction for one linear threshold neuron. We need intermediate nonlinear decisions.",
            Circumscribe(pos, color=GREEN),
            Circumscribe(bad, color=RED),
        )

    def chapter_16(self):
        x1 = Signal("x1", 0).move_to([-5.6, 1.6, 0])
        x0 = Signal("x0", 0).move_to([-5.6, -1.1, 0])
        h1 = Signal("h1", 0, GREEN).move_to([-0.5, 1.6, 0])
        h2 = Signal("h2", 0, GREEN).move_to([-0.5, -1.1, 0])
        out = Signal("out", 0, YELLOW, radius=0.6).move_to([4.8, 0.25, 0])
        edges = [
            wire(x1, h1),
            wire(x0, h1),
            wire(x1, h2),
            wire(x0, h2),
            wire(h1, out),
            wire(h2, out),
        ]
        self.step(
            "Give one hidden neuron the job of detecting x1=1 and x0=0.",
            FadeIn(x1),
            FadeIn(x0),
            FadeIn(h1),
            GrowArrow(edges[0]),
            GrowArrow(edges[1]),
        )
        h1eq = equation("h1 = step(2x1 − 2x0 − 1)", [0.1, 2.75, 0], 25, GREEN)
        self.step(
            "Its weighted sum is positive only for that mismatched input case.",
            Write(h1eq),
        )
        h2eq = equation("h2 = step(−2x1 + 2x0 − 1)", [0.1, -2.2, 0], 25, GREEN)
        self.step(
            "The second hidden neuron detects the opposite mismatch, x1=0 and x0=1.",
            FadeIn(h2),
            GrowArrow(edges[2]),
            GrowArrow(edges[3]),
            Write(h2eq),
        )
        self.step(
            "The output receives both hidden bits. It accepts either detection using step(2h1 + 2h2 − 1).",
            FadeIn(out),
            GrowArrow(edges[4]),
            GrowArrow(edges[5]),
        )
        for a, b in ((0, 0), (1, 0), (0, 1), (1, 1)):
            pre, hidden, op, y = model.xor_forward(a, b)
            self.note(
                f"Inputs {a},{b}: hidden sums are {pre[0]} and {pre[1]}. They become bits {hidden[0]},{hidden[1]}; output sum {op} becomes {y}."
            )
            self.move(x1.change(a), x0.change(b))
            self.flow(*edges[:4], seconds=1.0)
            self.move(h1.change(hidden[0], GREEN), h2.change(hidden[1], GREEN))
            self.flow(*edges[4:], seconds=0.9)
            self.move(out.change(y, YELLOW))
            self.hold(2)
        self.step(
            "The hidden results are computed CSS values. They are consumed downstream, not turned into additional checkboxes.",
            Circumscribe(h1, color=GREEN),
            Circumscribe(h2, color=GREEN),
        )
        self.step(
            "These XOR weights are hand-picked. The trained digit classifier is a separate model and does not consume this XOR output.",
            Indicate(out, color=YELLOW),
        )
        self.clear_stage()
        p = code_panel(
            model.css("xor_out_t0_m1", "xor_out_t1_m1"),
            "Actual output-neuron inputs",
            center=(0, 0.4, 0),
            width=12,
        )
        self.step(
            "Here the output neuron reads xor_h1_out and xor_h2_out by name. Those references are direct evidence of the hidden-layer connection.",
            FadeIn(p),
        )

    def chapter_17(self):
        panel = code_panel(
            model.css("nb_h1pre", "nb_h1", "nb_h2pre", "nb_h2"),
            "Native comparison · actual CSS",
            center=(0, 0.4, 0),
            width=12,
        )
        self.step(
            "CSS does not require us to expand this network into binary gates. Native arithmetic can express its weighted sums directly.",
            FadeIn(panel),
        )
        self.step(
            "For integer z, clamping z+1 into the range zero to one implements step(z). That shortcut depends on the integer domain.",
            Indicate(panel.lines[2], color=YELLOW),
        )
        self.clear_stage()
        a = Signal("a", 2).move_to([-4.5, 1.0, 0])
        b = Signal("b", 3).move_to([-1.8, 1.0, 0])
        p = Signal("product", 6, GREEN, radius=0.6).move_to([3.8, 1.0, 0])
        formula = equation("calc(var(--a) * var(--b))", [0, -1.1, 0], 33, YELLOW)
        self.step(
            "Two numeric runtime variables can also multiply directly in calc(). Earlier project documentation incorrectly denied this.",
            FadeIn(a),
            FadeIn(b),
            FadeIn(p),
            Write(formula),
        )
        for aa, bb in ((2, 3), (3, 3), (0, 3), (1, 2), (2, 2)):
            self.move(a.change(aa), b.change(bb), p.change(aa * bb, GREEN))
            self.hold(3)
        self.step(
            "Both browser engines compare native multiplication with the structural multiplier across all sixteen two-bit operand pairs.",
            Circumscribe(formula, color=BLUE),
        )
        self.clear_stage()
        counts = (
            VGroup(
                text("Gate XOR: 177 gates", 37, YELLOW),
                text("Native XOR + matrix rows: 8 declarations", 32, GREEN),
                text(
                    "Inputs, aliases, and decimal views are separate counts.", 23, MUTED
                ),
            )
            .arrange(DOWN, buff=0.6)
            .move_to([0, 0.4, 0])
        )
        self.step(
            "Gate mode exposes the binary arithmetic. Native mode shows how compact the same fixed calculations can be.",
            FadeIn(counts),
        )
        self.step(
            "The comparison is between two real implementations. It is not proof of a CSS multiplication restriction.",
            Indicate(counts[1], color=GREEN),
        )
        self.step(
            "The browser provides arithmetic in both cases. Neither implementation constructs the browser engine itself from transistors.",
            Indicate(counts[0], color=YELLOW),
        )

    def chapter_18(self):
        p = model.predict(model.canvases()["seven"])
        grid = PixelGrid(14, 4.7).move_to([-3.4, 0.25, 0])
        count = equation("0 active cells", [3.8, 1.4, 0], 35, ORANGE)
        self.step(
            "The paint area has fourteen rows and fourteen columns. That gives 196 independently checked or unchecked input cells.",
            Create(grid),
            Write(count),
        )
        self.note(
            "Build the exact thin-seven test fixture one active cell at a time. The pattern, not an image screenshot, is the input."
        )
        for n, i in enumerate(np.flatnonzero(p.canvas), 1):
            self.move(
                grid.cells[int(i)].animate.set_fill(ORANGE),
                Transform(
                    count, equation(f"{n} active cells", count.get_center(), 35, ORANGE)
                ),
                seconds=0.17,
            )
        self.hold(3.5)
        ids = equation("mc0 … mc195", [3.8, -0.2, 0], 29, BLUE)
        self.step(
            "The checkbox names use row-major order. Move across one row, then continue at the start of the next.",
            Write(ids),
        )
        for i in (0, 13, 14, 27, 195):
            marker = SurroundingRectangle(grid.cells[i], color=YELLOW, buff=0.02)
            tag = equation(
                f"row {i // 14}, column {i % 14}\nindex = 14×{i // 14}+{i % 14} = {i}",
                [3.8, -1.5, 0],
                24,
                YELLOW,
                width=6.2,
            )
            self.move(Create(marker), FadeIn(tag))
            self.hold(1.5)
            self.move(FadeOut(marker), FadeOut(tag), seconds=0.3)
        self.step(
            "The visible orange blobs overlap neighboring cells, but that overlap is not sampled back into the model. Only checked cells supply bits.",
            Indicate(grid, color=ORANGE),
        )
        self.step(
            "The drawing script interpolates pointer positions and toggles these cells. It does not calculate the following image-processing stages.",
            Circumscribe(count, color=YELLOW),
        )
        self.step(
            "With all JavaScript removed, native clicks still toggle cells. Smooth drag painting is the convenience you give up in the script-free build.",
            Indicate(ids, color=BLUE),
        )

    def chapter_19(self):
        grid = PixelGrid(7, 4.6).move_to([-3.4, 0.25, 0])
        rule = equation(
            "self OR up OR down\nOR left OR right", [3.8, 1.1, 0], 29, YELLOW, width=6.4
        )
        self.step(
            "Dilation replaces each cell with the OR of itself and its four orthogonal neighbors. Diagonal cells are not part of this neighborhood.",
            Create(grid),
            Write(rule),
        )
        center = 24
        plus = [24, 17, 31, 23, 25]
        self.step(
            "Start with one active center cell. Its value contributes to the output at the center and each adjacent location.",
            grid.cells[center].animate.set_fill(ORANGE),
        )
        self.step(
            "One active input therefore grows into a plus-shaped group of five active outputs.",
            *[grid.cells[i].animate.set_fill(YELLOW) for i in plus if i != center],
        )
        self.step(
            "The corners around that plus remain off. This is not a full three-by-three square dilation.",
            Circumscribe(VGroup(*[grid.cells[i] for i in plus]), color=YELLOW),
        )
        self.move(grid.change([0] * 49))
        self.step(
            "At a boundary, missing neighbors contribute nothing. A corner input activates only three output cells.",
            *[grid.cells[i].animate.set_fill(ORANGE) for i in (0, 1, 7)],
        )
        self.clear_stage()
        p = model.predict(model.canvases()["seven"])
        left = PixelGrid(14, 4.4, p.canvas).move_to([-3.8, 0.3, 0])
        right = PixelGrid(14, 4.4).move_to([3.8, 0.3, 0])
        arrow = Arrow([-1.2, 0.3, 0], [1.2, 0.3, 0], buff=0.1, color=YELLOW)
        self.step(
            "Now apply the same neighborhood operation to the real seven. Every output uses the original input stage, not a partially updated neighbor.",
            FadeIn(left),
            Create(right),
            GrowArrow(arrow),
        )
        self.note(
            "The fixture starts with 18 active cells. One dilation round produces 56 active cells."
        )
        for row in range(14):
            self.move(
                *[
                    right.cells[row * 14 + c].animate.set_fill(
                        YELLOW if p.dilated[row * 14 + c] else PANEL
                    )
                    for c in range(14)
                ],
                seconds=0.35,
            )
        self.hold(6)
        self.step(
            "This thickens the stroke before reduction. It can help thin marks survive, but it can also merge nearby strokes or close gaps.",
            Indicate(right, color=YELLOW),
        )
        self.step(
            "The browser performs these OR operations in CSS. The pointer-input script does not perform dilation.",
            Circumscribe(arrow, color=BLUE),
        )

    def chapter_20(self):
        p = model.predict(model.canvases()["seven"])
        source = PixelGrid(14, 4.4, p.dilated, color=YELLOW).move_to([-3.8, 0.3, 0])
        target = PixelGrid(7, 3.9, color=GREEN).move_to([3.7, 0.3, 0])
        self.step(
            "Divide the dilated image into non-overlapping two-by-two blocks. Each block supplies one output feature.",
            FadeIn(source),
            Create(target),
        )
        self.step(
            "The reduction is OR. Any active cell in a block turns its output on. Only four zeros produce an off output.",
            Circumscribe(source.block(0, 0), color=BLUE),
        )
        source_box = SurroundingRectangle(source.block(0, 0), color=ORANGE, buff=0.03)
        target_box = SurroundingRectangle(target.cells[0], color=ORANGE, buff=0.03)
        self.move(Create(source_box), Create(target_box))
        self.note(
            "Follow each block into its matching feature. The 14×14 image becomes a 7×7 vector of bits, not gray pixel averages."
        )
        for i, value in enumerate(p.features):
            r, c = divmod(i, 7)
            self.move(
                Transform(
                    source_box,
                    SurroundingRectangle(
                        source.block(2 * r, 2 * c), color=ORANGE, buff=0.03
                    ),
                ),
                Transform(
                    target_box,
                    SurroundingRectangle(target.cells[i], color=ORANGE, buff=0.03),
                ),
                target.cells[i].animate.set_fill(GREEN if value else PANEL),
                seconds=0.12,
            )
            self.hold(0.08)
        self.move(FadeOut(source_box), FadeOut(target_box))
        self.step(
            "The saved seven produces twenty active features. The classifier receives these forty-nine bits, not the original 196 cells.",
            Indicate(target, color=GREEN),
        )
        self.step(
            "An empty block and a block with one active cell produce different results. One and four active cells both produce the same on bit.",
            Circumscribe(target.cells[1], color=YELLOW),
        )
        self.step(
            "That reduction discards information. Different drawings can become the same feature pattern and therefore receive identical predictions.",
            Indicate(source, color=ORANGE),
            Indicate(target, color=GREEN),
        )
        self.step(
            "The trainer simulates this same dilation and OR reduction. Its earlier crop and centering steps do not occur in the live browser.",
            Circumscribe(source, color=BLUE),
        )

    def chapter_21(self):
        p = model.predict(model.canvases()["seven"])
        grid = PixelGrid(7, 3.4, p.features, color=GREEN).move_to([-4.7, 0.25, 0])
        self.step(
            "The reduced grid is a feature vector x with forty-nine entries. Its ordering must match the ordering of each weight row.",
            FadeIn(grid),
        )
        outline = SurroundingRectangle(grid.cells[0], color=YELLOW, buff=0.03)
        idx = equation("x[0] = 0", [-4.7, -2.1, 0], 26, BLUE)
        self.move(Create(outline), Write(idx))
        for i in (0, 1, 6, 7, 13, 48):
            self.move(
                Transform(
                    outline,
                    SurroundingRectangle(grid.cells[i], color=YELLOW, buff=0.03),
                ),
                Transform(
                    idx,
                    equation(f"x[{i}] = {p.features[i]}", idx.get_center(), 26, BLUE),
                ),
                seconds=0.8,
            )
            self.hold(2)
        chart = score_chart(p.scores, width=7.0, height=4.5).move_to([2.2, 0.25, 0])
        self.step(
            "The classifier has one weight row and one bias for each digit. Each row produces its own score.",
            FadeIn(chart),
        )
        dims = equation(
            "W: 10×49    x: 49×1    b: 10×1", [1.8, 2.85, 0], 23, YELLOW, width=9.3
        )
        self.step(
            "Matrix multiplication gives ten outputs. Adding the ten biases produces s = W x + b.",
            Write(dims),
        )
        self.step(
            "Positive and negative scores are allowed. These are comparison scores, not percentages and not probabilities.",
            Circumscribe(chart.rows[6], color=RED),
        )
        self.step(
            "For this exact input, digit seven has score twenty-four. We will trace its individual terms before choosing the winner.",
            Circumscribe(chart.rows[7], color=YELLOW),
        )
        self.step(
            "This is a linear classifier over processed features. There is no learned hidden layer in the shipped digit model.",
            Indicate(dims, color=GREEN),
        )

    def chapter_22(self):
        p = model.predict(model.canvases()["seven"])
        w = model.weights()
        row = w["weights"][7]
        bias = w["bias"][7]
        grid = PixelGrid(7, 3.8, p.features, color=BLUE).move_to([-4.3, 0.3, 0])
        total = Signal("running score", bias, GREEN, radius=0.72).move_to([4.5, 0.2, 0])
        current = equation(
            f"start at bias {bias}", [1.8, 2.0, 0], 30, YELLOW, width=9.8
        )
        self.step(
            "A score starts at its class bias. Each feature then contributes its stored weight times its input bit.",
            FadeIn(grid),
            FadeIn(total),
            Write(current),
        )
        self.step(
            f"Digit seven starts at bias {bias}. The following numbers come from scripts/weights_mnist.json.",
            Circumscribe(total, color=YELLOW),
        )
        marker = SurroundingRectangle(grid.cells[0], color=ORANGE, buff=0.025)
        self.move(Create(marker))
        acc = bias
        self.note(
            "Follow all forty-nine positions. An off feature contributes zero. An on feature contributes its signed weight."
        )
        for i, (weight, bit) in enumerate(zip(row, p.features)):
            product = weight * bit
            acc += product
            color = GREEN if product > 0 else RED if product < 0 else MUTED
            expression = equation(
                f"i={i:02d}    {weight} × {bit} = {product:+d}",
                current.get_center(),
                30,
                color,
                width=9.4,
            )
            self.move(
                Transform(
                    marker,
                    SurroundingRectangle(grid.cells[i], color=ORANGE, buff=0.025),
                ),
                Transform(current, expression),
                seconds=0.2,
            )
            if product:
                token = text(f"{product:+d}", 28, color, mono=True).move_to(
                    current.get_center() + DOWN * 0.65
                )
                self.move(FadeIn(token), seconds=0.1)
                self.move(
                    token.animate.move_to(total.ring.get_left() + LEFT * 0.25),
                    total.change(acc, GREEN),
                    seconds=0.3,
                )
                self.move(FadeOut(token), seconds=0.1)
            else:
                self.move(total.change(acc, GREEN), seconds=0.15)
            self.hold(0.25 if product else 0.15)
        self.step(
            f"The accumulated score is {acc}. This agrees with the browser reference for the same twenty active features.",
            Circumscribe(total, color=YELLOW),
        )
        self.step(
            "Off pixels are still part of the vector, but their products vanish. Positive weights raise this score; negative weights lower it.",
            Indicate(grid, color=BLUE),
        )
        self.clear_stage()
        f = equation(
            "score[k] = bias[k] + Σ weight[k][i] × pixel[i]", [0, 1.8, 0], 31, YELLOW
        )
        panel = code_panel(
            "bias[c] + (0..NPIX)\n  .map(|i| weights[c][i] * x[i] as i64)\n  .sum::<i64>()",
            "train/src/mnist.rs · score, line-wrapped",
            center=(0, -0.2, 0),
            width=12,
        )
        self.step(
            "This is the scalar reference calculation in the trainer. It is useful for understanding the math and checking the browser.",
            Write(f),
            FadeIn(panel),
        )
        self.step(
            "The browser does not call this Rust function. Its CSS circuit computes the same integer using the adders and gates from the earlier chapters.",
            Circumscribe(panel, color=BLUE),
        )

    def chapter_23(self):
        p = model.predict(model.canvases()["seven"])
        w = model.weights()
        groups = model.planes(w["weights"][7], p.features)
        labels = list(groups)
        xs = [-5.6, -1.9, 1.9, 5.6]
        objects = []
        self.step(
            "Digit weights are restricted to minus three through three. Each magnitude therefore needs only a low bit and a high bit."
        )
        for k, (label, x) in enumerate(zip(labels, xs)):
            color = GREEN if k < 2 else RED
            header = text(label, 24, color, width=3.3).move_to([x, 2.25, 0])
            indices = groups[label]
            dots = VGroup(
                *[
                    Dot(
                        [x + (i % 7 - 3) * 0.28, 1.2 - (i // 7) * 0.32, 0],
                        radius=0.085,
                        color=color,
                    )
                    for i in range(len(indices))
                ]
            )
            count = text(str(len(indices)), 42, color, mono=True).move_to([x, -0.35, 0])
            multiplier = text("×1" if k % 2 == 0 else "×2", 30, YELLOW).move_to(
                [x, -1.35, 0]
            )
            obj = VGroup(header, dots, count, multiplier)
            objects.append(obj)
            self.step(
                f"{label.capitalize()} contains {len(indices)} active inputs for this class. Each dot is one contributing input in that bit plane.",
                FadeIn(obj),
            )
        pl, ph, nl, nh = [len(groups[label]) for label in labels]
        f = equation(
            f"({pl} + 2×{ph}) − ({nl} + 2×{nh}) + {w['bias'][7]} = {p.scores[7]}",
            [0, -2.35, 0],
            30,
            YELLOW,
        )
        self.step(
            "Count the groups, double the high planes, subtract the negative contribution, and add the bias. The score is unchanged.",
            Write(f),
        )
        self.step(
            "A weight of three contributes once to the low plane and once to the high plane. Its contribution is one plus two, not a new kind of gate.",
            Indicate(objects[0], color=GREEN),
            Indicate(objects[1], color=GREEN),
        )
        self.clear_stage()
        count = 3
        first = bit_word(model.word(count, 4)).move_to([-3.2, 0.7, 0])
        second = bit_word(model.word(2 * count, 5)).move_to([3.1, 0.7, 0])
        arrow = Arrow([-0.8, 0.9, 0], [0.8, 0.9, 0], color=YELLOW, buff=0.1)
        self.step(
            "Doubling a binary count shifts the digits left and inserts a low zero. This example turns three into six without a general multiplier.",
            FadeIn(first),
            GrowArrow(arrow),
            FadeIn(second),
        )
        self.step(
            "The compiler stores bits low-first, so it prepends that zero to its array. The displayed word puts the same new zero on the right.",
            Circumscribe(second[-1], color=YELLOW),
        )
        self.step(
            "The counts themselves use full and half adders. Three equal-weight bits become a sum bit at that weight and a carry at twice the weight.",
            Circumscribe(first, color=BLUE),
        )
        self.step(
            "The optimized representation changes the circuit size, not the mathematical weighted sum. Independent tests compare both formulas.",
            Indicate(second, color=GREEN),
        )

    def chapter_24(self):
        p = model.predict(model.canvases()["seven"])
        chart = score_chart(p.scores, width=8.0, height=4.6).move_to([-2, 0.1, 0])
        best = Signal("winner index", 0, YELLOW, radius=0.55).move_to([4.9, 1.5, 0])
        runner = Signal("runner-up score", -64, BLUE, radius=0.55).move_to(
            [4.9, -0.65, 0]
        )
        self.step(
            "Argmax means the index of the largest score. Start with class zero as the incumbent.",
            FadeIn(chart),
            FadeIn(best),
            FadeIn(runner),
        )
        self.step(
            "The runner-up track starts at minus sixty-four, the smallest signed value, and updates as real scores replace it.",
            Indicate(runner, color=BLUE),
        )
        marker = SurroundingRectangle(chart.rows[0], color=YELLOW, buff=0.08)
        self.move(Create(marker))
        index = 0
        second = -64
        trace = []
        for k in range(1, 10):
            wins = p.scores[k] > p.scores[index]
            if wins:
                second = p.scores[index]
                index = k
            else:
                second = max(second, p.scores[k])
            trace.append((k, index, second))
        # Three narrated checkpoints instead of one caption per class: fewer
        # captions, same per-class transforms, values still read from `p`.
        groups = [range(1, 4), range(4, 7), range(7, 10)]
        for ks in groups:
            leader_before = trace[ks[0] - 2][1] if ks[0] > 1 else 0
            leader_after = trace[ks[-1] - 1][1]
            scores_shown = ", ".join(str(p.scores[k]) for k in ks)
            if leader_after != leader_before:
                message = (
                    f"Classes {ks[0]} through {ks[-1]} score {scores_shown}. "
                    f"Class {leader_after} takes the lead at {p.scores[leader_after]}."
                )
            else:
                message = (
                    f"Classes {ks[0]} through {ks[-1]} score {scores_shown}. "
                    f"None beat class {leader_after}'s {p.scores[leader_after]}."
                )
            self.note(message)
            for k in ks:
                _, index, second = trace[k - 1]
                self.move(
                    Transform(
                        marker,
                        SurroundingRectangle(chart.rows[k], color=YELLOW, buff=0.08),
                    ),
                    best.change(index, YELLOW),
                    runner.change(second, BLUE),
                    seconds=0.9,
                )
                self.hold(1.2)
            if self.voice:
                self.hold_raw(max(0.5, self.audio_end - self.time) + 0.2)
            self.check_layout()
        margin = equation(
            f"margin = {p.scores[index]} − {second} = {p.margin}",
            [0, -2.55, 0],
            30,
            GREEN,
        )
        self.step(
            "The final gap is winner minus runner-up. That gap is not a percentage confidence.",
            Write(margin),
        )
        one = model.predict(model.canvases()["one"])
        self.step(
            "The thin-one fixture is a real failure. Classes four and seven both score nine, so class four wins the tie.",
            Transform(
                chart, score_chart(one.scores, width=8, height=4.6).move_to(chart)
            ),
            best.change(one.winner, YELLOW),
            runner.change(9, BLUE),
            Transform(
                margin, equation("margin = 9 − 9 = 0", margin.get_center(), 30, RED)
            ),
            FadeOut(marker),
        )
        self.step(
            "The model must pick a digit even on ties. Lowest-index tie-breaking is deterministic, not an accuracy guarantee.",
            Circumscribe(best, color=YELLOW),
        )
        self.step(
            "The gate comparator sign-extends scores before subtraction. The extra bit keeps the comparison from overflowing.",
            Indicate(runner, color=BLUE),
        )

    def chapter_25(self):
        bits = bit_word(model.word(7, 4)).move_to([-3.5, 1.2, 0])
        display = SevenSegment(size=3.4).move_to([4.0, 0.25, 0])
        self.step(
            "The winning index is seven, written 0111 in display order. The circuit decodes that index into one-hot digit signals.",
            FadeIn(bits),
            FadeIn(display),
        )
        expr = equation(
            "digit7 = NOT(b3) AND b2 AND b1 AND b0",
            [-0.7, -1.8, 0],
            27,
            YELLOW,
            width=12.5,
        )
        self.step(
            "Digit seven requires a zero high bit and three low ones. This AND expression is true only for that index.",
            Write(expr),
        )
        active = equation("digit7 = 1", [-3.5, -0.4, 0], 30, GREEN)
        self.step(
            "The digit-seven signal contributes to the top, upper-right, and lower-right segment ORs.",
            display.change(7),
            Write(active),
        )
        labels = VGroup(
            *[
                text(name, 20, MUTED).next_to(
                    part, LEFT if name in "ef" else RIGHT, buff=0.1
                )
                for name, part in display.segments.items()
            ]
        )
        self.step(
            "Those segment names are a, b, and c. The remaining segments stay off.",
            FadeIn(labels),
        )
        self.step(
            "Each segment ORs the minterms of all digits that need it. This is a decoder, not a second digit-recognition model.",
            Circumscribe(display, color=YELLOW),
        )
        self.note(
            "These are decoder examples with supplied indices, not new classifier predictions. Watch the bit word and segment pattern agree."
        )
        for digit in range(10):
            self.move(
                *[cell.change(v) for cell, v in zip(bits, model.word(digit, 4))],
                display.change(digit),
                Transform(
                    active,
                    equation(
                        f"digit7 = {int(digit == 7)}",
                        active.get_center(),
                        30,
                        GREEN if digit == 7 else MUTED,
                    ),
                ),
                seconds=0.7,
            )
            self.hold(2)
        self.step(
            "The display reads gate bits directly. Decimal counters elsewhere decode words with native arithmetic only for human readability.",
            Indicate(display, color=GREEN),
        )
        self.step(
            "Display views never feed back into the network. Drawing input and calculated output remain separate.",
            Circumscribe(bits, color=BLUE),
        )

    def chapter_26(self):
        toy = text("TOY UPDATE · 2 classes, 3 features", 22, MUTED).move_to([0, 2.7, 0])
        x = matrix([[1, 0, 1]], BLUE, size=34).move_to([-4.4, 1.1, 0])
        wrong = matrix([[0, 0, 0]], RED, size=30).move_to([2.4, 1.65, 0])
        right = matrix([[0, 0, 0]], GREEN, size=30).move_to([2.4, -0.1, 0])
        self.step(
            "Learning changes weights using labeled examples. Here tied zero scores predict class zero, but the correct label is one.",
            FadeIn(toy),
            FadeIn(x),
            FadeIn(wrong),
            FadeIn(right),
        )
        self.step(
            "On a mistake, add the active input bits to the correct class weights. Raise that class bias by one.",
            Transform(right, matrix([[1, 0, 1]], GREEN, size=30).move_to(right)),
        )
        self.step(
            "Subtract the same input from the mistaken class weights. Lower its bias by one.",
            Transform(wrong, matrix([[-1, 0, -1]], RED, size=30).move_to(wrong)),
        )
        scores = equation("class 0: −3     class 1: +3", [0, -1.8, 0], 32, YELLOW)
        self.step(
            "After this update, the same example favors class one. This illustrates the update rule, not an actual MNIST training sample.",
            Write(scores),
        )
        self.clear_stage()
        panel = code_panel(
            "weights[y][i] += x[i] as i64;\nweights[pred][i] -= x[i] as i64;\n\nbias[y] += 1;\nbias[pred] -= 1;",
            "train/src/mnist.rs · train_perceptron",
            center=(0, 0.8, 0),
            width=12,
        )
        self.step(
            "The Rust trainer applies this rule on mistakes for eight epochs. It is a plain multiclass perceptron.",
            FadeIn(panel),
        )
        q = equation(
            "divide by scale → round → clip to [−3,3]", [0, -1.7, 0], 30, GREEN
        )
        self.step(
            "Quantization shrinks weights to fit the bit-plane circuit. It can change predictions, so the integer model must be evaluated.",
            Write(q),
        )
        self.clear_stage()
        split = (
            VGroup(
                text("50,000 training images", 31, BLUE),
                text("10,000 validation images", 31, YELLOW),
                text("10,000 official test images", 31, GREEN),
            )
            .arrange(DOWN, buff=0.55)
            .move_to([-3.8, 0.5, 0])
        )
        runtime = (
            VGroup(
                text("Rust trains", 30, INK),
                text("JSON stores weights", 30, INK),
                text("Rust emits HTML + CSS", 30, INK),
                text("Browser evaluates fixed weights", 26, ORANGE),
            )
            .arrange(DOWN, buff=0.5)
            .move_to([3.7, 0.5, 0])
        )
        self.step(
            "Training uses fifty thousand images. Ten thousand additional training images are reserved for validation; the official test split is separate.",
            FadeIn(split),
        )
        self.step(
            "Once saved weights are compiled into CSS, drawing does not update them. Browser inference is a forward calculation, not learning.",
            FadeIn(runtime),
        )
        self.step(
            "The larger digit MLP was an unshipped experiment; its trainer has been removed, but the negative result remains in docs/DESIGN_MLP.md. The XOR network above is a separate hidden-layer example.",
            Indicate(runtime[-1], color=ORANGE),
        )

    def chapter_27(self):
        blank = model.predict([0] * 196)
        grid = PixelGrid(14, 3.7).move_to([-4.4, 0.4, 0])
        disp = SevenSegment(1, size=2.6).move_to([4.3, 0.5, 0])
        formula = equation("all pixels = 0 → scores = biases", [0, -1.9, 0], 31, YELLOW)
        self.step(
            "An empty drawing still has scores. Every input product is zero, leaving only the biases.",
            FadeIn(grid),
            FadeIn(disp),
            Write(formula),
        )
        self.step(
            f"Class one has the largest bias, nineteen. The blank canvas therefore chooses {blank.winner}; it did not recognize an invisible digit.",
            Circumscribe(disp, color=YELLOW),
        )
        one = model.predict(model.canvases()["one"])
        self.step(
            "The canonical thin one is misclassified as four. Correct arithmetic does not imply a good prediction on every drawing.",
            grid.change(one.canvas),
            disp.change(one.winner),
            Transform(
                formula,
                equation(
                    "drawn 1 → predicted 4    margin 0", formula.get_center(), 31, RED
                ),
            ),
        )
        self.step(
            "Dilation and reduction lose detail. The runtime also does not crop or center your drawing as the training image pipeline does.",
            Indicate(grid, color=ORANGE),
        )
        self.clear_stage()
        verified = (
            VGroup(
                text("Verified on the actual page", 30, GREEN),
                text("Gate and small arithmetic truth tables", 23, INK),
                text("Covered digit scores and displayed outputs", 23, INK),
                text("Inference with JavaScript disabled and deleted", 23, INK),
            )
            .arrange(DOWN, buff=0.32)
            .move_to([0, 1.3, 0])
        )
        self.step(
            "The audit checks real browser values against independent arithmetic. It also verifies native clicks with page JavaScript disabled and with the script deleted.",
            FadeIn(verified),
        )
        limits = (
            VGroup(
                text("Not an exhaustive proof", 30, YELLOW),
                text("2^196 possible drawings are not all tested.", 23, INK),
                text("MNIST training accuracy was not rerun.", 23, INK),
                text("Historical artifacts were inspected, not all executed.", 23, INK),
            )
            .arrange(DOWN, buff=0.32)
            .move_to([0, -1.05, 0])
        )
        self.step(
            "The recorded 75.42% belongs to the saved model metadata. Glyph acceptance results also influenced development, so those small scores are not untouched tests.",
            FadeIn(limits),
        )
        self.clear_stage()
        path = equation("dist/no-js.html", [0, 1.3, 0], 45, GREEN)
        operation = equation(
            "native click → CSS calculation → output", [0, -0.1, 0], 34, BLUE
        )
        self.step(
            "The new no-js.html export contains no script. It keeps the same 6,834 signal declarations and the same trained weights.",
            Write(path),
            Write(operation),
        )
        self.step(
            "It is still HTML plus CSS, not HTML tags doing arithmetic by themselves. Only smooth drag-to-paint input is removed.",
            Circumscribe(path, color=GREEN),
        )

    def chapter_28(self):
        p = model.predict(model.canvases()["seven"])
        grids = [
            PixelGrid(14, 2.5, p.canvas),
            PixelGrid(14, 2.5, p.dilated, color=YELLOW),
            PixelGrid(7, 2.5, p.features, color=GREEN),
        ]
        for grid, x in zip(grids, (-5.0, 0, 5.0)):
            grid.move_to([x, 0.45, 0])
        labels = [
            text(label, 23, color).move_to([x, 2.3, 0])
            for label, x, color in [
                ("checkbox input", -5, ORANGE),
                ("neighbor OR", 0, YELLOW),
                ("block OR", 5, GREEN),
            ]
        ]
        self.step(
            "Rebuild the path from the input. The drawing is a set of binary checkbox states.",
            FadeIn(grids[0]),
            FadeIn(labels[0]),
        )
        a = Arrow([-3.5, 0.45, 0], [-1.5, 0.45, 0], buff=0.1, color=EDGE)
        self.step(
            "Dilation calculates neighbor ORs from those bits. No image screenshot or JavaScript inference is involved.",
            FadeIn(grids[1]),
            FadeIn(labels[1]),
            GrowArrow(a),
        )
        b = Arrow([1.5, 0.45, 0], [3.5, 0.45, 0], buff=0.1, color=EDGE)
        self.step(
            "Each two-by-two block reduces to one feature bit. The network sees preview reads these same results.",
            FadeIn(grids[2]),
            FadeIn(labels[2]),
            GrowArrow(b),
        )
        self.flow(a, b, seconds=3)
        self.clear_stage()
        features = PixelGrid(7, 3, p.features, color=GREEN).move_to([-5.0, 0.5, 0])
        chart = score_chart(p.scores, width=5.7, height=4.1).move_to([0.2, 0.3, 0])
        display = SevenSegment(7, size=2.8).move_to([5.5, 0.5, 0])
        self.step(
            "The forty-nine features feed ten weighted sums. Each class adds its own bias to its own row of products.",
            FadeIn(features),
            FadeIn(chart),
        )
        self.step(
            "Argmax compares the ten scores. Seven wins this fixture with score twenty-four and margin nineteen.",
            Circumscribe(chart.rows[7], color=YELLOW),
        )
        self.step(
            "The winning index drives minterms and segment ORs. The visible digit is a view of those calculated gate signals.",
            FadeIn(display),
        )
        self.step(
            "HTML supplies input state. CSS describes and evaluates the graph through the browser engine. Rust trains and generates the artifact before runtime.",
            Indicate(features, color=BLUE),
            Indicate(chart, color=GREEN),
            Indicate(display, color=YELLOW),
        )
        self.clear_stage()
        files = (
            VGroup(
                text("Inspect the code alongside the animation", 32, INK),
                text("gen/src/circuit.rs  ·  gates, arithmetic, neurons", 24, BLUE),
                text("gen/src/main.rs  ·  wiring and display mappings", 24, BLUE),
                text("train/src/mnist.rs  ·  learning and preprocessing", 24, BLUE),
                text("docs/STUDY_HANDOFF.md  ·  next-chat knowledge test", 24, YELLOW),
            )
            .arrange(DOWN, buff=0.42)
            .move_to([0, 0.4, 0])
        )
        self.step(
            "The follow-along notes contain these explanations with chapter times. The handoff asks the next chat to test your understanding without assuming mastery.",
            FadeIn(files),
        )
        self.step(
            "The animations were rendered in Manim for teaching. The deployed neural-network inference remains the HTML and CSS artifact you can inspect and test.",
            Circumscribe(files[1], color=BLUE),
        )
