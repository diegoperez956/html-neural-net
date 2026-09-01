//! M12 part 1: 49 -> H=16 -> 10 MLP trainer, per docs/DESIGN_MLP.md.
//!
//! Replaces the linear trainer as the shipped `mnist` command (mnist.rs's
//! `run()` stays in the tree as the honest linear baseline -- see
//! train/README.md -- reachable via the `linear` CLI verb, and reused here
//! for its preprocessing pipeline and the val/test split).
//!
//! Hard constraints from the CSS circuit (docs/DESIGN_MLP.md), not
//! negotiable:
//!   1. Weights quantize to integers in [-3,3].
//!   2. Per-neuron plane budget: sum of POSITIVE weights and sum of |NEGATIVE
//!      weights| must each stay <= PLANE_BUDGET (~60, 7-bit signed headroom).
//!      (`gen/src/circuit.rs`'s `weighted_score` shows this is exactly
//!      popcount(plane0) + 2*popcount(plane1) per sign, which collapses to
//!      sum(|w|) per sign since a weight of magnitude m contributes m to that
//!      sum regardless of which plane(s) it sets.)
//!   3. Hidden activation is the sign bit: h_out = 1 if score_h >= 0 else 0.
//!   4. Output layer (H=16 -> 10) keeps 7-bit scores; budget is automatically
//!      satisfied there (max possible sum = 16*3 = 48 < 60), so only the
//!      hidden layer needs pruning.

use crate::mnist;
use crate::rng::Rng;
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

const H: usize = 16;
const NPIX: usize = mnist::NPIX; // 49
const NUM_CLASSES: usize = 10;
const WIDTH: i64 = 7; // signed score width the circuit uses for both layers
const SCORE_HI: i64 = (1 << (WIDTH - 1)) - 1; // 63
const SCORE_LO: i64 = -(1 << (WIDTH - 1)); // -64
const PLANE_BUDGET: i64 = 60; // slack under 63 for bias headroom, per design doc

// Reuses the honest threshold Job 1 selected against validation (t=0.2,
// train/README.md) rather than re-running that search -- same preprocessing,
// same split, so the two architectures are compared apples-to-apples.
const THRESHOLD: f64 = 0.2;

// Honest linear baseline this MLP must clear (train/README.md, Job 1 of
// M12): test accuracy 0.8189 at t=0.2, seed=10, selected against a held-out
// validation split, never against the test set.
const LINEAR_BASELINE_TEST_ACC: f64 = 0.8189;

const EPOCHS: usize = 60;
const RETRAIN_EPOCHS: usize = 2;
const LR: f64 = 0.05;
// Straight-through estimator: forward pass uses the real sign-threshold
// (matches the circuit exactly), backward pretends the threshold were a
// hard-tanh clipped to [-STE_WIDTH, STE_WIDTH] so gradient can flow at all.
// Standard BNN training trick (Bengio et al. 2013 straight-through
// estimator) -- needed because the actual activation (a sign bit) has zero
// gradient almost everywhere.
const STE_WIDTH: f64 = 1.0;

// Single fixed init seed. Not scanned against anything (that was the D-007
// mistake for the shuffle seed) -- one seed, documented, done.
const INIT_SEED: u64 = 1;
const EPOCH_SHUFFLE_SEED: u64 = 2;

type Mat = Vec<Vec<f64>>;

struct FloatMlp {
    hw: Mat,      // H x NPIX
    hb: Vec<f64>, // H
    ow: Mat,      // NUM_CLASSES x H
    ob: Vec<f64>, // NUM_CLASSES
}

fn init_mlp() -> FloatMlp {
    let mut rng = Rng::new(INIT_SEED);
    let hidden_scale = 1.0 / (NPIX as f64).sqrt();
    let output_scale = 1.0 / (H as f64).sqrt();
    let mut rand_signed = |scale: f64| (rng.next_f64() * 2.0 - 1.0) * scale;
    let hw = (0..H).map(|_| (0..NPIX).map(|_| rand_signed(hidden_scale)).collect()).collect();
    let hb = vec![0.0; H];
    let ow = (0..NUM_CLASSES).map(|_| (0..H).map(|_| rand_signed(output_scale)).collect()).collect();
    let ob = vec![0.0; NUM_CLASSES];
    FloatMlp { hw, hb, ow, ob }
}

