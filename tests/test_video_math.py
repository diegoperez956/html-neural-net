import unittest

from video.model import (
    addition_trace,
    canvases,
    css,
    dilation,
    downsample,
    full_adder,
    planes,
    predict,
    signed,
    weights,
    word,
    xor_forward,
)


class VideoMathTests(unittest.TestCase):
    def test_full_adder_and_carry_trace(self):
        for a in (0, 1):
            for b in (0, 1):
                for carry in (0, 1):
                    s, c = full_adder(a, b, carry)
                    self.assertEqual(s + 2 * c, a + b + carry)
        for a in range(16):
            for b in range(16):
                trace = addition_trace(a, b)
                value = sum(step["sum"] << step["column"] for step in trace)
                self.assertEqual(value + (trace[-1]["carry_out"] << 4), a + b)

    def test_signed_words_and_xor(self):
        for value in range(-8, 8):
            self.assertEqual(signed(word(value, 4)), value)
        for a in (0, 1):
            for b in (0, 1):
                self.assertEqual(xor_forward(a, b)[-1], a ^ b)

    def test_canvas_geometry(self):
        bits = [0] * 196
        bits[0] = 1
        self.assertEqual(sum(dilation(bits)), 3)
        bits[0], bits[105] = 0, 1
        self.assertEqual(sum(dilation(bits)), 5)
        self.assertEqual(downsample([0] * 196), [0] * 49)
        self.assertEqual(downsample([1] * 196), [1] * 49)

    def test_real_seven_and_known_failure(self):
        seven = predict(canvases()["seven"])
        self.assertEqual(
            [sum(seven.canvas), sum(seven.dilated), sum(seven.features)], [18, 56, 20]
        )
        self.assertEqual(seven.scores, [-12, 1, 1, 5, 3, 4, -27, 24, -9, 5])
        self.assertEqual((seven.winner, seven.margin), (7, 19))
        one = predict(canvases()["one"])
        self.assertEqual((one.winner, one.margin), (4, 0))
        self.assertEqual(predict([0] * 196).winner, 1)

    def test_bitplanes_match_weighted_sum(self):
        model = weights()
        for canvas in canvases().values():
            prediction = predict(canvas)
            for k, row in enumerate(model["weights"]):
                p = planes(row, prediction.features)
                score = (
                    len(p["positive low"])
                    + 2 * len(p["positive high"])
                    - len(p["negative low"])
                    - 2 * len(p["negative high"])
                    + model["bias"][k]
                )
                self.assertEqual(score, prediction.scores[k])

    def test_code_excerpt_comes_from_artifact(self):
        self.assertEqual(css("ha_carry"), "--ha_carry: min(var(--a), var(--b));")
        self.assertIn("var(--fa_s1)", css("fa_sum"))
