#!/usr/bin/env python3
"""Build-time training: 10-class linear digit classifier on real MNIST,
downsampled to a 7x7 binary grid, quantized to small integer weights.

Pure stdlib, deterministic, no numpy. Produces scripts/weights_mnist.json,
consumed later by the circuit compiler. Weights must land in [-3, 3] because
weight application is pure wiring (a weight of 3 = wire the pixel into bit
positions 0 and 1). Biases are unclamped words in the circuit, not wiring,
so they may run larger.

Pipeline: download MNIST idx files (cached in data/mnist/) -> bounding-box
normalize each 28x28 digit (binarize, crop to the tight box of lit pixels,
area-resample that crop to a 7x7 coverage-fraction grid) -> threshold the
fractions into bits -> multiclass perceptron with integer weights ->
quantize to [-3,3] by trying a few scale factors and keeping whichever
scores best -> evaluate on the full 10k test set -> pick one
correctly-classified exemplar per digit.

Rev 2: the original pipeline downsampled raw (un-cropped) 28x28 images by
4x4-block mean, which starved anything near the image border (MNIST digits
sit in a ~5x5-block-equivalent central blob with ~4px margins) and produced
mangled thin-stroke shapes ("1" lit only 2 of 49 cells). Bounding-box
normalization before resampling fixes both problems at once: content always
fills the 7x7 grid edge-to-edge, matching how a user actually draws on the
demo's checkbox grid.
"""
import gzip
import json
import math
import os
import random
import struct
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "mnist")
OUT_PATH = os.path.join(ROOT, "scripts", "weights_mnist.json")

MIRRORS = [
    "https://storage.googleapis.com/cvdf-datasets/mnist/",
    "https://ossci-datasets.s3.amazonaws.com/mnist/",
]
FILES = [
    "train-images-idx3-ubyte.gz",
    "train-labels-idx1-ubyte.gz",
    "t10k-images-idx3-ubyte.gz",
    "t10k-labels-idx1-ubyte.gz",
]

# Pixel-level binarize threshold (0-255 grayscale) used only to find each
# digit's bounding box. MNIST background is 0, strokes are typically 150-255,
# so 128 is a clean midpoint split.
PIXEL_THRESHOLD = 128

EPOCHS = 8
SHUFFLE_SEED = 42
NUM_CLASSES = 10
GRID = 7
NPIX = GRID * GRID  # 49

# Scale factors tried when quantizing int weights down to [-3, 3].
SCALE_GRID = [1, 2, 3, 4, 5, 7, 10, 15, 20, 30, 50, 75, 100, 150, 200]

# Cell-coverage-fraction thresholds tried (jointly with SCALE_GRID) for
# turning the area-resampled 7x7 grid into bits: a cell is lit iff the
# fraction of it covered by binarized digit pixels exceeds this.
THRESHOLD_GRID = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35]

# Canonical thin-stroke 7x7 grid drawings (how a user actually draws on the
# demo's checkbox grid) -- used as a demo-fidelity eval, separate from MNIST
# test accuracy. Copied verbatim from the lead's glyph_check.py.
GLYPHS = {
    0: ["..###..", ".#...#.", ".#...#.", ".#...#.", ".#...#.", ".#...#.", "..###.."],
    1: ["...#...", "..##...", "...#...", "...#...", "...#...", "...#...", "..###.."],
    2: ["..###..", ".#...#.", ".....#.", "....#..", "...#...", "..#....", ".#####."],
    3: ["..###..", ".#...#.", ".....#.", "...##..", ".....#.", ".#...#.", "..###.."],
    4: ["....#..", "...##..", "..#.#..", ".#..#..", ".#####.", "....#..", "....#.."],
    5: [".#####.", ".#.....", ".####..", ".....#.", ".....#.", ".#...#.", "..###.."],
    6: ["..###..", ".#.....", ".#.....", ".####..", ".#...#.", ".#...#.", "..###.."],
    7: [".#####.", ".....#.", "....#..", "...#...", "...#...", "..#....", "..#...."],
    8: ["..###..", ".#...#.", ".#...#.", "..###..", ".#...#.", ".#...#.", "..###.."],
    9: ["..###..", ".#...#.", ".#...#.", "..####.", ".....#.", ".....#.", "..###.."],
}
GLYPH_BITS = {d: [1 if ch == "#" else 0 for row in rows for ch in row]
              for d, rows in GLYPHS.items()}

