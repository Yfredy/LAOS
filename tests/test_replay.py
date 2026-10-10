"""录音回放（rec.replay / mic.replay）——驱动工具 + 内核内建 + laosweb 端点。

    python -m unittest tests.test_replay -v

三层都在本文件：驱动工具直调（注入 _ring，无需声卡/conda）；内核内建用
_FakeDriver 替身注入 kernel.drivers；laosweb 端点测试在 tests/test_laosweb.py
（TestReplayApi，见 Task 4）。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))

import drv_mic  # noqa: E402
from laos.context import ContextManager  # noqa: E402
from laos.mcp import CallResult  # noqa: E402
from laos.ringbuf import AudioRingBuffer  # noqa: E402


class TestMicReplayTool(unittest.TestCase):
    """mic.replay 驱动工具（直调函数，注入 _ring；无需声卡）。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self._cwd = os.getcwd()
        os.chdir(self._td.name)  # var/ear/replay 写进临时目录
        drv_mic._ring = AudioRingBuffer(16000, 60)
        drv_mic._ring.feed(b"\x11\x22" * 16000)  # 1s 样本

    def tearDown(self):
        os.chdir(self._cwd)
        drv_mic._ring = None
        self._td.cleanup()

    def test_replay_writes_wav_and_json(self):
        out = json.loads(drv_mic.mic_replay(0.5))
        self.assertTrue(out["ok"])
        self.assertTrue(Path(out["wav"]).exists())
        self.assertEqual(out["sample_rate"], 16000)
        with wave.open(out["wav"], "rb") as w:
            self.assertEqual(w.getframerate(), 16000)
            self.assertEqual(w.getnframes(), 8000)  # 0.5s @16kHz

    def test_replay_more_than_ring_returns_available(self):
        out = json.loads(drv_mic.mic_replay(30))
        self.assertLessEqual(out["seconds"], 1.01)
        self.assertGreaterEqual(out["ring_seconds"], 0.99)

    def test_replay_disabled_under_laos_rec_0(self):
        prior = os.environ.get("LAOS_REC")  # 保存原值，测完还原（不裸 del）
        os.environ["LAOS_REC"] = "0"
        try:
            with self.assertRaises(PermissionError):
                drv_mic.mic_replay()
        finally:
            if prior is None:
                os.environ.pop("LAOS_REC", None)
            else:
                os.environ["LAOS_REC"] = prior

    def test_replay_without_ring_raises_enoent(self):
        drv_mic._ring = None
        with self.assertRaises(RuntimeError):
            drv_mic.mic_replay()

    def test_prune_keeps_last_20_snapshots(self):
        for _ in range(23):
            drv_mic.mic_replay(0.1)
        files = sorted(Path("var", "ear", "replay").glob("replay-*.wav"))
        self.assertEqual(len(files), 20)

    def test_ring_seconds_env_clamped_to_budget(self):
        # 内存预算红线：默认 30s、下限 5s、上限 120s、坏值回落 30s
        prior = os.environ.get("LAOS_REPLAY_RING_S")  # 保存原值，测完还原
        try:
            self.assertEqual(drv_mic._ring_seconds_from_env(), 30.0)
            os.environ["LAOS_REPLAY_RING_S"] = "9999"
            self.assertEqual(drv_mic._ring_seconds_from_env(), 120.0)
            os.environ["LAOS_REPLAY_RING_S"] = "3"
            self.assertEqual(drv_mic._ring_seconds_from_env(), 5.0)
            os.environ["LAOS_REPLAY_RING_S"] = "abc"
            self.assertEqual(drv_mic._ring_seconds_from_env(), 30.0)
        finally:
            if prior is None:
                os.environ.pop("LAOS_REPLAY_RING_S", None)
            else:
                os.environ["LAOS_REPLAY_RING_S"] = prior


class _FakeDriver:
    """MCPClient 替身：按工具名回放预制 CallResult（或 callable(args)）。"""

    def __init__(self, tools, results):
        self.tools = {t: None for t in tools}
        self._results = results

    def call_tool(self, name, args):
        r = self._results[name]
        return r(args) if callable(r) else r

    def close(self):  # shutdown() -> unload_driver() 会调 client.close()
        pass


