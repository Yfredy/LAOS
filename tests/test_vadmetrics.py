# tests/test_vadmetrics.py
"""laos.vadmetrics —— VAD 成对指标：FA/FR/F1 + BG-FAR（防装死闸门）。

    /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_vadmetrics -v

来源：docs/research/2026-10-06-four-wechat-articles.md 采纳件 B
（Foreground VAD, arXiv 2609.19856 的指标配对原则）：BG-FAR 单独看会被
"永远输出 0"的装死模型刷满——必须配 Foreground F1 当闸门。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.vadmetrics import evaluate_vad  # noqa: E402


class TestBasicRates(unittest.TestCase):
    def test_perfect_prediction(self):
        m = evaluate_vad([1, 1, 0, 0], [1, 1, 0, 0])
        self.assertEqual(m["f1"], 1.0)
        self.assertEqual(m["fa_rate"], 0.0)
        self.assertEqual(m["fr_rate"], 0.0)
        self.assertEqual(m["frames"], 4)

    def test_miss_and_false_alarm_rates(self):
        # ref 有 3 帧语音、1 帧静音：pred 漏 1 帧（fr=1/3）、静音帧误报（fa=1/1）
        m = evaluate_vad([1, 0, 1, 1], [1, 1, 1, 0])
        self.assertAlmostEqual(m["fr_rate"], 1 / 3)
        self.assertEqual(m["fa_rate"], 1.0)
        self.assertAlmostEqual(m["f1"], 2 / 3)  # P=2/3 R=2/3 → 2PR/(P+R)=2/3

    def test_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_vad([1, 0], [1, 0, 0])

    def test_background_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_vad([1, 0], [1, 0], background=[1])

    def test_empty_input_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_vad([], [])


class TestBgFar(unittest.TestCase):
    def test_bg_far_zero_without_background_mask(self):
        m = evaluate_vad([1, 1, 0, 0], [1, 1, 0, 0])
        self.assertIsNone(m["bg_far"])
        self.assertIsNone(m["bg_far_valid"])

    def test_background_false_alarms_counted(self):
        # 前景静音帧（ref=0）里背景有声（background=1），pred 全开 → BG-FAR=1.0
        m = evaluate_vad([1, 1, 1, 1], [1, 1, 0, 0], background=[0, 0, 1, 1])
        self.assertEqual(m["bg_far"], 1.0)
        self.assertTrue(m["bg_far_valid"])  # f1=2/3 ≥ 0.5：指标可信

    def test_bg_far_ignores_foreground_silence_without_background(self):
        # ref=0 但 background=0 的帧不算进 BG-FAR 分母
        m = evaluate_vad([1, 0, 1, 0], [1, 1, 0, 0], background=[0, 0, 1, 0])
        # 只有第 3 帧是"前景静音∧背景有声"，pred=1 → bg_far=1.0
        self.assertEqual(m["bg_far"], 1.0)

    def test_dead_model_invalidates_bg_far(self):
        # 装死模型：pred 全 0，BG-FAR 表面完美 = 0.0，但 f1=0 → 闸门判无效
        m = evaluate_vad([0, 0, 0, 0], [1, 1, 0, 0], background=[0, 0, 1, 1])
        self.assertEqual(m["bg_far"], 0.0)
        self.assertEqual(m["f1"], 0.0)
        self.assertFalse(m["bg_far_valid"])

    def test_f1_at_floor_is_valid(self):
        # f1 恰好等于闸门值 → 有效（>= 语义）
        m = evaluate_vad([1, 1, 0, 0, 0], [1, 0, 0, 0, 0], background=[0, 0, 0, 0, 1],
                         f1_floor=0.5)
        # tp=1 fp=1 fn=0 → P=0.5 R=1.0 f1=2*0.5/1.5=2/3 ≥ 0.5
        self.assertTrue(m["bg_far_valid"])

    def test_f1_below_floor_invalidates(self):
        m = evaluate_vad([1, 0, 0, 0, 0], [1, 1, 1, 0, 0], background=[0, 0, 0, 0, 1],
                         f1_floor=0.5)
        # tp=1 fp=0 fn=2 → P=1 R=1/3 f1=0.5? 2*(1/3)/(4/3)=0.5 → 恰在闸门
        # 换更差的：漏 2 报且多 1 假
        m = evaluate_vad([1, 1, 0, 0, 0], [1, 1, 1, 1, 0], background=[0, 0, 0, 0, 1],
                         f1_floor=0.5)
        # tp=2 fp=1 fn=2 → P=2/3 R=0.5 f1=2*(1/3)/(7/6)=4/7≈0.571
        m = evaluate_vad([0, 0, 0, 0, 0], [1, 1, 1, 1, 0], background=[0, 0, 0, 0, 1],
                         f1_floor=0.5)
        # f1=0 → 无效
        self.assertFalse(m["bg_far_valid"])

    def test_empty_bg_subset_returns_none(self):
        # 没有任何"前景静音∧背景有声"帧 → bg_far 未定义
        m = evaluate_vad([1, 1, 0, 0], [1, 1, 0, 0], background=[0, 0, 0, 0])
        self.assertIsNone(m["bg_far"])
        self.assertIsNone(m["bg_far_valid"])


if __name__ == "__main__":
    unittest.main()
