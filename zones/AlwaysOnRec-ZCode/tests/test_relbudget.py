"""可靠性预算调度（Patient Bytes 启发）——失败耗尽即挂起。

    python -m unittest tests.test_relbudget -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.scheduler import AgentScheduler  # noqa: E402


class TestReliabilityBudget(unittest.TestCase):
    def test_failures_exhaust_budget_and_suspend(self):
        s = AgentScheduler()
        s.register(1, err_budget=2)
        s.note_outcome(1, False)
        self.assertNotIn(1, s._suspended)
        s.note_outcome(1, False)
        self.assertIn(1, s._suspended)
        self.assertIn("err-budget exhausted", s._suspended_reason[1])

    def test_success_does_not_consume(self):
        s = AgentScheduler()
        s.register(1, err_budget=1)
        for _ in range(10):
            s.note_outcome(1, True)
        self.assertNotIn(1, s._suspended)

    def test_no_budget_is_unlimited(self):
        s = AgentScheduler()
        s.register(1)  # err_budget 默认 None
        for _ in range(50):
            s.note_outcome(1, False)
        self.assertNotIn(1, s._suspended)

    def test_retire_cleans_err_bookkeeping(self):
        s = AgentScheduler()
        s.register(1, err_budget=2)
        s.note_outcome(1, False)
        s.retire(1)
        snap = {row["pid"]: row for row in s.snapshot()}
        self.assertNotIn(1, snap)

    def test_snapshot_shape(self):
        s = AgentScheduler()
        s.register(1, err_budget=3)
        s.note_outcome(1, False)
        row = s.snapshot()[0]
        self.assertEqual(row["pid"], 1)
        self.assertEqual(row["err_used"], 1)
        self.assertEqual(row["err_budget"], 3)
        self.assertFalse(row["suspended"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
