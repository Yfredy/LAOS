# tests/test_stale.py
"""Stale context —— 观察簿与内核级陈旧检测（HKU, AgenticOS @ SOSP 2026）。

    python -m unittest tests.test_stale -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.context import ContextManager  # noqa: E402


class TestObservationBook(unittest.TestCase):
    def test_observe_then_invalidate(self):
        ctx = ContextManager(system_prompt="s")
        ctx.observe("/main/workspace/hosts", "digest-1")
        ctx.invalidate("/main/workspace/hosts")
        self.assertEqual(ctx.drain_notices(), ["/main/workspace/hosts"])
        self.assertEqual(ctx.drain_notices(), [])  # 一次性

    def test_invalidate_unknown_path_is_noop(self):
        ctx = ContextManager(system_prompt="s")
        ctx.invalidate("/never/observed")
        self.assertEqual(ctx.drain_notices(), [])

    def test_reobserve_heals(self):
        ctx = ContextManager(system_prompt="s")
        ctx.observe("/p", "d1")
        ctx.invalidate("/p")
        ctx.observe("/p", "d2")  # 重读即愈合
        self.assertEqual(ctx.drain_notices(), [])

    def test_notice_uses_user_role_and_prefix(self):
        ctx = ContextManager(system_prompt="s")
        msg = ctx.notice("STALE: /p")
        self.assertEqual(msg.role, "user")
        self.assertTrue(msg.content.startswith("[kernel-notice] "))
        # notice 不得替换系统提示
        self.assertEqual(ctx.messages[0]["content"], "s")

    def test_invalidate_counts_stats(self):
        ctx = ContextManager(system_prompt="s")
        ctx.observe("/p", "d")
        ctx.invalidate("/p")
        self.assertEqual(ctx.stats.stale_marks, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
