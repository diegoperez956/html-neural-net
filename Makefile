.PHONY: build test clean

build:
	python3 scripts/generate.py

test: build
	python3 -m unittest discover -s tests -v

clean:
	rm -f dist/index.html
