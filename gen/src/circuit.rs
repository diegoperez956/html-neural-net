//! Build-time circuit compiler. Named CSS signals compose arithmetic and
//! fixed-weight inference. The original Python compiler was retired in D-008.

/// `ref(name)` in python: var(--name)
pub fn r#ref(name: &str) -> String {
    format!("var(--{})", name)
}

fn is_name(x: &str) -> bool {
    let b = x.as_bytes();
    if b.is_empty() {
        return false;
    }
    let first = b[0];
    if !(first.is_ascii_alphabetic() || first == b'_') {
        return false;
    }
    b[1..].iter().all(|c| c.is_ascii_alphanumeric() || *c == b'_' || *c == b'-')
}

/// `_op`: normalize a circuit operand. Plain identifiers become refs;
/// '0'/'1' and expression fragments pass through untouched.
pub(crate) fn op(x: &str) -> String {
    if x == "0" || x == "1" {
        return x.to_string();
    }
    for p in ["var(", "calc(", "min(", "max("] {
        if x.starts_with(p) {
            return x.to_string();
        }
    }
    if is_name(x) {
        return r#ref(x);
    }
    x.to_string()
}

pub fn not_e(a: &str) -> String {
    format!("calc(1 - ({a}))")
}
pub fn and_e(a: &str, b: &str) -> String {
    format!("min({a}, {b})")
}
pub fn or_e(a: &str, b: &str) -> String {
    format!("max({a}, {b})")
}
pub fn xor_e(a: &str, b: &str) -> String {
    format!("calc(max({a}, {b}) - min({a}, {b}))")
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Gate {
    Not,
    And,
    Or,
    Xor,
}
impl Gate {
    fn lower(&self) -> &'static str {
        match self {
            Gate::Not => "not",
            Gate::And => "and",
            Gate::Or => "or",
            Gate::Xor => "xor",
        }
    }
}

/// Ordered signal table; insertion order IS the output order (python dict).
pub struct Circuit {
    pub signals: Vec<(String, String)>,
    seen: std::collections::HashSet<String>,
}

impl Default for Circuit {
    fn default() -> Self {
        Self::new()
    }
}

impl Circuit {
    pub fn new() -> Self {
        Circuit { signals: Vec::new(), seen: Default::default() }
    }

    pub fn emit(&mut self, name: &str, expr: &str) -> String {
        assert!(self.seen.insert(name.to_string()), "duplicate signal {name}");
        self.signals.push((name.to_string(), expr.to_string()));
        name.to_string()
    }

    pub fn gate2(&mut self, kind: Gate, a: &str, b: Option<&str>, name: Option<&str>) -> String {
        let a = op(a);
        let b = b.map(op);
        let expr = match (kind, &b) {
            (Gate::Not, _) => not_e(&a),
            (Gate::And, Some(b)) => and_e(&a, b),
            (Gate::Or, Some(b)) => or_e(&a, b),
            (Gate::Xor, Some(b)) => xor_e(&a, b),
            _ => panic!("binary gate without operand"),
        };
        let name = match name {
            Some(n) => n.to_string(),
            None => format!("{}_{}", kind.lower(), self.signals.len()),
        };
        self.emit(&name, &expr)
    }

    pub fn gate(&mut self, kind: Gate, a: &str, name: &str) -> String {
        self.gate2(kind, a, None, Some(name))
    }

    pub fn half_adder(&mut self, name: &str, a: &str, b: &str) -> (String, String) {
        let s = self.gate2(Gate::Xor, a, Some(b), Some(&format!("{name}_sum")));
        let c = self.gate2(Gate::And, a, Some(b), Some(&format!("{name}_carry")));
        (s, c)
    }

