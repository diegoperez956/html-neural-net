#!/usr/bin/env python3
"""Build-time training: perceptron learns 3x3 horizontal-bar vs vertical-bar.

Pure stdlib, deterministic, tiny. Produces scripts/weights.json consumed by
generate.py. This is the ONLY trained part of the demo; everything else is
hand-designed integer weights (documented).

Output classes: +1 = horizontal bar (top row), -1 = vertical bar (left col).
Perceptron: w <- w + y*x for misclassified (x augmented with bias as x_0=1).
"""
import json
import os

# 3x3 bit grid, row-major; class labels
TRAIN = [
    # horizontal bars (top row lit)
    ([1, 1, 1, 0, 0, 0, 0, 0, 0], +1),
    ([1, 1, 1, 0, 1, 0, 0, 0, 0], +1),   # with center dot
    ([1, 1, 1, 0, 0, 0, 0, 0, 1], +1),   # corner noise
    # vertical bars (left column lit)
    ([1, 0, 0, 1, 0, 0, 1, 0, 0], -1),
    ([1, 0, 0, 1, 1, 0, 1, 0, 0], -1),   # center dot
    ([1, 0, 0, 1, 0, 0, 1, 0, 1], -1),   # corner noise
    # near-blank controls
    ([0, 0, 0, 0, 0, 0, 0, 0, 0], -1),
    ([0, 1, 0, 0, 0, 0, 0, 0, 0], -1),
    ([0, 0, 0, 0, 1, 0, 0, 0, 0], -1),
]


def train():
    w = [0] * 10  # 9 pixels + bias at index 0 (x_0 = 1)
    for _ in range(100):  # fixed epochs; convergence checked below
        changed = False
        for x, y in TRAIN:
            s = w[0] + sum(w[i + 1] * x[i] for i in range(9))
            pred = 1 if s >= 0 else -1
            if pred != y:
                changed = True
                w[0] += y
                for i in range(9):
                    w[i + 1] += y * x[i]
        if not changed:
            break
    assert all(w[0] + sum(w[i + 1] * x[i] for i in range(9)) >= 0 for x, y in TRAIN if y == +1), \
        "training failed to separate positive class"
    assert all(w[0] + sum(w[i + 1] * x[i] for i in range(9)) < 0 for x, y in TRAIN if y == -1), \
        "training failed to separate negative class"
    return w


def main():
    w = train()
    out = {"bias": w[0], "weights": w[1:]}
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "scripts", "weights.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print("trained:", out)
    print("wrote", path)


if __name__ == "__main__":
    main()
