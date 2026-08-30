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
        for name, val in ids.items():
            self.page.set_checked(f"#{name}", bool(val))

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
                 NeuronTests, XorTests):
        cls = type(f"{base.__name__}_{engine}", (base,), {"engine": engine})
        cls.__module__ = __name__
        globals()[cls.__name__] = cls


if __name__ == "__main__":
    unittest.main()
