# tests/test_cow.py
"""CoW 原语测试（全平台可跑：hardlink/os.replace 在 Windows/POSIX 都成立）。

    python -m unittest tests.test_cow -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.cow import cow_append, cow_write, is_shared  # noqa: E402


class TestCow(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def _hardlinked_pair(self) -> tuple[Path, Path]:
        base = self.root / "f.txt"
        base.write_text("v0", encoding="utf-8")
        child = self.root / "child" / "f.txt"
        child.parent.mkdir(exist_ok=True)
        os.link(base, child)
        return base, child

    def test_is_shared_detects_hardlink(self):
        base, child = self._hardlinked_pair()
        self.assertTrue(is_shared(base))
        self.assertTrue(is_shared(child))

    def test_write_breaks_link_and_keeps_base(self):
        base, child = self._hardlinked_pair()
        cow_write(child, "v1", "utf-8")
        self.assertEqual(base.read_text(encoding="utf-8"), "v0")
        self.assertEqual(child.read_text(encoding="utf-8"), "v1")
        self.assertFalse(is_shared(base))

    def test_append_breaks_link_and_keeps_base(self):
        base, child = self._hardlinked_pair()
        cow_append(child, "-tail", "utf-8")
        self.assertEqual(base.read_text(encoding="utf-8"), "v0")
        self.assertEqual(child.read_text(encoding="utf-8"), "v0-tail")

    def test_append_creates_missing_file(self):
        p = self.root / "new.txt"
        cow_append(p, "hello", "utf-8")
        self.assertEqual(p.read_text(encoding="utf-8"), "hello")

    def test_write_accepts_bytes_and_leaves_no_tmp(self):
        p = self.root / "bin.dat"
        cow_write(p, b"\x00\x01")
        self.assertEqual(p.read_bytes(), b"\x00\x01")
        self.assertEqual(
            [q.name for q in self.root.iterdir()], ["bin.dat"], "残留 .tmp 文件"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
