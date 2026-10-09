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


if __name__ == "__main__":
    unittest.main()
