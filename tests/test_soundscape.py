"""soundscape —— 频域声景特征（Goertzel 分带 + LUFS 复用，纯 stdlib）。

    python -m unittest tests.test_soundscape -v
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.soundscape import BANDS, aggregate, describe, render  # noqa: E402


def _sine_pcm(seconds: float, freq: float, sr: int = 16000,
              amp: float = 0.5) -> bytes:
    import array
    n = int(seconds * sr)
    a = array.array("h",
                    (int(amp * 32767 * math.sin(2 * math.pi * freq * i / sr))
                     for i in range(n)))
    return a.tobytes()


class TestSoundscape(unittest.TestCase):
    # 信号一律 0.5s：响度计 400ms 窗/100ms hop 至少出两块（0.3s 会走
    # -inf→floor 路径，正弦 LUFS 断言会失真）
    def test_sine_peaks_at_its_band(self):
        feats = describe(_sine_pcm(0.5, 1000))
        self.assertEqual(feats["peak_band"], 1000)
        others = [v for b, v in feats["bands_db"].items() if b != 1000]
        self.assertGreater(feats["bands_db"][1000], max(others) + 6.0)

    def test_flatness_within_unit_range(self):
        for pcm in (_sine_pcm(0.5, 500), _sine_pcm(0.5, 2000)):
            self.assertGreaterEqual(describe(pcm)["flatness"], 0.0)
            self.assertLessEqual(describe(pcm)["flatness"], 1.0)

    def test_silence_floors_without_raising(self):
        feats = describe(b"\x00\x00" * 8000)  # 0.5s 全零 → 全程 <-70dB 门下
        self.assertEqual(feats["lufs"], -120.0)
        self.assertEqual(feats["plr"], 0.0)
        for v in feats["bands_db"].values():
            self.assertLessEqual(v, -100.0)

    def test_short_signal_floors_not_inf(self):
        # <0.4s 信号：integrated_loudness 返回 -inf，describe 必须钳到 floor
        feats = describe(_sine_pcm(0.2, 1000))
        self.assertEqual(feats["lufs"], -120.0)  # -inf 一律钳到 floor
        self.assertTrue(feats["lufs"] != float("-inf"))

    def test_empty_pcm_safe(self):
        feats = describe(b"")
        self.assertEqual(set(feats), {"lufs", "true_peak_dbtp", "plr",
                                      "bands_db", "flatness", "peak_band"})
        self.assertEqual(feats["bands_db"], {b: -120.0 for b in BANDS})

    def test_aggregate_averages(self):
        f1 = describe(_sine_pcm(0.5, 500))
        f2 = describe(_sine_pcm(0.5, 2000))
        agg = aggregate([f1, f2])
        self.assertAlmostEqual(agg["lufs"], (f1["lufs"] + f2["lufs"]) / 2,
                               delta=0.15)
        self.assertAlmostEqual(
            agg["bands_db"][500],
            (f1["bands_db"][500] + f2["bands_db"][500]) / 2, delta=0.15)

    def test_render_compact_line(self):
        feats = describe(_sine_pcm(0.5, 1000))
        line = render(feats, "14", 3)
        self.assertIn("14时", line)
        self.assertIn("3段", line)
        self.assertIn("LUFS", line)


if __name__ == "__main__":
    unittest.main()
