# tests/test_telemetry_hooks.py
"""埋点发射钩子测试（Task 2）：wakegate/dialogsched 可选 on_event 回调。

三事件最小发射点（docs/design/2026-10-07-instrumentation-design.md §3.5
D 类字段表；laos/telemetry.py EVENT_FIELDS 注册表为同源契约）：
- d.wake.state_change：wake() 醒 / process() 入 Processing / 四条休眠路径
  （sleep_word、max_turns、session_timeout、followup_timeout）；
- d.dialog.turn：DialogQueue.enqueue 成功入队（无明文 text，sha8 脱敏）；
- d.speculative.cancel：PauseWindow.handle_speech_activity 返回 True。

另测：字段名与设计注册表一致（计数脱敏级，无明文 request/text 值）、
回调异常被吞掉（埋点永不影响主链路）、不注入回调零行为变化。
生产核（wakegate/dialogsched）不 import telemetry——本测试跨查注册表
仅属测试侧契约校验，装配层接线在后续任务。
"""
import hashlib
import json
import unittest

from laos.dialogsched import DialogQueue, GenerationGate, PauseWindow
from laos.telemetry import EVENT_FIELDS, GLOBAL_FORBIDDEN_FIELDS
from laos.wakegate import WakeConfig, WakeGate

# 每事件预期字段全集（设计 §3.5 注册表字段 + 任务书点名的补充字段）
EXPECTED_FIELDS = {
    "d.wake.state_change": {"from", "to", "reason", "turns", "session_ms"},
    "d.dialog.turn": {"turn_id", "generation", "use_llm", "speculative",
                      "merged_segments", "utter_len", "utter_sha8"},
    "d.speculative.cancel": {"dialog_id", "reason", "merged",
                             "tokens_wasted_est", "resume_samples"},
}
# 任务书点名、但不在设计 §3.5 注册表内的补充字段（其余字段必须全部
# 落在 telemetry.EVENT_FIELDS 注册表内——字段名与设计一致的硬约束）
TASK_EXTRA_FIELDS = {"use_llm", "resume_samples"}


class FakeClock:
    def __init__(self, now: float = 0.0):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, sec: float) -> None:
        self.now += sec


class Collector:
    """注入用收集回调：按序记录 (event, fields)。"""

    def __init__(self):
        self.events = []

    def __call__(self, event: str, fields: dict) -> None:
        self.events.append((event, dict(fields)))

    def of(self, event: str) -> list:
        return [f for e, f in self.events if e == event]


class RaisingCollector:
    """异常回调：埋点必须吞掉，不得影响主链路。"""

    def __call__(self, event: str, fields: dict) -> None:
        raise RuntimeError("telemetry sink down")


def make_gate(clock, on_event=None, **cfg) -> WakeGate:
    opts = dict(enabled=True, wake_words=["小劳"], sleep_words=["闭嘴"],
                follow_up_timeout_sec=12.0, max_session_sec=120.0, max_turns=6)
    opts.update(cfg)
    gate = WakeGate(clock, on_event)
    gate.configure(WakeConfig(**opts))
    return gate


