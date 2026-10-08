"""跨 agent 能力委派（capability，可委派不可提升）。

对比 AIOS Access Manager 的"同组即可见"特权组模型：laos 用 capability 子集委派，
父只能委派自己拥有的能力，子不可提升。

    python -m unittest tests.test_capability -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.kernel import CapabilitySet  # noqa: E402


class TestCapabilityDelegate(unittest.TestCase):
    def test_delegate_subset_ok(self):
        parent = CapabilitySet(["fs.*", "sys.*"])
        child = parent.delegate(["sys.*"])
        self.assertTrue(child.allows("sys.info"))
        self.assertFalse(child.allows("fs.read"))

    def test_delegate_cannot_escalate(self):
        parent = CapabilitySet(["sys.*"])
        with self.assertRaises(ValueError):
            parent.delegate(["fs.*", "proc.*"])  # 父没有，不可委派


if __name__ == "__main__":
    unittest.main()
