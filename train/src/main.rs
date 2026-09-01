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
        // Shipped trainer: honest val-selected linear classifier, selected
        // against a drawn-style validation proxy (see D-010 in
        // docs/DECISIONS.md and train/README.md). Writes
        // scripts/weights_mnist.json, the linear schema gen/ expects.
        Some("mnist") => mnist::run(&root),
        // M12 MLP (docs/DESIGN_MLP.md): recorded negative result, not
        // shipped. Writes its own scripts/weights_mlp.json, not part of
        // `make build`.
        Some("mlp") => mlp::run(&root),
        _ => {
            eprintln!("usage: train <glyph|mnist|mlp>");
            std::process::exit(1);
        }
    }
}
