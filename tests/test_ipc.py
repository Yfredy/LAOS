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


if __name__ == "__main__":
    unittest.main(verbosity=2)
