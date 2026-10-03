.PHONY: build train test test-unit test-runtime clean

PYTHON ?= python3
CARGO ?= cargo

train:
	$(CARGO) build --locked --release --manifest-path train/Cargo.toml
	./train/target/release/train glyph
	./train/target/release/train mnist

build:
	$(CARGO) build --locked --release --manifest-path gen/Cargo.toml
	./gen/target/release/htmlnet-gen dist/index.html
	./gen/target/release/htmlnet-gen dist/no-js.html --no-js

test: test-unit test-runtime

test-unit:
	$(CARGO) test --locked --manifest-path gen/Cargo.toml
	$(CARGO) test --locked --manifest-path train/Cargo.toml

test-runtime: build
	$(PYTHON) -m unittest discover -s tests -v

clean:
	rm -f dist/index.html
