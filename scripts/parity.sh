#!/usr/bin/env bash
# Cross-language parity check: python3 scripts/generate.py vs the Rust port
# in gen/ must produce byte-identical output from the same weights JSONs.
set -euo pipefail
cd "$(dirname "$0")/.."

py_out="$(mktemp)"
rust_out="$(mktemp)"
trap 'rm -f "$py_out" "$rust_out"' EXIT

python3 scripts/generate.py "$py_out"
cargo build --release --manifest-path gen/Cargo.toml --quiet
./gen/target/release/htmlnet-gen "$rust_out"

py_sha="$(sha256sum "$py_out" | cut -d' ' -f1)"
rust_sha="$(sha256sum "$rust_out" | cut -d' ' -f1)"

if [ "$py_sha" = "$rust_sha" ]; then
    echo "PARITY OK  sha256=$py_sha"
else
    echo "PARITY MISMATCH"
    echo "  python: $py_sha"
    echo "  rust:   $rust_sha"
    diff "$py_out" "$rust_out" | head -40 || true
    exit 1
fi