/// Forward pass shared shape for float (pre-quantization) training and eval:
/// hidden pre-activations, hidden binary outputs, output scores.
fn forward(m: &FloatMlp, x: &[u8]) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
    let zh: Vec<f64> = (0..H)
        .map(|h| m.hb[h] + (0..NPIX).map(|i| m.hw[h][i] * x[i] as f64).sum::<f64>())
        .collect();
    let ah: Vec<f64> = zh.iter().map(|&z| if z >= 0.0 { 1.0 } else { 0.0 }).collect();
    let zk: Vec<f64> = (0..NUM_CLASSES)
        .map(|k| m.ob[k] + (0..H).map(|h| m.ow[k][h] * ah[h]).sum::<f64>())
        .collect();
    (zh, ah, zk)
}

fn softmax(z: &[f64]) -> Vec<f64> {
    let max = z.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let exps: Vec<f64> = z.iter().map(|&v| (v - max).exp()).collect();
    let sum: f64 = exps.iter().sum();
    exps.iter().map(|&v| v / sum).collect()
}

fn predict_float(m: &FloatMlp, x: &[u8]) -> usize {
    let (_, _, zk) = forward(m, x);
    argmax(&zk)
}

fn argmax(v: &[f64]) -> usize {
    let mut best = 0;
    for i in 1..v.len() {
        if v[i] > v[best] {
            best = i;
        }
    }
    best
}

fn accuracy_float(m: &FloatMlp, xs: &[Vec<u8>], ys: &[u8]) -> f64 {
    let correct = xs.iter().zip(ys).filter(|(x, &y)| predict_float(m, x) == y as usize).count();
    correct as f64 / xs.len() as f64
}

/// One epoch of per-sample SGD with a straight-through estimator for the
/// hidden layer's sign-threshold activation. `hidden_mask` (if given) keeps
/// pruned hidden weights pinned at exactly zero -- the "retrain surviving
/// weights" step after pruning.
fn train_epoch(m: &mut FloatMlp, xs: &[Vec<u8>], ys: &[u8], order: &[usize], hidden_mask: Option<&[Vec<bool>]>) {
    for &idx in order {
        let x = &xs[idx];
        let y = ys[idx] as usize;
        let (zh, ah, zk) = forward(m, x);
        let probs = softmax(&zk);

        let mut dout = probs;
        dout[y] -= 1.0;

        // dA[h] = sum_k dout[k] * ow[k][h], computed against the PRE-update
        // output weights (captured before we touch them below).
        let mut da = vec![0.0; H];
        for h in 0..H {
            da[h] = (0..NUM_CLASSES).map(|k| dout[k] * m.ow[k][h]).sum();
        }

        for k in 0..NUM_CLASSES {
            for h in 0..H {
                m.ow[k][h] -= LR * dout[k] * ah[h];
            }
            m.ob[k] -= LR * dout[k];
        }

        for h in 0..H {
            let ste = if zh[h].abs() < STE_WIDTH { 1.0 } else { 0.0 };
            let dz = da[h] * ste;
            for i in 0..NPIX {
                if let Some(mask) = hidden_mask {
                    if !mask[h][i] {
                        continue; // pruned: stays exactly zero
                    }
                }
                m.hw[h][i] -= LR * dz * x[i] as f64;
            }
            m.hb[h] -= LR * dz;
        }
    }
}

// ---------- per-neuron quantization (prune + quantize in one step) ----------

fn clip3(v: i64) -> i64 {
    v.max(-3).min(3)
}

/// pos/neg plane-budget sums for one neuron's already-quantized weights.
fn plane_sums(q: &[i64]) -> (i64, i64) {
    let pos = q.iter().filter(|&&w| w > 0).sum::<i64>();
    let neg = q.iter().filter(|&&w| w < 0).map(|&w| -w).sum::<i64>();
    (pos, neg)
}

