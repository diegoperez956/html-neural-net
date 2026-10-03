"""Independent arithmetic for the animation. No Manim or browser dependency."""

import ast
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def canvases():
    tree = ast.parse((ROOT / "tests/test_runtime.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "THIN_CANVASES"
            for target in node.targets
        ):
            return {
                name: [int(c == "#") for row in rows for c in row]
                for name, rows in ast.literal_eval(node.value).items()
            }
    raise ValueError("THIN_CANVASES fixture not found")


def weights():
    result = json.loads((ROOT / "scripts/weights_mnist.json").read_text())
    assert len(result["weights"]) == len(result["bias"]) == 10
    assert all(len(row) == 49 for row in result["weights"])
    assert (result["canvas"], result["dilate_iters"], result["block_threshold"]) == (
        14,
        1,
        1,
    )
    return result


def dilation(bits, side=14):
    assert len(bits) == side * side and set(bits) <= {0, 1}
    return [
        int(
            any(
                bits[rr * side + cc]
                for rr, cc in ((r, c), (r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
                if 0 <= rr < side and 0 <= cc < side
            )
        )
        for r in range(side)
        for c in range(side)
    ]


def downsample(bits):
    assert len(bits) == 196 and set(bits) <= {0, 1}
    return [
        int(any(bits[(2 * r + dr) * 14 + 2 * c + dc] for dr in (0, 1) for dc in (0, 1)))
        for r in range(7)
        for c in range(7)
    ]


def scores(features):
    model = weights()
    assert len(features) == 49 and set(features) <= {0, 1}
    return [
        bias + sum(w * x for w, x in zip(row, features))
        for row, bias in zip(model["weights"], model["bias"])
    ]


@dataclass(frozen=True)
class Prediction:
    canvas: list[int]
    dilated: list[int]
    features: list[int]
    scores: list[int]
    winner: int
    margin: int


def predict(canvas):
    dilated = dilation(canvas)
    features = downsample(dilated)
    values = scores(features)
    winner = max(range(10), key=values.__getitem__)
    ordered = sorted(values)
    return Prediction(
        canvas, dilated, features, values, winner, ordered[-1] - ordered[-2]
    )


def word(value, width):
    """MSB first for display. The Rust circuit arrays use the opposite order."""
    return [((value & ((1 << width) - 1)) >> i) & 1 for i in reversed(range(width))]


def signed(bits):
    return sum(
        bit * (-(1 << i) if i == len(bits) - 1 else 1 << i)
        for i, bit in enumerate(reversed(bits))
    )


def full_adder(a, b, carry):
    assert {a, b, carry} <= {0, 1}
    t = a ^ b
    return t ^ carry, (a & b) | (t & carry)


def addition_trace(a, b, width=4):
    carry = 0
    result = []
    for i in range(width):
        aa, bb = (a >> i) & 1, (b >> i) & 1
        total, next_carry = full_adder(aa, bb, carry)
        result.append(
            {
                "column": i,
                "a": aa,
                "b": bb,
                "carry_in": carry,
                "sum": total,
                "carry_out": next_carry,
            }
        )
        carry = next_carry
    return result


def xor_forward(x1, x0):
    pre = [2 * x1 - 2 * x0 - 1, -2 * x1 + 2 * x0 - 1]
    hidden = [int(z >= 0) for z in pre]
    output_pre = 2 * hidden[0] + 2 * hidden[1] - 1
    return pre, hidden, output_pre, int(output_pre >= 0)


def planes(row, features):
    assert len(row) == len(features)
    return {
        "positive low": [
            i for i, (w, x) in enumerate(zip(row, features)) if x and w in (1, 3)
        ],
        "positive high": [
            i for i, (w, x) in enumerate(zip(row, features)) if x and w in (2, 3)
        ],
        "negative low": [
            i for i, (w, x) in enumerate(zip(row, features)) if x and w in (-1, -3)
        ],
        "negative high": [
            i for i, (w, x) in enumerate(zip(row, features)) if x and w in (-2, -3)
        ],
    }


SEGMENTS = {
    0: "abcdef",
    1: "bc",
    2: "abdeg",
    3: "abcdg",
    4: "bcfg",
    5: "acdfg",
    6: "acdefg",
    7: "abc",
    8: "abcdefg",
    9: "abcdfg",
}


def declarations():
    return dict(
        re.findall(
            r"^\.rt \{ --([\w-]+): ([^;]+); \}",
            (ROOT / "dist/index.html").read_text(),
            re.M,
        )
    )


def css(*names):
    values = declarations()
    return "\n".join(f"--{name}: {values[name]};" for name in names)


def source_digest():
    paths = [
        ROOT / p
        for p in (
            "scripts/weights_mnist.json",
            "gen/src/main.rs",
            "gen/src/circuit.rs",
            "tests/test_runtime.py",
        )
    ]
    return hashlib.sha256(b"\0".join(path.read_bytes() for path in paths)).hexdigest()
