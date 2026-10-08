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
import platform
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

PROTOCOL_VERSION = "2026-07-28"

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
    irreversibility_cost: int = 1  # 不可逆操作的风险定价（Irreversibility Budget）

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "reversible": self.reversible,
            "risk": self.risk,
            "irreversibilityCost": self.irreversibility_cost,
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
        # server→client 请求的 id 计数（从 10000 起，避免与 client 请求 id 混淆）
        self._req_id = 10000
        # Tasks（2026-07-28）：taskId -> {"taskId","status","content","is_error"}
        self._tasks: dict[str, dict] = {}
        self._task_seq = 0

    def tool(self, name: str, description: str, schema: dict | None = None,
             reversible: bool = True, risk: str = "low",
             irreversibility_cost: int = 1):
        def deco(fn: Callable[..., str]):
            self._tools[name] = (
                ToolSpec(
                    name, description,
                    schema or {"type": "object", "properties": {}},
                    reversible=reversible, risk=risk,
                    irreversibility_cost=irreversibility_cost,
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
                    "capabilities": {"tools": {}, "tasks": {}},
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
            spec, fn = entry
            if "task" in params:
                # Tasks（2026-07-28）：异步执行，立即返回任务句柄。
                # 注意用 key 存在性判断而非真值——规范线格式是 "task": {}（空 dict 为假值）。
                # 红线：task 线程内禁止 elicit（会与主循环抢 stdin）。
                self._task_seq += 1
                task_id = f"t-{self._task_seq}"
                record = {"taskId": task_id, "status": "working",
                          "content": None, "is_error": False}
                self._tasks[task_id] = record

                def _run():
                    try:
                        out = str(fn(**arguments))
                        record["content"] = [{"type": "text", "text": out}]
                    except Exception as exc:
                        record["content"] = [{"type": "text", "text": str(exc)}]
                        record["is_error"] = True
                    record["status"] = "completed"

                threading.Thread(target=_run, daemon=True).start()
                return {"jsonrpc": "2.0", "id": rid,
                        "result": {"task": {"taskId": task_id, "status": "working"}}}
            try:
                out = fn(**arguments)
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

        if method == "tasks/get":
            task = self._tasks.get((req.get("params") or {}).get("taskId", ""))
            if task is None:
                return {"jsonrpc": "2.0", "id": rid,
                        "error": {"code": _JSONRPC_METHOD_NOT_FOUND,
                                  "message": "ENOENT: no such task"}}
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"task": {"taskId": task["taskId"], "status": task["status"]}}}

        if method == "tasks/result":
            task = self._tasks.get((req.get("params") or {}).get("taskId", ""))
            if task is None:
                return {"jsonrpc": "2.0", "id": rid,
                        "error": {"code": _JSONRPC_METHOD_NOT_FOUND,
                                  "message": "ENOENT: no such task"}}
            if task["status"] != "completed":
                return {"jsonrpc": "2.0", "id": rid,
                        "result": {"task": {"taskId": task["taskId"], "status": task["status"]}}}
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"status": "completed", "content": task["content"],
                               "isError": task["is_error"]}}

        return {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {
                "code": _JSONRPC_METHOD_NOT_FOUND,
                "message": f"unknown method: {method}",
            },
        }

    def serve_forever(self) -> None:
        """stdio 主循环：逐行读 JSON-RPC 请求（readline 而非迭代器，
        便于 elicit 在工具执行中途再读一行响应而不丢缓冲数据）。"""
        while True:
            line = sys.stdin.readline()
            if not line:  # EOF
                break
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

    def elicit(self, message: str, schema: dict | None = None) -> dict:
        """server→client 请求用户输入（MCP elicitation/create，同步路径专用）。

        仅允许在 serve_forever 主线程的工具执行中调用——task 线程内调用
        会与主循环抢 stdin（规范上也不允许）。
        """
        self._req_id += 1
        req_id = self._req_id
        self._write({"jsonrpc": "2.0", "id": req_id, "method": "elicitation/create",
                     "params": {"message": message, "requestedSchema": schema or {}}})
        while True:
            line = sys.stdin.readline()
            if not line:
                raise RuntimeError(f"EIO: stdin closed during elicitation: {message!r}")
            line = line.strip()
            if not line:
                continue
            resp = json.loads(line)
            if resp.get("id") != req_id:
                continue  # 与本次请求无关的消息（理论上不应出现）丢弃
            if "error" in resp:
                raise PermissionError(f"EDENIED: elicitation rejected by client: "
                                      f"{resp['error'].get('message', '')}")
            result = resp.get("result") or {}
            if result.get("action") == "accept":
                return result
            raise PermissionError(f"EDENIED: elicitation declined ({message!r})")

    def _write(self, obj: dict) -> None:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


