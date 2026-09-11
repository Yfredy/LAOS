"""上下文抢占快照（受 AIOS Context Manager 启发，作用于 Agent 上下文窗口）。

    python -m unittest tests.test_context -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.context import ContextManager  # noqa: E402


class TestContextSnapshot(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_save_restore_snapshot(self):
        ctx = ContextManager(system_prompt="s", max_tokens=4000, swap_dir=self.root / "swap")
        ctx.append("user", "msg-1")
        ctx.append("user", "msg-2")
        snap = ctx.save_snapshot()
        self.assertTrue(snap.exists())
        ctx.append("user", "msg-3")
        self.assertEqual(len(ctx._window), 3)
        ctx.load_snapshot(snap)
        self.assertEqual(len(ctx._window), 2)
        self.assertEqual(ctx._window[-1].content, "msg-2")

    def test_suspend_resume_marks_state(self):
        ctx = ContextManager(system_prompt="s", max_tokens=4000)
        ctx.append("user", "a")
        ctx.suspend()
        self.assertTrue(ctx.suspended)
        ctx.resume()
        self.assertFalse(ctx.suspended)


if __name__ == "__main__":
    unittest.main()
