#!/usr/bin/env python3
"""drv_proc —— 进程“设备驱动”（MCP Server）。

把宿主的进程能力封装成 2 条 syscall：proc.list / proc.exec。

exec 走**白名单**而不是黑名单：只有声明过的命令前缀才允许执行，
且内置危险模式拦截（rm -rf /、mkfs、dd 等）。这是纵深防御的第三层。
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402

drv = MCPServer("drv_proc", version="0.1.0")

# 白名单：只有这些命令前缀可以被 Agent 执行
ALLOWLIST: tuple[str, ...] = tuple(
    filter(None, os.environ.get("LAOS_EXEC_ALLOW", "echo,hostname,uname,whoami,uptime").split(","))
)

# 无论白名单怎么配，这些模式一律拒绝
DENY_PATTERNS: tuple[str, ...] = (
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){",
    "> /dev/sda",
    "shutdown",
    "reboot",
)

TIMEOUT = int(os.environ.get("LAOS_EXEC_TIMEOUT", "5"))


@drv.tool(
    "proc.list",
    "列出当前进程列表（跨平台，只返回摘要字段）",
    {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}},
)
def proc_list(limit: int = 20) -> str:
    system = platform.system()
    if system == "Windows":
        cmd = ["tasklist", "/FO", "CSV", "/NH"]
    else:
        cmd = ["ps", "-eo", "pid,ppid,etime,comm", "--no-headers"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except Exception as exc:
        return f"EIO: {exc}"
    lines = [l for l in out.stdout.strip().splitlines() if l.strip()]
    return "\n".join(lines[:limit]) or "(empty)"


@drv.tool(
    "proc.exec",
    "执行一条白名单内的命令（只读倾向，禁止危险操作）",
    {
        "type": "object",
        "properties": {"cmdline": {"type": "string", "description": "要执行的命令行"}},
        "required": ["cmdline"],
    },
    reversible=False,
    risk="high",
    irreversibility_cost=3,
)
def proc_exec(cmdline: str) -> str:
    cmd = cmdline.strip()
    if not cmd:
        raise ValueError("EINVAL: empty cmdline")

    low = cmd.lower()
    for pat in DENY_PATTERNS:
        if pat in low:
            raise PermissionError(f"EDENIED: dangerous command blocked by driver: {pat!r}")

    prog = cmd.split()[0]
    if prog not in ALLOWLIST:
        raise PermissionError(
            f"EACCES: {prog!r} not in exec allowlist {list(ALLOWLIST)}"
        )

    try:
        out = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=os.environ.get("LAOS_EXEC_CWD") or None,
        )
    except subprocess.TimeoutExpired:
        return f"ETIMEDOUT: {cmd}"
    body = (out.stdout or "").strip() or (out.stderr or "").strip()
    return f"exit={out.returncode}\n{body}"


if __name__ == "__main__":
    drv.serve_forever()
