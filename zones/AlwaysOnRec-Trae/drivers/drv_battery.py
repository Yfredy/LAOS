#!/usr/bin/env python3
"""drv_battery —— 电池"传感器驱动"（MCP Server）。

把电池状态暴露成 syscall `battery.status`，供动态功耗定价消费：
低电量时内核上调风险定价乘数，Agent 自动收敛不可逆操作。

双传输：
    termux  Termux:API（`termux-battery-status`，手机端自包含方案）
    app     TimnetLpaiApp 的 /battery 端点（经 adb forward / 本机回环）

传输选择 LAOS_BATTERY_TRANSPORT = termux | app | none（默认 none →
返回 UNAVAILABLE，调用方优雅降级）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402

drv = MCPServer("drv_battery", version="0.1.0")

TRANSPORT = os.environ.get("LAOS_BATTERY_TRANSPORT", "none")
PHONE_ENDPOINT = os.environ.get("LAOS_NPU_ENDPOINT", "http://127.0.0.1:8900")


def parse_termux_battery(raw: str) -> dict:
    """解析 Termux:API 的 JSON 输出 → {percent, charging}。"""
    data = json.loads(raw)
    return {"percent": int(data.get("percentage", 0)),
            "charging": str(data.get("status", "")).upper() in ("CHARGING", "FULL")}


def parse_app_battery(raw: str) -> dict:
    """解析 App /battery 的 JSON 输出 → {percent, charging}。"""
    data = json.loads(raw)
    return {"percent": int(data.get("percent", 0)),
            "charging": bool(data.get("charging", False))}


@drv.tool("battery.status", "查询电池电量与充电状态",
          {"type": "object", "properties": {}})
def battery_status() -> str:
    if TRANSPORT == "termux":
        r = subprocess.run(["termux-battery-status"], capture_output=True,
                           text=True, timeout=10)
        if r.returncode != 0:
            raise IOError(f"EIO: termux-battery-status rc={r.returncode}: "
                          f"{(r.stdout + r.stderr)[:200]}")
        return json.dumps(parse_termux_battery(r.stdout), ensure_ascii=False)
    if TRANSPORT == "app":
        with urllib.request.urlopen(f"{PHONE_ENDPOINT}/battery", timeout=5) as r:
            return json.dumps(parse_app_battery(r.read().decode("utf-8")),
                              ensure_ascii=False)
    return json.dumps({"error": "ENOSYS: no battery transport "
                                "(set LAOS_BATTERY_TRANSPORT=termux|app)"})


if __name__ == "__main__":
    drv.serve_forever()