class WakeTransitionHook(unittest.TestCase):
    """d.wake.state_change：三迁移点（醒/入 Processing/四休眠路径）。"""

    def test_wake_emits_sleeping_to_listening(self):
        col = Collector()
        gate = make_gate(FakeClock(100.0), col)
        self.assertTrue(gate.wake())
        self.assertEqual(col.of("d.wake.state_change"), [{
            "from": "sleeping", "to": "listening", "reason": "wake",
            "turns": 0, "session_ms": 0}])

    def test_process_emits_listening_to_processing(self):
        col = Collector()
        gate = make_gate(FakeClock(), col)
        gate.wake()
        self.assertTrue(gate.process("你好").answer)
        self.assertEqual(col.of("d.wake.state_change")[-1], {
            "from": "listening", "to": "processing", "reason": "turn",
            "turns": 0, "session_ms": 0})

    def test_sleep_word_path_emits(self):
        col = Collector()
        gate = make_gate(FakeClock(), col)
        gate.wake()
        self.assertTrue(gate.process("闭嘴").slept)
        self.assertEqual(col.of("d.wake.state_change")[-1], {
            "from": "listening", "to": "sleeping", "reason": "sleep_word",
            "turns": 0, "session_ms": 0})

    def test_max_turns_path_emits(self):
        col = Collector()
        gate = make_gate(FakeClock(), col, max_turns=1)
        gate.wake()
        self.assertTrue(gate.process("一").answer)      # turns: 0 → 1
        gate.finish_turn()                              # → follow_up
        self.assertFalse(gate.process("二").answer)     # 轮数满，静默回睡
        self.assertEqual(col.of("d.wake.state_change")[-1], {
            "from": "follow_up", "to": "sleeping", "reason": "max_turns",
            "turns": 1, "session_ms": 0})

    def test_session_timeout_path_emits(self):
        clock, col = FakeClock(), Collector()
        gate = make_gate(clock, col)
        gate.wake()                                     # session_started = 0
        clock.advance(121.0)
        gate.state()                                    # 触发 _expire
        self.assertEqual(col.of("d.wake.state_change")[-1], {
            "from": "listening", "to": "sleeping", "reason": "session_timeout",
            "turns": 0, "session_ms": 121000})

    def test_followup_timeout_path_emits(self):
        clock, col = FakeClock(), Collector()
        gate = make_gate(clock, col)
        gate.wake()
        gate.process("一")
        gate.finish_turn()                              # deadline = 0 + 12s
        clock.advance(13.0)
        gate.state()
        self.assertEqual(col.of("d.wake.state_change")[-1], {
            "from": "follow_up", "to": "sleeping", "reason": "followup_timeout",
            "turns": 1, "session_ms": 13000})

    def test_rejected_calls_emit_nothing(self):
        col = Collector()
        gate = make_gate(FakeClock(), col)
        gate.wake()
        gate.wake()                                     # 已醒，拒绝迁移
        gate.process("")                                # 空文本丢弃
        self.assertEqual(len(col.of("d.wake.state_change")), 1)

    def test_callback_exception_swallowed(self):
        gate = make_gate(FakeClock(), RaisingCollector())
        self.assertTrue(gate.wake())
        self.assertTrue(gate.process("你好").answer)    # 主链路不受影响
        self.assertEqual(gate.state_name(), "processing")


class DialogTurnHook(unittest.TestCase):
    """d.dialog.turn：DialogQueue.enqueue 成功入队后发射（无明文 text）。"""

    def setUp(self):
        self.col = Collector()
        self.pause = PauseWindow(FakeClock(), on_event=self.col)
        self.queue = DialogQueue(self.pause, GenerationGate(),
                                 on_event=self.col)

    def test_enqueue_emits_dialog_turn(self):
        text = "今天天气怎么样"
        job = self.queue.enqueue(True, text)
        self.assertEqual(col0 := self.col.of("d.dialog.turn"), [{
            "turn_id": 1, "generation": 1, "use_llm": True,
            "speculative": False, "merged_segments": 1,
            "utter_len": len(text),
            "utter_sha8": hashlib.sha256(text.encode()).hexdigest()[:8]}])
        self.assertEqual(job.id, col0[0]["turn_id"])

    def test_second_enqueue_increments_turn_and_generation(self):
        self.queue.enqueue(True, "一")
        self.queue.enqueue(False, "二")
        second = self.col.of("d.dialog.turn")[1]
        self.assertEqual((second["turn_id"], second["generation"],
                          second["use_llm"]), (2, 2, False))

    def test_empty_enqueue_emits_nothing(self):
        self.assertIsNone(self.queue.enqueue(False, ""))
        self.assertEqual(self.col.events, [])

    def test_merged_speculative_enqueue_reports_segments(self):
        clock = FakeClock(10.0)
        pause = PauseWindow(clock, on_event=self.col)
        queue = DialogQueue(pause, GenerationGate(), on_event=self.col)
        pause.prepare_candidate("前半句")
        pause.register_dialog(1, True, 11.0)
        self.assertTrue(pause.handle_speech_activity(True, True, 2000))
        cand = pause.prepare_candidate("后半句")        # 续说合并，2 段
        queue.enqueue(False, cand.text, speculative=True,
                      merged_segments=cand.merged_segments)
        turn = self.col.of("d.dialog.turn")[-1]
        self.assertEqual((turn["merged_segments"], turn["speculative"],
                          turn["utter_len"]), (2, True, len(cand.text)))

    def test_callback_exception_swallowed(self):
        queue = DialogQueue(PauseWindow(FakeClock()), GenerationGate(),
                            on_event=RaisingCollector())
        job = queue.enqueue(True, "异常_sink下_照样入队")
        self.assertIsNotNone(job)


