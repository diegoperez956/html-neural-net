#!/usr/bin/env python3
"""htmlnet demo generator. Build-time only; output is HTML+CSS with zero JS.

Usage: python3 scripts/generate.py [out.html]
"""
import os
import sys
from circuit import Circuit, Net, ref, render

BASE_CSS = """
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 48px 24px; background: #0b0e14; color: #cfe3ff;
    font: 15px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  .wrap { max-width: 680px; margin: 0 auto; }
  h1 { font-size: 21px; margin: 0 0 6px; }
  .sub { color: #7d8fa9; font-size: 13px; margin: 0 0 32px; max-width: 54ch; }
  .stage { display: flex; gap: 56px; align-items: center; flex-wrap: wrap; margin-bottom: 44px; }

  /* the drawing box: one canvas, not 49 widgets */
  .pad { display: flex; flex-direction: column; gap: 14px; }
  .grid7 {
    display: grid; grid-template-columns: repeat(7, 42px); grid-auto-rows: 42px;
    border: 1px solid #1e2a3d; border-radius: 12px; overflow: hidden;
    background: #0d1320; cursor: crosshair; touch-action: manipulation;
  }
  .cell7 { position: relative; box-shadow: inset 0 0 0 1px #38ff8c0d;
           transition: background .1s ease, box-shadow .1s ease; }
  .cell7:hover { background: #38ff8c17; }
  .cell7:active { background: #38ff8c2e; }
  .cell7:has(input:checked) {
    background: #38ff8cd9;
    box-shadow: inset 0 0 0 1px #38ff8c59, inset 0 0 12px #38ff8c26;
  }
  .cell7 input { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: crosshair; }
  .cell7:has(input:focus-visible) { outline: 2px solid #38ff8c; outline-offset: -2px; z-index: 1; }
  input[type="reset"] {
    align-self: flex-start; background: none; color: #7d8fa9; border: 1px solid #1e2a3d;
    border-radius: 999px; padding: 5px 16px; cursor: pointer; font: inherit; font-size: 13px;
  }
  input[type="reset"]:hover { color: #cfe3ff; border-color: #38ff8c80; }

  /* the answer: wakes up when the box has ink */
  .guess { display: flex; flex-direction: column; align-items: center; gap: 18px;
           opacity: .3; transition: opacity .25s ease; }
  .stage:has(.grid7 input:checked) .guess { opacity: 1; }
  .digit7 { position: relative; width: 90px; height: 150px; }
  .seg { position: absolute; background: #17202f; border-radius: 3px; transition: background .18s ease; }
  .seg-a { top: 0; left: 12px; width: 66px; height: 12px; }
  .seg-b { top: 9px; right: 0; width: 12px; height: 66px; }
  .seg-c { bottom: 9px; right: 0; width: 12px; height: 66px; }
  .seg-d { bottom: 0; left: 12px; width: 66px; height: 12px; }
  .seg-e { bottom: 9px; left: 0; width: 12px; height: 66px; }
  .seg-f { top: 9px; left: 0; width: 12px; height: 66px; }
  .seg-g { top: 69px; left: 12px; width: 66px; height: 12px; }
  .mn-digits { display: flex; gap: 9px; font-size: 17px; }
  .meter { width: 122px; height: 6px; border-radius: 3px; background: #17202f; overflow: hidden; }
  .meter-fill { height: 100%; background: #38ff8c;
                width: calc(min(100, var(--mnist_margin_dec) * 4) * 1%);
                transition: width .18s ease; }

  /* under the hood: the whole composition ladder, opt-in */
  details.hood { border-top: 1px solid #1e2a3d; padding-top: 18px; }
  details.hood summary {
    cursor: pointer; color: #5f7190; font-size: 13px; list-style: none;
    display: inline-flex; align-items: center; gap: 8px; user-select: none;
  }
  details.hood summary::-webkit-details-marker { display: none; }
  details.hood summary::before { content: "+"; color: #38ff8c; font-size: 15px; }
  details.hood[open] summary::before { content: "−"; }
  details.hood summary:hover { color: #cfe3ff; }

  h2 { font-size: 16px; margin: 28px 0 8px; border-top: 1px solid #1e2a3d; padding-top: 14px; }
  .row { margin: 4px 0; }
  label { display: inline-flex; gap: 6px; align-items: center; margin-right: 14px; }
  input[type="checkbox"] { accent-color: #38ff8c; width: 15px; height: 15px; }
  .led { display: inline-block; width: 11px; height: 11px; margin: 0 1px; border-radius: 2px;
         background: #223; vertical-align: middle; }
  .bits { display: inline-flex; gap: 2px; align-items: center; margin-right: 8px; }
  .v { color: #7CFC9B; }
  .tag { color: #5f7190; font-size: 12px; }
  .kbd { color: #8fa8c8; }
  .ladder { color: #38ff8c; font-size: 13px; letter-spacing: 1px; margin: 18px 0; }
  .ladder .dim { color: #5f7190; }
  input[type="checkbox"]:focus-visible { outline: 2px solid #38ff8c; outline-offset: 2px; }
  section:focus-within h2 { color: #7CFC9B; }
  .caption { color: #4c5f7a; font-size: 11px; }
  footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid #1e2a3d; }
  .grid { display: grid; grid-template-columns: repeat(3, 34px); gap: 6px; margin: 8px 0; }
  .cell { display: flex; align-items: center; justify-content: center; width: 34px; height: 34px; border: 1px solid #223; border-radius: 4px; cursor: pointer; }
  .cell:has(input:checked) { border-color: #38ff8c; box-shadow: 0 0 6px #38ff8c55 inset; }
  .cell input { position: absolute; opacity: 0; width: 0; height: 0; }
  .cell:has(input:focus-visible) { outline: 2px solid #38ff8c; outline-offset: 2px; }
  @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
"""


