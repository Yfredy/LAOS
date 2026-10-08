#!/usr/bin/env python3
"""kernel —— Linux AgentOS demo 的"内核"：监督者角色。

对应表：能力表 = syscall 表的权限位（per-agent allow-list）；审计 = 内核
日志（audit.jsonl，一行一事件）；MCP server = 驱动（syscall 经 _dispatch
代理到驱动）；agent = 进程（真 pid/信号/退出码——本文件不做模拟）。
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
VAR = HERE / "var"


class DemoKernel:
    def __init__(self, mcp_cmd: list[str] | None = None):
        self.mcp_cmd = mcp_cmd or [sys.executable, str(HERE / "mcp_fs.py")]
        self.mcp = None                   # 测试可注入假驱动；否则懒起真 MCP
        self._procs: dict[int, subprocess.Popen] = {}
        self._caps: dict[int, set[str]] = {}
        self._names: dict[int, str] = {}
        self.audit_path = VAR / "audit.jsonl"
        VAR.mkdir(exist_ok=True)
        self.audit_path.write_text("", encoding="utf-8")
        self._lock = threading.Lock()

    # -- 进程面 ------------------------------------------------------------
    def write_script(self, agent_id: str, script: list[dict]) -> None:
        d = VAR / "scripts"
        d.mkdir(exist_ok=True)
        (d / f"{agent_id}.json").write_text(json.dumps(script), encoding="utf-8")

    def spawn(self, agent_id: str, caps: list[str],
              program: list[str] | None = None) -> int:
        program = program or [sys.executable, str(HERE / "agent.py"), agent_id]
        proc = subprocess.Popen(program, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True,
                                encoding="utf-8")
        self._procs[proc.pid] = proc
        self._caps[proc.pid] = set(caps)
        self._names[proc.pid] = agent_id
        return proc.pid

    def kill(self, pid: int, sig=signal.SIGTERM) -> None:
        self._procs[pid].send_signal(sig)

    def agent_exit(self, pid: int):
        return self._procs[pid].poll()

    # -- syscall 面 ----------------------------------------------------------
    def syscall_loop(self, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        pending = {pid: p for pid, p in self._procs.items()}
        while pending and time.monotonic() < deadline:
            for pid, proc in list(pending.items()):
                line = proc.stdout.readline()
                if not line:                       # agent 退出（EOF）
                    del pending[pid]
                    continue
                req = json.loads(line)
                reply = self._syscall(pid, req)
                try:
                    proc.stdin.write(json.dumps(reply, ensure_ascii=False) + "\n")
                    proc.stdin.flush()
                except (BrokenPipeError, ValueError):
                    # agent 已被信号杀死（无读者）：syscall 已审计，应答无处投递
                    del pending[pid]
                    continue

    def _syscall(self, pid: int, req: dict) -> dict:
        op, args = str(req.get("op")), req.get("args") or {}
        if op not in self._caps[pid]:
            reply = {"ok": False, "error": f"EPERM: {op} not in caps of pid {pid}"}
        elif op == "sleep":
            reply = {"ok": True, "result": "interrupted?"}
        else:
            reply = self._dispatch(op, args)      # 放行 → 代理到 MCP 驱动
        self._audit(pid, op, args, reply)
        return reply

    def _dispatch(self, op: str, args: dict) -> dict:
        if self.mcp is None:
            self.mcp = _McpProxy(self.mcp_cmd)
        try:
            out = self.mcp.call(op, args)
            return {"ok": True, "result": out["content"][0]["text"]}
        except Exception as exc:
            return {"ok": False, "error": f"EIO: {exc}"}

    # -- 审计 --------------------------------------------------------------
    def _audit(self, pid: int, op: str, args: dict, reply: dict) -> None:
        row = {"t": time.time(), "pid": pid, "agent": self._names[pid],
               "op": op, "args": args, "ok": reply["ok"],
               "result": str(reply.get("result") or reply.get("error"))[:120]}
        with self._lock:
            with self.audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def audit_rows(self) -> list[dict]:
        return [json.loads(l) for l in
                self.audit_path.read_text(encoding="utf-8").splitlines() if l]


class _McpProxy:
    """内核持有的 MCP 客户端：起 mcp_fs 子进程，握手后逐条 tools/call。"""

    def __init__(self, cmd: list[str]):
        self._p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, text=True,
                                   encoding="utf-8")
        self._id = 0

    def call(self, name: str, args: dict) -> dict:
        self._id += 1
        req = {"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
               "params": {"name": name, "arguments": args}}
        self._p.stdin.write(json.dumps(req) + "\n")
        self._p.stdin.flush()
        return json.loads(self._p.stdout.readline())["result"]
