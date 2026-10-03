mod glyph;
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
        // Shipped linear trainer: threshold/seed/scale selected against
        // a transformed-MNIST proxy; architecture and release floors also
        // inspected synthetic glyph results (D-011, train/README.md). Writes
        // scripts/weights_mnist.json, the linear schema gen/ expects.
        Some("mnist") => mnist::run(&root),
        // Feasibility-prototype support: dumps the same 49-bit MNIST
        // features `mnist` trains on (fixed t=0.65) as JSON, for a non-Rust
        // (NumPy) reference and a generated page. Writes
        // data/mnist_bits_t065.json; not part of `make build`.
        Some("export-bits") => mnist::export_bits(&root),
        _ => {
            eprintln!("usage: train <glyph|mnist|export-bits>");
            std::process::exit(1);
        }
    }
}
