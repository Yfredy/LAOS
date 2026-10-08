#!/usr/bin/env python3
"""drv_events —— 全天候感知"事件驱动"（MCP Server）。

拉取真机 App 的 /events 端点（情感变化等传感器事件环形缓冲）。
存储不归本驱动：agent 拉到自己上下文后，自行 mem.remember(kind="sensor")
入库——保持"驱动只做设备、内核管语义"的分层。

    ADSP LPAI（<5mW 常驻）→ App /events → drv_events → agent 上下文 → mem.*
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402

drv = MCPServer("drv_events", version="0.1.0")

ENDPOINT = os.environ.get("LAOS_NPU_ENDPOINT", "http://127.0.0.1:8900")


def fetch_events(since_ts: float = 0, timeout: float = 5.0) -> list[dict]:
    """拉取 App 端点的事件数组（since 毫秒时间戳之后的新事件）。"""
    url = f"{ENDPOINT.rstrip('/')}/events?since={since_ts}"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data.get("events", [])


def ingest_events(events: list[dict], memory) -> int:
    """事件 → 记忆库（kind="sensor"）。返回入库条数（laosd 常驻循环用）。"""
    n = 0
    for e in events:
        memory.remember(kind="sensor",
                        text=f"传感器事件 [{e.get('type', '?')}] {e.get('emotion', '')} "
                             f"conf={e.get('confidence', '')}",
                        tags=["device"])
        n += 1
    return n


@drv.tool(
    "events.since",
    "拉取真机传感器事件（情感变化等；since_ts 为毫秒时间戳）",
    {"type": "object",
     "properties": {"since_ts": {"type": "number"}},
     "required": []},
)
def events_since(since_ts: float = 0) -> str:
    events = fetch_events(since_ts)
    return json.dumps({"count": len(events), "events": events[:20]},
                      ensure_ascii=False)


@drv.tool("events.status", "事件端点可达性与配置",
          {"type": "object", "properties": {}})
def events_status() -> str:
    try:
        events = fetch_events(since_ts=0)
        return json.dumps({"endpoint": ENDPOINT, "reachable": True,
                           "events": len(events)}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"endpoint": ENDPOINT, "reachable": False,
                           "detail": str(exc)[:120]}, ensure_ascii=False)


if __name__ == "__main__":
    drv.serve_forever()
