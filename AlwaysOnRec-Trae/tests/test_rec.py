# tests/test_rec.py
"""drv_rec —— VAD 触发式录音会话驱动（FakeSoundDevice 注入，无真机）。

    python -m unittest tests.test_rec -v
"""
from __future__ import annotations

import math
import sys
import time
import unittest
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))

import drv_rec  # noqa: E402

SR = drv_rec.SAMPLE_RATE


def synth_pcm(ms_voiced: int, ms_silence: int, reps: int) -> bytes:
    """合成 [有声/静音]×reps 的 PCM16LE 字节。"""
    out = bytearray()
    for _ in range(reps):
        for i in range(SR * ms_voiced // 1000):
            v = int(0.5 * 26000 * math.sin(2 * math.pi * 440 * i / SR))
            out += v.to_bytes(2, "little", signed=True)
        out += b"\x00\x00" * (SR * ms_silence // 1000)
    return bytes(out)


class FakeInputStream:
    """按回调节奏推送预置音频的假流。"""

    def __init__(self, callback, blocks: list[bytes], blocksize_ms: int):
        self._cb = callback
        self._blocks = blocks
        self._blocksize = blocksize_ms
        self.stopped = False

    def start(self):
        for b in self._blocks:
            if self.stopped:
                break
            self._cb(b, None, None, None)

    def stop(self):
        self.stopped = True

    def close(self):
        pass


class RecCase(unittest.TestCase):
    def setUp(self):
        self._td = Path(__file__).parent / "_rec_tmp"
        self._td.mkdir(exist_ok=True)
        drv_rec.set_output_dir(self._td)
        drv_rec._reset()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._td, ignore_errors=True)
        drv_rec._reset()
        drv_rec.set_output_dir(None)

    def _start_with(self, audio: bytes, threshold=-35.0):
        chunk = SR // 10 * 2  # 100ms 块
        blocks = [audio[i:i + chunk] for i in range(0, len(audio), chunk)]

        def factory(samplerate, blocksize, dtype, callback):
            return FakeInputStream(callback, blocks, 100)

        drv_rec.set_input_factory(factory)
        return drv_rec.rec_start(threshold_dbfs=threshold)

    def test_two_voiced_segments_two_wavs(self):
        audio = synth_pcm(400, 600, 2)  # 有-静-有-静
        out = self._start_with(audio)
        self.assertIn("OK", out)
        stop = drv_rec.rec_stop()
        self.assertIn("2", stop)  # 2 段
        wavs = list(self._td.glob("rec-*.wav"))
        self.assertEqual(len(wavs), 2)
        for w in wavs:
            with wave.open(str(w)) as f:
                self.assertEqual(f.getframerate(), SR)
                self.assertGreater(f.getnframes(), SR * 300 // 1000)  # ≥300ms

    def test_disabled_by_env(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"LAOS_REC": "0"}):
            with self.assertRaises(PermissionError):
                drv_rec.rec_start()

    def test_gc_removes_stale_only(self):
        import os
        old = self._td / "rec-0000-old.wav"
        old.write_bytes(b"x")
        past = time.time() - 3600
        os.utime(old, (past, past))
        fresh = self._td / "rec-9999-fresh.wav"
        fresh.write_bytes(b"y")
        removed = drv_rec.rec_gc(keep_hours=0.5)
        self.assertIn("removed 1", removed)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_status(self):
        st = drv_rec.rec_status()
        self.assertIn("recording=False", st)


if __name__ == "__main__":
    unittest.main(verbosity=2)