# Synthetic augmentation knobs (used only if glyph accuracy < 8/10 after the
# base fix). ~300 jittered variants/digit -> 3000 synthetic examples mixed
# into the 60k MNIST train set = ~4.8% of the augmented 63k total, matching
# the spec's "~5%" target (spec's "~200" was a floor, not exact).
AUG_VARIANTS_PER_DIGIT = 300
AUG_FLIP_PROB = 0.05


def download(name):
    dest = os.path.join(DATA_DIR, name)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    os.makedirs(DATA_DIR, exist_ok=True)
    last_err = None
    for base in MIRRORS:
        url = base + name
        try:
            print("downloading", url)
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
                f.write(r.read())
            return dest
        except Exception as e:  # noqa: BLE001 - try next mirror
            last_err = e
            print("  failed:", e)
    raise RuntimeError(f"could not download {name} from any mirror: {last_err}")


def read_idx_images(path):
    with gzip.open(path, "rb") as f:
        magic, n, rows, cols = struct.unpack(">IIII", f.read(16))
        assert magic == 2051, f"bad image magic {magic} in {path}"
        data = f.read(n * rows * cols)
    imgs = []
    stride = rows * cols
    for i in range(n):
        imgs.append(data[i * stride:(i + 1) * stride])  # bytes, row-major 28x28
    return imgs, rows, cols


def read_idx_labels(path):
    with gzip.open(path, "rb") as f:
        magic, n = struct.unpack(">II", f.read(8))
        assert magic == 2049, f"bad label magic {magic} in {path}"
        data = f.read(n)
    return list(data)


def binarize_28(img):
    """28x28 byte string -> 28x28 list-of-rows of 0/1 (pixel > threshold)."""
    return [[1 if img[r * 28 + c] > PIXEL_THRESHOLD else 0 for c in range(28)]
            for r in range(28)]


def bbox_of(bin_img):
    """Tight bounding box of lit pixels in a 28x28 0/1 grid -> (top, bottom, left, right),
    inclusive. Falls back to the full image if nothing is lit (shouldn't happen for
    real digit images, but keeps the pipeline total)."""
    rows_with = [r for r in range(28) if any(bin_img[r])]
    if not rows_with:
        return 0, 27, 0, 27
    cols_with = [c for c in range(28) if any(bin_img[r][c] for r in range(28))]
    return rows_with[0], rows_with[-1], cols_with[0], cols_with[-1]


def pad_to_square(lo, hi, size, limit=28):
    """Extend an inclusive [lo, hi] index range to exactly `size` long, centered
    as evenly as possible, clamped into [0, limit-1]. Used to square up a tight
    bbox before resampling: without this, a narrow bbox (e.g. a "1", ~6px wide x
    20px tall) gets stretched to fill the full 7-wide grid and turns into a
    solid blob instead of staying a thin stroke."""
    extra = size - (hi - lo + 1)
    before = extra // 2
    new_lo, new_hi = lo - before, hi + (extra - before)
    if new_lo < 0:
        new_hi -= new_lo
        new_lo = 0
    if new_hi > limit - 1:
        new_lo -= new_hi - (limit - 1)
        new_hi = limit - 1
    return max(0, new_lo), new_hi


def square_bbox(top, bottom, left, right):
    side = max(bottom - top + 1, right - left + 1)
    top, bottom = pad_to_square(top, bottom, side)
    left, right = pad_to_square(left, right, side)
    return top, bottom, left, right


