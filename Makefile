.PHONY: build train test clean

build: train
	python3 scripts/generate.py dist/index.html

train:
	python3 scripts/train.py

test: build
	python3 -m unittest discover -s tests -v

clean:
	rm -f dist/index.html
