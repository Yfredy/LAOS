# tests/test_binaural.py
"""laos.binaural —— 双耳空间线索（Goertzel 逐频点 ILD/IPD）。

    /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_binaural -v

来源：SAIL（arXiv 2609.34347）证明最小可用的空间流特征就是双耳相位差与
强度差——本模块是其纯 stdlib 内核版。测试全部用合成正弦（相位/幅度关系
解析可知），断言精确值。符号约定：IPD = angle(L) - angle(R)，正值 = 左耳
超前（声源偏左）；ILD = 20·log10(|L|/|R|)，正值 = 左耳更响。
"""
from __future__ import annotations

import cmath
import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.binaural import binaural_features, goertzel, ild_db, ipd_rad  # noqa: E402

SR = 48_000
N = 480  # 10ms 窗，1kHz 恰好整数 bin（k=10）


def sine(freq: float, n: int = N, sr: int = SR, phase: float = 0.0,
         amp: float = 1.0) -> list[int]:
    """合成 PCM16 正弦。"""
    return [int(amp * 20000.0 * math.sin(2 * math.pi * freq * i / sr + phase))
            for i in range(n)]


class TestGoertzel(unittest.TestCase):
    def test_matches_direct_dft_sum(self):
        x = sine(1000.0, phase=0.7)
        w = 2 * math.pi * 1000.0 / SR
        ref = sum(v * cmath.exp(-1j * w * i) for i, v in enumerate(x))
        g = goertzel(x, SR, 1000.0)
        self.assertAlmostEqual(abs(g), abs(ref), delta=abs(ref) * 1e-6)
        self.assertAlmostEqual(g.real, ref.real, delta=abs(ref) * 1e-6)
        self.assertAlmostEqual(g.imag, ref.imag, delta=abs(ref) * 1e-6)

    def test_magnitude_scales_with_amplitude(self):
        a1 = abs(goertzel(sine(1000.0, amp=0.5), SR, 1000.0))
        a2 = abs(goertzel(sine(1000.0, amp=1.0), SR, 1000.0))
        self.assertAlmostEqual(a2 / a1, 2.0, places=3)


class TestILD(unittest.TestCase):
    def test_half_amplitude_right_gives_plus_6db(self):
        left = sine(1000.0, amp=1.0)
        right = sine(1000.0, amp=0.5)
        vals = ild_db(left, right, SR, freqs=(1000.0,))
        self.assertAlmostEqual(vals[0], 20 * math.log10(2.0), delta=0.05)

    def test_identical_channels_zero_ild(self):
        x = sine(1000.0)
        vals = ild_db(x, x, SR, freqs=(1000.0,))
        self.assertAlmostEqual(vals[0], 0.0, delta=0.01)

    def test_silence_gives_zero_not_nan(self):
        z = [0] * N
        vals = ild_db(z, z, SR, freqs=(1000.0,))
        self.assertEqual(vals[0], 0.0)


class TestIPD(unittest.TestCase):
    def test_right_lagging_pi_over_3_gives_plus_pi_over_3(self):
        left = sine(1000.0, phase=0.0)
        right = sine(1000.0, phase=-math.pi / 3)   # 右耳滞后 π/3
        vals = ipd_rad(left, right, SR, freqs=(1000.0,))
        self.assertAlmostEqual(vals[0], math.pi / 3, delta=0.05)

    def test_identical_channels_zero_ipd(self):
        x = sine(1000.0, phase=0.3)
        vals = ipd_rad(x, x, SR, freqs=(1000.0,))
        self.assertAlmostEqual(vals[0], 0.0, delta=1e-6)


class TestFeatures(unittest.TestCase):
    def test_binaural_features_keys_and_length(self):
        left = sine(1000.0)
        right = sine(1000.0, amp=0.5, phase=-math.pi / 3)
        out = binaural_features(left, right, SR, freqs=(500.0, 1000.0, 2000.0))
        self.assertEqual(set(out), {"ild_db", "ipd_rad"})
        self.assertEqual(len(out["ild_db"]), 3)
        self.assertEqual(len(out["ipd_rad"]), 3)
        self.assertAlmostEqual(out["ild_db"][1], 20 * math.log10(2.0), delta=0.05)
        self.assertAlmostEqual(out["ipd_rad"][1], math.pi / 3, delta=0.05)


if __name__ == "__main__":
    unittest.main(verbosity=2)
