# tests/test_confgate.py
"""laos.confgate —— 置信度三段闸：本地执行 / 云端校验 / 丢弃。

    /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_confgate -v

来源：docs/research/2026-10-06-four-wechat-articles.md 采纳件 A
（EdgeAI-KWS 端侧部署的边云置信度分流回调）+ 2026-10-06-qnn-workspace-study.md
裁决 B（SER 概率低时不应触发上层动作）。隐私默认：cloud_enabled=False 时
中段置信度直接丢弃——纯本地模式不上传。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.confgate import ConfidenceGate  # noqa: E402


class TestConfidenceGateBands(unittest.TestCase):
    def setUp(self):
        self.g = ConfidenceGate()  # 默认 local=0.9 cloud=0.7

    def test_high_confidence_executes_locally(self):
        self.assertEqual(self.g.decide(0.95), "local")

    def test_boundary_at_local_is_local(self):
        self.assertEqual(self.g.decide(0.9), "local")

    def test_mid_confidence_goes_to_cloud(self):
        self.assertEqual(self.g.decide(0.8), "cloud")

    def test_boundary_at_cloud_is_cloud(self):
        self.assertEqual(self.g.decide(0.7), "cloud")

    def test_low_confidence_drops(self):
        self.assertEqual(self.g.decide(0.5), "drop")

    def test_zero_drops(self):
        self.assertEqual(self.g.decide(0.0), "drop")

    def test_perfect_score_executes_locally(self):
        self.assertEqual(self.g.decide(1.0), "local")


class TestConfidenceGateCloudDisabled(unittest.TestCase):
    def test_mid_band_drops_when_cloud_disabled(self):
        g = ConfidenceGate(cloud_enabled=False)
        self.assertEqual(g.decide(0.8), "drop")   # 隐私默认：不上传

    def test_high_band_still_local_when_cloud_disabled(self):
        g = ConfidenceGate(cloud_enabled=False)
        self.assertEqual(g.decide(0.95), "local")


class TestConfidenceGateValidation(unittest.TestCase):
    def test_cloud_at_or_above_local_rejected(self):
        with self.assertRaises(ValueError):
            ConfidenceGate(local=0.7, cloud=0.7)
        with self.assertRaises(ValueError):
            ConfidenceGate(local=0.6, cloud=0.8)

    def test_out_of_range_thresholds_rejected(self):
        with self.assertRaises(ValueError):
            ConfidenceGate(local=1.1)
        with self.assertRaises(ValueError):
            ConfidenceGate(cloud=0.0)

    def test_out_of_range_score_rejected(self):
        g = ConfidenceGate()
        with self.assertRaises(ValueError):
            g.decide(1.5)
        with self.assertRaises(ValueError):
            g.decide(-0.1)


if __name__ == "__main__":
    unittest.main()
