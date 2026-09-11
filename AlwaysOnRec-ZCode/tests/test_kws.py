# tests/test_kws.py
"""laos/kws —— 零依赖包络 DTW 私有唤醒词 + scripts/kws_confusables.py 易混词生成。

    python -m unittest tests.test_kws -v
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from laos.kws import KeywordSpotter, envelope  # noqa: E402

SR = 8000


def phrase_pattern(burst_ms=(150, 120, 180), gap_ms=100, amp=0.5) -> list[int]:
    """三连能量脉冲 = 一个"词"的包络形状。"""
    out: list[int] = []
    for j, ms in enumerate(burst_ms):
        for i in range(SR * ms // 1000):
            out.append(int(amp * 20000 * math.sin(2 * math.pi * 440 * i / SR)))
        if j < len(burst_ms) - 1:
            out.extend([0] * (SR * gap_ms // 1000))
    return out


def other_pattern() -> list[int]:
    """不同的词：两连脉冲、更慢。"""
    return phrase_pattern(burst_ms=(250, 250), gap_ms=200)


class TestKeywordSpotter(unittest.TestCase):
    def test_match_same_phrase_with_gain_and_shift(self):
        spotter = KeywordSpotter()
        spotter.enroll("laosi", phrase_pattern(), SR)
        probe = phrase_pattern(amp=0.15)  # 音量差 3 倍多
        probe = [0] * (SR // 10) + probe  # 前面垫 100ms 偏移
        score = spotter.match(probe, SR, "laosi")
        self.assertTrue(score, f"同词（增益/偏移后）应命中，dist={score}")

    def test_reject_different_phrase(self):
        spotter = KeywordSpotter()
        spotter.enroll("laosi", phrase_pattern(), SR)
        self.assertFalse(spotter.match(other_pattern(), SR, "laosi"))

    def test_best_match_among_multiple(self):
        spotter = KeywordSpotter()
        spotter.enroll("hello", other_pattern(), SR)
        spotter.enroll("laosi", phrase_pattern(), SR)
        self.assertEqual(spotter.best(phrase_pattern(amp=0.3), SR)[0], "laosi")

    def test_envelope_normalizes_gain(self):
        e1 = envelope(phrase_pattern(amp=1.0), SR)
        e2 = envelope(phrase_pattern(amp=0.1), SR)
        self.assertAlmostEqual(max(e1), 1.0, places=6)
        for a, b in zip(e1, e2):
            self.assertAlmostEqual(a, b, delta=0.01)


class TestConfusables(unittest.TestCase):
    def test_deterministic_and_capped(self):
        from kws_confusables import generate
        a = generate("劳斯", ["lai", "si"], limit=20)
        b = generate("劳斯", ["lai", "si"], limit=20)
        self.assertEqual(a, b)
        self.assertLessEqual(len(a), 20)

    def test_contains_confusion_substitution(self):
        from kws_confusables import generate
        words = generate("劳斯", ["lai", "si"], limit=50)
        # n/l 混淆：lai -> nai 必然在表里
        self.assertIn("nai si", words)
        self.assertNotIn("lai si", words)  # 原词不算易混词

    def test_empty_syllables(self):
        from kws_confusables import generate
        self.assertEqual(generate("劳斯", []), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
