#!/usr/bin/env python3
"""htmlnet circuit compiler.

Build-time tool (allowed to be normal code). Emits an HTML+CSS-only artifact.

Model:
  * every signal is a named custom property registered @property <integer>
    inheriting from one .rt ancestor (the <body>);
  * primary bits come from checkboxes via body.rt:has(...) rules;
  * gates are named bit signals built from the primitive basis:
        NOT(a) = 1 - a
        AND(a,b) = min(a,b)
        OR(a,b) = max(a,b)
        XOR(a,b) = max(a,b) - min(a,b)
  * larger structures (adders, multipliers, dot products, matrix-vector,
    neurons, MLP) are *composed* from those gate signals at build time;
  * display: per-bit LEDs read bit signals directly. Composite decimal views
    use native calc() and are labeled VIEW (outside the gate circuit).

Numeric formats: fixed-width two's complement. Neuron products are 3-bit
signed (range -4..7), preactivations 4-bit signed (-8..7), threshold = sign
bit. Overflow impossible by construction; tests assert maxima.
"""
from __future__ import annotations

import dataclasses
import re

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def _op(x: str) -> str:
    """Normalize a circuit operand: plain identifiers are signal names -> ref;
    '0'/'1' and built expressions pass through."""
    if x in ("0", "1"):
        return x
    if x.startswith(("var(", "calc(", "min(", "max(")):
        return x
    if _NAME.match(x):
        return ref(x)
    return x


# ---------------------------------------------------------------- primitives

def ref(name: str) -> str:
    return f"var(--{name})"


def NOT(a: str) -> str:
    return f"calc(1 - ({a}))"


def AND(a: str, b: str) -> str:
    return f"min({a}, {b})"


def OR(a: str, b: str) -> str:
    return f"max({a}, {b})"


def XOR(a: str, b: str) -> str:
    return f"calc(max({a}, {b}) - min({a}, {b}))"


# -------------------------------------------------------------------- circuit

class Circuit:
    """Accumulates named signal declarations in dependency order."""

    def __init__(self):
        self.signals: dict[str, str] = {}   # name -> calc expression
        self.display: list[dict] = []       # display widgets for the page

    def emit(self, name: str, expr: str) -> str:
        assert name not in self.signals, f"duplicate signal {name}"
        self.signals[name] = expr
        return name

    # --- gates -----------------------------------------------------------

    def gate(self, kind: str, a: str, b: str = None, name: str = None) -> str:
        a, b = _op(a), _op(b) if b is not None else None
        if kind == "NOT":
            expr = NOT(a)
        elif kind == "AND":
            expr = AND(a, b)
        elif kind == "OR":
            expr = OR(a, b)
        elif kind == "XOR":
            expr = XOR(a, b)
        else:
            raise ValueError(kind)
        name = name or f"{kind.lower()}_{len(self.signals)}"
        return self.emit(name, expr)

    # --- adders ----------------------------------------------------------

    def half_adder(self, name: str, a: str, b: str):
        s = self.gate("XOR", a, b, name=f"{name}_sum")
        c = self.gate("AND", a, b, name=f"{name}_carry")
        return s, c

    def full_adder(self, name: str, a: str, b: str, cin: str):
        a, b, cin = _op(a), _op(b), _op(cin)
        s1 = self.gate("XOR", a, b, name=f"{name}_s1")
        c1 = self.gate("AND", a, b, name=f"{name}_c1")
        s = self.gate("XOR", ref(s1), cin, name=f"{name}_sum")
        c2 = self.gate("AND", ref(s1), cin, name=f"{name}_c2")
        cout = self.gate("OR", ref(c1), ref(c2), name=f"{name}_carry")
        return s, cout

    def ripple_add(self, name: str, a_bits, b_bits, cin: str = "0"):
        """N-bit ripple adder. a_bits/b_bits: LSB-first lists of signal names,
        refs, or literals. Returns LSB-first list of sum signal names."""
        outs = []
        carry = _op(cin)
        for i, (ab, bb) in enumerate(zip(a_bits, b_bits)):
            s, c = self.full_adder(f"{name}_b{i}", ab, bb, carry)
            outs.append(s)
            carry = ref(c)
        return outs



    # --- unsigned structural multiplication -------------------------------

    def unsigned_mult(self, name: str, a_bits, b_bits):
        """a_bits LSB-first, b_bits LSB-first; returns product bits LSB-first.
        Partial products are AND gates; rows added with the same ripple adder
        construction used elsewhere (no lookup)."""
        w = len(a_bits) + len(b_bits)
        rows = []
        for j, bj in enumerate(b_bits):
            row = ["0"] * j + [self.gate("AND", ai, bj, name=f"{name}_pp{i}_{j}")
                               for i, ai in enumerate(a_bits)] + ["0"] * (w - j - len(a_bits))
            rows.append(row)
        acc = rows[0]
        for k in range(1, len(rows)):
            acc = self.ripple_add(f"{name}_row{k}", acc, rows[k], "0")
        return acc

    # --- two's complement helpers ----------------------------------------

    def negate(self, name: str, bits):
        """Two's complement negation: bitwise NOT (gates) + 1 via ripple add."""
        nb = [self.gate("NOT", b, name=f"{name}_n{i}") for i, b in enumerate(bits)]
        zero = ["0"] * len(bits)
        return self.ripple_add(f"{name}_neg", nb, zero, "1")


