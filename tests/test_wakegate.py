# tests/test_wakegate.py
"""WakeGate（唤醒会话闸门）测试：四态机全路径。

语义对照上游 voicenpu_engine include/scheduler/wake_gate.h（AGPL-3.0，
语义复现非拷贝）。假时钟驱动超时路径。

    python -m unittest tests.test_wakegate -v
"""
from __future__ import annotations

import unittest

from laos.wakegate import WakeConfig, WakeGate, WakeState


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, sec):
        self.now += sec


def make_gate(clock, **overrides):
    cfg = WakeConfig(enabled=True, wake_words=["小乐"],
                     sleep_words=["小乐休息", "小乐再见"],
                     follow_up_timeout_sec=12.0, max_session_sec=120.0,
                     max_turns=6)
    for key, value in overrides.items():
        setattr(cfg, key, value)
    gate = WakeGate(clock)
    gate.configure(cfg)
    return gate


class WakeGateStates(unittest.TestCase):
    def test_disabled_passes_everything(self):
        gate = make_gate(FakeClock())
        gate.configure(WakeConfig(enabled=False))
        self.assertEqual(gate.state(), WakeState.LISTENING)
        result = gate.process("你好")
        self.assertTrue(result.answer)
        self.assertFalse(gate.wake())          # 关闭态唤醒无效

    def test_wake_only_from_sleeping(self):
        clock = FakeClock()
        gate = make_gate(clock)
        self.assertEqual(gate.state(), WakeState.SLEEPING)
        self.assertFalse(gate.process("小乐你好").answer)   # 文本永不唤醒
        self.assertTrue(gate.wake())                        # KWS 唤醒
        self.assertEqual(gate.state(), WakeState.LISTENING)
        self.assertFalse(gate.wake())                       # 已醒再 wake 无效

    def test_process_advances_to_processing(self):
        gate = make_gate(FakeClock())
        gate.wake()
        result = gate.process(" 今天天气怎么样 ")
        self.assertTrue(result.answer)
        self.assertEqual(result.text, "今天天气怎么样")      # 去空白归一化
        self.assertEqual(gate.state(), WakeState.PROCESSING)

    def test_sleep_word_returns_to_sleep(self):
        gate = make_gate(FakeClock())
        gate.wake()
        result = gate.process("小乐休息吧")
        self.assertFalse(result.answer)
        self.assertTrue(result.slept)
        self.assertEqual(gate.state(), WakeState.SLEEPING)

    def test_empty_text_dropped(self):
        gate = make_gate(FakeClock())
        gate.wake()
        result = gate.process("  ")
        self.assertFalse(result.answer)
        self.assertFalse(result.slept)
        self.assertEqual(gate.state(), WakeState.LISTENING)  # 不迁移

    def test_processing_backchannel_swallowed(self):
        # R1（ARVIS 波）：播报中的附和（"嗯嗯"）吞掉——播报继续不打断
        gate = make_gate(FakeClock())
        gate.wake()
        gate.process("第一句")
        result = gate.process("嗯嗯")
        self.assertFalse(result.answer)
        self.assertTrue(result.backchannel)
        self.assertFalse(result.slept)
        self.assertEqual(gate.state(), WakeState.PROCESSING)

    def test_processing_real_text_barges_in(self):
        # R1：播报中真打断（终稿权威）——让位后按正常轮处理
        gate = make_gate(FakeClock())
        gate.wake()
        gate.process("第一句")
        result = gate.process("不是这个意思")
        self.assertTrue(result.answer)
        self.assertFalse(result.backchannel)
        self.assertEqual(gate.state(), WakeState.PROCESSING)   # 新 turn 处理中
        self.assertEqual(gate._turns, 2)

    def test_processing_sleep_word_sleeps(self):
        # R1 行为变更：播报中喊休眠词同样生效（旧语义直接丢弃）
        gate = make_gate(FakeClock())
        gate.wake()
        gate.process("你好")
        result = gate.process("小乐休息")
        self.assertFalse(result.answer)
        self.assertTrue(result.slept)
        self.assertEqual(gate.state(), WakeState.SLEEPING)

    def test_speech_started_during_processing_stays(self):
        # R1 行为变更：播报中开口不再直接让位——等终稿过话轮路由
        gate = make_gate(FakeClock())
        gate.wake()
        gate.process("你好")
        gate.speech_started()
        self.assertEqual(gate.state(), WakeState.PROCESSING)
        # 随后的终稿才定夺：附和吞 / 真打断让位
        self.assertTrue(gate.process("换个问题").answer)

    def test_barge_classifier_injection(self):
        gate = make_gate(FakeClock())
        gate.wake()
        gate.process("第一句")
        gate.set_barge_classifier(lambda text: True)   # 全吞（语义档 continue）
        result = gate.process("真打断的话")
        self.assertFalse(result.answer)
        self.assertTrue(result.backchannel)
        self.assertEqual(gate.state(), WakeState.PROCESSING)
        gate.set_barge_classifier(None)                # 恢复关键词档
        self.assertTrue(gate.process("真打断的话").answer)

    def test_barge_classifier_exception_fails_to_interrupt(self):
        # 分类器崩了按真打断——宁可让位也不装聋
        gate = make_gate(FakeClock())
        gate.wake()
        gate.process("第一句")
        gate.set_barge_classifier(lambda text: 1 / 0)
        result = gate.process("嗯嗯")
        self.assertTrue(result.answer)
        self.assertFalse(result.backchannel)

    def test_backchannel_words_config(self):
        gate = make_gate(FakeClock(), backchannel_words=["收到"])
        gate.wake()
        gate.process("第一句")
        self.assertTrue(gate.process("收到").backchannel)
        self.assertFalse(gate.process("嗯嗯").backchannel)   # 不在自定义表

    def test_max_turns_sleeps(self):
        gate = make_gate(FakeClock(), max_turns=2)
        gate.wake()
        self.assertTrue(gate.process("一").answer)
        gate.finish_turn()
        gate.speech_started()
        self.assertTrue(gate.process("二").answer)
        gate.finish_turn()
        gate.speech_started()
        third = gate.process("三")
        self.assertFalse(third.answer)
        self.assertFalse(third.slept)                         # 静默回睡
        self.assertEqual(gate.state(), WakeState.SLEEPING)

    def test_finish_turn_then_follow_up_timeout(self):
        clock = FakeClock()
        gate = make_gate(clock)
        gate.wake()
        clock.advance(1.0)
        gate.process("你好")
        gate.finish_turn(delay_sec=2.0)                       # 播报 2s 并入窗口
        self.assertEqual(gate.state(), WakeState.FOLLOW_UP)
        clock.advance(13.9)                                   # < 2 + 12
        self.assertEqual(gate.state(), WakeState.FOLLOW_UP)
        clock.advance(0.2)
        self.assertEqual(gate.state(), WakeState.SLEEPING)

    def test_speech_started_returns_to_listening(self):
        gate = make_gate(FakeClock())
        gate.wake()
        gate.process("你好")
        gate.finish_turn()
        self.assertEqual(gate.state(), WakeState.FOLLOW_UP)
        gate.speech_started()
        self.assertEqual(gate.state(), WakeState.LISTENING)
        self.assertTrue(gate.process("继续").answer)

    def test_barge_in_only_during_processing(self):
        gate = make_gate(FakeClock())
        self.assertFalse(gate.barge_in())
        gate.wake()
        self.assertFalse(gate.barge_in())
        gate.process("你好")
        self.assertTrue(gate.barge_in())
        self.assertEqual(gate.state(), WakeState.LISTENING)

    def test_session_timeout_forces_sleep(self):
        clock = FakeClock()
        gate = make_gate(clock)
        gate.wake()
        clock.advance(119.0)
        self.assertEqual(gate.state(), WakeState.LISTENING)
        clock.advance(1.1)
        self.assertEqual(gate.state(), WakeState.SLEEPING)

    def test_tick_reports_change(self):
        clock = FakeClock()
        gate = make_gate(clock)
        gate.wake()
        gate.process("你好")
        gate.finish_turn()
        self.assertFalse(gate.tick())
        clock.advance(13.0)
        self.assertTrue(gate.tick())
        self.assertEqual(gate.state_name(), "sleeping")


if __name__ == "__main__":
    unittest.main()
