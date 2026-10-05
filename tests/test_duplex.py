# tests/test_duplex.py
"""laos.duplex —— 双工时序度量（Duplex-MPE 四能力中三个时序项）。

    /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_duplex -v

测试策略：全部手写合成事件时间线，断言精确数值——分析器是纯函数，无音频/
真机依赖。来源：docs/research/2026-10-05-speech-weekly-spatial-duplex.md
（Duplex-MPE arXiv 2609.31948：发起/准确/沉默/停止四能力中，发起、沉默、
停止是纯时序量，OS 层可客观计量；"准确"归 ASR/Jev 层，不在本模块）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.duplex import DuplexMetrics, analyze, summarize  # noqa: E402


class TestAnalyze(unittest.TestCase):
    def test_response_latency_pairs_user_end_to_next_agent_start(self):
        m = analyze([(0.0, "user_start"), (1.0, "user_end"),
                     (1.35, "agent_start"), (2.5, "agent_end")])
        self.assertEqual(len(m.response_latencies), 1)
        self.assertAlmostEqual(m.response_latencies[0], 0.35)

    def test_premature_response_counted_when_agent_starts_during_user_speech(self):
        m = analyze([(0.0, "user_start"), (2.0, "user_end"),
                     (1.5, "agent_start"), (3.0, "agent_end")])
        self.assertEqual(m.premature_responses, 1)
        # 抢话的 agent_start 先于 user_end，不算响应延迟
        self.assertEqual(m.response_latencies, [])

    def test_agent_start_in_gap_after_earlier_turn_pairs_with_latest_user_end(self):
        # 第一轮 (0,1) 已结束；第二轮开口 2.0 未结束时代理抢话 2.5 ——
        # 既不计抢话后的新响应延迟，也不许倒挂配到第一轮
        m = analyze([(0.0, "user_start"), (1.0, "user_end"),
                     (2.0, "user_start"), (2.5, "agent_start"),
                     (3.0, "user_end"), (4.0, "agent_end")])
        self.assertEqual(m.premature_responses, 1)
        self.assertEqual(m.response_latencies, [])

    def test_barge_in_latency_to_agent_end(self):
        m = analyze([(0.0, "agent_start"), (5.0, "barge_in"), (5.12, "agent_end")])
        self.assertEqual(len(m.barge_in_latencies), 1)
        self.assertAlmostEqual(m.barge_in_latencies[0], 0.12)
        self.assertEqual(m.interrupts, 1)

    def test_overlap_duration_intersects_intervals(self):
        m = analyze([(0.0, "user_start"), (2.0, "user_end"),
                     (1.0, "agent_start"), (3.0, "agent_end")])
        self.assertEqual(m.overlap_durations, [1.0])
        self.assertAlmostEqual(m.overlap_ratio, 0.25)
        # 重叠的同时该 agent_start 也构成一次抢话（用户还没说完）
        self.assertEqual(m.premature_responses, 1)

    def test_empty_timeline_gives_zero_ratio_not_error(self):
        m = analyze([])
        self.assertEqual(m.overlap_ratio, 0.0)
        self.assertEqual(m.total_user_speech, 0.0)
        self.assertEqual(m.total_agent_speech, 0.0)

    def test_horizon_truncates_unpaired_events(self):
        m = analyze([(0.0, "user_start"), (1.0, "user_end"), (12.0, "agent_start")])
        self.assertEqual(m.response_latencies, [])

    def test_unclosed_intervals_dropped(self):
        m = analyze([(0.0, "user_start"), (1.0, "user_end"), (2.0, "agent_start")])
        self.assertEqual(m.total_agent_speech, 0.0)
        self.assertEqual(m.total_user_speech, 1.0)

    def test_unsorted_input_is_sorted_first(self):
        a = analyze([(0.0, "user_start"), (1.0, "user_end"), (1.5, "agent_start")])
        b = analyze([(1.5, "agent_start"), (0.0, "user_start"), (1.0, "user_end")])
        self.assertEqual(a.response_latencies, b.response_latencies)
        self.assertEqual(a.total_user_speech, b.total_user_speech)


class TestSummarize(unittest.TestCase):
    def test_json_serializable_with_full_metrics(self):
        m = analyze([(0.0, "user_start"), (1.0, "user_end"), (1.4, "agent_start"),
                     (3.0, "agent_end"), (3.2, "barge_in"), (3.3, "agent_end")])
        out = summarize(m)
        import json
        json.dumps(out)  # 可序列化即通过
        self.assertAlmostEqual(out["response_latency"]["median"], 0.4)
        self.assertEqual(out["interrupts"], 1)

    def test_empty_metrics_fields_are_none(self):
        out = summarize(DuplexMetrics())
        self.assertIsNone(out["response_latency"]["median"])
        self.assertIsNone(out["response_latency"]["p90"])
        self.assertEqual(out["overlap_ratio"], 0.0)
        self.assertEqual(out["interrupts"], 0)
        self.assertEqual(out["response_latency"]["n"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