/// Quantize one neuron's float weights to integers in [-3,3] by scanning
/// SCALE_GRID ascending and picking, among scales whose plane sums satisfy
/// `budget`, the one with lowest reconstruction error sum((w - q*scale)^2).
/// Also returns the clipped integer bias for that scale, kept inside the
/// exact range the circuit's `weighted_score` assert requires
/// (score_min >= SCORE_LO, score_max <= SCORE_HI).
fn quantize_neuron(w: &[f64], bias: f64, budget: i64) -> (Vec<i64>, i64) {
    let mut best: Option<(f64, i64, Vec<i64>)> = None; // (mse, scale, q)
    for &scale in mnist::SCALE_GRID {
        let q: Vec<i64> = w.iter().map(|&wi| clip3(mnist::python_round(wi / scale as f64))).collect();
        let (pos, neg) = plane_sums(&q);
        if pos > budget || neg > budget {
            continue;
        }
        let mse: f64 = w.iter().zip(&q).map(|(&wi, &qi)| { let d = wi - (qi * scale) as f64; d * d }).sum();
        if best.as_ref().map(|(bm, _, _)| mse < *bm).unwrap_or(true) {
            best = Some((mse, scale, q));
        }
    }
    // Largest scale in the grid always drives every weight to 0, so pos=neg=0
    // trivially satisfies any budget >= 0 -- `best` is never None.
    let (_, scale, q) = best.expect("quantize_neuron: no scale satisfied the plane budget");
    let (pos, neg) = plane_sums(&q);
    let bias_hi = SCORE_HI - pos;
    let bias_lo = SCORE_LO + neg;
    let bq = mnist::python_round(bias / scale as f64).max(bias_lo).min(bias_hi);
    (q, bq)
}

struct IntMlp {
    hw: Vec<Vec<i64>>,
    hb: Vec<i64>,
    ow: Vec<Vec<i64>>,
    ob: Vec<i64>,
}

fn quantize_mlp(m: &FloatMlp) -> IntMlp {
    let mut hw = Vec::with_capacity(H);
    let mut hb = Vec::with_capacity(H);
    for h in 0..H {
        let (q, bq) = quantize_neuron(&m.hw[h], m.hb[h], PLANE_BUDGET);
        hw.push(q);
        hb.push(bq);
    }
    let mut ow = Vec::with_capacity(NUM_CLASSES);
    let mut ob = Vec::with_capacity(NUM_CLASSES);
    for k in 0..NUM_CLASSES {
        // Output layer budget is automatically satisfied (16*3=48 < 60) but
        // reuses the same routine for one code path.
        let (q, bq) = quantize_neuron(&m.ow[k], m.ob[k], PLANE_BUDGET);
        ow.push(q);
        ob.push(bq);
    }
    IntMlp { hw, hb, ow, ob }
}

/// Reconstruction-error (MSE) quantization picks a scale per neuron with no
/// idea which weights actually matter for the decision boundary. Refine it
/// with greedy coordinate descent against VALIDATION accuracy (never test):
/// for each neuron in turn, try every budget-satisfying scale with the rest
/// of the network held fixed, and keep whichever scale is best for the
/// network's actual integer-forward-pass accuracy. `passes` sweeps over all
/// neurons once each.
fn quantize_mlp_accuracy_search(m: &FloatMlp, val_bits: &[Vec<u8>], val_ys: &[u8], passes: usize) -> IntMlp {
    let mut im = quantize_mlp(m);
    for _ in 0..passes {
        for h in 0..H {
            let mut best_acc = accuracy_int(&im, val_bits, val_ys);
            let mut best = (im.hw[h].clone(), im.hb[h]);
            for &scale in mnist::SCALE_GRID {
                let q: Vec<i64> = m.hw[h].iter().map(|&wi| clip3(mnist::python_round(wi / scale as f64))).collect();
                let (pos, neg) = plane_sums(&q);
                if pos > PLANE_BUDGET || neg > PLANE_BUDGET {
                    continue;
                }
                let bq = mnist::python_round(m.hb[h] / scale as f64).max(SCORE_LO + neg).min(SCORE_HI - pos);
                let saved = (im.hw[h].clone(), im.hb[h]);
                im.hw[h] = q.clone();
                im.hb[h] = bq;
                let acc = accuracy_int(&im, val_bits, val_ys);
                if acc > best_acc {
                    best_acc = acc;
                    best = (q, bq);
                }
                im.hw[h] = saved.0;
                im.hb[h] = saved.1;
            }
            im.hw[h] = best.0;
            im.hb[h] = best.1;
        }
        for k in 0..NUM_CLASSES {
            let mut best_acc = accuracy_int(&im, val_bits, val_ys);
            let mut best = (im.ow[k].clone(), im.ob[k]);
            for &scale in mnist::SCALE_GRID {
                let q: Vec<i64> = m.ow[k].iter().map(|&wi| clip3(mnist::python_round(wi / scale as f64))).collect();
                let (pos, neg) = plane_sums(&q);
                if pos > PLANE_BUDGET || neg > PLANE_BUDGET {
                    continue;
                }
                let bq = mnist::python_round(m.ob[k] / scale as f64).max(SCORE_LO + neg).min(SCORE_HI - pos);
                let saved = (im.ow[k].clone(), im.ob[k]);
                im.ow[k] = q.clone();
                im.ob[k] = bq;
                let acc = accuracy_int(&im, val_bits, val_ys);
                if acc > best_acc {
                    best_acc = acc;
                    best = (q, bq);
                }
                im.ow[k] = saved.0;
                im.ob[k] = saved.1;
            }
            im.ow[k] = best.0;
            im.ob[k] = best.1;
        }
    }
    im
}

