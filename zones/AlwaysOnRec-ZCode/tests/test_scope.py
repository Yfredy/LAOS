# tests/test_scope.py
"""task_scope —— 意图驱动的路径级能力收窄（Oracle Labs, AgenticOS'26）。

    python -m unittest tests.test_scope -v
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


class TestTaskScope(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8",
               "LAOS_FS_ROOT": str(self.workdir / "branches")}
        self.kernel.load_driver("fs", [sys.executable, str(REPO / "drivers" / "drv_fs.py")],
                                env=env)
        self.kernel.load_driver("sys", [sys.executable, str(REPO / "drivers" / "drv_sys.py")],
                                env=env)
        self.main = self.kernel.branches.create_root("main")
        ws = self.main.workspace / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "hosts").write_text("127.0.0.1 localhost\n", encoding="utf-8")
        (ws / "other.txt").write_text("other\n", encoding="utf-8")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, caps, task_scope=None):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name="a", caps=caps, ctx=ctx, branch="main",
                                 task_scope=task_scope)

    def _read(self, pid, path):
        return asyncio.run(self.kernel.syscall(pid, "fs.read", {"path": path}))

    def test_within_scope_allowed(self):
        pcb = self._spawn(["fs.*"], task_scope=["/main/workspace/"])
        res = self._read(pcb.pid, "/main/workspace/hosts")
        self.assertTrue(res.ok, res.error)

    def test_outside_scope_denied(self):
        pcb = self._spawn(["fs.*"], task_scope=["/main/workspace/hosts"])
        res = self._read(pcb.pid, "/main/workspace/other.txt")
        self.assertFalse(res.ok)
        self.assertIn("outside task scope", res.error)

    def test_prefix_must_match_from_start(self):
        pcb = self._spawn(["fs.*"], task_scope=["/main/workspace/other"])
        res = self._read(pcb.pid, "/main/workspace/hosts")
        self.assertFalse(res.ok)
        self.assertIn("outside task scope", res.error)

    def test_dotdot_traversal_denied(self):
        # .. 穿越不得绕过 scope：归一化后落在 /secret.txt（scope 之外），
        # 修复前靠原始字符串 startswith("/main/workspace/") 蒙混过关，
        # jail 归一化后实际读到 main 分支外的 secret
        (self.workdir / "branches" / "secret.txt").write_text(
            "top secret\n", encoding="utf-8")
        pcb = self._spawn(["fs.*"], task_scope=["/main/workspace/"])
        res = self._read(pcb.pid, "/main/workspace/../../secret.txt")
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)
        self.assertIn("outside task scope", res.error)
        self.assertNotIn("top secret", res.text)

    def test_scope_boundary_is_separator_aware(self):
        # 前缀必须落在 '/' 边界：scope 项 /main/workspace/hosts 不得
        # 误纳 /main/workspace/hosts.txt（裸 startswith 的经典缺陷）
        (self.main.workspace / "workspace" / "hosts.txt").write_text(
            "decoy\n", encoding="utf-8")
        pcb = self._spawn(["fs.*"], task_scope=["/main/workspace/hosts"])
        res = self._read(pcb.pid, "/main/workspace/hosts.txt")
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)
        self.assertIn("outside task scope", res.error)
        self.assertNotIn("decoy", res.text)

    def test_no_scope_unrestricted(self):
        pcb = self._spawn(["fs.*"])
        res = self._read(pcb.pid, "/main/workspace/other.txt")
        self.assertTrue(res.ok, res.error)

    def test_pathless_tools_unaffected(self):
        pcb = self._spawn(["sys.*"], task_scope=["/nowhere/"])
        res = asyncio.run(self.kernel.syscall(pcb.pid, "sys.info", {}))
        self.assertTrue(res.ok, res.error)

    def test_fork_child_inherits_scope(self):
        from laos.agent import Agent
        from laos.brain import ScriptedBrain
        parent = self._spawn(["fs.*"], task_scope=["/main/workspace/hosts"])
        parent_agent = Agent(self.kernel, parent, ScriptedBrain(branch="main"))
        child = parent_agent.fork_child("child", ["fs.*"], "main",
                                        ScriptedBrain(branch="main"))
        self.assertEqual(child.pcb.task_scope, ["/main/workspace/hosts"])
        res = self._read(child.pcb.pid, "/main/workspace/other.txt")
        self.assertIn("outside task scope", res.error)


class TestTimeWindowScope(unittest.TestCase):
    """task_scope 的 time: 前缀 —— mic.* 的时间窗收窄。

    对应业界对照：Apple Siri Recap 的"按时间/地点决定何时可听"
    （docs/research/always-on-recording/2026-09-11-verticals-apple-articles.md
    §3.3 / §6 Task 2）。time: 仅约束 mic.* 前缀，其他 syscall 不受影响；
    无 time: 前缀时行为与旧版完全一致。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        # 注入假 mic.status 内建：不拉真驱动，闸门行为在内核层即可断言
        from laos.mcp import ToolSpec, CallResult
        self.kernel._builtin_specs["mic.status"] = ToolSpec(
            "mic.status", "录音状态（测试内建）",
            {"type": "object", "properties": {}}, reversible=True, risk="low")
        self.kernel._builtin_impls["mic.status"] = (
            lambda pcb, args: CallResult.ok_text("recording=false"))
        self.main = self.kernel.branches.create_root("main")
        self._ctxs = []  # 防 GC：ContextManager 生命周期跟 PCB 一致

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, task_scope):
        from laos.context import ContextManager
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        self._ctxs.append(ctx)
        return self.kernel.spawn(name="a", caps=["mic.*", "mem.*"], ctx=ctx,
                                 branch="main", task_scope=task_scope)

    def _status(self, pid):
        return asyncio.run(self.kernel.syscall(pid, "mic.status", {}))

    def test_inside_window_allowed(self):
        pcb = self._spawn(["time:09:00-18:00"])
        self.kernel._now_hhmm = lambda: "12:00"
        res = self._status(pcb.pid)
        self.assertTrue(res.ok, res.error)

    def test_outside_window_denied(self):
        pcb = self._spawn(["time:09:00-18:00"])
        self.kernel._now_hhmm = lambda: "23:30"
        res = self._status(pcb.pid)
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)
        self.assertIn("time window", res.error)

    def test_overnight_window(self):
        pcb = self._spawn(["time:22:00-06:00"])
        self.kernel._now_hhmm = lambda: "23:30"
        self.assertTrue(self._status(pcb.pid).ok)   # 跨零点：深夜在窗内
        self.kernel._now_hhmm = lambda: "12:00"
        res = self._status(pcb.pid)
        self.assertFalse(res.ok)                    # 正午在窗外
        self.assertIn("time window", res.error)

    def test_no_time_prefix_unaffected(self):
        pcb = self._spawn(["/main/workspace/"])     # 只有路径 scope
        self.kernel._now_hhmm = lambda: "23:30"
        self.assertTrue(self._status(pcb.pid).ok, "无 time: 前缀不得限 mic.*")

    def test_time_prefix_ignores_non_mic_tools(self):
        pcb = self._spawn(["time:09:00-18:00"])
        self.kernel._now_hhmm = lambda: "23:30"
        res = asyncio.run(self.kernel.syscall(pcb.pid, "mem.stats", {}))
        self.assertTrue(res.ok, res.error)          # 时间窗只约束 mic.*


if __name__ == "__main__":
    unittest.main(verbosity=2)