    pub fn full_adder(&mut self, name: &str, a: &str, b: &str, cin: &str) -> (String, String) {
        let (a, b, cin) = (op(a), op(b), op(cin));
        let s1 = self.gate2(Gate::Xor, &a, Some(&b), Some(&format!("{name}_s1")));
        let c1 = self.gate2(Gate::And, &a, Some(&b), Some(&format!("{name}_c1")));
        let s = self.gate2(
            Gate::Xor,
            &r#ref(&s1),
            Some(&cin),
            Some(&format!("{name}_sum")),
        );
        let c2 = self.gate2(
            Gate::And,
            &r#ref(&s1),
            Some(&cin),
            Some(&format!("{name}_c2")),
        );
        let cout = self.gate2(Gate::Or, &r#ref(&c1), Some(&r#ref(&c2)), Some(&format!("{name}_carry")));
        (s, cout)
    }

    /// N-bit ripple adder over LSB-first operand lists (signal names, refs,
    /// or literals). Returns LSB-first sum signal names.
    pub fn ripple_add(&mut self, name: &str, a_bits: &[String], b_bits: &[String], cin: &str) -> Vec<String> {
        let mut outs = Vec::new();
        let mut carry = op(cin);
        for (i, (ab, bb)) in a_bits.iter().zip(b_bits.iter()).enumerate() {
            let (s, c) = self.full_adder(&format!("{name}_b{i}"), ab, bb, &carry);
            outs.push(s);
            carry = r#ref(&c);
        }
        outs
    }

    /// Unsigned structural multiplication; partial products are AND gates,
    /// rows folded with ripple adders. Returns LSB-first product bits.
    pub fn unsigned_mult(&mut self, name: &str, a_bits: &[String], b_bits: &[String]) -> Vec<String> {
        let w = a_bits.len() + b_bits.len();
        let mut rows: Vec<Vec<String>> = Vec::new();
        for (j, bj) in b_bits.iter().enumerate() {
            let mut row: Vec<String> = vec!["0".to_string(); j];
            for (i, ai) in a_bits.iter().enumerate() {
                row.push(self.gate2(Gate::And, ai, Some(bj), Some(&format!("{name}_pp{i}_{j}"))));
            }
            row.extend(std::iter::repeat("0".to_string()).take(w - j - a_bits.len()));
            rows.push(row);
        }
        let mut acc = rows.remove(0);
        let n_rows = rows.len() + 1;
        for k in 1..n_rows {
            let next = rows.remove(0);
            acc = self.ripple_add(&format!("{name}_row{k}"), &acc, &next, "0");
        }
        acc
    }
}

impl Circuit {
    /// Carry-save popcount (python popcount): fold 3 wires of equal weight
    /// into a full adder, 2 into a half adder, single ordered pass.
    pub fn popcount(&mut self, name: &str, bits: &[String]) -> Vec<String> {
        assert!(!bits.is_empty(), "{name}: popcount needs at least one input");
        let mut cols: std::collections::HashMap<usize, Vec<String>> = Default::default();
        cols.insert(0, bits.iter().map(|b| op(b)).collect());
        let mut max_w = 0usize;
        let mut result: Vec<String> = Vec::new();
        let mut k = 0usize;
        let mut w = 0usize;
        while w <= max_w {
            let mut col = cols.remove(&w).unwrap_or_default();
            while col.len() >= 3 {
                let (s, cy) = self.full_adder(
                    &format!("{name}_pc{w}_{k}"), &col[0], &col[1], &col[2]);
                k += 1;
                col = col[3..].to_vec();
                col.push(r#ref(&s));
                cols.entry(w + 1).or_default().push(r#ref(&cy));
                max_w = max_w.max(w + 1);
            }
            if col.len() == 2 {
                let (s, cy) = self.half_adder(
                    &format!("{name}_pc{w}_{k}"), &col[0], &col[1]);
                k += 1;
                col = vec![r#ref(&s)];
                cols.entry(w + 1).or_default().push(r#ref(&cy));
                max_w = max_w.max(w + 1);
            }
            result.push(if col.is_empty() { "0".to_string() } else { col[0].clone() });
            w += 1;
        }
        result
    }

    /// Tournament left-fold argmax with streaming top-2 (matches the current
    /// python argmax: ties keep the lowest index). incumbent vs challenger
    /// each round via one folded subtraction; a second folded subtraction
    /// (reusing the challenger's NOT gates) advances the runner-up track.
    /// Returns (idx_bits, winning_score_bits, margin_bits) LSB-first.
    pub fn argmax(&mut self, name: &str, scores: &[Vec<String>])
        -> (Vec<String>, Vec<String>, Vec<String>)
    {
        let n = scores.len();
        assert!(n >= 1);
        let width = scores[0].len();
        assert!(scores.iter().all(|s| s.len() == width));
        let idx_width = if n == 1 { 1 } else { (n - 1).ilog2() as usize + 1 };
        let ext_w = width + 1;

        let sext = |bits: &[String]| -> Vec<String> {
            let mut v = bits.to_vec();
            while v.len() < ext_w {
                let last = v.last().unwrap().clone();
                v.push(last);
            }
            v
        };
        let bits_of = |v: i64, w: usize| -> Vec<String> {
            (0..w).map(|i| if (v >> i) & 1 == 1 { "1".into() } else { "0".into() }).collect()
        };

        let mut inc_score = scores[0].clone();
        let mut inc_idx = bits_of(0, idx_width);
        let mut run_score = bits_of(-(1i64 << (width - 1)), width); // min signed value

        for r in 1..n {
            let chal_score = scores[r].clone();
            let chal_idx = bits_of(r as i64, idx_width);
            let not_chal: Vec<String> = sext(&chal_score).iter().enumerate()
                .map(|(i, b)| self.gate(Gate::Not, b, &format!("{name}_r{r}_nc{i}")))
                .collect();
            let diff = self.ripple_add(
                &format!("{name}_r{r}_diff"), &sext(&inc_score), &not_chal, "1");
            let s = diff[diff.len() - 1].clone();
            let ns = self.gate(Gate::Not, &r#ref(&s), &format!("{name}_r{r}_ns"));
            let diff2 = self.ripple_add(
                &format!("{name}_r{r}_d2"), &sext(&run_score), &not_chal, "1");
            let s2 = diff2[diff2.len() - 1].clone();
            let ns2 = self.gate(Gate::Not, &r#ref(&s2), &format!("{name}_r{r}_ns2"));
            let (s_ref, ns_ref, s2_ref, ns2_ref) =
                (r#ref(&s), r#ref(&ns), r#ref(&s2), r#ref(&ns2));

            // mux(inc_bit, chal_bit, tag): out = OR(AND(s,chal), AND(ns,inc))
            let mux = |slf: &mut Self, cond: &str, ncond: &str,
                           hit_bit: &str, keep_bit: &str, tag: &str| -> String {
                let hit = slf.gate2(Gate::And, cond, Some(&op(hit_bit)),
                    Some(&format!("{name}_r{r}_{tag}_hit")));
                let keep = slf.gate2(Gate::And, ncond, Some(&op(keep_bit)),
                    Some(&format!("{name}_r{r}_{tag}_keep")));
                slf.gate2(Gate::Or, &r#ref(&hit), Some(&r#ref(&keep)),
                    Some(&format!("{name}_r{r}_{tag}_out")))
            };

            // runner-up candidate: rises to the challenger iff chal > runner-up
            let mut run_up = Vec::with_capacity(width);
            for i in 0..width {
                run_up.push(mux(self, &s2_ref, &ns2_ref, &chal_score[i], &run_score[i],
                    &format!("u{i}")));
            }
            // if the challenger wins, the old incumbent becomes the new runner-up
            let mut new_run = Vec::with_capacity(width);
            for i in 0..width {
                new_run.push(mux(self, &s_ref, &ns_ref, &inc_score[i], &run_up[i],
                    &format!("n{i}")));
            }
            let mut new_score = Vec::with_capacity(width);
            for i in 0..width {
                new_score.push(mux(self, &s_ref, &ns_ref, &chal_score[i], &inc_score[i],
                    &format!("s{i}")));
            }
            let mut new_idx = Vec::with_capacity(idx_width);
            for i in 0..idx_width {
                new_idx.push(mux(self, &s_ref, &ns_ref, &chal_idx[i], &inc_idx[i],
                    &format!("i{i}")));
            }
            inc_score = new_score;
            inc_idx = new_idx;
            run_score = new_run;
        }

        let not_run: Vec<String> = sext(&run_score).iter().enumerate()
            .map(|(i, b)| self.gate(Gate::Not, b, &format!("{name}_mnr{i}")))
            .collect();
        let margin = self.ripple_add(
            &format!("{name}_margin"), &sext(&inc_score), &not_run, "1");
        (inc_idx, inc_score, margin)
    }

    /// One AND-tree minterm per value 0..2^len-1 (NOTs emitted once per bit).
    pub fn digit_minterms(&mut self, name: &str, idx_bits: &[String]) -> Vec<String> {
        let nots: Vec<String> = idx_bits.iter().enumerate()
            .map(|(i, b)| self.gate(Gate::Not, b, &format!("{name}_not{i}")))
            .collect();
        let mut minterms = Vec::new();
        for val in 0..(1usize << idx_bits.len()) {
            let terms: Vec<String> = (0..idx_bits.len())
                .map(|i| if (val >> i) & 1 == 1 { r#ref(&idx_bits[i]) } else { r#ref(&nots[i]) })
                .collect();
            let mut acc = terms[0].clone();
            let mut acc_name: Option<String> = None;
            for (i, t) in terms.iter().enumerate().skip(1) {
                acc_name = Some(self.gate2(Gate::And, &acc, Some(t),
                                          Some(&format!("{name}_m{val}_and{i}"))));
                acc = r#ref(acc_name.as_ref().unwrap());
            }
            minterms.push(acc_name.unwrap());
        }
        minterms
    }

    /// Segment -> lit digits (python SEVENSEG_MAP).
    const SEVENSEG: [(&str, &[u8]); 7] = [
        ("a", &[0, 2, 3, 5, 6, 7, 8, 9]),
        ("b", &[0, 1, 2, 3, 4, 7, 8, 9]),
        ("c", &[0, 1, 3, 4, 5, 6, 7, 8, 9]),
        ("d", &[0, 2, 3, 5, 6, 8, 9]),
        ("e", &[0, 2, 6, 8]),
        ("f", &[0, 4, 5, 6, 8, 9]),
        ("g", &[2, 3, 4, 5, 6, 8, 9]),
    ];

    /// 7 segment signals, each an OR-tree of its lit digits' minterms.
    pub fn sevenseg(&mut self, name: &str, minterms: &[String]) -> Vec<String> {
        let mut segs = Vec::new();
        for (seg, digits) in Self::SEVENSEG {
            let mut acc_name = minterms[digits[0] as usize].clone();
            let mut acc = r#ref(&acc_name);
            for &d in &digits[1..] {
                acc_name = self.gate2(Gate::Or, &acc, Some(&r#ref(&minterms[d as usize])),
                                      Some(&format!("{name}_{seg}_or{d}")));
                acc = r#ref(&acc_name);
            }
            segs.push(acc_name);
        }
        segs
    }
}

// --------------------------------------------------------------- network math

/// Fixed-weight network building blocks over a Circuit (python `Net`).
pub struct Net<'a> {
    pub c: &'a mut Circuit,
}

impl<'a> Net<'a> {
    pub fn new(c: &'a mut Circuit) -> Self {
        Net { c }
    }

    /// Two's complement constant, LSB-first list of literal '0'/'1'.
    pub fn const_bits(&self, value: i64, width: usize) -> Vec<String> {
        let mask = (1i64 << width) - 1;
        let v = value & mask;
        (0..width).map(|i| if (v >> i) & 1 == 1 { "1".to_string() } else { "0".to_string() }).collect()
    }

    /// Threshold neuron. weights: signed ints (|w| < 2**(pwidth-1)), biases:
    /// signed ints, inputs: bit signal names. Products are built by
    /// structural negation of bit-masked magnitudes (real gates, no
    /// multiplier shortcut), summed by ripple adders. Returns (output_bit,
    /// sum_bits_lsb).
    pub fn neuron(&mut self, name: &str, weights: &[i64], biases: &[i64], inputs: &[String],
                  pwidth: usize, swidth: usize) -> (String, Vec<String>) {
        let mut terms: Vec<Vec<String>> = Vec::new();
        for (i, (w, x)) in weights.iter().zip(inputs.iter()).enumerate() {
            let mag = w.abs();
            let sign = *w < 0;
            let mag_bits = self.const_bits(mag, pwidth);
            let masked: Vec<String> = mag_bits.iter().enumerate()
                .map(|(j, mb)| self.c.gate2(Gate::And, mb, Some(x), Some(&format!("{name}_t{i}_m{j}"))))
                .collect();
            let masked = if sign {
                let nb: Vec<String> = masked.iter().enumerate()
                    .map(|(j, b)| self.c.gate(Gate::Not, b, &format!("{name}_t{i}_n{j}")))
                    .collect();
                self.c.ripple_add(&format!("{name}_t{i}_neg"), &nb, &vec!["0".to_string(); pwidth], "1")
            } else {
                masked
            };
            terms.push(masked);
        }

        let sext = |bits: &[String]| -> Vec<String> {
            let mut v = bits.to_vec();
            while v.len() < swidth {
                let last = v.last().unwrap().clone();
                v.push(last);
            }
            v
        };

        let mut acc = if terms.is_empty() {
            vec!["0".to_string(); swidth]
        } else {
            sext(&terms[0])
        };
        for t in terms.iter().skip(1) {
            let add_name = format!("{name}_add{}", self.c.signals.len());
            acc = self.c.ripple_add(&add_name, &acc, &sext(t), "0");
        }
        for b in biases {
            let bias_name = format!("{name}_bias{}", self.c.signals.len());
            let bias_bits = self.const_bits(*b, swidth);
            acc = self.c.ripple_add(&bias_name, &acc, &bias_bits, "0");
        }
        let sign_bit = acc[acc.len() - 1].clone();
        let out = self.c.gate(Gate::Not, &r#ref(&sign_bit), &format!("{name}_out"));
        (out, acc)
    }

    /// Per-class weighted sum for integer weights in [-3,3] over bit signals,
    /// plus integer bias, as width-bit signed two's complement. Weight
    /// magnitude is decomposed into two bit-planes (P0: |w| in {1,3}, P1: |w|
    /// in {2,3}), separately for positive/negative w; each plane's popcount
    /// (restricted to lit inputs) gives its contribution directly (P1 doubled
    /// via a "0" prefix / shift-left-1). score = pos - neg + bias. Asserts
    /// (from the actual weights/bias) that popcount planes and the final
    /// score fit signed `width` bits. Returns the score bits, LSB-first.
    pub fn weighted_score(&mut self, name: &str, weights: &[i64], bias: i64, inputs: &[String],
                           width: usize) -> Vec<String> {
        assert_eq!(weights.len(), inputs.len());
        assert!(weights.iter().all(|&w| (-3..=3).contains(&w)), "{name}: weight magnitude > 3");

        let plane = |pred: &dyn Fn(i64) -> bool| -> Vec<String> {
            weights.iter().zip(inputs.iter())
                .filter(|(w, _)| pred(**w))
                .map(|(_, x)| x.clone())
                .collect()
        };
        let p0pos = plane(&|w| w > 0 && (w.abs() == 1 || w.abs() == 3));
        let p1pos = plane(&|w| w > 0 && (w.abs() == 2 || w.abs() == 3));
        let p0neg = plane(&|w| w < 0 && (w.abs() == 1 || w.abs() == 3));
        let p1neg = plane(&|w| w < 0 && (w.abs() == 2 || w.abs() == 3));

        let pos_max = (p0pos.len() + 2 * p1pos.len()) as i64;
        let neg_max = (p0neg.len() + 2 * p1neg.len()) as i64;
        let lo = -(1i64 << (width - 1));
        let hi = (1i64 << (width - 1)) - 1;
        assert!(pos_max <= hi && neg_max <= hi,
            "{name}: popcount plane too large for width {width} (pos_max={pos_max}, neg_max={neg_max})");
        let score_max = bias + pos_max;
        let score_min = bias - neg_max;
        assert!(lo <= score_min && score_max <= hi,
            "{name}: score range [{score_min},{score_max}] does not fit signed width {width} [{lo},{hi}]");

        let zext = |bits: &[String]| -> Vec<String> {
            let pad = width as isize - bits.len() as isize;
            assert!(pad >= 0, "{name}: popcount output wider than width {width}");
            let mut v = bits.to_vec();
            v.extend(std::iter::repeat("0".to_string()).take(pad as usize));
            v
        };

        let p0pos_c = if p0pos.is_empty() { vec!["0".to_string()] } else { self.c.popcount(&format!("{name}_p0pos"), &p0pos) };
        let p1pos_c = if p1pos.is_empty() { vec!["0".to_string()] } else { self.c.popcount(&format!("{name}_p1pos"), &p1pos) };
        let mut p1pos_shifted = vec!["0".to_string()];
        p1pos_shifted.extend(p1pos_c);
        let pos = self.c.ripple_add(&format!("{name}_pos"), &zext(&p0pos_c), &zext(&p1pos_shifted), "0");

        let p0neg_c = if p0neg.is_empty() { vec!["0".to_string()] } else { self.c.popcount(&format!("{name}_p0neg"), &p0neg) };
        let p1neg_c = if p1neg.is_empty() { vec!["0".to_string()] } else { self.c.popcount(&format!("{name}_p1neg"), &p1neg) };
        let mut p1neg_shifted = vec!["0".to_string()];
        p1neg_shifted.extend(p1neg_c);
        let neg = self.c.ripple_add(&format!("{name}_neg"), &zext(&p0neg_c), &zext(&p1neg_shifted), "0");

        let not_neg: Vec<String> = neg.iter().enumerate()
            .map(|(i, b)| self.c.gate(Gate::Not, b, &format!("{name}_notneg{i}")))
            .collect();
        let diff = self.c.ripple_add(&format!("{name}_diff"), &pos, &not_neg, "1");
        let bias_bits = self.const_bits(bias, width);
        self.c.ripple_add(&format!("{name}_score"), &diff, &bias_bits, "0")
    }

}

// ------------------------------------------------------------------ rendering

/// Renders the full HTML page: `@property` declarations (sorted by name),
/// `.rt` signal declarations (insertion order), extra CSS and body.
pub fn render(c: &Circuit, extra_css: &str, body: &str, title: &str) -> String {
    let mut names: Vec<&str> = c.signals.iter().map(|(n, _)| n.as_str()).collect();
    names.sort_unstable();
    let props = names.iter()
        .map(|n| format!("@property --{n} {{ syntax: \"<integer>\"; inherits: true; initial-value: 0; }}"))
        .collect::<Vec<_>>()
        .join("\n");
    let decls = c.signals.iter()
        .map(|(n, e)| format!(".rt {{ --{n}: {e}; }}"))
        .collect::<Vec<_>>()
        .join("\n");
    format!(
        "<!DOCTYPE html>\n\
<html lang=\"en\">\n\
<head>\n\
<meta charset=\"utf-8\">\n\
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n\
<title>{title}</title>\n\
<style>\n\
{extra_css}\n\
\n\
{props}\n\
\n\
/* generated netlist — composed at build time from gate primitives */\n\
{decls}\n\
</style>\n\
</head>\n\
<body class=\"rt\">\n\
{body}\n\
</body>\n\
</html>\n"
    )
}