// ---------- the actual integer forward pass the circuit computes ----------

fn predict_int(m: &IntMlp, x: &[u8]) -> usize {
    let scores = int_scores(m, x);
    argmax_i64(&scores)
}

fn int_scores(m: &IntMlp, x: &[u8]) -> Vec<i64> {
    let hidden_out: Vec<i64> = (0..H)
        .map(|h| {
            let score = m.hb[h] + (0..NPIX).map(|i| m.hw[h][i] * x[i] as i64).sum::<i64>();
            if score >= 0 { 1 } else { 0 }
        })
        .collect();
    (0..NUM_CLASSES)
        .map(|k| m.ob[k] + (0..H).map(|h| m.ow[k][h] * hidden_out[h]).sum::<i64>())
        .collect()
}

fn argmax_i64(v: &[i64]) -> usize {
    let mut best = 0;
    for i in 1..v.len() {
        if v[i] > v[best] {
            best = i;
        }
    }
    best
}

fn accuracy_int(m: &IntMlp, xs: &[Vec<u8>], ys: &[u8]) -> f64 {
    let correct = xs.iter().zip(ys).filter(|(x, &y)| predict_int(m, x) == y as usize).count();
    correct as f64 / xs.len() as f64
}

fn glyph_accuracy_int(m: &IntMlp) -> f64 {
    let gb = mnist::glyph_bits();
    let correct = gb.iter().filter(|(&d, bits)| predict_int(m, bits) == d as usize).count();
    correct as f64 / gb.len() as f64
}

fn find_exemplars_int(m: &IntMlp, xs: &[Vec<u8>], ys: &[u8]) -> BTreeMap<u8, Vec<u8>> {
    let mut exemplars: BTreeMap<u8, Vec<u8>> = BTreeMap::new();
    for (x, &y) in xs.iter().zip(ys) {
        if exemplars.contains_key(&y) {
            continue;
        }
        if predict_int(m, x) == y as usize {
            exemplars.insert(y, x.clone());
        }
    }
    let missing: Vec<u8> = (0..NUM_CLASSES as u8).filter(|d| !exemplars.contains_key(d)).collect();
    assert!(missing.is_empty(), "no correctly-classified test exemplar for digits {missing:?}");
    exemplars
}

/// Worst-case |P0| + 2|P1| (== plane_sums().0.max(.1) here, see module docs)
/// across every hidden and output neuron, for the report.
fn worst_case_plane_budget(m: &IntMlp) -> i64 {
    let mut worst = 0;
    for h in 0..H {
        let (pos, neg) = plane_sums(&m.hw[h]);
        worst = worst.max(pos).max(neg);
    }
    for k in 0..NUM_CLASSES {
        let (pos, neg) = plane_sums(&m.ow[k]);
        worst = worst.max(pos).max(neg);
    }
    worst
}

fn nonzero_per_hidden_neuron(m: &IntMlp) -> Vec<usize> {
    m.hw.iter().map(|row| row.iter().filter(|&&w| w != 0).count()).collect()
}

// ---------- main ----------