class SpeculativeCancelHook(unittest.TestCase):
    """d.speculative.cancel：handle_speech_activity 返回 True 的取消路径。"""

    def _armed(self, on_event):
        clock = FakeClock(10.0)
        pause = PauseWindow(clock, on_event=on_event)
        pause.prepare_candidate("句中停顿的话")
        pause.register_dialog(7, True, 11.0)            # 投机轮，commit 窗内
        return pause

    def test_resume_cancel_emits_event(self):
        col = Collector()
        pause = self._armed(col)
        self.assertTrue(pause.handle_speech_activity(True, True, 2000))
        self.assertEqual(col.of("d.speculative.cancel"), [{
            "dialog_id": 7, "reason": "resume_cancel", "merged": True,
            "tokens_wasted_est": 0, "resume_samples": 2000}])

    def test_below_threshold_no_cancel_event(self):
        col = Collector()
        pause = self._armed(col)
        self.assertFalse(pause.handle_speech_activity(True, True, 100))
        self.assertFalse(pause.handle_speech_activity(False, True, 100))
        self.assertEqual(col.of("d.speculative.cancel"), [])

    def test_callback_exception_swallowed(self):
        pause = self._armed(RaisingCollector())
        self.assertTrue(pause.handle_speech_activity(True, True, 2000))


class SchemaConformance(unittest.TestCase):
    """三事件字段名与设计 §3.5 注册表一致；事件负载无明文 request/text。"""

    def _collect_all(self) -> Collector:
        col = Collector()
        clock = FakeClock()
        gate = make_gate(clock, col)
        gate.wake()
        gate.process("明文探针话语XYZ123")
        pause = PauseWindow(FakeClock(10.0), on_event=col)
        pause.prepare_candidate("明文探针话语XYZ123")
        pause.register_dialog(1, True, 11.0)
        pause.handle_speech_activity(True, True, 2000)
        queue = DialogQueue(pause, GenerationGate(), on_event=col)
        queue.enqueue(True, "明文探针话语XYZ123")
        return col

    def test_field_names_match_design_registry(self):
        col = self._collect_all()
        self.assertTrue(col.events)
        for event, fields in col.events:
            self.assertEqual(set(fields), EXPECTED_FIELDS[event], event)
            core = set(fields) - TASK_EXTRA_FIELDS
            self.assertTrue(core <= set(EVENT_FIELDS[event]),
                            f"{event}: {core - set(EVENT_FIELDS[event])} "
                            "不在设计 §3.5 注册表内")

    def test_no_plaintext_leak(self):
        col = self._collect_all()
        for event, fields in col.events:
            self.assertFalse(set(fields) & GLOBAL_FORBIDDEN_FIELDS, event)
        self.assertNotIn("明文探针话语XYZ123", json.dumps(col.events))


class ZeroBehaviorWithoutHook(unittest.TestCase):
    """不注入 on_event（默认 None）：主链路行为不变的最小冒烟。"""

    def test_defaults_work(self):
        gate = WakeGate(FakeClock())
        gate.configure(WakeConfig(enabled=True, sleep_words=["闭嘴"]))
        self.assertTrue(gate.wake())
        self.assertTrue(gate.process("你好").answer)
        queue = DialogQueue(PauseWindow(FakeClock()), GenerationGate())
        self.assertIsNotNone(queue.enqueue(True, "你好"))


if __name__ == "__main__":
    unittest.main()
