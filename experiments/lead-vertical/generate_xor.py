#!/usr/bin/env python3
"""Build-time generator for the lead XOR-MLP proof experiment.

XOR network (threshold, integer weights):
  h1 = step( +2*x1 -2*x0 -1 )     -> x1 AND NOT x0
  h2 = step( -2*x1 +2*x0 -1 )     -> NOT x1 AND x0
  out = step( +2*h1 +2*h2 -1 )    -> XOR

Gates are named bit signals on one .rt ancestor. Full adder = 5 gate decls.
Weight application: weights are fixed constants +/-2, so t = w*x is built by
bit replication (wiring), not a multiplier circuit. Bias -1 is constant 1111.
Signed sum = 4-bit two's complement ripple adders; threshold = sign bit.
"""
import sys

SIGNALS = []  # (name, expr) in declaration order
PROPS = set()

def signal(name, expr):
    SIGNALS.append((name, expr))
    PROPS.add(name)

def bit_ref(name):
    return f"var(--{name})"

def NOT(a):
    return f"calc(1 - ({a}))"

def AND(a, b):
    return f"min({a}, {b})"

def OR(a, b):
    return f"max({a}, {b})"

def XOR(a, b):
    return f"calc(max({a}, {b}) - min({a}, {b}))"

def fa(name, a, b, cin):
    """Full adder: emits gates for sum/cout, returns (sum_name, cout_name)."""
    s1 = f"{name}_s1"; c1 = f"{name}_c1"; sm = f"{name}_sum"
    c2 = f"{name}_c2"; co = f"{name}_cout"
    signal(s1, XOR(a, b))
    signal(c1, AND(a, b))
    signal(sm, XOR(bit_ref(s1), cin))
    signal(c2, AND(bit_ref(s1), cin))
    signal(co, OR(bit_ref(c1), bit_ref(c2)))
    return sm, co

def ripple4(name, a_bits, b_bits, cin_expr):
    """4-bit ripple adder. a_bits/b_bits: list of 4 signal refs or literals, LSB first."""
    outs = []
    carry = cin_expr
    for i in range(4):
        s, co = fa(f"{name}_b{i}", a_bits[i], b_bits[i], carry)
        outs.append(s)
        carry = bit_ref(co)
    return outs

def wt_bits(w, x):
    """4-bit two's complement of w*x for w in {+2,-2}, x a signal ref. LSB first."""
    if w == +2:
        return ["0", x, "0", "0"]            # 2x: bits 0010/0000
    if w == -2:
        return ["0", x, x, x]                # -2x: 0000 or 1110
    raise ValueError(w)

def neuron(name, w1, w2, x1, x2):
    """threshold neuron y = step(w1*x1 + w2*x2 - 1), 4-bit signed."""
    t1 = wt_bits(w1, x1)
    t2 = wt_bits(w2, x2)
    tmp = ripple4(f"{name}_tmp", t1, t2, "0")
    pre = ripple4(f"{name}_pre", [bit_ref(t) for t in tmp], ["1", "1", "1", "1"], "0")
    sign = pre[3]
    y = f"{name}_out"
    signal(y, NOT(bit_ref(sign)))
    return y, pre

def main(path):
    x1, x0 = "x1", "x0"
    h1, h1pre = neuron("h1", +2, -2, bit_ref(x1), bit_ref(x0))
    h2, h2pre = neuron("h2", -2, +2, bit_ref(x1), bit_ref(x0))
    out, outpre = neuron("out", +2, +2, bit_ref(h1), bit_ref(h2))

    props = "\n".join(
        f"    @property --{p} {{ syntax: \"<integer>\"; inherits: true; initial-value: 0; }}"
        for p in sorted(PROPS)
    )
    decls = "\n".join(f"    .rt {{ --{n}: {e}; }}" for n, e in SIGNALS)

    # per-bit LED views: bit i of a 4-bit signed word lights a distinct cell
    def word_view(prefix, bits):
        # bits: signal names LSB first
        out = []
        for i, bname in enumerate(bits):
            out.append(
                f'    .{prefix}_b{i}::after {{ content: ""; display: inline-block; '
                f'width: 10px; height: 10px; margin: 1px; '
                f'background: color-mix(in srgb, #38ff8c, #0b0e14 var(--ledoff, 0%)); '
                f'--ledoff: calc((1 - var(--{bname})) * 100%); }}'
            )
        return "\n".join(out)

    led_css = "\n".join([
        word_view("h1pre", h1pre),
        word_view("h2pre", h2pre),
        word_view("outpre", outpre),
    ])
    # decimal views via native calc (labeled VIEW, not gate logic)
    def dec_view(prefix, bits):
        terms = " + ".join(f"({2**i} * var(--{b}))" for i, b in enumerate(bits))
        return (
            f'    .{prefix}_dec::after {{ counter-reset: v calc({terms}); content: counter(v); }}'
        )

    dec_css = "\n".join([
        dec_view("h1pre", h1pre),
        dec_view("h2pre", h2pre),
        dec_view("outpre", outpre),
        dec_view("h1v", [h1]),
        dec_view("h2v", [h2]),
        dec_view("outv", [out]),
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>lead proof: gate-built XOR MLP</title>
<style>
    body {{ background: #0b0e14; color: #cfe3ff; font: 15px/1.5 ui-monospace, monospace; }}
    .row {{ margin: 6px 0; }}
    label {{ margin-right: 16px; }}
{props}

    /* primary inputs: form state -> bits */
    .rt {{ --x1: 0; --x0: 0; }}
    body.rt:has(#x1:checked) {{ --x1: 1; }}
    body.rt:has(#x0:checked) {{ --x0: 1; }}

    /* netlist (generated) */
{decls}

    /* per-bit LEDs */
{led_css}

    /* composite decimal views: native calc, display only */
{dec_css}
    .tag {{ color: #7d8fa9; font-size: 12px; }}
</style>
</head>
<body class="rt">
  <div class="row">
    <label><input type="checkbox" id="x1"> x1</label>
    <label><input type="checkbox" id="x0"> x0</label>
  </div>
  <div class="row">h1 = step(+2x1 - 2x0 - 1) &nbsp; LED: <span class="h1pre_b3"></span><span class="h1pre_b2"></span><span class="h1pre_b1"></span><span class="h1pre_b0"></span> = <span class="h1pre_dec"></span> &nbsp; h1 = <span class="h1v_dec"></span></div>
  <div class="row">h2 = step(-2x1 + 2x0 - 1) &nbsp; LED: <span class="h2pre_b3"></span><span class="h2pre_b2"></span><span class="h2pre_b1"></span><span class="h2pre_b0"></span> = <span class="h2pre_dec"></span> &nbsp; h2 = <span class="h2v_dec"></span></div>
  <div class="row">out = step(+2h1 + 2h2 - 1) &nbsp; LED: <span class="outpre_b3"></span><span class="outpre_b2"></span><span class="outpre_b1"></span><span class="outpre_b0"></span> = <span class="outpre_dec"></span> &nbsp; XOR = <span class="outv_dec"></span></div>
  <div class="row tag">LEDs read gate signals directly. Decimal views use native calc() (display only, outside gate circuit).</div>
</body>
</html>
"""
    open(path, "w").write(html)
    print(f"wrote {path}: {len(SIGNALS)} gate signals, {len(PROPS)} properties")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "experiments/lead-vertical/xor.html")
