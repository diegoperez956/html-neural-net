mod glyph;
mod mlp;
mod mnist;
mod rng;

use std::path::PathBuf;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()
}

fn main() {
    let cmd = std::env::args().nth(1);
    let root = repo_root();
    match cmd.as_deref() {
        Some("glyph") => glyph::run(&root),
        // Shipped trainer: 49 -> 16 -> 10 MLP, per docs/DESIGN_MLP.md.
        Some("mnist") => mlp::run(&root),
        // Honest linear baseline (train/README.md) -- kept runnable for
        // reproducibility/regression checks, not part of the shipped output.
        Some("linear") => mnist::run(&root),
        _ => {
            eprintln!("usage: train <glyph|mnist|linear>");
            std::process::exit(1);
        }
    }
}
