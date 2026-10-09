# tests/test_journal.py
"""journal 管线 —— 分段批量转写入记忆 + 即焚（mock ear 通道）。

    python -m unittest tests.test_journal -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))
sys.path.insert(0, str(REPO / "bin"))


def _make_wav(path: Path, ms: int = 300, sr: int = 16000) -> None:
    import math
    import wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        frames = bytearray()
        for i in range(sr * ms // 1000):
            frames += int(0.5 * 26000 * math.sin(2 * math.pi * 440 * i / sr)) \
                .to_bytes(2, "little", signed=True)
        w.writeframes(bytes(frames))


class TestJournalPipeline(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self.journal_dir = self.root / "journal"
        self.journal_dir.mkdir()
        # 3 段：2 份有效 wav + 1 份坏 wav（驱动报错继续）
        _make_wav(self.journal_dir / "rec-0001-1.wav", ms=400)
        _make_wav(self.journal_dir / "rec-0002-2.wav", ms=500)
        (self.journal_dir / "rec-0003-3.wav").write_bytes(b"not a wav")

        from laos.memory import MemoryStore
        self.memory = MemoryStore(self.root / "memory.jsonl")

        # mock ear.transcribe：有效 wav → 文本+情感；坏 wav → 抛错
        import drv_ear
        calls = []

        def fake_transcribe(wav, language="auto"):
            calls.append(wav)
            if "0003" in wav:
                raise IOError("EIO: bad wav")
            return json.dumps({"text": f"转录内容-{Path(wav).stem[-5:]}",
                               "language": "zh", "emotions": ["HAPPY"],
                               "source": "funasr", "latency_ms": 5.0})

        drv_ear.transcribe = fake_transcribe
        self.calls = calls
        self._transcribe = drv_ear.transcribe

    def tearDown(self):
        self._td.cleanup()

    def test_journal_items_two_ok_one_error(self):
        import drv_ear
        from journal import run_pipeline
        result = run_pipeline(self.journal_dir, self.memory,
                              transcribe=drv_ear.transcribe, gc_keep_hours=0)
        self.assertEqual(len(result["ok"]), 2)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(self.memory.stats()["by_kind"].get("journal"), 2)
        # 情感标签入 tags
        kinds = [m for m in self.memory.recall("转录", k=5)]
        self.assertTrue(any("HAPPY" in m.get("tags", []) for m in kinds))

    def test_gc_removes_transcribed_wavs(self):
        import drv_ear
        from journal import run_pipeline
        result = run_pipeline(self.journal_dir, self.memory,
                              transcribe=drv_ear.transcribe, gc_keep_hours=0)
        # keep=0：转写后全部即焚（含坏段）
        self.assertEqual(len(list(self.journal_dir.glob("*.wav"))), 0)

    def test_empty_dir_friendly(self):
        from journal import run_pipeline
        empty = self.root / "empty"
        empty.mkdir()
        result = run_pipeline(empty, self.memory)
        self.assertEqual(result["ok"], [])
        self.assertEqual(result["errors"], [])

    def test_soundscape_memories_per_hour(self):
        import os
        # 两段分属不同小时（mtime 相差 1h）：小时聚合键不同 → 两条声景记忆
        os.utime(self.journal_dir / "rec-0001-1.wav",
                 (1759957200.0, 1759957200.0))
        os.utime(self.journal_dir / "rec-0002-2.wav",
                 (1759960800.0, 1759960800.0))
        from journal import run_pipeline
        result = run_pipeline(self.journal_dir, self.memory,
                              transcribe=self._transcribe,
                              gc_keep_hours=None)
        self.assertEqual(len(result["soundscape_hours"]), 2)
        sc = [m for m in self.memory.recall("LUFS", k=10)
              if m.get("kind") == "soundscape"]
        self.assertGreaterEqual(len(sc), 2)
        self.assertTrue(all("LUFS" in m["text"] for m in sc))
        # 既有 journal 记忆不受影响
        self.assertEqual(self.memory.stats()["by_kind"].get("journal"), 2)

    def test_spectral_false_opts_out(self):
        from journal import run_pipeline
        result = run_pipeline(self.journal_dir, self.memory,
                              transcribe=self._transcribe,
                              spectral=False, gc_keep_hours=None)
        self.assertEqual(result["soundscape_hours"], [])
        self.assertIsNone(self.memory.stats()["by_kind"].get("soundscape"))

    def test_features_survive_gc_zero(self):
        from journal import run_pipeline
        result = run_pipeline(self.journal_dir, self.memory,
                              transcribe=self._transcribe, gc_keep_hours=0)
        # 音频全焚后声景记忆仍在（特征先于 GC 提取）
        self.assertEqual(len(list(self.journal_dir.glob("*.wav"))), 0)
        self.assertEqual(len(result["soundscape_hours"]), 1)

    def test_default_transcribe_resolution_uses_ear_transcribe(self):
        # 回归钉：默认转写解析必须指向真实导出名 ear_transcribe
        #（预存 bug：曾引用不存在的 drv_ear.transcribe，CLI 裸跑 AttributeError；
        #  测试里因 setUp 打了同名 mock 而长期漏网）
        import drv_ear
        real = drv_ear.ear_transcribe
        drv_ear.ear_transcribe = self._transcribe
        setUp_fake = drv_ear.transcribe      # setUp 的旧 mock 名：先摘除，
        del drv_ear.transcribe               # 还原"真实模块无 transcribe"面
        try:
            from journal import run_pipeline
            result = run_pipeline(self.journal_dir, self.memory,
                                  gc_keep_hours=None)  # 不传 transcribe：走默认解析
            self.assertEqual(len(result["ok"]), 2)
            self.assertEqual(len(result["soundscape_hours"]), 1)
        finally:
            drv_ear.ear_transcribe = real
            drv_ear.transcribe = setUp_fake


if __name__ == "__main__":
    unittest.main(verbosity=2)
