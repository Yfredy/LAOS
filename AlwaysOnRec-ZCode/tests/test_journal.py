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

    def test_title_schema_first_line_hash_title(self):
        """Apple Siri-Recap 式 schema：text 首行 = # 短标题（≤20 字，取首句）。"""
        def two_sentence_transcribe(wav, language="auto"):
            return json.dumps({
                "text": "今天下午三点和医生讨论了复查安排。他说指标比上个月好转，先维持当前药量。",
                "language": "zh", "emotions": ["NEUTRAL"],
                "source": "funasr", "latency_ms": 4.0})

        from journal import run_pipeline
        run_pipeline(self.journal_dir, self.memory,
                     transcribe=two_sentence_transcribe, gc_keep_hours=0)
        recs = [m for m in self.memory._records if m.get("kind") == "journal"]
        self.assertTrue(recs)
        first = recs[0]["text"].splitlines()[0]
        self.assertTrue(first.startswith("# "))
        title = first[2:]
        self.assertLessEqual(len(title), 20)
        self.assertTrue(title.startswith("今天下午三点和医生讨论了"))

    def test_title_schema_short_text_fallback(self):
        """无句界/短文本：标题回退为全文前 20 字，且不产生空标题。"""
        def short_transcribe(wav, language="auto"):
            return json.dumps({"text": "早上好", "language": "zh",
                               "emotions": ["HAPPY"], "source": "server",
                               "latency_ms": 3.0})

        from journal import run_pipeline
        run_pipeline(self.journal_dir, self.memory,
                     transcribe=short_transcribe, gc_keep_hours=0)
        recs = [m for m in self.memory._records if m.get("kind") == "journal"]
        first = recs[0]["text"].splitlines()[0]
        self.assertEqual(first, "# 早上好")
        # 第二行保留时间戳前缀
        self.assertRegex(recs[0]["text"].splitlines()[1], r"^\[\d{2}:\d{2}\] 早上好$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
