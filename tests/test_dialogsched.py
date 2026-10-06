# tests/test_dialogsched.py
"""对话调度核测试：generation 打断 / 投机 prefill 窗口 / latest-only 队列 /
麦克风闸 / 声控模式解析 / TTS 双后端路由。

语义对照上游 voicenpu_engine voice_scheduler.cpp / dialog_controller.cpp /
tts_backend.h（AGPL-3.0，语义复现非拷贝）。

    python -m unittest tests.test_dialogsched -v
"""
from __future__ import annotations

import unittest
from typing import List

from laos.dialogsched import (
    DialogQueue,
    GenerationGate,
    MicrophoneGate,
    PauseWindow,
    TtsRouter,
    parse_mode_request,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, sec):
        self.now += sec


class GenerationGateTests(unittest.TestCase):
    def test_interrupt_bumps_and_invalidates(self):
        gate = GenerationGate()
        g0 = gate.current()
        g1 = gate.interrupt()
        self.assertEqual(g1, g0 + 1)
        self.assertFalse(gate.is_current(g0))
        self.assertTrue(gate.is_current(g1))

    def test_on_interrupt_callback(self):
        calls: List[str] = []
        gate = GenerationGate(on_interrupt=lambda: calls.append("abort"))
        gate.interrupt()
        self.assertEqual(calls, ["abort"])


class PauseWindowTests(unittest.TestCase):
    def test_prepare_candidate_merges_after_cancel(self):
        clock = FakeClock()
        pause = PauseWindow(clock)
        first = pause.prepare_candidate("今天天气")
        self.assertEqual(first.text, "今天天气")
        self.assertEqual(first.merged_segments, 1)
        # 模拟投机轮被续说取消（置合并标志的最短路径）
        pause.register_dialog(1, speculative=True,
                              commit_deadline=first.commit_deadline)
        pause.handle_speech_activity(speech_started=True, speech_active=True,
                                     sample_count=pause.resume_min_samples)
        second = pause.prepare_candidate("怎么样呢")
        self.assertEqual(second.text, "今天天气，怎么样呢")
        self.assertEqual(second.merged_segments, 2)

    def test_deadline_is_observation_window(self):
        clock = FakeClock()
        pause = PauseWindow(clock)
        pause.configure(observation_ms=500, resume_min_ms=96)
        candidate = pause.prepare_candidate("你好")
        self.assertAlmostEqual(candidate.commit_deadline, 0.5)

    def test_non_speculative_cancels_pending_speculative(self):
        clock = FakeClock()
        pause = PauseWindow(clock)
        candidate = pause.prepare_candidate("你好")
        pause.register_dialog(7, speculative=True,
                              commit_deadline=candidate.commit_deadline)
        pause.register_dialog(8, speculative=False, commit_deadline=0.0)
        self.assertEqual(pause.commit_decision(7, clock()), "cancel")

    def test_resume_requires_min_samples(self):
        clock = FakeClock()
        pause = PauseWindow(clock)
        candidate = pause.prepare_candidate("你好")
        pause.register_dialog(1, speculative=True,
                              commit_deadline=candidate.commit_deadline)
        # 窗口内新语音起 → resume 候选
        self.assertFalse(pause.handle_speech_activity(True, True, 100))
        # 累计不足 1536 采样不取消
        self.assertFalse(pause.handle_speech_activity(False, True, 1000))
        # 语音中断 → resume 候选作废
        self.assertFalse(pause.handle_speech_activity(False, False, 0))
        self.assertFalse(pause.handle_speech_activity(False, True, 9999))

    def test_resume_cancel_path(self):
        clock = FakeClock()
        pause = PauseWindow(clock)
        candidate = pause.prepare_candidate("你好")
        pause.register_dialog(1, speculative=True,
                              commit_deadline=candidate.commit_deadline)
        self.assertTrue(pause.handle_speech_activity(True, True,
                                                     pause.resume_min_samples))
        self.assertEqual(pause.commit_decision(1, clock()), "cancel")
        self.assertTrue(pause.take_cancelled(1))
        self.assertFalse(pause.take_cancelled(1))            # 只可取一次

    def test_commit_decision_waits_then_commits(self):
        clock = FakeClock()
        pause = PauseWindow(clock)
        candidate = pause.prepare_candidate("你好")
        pause.register_dialog(1, speculative=True,
                              commit_deadline=candidate.commit_deadline)
        clock.advance(0.4)
        self.assertEqual(pause.commit_decision(1, clock()), "wait")
        clock.advance(0.2)
        self.assertEqual(pause.commit_decision(1, clock()), "commit")
        self.assertEqual(pause.commit_decision(1, clock()), "commit")  # 幂等

    def test_resume_extends_commit_deadline_by_200ms(self):
        clock = FakeClock()
        pause = PauseWindow(clock)
        candidate = pause.prepare_candidate("你好")
        pause.register_dialog(1, speculative=True,
                              commit_deadline=candidate.commit_deadline)
        pause.handle_speech_activity(True, True, 100)        # resume 候选
        clock.advance(0.6)                                   # 过了原 deadline
        self.assertEqual(pause.commit_decision(1, clock()), "wait")  # +200ms 内
        clock.advance(0.25)
        self.assertEqual(pause.commit_decision(1, clock()), "commit")

    def test_speech_started_outside_window_not_candidate(self):
        clock = FakeClock()
        pause = PauseWindow(clock)
        candidate = pause.prepare_candidate("你好")
        clock.advance(1.0)                                   # 窗口已过
        pause.register_dialog(1, speculative=True,
                              commit_deadline=candidate.commit_deadline)
        self.assertFalse(pause.handle_speech_activity(True, True, 9999))