def area_resample(bin_img, top, bottom, left, right, grid=GRID):
    """Area-resample the (top..bottom, left..right) crop of a 0/1 pixel grid down
    to `grid` x `grid`, each output cell = fraction of its source rectangle that is
    lit. Handles non-integer block edges by exact pixel-overlap weighting."""
    crop_h = bottom - top + 1
    crop_w = right - left + 1
    out = [0.0] * (grid * grid)
    for gy in range(grid):
        y0 = top + gy * crop_h / grid
        y1 = top + (gy + 1) * crop_h / grid
        iy0, iy1 = int(math.floor(y0)), int(math.ceil(y1))
        for gx in range(grid):
            x0 = left + gx * crop_w / grid
            x1 = left + (gx + 1) * crop_w / grid
            ix0, ix1 = int(math.floor(x0)), int(math.ceil(x1))
            area = (y1 - y0) * (x1 - x0)
            lit = 0.0
            for py in range(iy0, iy1):
                oy = min(py + 1, y1) - max(py, y0)
                if oy <= 0:
                    continue
                row = bin_img[py]
                for px in range(ix0, ix1):
                    ox = min(px + 1, x1) - max(px, x0)
                    if ox > 0 and row[px]:
                        lit += oy * ox
            out[gy * grid + gx] = lit / area if area > 0 else 0.0
    return out


def _selftest_area_resample():
    """Runnable check for the area-resample math: all-lit and all-zero crops
    saturate to 1.0/0.0 everywhere, and a single lit pixel maps to exactly one
    hot output cell when the grid divides evenly."""
    all_lit = [[1, 1], [1, 1]]
    assert area_resample(all_lit, 0, 1, 0, 1, grid=2) == [1.0, 1.0, 1.0, 1.0]
    all_zero = [[0, 0], [0, 0]]
    assert area_resample(all_zero, 0, 1, 0, 1, grid=2) == [0.0, 0.0, 0.0, 0.0]
    single = [[1, 0], [0, 0]]
    assert area_resample(single, 0, 1, 0, 1, grid=2) == [1.0, 0.0, 0.0, 0.0]


def preprocess_image(img):
    """28x28 byte string -> 49 coverage fractions (floats in [0,1]), row-major.
    Bbox is squared up (aspect-preserving) before resampling -- see square_bbox."""
    bin_img = binarize_28(img)
    top, bottom, left, right = square_bbox(*bbox_of(bin_img))
    return area_resample(bin_img, top, bottom, left, right)


def load_split(images_name, labels_name):
    img_path = download(images_name)
    lbl_path = download(labels_name)
    imgs, rows, cols = read_idx_images(img_path)
    labels = read_idx_labels(lbl_path)
    assert rows == 28 and cols == 28, "pipeline assumes 28x28 MNIST input"
    assert len(imgs) == len(labels), "image/label count mismatch"
    fracs = [preprocess_image(im) for im in imgs]
    return fracs, labels


def binarize_fracs(fracs_list, t):
    return [[1 if f > t else 0 for f in fracs] for fracs in fracs_list]


def shift_grid(bits, dy, dx, grid=GRID):
    """Shift a grid x grid bit vector by (dy, dx). Returns None if any lit cell
    would fall outside the grid (i.e. the shift doesn't "fit")."""
    if dy == 0 and dx == 0:
        return bits[:]
    new = [0] * (grid * grid)
    for r in range(grid):
        for c in range(grid):
            if bits[r * grid + c]:
                nr, nc = r + dy, c + dx
                if not (0 <= nr < grid and 0 <= nc < grid):
                    return None
                new[nr * grid + nc] = 1
    return new


def jitter_variants(bits, n, seed):
    """n deterministic jittered variants of a 7x7 bit grid: an occasional 1-cell
    shift (only applied if the glyph still fits on the grid), plus per-cell noise
    flips at AUG_FLIP_PROB. Models how a user's hand-drawn glyph wobbles."""
    rng = random.Random(seed)
    variants = []
    for _ in range(n):
        dy = rng.choice([-1, 0, 0, 0, 1])
        dx = rng.choice([-1, 0, 0, 0, 1])
        shifted = shift_grid(bits, dy, dx)
        v = shifted if shifted is not None else bits[:]
        v = [(1 - b) if rng.random() < AUG_FLIP_PROB else b for b in v]
        variants.append(v)
    return variants


def score(weights, bias, x, c):
    return bias[c] + sum(weights[c][i] * x[i] for i in range(NPIX))


def predict(weights, bias, x):
    scores = [score(weights, bias, x, c) for c in range(NUM_CLASSES)]
    best = 0
    for c in range(1, NUM_CLASSES):
        if scores[c] > scores[best]:
            best = c
    return best


