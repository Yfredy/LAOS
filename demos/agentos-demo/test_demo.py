# demos/agentos-demo/test_demo.py —— Linux AgentOS demo 测试（WSL 侧运行）
# 运行：wsl -- python3 demos/agentos-demo/test_demo.py
# 零依赖；不 import laos（demo 自包含）。
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class McpFsTest(unittest.TestCase):
    """MCP 文件服务 = 设备驱动：stdio 上的 JSON-RPC 2.0。"""

    def _server(self, jail: Path):
        env = dict(os.environ, DEMO_JAIL=str(jail))
        return subprocess.Popen(
            [sys.executable, str(HERE / "mcp_fs.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env, text=True, encoding="utf-8")

    def _rpc(self, proc, obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())

    def test_handshake_tools_list_and_call(self):
        with tempfile.TemporaryDirectory() as td:
            jail = Path(td)
            (jail / "a.txt").write_text("hello", encoding="utf-8")
            p = self._server(jail)
            try:
                init = self._rpc(p, {"jsonrpc": "2.0", "id": 1,
                                      "method": "initialize",
                                      "params": {}})
                self.assertIn("result", init)
                tools = self._rpc(p, {"jsonrpc": "2.0", "id": 2,
                                      "method": "tools/list"})
                names = {t["name"] for t in tools["result"]["tools"]}
                self.assertEqual(names, {"fs.read", "fs.write", "time.now"})
                r = self._rpc(p, {"jsonrpc": "2.0", "id": 3,
                                  "method": "tools/call",
                                  "params": {"name": "fs.read",
                                             "arguments": {"path": "a.txt"}}})
                self.assertEqual(r["result"]["content"][0]["text"], "hello")
            finally:
                p.stdin.close()
                p.wait(timeout=5)

    def test_jail_escape_denied(self):
        with tempfile.TemporaryDirectory() as td:
            jail = Path(td) / "jail"
            jail.mkdir()
            secret = Path(td) / "secret.txt"
            secret.write_text("nope", encoding="utf-8")
            p = self._server(jail)
            try:
                r = self._rpc(p, {"jsonrpc": "2.0", "id": 1,
                                  "method": "tools/call",
                                  "params": {"name": "fs.read",
                                             "arguments": {"path": "../secret.txt"}}})
                self.assertTrue(r.get("error") or
                                r["result"].get("isError"))
            finally:
                p.stdin.close()
                p.wait(timeout=5)


from kernel import DemoKernel   # noqa: E402  (demo 目录自包含，同目录 import)


class _ScriptServer:
    """测试用假 MCP server：一条预先编排的应答。"""

    def __init__(self, reply: dict):
        self._reply = reply

    def call(self, name: str, args: dict) -> dict:
        return self._reply


class KernelAgentTest(unittest.TestCase):
    def _boot(self, caps, script):
        k = DemoKernel()
        k.mcp = _ScriptServer({"content": [{"type": "text", "text": "DATA"}]})
        aid = f"agent-{abs(hash(str(script))) % 1000}"
        k.write_script(aid, script)
        pid = k.spawn(aid, caps)
        k.syscall_loop(timeout=10)
        return k, pid

    def test_agent_is_real_process_and_gates(self):
        # agent 有能力表：fs.read 放行、fs.write 拒 EPERM
        k, pid = self._boot(["fs.read"], [
            {"op": "fs.read", "args": {"path": "a.txt"}},
            {"op": "fs.write", "args": {"path": "b.txt", "data": "x"}},
        ])
        self.assertGreater(pid, 0)
        rows = k.audit_rows()
        ops = [(r["op"], r["ok"]) for r in rows]
        self.assertEqual(ops, [("fs.read", True), ("fs.write", False)])
        self.assertIn("EPERM", rows[1]["result"])

    def test_agent_exit_code_is_real(self):
        k, pid = self._boot(["fs.read"], [{"op": "fs.read", "args": {"path": "a"}}])
        self.assertEqual(k.agent_exit(pid), 0)

    def test_signal_kill(self):
        k = DemoKernel()
        aid = "sleeper"
        k.write_script(aid, [{"op": "sleep", "args": {"sec": 60}}])
        pid = k.spawn(aid, [])
        import signal
        import time as _t
        _t.sleep(0.5)
        k.kill(pid, signal.SIGTERM)            # 内核对真进程发真信号
        k.syscall_loop(timeout=5)
        self.assertLess(k.agent_exit(pid), 0)  # 负值=被信号杀死（Linux 语义）


if __name__ == "__main__":
    unittest.main()
