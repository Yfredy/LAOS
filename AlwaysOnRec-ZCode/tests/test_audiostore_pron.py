# tests/test_audiostore_pron.py
"""laos/audiostore（编解码留存档，默认关）+ laos/pronunciation（韵律评分）+ ear.assess。

    python -m unittest tests.test_audiostore_pron -v
"""
from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))
sys.path.insert(0, str(REPO / "bin"))

SR = 8000


def tone_wav(ms: int = 500, amp: float = 0.5) -> bytes:
    """合成 PCM16 WAV 字节（440Hz 正弦）。"""
    import io
    import struct
    import wave
    samples = [int(amp * 26000 * math.sin(2 * math.pi * 440 * i / SR))
               for i in range(SR * ms // 1000)]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return buf.getvalue()


class TestAudioStore(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self.wav = tone_wav()

    def tearDown(self):
        self._td.cleanup()

    def test_ulaw_roundtrip_and_compression(self):
        from laos.audiostore import AudioStore
        store = AudioStore(self.root / "archive", codec="ulaw")
        path = store.store("rec-0001.wav", self.wav)
        self.assertTrue(path.exists())
        self.assertEqual(path.suffix, ".ulaw")
        # µ-law 每样本 8bit vs PCM16 16bit：压缩率 ~0.5
        ratio = path.stat().st_size / len(self.wav)
        self.assertLess(ratio, 0.6)
        self.assertGreater(ratio, 0.3)
        back = store.load(path)
        self.assertEqual(len(back), len(self.wav))  # 重建后样本数一致
        self.assertEqual(store.stats()["files"], 1)

    def test_wav_passthrough(self):
        from laos.audiostore import AudioStore
        store = AudioStore(self.root / "archive", codec="wav")
        path = store.store("rec-0002.wav", self.wav)
        self.assertEqual(path.stat().st_size, len(self.wav))

    def test_unknown_codec_rejected(self):
        from laos.audiostore import AudioStore
        with self.assertRaises(ValueError):
            AudioStore(self.root / "archive", codec="mp3")

    def test_journal_archive_wired_before_gc(self):
        """journal 管线：archive 传入时，转写成功的段在即焚前先进留存档。"""
        import json
        import drv_ear
        from journal import run_pipeline
        from laos.audiostore import AudioStore
        jdir = self.root / "journal"
        jdir.mkdir()
        (jdir / "rec-0001.wav").write_bytes(tone_wav(300))

        drv_ear.transcribe = lambda w, language="auto": json.dumps(
            {"text": "测试转写", "emotions": ["NEUTRAL"], "source": "server"})
        store = AudioStore(self.root / "archive", codec="ulaw")
        run_pipeline(jdir, _FakeMemory(), transcribe=drv_ear.transcribe,
                     gc_keep_hours=0, archive=store)
        # 原音频即焚，留存档有压缩副本（默认关：不传 archive 则无副本）
        self.assertEqual(len(list(jdir.glob("*.wav"))), 0)
        self.assertEqual(store.stats()["files"], 1)


class _FakeMemory:
    def remember(self, **kw):
        return 0

    def stats(self):
        return {"by_kind": {}}


class TestPronunciation(unittest.TestCase):
    def test_prosodic_features_shape(self):
        from laos.pronunciation import prosodic_features
        # 两段语音 + 中间 500ms 停顿（两端 pad 各吃 100ms，实测仍有 300ms）
        feats = prosodic_features(_tone_samples(400) + [0] * (SR // 2) + _tone_samples(400), SR)
        self.assertIn("duration_s", feats)
        self.assertIn("speech_ratio", feats)
        self.assertIn("pauses", feats)
        self.assertIn("syllables_per_sec", feats)
        self.assertEqual(feats["pauses"], 1)
        self.assertGreater(feats["speech_ratio"], 0.5)

    def test_assess_zero_dep_covers_prosody_only(self):
        from laos.pronunciation import assess
        result = assess(_tone_samples(500), SR)
        self.assertIsInstance(result["fluency"], int)
        self.assertIsNone(result["accuracy"])       # 音素准确度需 GOPT 后端
        self.assertEqual(result["backend"], "none")

    def test_assess_with_backend(self):
        from laos.pronunciation import assess
        fake = lambda samples, sr, text: {"accuracy": 88, "completeness": 90}
        result = assess(_tone_samples(500), SR, expected_text="hello", backend=fake)
        self.assertEqual(result["accuracy"], 88)
        self.assertEqual(result["backend"], "custom")

    def test_ear_assess_tool(self):
        import drv_ear
        wav_path = self._td.name + "/a.wav"
        Path(wav_path).write_bytes(tone_wav(400))
        raw = drv_ear.ear_assess(wav_path)
        import json
        data = json.loads(raw)
        self.assertIn("fluency", data)

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._td.cleanup()


def _tone_samples(ms: int, amp: float = 0.5) -> list[int]:
    return [int(amp * 26000 * math.sin(2 * math.pi * 440 * i / SR))
            for i in range(SR * ms // 1000)]


if __name__ == "__main__":
    unittest.main(verbosity=2)