class DialogQueueTests(unittest.TestCase):
    def test_latest_only(self):
        clock = FakeClock()
        pause = PauseWindow(clock)
        gate = GenerationGate()
        queue = DialogQueue(pause, gate, clock)
        job1 = queue.enqueue(True, "第一句")
        job2 = queue.enqueue(True, "第二句")
        self.assertEqual(queue.dropped, 1)
        popped = queue.pop()
        self.assertIs(popped, job2)
        self.assertIsNone(queue.pop())

    def test_empty_text_rejected(self):
        queue = DialogQueue(PauseWindow(FakeClock()), GenerationGate())
        self.assertIsNone(queue.enqueue(True, ""))

    def test_enqueue_bumps_generation(self):
        gate = GenerationGate()
        queue = DialogQueue(PauseWindow(FakeClock()), gate)
        job = queue.enqueue(True, "你好")
        self.assertTrue(gate.is_current(job.generation))


class MicrophoneGateTests(unittest.TestCase):
    def test_blocks_during_playback_then_frees(self):
        clock = FakeClock()
        gate = MicrophoneGate(sample_rate=16000, post_tts_guard_ms=400,
                              clock=clock)
        self.assertTrue(gate.allow(aec_ready=False, barge_in_enabled=True))
        gate.emit_audio(16000)                               # 1s 播报
        self.assertFalse(gate.allow(False, True))
        clock.advance(1.0)
        self.assertTrue(gate.allow(False, True))

    def test_barge_in_with_aec_always_allowed(self):
        gate = MicrophoneGate(clock=FakeClock())
        gate.emit_audio(16000)
        self.assertTrue(gate.allow(aec_ready=True, barge_in_enabled=True))

    def test_extend_guard(self):
        clock = FakeClock()
        gate = MicrophoneGate(sample_rate=16000, post_tts_guard_ms=400,
                              clock=clock)
        gate.emit_audio(16000)
        clock.advance(0.9)
        gate.extend_guard()                                   # 仍在播报 → +400ms
        self.assertFalse(gate.allow(False, True))
        clock.advance(0.5)
        self.assertTrue(gate.allow(False, True))


class ParseModeRequestTests(unittest.TestCase):
    def test_online(self):
        self.assertEqual(parse_mode_request("小乐，切换到在线模式"), "online")
        self.assertEqual(parse_mode_request("改成联网模式吧"), "online")

    def test_offline(self):
        self.assertEqual(parse_mode_request("小乐，切换到离线模式"), "offline")
        self.assertEqual(parse_mode_request("用本地模式"), "offline")

    def test_none_cases(self):
        self.assertIsNone(parse_mode_request("今天在线吗"))
        self.assertIsNone(parse_mode_request("又在线又离线怎么回事"))
        self.assertIsNone(parse_mode_request("在线离线" * 30))   # >60 字节


class FakeTts:
    def __init__(self, name, rate=44100, fail=False):
        self._name, self._rate, self.fail = name, rate, fail
        self.chunks: List[List[float]] = []

    def ready(self):
        return True

    def sample_rate(self):
        return self._rate

    def name(self):
        return self._name

    def cancel(self):
        pass

    def synthesize_stream(self, text, sink):
        if self.fail:
            return False
        self.chunks.append([0.1])
        return sink([0.1])


class TtsRouterTests(unittest.TestCase):
    def test_select_rejects_rate_mismatch(self):
        router = TtsRouter(FakeTts("offline", 44100), FakeTts("online", 24000))
        self.assertFalse(router.select("online"))
        self.assertEqual(router.name(), "offline")

    def test_online_failure_falls_back_when_nothing_emitted(self):
        online = FakeTts("online", fail=True)
        offline = FakeTts("offline")
        router = TtsRouter(offline, online)
        router.select("online")
        got: List[float] = []

        def sink(chunk: List[float]) -> bool:
            got.extend(chunk)
            return True

        self.assertTrue(router.synthesize_stream("你好", sink))
        self.assertTrue(got)
        self.assertTrue(router.take_fell_back())
        self.assertFalse(router.take_fell_back())             # 只报一次

    def test_no_fallback_mid_reply(self):
        # 在线后端发出第一块后失败：已出声，句中不换声线
        class HalfFail:
            def __init__(self):
                self.calls = 0

            def ready(self):
                return True

            def sample_rate(self):
                return 44100

            def name(self):
                return "half"

            def cancel(self):
                pass

            def synthesize_stream(self, text, sink):
                self.calls += 1
                if self.calls == 1:
                    return sink([0.5])
                return False

        offline = FakeTts("offline")
        router = TtsRouter(offline, HalfFail())
        router.select("online")
        got: List[float] = []
        self.assertFalse(router.synthesize_stream("你好", got.extend))
        self.assertEqual(got, [0.5])
        self.assertFalse(router.take_fell_back())

    def test_offline_failure_no_online_escalation(self):
        router = TtsRouter(FakeTts("offline", fail=True), FakeTts("online"))
        self.assertFalse(router.synthesize_stream("你好", lambda chunk: True))


if __name__ == "__main__":
    unittest.main()
