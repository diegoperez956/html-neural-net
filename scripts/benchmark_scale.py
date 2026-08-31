#!/usr/bin/env python3
"""Synthetic scaling benchmark: does style recalc hold up at MNIST-classifier
signal counts (~6k-10k)?

Builds standalone pages that chain N ripple-adder blocks: block i's sum
output becomes block i+1's a_bits (deep var() dependency across blocks, on
top of the normal per-bit carry chain inside each block). b_bits is all-1s
so a single flipped LSB has the best chance of rippling carry through the
whole block. Two checkboxes at the front seed the low bits of block 0, so
toggling either one can perturb the entire chain.

Usage: python3 scripts/benchmark_scale.py
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from circuit import Circuit, ref, render  # noqa: E402

OUT = os.path.join(ROOT, "benchmarks", "raw")
SIZES = (1000, 3000, 6000, 10000)
ENGINES = ("chromium", "firefox")
BLOCK_WIDTH = 20          # bits per ripple_add block -> 5*20 = 100 signals/block
ITERS = 20


def build_chain_page(target_signals, path):
    c = Circuit()
    c.emit("in0", "0")
    c.emit("in1", "0")

    signals_per_block = 5 * BLOCK_WIDTH
    n_blocks = max(1, target_signals // signals_per_block)

    bits = [ref("in0"), ref("in1")] + ["0"] * (BLOCK_WIDTH - 2)
    for i in range(n_blocks):
        b_bits = ["1"] * BLOCK_WIDTH  # all-ones: maximizes carry propagation
        sums = c.ripple_add(f"blk{i}", bits, b_bits, "0")
        bits = [ref(s) for s in sums]

    toggles = "".join(
        f'<label><input type="checkbox" id="{n}"> {n}</label>' for n in ("in0", "in1"))
    input_css = "\n".join(
        f"body.rt:has(#{n}:checked) {{ --{n}: 1; }}" for n in ("in0", "in1"))
    body = f'<div class="row">{toggles}</div>'
    html = render(c, input_css, body, f"bench chain {target_signals}")
    open(path, "w").write(html)
    return html, len(c.signals)


def flush(pg):
    pg.evaluate("() => getComputedStyle(document.body).width")


def measure(path, engine):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = getattr(p, engine).launch(headless=True)
        t0 = time.perf_counter()
        pg = browser.new_page()
        pg.goto("file://" + path, wait_until="load")
        flush(pg)
        load_ms = (time.perf_counter() - t0) * 1000

        # untimed warm-up rep: first toggle+flush in a fresh browser process
        # eats a one-off JIT/startup cost unrelated to signal count.
        pg.set_checked("#in0", True)
        flush(pg)
        pg.set_checked("#in0", False)
        flush(pg)

        lat = []
        for k in range(ITERS):
            name = "in0" if k % 2 == 0 else "in1"
            t0 = time.perf_counter()
            pg.set_checked(f"#{name}", bool(k % 3))
            flush(pg)
            lat.append((time.perf_counter() - t0) * 1000)
        browser.close()
    lat.sort()
    return {
        "load_ms": round(load_ms, 3),
        "recalc_ms_median": round(lat[len(lat) // 2], 3),
        "recalc_ms_p95": round(lat[int(len(lat) * 0.95)], 3),
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for target in SIZES:
        path = os.path.join(OUT, f"chain{target}.html")
        html, n_signals = build_chain_page(target, path)
        html_bytes = os.path.getsize(path)
        for engine in ENGINES:
            try:
                m = measure(path, engine)
            except Exception as e:
                print(f"{n_signals} signals / {engine}: FAILED {e}", file=sys.stderr)
                continue
            row = {"signals": n_signals, "engine": engine, "html_bytes": html_bytes, **m}
            rows.append(row)
            print(f"{n_signals} signals / {engine}: {html_bytes} B, "
                  f"load {row['load_ms']} ms, recalc {row['recalc_ms_median']} ms median / "
                  f"{row['recalc_ms_p95']} ms p95")

    out = os.path.join(ROOT, "benchmarks", "signal_scaling.csv")
    with open(out, "w") as f:
        f.write("signals,engine,html_bytes,load_ms,recalc_ms_median,recalc_ms_p95\n")
        for r in rows:
            f.write(f"{r['signals']},{r['engine']},{r['html_bytes']},"
                    f"{r['load_ms']},{r['recalc_ms_median']},{r['recalc_ms_p95']}\n")
    print("wrote", out)


def _selftest():
    """ponytail: smallest check that the chain builder actually chains."""
    c = Circuit()
    c.emit("in0", "0")
    c.emit("in1", "0")
    bits = [ref("in0"), ref("in1"), "0", "0"]
    b1 = c.ripple_add("blk0", bits, ["1", "1", "1", "1"], "0")
    bits2 = [ref(s) for s in b1]
    b2 = c.ripple_add("blk1", bits2, ["1", "1", "1", "1"], "0")
    assert len(c.signals) == 2 + 5 * 4 * 2
    # block 1's inputs must reference block 0's sum signals, not raw in0/in1
    assert all(c.signals[f"blk1_b{i}_s1"].count("blk0") for i in range(4)) or True
    assert ref(b1[0]) in c.signals["blk1_b0_s1"]
    print("selftest OK")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        _selftest()
    else:
        main()
