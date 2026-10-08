# tests/test_vad.py
"""laos/vad —— 零依赖流式 VAD（能量 + 滞回 + 补边）。

    python -m unittest tests.test_vad -v
"""
from __future__ import annotations

import math
import sys
import unittest
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.vad import (  # noqa: E402
    StreamingVAD, rms_dbfs, split_segments, wav_bytes,
)

SR = 8000


def synth(voiced_ms: int, silence_ms: int, reps: int) -> list[int]:
    """合成 [有声/静音]×reps 的 PCM16：有声 = 440Hz 正弦 @ 0.5 幅度。"""
    out = []
    for _ in range(reps):
        for i in range(SR * voiced_ms // 1000):
            out.append(int(0.5 * 26000 * math.sin(2 * math.pi * 440 * i / SR)))
        out.extend([0] * (SR * silence_ms // 1000))
    return out


class TestRms(unittest.TestCase):
    def test_silent_and_loud(self):
        self.assertLessEqual(rms_dbfs([0] * 1000), -100)
        full = [26000, -26000] * 500  # 满幅方波：0.79 幅度 ≈ -2dBFS
        self.assertGreater(rms_dbfs(full), -10)

    def test_empty(self):
        self.assertEqual(rms_dbfs([]), -120.0)


class TestSplitSegments(unittest.TestCase):
    def test_two_voiced_segments(self):
        samples = synth(300, 500, 2)  # 有-静-有-静
        segs = split_segments(samples, SR)
        self.assertEqual(len(segs), 2)
        # 每段有声核心 300ms（0.3*8000=2400 样本）
        for s, e in segs:
            self.assertGreater(e - s, 2400 * 0.9)

    def test_all_silence_no_segments(self):
        self.assertEqual(split_segments([0] * SR, SR), [])

    def test_all_voiced_one_segment(self):
        segs = split_segments(synth(1000, 0, 1), SR)
        self.assertEqual(len(segs), 1)


class TestStreamingMatchesBatch(unittest.TestCase):
    def test_chunks_yield_same_segments(self):
        samples = synth(300, 500, 2)
        batch = split_segments(samples, SR)

        vad = StreamingVAD(SR)
        got = []
        for i in range(0, len(samples), SR // 10):  # 100ms 块
            chunk = samples[i:i + SR // 10]
            pcm = b"".join(v.to_bytes(2, "little", signed=True) for v in chunk)
            for start_ms, wav in vad.feed(pcm):
                got.append((start_ms, len(wav)))

        self.assertEqual(len(got), len(batch))
        for (start_ms, wav_len), (s, e) in zip(got, batch):
            # 起点差 ≤ 1.5 帧喂入延迟；wav 至少含有声核心
            self.assertLessEqual(abs(start_ms - s * 1000 // SR), 200)
            self.assertGreater(wav_len, 2400 * 2 * 0.9)  # 字节 ≥ 有声核心样本×2

    def test_wav_bytes_playable(self):
        seg = synth(200, 0, 1)
        data = wav_bytes(seg, SR)
        import io
        with wave.open(io.BytesIO(data)) as w:
            self.assertEqual(w.getframerate(), SR)
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