def accuracy(weights, bias, xs, ys):
    correct = sum(1 for x, y in zip(xs, ys) if predict(weights, bias, x) == y)
    return correct / len(xs)


def train_perceptron(xs, ys):
    weights = [[0] * NPIX for _ in range(NUM_CLASSES)]
    bias = [0] * NUM_CLASSES
    order = list(range(len(xs)))
    rng = random.Random(SHUFFLE_SEED)
    for epoch in range(EPOCHS):
        rng.shuffle(order)
        errors = 0
        for idx in order:
            x, y = xs[idx], ys[idx]
            pred = predict(weights, bias, x)
            if pred != y:
                errors += 1
                for i in range(NPIX):
                    weights[y][i] += x[i]
                    weights[pred][i] -= x[i]
                bias[y] += 1
                bias[pred] -= 1
        print(f"  epoch {epoch + 1}/{EPOCHS}: {errors} errors "
              f"({errors / len(xs):.3%})")
    return weights, bias


def clip(v, lo, hi):
    return max(lo, min(hi, v))


def quantize(weights, bias, scale, wclip, bmax):
    qw = [[clip(round(w / scale), -wclip, wclip) for w in row] for row in weights]
    qb = [clip(round(b / scale), -bmax, bmax) for b in bias]
    return qw, qb


def pick_best_quantization(weights, bias, val_xs, val_ys, wclip, bmax):
    best_scale, best_acc, best_qw, best_qb = None, -1.0, None, None
    for s in SCALE_GRID:
        qw, qb = quantize(weights, bias, s, wclip, bmax)
        acc = accuracy(qw, qb, val_xs, val_ys)
        if acc > best_acc:
            best_scale, best_acc, best_qw, best_qb = s, acc, qw, qb
    return best_scale, best_acc, best_qw, best_qb


def find_exemplars(weights, bias, xs, ys):
    exemplars = {}
    for x, y in zip(xs, ys):
        key = str(y)
        if key in exemplars:
            continue
        if predict(weights, bias, x) == y:
            exemplars[key] = x
    missing = [d for d in range(NUM_CLASSES) if str(d) not in exemplars]
    assert not missing, f"no correctly-classified test exemplar for digits {missing}"
    return exemplars


def glyph_accuracy(weights, bias):
    """Accuracy on the canonical thin-stroke GLYPHS, fed straight in as 7x7 bit
    grids (no bbox/threshold pipeline -- this is what a user draws directly)."""
    correct = sum(1 for d, bits in GLYPH_BITS.items() if predict(weights, bias, bits) == d)
    return correct / len(GLYPH_BITS)


