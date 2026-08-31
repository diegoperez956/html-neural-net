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
        Some("mnist") => mnist::run(&root),
        _ => {
            eprintln!("usage: train <glyph|mnist>");
            std::process::exit(1);
        }
    }
}
