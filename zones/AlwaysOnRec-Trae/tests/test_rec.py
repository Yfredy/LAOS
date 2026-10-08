# tests/test_rec.py
"""drv_rec —— VAD 触发式录音会话驱动（FakeSoundDevice 注入，无真机）。

    python -m unittest tests.test_rec -v
"""
from __future__ import annotations

import io
import math
import sys
import time
import unittest
import wave
from pathlib import Path
from unittest import mock

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


def synth_wav(pcm: bytes) -> bytes:
    """PCM16LE 字节 → 合法 WAV 文件字节（与 StreamingVAD 落盘段同构）。"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm)
    return buf.getvalue()


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

    def _start_with(self, audio: bytes, threshold=-35.0, encoding="auto"):
        chunk = SR // 10 * 2  # 100ms 块
        blocks = [audio[i:i + chunk] for i in range(0, len(audio), chunk)]

        def factory(samplerate, blocksize, dtype, callback):
            return FakeInputStream(callback, blocks, 100)

        drv_rec.set_input_factory(factory)
        return drv_rec.rec_start(threshold_dbfs=threshold, encoding=encoding)

    def test_two_voiced_segments_two_wavs(self):
        audio = synth_pcm(400, 600, 2)  # 有-静-有-静
        # 显式 encoding="wav"：本用例钉住 VAD 分段语义（段必须能被 stdlib wave 解析）
        out = self._start_with(audio, encoding="wav")
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
        # Task 2 扩展字段：实际编码 / 累计淘汰数 / 目录总字节
        self.assertIn("encoding=", st)
        self.assertIn("evicted=", st)
        self.assertIn("bytes=", st)

    # ---- Task 2：Opus 编码（自动降级）全流程 ----

    def test_auto_encoding_degrades_to_wav(self):
        # 主测试路径：mock _SF_OK=False（无 soundfile/无 OPUS）→ auto 全流程落 .wav，不崩不丢段
        audio = synth_pcm(400, 600, 1)
        with mock.patch.object(drv_rec, "_SF_OK", False):
            out = self._start_with(audio)
            self.assertIn("OK", out)
            drv_rec.rec_stop()
        self.assertEqual(len(list(self._td.glob("rec-*.wav"))), 1)
        self.assertEqual(list(self._td.glob("rec-*.opus")), [])

    def test_start_accepts_encoding_param(self):
        # 显式 encoding="wav"：即使真环境有 OPUS 也强制落 .wav
        audio = synth_pcm(400, 600, 1)
        out = self._start_with(audio, encoding="wav")
        self.assertIn("OK", out)
        drv_rec.rec_stop()
        self.assertEqual(len(list(self._td.glob("rec-*.wav"))), 1)
        self.assertEqual(list(self._td.glob("rec-*.opus")), [])

    @unittest.skipUnless(getattr(drv_rec, "_SF_OK", False),
                         "本机 libsndfile 无 OPUS 写支持，跳过真编码路径")
    def test_auto_encoding_produces_opus(self):
        # 真环境有 OPUS：默认 auto 应产 .opus 段
        audio = synth_pcm(400, 600, 1)
        out = self._start_with(audio)
        self.assertIn("OK", out)
        drv_rec.rec_stop()
        self.assertEqual(len(list(self._td.glob("rec-*.opus"))), 1)
        self.assertEqual(len(list(self._td.glob("rec-*.wav"))), 0)


class EncodingCase(unittest.TestCase):
    """encode_segment / _segment_ext —— Opus 编码与自动降级（模块级纯函数）。"""

    def _wav_bytes(self) -> bytes:
        return synth_wav(synth_pcm(100, 0, 1))

    def test_wav_passthrough(self):
        # encoding="wav" 原样透传（存储层不该动它）
        wav = self._wav_bytes()
        out, enc = drv_rec.encode_segment(wav, "wav")
        self.assertEqual(enc, "wav")
        self.assertEqual(out, wav)

    def test_segment_ext(self):
        self.assertEqual(drv_rec._segment_ext("wav"), ".wav")
        self.assertEqual(drv_rec._segment_ext("opus"), ".opus")

    def test_opus_fallback_without_soundfile(self):
        # 主测试路径：mock _SF_OK=False 模拟无 soundfile / 无 OPUS → 静默降级 wav，绝不抛错
        wav = self._wav_bytes()
        with mock.patch.object(drv_rec, "_SF_OK", False):
            out, enc = drv_rec.encode_segment(wav, "opus")
            self.assertEqual(enc, "wav")
            self.assertEqual(out, wav)
            out2, enc2 = drv_rec.encode_segment(wav, "auto")
        self.assertEqual(enc2, "wav")
        self.assertEqual(out2, wav)

    @unittest.skipUnless(getattr(drv_rec, "_SF_OK", False),
                         "本机 libsndfile 无 OPUS 写支持，跳过真编码路径")
    def test_opus_real_encode(self):
        # 真环境有 OPUS：产出非空且不同于原 WAV 的 opus 字节
        wav = self._wav_bytes()
        out, enc = drv_rec.encode_segment(wav, "opus")
        self.assertEqual(enc, "opus")
        self.assertTrue(out)
        self.assertNotEqual(out, wav)


class QuotaCase(unittest.TestCase):
    """存储配额 FIFO 淘汰（LAOS_REC_MAX_BYTES / LAOS_REC_MAX_SEGMENTS）。"""

    def setUp(self):
        self._td = Path(__file__).parent / "_rec_quota_tmp"
        self._td.mkdir(exist_ok=True)
        drv_rec.set_output_dir(self._td)
        drv_rec._reset()
        drv_rec._evicted_total = 0  # 累计淘汰数测试隔离

    def tearDown(self):
        import shutil
        shutil.rmtree(self._td, ignore_errors=True)
        drv_rec._reset()
        drv_rec.set_output_dir(None)

    def test_segment_count_quota_fifo(self):
        # 3 段 > MAX_SEGMENTS=2 → 最旧的 rec-0001 被 FIFO 淘汰，status 记 evicted
        import os
        with mock.patch.dict(os.environ, {"LAOS_REC_MAX_SEGMENTS": "2"}), \
                mock.patch.object(drv_rec, "_SF_OK", False):
            for i in range(3):
                drv_rec._save_segment(i * 1000, synth_wav(synth_pcm(100, 0, 1)))
        names = sorted(p.name for p in self._td.glob("rec-*.*"))
        self.assertEqual(len(names), 2)
        self.assertTrue(names[0].startswith("rec-0002"))
        self.assertTrue(names[1].startswith("rec-0003"))
        self.assertIn("evicted=1", drv_rec.rec_status())

    def test_bytes_quota_evicts_until_under(self):
        # 每段 ≈12.8KB（400ms PCM16LE），字节配额 4096 → 写完即淘汰直到低于阈值
        import os
        with mock.patch.dict(os.environ, {"LAOS_REC_MAX_BYTES": "4096"}), \
                mock.patch.object(drv_rec, "_SF_OK", False):
            drv_rec._save_segment(0, synth_wav(synth_pcm(400, 0, 1)))
            drv_rec._save_segment(1000, synth_wav(synth_pcm(400, 0, 1)))
        self.assertEqual(list(self._td.glob("rec-*.*")), [])
        st = drv_rec.rec_status()
        self.assertIn("evicted=2", st)
        self.assertIn("bytes=0", st)


if __name__ == "__main__":
    unittest.main(verbosity=2)
