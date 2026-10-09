"""rhythm —— 时域节律档案（journal 记忆 → 小时画像，纯派生）。

    python -m unittest tests.test_rhythm -v
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.rhythm import busiest, dominant_emotion, hour_profile, render  # noqa: E402


def _journal_rec(ts: float, emotion: str) -> dict:
    return {"id": 1, "ts": ts, "kind": "journal", "text": "x",
            "tags": [emotion], "origin": "journal"}


def _at_today(hour: int, minute: int = 0) -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday,
                        hour, minute, 0, 0, 0, -1))


class TestRhythm(unittest.TestCase):
    def test_groups_by_local_hour(self):
        p = hour_profile([_journal_rec(_at_today(9), "NEUTRAL"),
                          _journal_rec(_at_today(9, 30), "HAPPY"),
                          _journal_rec(_at_today(14), "ANGRY")])
        self.assertEqual(p["09"]["segments"], 2)
        self.assertEqual(p["14"]["segments"], 1)

    def test_emotion_falls_back_to_neutral(self):
        p = hour_profile([{"ts": _at_today(8), "tags": ["chat"]}])
        self.assertEqual(p["08"]["emotions"], {"NEUTRAL": 1})

    def test_busiest_and_dominant(self):
        recs = ([_journal_rec(_at_today(9), "NEUTRAL")]
                + [_journal_rec(_at_today(14), f) for f in ("HAPPY", "SAD")])
        p = hour_profile(recs)
        self.assertEqual(busiest(p), "14")
        self.assertEqual(dominant_emotion(p), "NEUTRAL")  # 三情绪并列 1 票，Counter 取首遇（插入序）

    def test_empty_profile(self):
        self.assertEqual(hour_profile([]), {})
        self.assertIsNone(busiest({}))
        self.assertIsNone(dominant_emotion({}))
        self.assertEqual(render({}), "")

    def test_render_sorted_compact(self):
        p = hour_profile([_journal_rec(_at_today(14), "HAPPY"),
                          _journal_rec(_at_today(9), "NEUTRAL")])
        line = render(p)
        self.assertIn("09时 1段(NEUTRAL:1)", line)
        self.assertIn("14时 1段(HAPPY:1)", line)
        self.assertLess(line.index("09时"), line.index("14时"))


if __name__ == "__main__":
    unittest.main()
