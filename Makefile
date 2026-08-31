.PHONY: build train test clean build-rust parity

build: train
	python3 scripts/generate.py dist/index.html

train:
	python3 scripts/train.py
	python3 scripts/train_mnist.py

test: build
	python3 -m unittest discover -s tests -v

# Build dist/index.html with the Rust port (gen/) instead of Python.
# Byte-identical to `make build` — see scripts/parity.sh / `make parity`.
build-rust: train
	cargo build --release --manifest-path gen/Cargo.toml
	./gen/target/release/htmlnet-gen dist/index.html

# Cross-language parity check: python3 scripts/generate.py vs gen/ must
# produce byte-identical output.
parity:
	./scripts/parity.sh

clean:
	rm -f dist/index.html
