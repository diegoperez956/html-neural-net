//! Build-time page generator (originally a 1:1 port of scripts/generate.py,
//! deleted after the D-008 Rust migration; Rust is now the sole build path).
//! Inference runs in CSS. This program emits the circuits, markup, and a
//! separate pointer-input script. Rust does not run in the browser.

mod circuit;

use circuit::{r#ref, render, Circuit, Gate, Net};
use serde::Deserialize;
use std::fs;
use std::path::Path;

const BASE_CSS: &str = include_str!("base_css.txt");

fn led_css(signal: &str, cls: &str) -> String {
    led_css_lit(signal, cls, "#fe8019")
}

fn led_css_lit(signal: &str, cls: &str, lit: &str) -> String {
    format!(
        ".{cls} {{ background: color-mix(in srgb, {lit}, #3c3836 calc((1 - var(--{signal})) * 100%)); }}"
    )
}

fn text_led_css(signal: &str, cls: &str) -> String {
    format!(
        ".{cls} {{ color: color-mix(in srgb, #fabd2f, #7c6f64 calc((1 - var(--{signal})) * 100%)); }}"
    )
}

/// @font-face rules embedding JetBrains Mono as base64 data URIs (single-file
/// constraint: no external font requests). Read at generation time from
/// assets/fonts/*.b64.
fn font_css(manifest_dir: &str) -> String {
    let assets = Path::new(manifest_dir).join("..").join("assets").join("fonts");
    let reg = fs::read_to_string(assets.join("JetBrainsMono-Regular.b64")).unwrap();
    let bold = fs::read_to_string(assets.join("JetBrainsMono-Bold.b64")).unwrap();
    let reg = reg.trim();
    let bold = bold.trim();
    format!(
        "\n@font-face {{\n  font-family: 'JetBrains Mono';\n  src: url(data:font/woff2;base64,{reg}) format(\"woff2\");\n  font-weight: 400;\n  font-style: normal;\n  font-display: swap;\n}}\n@font-face {{\n  font-family: 'JetBrains Mono';\n  src: url(data:font/woff2;base64,{bold}) format(\"woff2\");\n  font-weight: 700;\n  font-style: normal;\n  font-display: swap;\n}}\n"
    )
}

fn dec_css(cls: &str, sig: &str) -> String {
    format!(".{cls}::after {{ counter-reset: v var(--{sig}); content: counter(v); }}")
}

#[derive(Deserialize)]
struct ClsWeights {
    bias: i64,
    weights: [i64; 9],
}

#[derive(Deserialize)]
struct MnistWeights {
    weights: [Vec<i64>; 10],
    bias: [i64; 10],
    test_accuracy: f64,
    /// M13 pipeline fields: the runtime canvas is canvas×canvas checkboxes,
    /// dilated dilate_iters times (4-neighbor OR), then 2×2 blocks reduce to
    /// the 49 classifier bits via popcount >= block_threshold.
    block_threshold: usize,
    canvas: usize,
    dilate_iters: usize,
}

/// Python `{value:.0%}` — multiply by 100, round to 0 decimals, append '%'.
fn pct0(value: f64) -> String {
    format!("{:.0}%", value * 100.0)
}

/// Python `repr()` of a `list[int]` — "[1, 0, 2, -1]".
fn py_int_list(v: &[i64]) -> String {
    let inner = v.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(", ");
    format!("[{inner}]")
}

fn leds(cls: &str, nbits: usize) -> String {
    (0..nbits).rev().map(|i| format!(r#"<span class="led {cls}_{i}"></span>"#)).collect()
}

fn main() {
    let mut no_js = false;
    let mut output = None;
    for arg in std::env::args().skip(1) {
        if arg == "--no-js" {
            no_js = true;
        } else {
            assert!(!arg.starts_with('-') && output.is_none(), "usage: htmlnet-gen [output.html] [--no-js]");
            output = Some(arg);
        }
    }
    let out_path = output.unwrap_or_else(|| {
        if no_js { "dist/no-js.html" } else { "dist/index.html" }.to_string()
    });

    // scripts/ is a sibling of gen/ regardless of the invoking cwd — mirrors
    // python's __file__-relative weights loading.
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let scripts_dir = Path::new(manifest_dir).join("..").join("scripts");

    let mut c = Circuit::new();

    // ---------------- 1. primary bits x1, x0 (master XOR pair) -------------
    // ---------------- 2. gates: a, b toggles ---------------------------------
    let mut inputs: Vec<String> = vec![
        "x1", "x0", "a", "b", "cin", "a1", "a0", "b1", "b0", "c3", "c2", "c1", "c0", "d3", "d2",
        "d1", "d0", "u1", "u0", "v1", "v0",
    ]
    .into_iter()
    .map(String::from)
    .collect();
    inputs.extend((0..9).map(|i| format!("g{i}")));
    // M13: the 49 classifier inputs are no longer primary checkbox bits --
    // they are gate outputs (OR downsample of dilated canvas cells). The
    // primary inputs are the 14x14 paint-canvas cells mc0..mc195.
    inputs.extend((0..196).map(|i| format!("mc{i}")));
    for name in &inputs {
        c.emit(name, "0"); // placeholder; overridden by :has rules
    }

    let not_a = c.gate(Gate::Not, &r#ref("a"), "g_not");
    let and_g = c.gate2(Gate::And, &r#ref("a"), Some(&r#ref("b")), Some("g_and"));
    let or_g = c.gate2(Gate::Or, &r#ref("a"), Some(&r#ref("b")), Some("g_or"));
    let xor_g = c.gate2(Gate::Xor, &r#ref("a"), Some(&r#ref("b")), Some("g_xor"));
    let _ = (&not_a, &and_g, &or_g, &xor_g); // referenced only via LED CSS below

    // half adder (M2)
    let (ha_s, ha_c) = c.half_adder("ha", &r#ref("a"), &r#ref("b"));
    // full adder (M3)
    let (fa_s, fa_c) = c.full_adder("fa", &r#ref("a"), &r#ref("b"), &r#ref("cin"));

    // 2-bit adder + 2x2 multiplier (M4/M5)
    let s2 = c.ripple_add(
        "add2",
        &[r#ref("a0"), r#ref("a1"), "0".into()],
        &[r#ref("b0"), r#ref("b1"), "0".into()],
        "0",
    );
    let p2 = c.unsigned_mult("mul2", &[r#ref("a0"), r#ref("a1")], &[r#ref("b0"), r#ref("b1")]);

    // 4-bit adder (M4 exhaustively testable)
    let s4 = c.ripple_add(
        "add4",
        &[r#ref("c0"), r#ref("c1"), r#ref("c2"), r#ref("c3"), "0".into()],
        &[r#ref("d0"), r#ref("d1"), r#ref("d2"), r#ref("d3"), "0".into()],
        "0",
    );

    // Two-component binary vectors, not two-bit scalar entries. Sum range: 0..2.
    let p_u0v0 = c.unsigned_mult("d_u0v0", &[r#ref("u0")], &[r#ref("v0")]); // 1 bit
    let p_u1v1 = c.unsigned_mult("d_u1v1", &[r#ref("u1")], &[r#ref("v1")]); // 1 bit
    let mut p_u0v0_ext = p_u0v0.clone();
    p_u0v0_ext.extend(["0".to_string(), "0".to_string(), "0".to_string(), "0".to_string()]);
    let mut p_u1v1_ext = p_u1v1.clone();
    p_u1v1_ext.extend(["0".to_string(), "0".to_string(), "0".to_string(), "0".to_string()]);
    let dot_bits = c.ripple_add("dot_sum", &p_u0v0_ext, &p_u1v1_ext, "0");

    // matrix x vector: fixed W = [[2,1],[1,2]] x [v1,v0] -> two outputs.
    // weight x input = gate-masked magnitude bits (wiring), row = ripple sum.
    fn mask4(v: i64) -> [String; 4] {
        std::array::from_fn(|i| if (v >> i) & 1 == 1 { "1".to_string() } else { "0".to_string() })
    }
    fn row_of(c: &mut Circuit, name: &str, wx1: i64, wx0: i64, x1name: &str, x0name: &str) -> Vec<String> {
        let t1: Vec<String> = mask4(wx1)
            .iter()
            .enumerate()
            .map(|(j, m)| c.gate2(Gate::And, m, Some(&r#ref(x1name)), Some(&format!("{name}_t0_{j}"))))
            .collect();
        let t0: Vec<String> = mask4(wx0)
            .iter()
            .enumerate()
            .map(|(j, m)| c.gate2(Gate::And, m, Some(&r#ref(x0name)), Some(&format!("{name}_t1_{j}"))))
            .collect();
        c.ripple_add(name, &t1, &t0, "0")
    }
    let row0 = row_of(&mut c, "mv_row0", 2, 1, "v1", "v0");
    let row1 = row_of(&mut c, "mv_row1", 1, 2, "v1", "v0");

    // neuron (h1 of the XOR net) + full XOR MLP with stable test aliases
    let mut n = Net::new(&mut c);
    let (n_out, n_pre) = n.neuron("n1", &[2, -2], &[-1], &[r#ref("x1"), r#ref("x0")], 3, 4);
    for (i, b) in n_pre.iter().enumerate() {
        n.c.emit(&format!("n1_pre_b{i}"), &r#ref(b));
    }

    let (h1, h1_pre) = n.neuron("xor_h1", &[2, -2], &[-1], &[r#ref("x1"), r#ref("x0")], 3, 4);
    let (h2, h2_pre) = n.neuron("xor_h2", &[-2, 2], &[-1], &[r#ref("x1"), r#ref("x0")], 3, 4);
    let (out, out_pre) = n.neuron("xor_out", &[2, 2], &[-1], &[r#ref(&h1), r#ref(&h2)], 3, 4);
    for (tag, pre) in [("h1", &h1_pre), ("h2", &h2_pre), ("out", &out_pre)] {
        for (i, b) in pre.iter().enumerate() {
            n.c.emit(&format!("xor_{tag}_pre_b{i}"), &r#ref(b));
        }
    }

    // ---------------- trained classifier (M10) ------------------------------
    let trained: ClsWeights =
        serde_json::from_str(&fs::read_to_string(scripts_dir.join("weights.json")).unwrap()).unwrap();
    let cls_bias = trained.bias;
    let cls_weights = trained.weights;
    let cls_inputs: Vec<String> = (0..9).map(|i| r#ref(&format!("g{i}"))).collect();
    let (cls_out, cls_pre) = n.neuron("cls", &cls_weights, &[cls_bias], &cls_inputs, 3, 5);
    for (i, b) in cls_pre.iter().enumerate() {
        n.c.emit(&format!("cls_pre_b{i}"), &r#ref(b));
    }

    // ---------------- M13: 14x14 paint canvas -> dilation -> OR4 downsample --
    // Placed before the classifier so mn0..mn48 exist as named signals the
    // weighted scores consume. Mirrors train/src/mnist.rs's dilate14_all +
    // block_downsample exactly (the trainer simulates THIS circuit).
    let mnist: MnistWeights = serde_json::from_str(
        &fs::read_to_string(scripts_dir.join("weights_mnist.json")).unwrap(),
    )
    .unwrap();
    let mnist_weights = mnist.weights;
    let mnist_bias = mnist.bias;
    let mnist_test_acc = mnist.test_accuracy;
    assert_eq!(
        mnist.canvas, 14,
        "weights_mnist.json canvas is {} -- this generator only knows the 14x14 grid",
        mnist.canvas
    );
    assert_eq!(
        mnist.dilate_iters, 1,
        "weights_mnist.json dilate_iters is {} -- the runtime circuit emits exactly one dilation stage",
        mnist.dilate_iters
    );
    assert_eq!(
        mnist.block_threshold, 1,
        "weights_mnist.json block_threshold is {} -- refusing to emit an OR tree for a popcount spec. \
         D-011 fixes T=1 as architecture: the 2x2 block downsample is a pure OR (any ink lights the bit); \
         T>1 would need popcount comparators that are not built here",
        mnist.block_threshold
    );

    // Dilation: dl{i} = OR(self, 4-neighbors); edge cells OR fewer.
    // 196 named signals consumed by the downsample below.
    let mut dl: Vec<String> = Vec::with_capacity(196);
    for r in 0..14usize {
        for col in 0..14usize {
            let i = r * 14 + col;
            let mut terms = vec![format!("mc{i}")];
            if r > 0 {
                terms.push(format!("mc{}", (r - 1) * 14 + col));
            }
            if r < 13 {
                terms.push(format!("mc{}", (r + 1) * 14 + col));
            }
            if col > 0 {
                terms.push(format!("mc{}", i - 1));
            }
            if col < 13 {
                terms.push(format!("mc{}", i + 1));
            }
            let mut acc = terms[0].clone();
            for (j, t) in terms.iter().enumerate().skip(1) {
                let last = j == terms.len() - 1;
                let name = if last { format!("dl{i}") } else { format!("dlo{i}_{j}") };
                acc = n.c.gate2(Gate::Or, &acc, Some(t), Some(&name));
            }
            dl.push(acc);
        }
    }
    // Block downsample: mn{b} = OR over the 2x2 dilated block -- the same
    // 49 named signals the classifier weighted scores have always consumed.
    let mnist_inputs: Vec<String> = (0..49)
        .map(|b| {
            let br = b / 7;
            let bc = b % 7;
            let (r0, c0) = (2 * br, 2 * bc);
            let cells = [dl[r0 * 14 + c0].clone(), dl[r0 * 14 + c0 + 1].clone(), dl[(r0 + 1) * 14 + c0].clone(), dl[(r0 + 1) * 14 + c0 + 1].clone()];
            let mut acc = cells[0].clone();
            for (j, t) in cells.iter().enumerate().skip(1) {
                let last = j == cells.len() - 1;
                let name = if last { format!("mn{b}") } else { format!("mno{b}_{j}") };
                acc = n.c.gate2(Gate::Or, &acc, Some(t), Some(&name));
            }
            acc
        })
        .collect();

    const SCORE_W: usize = 7;
    let mut mnist_scores: Vec<Vec<String>> = Vec::new();
    for k in 0..10 {
        let raw = n.weighted_score(
            &format!("mnist_c{k}"),
            &mnist_weights[k],
            mnist_bias[k],
            &mnist_inputs,
            SCORE_W,
        );
        let bits: Vec<String> = raw
            .iter()
            .enumerate()
            .map(|(i, b)| n.c.emit(&format!("mnist_score{k}_b{i}"), &r#ref(b)))
            .collect();
        mnist_scores.push(bits);
    }

    let (mnist_idx_raw, _mnist_maxscore, mnist_margin_raw) = n.c.argmax("mnist_argmax", &mnist_scores);
    let mnist_idx: Vec<String> = mnist_idx_raw
        .iter()
        .enumerate()
        .map(|(i, b)| n.c.emit(&format!("mnist_idx_b{i}"), &r#ref(b)))
        .collect();
    let mnist_margin: Vec<String> = mnist_margin_raw
        .iter()
        .enumerate()
        .map(|(i, b)| n.c.emit(&format!("mnist_margin_b{i}"), &r#ref(b)))
        .collect();

    let mnist_minterms_raw = n.c.digit_minterms("mnist_mt", &mnist_idx);
    let mnist_minterms: Vec<String> = mnist_minterms_raw
        .iter()
        .enumerate()
        .map(|(k, m)| n.c.emit(&format!("mnist_digit{k}"), &r#ref(m)))
        .collect();

    let mnist_segs_raw = n.c.sevenseg("mnist_seg", &mnist_minterms);
    let mnist_segs: Vec<String> = "abcdefg"
        .chars()
        .zip(mnist_segs_raw.iter())
        .map(|(letter, b)| n.c.emit(&format!("mnist_seg_{letter}"), &r#ref(b)))
        .collect();

    // ---------------- Mode B: native CSS arithmetic (comparison baseline) ---
    // Numeric var() operands can multiply directly in calc(). Gate mode is
    // an educational construction, not a workaround for a CSS restriction.
    let c = n.c;
    for (sig, expr) in [
        ("nb_h1pre", "calc((2 * var(--x1)) - (2 * var(--x0)) - 1)"),
        ("nb_h1", "max(0, min(1, calc(var(--nb_h1pre) + 1)))"),
        ("nb_h2pre", "calc((2 * var(--x0)) - (2 * var(--x1)) - 1)"),
        ("nb_h2", "max(0, min(1, calc(var(--nb_h2pre) + 1)))"),
        ("nb_outpre", "calc((2 * var(--nb_h1)) + (2 * var(--nb_h2)) - 1)"),
        ("nb_out", "max(0, min(1, calc(var(--nb_outpre) + 1)))"),
        ("nb_mv0", "calc((2 * var(--v1)) + (1 * var(--v0)))"),
        ("nb_mv1", "calc((1 * var(--v1)) + (2 * var(--v0)))"),
    ] {
        c.emit(sig, expr);
    }

    // ---------------- CSS ----------------------------------------------------
    let mut led_css_parts: Vec<String> = vec![
        led_css("g_not", "l_not"),
        led_css("g_and", "l_and"),
        led_css("g_or", "l_or"),
        led_css("g_xor", "l_xor"),
        led_css(&ha_s, "l_ha_s"),
        led_css(&ha_c, "l_ha_c"),
        led_css(&fa_s, "l_fa_s"),
        led_css(&fa_c, "l_fa_c"),
    ];
    led_css_parts.extend(s2.iter().enumerate().map(|(i, s)| led_css(s, &format!("l_add2_{i}"))));
    led_css_parts.extend(p2.iter().enumerate().map(|(i, p)| led_css(p, &format!("l_mul2_{i}"))));
    led_css_parts.extend(s4.iter().enumerate().map(|(i, s)| led_css(s, &format!("l_add4_{i}"))));
    led_css_parts.extend(dot_bits.iter().enumerate().map(|(i, b)| led_css(b, &format!("l_dot_{i}"))));
    led_css_parts.extend(row0.iter().enumerate().map(|(i, b)| led_css(b, &format!("l_mv0_{i}"))));
    led_css_parts.extend(row1.iter().enumerate().map(|(i, b)| led_css(b, &format!("l_mv1_{i}"))));
    led_css_parts.push(led_css(&n_out, "l_n_out"));
    led_css_parts.extend(n_pre.iter().enumerate().map(|(i, b)| led_css(b, &format!("l_npre_{i}"))));
    led_css_parts.push(led_css(&h1, "l_h1"));
    led_css_parts.push(led_css(&h2, "l_h2"));
    led_css_parts.push(led_css(&out, "l_xor_out"));
    led_css_parts.push(led_css("nb_h1", "l_nb_h1"));
    led_css_parts.push(led_css("nb_h2", "l_nb_h2"));
    led_css_parts.push(led_css("nb_out", "l_nb_out"));
    led_css_parts.push(led_css(&cls_out, "l_cls_out"));
    led_css_parts.extend(cls_pre.iter().enumerate().map(|(i, b)| led_css(b, &format!("l_clspre_{i}"))));
    led_css_parts.extend(
        "abcdefg"
            .chars()
            .zip(mnist_segs.iter())
            .map(|(letter, b)| led_css_lit(b, &format!("l_mn_seg_{letter}"), "#fabd2f")),
    );
    led_css_parts.extend(
        mnist_minterms
            .iter()
            .enumerate()
            .map(|(k, m)| text_led_css(m, &format!("l_mn_digit_{k}"))),
    );
    let led_css_all = led_css_parts.join("\n");

    // decimal view signals: native-calc conversions materialized as registered
    // properties (display-only; testable via computed style). (bits, signed)
    // -- signed views put the -2**(width-1) sign-bit coefficient on the MSB.
    let mut dec_specs: Vec<(String, Vec<String>, bool)> = vec![
        ("add2_dec".into(), s2.clone(), false),
        ("mul2_dec".into(), p2.clone(), false),
        ("add4_dec".into(), s4.clone(), false),
        ("dot_dec".into(), dot_bits.clone(), false),
        ("mv0_dec".into(), row0.clone(), false),
        ("mv1_dec".into(), row1.clone(), false),
        ("npre_dec".into(), n_pre.clone(), true),
        ("xor_dec".into(), vec![out.clone()], false),
        ("nb_h1pre_dec".into(), vec!["nb_h1pre".into()], false),
        ("nb_h2pre_dec".into(), vec!["nb_h2pre".into()], false),
        ("nb_outpre_dec".into(), vec!["nb_outpre".into()], false),
        ("nb_out_dec".into(), vec!["nb_out".into()], false),
        ("nb_mv0_dec".into(), vec!["nb_mv0".into()], false),
        ("nb_mv1_dec".into(), vec!["nb_mv1".into()], false),
        ("clspre_dec".into(), cls_pre.clone(), true),
    ];
    for k in 0..10 {
        dec_specs.push((format!("mnist_score{k}_dec"), mnist_scores[k].clone(), true));
    }
    dec_specs.push(("mnist_digit_dec".into(), mnist_idx.clone(), false));
    dec_specs.push(("mnist_margin_dec".into(), mnist_margin.clone(), false));

    for (sig, bits, signed) in &dec_specs {
        let last = bits.len() - 1;
        let terms: Vec<String> = bits
            .iter()
            .enumerate()
            .map(|(i, b)| {
                let coeff: i64 = if *signed && i == last { -(1i64 << i) } else { 1i64 << i };
                format!("({coeff} * var(--{b}))")
            })
            .collect();
        c.emit(sig, &format!("calc({})", terms.join(" + ")));
    }

    let dec_css_all: String = {
        let mut parts: Vec<String> = vec![
            dec_css("d_add2", "add2_dec"),
            dec_css("d_mul2", "mul2_dec"),
            dec_css("d_add4", "add4_dec"),
            dec_css("d_dot", "dot_dec"),
            dec_css("d_mv0", "mv0_dec"),
            dec_css("d_mv1", "mv1_dec"),
            dec_css("d_npre", "npre_dec"),
            dec_css("d_xor", "xor_dec"),
            dec_css("d_nb_h1pre", "nb_h1pre_dec"),
            dec_css("d_nb_h2pre", "nb_h2pre_dec"),
            dec_css("d_nb_outpre", "nb_outpre_dec"),
            dec_css("d_nb_out", "nb_out_dec"),
            dec_css("d_nb_mv0", "nb_mv0_dec"),
            dec_css("d_nb_mv1", "nb_mv1_dec"),
            dec_css("d_clspre", "clspre_dec"),
        ];
        for k in 0..10 {
            parts.push(dec_css(&format!("d_mnist_score{k}"), &format!("mnist_score{k}_dec")));
        }
        parts.push(dec_css("d_mnist_digit", "mnist_digit_dec"));
        parts.push(dec_css("d_mnist_margin", "mnist_margin_dec"));
        parts.join("\n")
    };

    let input_css: String = inputs
        .iter()
        .map(|name| format!("body.rt:has(#{name}:checked) {{ --{name}: 1; }}"))
        .collect::<Vec<_>>()
        .join("\n");

    // "network sees" preview cells: one per post-downsample mn{i} gate bit,
    // lit orange when the bit is 1 (same color-mix readout technique as the
    // LEDs; deliberately pixelated -- it shows the abstraction).
    let seen_css_all: String = (0..49)
        .map(|i| {
            format!(
                ".px_{} {{ background: color-mix(in srgb, #fe8019, #1d2021 calc((1 - var(--mn{})) * 100%)); }}",
                i, i
            )
        })
        .collect::<Vec<_>>()
        .join("\n");

    let extra = format!(
        "{}\n{BASE_CSS}\n{input_css}\n{led_css_all}\n{dec_css_all}\n{seen_css_all}",
        font_css(manifest_dir)
    );

    let n_signals = c.signals.len();

    // ---------------- body ----------------------------------------------------
    let canvas_cells: String = (0..196)
        .map(|i| {
            format!(
                r#"<label class="cell14"><input type="checkbox" id="mc{i}" aria-label="cell {},{}"></label>"#,
                i / 14,
                i % 14
            )
        })
        .collect();
    let seen_cells: String = (0..49).map(|i| format!(r#"<div class="px px_{i}"></div>"#)).collect();
    let digit_labels: String =
        (0..10).map(|k| format!(r#"<span class="l_mn_digit_{k}">{k}</span>"#)).collect();
    let g_cells: String = (0..9)
        .map(|i| {
            format!(
                r#"<label class="cell"><input type="checkbox" id="g{i}" aria-label="cell {},{}"></label>"#,
                i / 3,
                i % 3
            )
        })
        .collect();
    let score_spans: String = (0..10)
        .map(|k| format!(r#"<span class="kbd">{k}:</span> <span class="v d_mnist_score{k}"></span> "#))
        .collect();
    let leds_add2 = leds("l_add2", 3);
    let leds_mul2 = leds("l_mul2", 4);
    let leds_add4 = leds("l_add4", 5);
    let leds_dot = leds("l_dot", 5);
    let leds_mv0 = leds("l_mv0", 4);
    let leds_mv1 = leds("l_mv1", 4);
    let leds_npre = leds("l_npre", 4);
    let leds_clspre = leds("l_clspre", 5);
    let cls_weights_str = py_int_list(&cls_weights);
    let mnist_test_acc_pct = pct0(mnist_test_acc);

    let body = format!(
        r####"
<main class="wrap">
<h1>draw a digit</h1>
<p class="sub">a neural network in html + css. drag to paint — no grid, just ink; it guesses through dilation and downsample gates feeding a classifier compiled from mnist weights. the only javascript is a small deletable input shim; delete it and clicking still works.</p>

<div class="app">
  <div class="titlebar">
    <span class="titletext">untitled_digit.png — paint.css</span>
    <input type="reset" form="draw" value="[ clear ]">
  </div>
  <div class="stage">
    <form class="pad" id="draw">
      <div class="grid14" role="group" aria-label="14 by 14 paint canvas">
        {canvas_cells}
      </div>
      <p class="caption">draw big and centred. fill the box.</p>
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
        {digit_labels}
      </div>
      <div class="seenwrap">
        <div class="seen" role="img" aria-label="what the network sees, 7 by 7">
          {seen_cells}
        </div>
        <div class="seencap">network sees</div>
      </div>
    </div>
  </div>
  <div class="statusbar"><span class="idle">no ink · bias output</span> guess: <span class="d_mnist_digit"></span> · margin: <span class="d_mnist_margin"></span> · {mnist_test_acc_pct} on cropped, centred mnist</div>
</div>

<details class="hood">
<summary>under the hood: checkbox state → bits → gates → adders → popcount scores → argmax (this classifier)</summary>
<div class="ladder">building blocks: bits → gates → arithmetic → neurons.<br>The XOR network and digit classifier are separate demos, not consecutive layers.</div>

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
  <div class="row"><span class="kbd">a + b =</span> <span class="bits">{leds_add2}</span>
  <span class="v d_add2"></span> <span class="caption">4·2·1</span></div>
  <div class="row"><span class="kbd">a × b =</span> <span class="bits">{leds_mul2}</span>
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
  <div class="row"><span class="kbd">c + d =</span> <span class="bits">{leds_add4}</span>
  <span class="v d_add4"></span> <span class="caption">16·8·4·2·1</span>
  <span class="tag">5 full-adder stages, including the carry bit</span></div>
</section>

<section>
  <h2>7 · dot product u·v (two binary components each)</h2>
  <div class="row">
    <label><input type="checkbox" id="u1"> u1</label>
    <label><input type="checkbox" id="u0"> u0</label>
    <label><input type="checkbox" id="v1"> v1</label>
    <label><input type="checkbox" id="v0"> v0</label>
  </div>
  <div class="row"><span class="kbd">u₀v₀ + u₁v₁ =</span> <span class="bits">{leds_dot}</span>
  <span class="v d_dot"></span> <span class="caption">16·8·4·2·1</span>
  <span class="tag">two multipliers + shared ripple adder</span></div>
</section>

<section>
  <h2>8 · matrix × vector — W = [[2,1],[1,2]], x = (v₁,v₀)</h2>
  <div class="row"><span class="kbd">row 0</span> <span class="bits">{leds_mv0}</span>
  <span class="v d_mv0"></span> <span class="tag">= 2v₁ + 1v₀</span></div>
  <div class="row"><span class="kbd">row 1</span> <span class="bits">{leds_mv1}</span>
  <span class="v d_mv1"></span> <span class="tag">= 1v₁ + 2v₀</span></div>
  <div class="tag">fixed weights are build-time constants; weight × input uses gate-masked magnitudes</div>
</section>

<section>
  <h2>9 · neuron — y = step(+2x₁ − 2x₀ − 1)</h2>
  <div class="row"><span class="kbd">preactivation (4-bit two's complement)</span>
  <span class="bits">{leds_npre}</span> <span class="v d_npre"></span> <span class="caption">−8·4·2·1</span></div>
  <div class="row"><span class="kbd">activation</span> <span class="led l_n_out"></span>
  <span class="tag">= 1 if preactivation ≥ 0 (NOT the sign bit)</span></div>
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
  <div class="row"><span class="kbd">out = max(0, min(1, 2h1+2h2))</span> <span class="led l_nb_out"></span>
  <span class="v d_nb_out"></span></div>
  <div class="row"><span class="kbd">Wx row 0 / row 1</span> <span class="v d_nb_mv0"></span> / <span class="v d_nb_mv1"></span></div>
  <div class="tag">8 arithmetic declarations for XOR and the matrix rows, excluding display views.
  The gate-built XOR uses 177 gates. The whole page has {n_signals} registered signals, including inputs and views.
  CSS can multiply two numeric runtime values with calc(var(--a) * var(--b)).
  Gate mode shows how arithmetic is constructed; native mode shows how little CSS the same math needs.</div>
</section>

<section>
  <h2>12 · trained classifier — 3×3 glyph → “top bar” vs “left bar”</h2>
  <div class="tag">trained at build time by a plain perceptron (train/src/glyph.rs) on 9 exemplars; weights compiled into the gate netlist. bias = {cls_bias}, w = {cls_weights_str}. The digit classifier also has learned weights. The XOR weights are hand-picked.</div>
  <div class="grid" role="group" aria-label="3 by 3 glyph grid">
    {g_cells}
  </div>
  <div class="row"><span class="kbd">preactivation (5-bit signed)</span> <span class="bits">{leds_clspre}</span> <span class="v d_clspre"></span></div>
  <div class="row"><span class="kbd">class</span> <span class="led l_cls_out"></span>
  <span class="tag">1 = top bar, 0 = left bar / other</span></div>
</section>

<section>
  <h2>13 · drawn-digit classifier, readouts</h2>
  <div class="tag">the paint canvas and display live on the main page; these readouts tap the same circuit's signals. 14×14 invisible canvas cells → one round of 4-neighbor dilation (dl gates) → 2×2 block OR-downsample (mn bits) → the 49-input linear classifier, weights trained on MNIST at build time (train/src/mnist.rs), {mnist_test_acc_pct} on cropped, centred MNIST test digits.</div>
  <div class="row"><span class="kbd">margin, top1 - top2 (decimal view)</span> <span class="v d_mnist_margin"></span></div>
  <div class="row"><span class="kbd">predicted digit (index bits, decimal view)</span> <span class="v d_mnist_digit"></span></div>
  <div class="row"><span class="kbd">per-class scores (signed, decimal views)</span></div>
  <div class="row">
    {score_spans}
  </div>
  <div class="tag">
  argmax = tournament left-fold over the 10 class scores (ties keep the lowest digit); each score = popcount-decomposed
  weighted sum (weights ∈ [−3,3] via bit-planes P0/P1) + bias, all gate-composed at build time. Seven-segment display and
  digit strip read the argmax/minterm gate signals directly (LEDs); the numeric readouts above are native-calc views,
  outside the gate circuit, exactly like every other decimal readout on this page.
  </div>
</section>

<section>
  <h2>honesty label</h2>
  <div class="tag">
  Runtime: the network, displays and readouts are HTML + CSS only (no WASM, no network requests, works from file://). The single &lt;script&gt; on the page is an input shim that translates pointer drags into checkbox toggles. It calculates pointer positions, never network scores. Delete it and click cells to run the same inference.<br>
  Gates are named bit identities over native CSS min()/max()/calc() — the browser's arithmetic is the substrate; we compose circuits on top.<br>
  Decimal numbers in green are native-calc display views, outside the gate circuit. LEDs read gate signals directly.<br>
  The MNIST classifier (§13) follows the same split: the canvas's dilation and OR-downsample stages, argmax/minterm/segment signals are gates, the score, digit and margin numbers are native-calc views. No exception.<br>
  Generated by gen/ (Rust) at build time; rebuilds are deterministic.
  </div>
</section>

</details>

<footer>
<div class="sig">htmlnet/1.0 (HTML+CSS) Server at file:// Port 0</div>
<div class="tag"><a class="kbd" href="how-it-works.html">how it works</a> · <span class="kbd">make build</span> / <span class="kbd">make test</span></div>
</footer>
</main>
<script>
/* input shim: drag-to-paint. the network + display are pure CSS — delete
   this block and the page still works, one click per cell. */
(() => {{
  const grid = document.querySelector('.grid14');
  if (!grid) return;
  let mode = null, downBox = null, pid = null, lastX = 0, lastY = 0;
  const boxOf = e => {{ const c = e.target.closest('.cell14'); return c && c.querySelector('input'); }};
  const boxAt = (x, y) => {{ const c = document.elementFromPoint(x, y)?.closest('.cell14'); return c && c.querySelector('input'); }};
  grid.addEventListener('pointerdown', e => {{
    if (mode !== null || e.button !== 0) return; /* one stroke at a time: a second finger must not re-arm */
    const box = boxOf(e) || boxAt(e.clientX, e.clientY); if (!box) return;
    try {{ grid.setPointerCapture(e.pointerId); }} catch {{}} /* synthetic test pointers have no active id */
    mode = !box.checked; box.checked = mode; downBox = box; pid = e.pointerId; lastX = e.clientX; lastY = e.clientY;
  }});
  grid.addEventListener('pointerover', e => {{
    if (mode === null || e.pointerId !== pid) return;
    const box = boxOf(e); if (box) box.checked = mode;
  }});
  grid.addEventListener('pointermove', e => {{
    if (mode === null || e.pointerId !== pid) return;
    if ((e.buttons & 1) === 0) {{ mode = null; pid = null; return; }} /* primary contact gone (missed pointerup) */
    const dx = e.clientX - lastX, dy = e.clientY - lastY;
    const steps = Math.max(1, Math.ceil(Math.hypot(dx, dy) / 16)); /* half of the 32px cell pitch */
    for (let i = 1; i <= steps; i++) {{ const box = boxAt(lastX + dx * i / steps, lastY + dy * i / steps); if (box) box.checked = mode; }}
    lastX = e.clientX; lastY = e.clientY;
  }});
  grid.addEventListener('click', e => {{
    const box = boxOf(e);
    if (box && box === downBox) e.preventDefault(); /* already painted on pointerdown */
    downBox = null; /* one-shot: keyboard toggles must not be suppressed */
  }});
  addEventListener('pointerup', e => {{ if (e.pointerId === pid) {{ mode = null; pid = null; }} }});
  addEventListener('pointercancel', e => {{ /* no click follows a cancel: also drop the suppression latch */
    if (e.pointerId === pid) {{ mode = null; pid = null; downBox = null; }} }});
}})();
</script>
"####
    );

    let body = if no_js {
        let (markup, _) = body.split_once("<script>").expect("input script boundary");
        markup
            .replace("drag to paint — no grid, just ink", "click cells to draw")
            .replace(
                "the only javascript is a small deletable input shim; delete it and clicking still works.",
                "this build contains no javascript. click once per cell; clear resets the drawing.",
            )
            .replace(
                "The single &lt;script&gt; on the page is an input shim that translates pointer drags into checkbox toggles. It calculates pointer positions, never network scores. Delete it and click cells to run the same inference.",
                "This build contains no JavaScript. Native checkbox clicks change inputs; CSS computes every network output.",
            )
    } else {
        body
    };
    let html = render(c, &extra, &body, "htmlnet — draw a digit, the network is pure CSS");
    if let Some(parent) = Path::new(&out_path).parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).unwrap();
        }
    }
    fs::write(&out_path, &html).unwrap();
    println!("wrote {out_path}: {n_signals} signals, {} bytes", html.len());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn glyph_schema_rejects_missing_or_extra_pixels() {
        for count in [8, 10] {
            let json = serde_json::json!({"bias": 0, "weights": vec![0; count]});
            assert!(serde_json::from_value::<ClsWeights>(json).is_err(), "accepted {count} glyph weights");
        }
    }

    #[test]
    fn digit_schema_rejects_missing_or_extra_classes() {
        let shipped: serde_json::Value = serde_json::from_str(include_str!("../../scripts/weights_mnist.json")).unwrap();
        for count in [9, 11] {
            for field in ["weights", "bias"] {
                let mut json = shipped.clone();
                let entry = json[field][0].clone();
                json[field] = serde_json::json!(vec![entry; count]);
                assert!(serde_json::from_value::<MnistWeights>(json).is_err(), "accepted {count} {field} rows");
            }
        }
    }
}
