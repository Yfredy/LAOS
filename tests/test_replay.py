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
        os.environ["LAOS_REC"] = "0"
        try:
            with self.assertRaises(PermissionError):
                drv_mic.mic_replay()
        finally:
            del os.environ["LAOS_REC"]

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
        self.assertEqual(drv_mic._ring_seconds_from_env(), 30.0)
        os.environ["LAOS_REPLAY_RING_S"] = "9999"
        self.assertEqual(drv_mic._ring_seconds_from_env(), 120.0)
        os.environ["LAOS_REPLAY_RING_S"] = "3"
        self.assertEqual(drv_mic._ring_seconds_from_env(), 5.0)
        os.environ["LAOS_REPLAY_RING_S"] = "abc"
        self.assertEqual(drv_mic._ring_seconds_from_env(), 30.0)
        del os.environ["LAOS_REPLAY_RING_S"]


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

    def test_replay_denied_without_cap(self):
        pid2 = self.kernel.spawn(name="noright", caps=["msg.*"],
                                 ctx=ContextManager(system_prompt="t",
                                                    max_tokens=2000)).pid
        result = asyncio.run(self.kernel.syscall(pid2, "rec.replay", {}))
        self.assertFalse(result.ok)
        self.assertIn("EPERM", result.text)

    def test_replay_missing_mic_driver_fails_enoent(self):
        del self.kernel.drivers["mic"]
        result = asyncio.run(self.kernel.syscall(self.pid, "rec.replay", {}))
        self.assertFalse(result.ok)
        self.assertIn("ENOENT", result.text)

    def test_replay_private_tools_marks_taint(self):
        from laos.sentinel import Sentinel, SentinelConfig
        self.kernel.sentinel = Sentinel(SentinelConfig(mode="auto"))
        asyncio.run(self.kernel.syscall(self.pid, "rec.replay", {}))
        self.assertTrue(self.kernel.sentinel.is_tainted(self.pid))


if __name__ == "__main__":
    unittest.main()