def led_css(signal: str, cls: str) -> str:
    return (
        f'.{cls} {{ background: color-mix(in srgb, #38ff8c, #101826 '
        f'calc((1 - var(--{signal})) * 100%)); }}'
    )


def text_led_css(signal: str, cls: str) -> str:
    """Same LED color-mix technique as led_css, applied to text color instead
    of background -- used to highlight the predicted digit in the 0-9 strip."""
    return (
        f'.{cls} {{ color: color-mix(in srgb, #38ff8c, #4c5f7a '
        f'calc((1 - var(--{signal})) * 100%)); }}'
    )


def dec_css(bits, cls: str, sig: str) -> str:
    """Native-calc decimal VIEW (labeled, display only). bits: bare signal names LSB first.
    The value is materialized as registered signal --{sig} (testable via computed style)
    and rendered via one clean var() into a counter."""
    terms = " + ".join(f"({2 ** i} * var(--{b}))" for i, b in enumerate(bits))
    return (f'.{cls}::after {{ counter-reset: v var(--{sig}); content: counter(v); }}')


def main(path):
    c = Circuit()
    n = Net(c)

    # ---------------- 1. primary bits x1, x0 (master XOR pair) -------------
    # ---------------- 2. gates: a, b toggles ---------------------------------
    inputs = ["x1", "x0", "a", "b", "cin",
              "a1", "a0", "b1", "b0",
              "c3", "c2", "c1", "c0", "d3", "d2", "d1", "d0",
              "u1", "u0", "v1", "v0"] + [f"g{i}" for i in range(9)] \
             + [f"mn{i}" for i in range(49)]
    for name in inputs:
        c.emit(name, "0")  # placeholder; overridden by :has rules

    not_a = c.gate("NOT", ref("a"), name="g_not")
    and_g = c.gate("AND", ref("a"), ref("b"), name="g_and")
    or_g = c.gate("OR", ref("a"), ref("b"), name="g_or")
    xor_g = c.gate("XOR", ref("a"), ref("b"), name="g_xor")

    # half adder (M2)
    ha_s, ha_c = c.half_adder("ha", ref("a"), ref("b"))
    # full adder (M3)
    fa_s, fa_c = c.full_adder("fa", ref("a"), ref("b"), ref("cin"))

    # 2-bit adder + 2x2 multiplier (M4/M5)
    s2 = c.ripple_add("add2", [ref("a0"), ref("a1"), "0"], [ref("b0"), ref("b1"), "0"], "0")
    p2 = c.unsigned_mult("mul2", [ref("a0"), ref("a1")], [ref("b0"), ref("b1")])

    # 4-bit adder (M4 exhaustively testable)
    s4 = c.ripple_add("add4",
                      [ref("c0"), ref("c1"), ref("c2"), ref("c3"), "0"],
                      [ref("d0"), ref("d1"), ref("d2"), ref("d3"), "0"], "0")

    # dot product of two 2-bit vectors u = (u1,u0), v = (v1,v0): u0*v0 + u1*v1
    p_u0v0 = c.unsigned_mult("d_u0v0", [ref("u0")], [ref("v0")])          # 1 bit
    p_u1v1 = c.unsigned_mult("d_u1v1", [ref("u1")], [ref("v1")])          # 1 bit
    dot_bits = c.ripple_add("dot_sum",
                            p_u0v0 + ["0", "0", "0", "0"],
                            p_u1v1 + ["0", "0", "0", "0"],
                            "0")

    # matrix x vector: fixed W = [[2,1],[1,2]] x [v1,v0] -> two outputs.
    # weight x input = gate-masked magnitude bits (wiring), row = ripple sum.
    def row_of(name, wx1, wx0, x1name, x0name):
        def mask(v):
            return [str((v >> i) & 1) for i in range(4)]
        t1 = [c.gate("AND", m, ref(x1name), name=f"{name}_t0_{j}")
              for j, m in enumerate(mask(wx1))]  # wx1*x1
        t0 = [c.gate("AND", m, ref(x0name), name=f"{name}_t1_{j}")
              for j, m in enumerate(mask(wx0))]  # wx0*x0
        return c.ripple_add(name, t1, t0, "0")

    row0 = row_of("mv_row0", 2, 1, "v1", "v0")
    row1 = row_of("mv_row1", 1, 2, "v1", "v0")

    # neuron (h1 of the XOR net) + full XOR MLP with stable test aliases
    n_out, n_pre = n.neuron("n1", [+2, -2], [-1], [ref("x1"), ref("x0")])
    for i, b in enumerate(n_pre):
        c.emit(f"n1_pre_b{i}", ref(b))

    h1, h1_pre = n.neuron("xor_h1", [+2, -2], [-1], [ref("x1"), ref("x0")])
    h2, h2_pre = n.neuron("xor_h2", [-2, +2], [-1], [ref("x1"), ref("x0")])
    out, out_pre = n.neuron("xor_out", [+2, +2], [-1], [ref(h1), ref(h2)])
    for tag, pre in (("h1", h1_pre), ("h2", h2_pre), ("out", out_pre)):
        for i, b in enumerate(pre):
            c.emit(f"xor_{tag}_pre_b{i}", ref(b))

    # ---------------- trained classifier (M10) ------------------------------
    import json as _json
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights.json")) as f:
        trained = _json.load(f)
    cls_bias = trained["bias"]
    cls_weights = trained["weights"]
    cls_inputs = [ref(f"g{i}") for i in range(9)]
    cls_out, cls_pre = n.neuron("cls", cls_weights, [cls_bias], cls_inputs, swidth=5)
    for i, b in enumerate(cls_pre):
        c.emit(f"cls_pre_b{i}", ref(b))

    # ---------------- M11: drawn-digit MNIST classifier ---------------------
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights_mnist.json")) as f:
        mnist = _json.load(f)
    mnist_weights, mnist_bias = mnist["weights"], mnist["bias"]
    mnist_test_acc = mnist["test_accuracy"]
    mnist_inputs = [ref(f"mn{i}") for i in range(49)]

    SCORE_W = 7
    mnist_scores = []
    for k in range(10):
        raw = n.weighted_score(f"mnist_c{k}", mnist_weights[k], mnist_bias[k],
                                mnist_inputs, width=SCORE_W)
        bits = [c.emit(f"mnist_score{k}_b{i}", ref(b)) for i, b in enumerate(raw)]
        mnist_scores.append(bits)

    mnist_idx_raw, _mnist_maxscore, mnist_margin_raw = c.argmax("mnist_argmax", mnist_scores)
    mnist_idx = [c.emit(f"mnist_idx_b{i}", ref(b)) for i, b in enumerate(mnist_idx_raw)]
    mnist_margin = [c.emit(f"mnist_margin_b{i}", ref(b)) for i, b in enumerate(mnist_margin_raw)]

    mnist_minterms_raw = c.digit_minterms("mnist_mt", mnist_idx)
    mnist_minterms = [c.emit(f"mnist_digit{k}", ref(m)) for k, m in enumerate(mnist_minterms_raw)]

    mnist_segs_raw = c.sevenseg("mnist_seg", mnist_minterms)
    mnist_segs = [c.emit(f"mnist_seg_{letter}", ref(b))
                  for letter, b in zip("abcdefg", mnist_segs_raw)]

    # ---------------- Mode B: native CSS arithmetic (comparison baseline) ---
    # var() * var() is illegal in CSS, so native mode only works where weights
    # are literal constants — which is exactly the neural-inference case here.
    for sig, expr in {
        "nb_h1pre": "calc((2 * var(--x1)) - (2 * var(--x0)) - 1)",
        "nb_h1": "max(0, min(1, calc(var(--nb_h1pre) + 1)))",
        "nb_h2pre": "calc((2 * var(--x0)) - (2 * var(--x1)) - 1)",
        "nb_h2": "max(0, min(1, calc(var(--nb_h2pre) + 1)))",
        "nb_outpre": "calc((2 * var(--nb_h1)) + (2 * var(--nb_h2)) - 1)",
        "nb_out": "max(0, min(1, calc(var(--nb_outpre) + 1)))",
        "nb_mv0": "calc((2 * var(--v1)) + (1 * var(--v0)))",
        "nb_mv1": "calc((1 * var(--v1)) + (2 * var(--v0)))",
    }.items():
        c.emit(sig, expr)

    # ---------------- CSS ----------------------------------------------------
    led_css_all = "\n".join([
        led_css("g_not", "l_not"), led_css("g_and", "l_and"),
        led_css("g_or", "l_or"), led_css("g_xor", "l_xor"),
        led_css(ha_s, "l_ha_s"), led_css(ha_c, "l_ha_c"),
        led_css(fa_s, "l_fa_s"), led_css(fa_c, "l_fa_c"),
        *[led_css(s, f"l_add2_{i}") for i, s in enumerate(s2)],
        *[led_css(p, f"l_mul2_{i}") for i, p in enumerate(p2)],
        *[led_css(s, f"l_add4_{i}") for i, s in enumerate(s4)],
        *[led_css(b, f"l_dot_{i}") for i, b in enumerate(dot_bits)],
        *[led_css(b, f"l_mv0_{i}") for i, b in enumerate(row0)],
        *[led_css(b, f"l_mv1_{i}") for i, b in enumerate(row1)],
        led_css(n_out, "l_n_out"),
        *[led_css(b, f"l_npre_{i}") for i, b in enumerate(n_pre)],
        led_css(h1, "l_h1"), led_css(h2, "l_h2"), led_css(out, "l_xor_out"),
        led_css("nb_h1", "l_nb_h1"), led_css("nb_h2", "l_nb_h2"), led_css("nb_out", "l_nb_out"),
        led_css(cls_out, "l_cls_out"),
        *[led_css(b, f"l_clspre_{i}") for i, b in enumerate(cls_pre)],
        *[led_css(b, f"l_mn_seg_{letter}") for letter, b in zip("abcdefg", mnist_segs)],
        *[text_led_css(m, f"l_mn_digit_{k}") for k, m in enumerate(mnist_minterms)],
    ])
    # decimal view signals: native-calc conversions materialized as registered
    # properties (display-only; testable via computed style). (bits, signed)
    # -- signed views put the -2**(width-1) sign-bit coefficient on the MSB.
    dec_specs = {
        "add2_dec": (s2, False), "mul2_dec": (p2, False), "add4_dec": (s4, False),
        "dot_dec": (dot_bits, False), "mv0_dec": (row0, False), "mv1_dec": (row1, False),
        "npre_dec": (n_pre, True), "xor_dec": ([out], False),
        "nb_h1pre_dec": (["nb_h1pre"], False), "nb_h2pre_dec": (["nb_h2pre"], False),
        "nb_outpre_dec": (["nb_outpre"], False), "nb_out_dec": (["nb_out"], False),
        "nb_mv0_dec": (["nb_mv0"], False), "nb_mv1_dec": (["nb_mv1"], False),
        "clspre_dec": (cls_pre, True),
        **{f"mnist_score{k}_dec": (mnist_scores[k], True) for k in range(10)},
        "mnist_digit_dec": (mnist_idx, False),
        "mnist_margin_dec": (mnist_margin, False),
    }
    for sig, (bits, signed) in dec_specs.items():
        terms = " + ".join(
            f"({(-(2 ** i) if (signed and i == len(bits) - 1) else 2 ** i)} * var(--{b}))"
            for i, b in enumerate(bits)
        )
        c.emit(sig, f"calc({terms})")

    dec_css_all = "\n".join([
        dec_css([s for s in s2], "d_add2", "add2_dec"),
        dec_css([p for p in p2], "d_mul2", "mul2_dec"),
        dec_css([s for s in s4], "d_add4", "add4_dec"),
        dec_css([b for b in dot_bits], "d_dot", "dot_dec"),
        dec_css([b for b in row0], "d_mv0", "mv0_dec"),
        dec_css([b for b in row1], "d_mv1", "mv1_dec"),
        dec_css([b for b in n_pre], "d_npre", "npre_dec"),
        dec_css([out], "d_xor", "xor_dec"),
        dec_css(["nb_h1pre"], "d_nb_h1pre", "nb_h1pre_dec"),
        dec_css(["nb_h2pre"], "d_nb_h2pre", "nb_h2pre_dec"),
        dec_css(["nb_outpre"], "d_nb_outpre", "nb_outpre_dec"),
        dec_css(["nb_out"], "d_nb_out", "nb_out_dec"),
        dec_css(["nb_mv0"], "d_nb_mv0", "nb_mv0_dec"),
        dec_css(["nb_mv1"], "d_nb_mv1", "nb_mv1_dec"),
        dec_css([b for b in cls_pre], "d_clspre", "clspre_dec"),
        *[dec_css(mnist_scores[k], f"d_mnist_score{k}", f"mnist_score{k}_dec") for k in range(10)],
        dec_css(mnist_idx, "d_mnist_digit", "mnist_digit_dec"),
        dec_css(mnist_margin, "d_mnist_margin", "mnist_margin_dec"),
    ])

    input_css = "\n".join(
        f"body.rt:has(#{name}:checked) {{ --{name}: 1; }}" for name in inputs
    )

    extra = BASE_CSS + "\n" + input_css + "\n" + led_css_all + "\n" + dec_css_all

    def leds(cls, nbits):
        return "".join(f'<span class="led {cls}_{i}"></span>' for i in range(nbits))

    n_signals = len(c.signals)
    body = f"""
<main class="wrap">
<h1>draw a digit</h1>
<p class="sub">a neural network running entirely in HTML + CSS, zero JavaScript. trained on MNIST at build time, compiled into logic gates. paint cells in the box; the display reads the network's answer.</p>

<div class="stage">
  <form class="pad">
    <div class="grid7" role="group" aria-label="7 by 7 drawing box">
      {"".join(f'<label class="cell7"><input type="checkbox" id="mn{i}" aria-label="cell {i // 7},{i % 7}"></label>' for i in range(49))}
    </div>
    <input type="reset" value="clear">
  </form>
  <div class="guess">
    <div class="digit7" role="img" aria-label="predicted digit">
      <div class="seg seg-a l_mn_seg_a"></div>
      <div class="seg seg-b l_mn_seg_b"></div>
      <div class="seg seg-c l_mn_seg_c"></div>
      <div class="seg seg-d l_mn_seg_d"></div>
      <div class="seg seg-e l_mn_seg_e"></div>
      <div class="seg seg-f l_mn_seg_f"></div>
      <div class="seg seg-g l_mn_seg_g"></div>
    </div>
    <div class="mn-digits" role="group" aria-label="lit digit indicator">
      {"".join(f'<span class="l_mn_digit_{k}">{k}</span>' for k in range(10))}
    </div>
    <div class="meter" role="img" aria-label="confidence"><div class="meter-fill"></div></div>
  </div>
</div>

<details class="hood">
<summary>under the hood: checkbox state → bits → gates → adders → multipliers → neurons → this classifier</summary>
<div class="ladder">checkbox state <span class="dim">→</span> bits <span class="dim">→</span> gates <span class="dim">→</span> adders <span class="dim">→</span> multiplication <span class="dim">→</span> dot product <span class="dim">→</span> matrix×vector <span class="dim">→</span> neurons <span class="dim">→</span> XOR MLP</div>

<section>
  <h2>1 · input bits</h2>
  <div class="row"><label><input type="checkbox" id="x1"> x1</label>
  <label><input type="checkbox" id="x0"> x0</label>
  <span class="tag">— shared inputs for the neuron and XOR network below</span></div>
</section>

<section>
  <h2>2 · logic gates (truth-table verified)</h2>
  <div class="row"><label><input type="checkbox" id="a"> a</label>
  <label><input type="checkbox" id="b"> b</label></div>
  <div class="row"><span class="kbd">NOT a</span> <span class="led l_not"></span> <span class="tag">= 1−a</span></div>
  <div class="row"><span class="kbd">a AND b</span> <span class="led l_and"></span> <span class="tag">= min(a,b)</span></div>
  <div class="row"><span class="kbd">a OR b</span> <span class="led l_or"></span> <span class="tag">= max(a,b)</span></div>
  <div class="row"><span class="kbd">a XOR b</span> <span class="led l_xor"></span> <span class="tag">= max(a,b)−min(a,b)</span></div>
</section>

<section>
  <h2>3 · half adder (uses a, b above)</h2>
  <div class="row"><span class="kbd">sum</span> <span class="led l_ha_s"></span>
  <span class="kbd">carry</span> <span class="led l_ha_c"></span>
  <span class="tag">sum = a⊕b, carry = a∧b</span></div>
</section>

<section>
  <h2>4 · full adder</h2>
  <div class="row"><label><input type="checkbox" id="cin"> carry-in</label>
  <span class="tag">(a, b shared)</span></div>
  <div class="row"><span class="kbd">sum</span> <span class="led l_fa_s"></span>
  <span class="kbd">carry-out</span> <span class="led l_fa_c"></span>
  <span class="tag">2 XOR + 2 AND + 1 OR, connected by named wires</span></div>
</section>

<section>
  <h2>5 · 2-bit adder and 2×2 multiplier</h2>
  <div class="row">
    <label><input type="checkbox" id="a1"> a1</label>
    <label><input type="checkbox" id="a0"> a0</label>
    <label><input type="checkbox" id="b1"> b1</label>
    <label><input type="checkbox" id="b0"> b0</label>
  </div>
  <div class="row"><span class="kbd">a + b =</span> <span class="bits">{leds('l_add2', 3)}</span>
  <span class="v d_add2"></span> <span class="caption">4·2·1</span></div>
  <div class="row"><span class="kbd">a × b =</span> <span class="bits">{leds('l_mul2', 4)}</span>
  <span class="v d_mul2"></span> <span class="caption">8·4·2·1</span>
  <span class="tag">partial products (AND gates) + ripple addition</span></div>
</section>

<section>
  <h2>6 · 4-bit adder (256-state exhaustively tested)</h2>
  <div class="row">
    <label><input type="checkbox" id="c3"> c3</label>
    <label><input type="checkbox" id="c2"> c2</label>
    <label><input type="checkbox" id="c1"> c1</label>
    <label><input type="checkbox" id="c0"> c0</label>
    <label><input type="checkbox" id="d3"> d3</label>
    <label><input type="checkbox" id="d2"> d2</label>
    <label><input type="checkbox" id="d1"> d1</label>
    <label><input type="checkbox" id="d0"> d0</label>
  </div>
  <div class="row"><span class="kbd">c + d =</span> <span class="bits">{leds('l_add4', 5)}</span>
  <span class="v d_add4"></span> <span class="caption">16·8·4·2·1</span>
  <span class="tag">4 full adders, carries chained as named wires</span></div>
</section>

<section>
  <h2>7 · dot product u·v (2-bit entries)</h2>
  <div class="row">
    <label><input type="checkbox" id="u1"> u1</label>
    <label><input type="checkbox" id="u0"> u0</label>
    <label><input type="checkbox" id="v1"> v1</label>
    <label><input type="checkbox" id="v0"> v0</label>
  </div>
  <div class="row"><span class="kbd">u₀v₀ + u₁v₁ =</span> <span class="bits">{leds('l_dot', 5)}</span>
  <span class="v d_dot"></span> <span class="caption">16·8·4·2·1</span>
  <span class="tag">two multipliers + shared ripple adder</span></div>
</section>

<section>
  <h2>8 · matrix × vector — W = [[2,1],[1,2]], x = (v₁,v₀)</h2>
  <div class="row"><span class="kbd">row 0</span> <span class="bits">{leds('l_mv0', 4)}</span>
  <span class="v d_mv0"></span> <span class="tag">= 2v₁ + 1v₀</span></div>
  <div class="row"><span class="kbd">row 1</span> <span class="bits">{leds('l_mv1', 4)}</span>
  <span class="v d_mv1"></span> <span class="tag">= 1v₁ + 2v₀</span></div>
  <div class="tag">fixed weights are build-time constants; weight × input uses gate-masked magnitudes</div>
</section>

<section>
  <h2>9 · neuron — y = step(+2x₁ − 2x₀ − 1)</h2>
  <div class="row"><span class="kbd">preactivation (4-bit two's complement)</span>
  <span class="bits">{leds('l_npre', 4)}</span> <span class="v d_npre"></span> <span class="caption">−8·4·2·1</span></div>
  <div class="row"><span class="kbd">activation</span> <span class="led l_n_out"></span>
  <span class="tag">= 1 if preactivation ≥ 0 (sign bit)</span></div>
</section>

<section>
  <h2>10 · XOR — solved by a 2-2-1 MLP</h2>
  <div class="row"><span class="kbd">h1 = step(+2x₁−2x₀−1)</span> <span class="led l_h1"></span></div>
  <div class="row"><span class="kbd">h2 = step(−2x₁+2x₀−1)</span> <span class="led l_h2"></span></div>
  <div class="row"><span class="kbd">out = step(+2h1+2h2−1)</span> <span class="led l_xor_out"></span>
  <span class="v d_xor"></span></div>
  <div class="tag">a single linear neuron cannot learn XOR; two hidden neurons can. All four inputs verified against an independent reference model.<br>
  inspect the live math: DevTools → Computed → <span class="kbd">--xor_h1_out</span>, <span class="kbd">--xor_out_out</span>…</div>
</section>

<section>
  <h2>11 · comparison — the same XOR in native CSS arithmetic</h2>
  <div class="row"><span class="kbd">h1 = max(0, min(1, 2x₁−2x₀))</span> <span class="led l_nb_h1"></span></div>
  <div class="row"><span class="kbd">h2 = max(0, min(1, −2x₁+2x₀))</span> <span class="led l_nb_h2"></span></div>
  <div class="row"><span class="kbd">out = max(0, min(1, 2h1+2h2−1))</span> <span class="led l_nb_out"></span>
  <span class="v d_nb_out"></span></div>
  <div class="row"><span class="kbd">Wx row 0 / row 1</span> <span class="v d_nb_mv0"></span> / <span class="v d_nb_mv1"></span></div>
  <div class="tag">~14 declarations total vs {n_signals} gate signals above. Same outputs, opposite philosophy.
  Because var()×var() is illegal in CSS, native mode only exists when one operand is a build-time constant —
  which is true for inference weights, and exactly why structural composition is unavoidable for interactive multiplication.</div>
</section>

<section>
  <h2>12 · trained classifier — 3×3 glyph → “top bar” vs “left bar”</h2>
  <div class="tag">trained at build time by a plain perceptron (scripts/train.py) on 9 exemplars; weights compiled into the gate netlist. bias = {cls_bias}, w = {cls_weights}. This is the only learned part of the demo.</div>
  <div class="grid" role="group" aria-label="3 by 3 glyph grid">
    {"".join(f'<label class="cell"><input type="checkbox" id="g{i}" aria-label="cell {i//3},{i%3}"></label>' for i in range(9))}
  </div>
  <div class="row"><span class="kbd">preactivation (5-bit signed)</span> <span class="bits">{leds('l_clspre', 5)}</span> <span class="v d_clspre"></span></div>
  <div class="row"><span class="kbd">class</span> <span class="led l_cls_out"></span>
  <span class="tag">1 = top bar, 0 = left bar / other</span></div>
</section>

<section>
  <h2>13 · drawn-digit classifier, readouts</h2>
  <div class="tag">the drawing box and display live on the main page; these readouts tap the same circuit's signals. linear classifier, weights trained on MNIST at build time (scripts/train_mnist.py), {mnist_test_acc:.0%} MNIST test accuracy.</div>
  <div class="row"><span class="kbd">margin, top1 - top2 (decimal view)</span> <span class="v d_mnist_margin"></span></div>
  <div class="row"><span class="kbd">predicted digit (index bits, decimal view)</span> <span class="v d_mnist_digit"></span></div>
  <div class="row"><span class="kbd">per-class scores (signed, decimal views)</span></div>
  <div class="row">
    {"".join(f'<span class="kbd">{k}:</span> <span class="v d_mnist_score{k}"></span> ' for k in range(10))}
  </div>
  <div class="tag">
  argmax = tournament left-fold over the 10 class scores (ties keep the lowest digit); each score = popcount-decomposed
  weighted sum (weights ∈ [−3,3] via bit-planes P0/P1) − bias, all gate-composed at build time. Seven-segment display and
  digit strip read the argmax/minterm gate signals directly (LEDs); the numeric readouts above are native-calc views,
  outside the gate circuit, exactly like every other decimal readout on this page.
  </div>
</section>

<section>
  <h2>honesty label</h2>
  <div class="tag">
  Runtime: HTML + CSS only (no script, no WASM, no network, works from file://).<br>
  Gates are named bit identities over native CSS min()/max()/calc() — the browser's arithmetic is the substrate; we compose circuits on top.<br>
  Decimal numbers in green are native-calc display views, outside the gate circuit. LEDs read gate signals directly.<br>
  The MNIST classifier (§13) follows the same split: argmax/minterm/segment signals are gates, the score, digit and margin numbers and the confidence meter are native-calc views. No exception.<br>
  Generated by scripts/generate.py at build time; rebuilds are deterministic.
  </div>
</section>

</details>

<footer class="tag">htmlnet · zero runtime JavaScript · <span class="kbd">make build</span> / <span class="kbd">make test</span></footer>
</main>
"""
    html = render(c, extra, body, "htmlnet — draw a digit, zero JavaScript")
    open(path, "w").write(html)
    print(f"wrote {path}: {n_signals} signals, {len(html.encode('utf-8'))} bytes")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dist/index.html")
