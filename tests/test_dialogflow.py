# tests/test_dialogflow.py
"""dialogflow —— 对话管线装配：路由防火墙 + 唤醒闸 + 对话队列 + JIT 记忆。

装配波次三件债的兑现处：
1. **phase="done"**（v0.21.0 遗留：d.dialog.turn 入队发 phase="queued"，
   完成态归装配层）——turn_done() 补发同 turn_id 的 phase="done"；
2. **JitMem 接入**（v0.24.0）：会话首个放行 turn 时 curate 一次（payload
   缓存供全会话），每轮 turn_done 把成败 outcome 回填；
3. **env 覆盖**（接线波）：WakeConfig.from_env + PauseWindow 参数 env 化。

入口防火墙：wake/asr/barge_in 先过 EventRouter（evroute.py，esp-claw
事件规则表转译），dropped 的事件不进对话核——"录音事件先过治理再进管线"。

    python -m unittest tests.test_dialogflow -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.dialogflow import DialogPipeline  # noqa: E402
from laos.evroute import EventRouter  # noqa: E402
from laos.jitmem import Curator  # noqa: E402
from laos.memory import MemoryStore  # noqa: E402
from laos.wakegate import WakeConfig, WakeGate  # noqa: E402


def make_pipeline(rules=None, curator=None, events=None):
    wake = WakeGate()
    wake.configure(WakeConfig(
        enabled=True, wake_words=["小劳"],
        sleep_words=["退下"], max_turns=2, follow_up_timeout_sec=5.0,
        max_session_sec=60.0))
    router = EventRouter(rules=rules)
    # on_event 协议为两参 (event, fields)——sink 适配成 (name, fields) 元组
    if events is None:
        sink = None
    else:
        def sink(name, fields):
            events.append((name, fields))
    return DialogPipeline(wake_gate=wake, router=router,
                          curator=curator, on_event=sink)


class TestSessionFlow(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.events = []
        self.store = MemoryStore(Path(self._td.name) / "memory.jsonl")
        self.store.remember("fact", "意式浓缩咖啡的配方", tags=["配方"])
        self.curator = Curator(self.store)
        self.pipe = make_pipeline(curator=self.curator, events=self.events)

    def tearDown(self):
        self._td.cleanup()

    def _wake_and_say(self, text):
        self.assertTrue(self.pipe.wake())
        return self.pipe.asr_final(text)

    def test_wake_then_first_turn_curates(self):
        payloads = []
        orig = self.curator.curate

        def spy(task, k=None):
            payloads.append(task)
            return orig(task, k)
        self.curator.curate = spy
        job = self._wake_and_say("咖啡配方是什么")
        self.assertIsNotNone(job)
        self.assertEqual(payloads, ["咖啡配方是什么"])   # 会话首 turn curate

    def test_second_turn_same_session_no_redundant_curate(self):
        self._wake_and_say("咖啡配方是什么")
        self.pipe.turn_done(True)
        self.pipe.speech_started()
        payloads = []
        orig = self.curator.curate

        def spy(task, k=None):
            payloads.append(task)
            return orig(task, k)
        self.curator.curate = spy
        job = self.pipe.asr_final("再说说豆子")
        self.assertIsNotNone(job)
        self.assertEqual(payloads, [])   # 同会话复用 payload

    def test_turn_done_emits_phase_done_and_outcome(self):
        job = self._wake_and_say("咖啡配方是什么")
        self.pipe.turn_done(True)
        dones = [e for e in self.events
                 if e[0] == "d.dialog.turn" and e[1].get("phase") == "done"]
        self.assertEqual(len(dones), 1)
        self.assertEqual(dones[0][1]["turn_id"], job.id)
        self.assertTrue(dones[0][1]["ok"])
        self.assertEqual(self.curator.stats()["outcomes"], 1)
        self.assertEqual(self.curator.stats()["successes"], 1)

    def test_turn_done_failure_outcome_false(self):
        self._wake_and_say("咖啡配方是什么")
        self.pipe.turn_done(False)
        self.assertEqual(self.curator.stats()["successes"], 0)
        self.assertEqual(self.curator.stats()["outcomes"], 1)

    def test_asr_while_sleeping_dropped_no_curate(self):
        job = self.pipe.asr_final("咖啡配方是什么")   # 未唤醒
        self.assertIsNone(job)
        self.assertEqual(self.curator.stats()["payloads"], 0)

    def test_sleep_word_ends_session(self):
        self._wake_and_say("咖啡配方是什么")
        self.pipe.turn_done(True)
        job = self.pipe.asr_final("退下")
        self.assertIsNone(job)
        self.assertEqual(self.pipe.wake_state(), "sleeping")

    def test_router_drop_is_event_firewall(self):
        # esp-claw DROP 语义进对话面：规则吞掉 asr.final，永不进唤醒闸
        rules = [{"id": "fw", "enabled": True, "consume_on_match": False,
                  "match": {"type": "asr.final", "text": "广告"},
                  "actions": [{"kind": "drop"}]}]
        self.pipe = make_pipeline(rules=rules, curator=self.curator,
                                  events=self.events)
        self.assertTrue(self.pipe.wake())
        job = self.pipe.asr_final("广告")
        self.assertIsNone(job)
        self.assertEqual(self.curator.stats()["payloads"], 0)  # 未 curate
        job2 = self.pipe.asr_final("正常问题")
        self.assertIsNotNone(job2)      # 未命中规则的事件照常进管线

    def test_barge_in_during_processing(self):
        self._wake_and_say("咖啡配方是什么")
        self.assertTrue(self.pipe.barge_in())
        self.assertEqual(self.pipe.wake_state(), "listening")

    def test_max_turns_sleeps(self):
        self._wake_and_say("第一句")
        self.pipe.turn_done(True)
        self.pipe.asr_final("第二句")
        self.pipe.turn_done(True)
        job = self.pipe.asr_final("第三句")
        self.assertIsNone(job)
        self.assertEqual(self.pipe.wake_state(), "sleeping")


class TestEnvOverrides(unittest.TestCase):
    def test_wake_config_from_env(self):
        env = {"LAOS_WAKE_ENABLED": "1",
               "LAOS_WAKE_WAKE_WORDS": "小劳, 劳拉",
               "LAOS_WAKE_SLEEP_WORDS": "退下,再见",
               "LAOS_WAKE_MAX_TURNS": "3",
               "LAOS_WAKE_SESSION_SEC": "90",
               "LAOS_WAKE_FOLLOWUP_SEC": "8"}
        cfg = WakeConfig.from_env(env)
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.wake_words, ["小劳", "劳拉"])
        self.assertEqual(cfg.sleep_words, ["退下", "再见"])
        self.assertEqual(cfg.max_turns, 3)
        self.assertEqual(cfg.max_session_sec, 90.0)
        self.assertEqual(cfg.follow_up_timeout_sec, 8.0)

    def test_wake_config_from_env_defaults(self):
        cfg = WakeConfig.from_env({})
        self.assertEqual(cfg, WakeConfig())   # 空 env = 全默认

    def test_wake_config_from_env_real_environ(self):
        # 不传 env → 读 os.environ（接线波：LAOS_WAKE_* 覆盖面）
        with mock.patch.dict(os.environ, {"LAOS_WAKE_MAX_TURNS": "9"}):
            cfg = WakeConfig.from_env()
        self.assertEqual(cfg.max_turns, 9)

    def test_dialog_obs_env(self):
        # LAOS_DIALOG_OBS_MS / LAOS_DIALOG_RESUME_MS → PauseWindow.configure
        pipe = make_pipeline()
        with mock.patch.dict(os.environ, {"LAOS_DIALOG_OBS_MS": "300",
                                          "LAOS_DIALOG_RESUME_MS": "120"}):
            pipe.configure_from_env()
        self.assertEqual(pipe.pause.observation_ms, 300)


if __name__ == "__main__":
    unittest.main()
