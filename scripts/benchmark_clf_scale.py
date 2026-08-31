#!/usr/bin/env python3
"""Classifier-scale probe: real circuit shapes (popcount scores + argmax +
seven-seg, optional hidden layer) at 49/144 inputs, H in {0,8,16,32}.

Standalone pages, same measurement pattern as benchmark_scale.py: toggle an
input checkbox, force style resolution, time it. Weights are synthetic
(sparse, quantized [-3,3]) except the linear-49 config which loads the real
trained weights for a true M11 baseline.

Usage: python3 scripts/benchmark_clf_scale.py [--selftest]
"""
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from circuit import Circuit, Net, ref, render  # noqa: E402

OUT = os.path.join(ROOT, "benchmarks", "raw")
ENGINES = ("chromium", "firefox")
ITERS = 20


def synth_weights(n_inputs, seed, zero_p):
    rng = random.Random(seed)
    return [0 if rng.random() < zero_p else rng.choice((-3, -2, -1, 1, 2, 3))
            for _ in range(n_inputs)]


def build_page(n_inputs, hidden, path, real_weights=None):
    """hidden=0 -> linear; else MLP with `hidden` threshold neurons."""
    c = Circuit()
    n = Net(c)
    inputs = [f"i{k}" for k in range(n_inputs)]
    for name in inputs:
        c.emit(name, "0")

    def sparse(n_in, seed):
        # keep popcount planes within signed-7 range: pos_max = |p0|+2|p1| <= 63
        p = 0.0
        while True:
            w = synth_weights(n_in, seed, p)
            ok = True
            for sgn in (1, -1):
                p0 = sum(1 for x in w if x * sgn > 0 and abs(x) in (1, 3))
                p1 = sum(1 for x in w if x * sgn > 0 and abs(x) in (2, 3))
                if p0 + 2 * p1 > 60:
                    ok = False
            if ok:
                return w
            p += 0.05

    if hidden == 0:
        width = 7
        scores = []
        for k in range(10):
            w = real_weights[k] if real_weights else sparse(n_inputs, 1000 + k)
            b = 0
            scores.append(n.weighted_score(f"c{k}", w, b, [ref(x) for x in inputs], width))
    else:
        # hidden layer: thresholded signed scores over all inputs
        hbits = []
        for h in range(hidden):
            w = sparse(n_inputs, 2000 + h)
            s = n.weighted_score(f"h{h}", w, 0, [ref(x) for x in inputs], 7)
            hbits.append(c.gate("NOT", ref(s[-1]), name=f"h{h}_out"))  # sign->bit
        # output layer over hidden bits; widen if planes can't fit 7 bits
        width = 7
        if hidden > 21:
            width = 8
        scores = []
        for k in range(10):
            w = [random.Random(3000 + k).choice((-2, -1, 1, 2)) for _ in range(hidden)]
            scores.append(n.weighted_score(f"c{k}", w, 0, [ref(x) for x in hbits], width))

    idx, _ = c.argmax("amx", scores)
    mt = c.digit_minterms("mt", idx)
    segs = c.sevenseg("sg", mt)
    for letter, s in zip("abcdefg", segs):
        c.emit(f"seg_{letter}", ref(s))

    toggles = " ".join(
        f'<input type="checkbox" id="{inputs[k]}">' for k in (1, 2))
    input_css = "\n".join(
        f"body.rt:has(#{x}:checked) {{ --{x}: 1; }}" for x in inputs)
    body = f'<div>{toggles}</div>'
    html = render(c, input_css, body, f"clf bench {n_inputs}x H{hidden}")
    open(path, "w").write(html)
    return len(c.signals), os.path.getsize(path)


def flush(pg):
    pg.evaluate(
        "() => getComputedStyle(document.body).getPropertyValue('--seg_a')")


def measure(path, engine):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = getattr(p, engine).launch(headless=True)
        t0 = time.perf_counter()
        pg = browser.new_page()
        pg.goto("file://" + path, wait_until="load")
        flush(pg)
        load_ms = (time.perf_counter() - t0) * 1000
        pg.set_checked("#i1", True)
        flush(pg)
        pg.set_checked("#i1", False)
        flush(pg)
        lat = []
        for k in range(ITERS):
            name = "i1" if k % 2 == 0 else "i2"
            t0 = time.perf_counter()
            pg.set_checked(f"#{name}", bool(k % 3))
            flush(pg)
            lat.append((time.perf_counter() - t0) * 1000)
        browser.close()
    lat.sort()
    return {"load_ms": round(load_ms, 3),
            "recalc_ms_median": round(lat[len(lat) // 2], 3),
            "recalc_ms_p95": round(lat[int(len(lat) * 0.95)], 3)}


def _selftest():
    p = "/tmp/clf_selftest.html"
    sig, size = build_page(49, 0, p)
    assert 3000 < sig < 6000, sig
    sig8, _ = build_page(49, 8, p)
    assert sig8 > sig
    sig32, size32 = build_page(49, 32, p)
    assert sig32 > sig8
    html = open(p).read()
    assert "--seg_g" in html and "amx_r9" in html
    print(f"selftest OK: linear49={sig} mlp49-32={sig32} signals, {size32} B")


def main():
    os.makedirs(OUT, exist_ok=True)
    real = None
    try:
        with open(os.path.join(ROOT, "scripts", "weights_mnist.json")) as f:
            real = json.load(f)["weights"]
    except OSError:
        pass
    configs = [("linear49-real", 49, 0, real)] + [
        (f"{kind}{n_in}-H{h}" if h else f"linear{n_in}", n_in, h, None)
        for n_in in (49, 144) for h in ((0, 8, 16, 32) if n_in == 49 else (0, 8, 16))
        for kind in ("mlp",)
    ]
    rows = []
    for tag, n_in, h, rw in configs:
        path = os.path.join(OUT, f"clf-{tag}.html")
        sig, size = build_page(n_in, h, path, rw)
        for engine in ENGINES:
            try:
                m = measure(path, engine)
            except Exception as e:
                print(f"{tag}/{engine}: FAILED {e}", file=sys.stderr)
                continue
            rows.append((tag, sig, size, engine, m))
            print(f"{tag}: {sig} signals {size} B | {engine} "
                  f"load {m['load_ms']}ms recalc {m['recalc_ms_median']}/"
                  f"{m['recalc_ms_p95']}ms (med/p95)")
    out = os.path.join(ROOT, "benchmarks", "clf_scaling.csv")
    with open(out, "w") as f:
        f.write("tag,signals,html_bytes,engine,load_ms,recalc_ms_median,recalc_ms_p95\n")
        for tag, sig, size, engine, m in rows:
            f.write(f"{tag},{sig},{size},{engine},{m['load_ms']},"
                    f"{m['recalc_ms_median']},{m['recalc_ms_p95']}\n")
    print("wrote", out)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        _selftest()
    else:
        main()
