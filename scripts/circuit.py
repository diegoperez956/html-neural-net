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

    # --- popcount (carry-save reduction) ----------------------------------

    def popcount(self, name: str, bits):
        """Count the set bits among `bits` (LSB-first list of signal names,
        refs, or literals) via carry-save reduction: repeatedly fold 3 wires
        of equal weight into a full adder (sum stays at that weight, carry
        moves to weight+1); 2 wires -> half adder; 1 wire passes through.
        Weights are only ever fed by lower weights, so a single pass over
        weights 0,1,2,... in order — fully reducing each column before
        moving on — terminates with <=1 wire per weight. Returns the count
        as an LSB-first bit list, width = ceil(log2(n+1))."""
        assert len(bits) >= 1, f"{name}: popcount needs at least one input"
        cols = {0: [_op(b) for b in bits]}
        max_w = 0
        result = []
        k = 0
        w = 0
        while w <= max_w:
            col = cols.get(w, [])
            while len(col) >= 3:
                s, cy = self.full_adder(f"{name}_pc{w}_{k}", col[0], col[1], col[2])
                k += 1
                col = col[3:] + [ref(s)]
                cols.setdefault(w + 1, []).append(ref(cy))
                max_w = max(max_w, w + 1)
            if len(col) == 2:
                s, cy = self.half_adder(f"{name}_pc{w}_{k}", col[0], col[1])
                k += 1
                col = [ref(s)]
                cols.setdefault(w + 1, []).append(ref(cy))
                max_w = max(max_w, w + 1)
            result.append(col[0] if col else "0")
            w += 1
        return result

    # --- argmax tournament --------------------------------------------------

    def argmax(self, name: str, scores):
        """Tournament left-fold argmax over equal-width signed scores (list of
        LSB-first bit-name lists). Incumbent starts at class 0; each round
        compares the incumbent against the next class (the challenger).
        diff = incumbent - challenger via NOT gates on the sign-extended
        challenger + one ripple add with carry-in 1 (two's-complement
        subtraction folded into a single adder). sign bit s=1 means the
        challenger is strictly greater (ties keep the incumbent, so the
        lowest-index class wins ties). Mux: out_i = OR(AND(s,chal_i),
        AND(NOT(s),inc_i)) — NOT(s) computed once per round and reused.

        Also tracks the runner-up score (streaming top-2): when the
        challenger wins, the old incumbent becomes the runner-up; otherwise
        the runner-up rises to max(runner-up, challenger) via a second
        folded subtraction (runner-up - challenger, reusing the
        challenger's NOT gates) whose sign bit s2=1 means challenger is
        strictly greater than the runner-up. The runner-up starts at the
        most negative representable score, so the invariant
        best >= runner-up >= every losing score seen holds.

        Returns (index_bits_lsb, winning_score_bits_lsb, margin_bits_lsb)
        where margin = best - runner-up via one more folded subtraction
        (best + NOT(runner-up) + 1); margin >= 0, fits the extended width."""
        n = len(scores)
        assert n >= 1
        width = len(scores[0])
        assert all(len(s) == width for s in scores)
        idx_width = max(1, (n - 1).bit_length())
        ext_w = width + 1

        def sext(bits):
            return bits + [bits[-1]] * (ext_w - len(bits))

        def bits_of(v, w):
            return [str((v >> i) & 1) for i in range(w)]

        inc_score = scores[0]
        inc_idx = bits_of(0, idx_width)
        run_score = bits_of(-(1 << (width - 1)), width)  # min signed value
        for r in range(1, n):
            chal_score = scores[r]
            chal_idx = bits_of(r, idx_width)
            not_chal = [self.gate("NOT", b, name=f"{name}_r{r}_nc{i}")
                        for i, b in enumerate(sext(chal_score))]
            diff = self.ripple_add(f"{name}_r{r}_diff", sext(inc_score), not_chal, "1")
            s = diff[-1]
            ns = self.gate("NOT", ref(s), name=f"{name}_r{r}_ns")
            diff2 = self.ripple_add(f"{name}_r{r}_d2", sext(run_score), not_chal, "1")
            s2 = diff2[-1]
            ns2 = self.gate("NOT", ref(s2), name=f"{name}_r{r}_ns2")

            def mux(inc_bit, chal_bit, tag):
                hit = self.gate("AND", ref(s), _op(chal_bit), name=f"{name}_r{r}_{tag}_hit")
                keep = self.gate("AND", ref(ns), _op(inc_bit), name=f"{name}_r{r}_{tag}_keep")
                return self.gate("OR", ref(hit), ref(keep), name=f"{name}_r{r}_{tag}_out")

            def mux_if(cond, ncond, keep_bit, hit_bit, tag):
                hit = self.gate("AND", ref(cond), _op(hit_bit), name=f"{name}_r{r}_{tag}_hit")
                keep = self.gate("AND", ref(ncond), _op(keep_bit), name=f"{name}_r{r}_{tag}_keep")
                return self.gate("OR", ref(hit), ref(keep), name=f"{name}_r{r}_{tag}_out")

            # runner-up candidate: rises to the challenger iff chal > runner-up
            run_up = [mux_if(s2, ns2, run_score[i], chal_score[i], f"u{i}")
                      for i in range(width)]
            # if the challenger wins, the old incumbent is the new runner-up
            new_run = [mux_if(s, ns, run_up[i], inc_score[i], f"n{i}")
                       for i in range(width)]
            inc_score = [mux(inc_score[i], chal_score[i], f"s{i}") for i in range(width)]
            inc_idx = [mux(inc_idx[i], chal_idx[i], f"i{i}") for i in range(idx_width)]
            run_score = new_run
        not_run = [self.gate("NOT", b, name=f"{name}_mnr{i}")
                   for i, b in enumerate(sext(run_score))]
        margin = self.ripple_add(f"{name}_margin", sext(inc_score), not_run, "1")
        return inc_idx, inc_score, margin

    # --- digit minterms + seven-segment decoder -----------------------------

    def digit_minterms(self, name: str, idx_bits):
        """idx_bits: LSB-first index bit-name list. Returns one AND-tree
        minterm signal per value 0..2**len(idx_bits)-1 (NOT gates emitted
        once per bit and reused across all minterms)."""
        nots = [self.gate("NOT", b, name=f"{name}_not{i}") for i, b in enumerate(idx_bits)]
        minterms = []
        for val in range(1 << len(idx_bits)):
            terms = [ref(idx_bits[i]) if (val >> i) & 1 else ref(nots[i])
                      for i in range(len(idx_bits))]
            acc = terms[0]
            acc_name = None
            for i in range(1, len(terms)):
                acc_name = self.gate("AND", acc, terms[i], name=f"{name}_m{val}_and{i}")
                acc = ref(acc_name)
            minterms.append(acc_name)
        return minterms

    SEVENSEG_MAP = {
        "a": {0, 2, 3, 5, 6, 7, 8, 9}, "b": {0, 1, 2, 3, 4, 7, 8, 9},
        "c": {0, 1, 3, 4, 5, 6, 7, 8, 9}, "d": {0, 2, 3, 5, 6, 8, 9},
        "e": {0, 2, 6, 8}, "f": {0, 4, 5, 6, 8, 9}, "g": {2, 3, 4, 5, 6, 8, 9},
    }

    def sevenseg(self, name: str, minterms):
        """minterms: 10 digit-minterm bit names. Returns 7 segment bit names
        (a,b,c,d,e,f,g), each an OR-tree of its lit digits' minterms."""
        segs = []
        for seg in "abcdefg":
            digits = sorted(self.SEVENSEG_MAP[seg])
            acc = ref(minterms[digits[0]])
            acc_name = minterms[digits[0]]
            for d in digits[1:]:
                acc_name = self.gate("OR", acc, ref(minterms[d]), name=f"{name}_{seg}_or{d}")
                acc = ref(acc_name)
            segs.append(acc_name)
        return segs


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

    def weighted_score(self, name, weights, bias, inputs, width=7):
        """Per-class weighted sum for integer weights w_i in [-3,3] over bit
        signals, plus integer bias, as width-bit signed two's complement.

        Weight magnitude is decomposed into two bit-planes: P0 = inputs with
        |w| in {1,3} (weight bit 0 set), P1 = inputs with |w| in {2,3}
        (weight bit 1 set) -- separately for positive and negative w. The
        popcount of each plane, restricted to lit (x_i=1) inputs, gives the
        plane's contribution directly (weight 3 inputs sit in both planes,
        contributing 1+2); P1's count is doubled by a pure-wiring "0" prefix
        (shift-left-1). pos = popcount(P0pos) + (popcount(P1pos)<<1); neg the
        same. score = pos - neg + bias, via NOT gates on neg's bits + one
        ripple add with carry-in 1 (subtraction folded into a single adder),
        then a second ripple add for the bias constant.

        Asserts (from the actual weights/bias, never a hardcoded ceiling)
        that popcount planes and the final score fit signed `width` bits.
        Returns the score bits, LSB-first."""
        c = self.c
        assert len(weights) == len(inputs)
        assert all(-3 <= w <= 3 for w in weights), f"{name}: weight magnitude > 3"

        def plane(pred):
            return [x for w, x in zip(weights, inputs) if pred(w)]

        p0pos = plane(lambda w: w > 0 and abs(w) in (1, 3))
        p1pos = plane(lambda w: w > 0 and abs(w) in (2, 3))
        p0neg = plane(lambda w: w < 0 and abs(w) in (1, 3))
        p1neg = plane(lambda w: w < 0 and abs(w) in (2, 3))

        # build-time width-sufficiency assertion, computed from this class's
        # actual weights/bias -- not a hardcoded magic number.
        pos_max = len(p0pos) + 2 * len(p1pos)
        neg_max = len(p0neg) + 2 * len(p1neg)
        lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
        assert pos_max <= hi and neg_max <= hi, (
            f"{name}: popcount plane too large for width {width} "
            f"(pos_max={pos_max}, neg_max={neg_max})")
        score_max, score_min = bias + pos_max, bias - neg_max
        assert lo <= score_min and score_max <= hi, (
            f"{name}: score range [{score_min},{score_max}] does not fit "
            f"signed width {width} [{lo},{hi}]")

        def zext(bits):
            pad = width - len(bits)
            assert pad >= 0, f"{name}: popcount output wider than width {width}"
            return bits + ["0"] * pad

        def plane_count(tag, pl):
            return c.popcount(f"{name}_{tag}", pl) if pl else ["0"]

        pos = c.ripple_add(f"{name}_pos",
                            zext(plane_count("p0pos", p0pos)),
                            zext(["0"] + plane_count("p1pos", p1pos)), "0")
        neg = c.ripple_add(f"{name}_neg",
                            zext(plane_count("p0neg", p0neg)),
                            zext(["0"] + plane_count("p1neg", p1neg)), "0")
        not_neg = [c.gate("NOT", b, name=f"{name}_notneg{i}") for i, b in enumerate(neg)]
        diff = c.ripple_add(f"{name}_diff", pos, not_neg, "1")
        bias_bits = self.const_bits(bias, width)
        score = c.ripple_add(f"{name}_score", diff, bias_bits, "0")
        return score

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