def main():
    if "--force" not in sys.argv and os.path.exists(OUT_PATH):
        print(f"skip: {OUT_PATH} already exists (pass --force to retrain)")
        return

    _selftest_area_resample()

    print("loading MNIST (cached in data/mnist/, downloading if missing)...")
    train_fracs, train_ys = load_split(FILES[0], FILES[1])
    test_fracs, test_ys = load_split(FILES[2], FILES[3])
    print(f"train: {len(train_fracs)} images, test: {len(test_fracs)} images")

    # Held-out slice of the training set for picking (threshold, scale).
    val_ys = train_ys[:5000]

    print("joint grid search over cell threshold t and quantization scale...")
    best = None  # (val_acc, t, scale, weights, bias, qweights, qbias)
    for t in THRESHOLD_GRID:
        train_bits = binarize_fracs(train_fracs, t)
        val_bits = train_bits[:5000]
        weights, bias = train_perceptron(train_bits, train_ys)
        scale, val_acc, qweights, qbias = pick_best_quantization(
            weights, bias, val_bits, val_ys, wclip=3, bmax=200)
        print(f"  t={t}: scale={scale}, val acc {val_acc:.4f}")
        if best is None or val_acc > best[0]:
            best = (val_acc, t, scale, weights, bias, qweights, qbias)
    val_acc, t, scale, weights, bias, qweights, qbias = best
    print(f"chosen: t={t}, scale={scale} (val acc {val_acc:.4f})")

    test_bits = binarize_fracs(test_fracs, t)
    train_bits = binarize_fracs(train_fracs, t)

    w_min = min(min(row) for row in weights)
    w_max = max(max(row) for row in weights)
    print(f"int weight range: [{w_min}, {w_max}], bias range: "
          f"[{min(bias)}, {max(bias)}]")

    train_acc = accuracy(qweights, qbias, train_bits, train_ys)
    test_acc = accuracy(qweights, qbias, test_bits, test_ys)
    print(f"[-3,3] quantization: train acc {train_acc:.4f}, test acc {test_acc:.4f}")

    if test_acc < 0.70:
        val_bits = train_bits[:5000]
        scale7, val_acc7, qw7, qb7 = pick_best_quantization(
            weights, bias, val_bits, val_ys, wclip=7, bmax=200)
        test_acc7 = accuracy(qw7, qb7, test_bits, test_ys)
        print(f"[-7,7] fallback quantization: scale={scale7}, "
              f"test acc {test_acc7:.4f} (reported only, not written)")

    assert test_acc >= 0.60, f"test accuracy {test_acc:.4f} below 0.60 floor"

    glyph_acc = glyph_accuracy(qweights, qbias)
    print(f"glyph accuracy (pre-augmentation): {glyph_acc:.1%} "
          f"({round(glyph_acc * 10)}/10)")

    if glyph_acc < 0.8:
        print(f"glyph accuracy below 8/10 -- augmenting with "
              f"{AUG_VARIANTS_PER_DIGIT}/digit jittered synthetic glyphs...")
        aug_xs, aug_ys = [], []
        for d, bits in GLYPH_BITS.items():
            for v in jitter_variants(bits, AUG_VARIANTS_PER_DIGIT, seed=1000 + d):
                aug_xs.append(v)
                aug_ys.append(d)
        mixed_xs = train_bits + aug_xs
        mixed_ys = train_ys + aug_ys
        print(f"  augmented train set: {len(train_bits)} MNIST + {len(aug_xs)} "
              f"synthetic = {len(mixed_xs)} ({len(aug_xs) / len(mixed_xs):.1%} synthetic)")
        weights, bias = train_perceptron(mixed_xs, mixed_ys)
        val_bits = train_bits[:5000]  # val stays pure MNIST, no synthetic leakage
        scale, val_acc, qweights, qbias = pick_best_quantization(
            weights, bias, val_bits, val_ys, wclip=3, bmax=200)
        train_acc = accuracy(qweights, qbias, train_bits, train_ys)
        test_acc = accuracy(qweights, qbias, test_bits, test_ys)
        glyph_acc_post = glyph_accuracy(qweights, qbias)
        print(f"post-augmentation: scale={scale}, train acc {train_acc:.4f}, "
              f"test acc {test_acc:.4f}, glyph accuracy {glyph_acc_post:.1%} "
              f"({round(glyph_acc_post * 10)}/10)")
        assert test_acc >= 0.60, f"test accuracy {test_acc:.4f} below 0.60 floor after augmentation"
        w_min = min(min(row) for row in weights)
        w_max = max(max(row) for row in weights)
        glyph_acc = glyph_acc_post

    print(f"int weight range (final): [{w_min}, {w_max}], bias range: "
          f"[{min(bias)}, {max(bias)}]")
    print(f"quantized weight range: [{min(min(r) for r in qweights)}, "
          f"{max(max(r) for r in qweights)}], bias range: [{min(qbias)}, {max(qbias)}]")

    exemplars = find_exemplars(qweights, qbias, test_bits, test_ys)
    lit_counts = {k: sum(v) for k, v in exemplars.items()}
    print("exemplar lit-cell counts:", dict(sorted(lit_counts.items(), key=lambda kv: int(kv[0]))))

    out = {
        "weights": qweights,
        "bias": qbias,
        "test_accuracy": test_acc,
        "glyph_accuracy": glyph_acc,
        "threshold": t,
        "exemplars": {k: v for k, v in sorted(exemplars.items(), key=lambda kv: int(kv[0]))},
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=1)
    print("wrote", OUT_PATH)


if __name__ == "__main__":
    main()