class TestRecReplayBuiltin(unittest.TestCase):
    """内核内建 rec.replay：mic+ear 组装 / caps / 审计 / 降级路径。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        from laos.kernel import AgentKernel
        self.kernel = AgentKernel(Path(self._td.name) / "var")
        wav = Path(self._td.name) / "replay-0001-0.wav"
        wav.write_bytes(b"RIFF--fake-wav--bytes")
        snap = CallResult.ok_text(json.dumps(
            {"ok": True, "wav": str(wav), "seconds": 20,
             "ring_seconds": 25, "sample_rate": 16000}))
        tr = CallResult.ok_text(json.dumps(
            {"text": "刚刚没听清的那句话", "language": "zh", "emotions": [],
             "source": "funasr", "latency_ms": 100}))
        self.kernel.drivers["mic"] = _FakeDriver(["mic.replay"],
                                                  {"mic.replay": snap})
        self.kernel.drivers["ear"] = _FakeDriver(["ear.transcribe"],
                                                  {"ear.transcribe": tr})
        self.pid = self.kernel.spawn(name="replayer",
                                     caps=["rec.replay"],
                                     ctx=ContextManager(system_prompt="t",
                                                        max_tokens=2000)).pid

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def test_replay_combines_mic_and_ear(self):
        result = asyncio.run(self.kernel.syscall(
            self.pid, "rec.replay", {"seconds": 20}))
        self.assertTrue(result.ok, result.text)
        payload = json.loads(result.text)
        self.assertEqual(payload["text"], "刚刚没听清的那句话")
        self.assertEqual(payload["source"], "funasr")
        self.assertEqual(payload["seconds"], 20)

    def test_replay_transcribe_false_skips_ear(self):
        result = asyncio.run(self.kernel.syscall(
            self.pid, "rec.replay", {"seconds": 20, "transcribe": False}))
        payload = json.loads(result.text)
        self.assertEqual(payload["text"], "")
        self.assertEqual(payload["source"], "none")
        self.assertEqual(payload["transcribe_ms"], 0)

    def test_replay_writes_mic_privacy_audit_metadata_only(self):
        asyncio.run(self.kernel.syscall(self.pid, "rec.replay", {}))
        recs = [r for r in self.kernel.audit.records
                if r.get("event") == "mic" and r.get("tool") == "rec.replay"]
        self.assertEqual(len(recs), 1)
        self.assertNotIn("text", recs[0])  # 只记元数据，转写文本永不入审计
        self.assertIn("seconds", recs[0])
        # C1 收口：转写文本不得泄入任何审计记录——syscall 审计的 result
        # 字段曾带完整 payload JSON，必须逐条扫全部记录的所有值
        # （不只 event=="mic"）才能守住
        leaked = [r for r in self.kernel.audit.records
                  if any("刚刚没听清的那句话" in str(v) for v in r.values())]
        self.assertEqual(leaked, [], f"transcript leaked into audit: {leaked}")

    def test_replay_denied_without_cap(self):
        pid2 = self.kernel.spawn(name="noright", caps=["msg.*"],
                                 ctx=ContextManager(system_prompt="t",
                                                    max_tokens=2000)).pid
        result = asyncio.run(self.kernel.syscall(pid2, "rec.replay", {}))
        self.assertFalse(result.ok)
        self.assertIn("EPERM", result.text)
        # M2：内核拒绝（无 caps）也要落 event:"mic" 账（denied:true）——
        # 与 mic.* 被内核 _deny 拒绝同口径
        denied = [r for r in self.kernel.audit.records
                  if r.get("event") == "mic" and r.get("tool") == "rec.replay"]
        self.assertEqual(len(denied), 1)
        self.assertTrue(denied[0]["denied"])
        self.assertIn("EPERM", denied[0]["reason"])

    def test_replay_missing_mic_driver_fails_enoent(self):
        del self.kernel.drivers["mic"]
        result = asyncio.run(self.kernel.syscall(self.pid, "rec.replay", {}))
        self.assertFalse(result.ok)
        self.assertIn("ENOENT", result.text)
        # M2：驱动缺失的失败路径同样补 event:"mic" 账（ok:False 纯元数据
        # + 短 errno，无文本/音频）
        fails = [r for r in self.kernel.audit.records
                 if r.get("event") == "mic" and r.get("tool") == "rec.replay"]
        self.assertEqual(len(fails), 1)
        self.assertFalse(fails[0]["ok"])
        self.assertIn("ENOENT", fails[0]["errno"])
        self.assertNotIn("text", fails[0])

    def test_replay_private_tools_marks_taint(self):
        from laos.sentinel import Sentinel, SentinelConfig
        self.kernel.sentinel = Sentinel(SentinelConfig(mode="auto"))
        asyncio.run(self.kernel.syscall(self.pid, "rec.replay", {}))
        self.assertTrue(self.kernel.sentinel.is_tainted(self.pid))


if __name__ == "__main__":
    unittest.main()


class TestReplaySummarize(unittest.TestCase):
    """rec.replay summarize 扩展位（v0.38.0）：LLM 摘要软降级，永不炸回放。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        from laos.kernel import AgentKernel
        self.kernel = AgentKernel(Path(self._td.name) / "var")
        wav = Path(self._td.name) / "replay-0001-0.wav"
        wav.write_bytes(b"RIFF--fake-wav--bytes")
        snap = CallResult.ok_text(json.dumps(
            {"ok": True, "wav": str(wav), "seconds": 20,
             "ring_seconds": 25, "sample_rate": 16000}))
        tr = CallResult.ok_text(json.dumps(
            {"text": "刚才那段没听清的话，讲了三件事", "language": "zh",
             "emotions": [], "source": "funasr", "latency_ms": 100}))
        self.kernel.drivers["mic"] = _FakeDriver(["mic.replay"],
                                                  {"mic.replay": snap})
        self.kernel.drivers["ear"] = _FakeDriver(["ear.transcribe"],
                                                  {"ear.transcribe": tr})
        self.pid = self.kernel.spawn(name="summer",
                                     caps=["rec.replay"],
                                     ctx=ContextManager()).pid

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _call(self, **kw):
        return asyncio.run(self.kernel.syscall(self.pid, "rec.replay", kw))

    def test_summarize_true_produces_summary(self):
        import laos.llm as llm_mod

        class _FakeLLM:
            def chat(self, messages):
                return "讲了三件事的一句话摘要"

        orig = llm_mod.LLMClient.from_env
        llm_mod.LLMClient.from_env = classmethod(lambda cls: _FakeLLM())
        try:
            r = self._call(seconds=20, transcribe=True, summarize=True)
        finally:
            llm_mod.LLMClient.from_env = orig
        self.assertTrue(r.ok, r.text)
        p = json.loads(r.text)
        self.assertEqual(p["summary"], "讲了三件事的一句话摘要")
        self.assertEqual(p["summary_status"], "ok")

    def test_summarize_without_llm_soft_degrades(self):
        import laos.llm as llm_mod
        orig = llm_mod.LLMClient.from_env
        llm_mod.LLMClient.from_env = classmethod(lambda cls: None)
        try:
            r = self._call(seconds=20, transcribe=True, summarize=True)
        finally:
            llm_mod.LLMClient.from_env = orig
        self.assertTrue(r.ok, r.text)  # 回放本体永不因摘要失败
        p = json.loads(r.text)
        self.assertEqual(p["summary"], "")
        self.assertEqual(p["summary_status"], "unconfigured")

    def test_summarize_llm_error_soft_degrades(self):
        import laos.llm as llm_mod

        class _BadLLM:
            def chat(self, messages):
                raise llm_mod.LLMError("boom")

        orig = llm_mod.LLMClient.from_env
        llm_mod.LLMClient.from_env = classmethod(lambda cls: _BadLLM())
        try:
            r = self._call(seconds=20, transcribe=True, summarize=True)
        finally:
            llm_mod.LLMClient.from_env = orig
        self.assertTrue(r.ok, r.text)
        p = json.loads(r.text)
        self.assertEqual(p["summary"], "")
        self.assertEqual(p["summary_status"], "failed")

    def test_summarize_off_by_default_and_needs_transcribe(self):
        p = json.loads(self._call(seconds=20).text)
        self.assertEqual(p["summary_status"], "off")
        p2 = json.loads(self._call(seconds=20, transcribe=False,
                                    summarize=True).text)
        self.assertEqual(p2["summary_status"], "off")

    def test_audit_carries_summarize_flag(self):
        self._call(seconds=20, transcribe=True, summarize=True)
        recs = [r for r in self.kernel.audit.records
                if r.get("event") == "mic" and r.get("tool") == "rec.replay"]
        self.assertTrue(recs and recs[-1].get("summarize") is True)
