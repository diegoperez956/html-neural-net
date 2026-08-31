//! Port of scripts/train.py: perceptron learns 3x3 horizontal-bar vs
//! vertical-bar. Pure, deterministic, no RNG involved -- an exact port.

use std::fs;
use std::path::Path;

const TRAIN: &[([i64; 9], i64)] = &[
    ([1, 1, 1, 0, 0, 0, 0, 0, 0], 1),
    ([1, 1, 1, 0, 1, 0, 0, 0, 0], 1),
    ([1, 1, 1, 0, 0, 0, 0, 0, 1], 1),
    ([1, 0, 0, 1, 0, 0, 1, 0, 0], -1),
    ([1, 0, 0, 1, 1, 0, 1, 0, 0], -1),
    ([1, 0, 0, 1, 0, 0, 1, 0, 1], -1),
    ([0, 0, 0, 0, 0, 0, 0, 0, 0], -1),
    ([0, 1, 0, 0, 0, 0, 0, 0, 0], -1),
    ([0, 0, 0, 0, 1, 0, 0, 0, 0], -1),
];

fn score(w: &[i64; 10], x: &[i64; 9]) -> i64 {
    w[0] + (0..9).map(|i| w[i + 1] * x[i]).sum::<i64>()
}

pub fn train() -> [i64; 10] {
    let mut w = [0i64; 10];
    for _epoch in 0..100 {
        let mut changed = false;
        for (x, y) in TRAIN {
            let s = score(&w, x);
            let pred = if s >= 0 { 1 } else { -1 };
            if pred != *y {
                changed = true;
                w[0] += y;
                for i in 0..9 {
                    w[i + 1] += y * x[i];
                }
            }
        }
        if !changed {
            break;
        }
    }
    for (x, y) in TRAIN {
        let s = score(&w, x);
        if *y == 1 {
            assert!(s >= 0, "training failed to separate positive class");
        } else {
            assert!(s < 0, "training failed to separate negative class");
        }
    }
    w
}

pub fn run(repo_root: &Path) {
    let w = train();
    let out = serde_json::json!({
        "bias": w[0],
        "weights": w[1..].to_vec(),
    });
    let path = repo_root.join("scripts").join("weights.json");
    fs::write(&path, serde_json::to_string_pretty(&out).unwrap()).expect("write weights.json");
    println!("trained: {out}");
    println!("wrote {}", path.display());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn separates_train_set() {
        let w = train();
        for (x, y) in TRAIN {
            let s = score(&w, x);
            let pred = if s >= 0 { 1 } else { -1 };
            assert_eq!(pred, *y);
        }
    }
}
