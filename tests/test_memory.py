# tests/test_memory.py
"""MemoryStore + mem.* 内建 syscall —— 个人记忆库（episodic memory）。

    python -m unittest tests.test_memory -v
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


# --- self_check（Task 4）---------------------------------------------------
# 模式参考 jev-chat-jarvis KbSelfCheck.kt（MIT, github.com/jev-chat/jev-chat-jarvis）：
# 自检是对"自检流程"的检查——scratch store 上写临时条目→验证各路径→
# finally 删光；①② 的检测能力靠"注入坏行确认抓得到"验证（只跑不炸不算过）。


class TestSelfCheck(unittest.TestCase):
    """MemoryStore.self_check 五检查项（scratch 路径 tempfile）。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self._td.name) / "memory.jsonl")

    def tearDown(self):
        self._td.cleanup()

    def test_self_check_passes_on_clean_scratch(self):
        """干净 scratch store：五项全过（失败清单为空）。"""
        self.assertEqual(self.store.self_check(), [])

    def test_check1_detects_unparsable_and_missing_field_lines(self):
        """① JSONL 完整性检测能力：注入截断半行与缺字段行必须被抓到——
        _load 会静默跳过坏行（内存视图看不到），唯一现形处是自检的重读扫描。"""
        self.store.remember("fact", "x")
        with self.store.path.open("a", encoding="utf-8") as fh:
            fh.write('{"id": 9, "kind": "fact", "text"\n')      # 崩溃残迹半行
            fh.write('{"id": 10, "kind": "fact", "ts": 1.0}\n')  # 缺 text
        failures = self.store.self_check()
        self.assertTrue(any("不可解析" in f for f in failures), failures)
        self.assertTrue(any("缺必含字段" in f for f in failures), failures)

    def test_check2_detects_duplicate_id(self):
        """② 重复 id 检测能力：注入与既有条目同 id 的合法行必须被抓到。"""
        rec = self.store.remember("fact", "x")
        with self.store.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": rec["id"], "kind": "fact",
                                 "text": "dup", "ts": 0.0}, ensure_ascii=False) + "\n")
        failures = self.store.self_check()
        self.assertTrue(any("id 重复" in f for f in failures), failures)

    def test_check3_paren_full_half_width_bigram_tolerance(self):
        """③ 全/半角括号：bigram 检索天然容错（"测试群(12)"与"测试群（12）"
        共享 bigram 测试/试群/12，Jaccard 3/9>0）——实测钉住该事实防回归，
        刻意不加归一化层（YAGNI）：若未来改成精确/词法匹配，全半角会静默失配。"""
        self.store.remember("fact", "测试群(12)")
        self.store.remember("fact", "测试群（12）")
        for query in ("测试群(12)", "测试群（12）"):
            got = {r["text"] for r in self.store.recall(query, k=10)}
            self.assertEqual(got, {"测试群(12)", "测试群（12）"}, f"query={query}")
        # 库里已有同款条目时自检仍全过（命中断言是超集口径 want ⊆ got）
        self.assertEqual(self.store.self_check(), [])

    def test_check3_fires_when_bigram_tolerance_regresses(self):
        """③ 不是绿泡泡：模拟"容错退化"（bigram 恒 0，如被改成精确匹配），
        self_check 必须报 ③。"""
        with mock.patch("laos.memory.bigram_jaccard", return_value=0.0):
            failures = self.store.self_check()
        self.assertTrue(any(f.startswith("③") for f in failures), failures)

    def test_check4_recall_empty_query_is_safe(self):
        """④ recall 空 query：不抛异常、零相关不捞（recency 不单独构成召回）。"""
        self.store.remember("fact", "测试群(12)")
        self.assertEqual(self.store.recall("", k=5), [])
        self.assertEqual(self.store.self_check(), [])

    def test_check5_temp_entries_forgotten_after_self_check(self):
        """⑤ 自检临时条目用后即删：内存与磁盘都复原到自检前（逐字节）。"""
        self.store.remember("fact", "既有条目")
        before = self.store.path.read_text(encoding="utf-8")
        self.assertEqual(self.store.self_check(), [])
        self.assertEqual(len(self.store._records), 1)
        self.assertNotIn("测试群", self.store.path.read_text(encoding="utf-8"))
        self.assertEqual(MemoryStore(self.store.path).stats()["total"], 1)
        # forget 走原子重写，写回格式与 _append 一致 → 文件逐字节复原
        self.assertEqual(self.store.path.read_text(encoding="utf-8"), before)


class TestLaosctlSelfcheck(unittest.TestCase):
    """laosctl selfcheck 子命令：scratch store 跑自检，不碰用户 var/memory.jsonl。"""

    def _run(self, *extra):
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        return subprocess.run(
            [sys.executable, str(REPO / "bin" / "laosctl.py"), "selfcheck", *extra],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)

    def test_selfcheck_scratch_passes_and_leaves_user_store_alone(self):
        user_store = REPO / "var" / "memory.jsonl"
        before = user_store.read_bytes() if user_store.exists() else None
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("自检通过", proc.stdout)
        after = user_store.read_bytes() if user_store.exists() else None
        self.assertEqual(after, before)

    def test_selfcheck_real_file_reports_failures_with_exit_1(self):
        """--file 显式指向坏行 store（对真实 store 跑的口子）：rc=1 并列出失败项。"""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "memory.jsonl"
            MemoryStore(p).remember("fact", "x")
            with p.open("a", encoding="utf-8") as fh:
                fh.write('{"id": 9, "text"\n')
            proc = self._run("--file", str(p))
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("不可解析", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
