"""MCP —— Model Context Protocol 的最小可用实现（JSON-RPC 2.0 over stdio）。

在 Linux AgentOS 里的定位：

    MCP Server  ==  设备驱动（driver）
    MCP tool    ==  系统调用号（syscall number）
    tools/call  ==  syscall(pid, nr, args)

这里只实现内核需要的子集：initialize / tools/list / tools/call，
线格式与官方 MCP 规范一致，生产环境可直接替换为官方 SDK。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable

PROTOCOL_VERSION = "2025-06-18"

_JSONRPC_PARSE_ERROR = -32700
_JSONRPC_INVALID_REQUEST = -32600
_JSONRPC_METHOD_NOT_FOUND = -32601
_JSONRPC_INTERNAL_ERROR = -32603


# --------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------
@dataclass
class ToolSpec:
    """一个 MCP tool 的描述，等价于内核里的一条 syscall 声明。"""

    name: str
    description: str
    input_schema: dict
    reversible: bool = True
    risk: str = "low"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "reversible": self.reversible,
            "risk": self.risk,
        }


@dataclass
class CallResult:
    """等价于 syscall 的返回值 + errno。"""

    ok: bool
    content: list[dict]
    error: str | None = None

    @property
    def text(self) -> str:
        if not self.ok:
            return f"[error] {self.error}"
        return "\n".join(c.get("text", "") for c in self.content if c.get("type") == "text")

    @classmethod
    def ok_text(cls, text: str) -> "CallResult":
        return cls(True, [{"type": "text", "text": text}])

    @classmethod
    def fail(cls, error: str) -> "CallResult":
        return cls(False, [], error)


# --------------------------------------------------------------------------
# Server 侧：让一个普通脚本变成“设备驱动”
# --------------------------------------------------------------------------
class MCPServer:
    def __init__(self, name: str, version: str = "0.1.0"):
        self.name = name
        self.version = version
        self._tools: dict[str, tuple[ToolSpec, Callable[..., str]]] = {}

    def tool(self, name: str, description: str, schema: dict | None = None,
             reversible: bool = True, risk: str = "low"):
        def deco(fn: Callable[..., str]):
            self._tools[name] = (
                ToolSpec(
                    name, description,
                    schema or {"type": "object", "properties": {}},
                    reversible=reversible, risk=risk,
                ),
                fn,
            )
            return fn

        return deco

    # -- 协议分发 ---------------------------------------------------------
    def _handle(self, req: dict) -> dict | None:
        rid = req.get("id")
        method = req.get("method", "")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            }

        if method.startswith("notifications/"):
            return None  # 通知无响应

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"tools": [t.to_dict() for t, _ in self._tools.values()]},
            }

        if method == "tools/call":
            params = req.get("params") or {}
            tool_name = params.get("name", "")
            arguments = params.get("arguments") or {}
            entry = self._tools.get(tool_name)
            if entry is None:
                return {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {
                        "code": _JSONRPC_METHOD_NOT_FOUND,
                        "message": f"ENOSYS: no such tool: {tool_name}",
                    },
                }
            try:
                out = entry[1](**arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {
                        "content": [{"type": "text", "text": str(out)}],
                        "isError": False,
                    },
                }
            except Exception as exc:
                # 驱动自己抛出的 errno 前缀（EACCES/EDENIED/ENOENT...）原样透传，
                # 不要再套一层 EIO，否则上层无法区分"被拒绝"和"驱动崩溃"
                return {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {
                        "content": [{"type": "text", "text": str(exc)}],
                        "isError": True,
                    },
                }

        return {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {
                "code": _JSONRPC_METHOD_NOT_FOUND,
                "message": f"unknown method: {method}",
            },
        }

    def serve_forever(self) -> None:
        """stdio 主循环：一行一个 JSON-RPC 请求。"""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": _JSONRPC_PARSE_ERROR, "message": "parse error"},
                }
                self._write(resp)
                continue
            resp = self._handle(req)
            if resp is not None:
                self._write(resp)

    def _write(self, obj: dict) -> None:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


# --------------------------------------------------------------------------
# Client 侧：内核用来跟驱动打交道的“驱动句柄”
# --------------------------------------------------------------------------
class MCPClient:
    """以子进程方式拉起一个 MCP Server，并通过 stdio 与之通信。"""

    def __init__(self, name: str, argv: list[str], env: dict | None = None):
        self.name = name
        self._argv = argv
        self._env = env
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._id = 0
        self.tools: dict[str, ToolSpec] = {}

    # -- 生命周期 ---------------------------------------------------------
    def start(self) -> None:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        if self._env:
            env.update(self._env)
        self._proc = subprocess.Popen(
            self._argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
        )
        self._initialize()
        self.tools = {t.name: t for t in self.list_tools()}

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.close()  # type: ignore[union-attr]
                self._proc.wait(timeout=3)
            except Exception:
                self._proc.kill()
        if self._proc:
            for stream in (self._proc.stdin, self._proc.stdout, self._proc.stderr):
                try:
                    if stream and not stream.closed:
                        stream.close()
                except Exception:
                    pass

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    # -- RPC --------------------------------------------------------------
    def _rpc(self, method: str, params: dict | None = None, notify: bool = False) -> dict:
        assert self._proc is not None, "driver not started"
        with self._lock:
            self._id += 1
            req: dict[str, Any] = {"jsonrpc": "2.0", "id": self._id, "method": method}
            if params is not None:
                req["params"] = params
            self._proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")  # type: ignore[union-attr]
            self._proc.stdin.flush()  # type: ignore[union-attr]
            if notify:
                return {}
            while True:
                line = self._proc.stdout.readline()  # type: ignore[union-attr]
                if not line:
                    raise RuntimeError(f"driver {self.name} exited unexpectedly")
                resp = json.loads(line)
                if resp.get("id") == self._id:
                    return resp

    def _initialize(self) -> None:
        self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "laosd", "version": "0.1.0"},
            },
        )
        self._rpc("notifications/initialized", notify=True)

    def list_tools(self) -> list[ToolSpec]:
        resp = self._rpc("tools/list")
        return [
            ToolSpec(
                t["name"],
                t.get("description", ""),
                t.get("inputSchema", {"type": "object", "properties": {}}),
            )
            for t in resp["result"]["tools"]
        ]

    def call_tool(self, name: str, arguments: dict) -> CallResult:
        resp = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if "error" in resp:
            return CallResult.fail(resp["error"].get("message", "unknown error"))
        result = resp.get("result", {})
        content = result.get("content", [])
        if result.get("isError"):
            return CallResult(False, content, content[0].get("text") if content else "EIO")
        return CallResult(True, content)
