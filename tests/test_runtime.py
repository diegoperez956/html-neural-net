"""htmlnet runtime tests — Playwright against the built dist/index.html.

The artifact must be JS-free; the *test harness* may evaluate JS in the page
to read registered custom properties (computed values are real integers
thanks to @property).

Run: make build && python3 -m unittest discover -s tests -v
"""
import os
import subprocess
import unittest

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "index.html")
URL = "file://" + DIST

ENGINES = ["chromium", "firefox"]


def s2c(v, width):
    """unsigned field -> two's complement int"""
    return v if v < (1 << (width - 1)) else v - (1 << width)


def dec(bits):
    return sum(b << i for i, b in enumerate(bits))


# ---- M13 canvas pipeline reference (mirrors train/src/mnist.rs + the gates) ----

def dilate14(bits):
    """one round of 4-neighbor OR dilation on a flat 14x14 bit list"""
    def g(r, c):
        return bits[r * 14 + c] if 0 <= r < 14 and 0 <= c < 14 else 0
    return [1 if any(g(r + dr, c + dc)
                     for dr, dc in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))) else 0
            for r in range(14) for c in range(14)]


def block_downsample(dilated, threshold):
    """per 2x2 block, popcount >= threshold -> 1 (row-major 7x7, mn{i} order)"""
    out = []
    for br in range(7):
        for bc in range(7):
            cnt = sum(dilated[(2 * br + dr) * 14 + (2 * bc + dc)]
                      for dr in (0, 1) for dc in (0, 1))
            out.append(1 if cnt >= threshold else 0)
    return out


def nn_upscale_2x(bits7):
    """7x7 -> 14x14 nearest-neighbor upscale (each cell fills its 2x2 block)"""
    out = [0] * 196
    for r in range(7):
        for c in range(7):
            v = bits7[r * 7 + c]
            for dr in (0, 1):
                for dc in (0, 1):
                    out[(2 * r + dr) * 14 + (2 * c + dc)] = v
    return out


# hand-picked thin-stroke 14x14 canvases (seven-segment construction, 1 cell
# wide) -- test inputs only; expected outputs always come from the reference
THIN_CANVASES = {
    "one": [
        "..............", "..............", "..........#...", "..........#...",
        "..........#...", "..........#...", "..........#...", "..............",
        "..........#...", "..........#...", "..........#...", "..........#...",
        "..........#...", "..............",
    ],
    "three": [
        "..............", "...########...", "..........#...", "..........#...",
        "..........#...", "..........#...", "..........#...", "...########...",
        "..........#...", "..........#...", "..........#...", "..........#...",
        "..........#...", "...########...",
    ],
    "seven": [
        "..............", "...########...", "..........#...", "..........#...",
        "..........#...", "..........#...", "..........#...", "..............",
        "..........#...", "..........#...", "..........#...", "..........#...",
        "..........#...", "..............",
    ],
}


def rows_to_bits(rows):
    return [1 if ch == "#" else 0 for row in rows for ch in row]


def norm_rgb(serialized):
    """engines serialize color-mix results differently (firefox: rgb(...),
    chromium: color(srgb ...)); normalize to an 8-bit rgb tuple"""
    import re as _re
    nums = [float(v) for v in _re.findall(r"[\d.]+", serialized)[:3]]
    scale = 255 if serialized.startswith("color(") else 1
    return tuple(round(v * scale) for v in nums)


