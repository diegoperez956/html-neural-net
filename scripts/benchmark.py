#!/usr/bin/env python3
"""Scaling benchmarks: generated size + browser recalc latency vs operand width.

Usage: python3 scripts/benchmark.py [--max-bits 12]
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from circuit import Circuit, ref, render  # noqa: E402

OUT = os.path.join(ROOT, "benchmarks", "raw")


def build_adder_page(bits, path):
    c = Circuit()
    names_a = []
    names_b = []
    inputs = []
    for i in range(bits):
        na, nb = f"a{i}", f"b{i}"
        c.emit(na, "0"); c.emit(nb, "0")
        names_a.append(ref(na)); names_b.append(ref(nb))
        inputs.append(na); inputs.append(nb)
    sums = c.ripple_add("add", names_a + ["0"], names_b + ["0"], "0")
    input_css = "\n".join(
        f"body.rt:has(#{n}:checked) {{ --{n}: 1; }}" for n in inputs)
    toggles = "".join(f'<label><input type="checkbox" id="{n}"> {n}</label>' for n in inputs)
    body = f'<div class="row">{toggles}</div>'
    html = render(c, input_css, body, f"bench {bits}-bit adder")
    open(path, "w").write(html)
    return html


def measure(bits):
    path = os.path.join(OUT, f"adder{bits}.html")
    os.makedirs(OUT, exist_ok=True)
    html = build_adder_page(bits, path)
    css_bytes = 0
    for line in html.splitlines():
        if line.strip().startswith(".rt {"):
            css_bytes += len(line)
    size = os.path.getsize(path)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page()
        pg.goto("file://" + path)
        # force one full style pass
        pg.evaluate("() => getComputedStyle(document.body).width")
        N = 40
        lat = []
        for k in range(N):
            i = k % bits
            name = f"a{i}" if k % 2 == 0 else f"b{i}"
            t0 = time.perf_counter()
            pg.set_checked(f"#{name}", bool(k % 3))
            pg.evaluate("() => getComputedStyle(document.body).width")
            lat.append((time.perf_counter() - t0) * 1000)
        b.close()
    lat.sort()
    return {
        "bits": bits,
        "html_bytes": size,
        "signals": len(html.split("@property")) - 1,
        "css_decl_bytes": css_bytes,
        "recalc_ms_median": round(lat[len(lat) // 2], 3),
        "recalc_ms_p95": round(lat[int(len(lat) * 0.95)], 3),
    }


def main(max_bits):
    rows = []
    for bits in (1, 2, 4, 8, 12, 16):
        if bits > max_bits:
            break
        try:
            rows.append(measure(bits))
        except Exception as e:
            print(f"{bits}-bit: FAILED {e}", file=sys.stderr)
            continue
        r = rows[-1]
        print(f"{r['bits']}-bit: {r['html_bytes']} B, {r['signals']} signals, "
              f"recalc {r['recalc_ms_median']} ms median / {r['recalc_ms_p95']} ms p95")
    out = os.path.join(ROOT, "benchmarks", "adder_scaling.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write("bits,html_bytes,signals,css_decl_bytes,recalc_ms_median,recalc_ms_p95\n")
        for r in rows:
            f.write(f"{r['bits']},{r['html_bytes']},{r['signals']},"
                    f"{r['css_decl_bytes']},{r['recalc_ms_median']},{r['recalc_ms_p95']}\n")
    print("wrote", out)


if __name__ == "__main__":
    main(int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--max-bits" else 12)