pub fn run(repo_root: &Path) {
    let data_dir = repo_root.join("data").join("mnist");
    let out_path = repo_root.join("scripts").join("weights_mnist.json");

    println!("loading MNIST (cached in data/mnist/, downloading if missing)...");
    let (train_fracs, train_ys) = mnist::load_split(&data_dir, mnist::FILES[0], mnist::FILES[1]);
    let (test_fracs, test_ys) = mnist::load_split(&data_dir, mnist::FILES[2], mnist::FILES[3]);

    let n_train = train_fracs.len();
    let core_end = n_train - mnist::VAL_SIZE;
    let core_bits = mnist::binarize_fracs(&train_fracs[..core_end], THRESHOLD);
    let core_ys = train_ys[..core_end].to_vec();
    let val_bits = mnist::binarize_fracs(&train_fracs[core_end..], THRESHOLD);
    let val_ys = train_ys[core_end..].to_vec();
    let test_bits = mnist::binarize_fracs(&test_fracs, THRESHOLD);
    println!(
        "core: {}, val: {}, test: {} (threshold={THRESHOLD}, reused from the honest linear baseline)",
        core_bits.len(),
        val_bits.len(),
        test_bits.len()
    );

    println!("training float MLP (49 -> {H} -> 10), straight-through sign activation, {EPOCHS} epochs...");
    let mut model = init_mlp();
    let mut order: Vec<usize> = (0..core_bits.len()).collect();
    let mut shuffle_rng = Rng::new(EPOCH_SHUFFLE_SEED);
    for epoch in 0..EPOCHS {
        shuffle_rng.shuffle(&mut order);
        train_epoch(&mut model, &core_bits, &core_ys, &order, None);
        if epoch % 10 == 9 || epoch == EPOCHS - 1 {
            let val_acc = accuracy_float(&model, &val_bits, &val_ys);
            println!("  epoch {}/{EPOCHS}: val acc (float, discrete-threshold) {val_acc:.4}", epoch + 1);
        }
    }
    let float_test_acc = accuracy_float(&model, &test_bits, &test_ys);
    let float_val_acc = accuracy_float(&model, &val_bits, &val_ys);
    println!("float model: val acc {float_val_acc:.4}, test acc {float_test_acc:.4} (reported only -- not what ships)");

    println!("pruning + quantizing to integers in [-3,3] (per-neuron plane budget <= {PLANE_BUDGET}, validation-guided scale search)...");
    let quantized = quantize_mlp_accuracy_search(&model, &val_bits, &val_ys, 2);
    let post_prune_val_acc = accuracy_int(&quantized, &val_bits, &val_ys);
    let post_prune_test_acc = accuracy_int(&quantized, &test_bits, &test_ys);
    println!("post-prune/quantize (pre-retrain): val acc {post_prune_val_acc:.4}, test acc {post_prune_test_acc:.4}");

    // Retrain surviving (nonzero) weights for a couple of epochs, holding
    // pruned positions at exactly zero, then requantize. Kept only if it
    // actually improves validation accuracy over the pre-retrain model --
    // same "don't accept a change validation doesn't support" rule as Job 1's
    // augmentation guard.
    let hidden_mask: Vec<Vec<bool>> = quantized.hw.iter().map(|row| row.iter().map(|&w| w != 0).collect()).collect();
    println!("retraining surviving weights for {RETRAIN_EPOCHS} epoch(s)...");
    let mut retrained_model = FloatMlp {
        hw: model.hw.clone(),
        hb: model.hb.clone(),
        ow: model.ow.clone(),
        ob: model.ob.clone(),
    };
    for h in 0..H {
        for i in 0..NPIX {
            if !hidden_mask[h][i] {
                retrained_model.hw[h][i] = 0.0;
            }
        }
    }
    for _ in 0..RETRAIN_EPOCHS {
        shuffle_rng.shuffle(&mut order);
        train_epoch(&mut retrained_model, &core_bits, &core_ys, &order, Some(&hidden_mask));
    }
    let requantized = quantize_mlp_accuracy_search(&retrained_model, &val_bits, &val_ys, 2);
    let requantized_val_acc = accuracy_int(&requantized, &val_bits, &val_ys);
    let final_int = if requantized_val_acc > post_prune_val_acc {
        println!("  retrain improved validation accuracy ({requantized_val_acc:.4} > {post_prune_val_acc:.4}) -- kept");
        requantized
    } else {
        println!("  retrain did not improve validation accuracy ({requantized_val_acc:.4} <= {post_prune_val_acc:.4}) -- discarded");
        quantized
    };
    let val_acc = accuracy_int(&final_int, &val_bits, &val_ys);
    // Final test-set read: exactly once, after every hyperparameter and the
    // prune/retrain/quantize pipeline are already fixed.
    let test_acc = accuracy_int(&final_int, &test_bits, &test_ys);
    let glyph_acc = glyph_accuracy_int(&final_int);
    let worst_budget = worst_case_plane_budget(&final_int);
    let nonzero = nonzero_per_hidden_neuron(&final_int);

    println!("final quantized integer MLP: val acc {val_acc:.4}, test acc {test_acc:.4}, glyph accuracy {:.1}% ({}/10)",
        glyph_acc * 100.0, (glyph_acc * 10.0).round());
    println!("nonzero weights per hidden neuron: {nonzero:?}");
    println!("worst-case |P0|+2|P1| across all neurons: {worst_budget} (budget {PLANE_BUDGET})");
    assert!(worst_budget <= PLANE_BUDGET, "plane budget violated: {worst_budget} > {PLANE_BUDGET}");

    if test_acc < LINEAR_BASELINE_TEST_ACC {
        println!(
            "ACCEPTANCE BAR NOT MET: MLP test acc {test_acc:.4} < linear baseline {LINEAR_BASELINE_TEST_ACC:.4}. \
             Not writing {}.", out_path.display()
        );
        return;
    }
    println!("acceptance bar cleared: {test_acc:.4} >= {LINEAR_BASELINE_TEST_ACC:.4}");

    let exemplars = find_exemplars_int(&final_int, &test_bits, &test_ys);
    let exemplars_json: BTreeMap<String, Vec<u8>> = exemplars.into_iter().map(|(k, v)| (k.to_string(), v)).collect();

    let out = serde_json::json!({
        "hidden_weights": final_int.hw,
        "hidden_biases": final_int.hb,
        "output_weights": final_int.ow,
        "output_biases": final_int.ob,
        "test_accuracy": test_acc,
        "val_accuracy": val_acc,
        "glyph_accuracy": glyph_acc,
        "threshold": THRESHOLD,
        "exemplars": exemplars_json,
        "float_test_accuracy": float_test_acc,
        "post_prune_test_accuracy": post_prune_test_acc,
        "linear_baseline_test_accuracy": LINEAR_BASELINE_TEST_ACC,
    });
    fs::write(&out_path, serde_json::to_string_pretty(&out).unwrap()).expect("write weights_mnist.json");
    println!("wrote {}", out_path.display());
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The plane-budget arithmetic is the one piece of this file where a
    /// silent bug would mean generating weights the circuit can't represent
    /// at all. Assert the derivation from gen/src/circuit.rs's
    /// `weighted_score` (P0 + 2*P1 per sign == sum(|w|) per sign) directly.
    #[test]
    fn plane_sums_match_bitplane_popcount_formula() {
        let w = vec![3, -3, 1, -1, 2, -2, 0, 3, -1];
        let (pos, neg) = plane_sums(&w);
        // pos: |3| + |1| + |2| + |3| = 9; neg: |3| + |1| + |2| + |1| = 7
        assert_eq!((pos, neg), (9, 7));
    }

    #[test]
    fn quantize_neuron_respects_budget_and_range() {
        let w: Vec<f64> = (0..NPIX).map(|i| (i as f64) - 24.0).collect(); // wide float range
        let (q, bq) = quantize_neuron(&w, 500.0, PLANE_BUDGET);
        assert!(q.iter().all(|&x| (-3..=3).contains(&x)));
        let (pos, neg) = plane_sums(&q);
        assert!(pos <= PLANE_BUDGET && neg <= PLANE_BUDGET);
        assert!(bq <= SCORE_HI - pos && bq >= SCORE_LO + neg);
    }

    #[test]
    fn int_forward_pass_is_deterministic_and_in_range() {
        let m = IntMlp {
            hw: vec![vec![1; NPIX]; H],
            hb: vec![0; H],
            ow: vec![vec![1; H]; NUM_CLASSES],
            ob: vec![0; NUM_CLASSES],
        };
        let x = vec![1u8; NPIX];
        let s1 = int_scores(&m, &x);
        let s2 = int_scores(&m, &x);
        assert_eq!(s1, s2);
        assert_eq!(predict_int(&m, &x), 0); // tie -> lowest digit
    }
}
