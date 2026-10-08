#!/usr/bin/env python3
"""mcp_fs —— Linux AgentOS demo 的"设备驱动"：stdio 上的 MCP 文件服务。

对应表：MCP server = 设备驱动（stdio = 设备总线，tools/list = 设备探测，
tools/call = 一次设备 I/O）。工具面刻意窄：fs.read/fs.write 只在 jail 内
（DEMO_JAIL），time.now 零状态——驱动只做设备语义，不做治理（治理在内核）。

JSON-RPC 2.0 over stdio（MCP 传输契约）；协议字段参考 laos/mcp.py 同型实现。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

TOOLS = [
    {"name": "fs.read", "description": "读 jail 内相对路径文件",
     "inputSchema": {"type": "object",
                     "properties": {"path": {"type": "string"}},
                     "required": ["path"]}},
    {"name": "fs.write", "description": "写 jail 内相对路径文件",
     "inputSchema": {"type": "object",
                     "properties": {"path": {"type": "string"},
                                    "data": {"type": "string"}},
                     "required": ["path", "data"]}},
    {"name": "time.now", "description": "当前时间（零状态驱动示例）",
     "inputSchema": {"type": "object", "properties": {}}},
]

SERVER_INFO = {"name": "mcp-fs", "version": "0.1.0"}


def _jail() -> Path:
    root = Path(os.environ.get("DEMO_JAIL", Path(__file__).parent / "var" / "jail"))
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _resolve(jail: Path, rel: str) -> Path:
    p = (jail / rel).resolve()
    if not p.is_relative_to(jail):   # 越界一律拒绝（驱动侧硬边界）
        raise PermissionError(f"EPERM: out of jail: {rel!r}")
    return p


def _call(name: str, args: dict) -> str:
    jail = _jail()
    if name == "fs.read":
        return _resolve(jail, str(args["path"])).read_text(encoding="utf-8")
    if name == "fs.write":
        p = _resolve(jail, str(args["path"]))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(args["data"]), encoding="utf-8")
        return f"OK {len(str(args['data']))} bytes"
    if name == "time.now":
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    raise ValueError(f"ENOSYS: unknown tool {name!r}")


def main() -> int:
    for line in sys.stdin:                      # 每行一个 JSON-RPC 请求
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        rid, method = req.get("id"), req.get("method")
        try:
            if method == "initialize":
                result = {"protocolVersion": "2025-06-18",
                          "capabilities": {"tools": {}},
                          "serverInfo": SERVER_INFO}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                text = _call(req["params"]["name"], req["params"].get("arguments") or {})
                result = {"content": [{"type": "text", "text": text}]}
            else:
                raise ValueError(f"ENOSYS: {method}")
            resp = {"jsonrpc": "2.0", "id": rid, "result": result}
        except Exception as exc:                # 驱动错误按 JSON-RPC error 回
            resp = {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32000, "message": f"{type(exc).__name__}: {exc}"}}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
