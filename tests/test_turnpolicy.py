# tests/test_turnpolicy.py
"""laos.turnpolicy —— 轮转三态策略 speak/hold/stop + TurnBuffer.interject。

    /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_turnpolicy -v

来源：docs/research/2026-10-05-speech-weekly-spatial-duplex.md
- Duplex-MPE（arXiv 2609.31948）：全双工助手四能力中"何时答/何时沉默/何时停"
  三个时序决策 → TurnPolicy 状态机；
- SALMONN-duo（2609.34247）/ Context Spanning（2609.33443）：慢系统返回的
  结果要无缝织入当前轮 → TurnBuffer.interject 插队帧。
"""
from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.turnbuf import TurnBuffer  # noqa: E402
from laos.turnpolicy import TurnPolicy  # noqa: E402


class TestTurnPolicyDecide(unittest.TestCase):
    def setUp(self):
        self.p = TurnPolicy()  # 默认 tail=500 min_speech=200 min_hold=250 (ms)

    def test_completed_turn_with_tail_silence_speaks(self):
        ev = [(0, "user_start"), (600, "user_end")]  # 说 600ms
        self.assertEqual(self.p.decide(ev, now_ms=1200), "speak")  # 静默 600ms

    def test_short_silence_holds(self):
        ev = [(0, "user_start"), (600, "user_end")]
        self.assertEqual(self.p.decide(ev, now_ms=800), "hold")  # 只静默 200ms

    def test_blip_speech_below_min_speech_holds(self):
        ev = [(0, "user_start"), (100, "user_end")]  # 咔哒声：只说 100ms
        self.assertEqual(self.p.decide(ev, now_ms=2000), "hold")

    def test_min_hold_gate_holds(self):
        p = TurnPolicy(tail_silence_ms=200, min_speech_ms=100, min_hold_ms=800)
        ev = [(0, "user_start"), (300, "user_end")]
        self.assertEqual(p.decide(ev, now_ms=700), "hold")   # 只保持 400ms
        self.assertEqual(p.decide(ev, now_ms=1200), "speak")  # 900ms ≥ 800

    def test_user_onset_while_agent_speaks_stops(self):
        ev = [(0, "agent_start"), (400, "user_start")]
        self.assertEqual(self.p.decide(ev, now_ms=450), "stop")

    def test_stop_takes_priority_over_speak(self):
        # 第一轮已完成（静默充足），但代理已在说话且用户再次开口 → stop
        ev = [(0, "user_start"), (600, "user_end"),
              (1000, "agent_start"), (1400, "user_start")]
        self.assertEqual(self.p.decide(ev, now_ms=1500), "stop")

    def test_no_events_holds(self):
        self.assertEqual(self.p.decide([], now_ms=0), "hold")

    def test_user_still_speaking_holds(self):
        ev = [(0, "user_start")]
        self.assertEqual(self.p.decide(ev, now_ms=3000), "hold")

    def test_custom_tail_silence_takes_effect(self):
        p = TurnPolicy(tail_silence_ms=200)
        ev = [(0, "user_start"), (600, "user_end")]
        self.assertEqual(p.decide(ev, now_ms=850), "speak")  # 静默 250ms ≥ 200

    def test_unsorted_input_is_equivalent(self):
        a = [(0, "user_start"), (600, "user_end")]
        b = [(600, "user_end"), (0, "user_start")]
        self.assertEqual(self.p.decide(a, 1200), self.p.decide(b, 1200))

    def test_already_answered_turn_does_not_speak_again(self):
        # 代理已对该话轮应答（agent_start 在 user_end 之后）→ 不重复触发
        ev = [(0, "user_start"), (600, "user_end"),
              (1000, "agent_start"), (2000, "agent_end")]
        self.assertEqual(self.p.decide(ev, now_ms=3000), "hold")


class TestInterject(unittest.TestCase):
    """TurnBuffer.interject —— 插队帧（SALMONN-duo 委托返回 / Context Spanning 注入）。"""

    def test_interject_goes_to_head_of_pending(self):
        tb = TurnBuffer()
        tb.append("A")
        tb.interject("B")
        tb.deliver_more("BA")
        self.assertEqual(tb.delivered_text, "BA")
        self.assertEqual(tb.pending_text, "")

    def test_interject_works_after_interrupt(self):
        tb = TurnBuffer()
        tb.append("旧内容")
        tb.interrupt()
        tb.interject("查到了")
        self.assertEqual(tb.pending_text, "查到了")
        self.assertTrue(tb.interrupted)

    def test_empty_interject_is_noop(self):
        tb = TurnBuffer()
        tb.append("A")
        tb.interject("")
        self.assertEqual(tb.pending_text, "A")

    def test_concurrent_append_interject_thread_safe(self):
        tb = TurnBuffer()

        def appender():
            for _ in range(500):
                tb.append("a")

        def interjector():
            for _ in range(500):
                tb.interject("b")

        t1, t2 = threading.Thread(target=appender), threading.Thread(target=interjector)
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(len(tb.pending_text), 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
