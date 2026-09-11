#!/usr/bin/env python3
"""drv_comms —— 通信"设备驱动"（MCP Server，Termux:API 传输）。

把短信收发与 TTS 播报封装成 syscall：

    comms.sms_list        读取短信列表
    comms.sms_send        发送短信（reversible=False：发出不可撤回）
    comms.tts_speak       TTS 播报（Agent 的"嘴"）

安全：sms_send 是高风险操作（reversible=False, risk="medium"）——结合内核
确认横幅，外发消息必须经人类裁决。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402

drv = MCPServer("drv_comms", version="0.1.0")

_runner = None  # 可注入的 subprocess 执行器（测试替换）


def _run(args: list[str], timeout: float = 15.0):
    if _runner is not None:
        return _runner(args, timeout)
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise IOError(f"EIO: {args[0]} rc={r.returncode}: {(r.stdout + r.stderr)[:200]}")
    return r


@drv.tool(
    "comms.sms_list", "读取短信列表（敏感数据）",
    {"type": "object",
     "properties": {"limit": {"type": "integer", "default": 10}}},
)
def sms_list(limit: int = 10) -> str:
    r = _run(["termux-sms-list", "-l", str(limit)])
    data = json.loads(r.stdout if hasattr(r, "stdout") else str(r))
    lines = [f"[{m.get('type', '?')}] {m.get('address', '?')}: "
             f"{str(m.get('body', ''))[:50]}" for m in data]
    return "\n".join(lines) or "(empty)"


@drv.tool(
    "comms.sms_send", "发送短信（不可撤回）",
    {"type": "object",
     "properties": {"to": {"type": "string"}, "text": {"type": "string"}},
     "required": ["to", "text"]},
    reversible=False, risk="medium",
)
def sms_send(to: str, text: str) -> str:
    to = (to or "").strip()
    if not to:
        raise ValueError("EINVAL: empty recipient")
    if not text:
        raise ValueError("EINVAL: empty text")
    _run(["termux-sms-send", "-n", to, text])
    return f"OK sms sent to {to}"


@drv.tool(
    "comms.tts_speak", "TTS 播报文本（Agent 的嘴）",
    {"type": "object", "properties": {"text": {"type": "string"}},
     "required": ["text"]},
)
def tts_speak(text: str) -> str:
    if not text:
        raise ValueError("EINVAL: empty text")
    _run(["termux-tts-speak", text])
    return f"OK spoken ({len(text)} chars)"


if __name__ == "__main__":
    drv.serve_forever()
