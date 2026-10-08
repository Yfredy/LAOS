# tests/test_mood.py
"""mood_report —— 听觉日志情感周报（字符图，纯 stdlib）。

    python -m unittest tests.test_mood -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "bin"))

from laos.memory import MemoryStore  # noqa: E402
from mood_report import build_report  # noqa: E402


def _seed(memory: MemoryStore, days_ago: int, emotion: str, text: str = "x") -> None:
    """插入一条 journal 记忆并把 ts 拨到指定天数前（直接改 _records 绕过 recall 衰减）。"""
    rec = memory.remember("journal", text, tags=[emotion])
    for r in memory._records:
        if r["id"] == rec["id"]:
            r["ts"] = datetime.now().timestamp() - days_ago * 86400
    memory._rewrite()


class TestMoodReport(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.memory = MemoryStore(Path(self._td.name) / "memory.jsonl")

    def tearDown(self):
        self._td.cleanup()

    def test_daily_aggregation(self):
        _seed(self.memory, 0, "HAPPY")
        _seed(self.memory, 0, "HAPPY")
        _seed(self.memory, 0, "SAD")
        _seed(self.memory, 1, "ANGRY")
        report = build_report(self.memory, days=7)
        today = datetime.now().strftime("%m-%d")
        self.assertEqual(report["days"][today]["HAPPY"], 2)
        self.assertEqual(report["days"][today]["SAD"], 1)

    def test_empty_friendly(self):
        report = build_report(self.memory, days=7)
        self.assertEqual(report["days"], {})
        self.assertIn("暂无", report["summary"])

    def test_summary_counts(self):
        _seed(self.memory, 0, "HAPPY")
        _seed(self.memory, 2, "SAD")
        report = build_report(self.memory, days=7)
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["by_emotion"]["HAPPY"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
