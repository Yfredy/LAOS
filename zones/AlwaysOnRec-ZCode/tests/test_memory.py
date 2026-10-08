# tests/test_memory.py
"""MemoryStore + mem.* 内建 syscall —— 个人记忆库（episodic memory）。

    python -m unittest tests.test_memory -v
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.context import ContextManager  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402
from laos.memory import MemoryStore, bigram_jaccard  # noqa: E402


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self._td.name) / "memory.jsonl")

    def tearDown(self):
        self._td.cleanup()

    def test_bigram_jaccard_basics(self):
        self.assertEqual(bigram_jaccard("", "abc"), 0.0)
        self.assertEqual(bigram_jaccard("abc", "abc"), 1.0)
        self.assertGreater(bigram_jaccard("编程语言", "编程语言是Python"), 0.0)

    def test_remember_recall_chinese(self):
        self.store.remember("fact", "我喜欢的编程语言是 Python", tags=["编程"])
        self.store.remember("episodic", "今天下午开了产品评审会", tags=["会议"])
        got = self.store.recall("编程语言", k=1)
        self.assertEqual(len(got), 1)
        self.assertIn("Python", got[0]["text"])
        self.assertGreater(got[0]["score"], 0.0)
        self.assertEqual(self.store.recall("完全不相关的查询词组", k=3), [])

    def test_forget(self):
        rec = self.store.remember("fact", "x")
        self.assertTrue(self.store.forget(rec["id"]))
        self.assertFalse(self.store.forget(rec["id"]))
        self.assertEqual(self.store.recall("x", k=5), [])

    def test_forget_rewrite_atomic_no_tmp_residue(self):
        """forget 全量重写走 temp + os.replace（同 cow.py）：重写后文件仍是
        合法 JSONL（每行可解析），且目录无 .tmp 残留——崩溃最坏留残迹，
        不会像"先 truncate 再写"那样毁掉整个库。"""
        self.store.remember("fact", "第一条")
        rec = self.store.remember("diary", "第二条")
        self.assertTrue(self.store.forget(rec["id"]))
        lines = self.store.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["text"], "第一条")
        self.assertEqual(
            [p.name for p in self.store.path.parent.iterdir()],
            [self.store.path.name], "残留 .tmp 文件")

    def test_stats_and_persistence(self):
        self.store.remember("fact", "a")
        self.store.remember("diary", "b")
        st = self.store.stats()
        self.assertEqual(st["total"], 2)
        self.assertEqual(st["by_kind"], {"fact": 1, "diary": 1})
        # 持久化：新实例读同一文件
        store2 = MemoryStore(self.store.path)
        self.assertEqual(store2.stats()["total"], 2)


class TestMemSyscalls(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.kernel = AgentKernel(Path(self._td.name) / "var", confirm=lambda op: True)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, caps):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name="a", caps=caps, ctx=ctx, branch="main")

    def test_remember_recall_roundtrip(self):
        pcb = self._spawn(["mem.*"])
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.remember", {"kind": "fact", "text": "用户偏好中文回复"}))
        self.assertTrue(res.ok, res.error)
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.recall", {"query": "偏好", "k": 3}))
        self.assertTrue(res.ok)
        self.assertIn("#", res.text)
        self.assertIn("用户偏好中文回复", res.text)

    def test_forget_enostr(self):
        pcb = self._spawn(["mem.*"])
        res = asyncio.run(self.kernel.syscall(pcb.pid, "mem.forget", {"id": 999}))
        self.assertFalse(res.ok)
        self.assertIn("ENOSTR", res.error)

    def test_mem_denied_without_caps(self):
        pcb = self._spawn(["sys.*"])
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.remember", {"kind": "fact", "text": "x"}))
        self.assertIn("EPERM", res.error)

    def test_mem_audited_as_builtin(self):
        pcb = self._spawn(["mem.*"])
        asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.remember", {"kind": "fact", "text": "x"}))
        events = [r for r in self.kernel.audit.records
                  if r.get("event") == "syscall" and r.get("builtin")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["tool"], "mem.remember")


if __name__ == "__main__":
    unittest.main(verbosity=2)
