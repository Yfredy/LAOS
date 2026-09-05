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


if __name__ == "__main__":
    unittest.main(verbosity=2)
