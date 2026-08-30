"""htmlnet runtime tests — Playwright against the built dist/index.html.

The artifact must be JS-free; the *test harness* may evaluate JS in the page
to read registered custom properties (computed values are real integers
thanks to @property).

Run: make build && python3 -m unittest discover -s tests -v
"""
import os
import subprocess
import sys
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
        self.assertNotIn("<script", lower)
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

    def test_deterministic_rebuild(self):
        import hashlib
        out = subprocess.run([sys.executable, "scripts/generate.py", "/tmp/htmlnet-rebuild.html"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        h1 = hashlib.sha256(open(DIST, "rb").read()).hexdigest()
        h2 = hashlib.sha256(open("/tmp/htmlnet-rebuild.html", "rb").read()).hexdigest()
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
        # same exemplars as scripts/train.py (kept in sync by test, not runtime)
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
                 NeuronTests, XorTests, NativeModeTests, ClassifierTests):
        cls = type(f"{base.__name__}_{engine}", (base,), {"engine": engine})
        cls.__module__ = __name__
        globals()[cls.__name__] = cls


if __name__ == "__main__":
    unittest.main()
