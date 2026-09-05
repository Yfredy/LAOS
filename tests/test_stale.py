# tests/test_stale.py
"""Stale context —— 观察簿与内核级陈旧检测（HKU, AgenticOS @ SOSP 2026）。

    python -m unittest tests.test_stale -v
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.context import ContextManager  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402


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


class TestKernelStaleWiring(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {
            "PYTHONPATH": str(REPO),
            "PYTHONIOENCODING": "utf-8",
            "LAOS_FS_ROOT": str(self.workdir / "branches"),
        }
        self.kernel.load_driver("fs", [sys.executable, str(REPO / "drivers" / "drv_fs.py")], env=env)
        self.kernel.load_driver("sys", [sys.executable, str(REPO / "drivers" / "drv_sys.py")], env=env)
        self.main = self.kernel.branches.create_root("main")
        (self.main.workspace / "workspace").mkdir(parents=True, exist_ok=True)
        (self.main.workspace / "workspace" / "hosts").write_text(
            "127.0.0.1 localhost\n", encoding="utf-8")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, name, caps):
        from laos.context import ContextManager
        ctx = ContextManager(system_prompt="t", max_tokens=2000,
                             swap_dir=self.workdir / "swap")
        return self.kernel.spawn(name=name, caps=caps, ctx=ctx, branch="main")

    def test_read_records_observation(self):
        pcb = self._spawn("reader", ["fs.*"])
        res = asyncio.run(self.kernel.syscall(pcb.pid, "fs.read",
                                              {"path": "/main/workspace/hosts"}))
        self.assertTrue(res.ok)
        self.assertIn("/main/workspace/hosts", pcb.ctx._observations)

    def test_writer_invalidates_other_readers_only(self):
        reader = self._spawn("reader", ["fs.*"])
        writer = self._spawn("writer", ["fs.*"])
        asyncio.run(self.kernel.syscall(reader.pid, "fs.read",
                                        {"path": "/main/workspace/hosts"}))
        asyncio.run(self.kernel.syscall(writer.pid, "fs.read",
                                        {"path": "/main/workspace/hosts"}))
        res = asyncio.run(self.kernel.syscall(writer.pid, "fs.append",
                                              {"path": "/main/workspace/hosts",
                                               "content": "# changed\n"}))
        self.assertTrue(res.ok)
        # 写者豁免（对刚写的内容知情），读者被标陈旧
        self.assertNotIn("/main/workspace/hosts", writer.ctx._stale)
        self.assertIn("/main/workspace/hosts", reader.ctx._stale)

    def test_object_stub_ctx_never_crashes(self):
        pcb = self.kernel.spawn(name="stub", caps=["fs.*"], ctx=object())
        res = asyncio.run(self.kernel.syscall(pcb.pid, "fs.read",
                                              {"path": "/main/workspace/hosts"}))
        self.assertTrue(res.ok)  # ctx 无 observe 方法时静默跳过


if __name__ == "__main__":
    unittest.main(verbosity=2)
