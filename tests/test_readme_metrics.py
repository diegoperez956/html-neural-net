"""The README's published saved-model metrics are a maintained text contract."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReadmeMetricsTests(unittest.TestCase):
    def test_published_saved_model_metrics_match_metadata(self):
        metadata = json.loads((ROOT / "scripts/weights_mnist.json").read_text())
        readme = (ROOT / "README.md").read_text()
        claims = {
            "test_accuracy": r"the saved model scores ([\d.]+)% on the cropped, centred 10k mnist test set",
            "glyph_accuracy": r"([\d]+)/10 2×-upscaled canonical glyphs",
            "thin_glyph_accuracy": r"([\d]+)/10 seven-segment-shaped 1-cell-wide glyphs",
        }
        for field, pattern in claims.items():
            with self.subTest(field=field):
                matches = re.findall(pattern, readme)
                self.assertEqual(len(matches), 1, f"missing or ambiguous claim for {field}")
                expected = (f"{metadata[field] * 100:.2f}" if field == "test_accuracy"
                            else str(round(metadata[field] * 10)))
                self.assertEqual(matches[0], expected)
