#!/usr/bin/env python3
"""drv_sys —— 系统信息“设备驱动”（MCP Server）。

提供 sys.info / sys.load 两条 syscall，并演示 Agentic OS 的一个必备能力：
**宿主机隐私信息保护**。Agent 出于排障目的需要看系统信息，但主机名、
内核精确版本、MAC 等标识信息可被用于指纹识别与外泄。这里默认脱敏，
只有显式设置 LAOS_PRIVACY_MASK=0 才输出原文。
"""

from __future__ import annotations

import hashlib
import os
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402

drv = MCPServer("drv_sys", version="0.1.0")
MASK = os.environ.get("LAOS_PRIVACY_MASK", "1") == "1"


def _mask(value: str, keep: int = 4) -> str:
    if not MASK:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{value[:keep]}***[{digest}]"


@drv.tool("sys.info", "返回宿主系统摘要（主机名默认脱敏）", {"type": "object", "properties": {}})
def sys_info() -> str:
    un = platform.uname()
    return (
        f"system={un.system} release={un.release if not MASK else un.release.split('-')[0]}\n"
        f"machine={un.machine} processor={_mask(un.processor or 'unknown', 6)}\n"
        f"hostname={_mask(un.node)}\n"
        f"python={platform.python_version()} cpus={os.cpu_count()}\n"
        f"privacy_mask={MASK}"
    )


@drv.tool("sys.load", "返回 CPU / 内存 / 磁盘使用情况", {"type": "object", "properties": {}})
def sys_load() -> str:
    lines = []
    try:
        load = os.getloadavg()
        lines.append(f"load1/5/15={load[0]:.2f}/{load[1]:.2f}/{load[2]:.2f}")
    except AttributeError:
        lines.append("loadavg=N/A (Windows)")

    if platform.system() != "Windows":
        try:
            with open("/proc/meminfo", encoding="utf-8") as f:
                info = dict(
                    (parts[0], int(parts[1]))
                    for line in f
                    if len(parts := line.split()) >= 2
                )
            total = info.get("MemTotal", 0) / 1024
            avail = info.get("MemAvailable", info.get("MemFree", 0)) / 1024
            lines.append(f"mem_total={total:.0f}MiB mem_avail={avail:.0f}MiB")
        except Exception:
            lines.append("mem=N/A")

    try:
        usage = os.statvfs(str(Path(__file__).resolve().anchor))
        total = usage.f_blocks * usage.f_frsize / 2**30
        free = usage.f_bavail * usage.f_frsize / 2**30
        lines.append(f"disk_total={total:.1f}GiB disk_free={free:.1f}GiB")
    except Exception:
        lines.append("disk=N/A")
    return "\n".join(lines)


if __name__ == "__main__":
    drv.serve_forever()
