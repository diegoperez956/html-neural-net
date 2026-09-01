.PHONY: build train test clean

train:
	cargo build --release --manifest-path train/Cargo.toml
	./train/target/release/train glyph
	./train/target/release/train mnist

build: train
	cargo build --release --manifest-path gen/Cargo.toml
	./gen/target/release/htmlnet-gen dist/index.html

test: build
	python3 -m unittest discover -s tests -v

clean:
	rm -f dist/index.html
