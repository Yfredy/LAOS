"""AudioRingBuffer —— 回放环形缓冲（纯 stdlib，内存即焚）。

    python -m unittest tests.test_ringbuf -v
"""
from __future__ import annotations

import io
import sys
import threading
import unittest
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.ringbuf import AudioRingBuffer  # noqa: E402


class TestAudioRingBuffer(unittest.TestCase):
    def test_feed_and_snapshot_returns_recent_bytes(self):
        ring = AudioRingBuffer(sample_rate=1000, max_seconds=2)
        ring.feed(b"\x01\x00" * 1000)          # 1s 的 0x0001 样本
        ring.feed(b"\x02\x00" * 1000)          # 1s 的 0x0002 样本
        self.assertEqual(ring.snapshot(1.0), b"\x02\x00" * 1000)

    def test_ring_trims_to_max_seconds(self):
        ring = AudioRingBuffer(sample_rate=1000, max_seconds=1)
        ring.feed(b"\x01\x00" * 1000)          # 1s
        ring.feed(b"\x02\x00" * 500)           # 再 0.5s → 超容裁旧
        self.assertAlmostEqual(ring.available_seconds(), 1.0, delta=0.01)
        self.assertNotIn(b"\x01\x00", ring.snapshot(0.2))

    def test_snapshot_more_than_available_returns_all(self):
        ring = AudioRingBuffer(sample_rate=1000, max_seconds=5)
        pcm = b"\x03\x00" * 500                # 0.5s
        ring.feed(pcm)
        self.assertEqual(ring.snapshot(20.0), pcm)
        self.assertAlmostEqual(ring.available_seconds(), 0.5, delta=0.01)

    def test_snapshot_empty_ring_returns_empty(self):
        ring = AudioRingBuffer(sample_rate=16000, max_seconds=60)
        self.assertEqual(ring.snapshot(15.0), b"")
        self.assertEqual(ring.available_seconds(), 0.0)

    def test_wav_bytes_header_is_playable_pcm16(self):
        ring = AudioRingBuffer(sample_rate=16000, max_seconds=10)
        pcm = bytes(range(256)) * 100          # 25600 B = 12800 样本 = 0.8s
        ring.feed(pcm)
        wav = ring.wav_bytes(0.8)
        with wave.open(io.BytesIO(wav), "rb") as w:
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 2)
            self.assertEqual(w.getframerate(), 16000)
            self.assertEqual(w.getnframes(), 12800)
            self.assertEqual(w.readframes(w.getnframes()), pcm)

    def test_concurrent_feed_and_snapshot_is_safe(self):
        ring = AudioRingBuffer(sample_rate=16000, max_seconds=30)
        errors: list[Exception] = []

        def feeder():
            try:
                for _ in range(200):
                    ring.feed(b"\x00\x01" * 1600)   # 每块 0.1s
            except Exception as exc:               # pragma: no cover
                errors.append(exc)

        th = threading.Thread(target=feeder)
        th.start()
        for _ in range(50):
            snap = ring.snapshot(5.0)
            self.assertLessEqual(len(snap), 5 * 16000 * 2)
        th.join()
        self.assertFalse(errors)


if __name__ == "__main__":
    unittest.main()
