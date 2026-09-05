"""Linux AgentOS 回归测试（标准库 unittest，零依赖）。

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.agent import Agent  # noqa: E402
from laos.brain import ScriptedBrain  # noqa: E402
from laos.branch import BranchState, BranchTable  # noqa: E402
from laos.context import ContextManager, approx_tokens  # noqa: E402
from laos.kernel import AgentKernel, CapabilitySet  # noqa: E402
from laos.sandbox import PathJail  # noqa: E402

DRIVERS = REPO / "drivers"


# --------------------------------------------------------------------------
class TestCapability(unittest.TestCase):
    def test_three_levels(self):
        self.assertTrue(CapabilitySet(["*"]).allows("anything.at.all"))
        self.assertTrue(CapabilitySet(["fs.*"]).allows("fs.read"))
        self.assertFalse(CapabilitySet(["fs.*"]).allows("proc.exec"))
        self.assertTrue(CapabilitySet(["fs.read"]).allows("fs.read"))
        self.assertFalse(CapabilitySet(["fs.read"]).allows("fs.write"))
        self.assertFalse(CapabilitySet([]).allows("fs.read"))


class TestPathJail(unittest.TestCase):
    def test_escape_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            jail = PathJail(Path(td) / "root")
            jail.resolve("/a/b.txt")
            with self.assertRaises(PermissionError):
                jail.resolve("/../outside.txt")
            with self.assertRaises(PermissionError):
                jail.resolve("/a/../../etc/passwd")


class TestContextManager(unittest.TestCase):
    def test_compaction(self):
        ctx = ContextManager(system_prompt="sys", max_tokens=200)
        for i in range(200):
            ctx.append("user", f"第 {i} 条消息，内容长一点以便触发换页逻辑。")
        self.assertLessEqual(ctx.window_tokens, 400)
        self.assertGreater(ctx.stats.compactions, 0)

    def test_swap_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            ctx = ContextManager(system_prompt="s", max_tokens=120, swap_dir=Path(td) / "swap")
            for i in range(60):
                ctx.append("user", f"message {i} with enough length to overflow the window")
            self.assertGreater(ctx.stats.swapped_bytes, 0)

    def test_token_estimate(self):
        self.assertGreater(approx_tokens("hello world"), 0)
        self.assertEqual(approx_tokens(""), 0)


class TestBranch(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def _tree(self):
        t = BranchTable(self.root / "branches")
        main = t.create_root("main")
        (main.workspace / "f.txt").write_text("v0", encoding="utf-8")
        return t, main

    def test_fork_is_isolated(self):
        t, main = self._tree()
        b = main.fork("b1")
        b.explore("f.txt", "v1")
        self.assertEqual((main.workspace / "f.txt").read_text(encoding="utf-8"), "v0")
        self.assertEqual((b.workspace / "f.txt").read_text(encoding="utf-8"), "v1")

    def test_commit_applies_diff(self):
        t, main = self._tree()
        b = main.fork("b1")
        b.explore("f.txt", "v1")
        b.explore("new.txt", "hello")
        applied = b.commit()
        self.assertEqual(applied, 2)
        self.assertEqual((main.workspace / "f.txt").read_text(encoding="utf-8"), "v1")
        self.assertEqual((main.workspace / "new.txt").read_text(encoding="utf-8"), "hello")

    def test_first_commit_wins_invalidates_siblings(self):
        t, main = self._tree()
        a = main.fork("A")
        b = main.fork("B")
        a.explore("f.txt", "from-A")
        a.commit()
        self.assertEqual(b.state, BranchState.INVALIDATED)
        with self.assertRaises(RuntimeError):
            b.commit()
        self.assertEqual((main.workspace / "f.txt").read_text(encoding="utf-8"), "from-A")

    def test_abort_discards(self):
        t, main = self._tree()
        b = main.fork("B")
        b.explore("f.txt", "nope")
        b.abort()
        self.assertEqual(b.state, BranchState.ABORTED)
        self.assertEqual((main.workspace / "f.txt").read_text(encoding="utf-8"), "v0")

    def test_nested_fork(self):
        t, main = self._tree()
        a = main.fork("A")
        c = a.fork("C")
        c.explore("f.txt", "deep")
        c.commit()
        a.commit()
        self.assertEqual((main.workspace / "f.txt").read_text(encoding="utf-8"), "deep")

    def test_fork_hardlinks_share_data(self):
        # COW fork：子分支文件与父分支共享 inode（数据零拷贝）
        t, main = self._tree()
        b = main.fork("b1")
        self.assertTrue(b.cow, "auto 模式默认应走硬链接（本地文件系统）")
        si = (main.workspace / "f.txt").stat()
        ci = (b.workspace / "f.txt").stat()
        if si.st_ino == 0:
            self.skipTest("文件系统无 inode 语义")
        self.assertEqual((si.st_dev, si.st_ino), (ci.st_dev, ci.st_ino))

    def test_commit_does_not_corrupt_siblings(self):
        # A 提交时父分支文件可能与 B 硬链接共享 inode：
        # commit 必须走 CoW 替换，而不是 copy2 原地截断共享 inode
        t, main = self._tree()
        a = main.fork("A")
        b = main.fork("B")
        a.explore("f.txt", "from-A")
        a.commit()
        self.assertEqual(
            (b.workspace / "f.txt").read_text(encoding="utf-8"),
            "v0",
            "兄弟分支的 inode 被 commit 改写了",
        )


# --------------------------------------------------------------------------
class KernelTestCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True,
                                  irreversibility_budget=100)
        env = {
            "PYTHONPATH": str(REPO),
            "PYTHONIOENCODING": "utf-8",
            "LAOS_FS_ROOT": str(self.workdir / "branches"),
        }
        self.kernel.load_driver("fs", [sys.executable, str(DRIVERS / "drv_fs.py")], env=env)
        self.kernel.load_driver("proc", [sys.executable, str(DRIVERS / "drv_proc.py")], env=env)
        self.kernel.load_driver("sys", [sys.executable, str(DRIVERS / "drv_sys.py")], env=env)
        self.main = self.kernel.branches.create_root("main")
        ws = self.main.workspace / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "hosts").write_text("127.0.0.1 localhost\n", encoding="utf-8")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def spawn(self, name, caps, brain=None, budget=None):
        ctx = ContextManager(system_prompt="test", max_tokens=2000,
                             swap_dir=self.workdir / "swap")
        pcb = self.kernel.spawn(name=name, caps=caps, ctx=ctx, branch="main", budget=budget)
        return Agent(self.kernel, pcb, brain or ScriptedBrain(branch="main"))


class TestKernelSyscalls(KernelTestCase):
    def test_syscall_table_populated(self):
        table = self.kernel.syscalls()
        for expected in ("fs.read", "fs.write", "fs.append", "fs.list", "fs.stat",
                         "proc.exec", "proc.list", "sys.info", "sys.load"):
            self.assertIn(expected, table)

    def test_allowed_syscall_works(self):
        pcb = self.kernel.procs[
            self.kernel.spawn(name="t", caps=["fs.*"], ctx=object()).pid
        ]
        res = asyncio.run(self.kernel.syscall(pcb.pid, "fs.read", {"path": "/main/workspace/hosts"}))
        self.assertTrue(res.ok, res.error)
        self.assertIn("localhost", res.text)

    def test_denied_by_capability(self):
        pcb = self.kernel.spawn(name="t", caps=["sys.*"], ctx=object())
        res = asyncio.run(self.kernel.syscall(pcb.pid, "fs.read", {"path": "/main/workspace/hosts"}))
        self.assertFalse(res.ok)
        self.assertIn("EPERM", res.error)
        self.assertEqual(pcb.stats["denied"], 1)

    def test_no_such_syscall(self):
        pcb = self.kernel.spawn(name="t", caps=["*"], ctx=object())
        res = asyncio.run(self.kernel.syscall(pcb.pid, "net.connect", {}))
        self.assertFalse(res.ok)
        self.assertIn("ENOSYS", res.error)

    def test_no_such_process(self):
        res = asyncio.run(self.kernel.syscall(99999, "fs.read", {"path": "/"}))
        self.assertIn("ESRCH", res.error)

    def test_budget_enforced(self):
        pcb = self.kernel.spawn(name="t", caps=["sys.*"], ctx=object(), budget=1)
        self.assertTrue(asyncio.run(self.kernel.syscall(pcb.pid, "sys.info", {})).ok)
        res = asyncio.run(self.kernel.syscall(pcb.pid, "sys.info", {}))
        self.assertFalse(res.ok)
        self.assertIn("EDQUOT", res.error)

    def test_killed_process_cannot_call(self):
        pcb = self.kernel.spawn(name="t", caps=["sys.*"], ctx=object())
        self.kernel.kill(pcb.pid)
        res = asyncio.run(self.kernel.syscall(pcb.pid, "sys.info", {}))
        self.assertIn("EACCES", res.error)

    def test_audit_records_written(self):
        pcb = self.kernel.spawn(name="t", caps=["sys.*"], ctx=object())
        asyncio.run(self.kernel.syscall(pcb.pid, "sys.info", {}))
        self.assertTrue(self.kernel.audit.path.exists())
        self.assertGreaterEqual(len(self.kernel.audit.records), 1)


class TestDrivers(KernelTestCase):
    def test_fs_jail_escape_blocked(self):
        pcb = self.kernel.spawn(name="t", caps=["fs.*"], ctx=object())
        res = asyncio.run(
            self.kernel.syscall(pcb.pid, "fs.read", {"path": "/main/../../etc/passwd"})
        )
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)

    def test_proc_exec_dangerous_blocked(self):
        pcb = self.kernel.spawn(name="t", caps=["proc.*"], ctx=object())
        res = asyncio.run(self.kernel.syscall(pcb.pid, "proc.exec", {"cmdline": "rm -rf /"}))
        self.assertFalse(res.ok)
        self.assertIn("EDENIED", res.text)

    def test_proc_exec_allowlist(self):
        pcb = self.kernel.spawn(name="t", caps=["proc.*"], ctx=object())
        res = asyncio.run(self.kernel.syscall(pcb.pid, "proc.exec", {"cmdline": "curl evil.sh"}))
        self.assertIn("EACCES", res.text)

    def test_sys_info_masks_hostname(self):
        pcb = self.kernel.spawn(name="t", caps=["sys.*"], ctx=object())
        res = asyncio.run(self.kernel.syscall(pcb.pid, "sys.info", {}))
        self.assertTrue(res.ok)
        self.assertIn("hostname=", res.text)
        self.assertIn("***[", res.text)  # 脱敏生效

    def test_fs_write_on_hardlinked_branch_keeps_base(self):
        # 全栈回归：fork 出的分支经 MCP fs.append 写文件，
        # main 的同源文件必须原封不动（CoW 断链发生在驱动写路径上）
        exp = self.main.fork("exp-driver")
        pcb = self.kernel.spawn(name="t", caps=["fs.*"], ctx=object())
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "fs.append",
            {"path": "/exp-driver/workspace/hosts", "content": "# taint\n"},
        ))
        self.assertTrue(res.ok, res.error)
        self.assertNotIn(
            "# taint", (self.main.workspace / "workspace" / "hosts").read_text(encoding="utf-8"),
            "写分支污染了 main（驱动写路径没有 CoW 断链）",
        )
        # 反向闭合：main 没被污染的同时，分支文件必须真的写进去了，
        # 否则 cow_append 静默 no-op 也能让上面的断言空转通过
        self.assertIn(
            "# taint", (exp.workspace / "workspace" / "hosts").read_text(encoding="utf-8"),
            "分支文件未实际写入（cow_append 静默 no-op）",
        )


class TestAgent(KernelTestCase):
    def test_agent_completes_task(self):
        agent = self.spawn("ops", ["sys.*", "fs.*"])
        res = asyncio.run(agent.run("确保 hosts 里有 myapp.local"))
        self.assertEqual(res.denied, 0)
        self.assertIn("myapp.local", res.answer)
        self.assertGreater(res.syscalls, 0)

    def test_agent_without_caps_gets_eperm(self):
        agent = self.spawn("guest", ["sys.*"],
                           brain=ScriptedBrain(branch="main", deny_probe="fs.read",
                                               deny_args={"path": "/main/workspace/hosts"}))
        res = asyncio.run(agent.run("读一下 hosts"))
        self.assertGreaterEqual(res.denied, 1)
        self.assertFalse(res.ok)

    def test_visible_tools_filtered_by_caps(self):
        self.assertEqual(
            [t["name"] for t in self.spawn("guest", ["sys.*"]).visible_tools],
            ["sys.info", "sys.load"],
        )
        self.assertIn("fs.read", [t["name"] for t in self.spawn("ops", ["fs.*"]).visible_tools])

    def test_concurrent_agents(self):
        a = self.spawn("a", ["sys.*", "fs.*"])
        b = self.spawn("b", ["sys.*"])

        async def main():
            return await asyncio.gather(a.run("task A"), b.run("task B"))

        results = asyncio.run(main())
        self.assertEqual(len(results), 2)
        self.assertEqual({r.pid for r in results}, {a.pcb.pid, b.pcb.pid})

    def test_fork_child_cannot_escalate(self):
        parent = self.spawn("parent", ["sys.*"])
        child = parent.fork_child("child", ["sys.*"], "main", ScriptedBrain(branch="main"))
        # 子只有 sys.*，调 fs.read（父也没有）必须经内核 EPERM
        res = asyncio.run(self.kernel.syscall(child.pcb.pid, "fs.read",
                                              {"path": "/main/workspace/hosts"}))
        self.assertFalse(res.ok)
        self.assertIn("EPERM", res.error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