# --------------------------------------------------------------- network math

class Net:
    """Fixed-weight network building blocks over a Circuit."""

    def __init__(self, c: Circuit):
        self.c = c

    def const_bits(self, value: int, width: int):
        """Two's complement constant, LSB-first list of literal '0'/'1'."""
        v = value & ((1 << width) - 1)
        return [str((v >> i) & 1) for i in range(width)]

    def neuron(self, name: str, weights, biases, inputs, pwidth=3, swidth=4):
        """Threshold neuron. weights: list of signed ints (|w| < 2**(pwidth-1)),
        biases: list of signed ints, inputs: list of bit signal names.
        pwidth: product word width (signed). swidth: sum word width (signed).
        Products are built by structural negation of bit-masked magnitudes
        (|w| AND input) — real gates, no multiplier shortcut — then summed by
        ripple adders. Returns (output_bit, sum_bits_lsb)."""
        c = self.c
        terms = []
        for i, (w, x) in enumerate(zip(weights, inputs)):
            mag = abs(w)
            sign = 1 if w < 0 else 0
            mag_bits = self.const_bits(mag, pwidth)
            masked = [c.gate("AND", mb, x, name=f"{name}_t{i}_m{j}")
                      for j, mb in enumerate(mag_bits)]
            if sign:
                nb = [c.gate("NOT", b, name=f"{name}_t{i}_n{j}") for j, b in enumerate(masked)]
                masked = c.ripple_add(f"{name}_t{i}_neg", nb, ["0"] * pwidth, "1")
            terms.append(masked)
        # sum products + biases with a ripple adder chain
        acc = terms[0] if terms else ["0"] * swidth
        # extend each term to swidth with sign extension
        def sext(bits):
            pad = swidth - len(bits)
            return bits + [bits[-1]] * pad
        acc = sext(acc)
        for t in terms[1:]:
            acc = c.ripple_add(f"{name}_add{len(c.signals)}", acc, sext(t), "0")
        for b in biases:
            acc = c.ripple_add(f"{name}_bias{len(c.signals)}", acc,
                               self.const_bits(b, swidth), "0")
        sign_bit = acc[-1]
        out = c.gate("NOT", ref(sign_bit), name=f"{name}_out")
        return out, acc

    def mlp_xor(self, prefix="xor"):
        """2-2-1 XOR MLP. h1 = step(+2x1 -2x0 -1), h2 = step(-2x1 +2x0 -1),
        out = step(+2h1 +2h2 -1)."""
        c = self.c
        h1, _ = self.neuron(f"{prefix}_h1", [+2, -2], [-1], [ref("x1"), ref("x0")])
        h2, _ = self.neuron(f"{prefix}_h2", [-2, +2], [-1], [ref("x1"), ref("x0")])
        out, _ = self.neuron(f"{prefix}_out", [+2, +2], [-1], [ref(h1), ref(h2)])
        return h1, h2, out


# ------------------------------------------------------------------ rendering

def render(c: Circuit, extra_css: str, body: str, title: str) -> str:
    props = "\n".join(
        f'@property --{n} {{ syntax: "<integer>"; inherits: true; initial-value: 0; }}'
        for n in sorted(c.signals)
    )
    decls = "\n".join(f".rt {{ --{n}: {e}; }}" for n, e in c.signals.items())
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{extra_css}

{props}

/* generated netlist — composed at build time from gate primitives */
{decls}
</style>
</head>
<body class="rt">
{body}
</body>
</html>
"""
