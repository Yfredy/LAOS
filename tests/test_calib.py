# tests/test_calib.py
"""calib 概率校准度量测试：Brier 分数 / ECE / 可靠性曲线。

语义依据 docs/research/2026-10-07-cloudflare-clef.md §二/§三：Clef 用
Brier loss 概率校准 + RLCD——决策模型要对概率负责，这三个函数是评判尺。

手算反例锚点：probs=[1,0,1] vs outcomes=[1,0,0] → Brier = (0+0+1)/3 = 1/3；
ECE 例 [0.05,0.15,0.95,1.0] vs [0,1,1,1] bins=10 →
    1/4*|0.05-0| + 1/4*|0.15-1| + 2/4*|0.975-1| = 0.2375。

    python -m unittest tests.test_calib -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos import calib  # noqa: E402
from laos.calib import brier_score, ece, reliability  # noqa: E402


class TestBrierScore(unittest.TestCase):
    def test_perfect_calibration_zero(self):
        # 预测概率与 0/1 实际完全一致 → 均方误差 0
        self.assertEqual(brier_score([1, 0, 1, 0], [1, 0, 1, 0]), 0.0)

    def test_hand_example_one_third(self):
        # 手算反例：(1-1)^2 + (0-0)^2 + (1-0)^2 = 1，均值 1/3
        self.assertAlmostEqual(brier_score([1, 0, 1], [1, 0, 0]), 1 / 3)

    def test_fractional_hand_example(self):
        # (0.8-1)^2 + (0.4-0)^2 = 0.04 + 0.16 = 0.20，均值 0.1
        self.assertAlmostEqual(brier_score([0.8, 0.4], [1, 0]), 0.1)

    def test_fully_miscalibrated_is_one(self):
        # 全部自信且全错 → 上界 1.0
        self.assertEqual(brier_score([1, 0], [0, 1]), 1.0)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            brier_score([], [])

    def test_prob_out_of_bounds_rejected(self):
        for bad in (-0.1, 1.01, -1, 2, float("nan"), float("inf")):
            with self.assertRaises(ValueError, msg=repr(bad)):
                brier_score([0.5, bad], [1, 0])

    def test_prob_must_be_numeric(self):
        for bad in ("0.5", None, True):
            with self.assertRaises(ValueError, msg=repr(bad)):
                brier_score([bad], [1])

    def test_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            brier_score([0.5, 0.5], [1])

    def test_outcomes_must_be_binary(self):
        for bad in (2, 0.5, -1, "yes", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                brier_score([0.5], [bad])

    def test_outcomes_accept_bool(self):
        # bool 是二元真值的自然表示：((0.8-1)^2+(0.2-0)^2)/2 = 0.04
        self.assertAlmostEqual(brier_score([0.8, 0.2], [True, False]), 0.04)


class TestECE(unittest.TestCase):
    def test_perfect_calibration_zero(self):
        self.assertEqual(ece([1, 0, 1, 0], [1, 0, 1, 0]), 0.0)

    def test_hand_example(self):
        # 桶 0: |0.05-0|=0.05 (n=1)；桶 1: |0.15-1|=0.85 (n=1)；
        # 桶 9: |0.975-1|=0.025 (n=2，0.95 与 1.0 同桶)
        got = ece([0.05, 0.15, 0.95, 1.0], [0, 1, 1, 1], bins=10)
        self.assertAlmostEqual(got, 0.25 * 0.05 + 0.25 * 0.85 + 0.5 * 0.025)

    def test_single_bin(self):
        # bins=1：全样本一桶，avg_p=1.0、freq=0.5 → ECE=0.5
        got = ece([1.0, 1.0], [1, 0], bins=1)
        self.assertAlmostEqual(got, 0.5)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            ece([], [], bins=10)

    def test_bins_below_one_rejected(self):
        for bad in (0, -1, -10):
            with self.assertRaises(ValueError, msg=repr(bad)):
                ece([0.5], [1], bins=bad)

    def test_bins_non_integer_rejected(self):
        for bad in (2.5, "10", True):
            with self.assertRaises(ValueError, msg=repr(bad)):
                ece([0.5], [1], bins=bad)

    def test_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            ece([0.5], [1, 0], bins=10)


class TestReliability(unittest.TestCase):
    def test_bucket_boundaries_left_closed_right_open(self):
        # 0.1/0.2/0.3/0.5/0.7 各归左端所在桶；1.0 归末桶（最后一桶闭）
        probs = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0]
        outcomes = [0, 1, 0, 1, 1, 0, 1, 1]
        curve = reliability(probs, outcomes, bins=10)
        lowers = [row[0] for row in curve]
        self.assertEqual(len(curve), 7)  # 桶 4/6/8 空，不出现
        self.assertEqual(lowers.count(0.1), 1)  # 0.1 ∈ [0.1,0.2)，不入桶 0
        for lower in (0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9):
            self.assertAlmostEqual(lowers.count(lower), 1, msg=str(lower))

    def test_float_boundary_pitfalls_bins_100(self):
        # 真坑值回归：bins=100 时 0.29*100=28.999999999999996、
        # 0.57*100=56.99999999999999、0.58*100=57.99999999999999——
        # BIN_EPSILON 置 0 会各错落一桶（0.3*10/0.7*10 精确等于 3.0/7.0，
        # 不是坑值；bins=10 边界用例对其零覆盖）
        curve = reliability([0.29, 0.57, 0.58], [1, 0, 1], bins=100)
        self.assertEqual([row[3] for row in curve], [1, 1, 1])
        self.assertAlmostEqual(curve[0][0], 0.29)  # 桶 29（eps=0 错落 28）
        self.assertAlmostEqual(curve[1][0], 0.57)  # 桶 57（eps=0 错落 56）
        self.assertAlmostEqual(curve[2][0], 0.58)  # 桶 58（eps=0 错落 57）

    def test_row_semantics(self):
        # 桶 7（0.8 两样本）与桶 1（0.2 一样本）的 avg_p/freq/n
        curve = reliability([0.8, 0.8, 0.2], [1, 0, 0], bins=10)
        self.assertEqual(len(curve), 2)
        low, avg_p, freq, n = curve[0]
        self.assertAlmostEqual(low, 0.2)  # 0.2 ∈ [0.2,0.3)
        self.assertAlmostEqual(avg_p, 0.2)
        self.assertAlmostEqual(freq, 0.0)
        self.assertEqual(n, 1)
        low, avg_p, freq, n = curve[1]
        self.assertAlmostEqual(low, 0.8)  # 0.8 ∈ [0.8,0.9)
        self.assertAlmostEqual(avg_p, 0.8)
        self.assertAlmostEqual(freq, 0.5)
        self.assertEqual(n, 2)

    def test_last_bucket_closed_includes_one(self):
        # 1.0 与 0.95 同入末桶 [0.9, 1.0]
        curve = reliability([1.0, 0.95], [1, 1], bins=10)
        self.assertEqual(len(curve), 1)
        low, avg_p, freq, n = curve[0]
        self.assertAlmostEqual(low, 0.9)
        self.assertAlmostEqual(avg_p, 0.975)
        self.assertAlmostEqual(freq, 1.0)
        self.assertEqual(n, 2)

    def test_perfect_calibration_diagonal(self):
        # 完美校准：每个非空桶 freq == avg_p（可靠性曲线在对角线上）。
        # 桶 0：0.0×1 全 0；桶 7：0.75×4 命中 3；桶 9：1.0×2 全中
        curve = reliability([1, 0, 0.75, 0.75, 0.75, 0.75, 1.0, 0.0],
                            [1, 0, 1, 1, 1, 0, 1, 0], bins=10)
        self.assertEqual(len(curve), 3)
        for _, avg_p, freq, _n in curve:
            self.assertAlmostEqual(avg_p, freq)

    def test_single_bin(self):
        curve = reliability([0.3, 0.9, 1.0], [0, 1, 1], bins=1)
        self.assertEqual(len(curve), 1)
        low, avg_p, freq, n = curve[0]
        self.assertAlmostEqual(low, 0.0)
        self.assertAlmostEqual(avg_p, (0.3 + 0.9 + 1.0) / 3)
        self.assertAlmostEqual(freq, 2 / 3)
        self.assertEqual(n, 3)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            reliability([], [], bins=10)

    def test_bins_rejected(self):
        with self.assertRaises(ValueError):
            reliability([0.5], [1], bins=0)
        with self.assertRaises(ValueError):
            reliability([0.5], [1], bins=1.5)

    def test_input_validation_shared(self):
        # 与 brier 同源的校验：越界/长度不齐/非二元 outcomes
        with self.assertRaises(ValueError):
            reliability([1.5], [1], bins=10)
        with self.assertRaises(ValueError):
            reliability([0.5, 0.5], [1], bins=10)
        with self.assertRaises(ValueError):
            reliability([0.5], [0.5], bins=10)


class TestEceReliabilityConsistency(unittest.TestCase):
    def test_ece_recomputable_from_reliability(self):
        # ECE 可由 reliability 输出按 n/N 加权重算（两函数共用一条链路）
        probs = [0.05, 0.15, 0.95, 1.0, 0.42, 0.42, 0.42]
        outcomes = [0, 1, 1, 1, 1, 0, 1]
        curve = reliability(probs, outcomes, bins=10)
        total = sum(row[3] for row in curve)
        self.assertEqual(total, len(probs))  # 只滤空桶，不丢样本
        recomputed = sum(n / total * abs(avg_p - freq)
                         for _, avg_p, freq, n in curve)
        self.assertAlmostEqual(ece(probs, outcomes, bins=10), recomputed)

    def test_consistency_holds_across_bin_counts(self):
        probs = [0.11, 0.32, 0.32, 0.58, 0.74, 0.99, 0.05, 0.66]
        outcomes = [0, 1, 0, 1, 1, 1, 0, 0]
        for bins in (1, 2, 3, 4, 8, 16):
            curve = reliability(probs, outcomes, bins=bins)
            total = sum(row[3] for row in curve)
            recomputed = sum(n / total * abs(avg_p - freq)
                             for _, avg_p, freq, n in curve)
            self.assertAlmostEqual(ece(probs, outcomes, bins=bins),
                                   recomputed, msg=f"bins={bins}")

    def test_calibration_beats_overconfidence(self):
        # 同样的答案对错率下，诚实概率（0.6/0.6）的 ECE 低于过度自信（1.0）
        honest = ece([0.6] * 10, [1, 1, 1, 1, 1, 1, 0, 0, 0, 0], bins=10)
        overconfident = ece([1.0] * 10, [1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
                            bins=10)
        self.assertLess(honest, overconfident)
        self.assertAlmostEqual(overconfident, 0.4)  # |1.0 - 0.6|，单桶


if __name__ == "__main__":
    unittest.main()