# --------------------------------------------------------------------------
# Client 侧：内核用来跟驱动打交道的“驱动句柄”
# --------------------------------------------------------------------------
class MCPClient:
    """以子进程方式拉起一个 MCP Server，并通过 stdio 与之通信。"""

    def __init__(self, name: str, argv: list[str], env: dict | None = None,
                 on_server_request: Callable[[str, dict], dict] | None = None):
        self.name = name
        self._argv = argv
        self._env = env
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._id = 0
        self.tools: dict[str, ToolSpec] = {}
        self.capabilities: dict = {}  # initialize 响应里的 server capabilities
        self._on_server_request = on_server_request

    @property
    def on_server_request(self) -> Callable[[str, dict], dict] | None:
        """server→client 请求（elicitation/create 等）的拦截 handler。

        handler(method, params) -> result dict；None 表示不支持（回 -32601）。
        须在 start() 之前设置。
        """
        return self._on_server_request

    @on_server_request.setter
    def on_server_request(self, handler: Callable[[str, dict], dict] | None) -> None:
        self._on_server_request = handler

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

    @property
    def driver_pid(self) -> int | None:
        """真实驱动进程 pid（unshare --fork 的直接子进程；shim execvp 后 pid 稳定）。

        非 Linux、无 /proc 或解析失败时回退 wrapper pid —— 调用方无需分支。
        """
        if self._proc is None:
            return None
        wrapper = self._proc.pid
        if platform.system() != "Linux":
            return wrapper
        try:
            raw = (Path("/proc") / str(wrapper) / "task" / str(wrapper) / "children").read_text()
            kids = raw.split()
            return int(kids[0]) if kids else wrapper
        except (OSError, ValueError):
            return wrapper

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
                if "method" in resp and resp.get("id") is not None:
                    # server→client 请求（elicitation/create 等）：拦截并回包
                    handler = self._on_server_request
                    if handler is not None:
                        try:
                            result = handler(resp["method"], resp.get("params") or {})
                        except Exception as exc:  # handler 抛错按 JSON-RPC error 回
                            self._proc.stdin.write(json.dumps(  # type: ignore[union-attr]
                                {"jsonrpc": "2.0", "id": resp["id"],
                                 "error": {"code": _JSONRPC_INTERNAL_ERROR,
                                           "message": str(exc)}}) + "\n")
                            self._proc.stdin.flush()  # type: ignore[union-attr]
                            continue
                        self._proc.stdin.write(json.dumps(  # type: ignore[union-attr]
                            {"jsonrpc": "2.0", "id": resp["id"], "result": result}) + "\n")
                        self._proc.stdin.flush()  # type: ignore[union-attr]
                        continue
                    self._proc.stdin.write(json.dumps(  # type: ignore[union-attr]
                        {"jsonrpc": "2.0", "id": resp["id"],
                         "error": {"code": _JSONRPC_METHOD_NOT_FOUND,
                                   "message": f"client does not support {resp['method']}"}}) + "\n")
                    self._proc.stdin.flush()  # type: ignore[union-attr]
                    continue
                if resp.get("id") == self._id:
                    return resp

    def _initialize(self) -> None:
        resp = self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "laosd", "version": "0.1.0"},
            },
        )
        self.capabilities = resp.get("result", {}).get("capabilities", {})
        self._rpc("notifications/initialized", notify=True)

    def list_tools(self) -> list[ToolSpec]:
        resp = self._rpc("tools/list")
        return [
            ToolSpec(
                t["name"],
                t.get("description", ""),
                t.get("inputSchema", {"type": "object", "properties": {}}),
                reversible=t.get("reversible", True),
                risk=t.get("risk", "low"),
                irreversibility_cost=int(t.get("irreversibilityCost", 1)),
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

    def call_tool_task(self, name: str, arguments: dict) -> str:
        """异步发起 tools/call（Tasks 2026-07-28），返回 taskId。"""
        resp = self._rpc("tools/call", {"name": name, "arguments": arguments,
                                        "task": {}})
        task = resp.get("result", {}).get("task") or {}
        if not task.get("taskId"):
            raise RuntimeError(f"driver {self.name} did not accept task mode")
        return task["taskId"]

    def task_result(self, task_id: str, timeout_s: float = 30.0,
                    poll_s: float = 0.05) -> CallResult:
        """轮询 tasks/result 直到 completed / 出错 / 超时。"""
        import time as _time
        deadline = _time.monotonic() + timeout_s
        while _time.monotonic() < deadline:
            resp = self._rpc("tasks/result", {"taskId": task_id})
            if "error" in resp:
                return CallResult.fail(resp["error"].get("message", "unknown error"))
            result = resp.get("result", {})
            if result.get("status") == "completed":
                content = result.get("content", [])
                if result.get("isError"):
                    return CallResult(False, content,
                                      content[0].get("text") if content else "EIO")
                return CallResult(True, content)
            _time.sleep(poll_s)
        return CallResult.fail(f"ETIMEDOUT: task {task_id}")
