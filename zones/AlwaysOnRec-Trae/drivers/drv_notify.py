#!/usr/bin/env python3
"""drv_notify —— 通知"传感器驱动"（MCP Server）。

把手机通知流暴露成 syscall `notify.list`，双传输：

    termux  Termux:API（`termux-notification-list`，手机端自包含方案）
    app     TimnetLpaiApp 的 /notifications 端点（HTTP，经 adb forward）

通知是敏感数据：`notify.*` 的 caps 只应授给可信 agent；每次读取写审计。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402

drv = MCPServer("drv_notify", version="0.1.0")

TRANSPORT = os.environ.get("LAOS_NOTIFY_TRANSPORT", "termux")
PHONE_ENDPOINT = os.environ.get("LAOS_PHONE_ENDPOINT", "http://127.0.0.1:8900")

_runner = None  # 可注入的 subprocess 执行器（测试替换）


def _run(args: list[str], timeout: float = 10.0):
    if _runner is not None:
        return _runner(args, timeout)
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise IOError(f"EIO: {args[0]} rc={r.returncode}: {(r.stdout + r.stderr)[:200]}")
    return r


def notify_list() -> str:
    """读取当前通知列表（JSON 字符串）。"""
    if TRANSPORT == "app":
        with urllib.request.urlopen(f"{PHONE_ENDPOINT}/notifications", timeout=5) as r:
            return r.read().decode("utf-8")
    r = _run(["termux-notification-list"])
    return r.stdout if hasattr(r, "stdout") else str(r)


@drv.tool("notify.list", "读取当前通知列表（敏感：仅授可信 agent）",
          {"type": "object", "properties": {}})
def _tool_notify_list() -> str:
    return notify_list()


if __name__ == "__main__":
    drv.serve_forever()
