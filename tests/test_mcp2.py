"""MCP 2026-07-28：Tasks + Elicitation（双向请求、任务异步）。

    python -m unittest tests.test_mcp2 -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.mcp import MCPClient  # noqa: E402

FIX_DRIVER = REPO / "tests" / "fix_mcp2_driver.py"


class _DriverCase(unittest.TestCase):
    """基类只创建 client 不 start——由子类先配好 handler 再 start。"""

    def setUp(self):
        self.client = MCPClient("fix", [sys.executable, str(FIX_DRIVER)])

    def tearDown(self):
        self.client.close()

    @staticmethod
    def _handler(accept):
        return lambda method, params: {"action": "accept" if accept else "decline",
                                       "value": ""}


class TestBidirectionalRequests(_DriverCase):
    """server→client 请求（elicitation/create）的拦截与回包。"""

    def _start_with(self, handler):
        self.client.on_server_request = handler
        self.client.start()

    def test_elicit_accept(self):
        self._start_with(self._handler(True))
        res = self.client.call_tool("elicit_gate", {"text": "rm -rf /tmp/x"})
        self.assertTrue(res.ok, res.error)
        self.assertIn("GATED: rm -rf /tmp/x", res.text)

    def test_elicit_decline_raises_edened(self):
        self._start_with(self._handler(False))
        res = self.client.call_tool("elicit_gate", {"text": "yolo"})
        self.assertFalse(res.ok)
        self.assertIn("EDENIED", res.text)

    def test_default_handler_rejects(self):
        self.client.start()  # 无 handler：client 应回 -32601，server 视为拒绝
        res = self.client.call_tool("elicit_gate", {"text": "x"})
        self.assertFalse(res.ok)
        self.assertIn("EDENIED", res.text)


class TestKernelTasksAndElicit(unittest.TestCase):
    """内核接线：syscall(task=True) 任务路径 + elicitation→confirm 路由。"""

    def setUp(self):
        import asyncio
        import tempfile

        from laos.context import ContextManager
        from laos.kernel import AgentKernel

        self.asyncio = asyncio
        self._td = tempfile.TemporaryDirectory()
        self.kernel = AgentKernel(Path(self._td.name) / "var", confirm=lambda op: True)
        self.kernel.load_driver("fix", [sys.executable, str(FIX_DRIVER)])
        # load_driver 已把 fix 驱动的全部工具注册进 syscall_table（echo/elicit_gate/slow）
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        self.pcb = self.kernel.spawn(name="a", caps=["*"], ctx=ctx)

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def test_task_true_completes(self):
        res = self.asyncio.run(self.kernel.syscall(
            self.pcb.pid, "echo", {"text": "hello"}, task=True))
        self.assertTrue(res.ok, res.error)
        self.assertIn("ECHO: hello", res.text)

    def test_elicit_routes_to_confirm(self):
        seen = []
        self.kernel.confirm = lambda op: seen.append(op) or False
        res = self.asyncio.run(self.kernel.syscall(
            self.pcb.pid, "elicit_gate", {"text": "x"}))
        self.assertFalse(res.ok)
        self.assertIn("EDENIED", res.text)  # confirm False → decline → driver 抛 EDENIED
        # confirm 收到的必须是 elicitation 语义的 op（人类在环路由生效的证据）
        self.assertEqual(
            seen, [{"tool": "elicitation", "message": "allow x?", "risk": "high"}])


class TestTasks(_DriverCase):
    """MCP Tasks：tools/call 异步执行 + tasks/get / tasks/result 轮询。"""

    def setUp(self):
        super().setUp()
        self.client.start()
        self.assertIn("tasks", self.client.capabilities)

    def test_task_lifecycle(self):
        task_id = self.client.call_tool_task("slow", {"seconds": 0.3})
        status = self.client._rpc("tasks/get", {"taskId": task_id})["result"]["task"]["status"]
        self.assertIn(status, ("working", "completed"))
        res = self.client.task_result(task_id, timeout_s=10.0)
        self.assertTrue(res.ok, res.error)
        self.assertIn("SLOW-OK", res.text)

    def test_task_result_unknown(self):
        res = self.client.task_result("t-nope", timeout_s=1.0)
        self.assertFalse(res.ok)
        self.assertIn("ENOENT", res.error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
