# tests/test_telemetry_hooks.py
"""埋点发射钩子测试（Task 2）：wakegate/dialogsched 可选 on_event 回调。

三事件最小发射点（docs/design/2026-10-07-instrumentation-design.md §3.5
D 类字段表；laos/telemetry.py EVENT_FIELDS 注册表为同源契约）：
- d.wake.state_change：wake() 醒 / process() 入 Processing / 四条休眠路径
  （sleep_word、max_turns、session_timeout、followup_timeout）；终审 T2
  补发三迁移 speech_started()/barge_in()/finish_turn()（reason=speech/
  barge_in/finish_turn，设计 §298 六函数发射点自此全覆盖）；
- d.dialog.turn：DialogQueue.enqueue 成功入队（无明文 text，sha8 脱敏）；
- d.speculative.cancel：PauseWindow.handle_speech_activity 返回 True。

另测：字段名与设计注册表一致（计数脱敏级，无明文 request/text 值）、
回调异常被吞掉（埋点永不影响主链路）、不注入回调零行为变化。
生产核（wakegate/dialogsched）不 import telemetry——本测试跨查注册表
仅属测试侧契约校验，装配层接线在后续任务。

fix round 1：①设计 §325 必须级取消路径（enqueue 清队 latest_only_
dropped + register_dialog 非投机轮作废 superseded）；②dialog.turn 加
phase="queued"（一轮一条契约：装配层完成态将发 phase="done"）；
③钩子字段经 TelemetryEmitter 落盘不丢（allowlist 已注册）。
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from laos.dialogsched import DialogQueue, GenerationGate, PauseWindow
from laos.telemetry import (EVENT_FIELDS, GLOBAL_FORBIDDEN_FIELDS,
                            TelemetryEmitter)
from laos.wakegate import WakeConfig, WakeGate

# 每事件预期字段全集（修复轮后全部字段都在设计 §3.5 注册表 +
# telemetry.EVENT_FIELDS 内——②③ 注册补齐，无"任务补充字段"残留）
EXPECTED_FIELDS = {
    "d.wake.state_change": {"from", "to", "reason", "turns", "session_ms"},
    "d.dialog.turn": {"turn_id", "generation", "use_llm", "speculative",
                      "merged_segments", "utter_len", "utter_sha8", "phase"},
}
# d.speculative.cancel 按取消路径分集（三路径字段并集已全部注册）
CANCEL_FIELDS_BY_REASON = {
    "resume_cancel": {"dialog_id", "reason", "merged", "tokens_wasted_est",
                      "resume_samples"},
    "latest_only_dropped": {"dialog_id", "reason", "merged",
                            "tokens_wasted_est", "dropped_ids"},
    "superseded": {"dialog_id", "reason", "merged", "tokens_wasted_est"},
}


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
    """d.wake.state_change：六迁移点（醒/入 Processing/四休眠路径 + 终审
    T2 补发的 speech_started/barge_in/finish_turn 三迁移）。"""

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

    # ---- 终审 T2 补发：speech_started / barge_in / finish_turn 三迁移 ----
    # （设计 §3.5 发射点清单 §298 六函数的空窗半数；reason 枚举：
    #   speech / barge_in / finish_turn；无状态变更的空调不发）

    def test_speech_started_emits_from_followup(self):
        clock, col = FakeClock(), Collector()
        gate = make_gate(clock, col)
        gate.wake()
        gate.process("一")                              # → processing
        gate.finish_turn()                              # → follow_up
        gate.speech_started()                           # follow_up → listening
        self.assertEqual(col.of("d.wake.state_change")[-1], {
            "from": "follow_up", "to": "listening", "reason": "speech",
            "turns": 1, "session_ms": 0})

    def test_speech_started_emits_from_processing(self):
        col = Collector()
        gate = make_gate(FakeClock(), col)
        gate.wake()
        gate.process("一")                              # → processing
        gate.speech_started()                           # processing → listening
        self.assertEqual(col.of("d.wake.state_change")[-1], {
            "from": "processing", "to": "listening", "reason": "speech",
            "turns": 1, "session_ms": 0})

    def test_speech_started_idle_states_emit_nothing(self):
        col = Collector()
        gate = make_gate(FakeClock(), col)
        gate.speech_started()                           # sleeping：空转不发
        gate.wake()                                     # → listening（1 条）
        gate.speech_started()                           # listening：无变更不发
        self.assertEqual(len(col.of("d.wake.state_change")), 1)

    def test_barge_in_emits_processing_to_listening(self):
        col = Collector()
        gate = make_gate(FakeClock(), col)
        gate.wake()
        gate.process("一")                              # → processing
        self.assertTrue(gate.barge_in())
        self.assertEqual(col.of("d.wake.state_change")[-1], {
            "from": "processing", "to": "listening", "reason": "barge_in",
            "turns": 1, "session_ms": 0})

    def test_barge_in_rejected_state_emits_nothing(self):
        col = Collector()
        gate = make_gate(FakeClock(), col)
        gate.wake()                                     # listening 态打断无效
        self.assertFalse(gate.barge_in())
        self.assertEqual(len(col.of("d.wake.state_change")), 1)

    def test_finish_turn_emits_processing_to_followup(self):
        clock, col = FakeClock(), Collector()
        gate = make_gate(clock, col)
        gate.wake()
        gate.process("一")                              # → processing
        gate.finish_turn(delay_sec=2.0)                # → follow_up
        self.assertEqual(col.of("d.wake.state_change")[-1], {
            "from": "processing", "to": "follow_up", "reason": "finish_turn",
            "turns": 1, "session_ms": 0})
        clock.advance(15.0)                             # 2+12s 窗口到期
        gate.state()
        self.assertEqual(col.of("d.wake.state_change")[-1]["reason"],
                         "followup_timeout", "补发后 FollowUp 窗口语义不变")

    def test_finish_turn_idle_state_emits_nothing(self):
        col = Collector()
        gate = make_gate(FakeClock(), col)
        gate.wake()                                     # listening 态空转
        gate.finish_turn()
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
            "utter_sha8": hashlib.sha256(text.encode()).hexdigest()[:8],
            "phase": "queued"}])                                  # ②
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


class CancelPathHooks(unittest.TestCase):
    """① 设计 §325 必须级取消路径：latest-only 清队 + 非投机轮作废投机轮。"""

    def test_enqueue_clear_emits_latest_only_dropped(self):
        col = Collector()
        queue = DialogQueue(PauseWindow(FakeClock()), GenerationGate(),
                            on_event=col)
        queue.enqueue(False, "第一句")
        queue.enqueue(False, "第二句")            # 清掉 id=1 的排队任务
        self.assertEqual(col.of("d.speculative.cancel"), [{
            "dialog_id": 1, "reason": "latest_only_dropped", "merged": False,
            "tokens_wasted_est": 0, "dropped_ids": 1}])

    def test_enqueue_empty_queue_no_cancel(self):
        col = Collector()
        queue = DialogQueue(PauseWindow(FakeClock()), GenerationGate(),
                            on_event=col)
        queue.enqueue(False, "唯一一句")
        self.assertEqual(col.of("d.speculative.cancel"), [])

    def test_nonspeculative_register_supersedes_pending(self):
        col = Collector()
        pause = PauseWindow(FakeClock(10.0), on_event=col)
        pause.prepare_candidate("投机半句")
        pause.register_dialog(5, True, 11.0)      # 投机轮挂起
        pause.register_dialog(6, False, 0.0)      # 非投机新轮作废投机轮 5
        self.assertEqual(col.of("d.speculative.cancel"), [{
            "dialog_id": 5, "reason": "superseded", "merged": False,
            "tokens_wasted_est": 0}])

    def test_register_without_pending_no_event(self):
        col = Collector()
        pause = PauseWindow(FakeClock(10.0), on_event=col)
        pause.register_dialog(6, False, 0.0)      # 无挂起投机轮
        self.assertEqual(col.of("d.speculative.cancel"), [])

    def test_superseded_callback_exception_swallowed(self):
        pause = PauseWindow(FakeClock(10.0), on_event=RaisingCollector())
        pause.prepare_candidate("投机半句")
        pause.register_dialog(5, True, 11.0)
        pause.register_dialog(6, False, 0.0)      # 不抛
        self.assertEqual(pause._speculative_id, 0)


class SinkForwarding(unittest.TestCase):
    """③ 装配层转发形态：钩子负载经 TelemetryEmitter 落盘，注册字段不丢
    （use_llm/phase/resume_samples/dropped_ids），且无 telemetry.strip 警告。"""

    def test_hook_fields_survive_sink(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "tel.jsonl"
        with TelemetryEmitter(path, throttle_sec=0.0,
                              clock=FakeClock(1000.0)) as em:
            self.assertTrue(em.emit("d.dialog.turn", module="dialogsched",
                                    fields={"turn_id": 1, "generation": 1,
                                            "use_llm": True,
                                            "speculative": False,
                                            "merged_segments": 2,
                                            "utter_len": 6,
                                            "utter_sha8": "0123abcd",
                                            "phase": "queued"}))
            self.assertTrue(em.emit(
                "d.speculative.cancel", module="dialogsched",
                fields={"dialog_id": 1, "reason": "latest_only_dropped",
                        "merged": False, "tokens_wasted_est": 0,
                        "dropped_ids": 1}))
            self.assertTrue(em.emit(
                "d.speculative.cancel", module="dialogsched",
                fields={"dialog_id": 2, "reason": "resume_cancel",
                        "merged": True, "tokens_wasted_est": 0,
                        "resume_samples": 2000}))
        rows = [json.loads(ln)
                for ln in path.read_text(encoding="utf-8").splitlines()]
        turn = next(r for r in rows if r["event"] == "d.dialog.turn")
        self.assertEqual(turn["fields"]["phase"], "queued")        # ② 落盘行
        self.assertIs(turn["fields"]["use_llm"], True)            # ③ 不丢
        by_reason = {r["fields"]["reason"]: r for r in rows
                     if r["event"] == "d.speculative.cancel"}
        self.assertEqual(by_reason["latest_only_dropped"]["fields"]
                         ["dropped_ids"], 1)
        self.assertEqual(by_reason["resume_cancel"]["fields"]
                         ["resume_samples"], 2000)
        self.assertEqual([r for r in rows if r["event"] == "telemetry.strip"],
                         [])


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
            if event == "d.speculative.cancel":
                expected = CANCEL_FIELDS_BY_REASON[fields["reason"]]
            else:
                expected = EXPECTED_FIELDS[event]
            self.assertEqual(set(fields), expected, event)
            self.assertTrue(set(fields) <= set(EVENT_FIELDS[event]),
                            f"{event}: {set(fields) - set(EVENT_FIELDS[event])} "
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
