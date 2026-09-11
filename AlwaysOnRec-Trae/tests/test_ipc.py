# tests/test_ipc.py
"""内核 IPC —— msg.* 内建 syscall + 运行时能力委托。

    python -m unittest tests.test_ipc -v
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


class IPCBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.kernel = AgentKernel(Path(self._td.name) / "var", confirm=lambda op: True)

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, name, caps):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name=name, caps=caps, ctx=ctx)

    def _call(self, pid, tool, args):
        return asyncio.run(self.kernel.syscall(pid, tool, args))


class TestMsg(IPCBase):
    def setUp(self):
        super().setUp()
        self.a = self._spawn("a", ["msg.*"])
        self.b = self._spawn("b", ["msg.*"])

    def test_send_recv_roundtrip(self):
        res = self._call(self.a.pid, "msg.send",
                         {"to_pid": self.b.pid, "text": "hello"})
        self.assertTrue(res.ok, res.error)
        res = self._call(self.b.pid, "msg.recv", {})
        self.assertTrue(res.ok)
        self.assertIn(f"from={self.a.pid}", res.text)
        self.assertIn("hello", res.text)
        res = self._call(self.b.pid, "msg.recv", {})
        self.assertIn("(empty)", res.text)

    def test_send_to_unknown_pid_esrch(self):
        res = self._call(self.a.pid, "msg.send", {"to_pid": 424242, "text": "x"})
        self.assertFalse(res.ok)
        self.assertIn("ESRCH", res.error)

    def test_caps_denial(self):
        c = self._spawn("c", ["sys.*"])  # 无 msg 能力
        res = self._call(c.pid, "msg.send", {"to_pid": self.a.pid, "text": "x"})
        self.assertIn("EPERM", res.error)

    def test_builtin_audited(self):
        self._call(self.a.pid, "msg.send", {"to_pid": self.b.pid, "text": "x"})
        events = [r for r in self.kernel.audit.records
                  if r.get("event") == "syscall" and r.get("builtin")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["tool"], "msg.send")

    def test_visible_tools_surface_builtins(self):
        from laos.agent import Agent
        from laos.brain import ScriptedBrain
        agent = Agent(self.kernel, self.a, ScriptedBrain(branch="main"))
        names = [t["name"] for t in agent.visible_tools]
        self.assertIn("msg.send", names)
        self.assertIn("msg.recv", names)


class TestMailboxQuotas(IPCBase):
    def setUp(self):
        super().setUp()
        self.a = self._spawn("a", ["msg.*"])
        self.b = self._spawn("b", ["msg.*"])

    def test_mailbox_overflow_enobufs(self):
        for i in range(16):
            res = self._call(self.a.pid, "msg.send",
                             {"to_pid": self.b.pid, "text": f"m{i}"})
            self.assertTrue(res.ok, res.error)
        res = self._call(self.a.pid, "msg.send", {"to_pid": self.b.pid, "text": "x"})
        self.assertIn("ENOBUFS", res.error)

    def test_oversized_message_emsgsize(self):
        res = self._call(self.a.pid, "msg.send",
                         {"to_pid": self.b.pid, "text": "x" * 4097})
        self.assertIn("EMSGSIZE", res.error)

    def test_msg_list(self):
        self._call(self.a.pid, "msg.send", {"to_pid": self.b.pid, "text": "x"})
        res = self._call(self.a.pid, "msg.list", {})
        self.assertIn(f"pid={self.b.pid}: 1 pending", res.text)


class TestDelegation(IPCBase):
    def setUp(self):
        super().setUp()
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8",
               "LAOS_FS_ROOT": str(Path(self._td.name) / "var" / "branches")}
        self.kernel.load_driver("fs", [sys.executable, str(REPO / "drivers" / "drv_fs.py")],
                                env=env)
        self.kernel.load_driver("sys", [sys.executable, str(REPO / "drivers" / "drv_sys.py")],
                                env=env)
        self.main = self.kernel.branches.create_root("main")
        (self.main.workspace / "workspace").mkdir(parents=True, exist_ok=True)
        (self.main.workspace / "workspace" / "hosts").write_text(
            "127.0.0.1 localhost\n", encoding="utf-8")
        self.ops = self._spawn("ops", ["fs.*", "sys.*", "msg.*"])
        self.guest = self._spawn("guest", ["sys.*", "msg.*"])

    def test_delegation_grants_and_expires(self):
        res = self._call(self.ops.pid, "sys.delegate",
                         {"to_pid": self.guest.pid,
                          "caps_subset": ["fs.read"], "ttl_calls": 2})
        self.assertTrue(res.ok, res.error)
        # guest 原本无 fs.read —— 委托后可用
        for _ in range(2):
            res = self._call(self.guest.pid, "fs.read",
                             {"path": "/main/workspace/hosts"})
            self.assertTrue(res.ok, res.error)
        # TTL 耗尽
        res = self._call(self.guest.pid, "fs.read",
                         {"path": "/main/workspace/hosts"})
        self.assertIn("EPERM", res.error)

    def test_delegation_cannot_elevate(self):
        res = self._call(self.guest.pid, "sys.delegate",
                         {"to_pid": self.ops.pid, "caps_subset": ["fs.*"],
                          "ttl_calls": 2})
        self.assertIn("EPERM", res.error)  # guest 自己没有 fs.*，不可授人

    def test_delegator_death_revokes(self):
        self._call(self.ops.pid, "sys.delegate",
                   {"to_pid": self.guest.pid, "caps_subset": ["fs.read"],
                    "ttl_calls": 5})
        self.kernel.kill(self.ops.pid)
        res = self._call(self.guest.pid, "fs.read",
                         {"path": "/main/workspace/hosts"})
        self.assertIn("EPERM", res.error)

    def test_delegate_unknown_target(self):
        res = self._call(self.ops.pid, "sys.delegate",
                         {"to_pid": 424242, "caps_subset": ["fs.read"],
                          "ttl_calls": 2})
        self.assertIn("ESRCH", res.error)

    def test_delegated_call_denied_by_validation_still_burns_ttl(self):
        # 语义钉子（attempt-based，与风险预算同价）：能力门先于参数校验，
        # 委托额度在能力检查放行那一刻即扣减 —— 校验拒绝同样计入 TTL。
        self._call(self.ops.pid, "sys.delegate",
                   {"to_pid": self.guest.pid, "caps_subset": ["fs.read"],
                    "ttl_calls": 1})
        res = self._call(self.guest.pid, "fs.read", {})  # 缺 path -> EINVAL
        self.assertFalse(res.ok)
        self.assertIn("EINVAL", res.error)
        # TTL 已扣为 0，补全参数也救不回来
        res = self._call(self.guest.pid, "fs.read",
                         {"path": "/main/workspace/hosts"})
        self.assertIn("EPERM", res.error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