class Base(unittest.TestCase):
    engine = None  # abstract; only per-engine subclasses run

    @classmethod
    def setUpClass(cls):
        if cls.engine is None:
            raise unittest.SkipTest("abstract base")
        cls.pw = sync_playwright().start()
        try:
            cls.browser = getattr(cls.pw, cls.engine).launch(headless=True)
        except Exception as e:
            raise unittest.SkipTest(f"{cls.engine} unavailable: {e}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.goto(URL)

    def tearDown(self):
        self.page.close()

    def set_bits(self, **ids):
        # test-side JS sets form state directly (the artifact itself stays JS-free)
        self.page.evaluate(
            "(ids) => { for (const [n, v] of Object.entries(ids)) "
            "{ const el = document.getElementById(n); el.checked = v; } }",
            ids,
        )

    def read(self, *names):
        props = ",".join(f"'--{n}'" for n in names)
        js = f"""() => {{
            const cs = getComputedStyle(document.body);
            const g = (n) => parseInt(cs.getPropertyValue(n).trim(), 10);
            return [{props}].map(g);
        }}"""
        return self.page.evaluate(js)

    def read_dec(self, names):
        """read a list of bit-signal names as an unsigned integer, LSB first"""
        vals = self.read(*names)
        return dec(vals)


class StaticChecks(Base):
    def test_no_javascript(self):
        html = open(DIST).read()
        lower = html.lower()
        # exactly one <script>: the input shim. Everything else on the page
        # (network computation, display, readouts) stays JS-free.
        self.assertEqual(lower.count("<script"), 1)
        self.assertNotIn("javascript:", lower)
        self.assertNotIn("onclick", lower)
        self.assertNotIn("onchange", lower)
        self.assertNotIn("oninput", lower)
        self.assertNotIn("onload", lower)
        self.assertNotIn("webassembly", lower)
        self.assertNotIn(".wasm", lower)
        self.assertNotIn("http://", lower)
        self.assertNotIn("https://", lower)
        self.assertNotIn("@import", lower)
        self.assertNotIn("src=", lower)
        self.assertNotIn("<link", lower)
        self.assertNotIn("<img", lower)

        i = html.index("<script>")
        j = html.index("</script>")
        script_body = html[i + len("<script>"):j]
        low_body = script_body.lower()
        self.assertLess(len(script_body.encode("utf-8")), 2500, "input shim too large")
        for forbidden in ("fetch", "xmlhttprequest", "websocket", "eval(",
                           "import", "localstorage", "document.cookie", "src="):
            self.assertNotIn(forbidden, low_body, f"shim contains {forbidden!r}")
        self.assertNotIn("Function(", script_body, "shim uses the Function constructor")

    def test_no_operand_pair_lookup_selectors(self):
        """Composition, not enumeration: :has() rules may only map single
        primary input checkboxes; no selector may encode a truth-table row."""
        import re
        html = open(DIST).read()
        has_rules = re.findall(r"body\.rt:has\(([^)]+)\)", html)
        self.assertTrue(has_rules, "expected input mapping rules")
        for rule in has_rules:
            ids = re.findall(r"#[A-Za-z0-9_:-]+", rule)
            self.assertEqual(len(ids), 1, f"multi-input :has rule: {rule}")

    def test_deterministic_rebuild(self):
        import hashlib
        import tempfile
        gen_bin = os.path.join(ROOT, "gen", "target", "release", "htmlnet-gen")
        if not os.path.isfile(gen_bin):
            self.fail(f"{gen_bin} not found — run `make build` first")
        with tempfile.TemporaryDirectory() as tmpdir:
            rebuild_path = os.path.join(tmpdir, "htmlnet-rebuild.html")
            out = subprocess.run([gen_bin, rebuild_path],
                                 cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            h1 = hashlib.sha256(open(DIST, "rb").read()).hexdigest()
            h2 = hashlib.sha256(open(rebuild_path, "rb").read()).hexdigest()
        self.assertEqual(h1, h2, "rebuild is not byte-identical")


class GateTests(Base):
    def test_gates_truth_table(self):
        for a in (0, 1):
            for b in (0, 1):
                self.set_bits(a=a, b=b)
                not_a, and_g, or_g, xor_g = self.read("g_not", "g_and", "g_or", "g_xor")
                self.assertEqual(not_a, 1 - a, f"NOT a={a}")
                self.assertEqual(and_g, a & b, f"AND a={a} b={b}")
                self.assertEqual(or_g, a | b, f"OR a={a} b={b}")
                self.assertEqual(xor_g, a ^ b, f"XOR a={a} b={b}")


class HalfAdderTests(Base):
    def test_all_4_states(self):
        for a in (0, 1):
            for b in (0, 1):
                self.set_bits(a=a, b=b)
                s, c = self.read("ha_sum", "ha_carry")
                self.assertEqual(s, a ^ b)
                self.assertEqual(c, a & b)


class FullAdderTests(Base):
    def test_all_8_states(self):
        for a in (0, 1):
            for b in (0, 1):
                for cin in (0, 1):
                    self.set_bits(a=a, b=b, cin=cin)
                    s, c = self.read("fa_sum", "fa_carry")
                    self.assertEqual(s, (a + b + cin) & 1)
                    self.assertEqual(c, (a + b + cin) >> 1)


class Add2Tests(Base):
    def test_all_16_states(self):
        for a in range(4):
            for b in range(4):
                self.set_bits(a1=a >> 1, a0=a & 1, b1=b >> 1, b0=b & 1)
                s = self.read_dec([f"add2_b{i}_sum" for i in range(3)])
                self.assertEqual(s, a + b, f"a={a} b={b}")


class Mul2Tests(Base):
    def test_all_16_states(self):
        for a in range(4):
            for b in range(4):
                self.set_bits(a1=a >> 1, a0=a & 1, b1=b >> 1, b0=b & 1)
                p = self.read_dec([f"mul2_row1_b{i}_sum" for i in range(4)])
                self.assertEqual(p, a * b, f"a={a} b={b}")


class Add4Tests(Base):
    def test_all_256_states(self):
        for a in range(16):
            for b in range(16):
                bits = {}
                for i in range(4):
                    bits[f"c{i}"] = (a >> i) & 1
                    bits[f"d{i}"] = (b >> i) & 1
                self.set_bits(**bits)
                s = self.read_dec([f"add4_b{i}_sum" for i in range(5)])
                self.assertEqual(s, a + b, f"a={a} b={b}")


class DotTests(Base):
    def test_all_16_states(self):
        for u in range(4):
            for v in range(4):
                self.set_bits(u1=u >> 1, u0=u & 1, v1=v >> 1, v0=v & 1)
                d = self.read_dec([f"dot_sum_b{i}_sum" for i in range(5)])
                expect = (u & 1) * (v & 1) + (u >> 1) * (v >> 1)
                self.assertEqual(d, expect, f"u={u} v={v}")


class MatVecTests(Base):
    def test_all_4_states(self):
        W = [[2, 1], [1, 2]]
        for v1 in (0, 1):
            for v0 in (0, 1):
                self.set_bits(v1=v1, v0=v0)
                r0 = self.read_dec([f"mv_row0_b{i}_sum" for i in range(4)])
                r1 = self.read_dec([f"mv_row1_b{i}_sum" for i in range(4)])
                self.assertEqual(r0, W[0][0] * v1 + W[0][1] * v0)
                self.assertEqual(r1, W[1][0] * v1 + W[1][1] * v0)


class NeuronTests(Base):
    def test_preactivation_and_activation(self):
        for x1 in (0, 1):
            for x0 in (0, 1):
                self.set_bits(x1=x1, x0=x0)
                pre_bits = self.read(*[f"n1_pre_b{i}" for i in range(4)])
                pre = s2c(dec(pre_bits), 4)
                expect = 2 * x1 - 2 * x0 - 1
                self.assertEqual(pre, expect, f"x1={x1} x0={x0}")
                out = self.read("n1_out")[0]
                self.assertEqual(out, 1 if expect >= 0 else 0)


class NativeModeTests(Base):
    """Mode B: same XOR + matvec via direct native CSS arithmetic."""

    def test_xor_all_4_states(self):
        for x1 in (0, 1):
            for x0 in (0, 1):
                self.set_bits(x1=x1, x0=x0)
                nb_h1, nb_h2, nb_out = self.read("nb_h1", "nb_h2", "nb_out")
                h1 = 1 if 2 * x1 - 2 * x0 - 1 >= 0 else 0
                h2 = 1 if 2 * x0 - 2 * x1 - 1 >= 0 else 0
                self.assertEqual(nb_h1, h1)
                self.assertEqual(nb_h2, h2)
                self.assertEqual(nb_out, x1 ^ x0)

    def test_matvec_all_4_states(self):
        for v1 in (0, 1):
            for v0 in (0, 1):
                self.set_bits(v1=v1, v0=v0)
                r0, r1 = self.read("nb_mv0", "nb_mv1")
                self.assertEqual(r0, 2 * v1 + v0)
                self.assertEqual(r1, v1 + 2 * v0)


class ClassifierTests(Base):
    """M10: perceptron-trained 3x3 glyph classifier (top bar vs left bar)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import json
        with open(os.path.join(ROOT, "scripts", "weights.json")) as f:
            w = json.load(f)
        cls.bias = w["bias"]
        cls.weights = w["weights"]

    def ref(self, bits):
        s = self.bias + sum(w * b for w, b in zip(self.weights, bits))
        return s, 1 if s >= 0 else 0

    def check(self, bits, expect_s=None):
        s, out = self.ref(bits)
        if expect_s is not None:
            self.assertEqual(s, expect_s)
        bits_map = {f"g{i}": bits[i] for i in range(9)}
        self.set_bits(**bits_map)
        pre = s2c(dec(self.read(*[f"cls_pre_b{i}" for i in range(5)])), 5)
        got_out = self.read("cls_out")[0]
        self.assertEqual(pre, s, f"preactivation bits={bits}")
        self.assertEqual(got_out, out, f"class bits={bits}")

    def test_training_exemplars(self):
        import json
        # same exemplars as train/src/glyph.rs (kept in sync by test, not runtime)
        exemplars = [
            ([1, 1, 1, 0, 0, 0, 0, 0, 0], 1),
            ([1, 1, 1, 0, 1, 0, 0, 0, 0], 1),
            ([1, 1, 1, 0, 0, 0, 0, 0, 1], 1),
            ([1, 0, 0, 1, 0, 0, 1, 0, 0], 0),
            ([1, 0, 0, 1, 1, 0, 1, 0, 0], 0),
            ([1, 0, 0, 1, 0, 0, 1, 0, 1], 0),
            ([0, 0, 0, 0, 0, 0, 0, 0, 0], 0),
            ([0, 1, 0, 0, 0, 0, 0, 0, 0], 0),
            ([0, 0, 0, 0, 1, 0, 0, 0, 0], 0),
        ]
        for bits, label in exemplars:
            self.check(bits)

    def test_random_states(self):
        import random
        rng = random.Random(42)
        for _ in range(32):
            self.check([rng.randint(0, 1) for _ in range(9)])


class MnistClassifierTests(Base):
    """M13: 14x14 paint canvas -> 4-neighbor OR dilation (dl gates) -> 2x2
    block downsample (mn bits) -> 7x7 linear classifier, argmax'd and
    7-seg decoded. Everything derived from scripts/weights_mnist.json."""

    SEG_MAP = {
        "a": {0, 2, 3, 5, 6, 7, 8, 9}, "b": {0, 1, 2, 3, 4, 7, 8, 9},
        "c": {0, 1, 3, 4, 5, 6, 7, 8, 9}, "d": {0, 2, 3, 5, 6, 8, 9},
        "e": {0, 2, 6, 8}, "f": {0, 4, 5, 6, 8, 9}, "g": {2, 3, 4, 5, 6, 8, 9},
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import json
        with open(os.path.join(ROOT, "scripts", "weights_mnist.json")) as f:
            w = json.load(f)
        cls.weights = w["weights"]
        cls.bias = w["bias"]
        cls.exemplars = w["exemplars"]
        cls.block_threshold = w["block_threshold"]
        cls.canvas = w["canvas"]

    def ref49(self, bits14):
        """canvas -> 49 classifier bits through the gate pipeline reference
        (dilation + block downsample, threshold derived from the JSON)."""
        assert self.canvas == 14
        return block_downsample(dilate14(bits14), self.block_threshold)

    def ref(self, bits49):
        """Independent reference model: score = bias + w.x per class,
        argmax with ties -> lowest digit."""
        scores = [self.bias[k] + sum(self.weights[k][i] * bits49[i] for i in range(49))
                  for k in range(10)]
        best = 0
        for k in range(1, 10):
            if scores[k] > scores[best]:
                best = k
        return scores, best

    def set_canvas(self, bits14):
        self.set_bits(**{f"mc{i}": bits14[i] for i in range(196)})

    def check(self, bits14, label=""):
        scores, best = self.ref(self.ref49(bits14))
        self.set_canvas(bits14)
        idx = self.read_dec([f"mnist_idx_b{i}" for i in range(4)])
        self.assertEqual(idx, best, f"{label} predicted index")
        got_scores = [s2c(self.read_dec([f"mnist_score{k}_b{i}" for i in range(7)]), 7)
                      for k in range(10)]
        self.assertEqual(got_scores, scores, f"{label} per-class scores")
        srt = sorted(scores)
        got_margin = self.read_dec([f"mnist_margin_b{i}" for i in range(8)])
        self.assertEqual(got_margin, srt[-1] - srt[-2], f"{label} margin")
        for k in range(10):
            self.assertEqual(self.read(f"mnist_digit{k}")[0], 1 if k == best else 0,
                              f"{label} minterm {k}")
        for seg, digits in self.SEG_MAP.items():
            expect = 1 if best in digits else 0
            self.assertEqual(self.read(f"mnist_seg_{seg}")[0], expect, f"{label} segment {seg}")

    def test_dilation_and_downsample_gates(self):
        """For hand-picked 14x14 patterns, the 196 dl{} dilation signals and
        the 49 mn{} downsample signals must match the Python-side reference
        (OR-dilation + block popcount >= T, T read from the weights JSON)."""
        patterns = {
            "empty": [0] * 196,
            "single-center": [1 if i == 105 else 0 for i in range(196)],
            "corner": [1 if i == 0 else 0 for i in range(196)],
            "full-row-5": [1 if 5 * 14 <= i < 6 * 14 else 0 for i in range(196)],
            "diagonal": [1 if i % 15 == 0 else 0 for i in range(196)],
            "border-ring": [1 if i // 14 in (0, 13) or i % 14 in (0, 13) else 0
                            for i in range(196)],
        }
        for name, bits14 in patterns.items():
            dilated = dilate14(bits14)
            down = block_downsample(dilated, self.block_threshold)
            self.set_canvas(bits14)
            got_dl = self.read(*[f"dl{i}" for i in range(196)])
            self.assertEqual(got_dl, dilated, f"{name} dilation")
            got_mn = self.read(*[f"mn{i}" for i in range(49)])
            self.assertEqual(got_mn, down, f"{name} downsample")

    def test_thin_stroke_canvases(self):
        for name, rows in THIN_CANVASES.items():
            self.check(rows_to_bits(rows), f"thin {name}")

    def test_upscaled_exemplar_canvases(self):
        # each stored 49-bit exemplar, routed through a 2x nn upscale onto the
        # canvas -- the reference recomputes what dilation + downsample make
        # of it (dilation can leak ink across block boundaries), so this
        # checks the whole chain rather than the stored bits verbatim.
        for k in range(10):
            self.check(nn_upscale_2x(self.exemplars[str(k)]), f"exemplar {k} upscaled")

    def test_random_canvases(self):
        import random
        rng = random.Random(0)
        for t in range(10):
            bits = [1 if rng.random() < 0.3 else 0 for _ in range(196)]
            self.check(bits, f"random {t}")


class DisplayTests(Base):
    """The rendered decimal views must actually resolve (adversarial BLOCK-1)."""

    def counter_reset(self, cls):
        return self.page.evaluate(
            "(cls) => getComputedStyle(document.querySelector(cls), '::after').counterReset",
            f".{cls}",
        )

    def assert_view(self, cls, expect_int):
        got = self.counter_reset(cls)
        self.assertEqual(got, f"v {expect_int}", f".{cls}::after rendered counter")

    def test_adder_and_multiplier_views(self):
        self.set_bits(a1=1, a0=0, b1=1, b0=1)          # a=2, b=3
        self.assert_view("d_add2", 5)
        self.assert_view("d_mul2", 6)

    def test_add4_view(self):
        bits = {f"c{i}": (10 >> i) & 1 for i in range(4)}
        bits.update({f"d{i}": (5 >> i) & 1 for i in range(4)})
        self.set_bits(**bits)
        self.assert_view("d_add4", 15)

    def test_dot_view(self):
        self.set_bits(u1=1, u0=0, v1=1, v0=0)          # u=2, v=2 -> 0*0 + 1*1
        self.assert_view("d_dot", 1)

    def test_matvec_views(self):
        self.set_bits(v1=1, v0=0)
        self.assert_view("d_mv0", 2)
        self.assert_view("d_mv1", 1)
        self.assert_view("d_nb_mv0", 2)
        self.assert_view("d_nb_mv1", 1)

    def test_neuron_and_xor_views(self):
        self.set_bits(x1=1, x0=0)
        self.assert_view("d_npre", 1)
        self.assert_view("d_xor", 1)
        self.assert_view("d_nb_out", 1)

    def test_negative_view(self):
        self.set_bits(x1=0, x0=1)
        self.assert_view("d_npre", -3)

    def test_classifier_view(self):
        self.set_bits(g0=1, g1=1, g2=1)                # top bar -> class 1
        self.assert_view("d_clspre", 1)

    def test_ax_tree_has_rendered_digits(self):
        self.set_bits(a1=1, a0=0, b1=1, b0=1)          # 5 and 6 rendered
        snap = self.page.locator("body").aria_snapshot()
        self.assertIn("5", snap)
        self.assertIn("6", snap)

    def test_mnist_views(self):
        import json
        with open(os.path.join(ROOT, "scripts", "weights_mnist.json")) as f:
            w = json.load(f)
        bits14 = rows_to_bits(THIN_CANVASES["seven"])
        bits49 = block_downsample(dilate14(bits14), w["block_threshold"])
        self.set_bits(**{f"mc{i}": bits14[i] for i in range(196)})
        # Per-class scores derived from the JSON + the pipeline reference
        # (not hardcoded) -- this test is meant to stay valid across
        # retrains, same as MnistClassifierTests.
        sc = [w["bias"][k] + sum(w["weights"][k][i] * bits49[i] for i in range(49))
              for k in range(10)]
        best = max(range(10), key=lambda k: (sc[k], -k))
        self.assert_view("d_mnist_digit", best)
        for k in range(10):
            self.assert_view(f"d_mnist_score{k}", sc[k])
        srt = sorted(sc)
        self.assert_view("d_mnist_margin", srt[-1] - srt[-2])

    def test_digit_strip_highlight(self):
        import json
        with open(os.path.join(ROOT, "scripts", "weights_mnist.json")) as f:
            w = json.load(f)
        bits14 = rows_to_bits(THIN_CANVASES["three"])
        bits49 = block_downsample(dilate14(bits14), w["block_threshold"])
        self.set_bits(**{f"mc{i}": bits14[i] for i in range(196)})
        sc = [w["bias"][k] + sum(w["weights"][k][i] * bits49[i] for i in range(49))
              for k in range(10)]
        best = 0
        for k in range(1, 10):
            if sc[k] > sc[best]:
                best = k
        other = (best + 1) % 10

        def color(cls):
            return norm_rgb(self.page.evaluate(
                "(cls) => getComputedStyle(document.querySelector(cls)).color", cls))

        self.assertEqual(color(f".l_mn_digit_{best}"), (250, 189, 47),
                         f".l_mn_digit_{best} lit")
        self.assertEqual(color(f".l_mn_digit_{other}"), (124, 111, 100),
                         f".l_mn_digit_{other} unlit")

    def test_network_sees_preview(self):
        """rendered-output check of the 'network sees' 7x7 preview: each px
        cell reads the POST-downsample mn{i} gate signal (pure CSS color-mix
        readout), lit orange when the bit is 1, canvas-dark when 0."""
        import json
        with open(os.path.join(ROOT, "scripts", "weights_mnist.json")) as f:
            w = json.load(f)
        bits14 = rows_to_bits(THIN_CANVASES["three"])
        bits49 = block_downsample(dilate14(bits14), w["block_threshold"])
        self.set_bits(**{f"mc{i}": bits14[i] for i in range(196)})
        for i in range(49):
            got = norm_rgb(self.page.evaluate(
                "(cls) => getComputedStyle(document.querySelector(cls)).backgroundColor",
                f".px_{i}"))
            expect = (254, 128, 25) if bits49[i] else (29, 32, 33)
            self.assertEqual(got, expect, f"preview cell {i}")

    def test_canvas_idle_and_blob(self):
        """paint-feel canvas (computed style, not screenshots): idle cells
        draw no visible border/grid, and a checked cell renders its oversized
        rounded ink blob, kept out of pointer hit-testing."""
        def cell_style(sel, pseudo=None):
            return self.page.evaluate(
                "(a) => { const el = document.querySelector(a.sel);"
                "const s = getComputedStyle(el, a.pseudo || null);"
                "return {border: s.borderTopStyle, bw: s.borderTopWidth,"
                "shadow: s.boxShadow, bg: s.backgroundColor,"
                "content: s.content, r: s.borderRadius, w: s.width,"
                "pe: s.pointerEvents}; }",
                {"sel": sel, "pseudo": pseudo})

        for i in (0, 97, 195):
            s = cell_style(f".grid14 label:nth-child({i + 1})")
            self.assertIn(s["border"], ("none", ""), f"cell {i} border")
            self.assertEqual(s["bw"], "0px", f"cell {i} border width")
            self.assertEqual(s["shadow"], "none", f"cell {i} box-shadow")
            self.assertEqual(s["bg"], "rgba(0, 0, 0, 0)", f"cell {i} background")

        # unchecked cell: no blob pseudo-element at all
        idle_after = cell_style(".grid14 label:nth-child(1)", "::after")
        self.assertEqual(idle_after["content"], "none", "unchecked cell must have no blob")

        # checked cell: oversized rounded orange blob, pointer-transparent
        self.set_bits(mc97=1)
        blob = cell_style(".grid14 label:nth-child(98)", "::after")
        self.assertEqual(blob["content"], '""', "checked cell renders a blob")
        self.assertEqual(norm_rgb(blob["bg"]), (254, 128, 25), "blob ink color")
        self.assertEqual(blob["r"], "50%", "blob is round")
        self.assertGreaterEqual(float(blob["w"].rstrip("px")), 38.0,
                                "blob must be oversized vs the 24px cell pitch")
        self.assertEqual(blob["pe"], "none", "blob must not intercept pointer events")


class DragShimTests(Base):
    """Rendered behavior of the input shim's <script> tag: pointer drags
    must paint canvas checkboxes the same way clicks do. The network +
    display stay pure CSS -- this only exercises the shim's event wiring."""

    def fire(self, elem_id, event_type, pointer_id=1):
        self.page.evaluate(
            "(a) => { document.getElementById(a.id).dispatchEvent("
            "new PointerEvent(a.type, {bubbles: true, cancelable: true, "
            "pointerId: a.pid, button: 0})); }",
            {"id": elem_id, "type": event_type, "pid": pointer_id},
        )

    def click_event(self, elem_id):
        self.page.evaluate(
            "(id) => document.getElementById(id).dispatchEvent("
            "new MouseEvent('click', {bubbles: true, cancelable: true}))",
            elem_id,
        )

    def checked(self, *ids):
        return self.page.evaluate(
            "(ids) => ids.map((i) => document.getElementById(i).checked)", list(ids)
        )

    def drag(self, down_id, *over_ids):
        self.fire(down_id, "pointerdown")
        for i in over_ids:
            self.fire(i, "pointerover")
        self.page.evaluate(
            "() => window.dispatchEvent(new PointerEvent('pointerup', {pointerId: 1}))"
        )
        # the pointerdown cell also receives a click after release, as a real
        # drag would -- the shim must suppress its default (no double-toggle)
        self.click_event(down_id)

    def test_drag_paints_three_cells(self):
        self.drag("mc0", "mc1", "mc2")
        self.assertEqual(self.checked("mc0", "mc1", "mc2"), [True, True, True])
        self.assertEqual(self.read("mc0", "mc1", "mc2"), [1, 1, 1])

    def test_second_pointerdown_erases(self):
        self.drag("mc0", "mc1", "mc2")
        # cell is now checked; a fresh pointerdown on it must erase, not paint
        self.fire("mc0", "pointerdown")
        self.assertEqual(self.checked("mc0"), [False])
        self.assertEqual(self.checked("mc1", "mc2"), [True, True])

    def test_plain_click_still_toggles_untouched_cell(self):
        # no-shim / keyboard path parity: a bare .click() (no pointer events
        # at all) still toggles a cell the drag never touched.
        self.assertEqual(self.checked("mc195"), [False])
        self.page.evaluate("() => document.getElementById('mc195').click()")
        self.assertEqual(self.checked("mc195"), [True])
        self.assertEqual(self.read("mc195"), [1])


class XorTests(Base):
    def test_all_4_states_with_intermediates(self):
        for x1 in (0, 1):
            for x0 in (0, 1):
                self.set_bits(x1=x1, x0=x0)
                h1p = s2c(dec(self.read(*[f"xor_h1_pre_b{i}" for i in range(4)])), 4)
                h2p = s2c(dec(self.read(*[f"xor_h2_pre_b{i}" for i in range(4)])), 4)
                h1, h2 = self.read("xor_h1_out", "xor_h2_out")
                self.assertEqual(h1p, 2 * x1 - 2 * x0 - 1)
                self.assertEqual(h2p, -2 * x1 + 2 * x0 - 1)
                self.assertEqual(h1, 1 if h1p >= 0 else 0)
                self.assertEqual(h2, 1 if h2p >= 0 else 0)
                out = self.read("xor_out_out")[0]
                self.assertEqual(out, x1 ^ x0, f"XOR({x1},{x0})")


# per-engine variants
def engine_case(name, engine):
    attrs = {"engine": engine}
    return type(name, (object,), attrs)


for engine in ENGINES:
    for base in (StaticChecks, GateTests, HalfAdderTests, FullAdderTests,
                 Add2Tests, Mul2Tests, Add4Tests, DotTests, MatVecTests,
                 NeuronTests, XorTests, NativeModeTests, ClassifierTests,
                 MnistClassifierTests, DisplayTests, DragShimTests):
        cls = type(f"{base.__name__}_{engine}", (base,), {"engine": engine})
        cls.__module__ = __name__
        globals()[cls.__name__] = cls


if __name__ == "__main__":
    unittest.main()
