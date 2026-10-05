#!/usr/bin/env python3
"""drv_apps —— 应用管理"设备驱动"（MCP Server，adb 通道）。

mobile-mcp 采纳批次（评估书 §5 ◐→●，docs/research/2026-09-29-mobile-mcp-assessment.md）：

    apps.list    列出已装应用（只读）
    apps.launch  启动应用（monkey LAUNCHER；内核 pkg 白名单闸）
    apps.close   强制停止应用（am force-stop；内核 pkg 白名单闸）

安全模型：与 drv_screen 同构——内核 task_scope `pkg:<package>` 白名单是
第一层（kernel.syscall 对 pkg 参数强制）；驱动层对包名做字符白名单校验
（字母/数字/点/下划线/连字符），杜绝 shell 注入面。
装卸 App（install/uninstall）仍按评估书裁决不实现（不可逆、FleetLedger
计价设计未先行）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402
from screen_adb import Adb  # noqa: E402

drv = MCPServer("drv_apps", version="0.1.0")

_adb: Adb | None = None

_PKG_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def set_adb(adb: Adb | None) -> None:
    """注入 adb 传输（测试用 FakeAdb；生产留 None 惰性构造默认 Adb）。"""
    global _adb
    _adb = adb


def get_adb() -> Adb:
    global _adb
    if _adb is None:
        _adb = Adb()
    return _adb


def _check_pkg(pkg: str) -> str:
    if not pkg or not _PKG_RE.match(pkg):
        raise ValueError(f"EINVAL: bad package name {pkg!r}")
    return pkg


@drv.tool("apps.list", "列出设备已装应用包名（只读）",
          {"type": "object", "properties": {}})
def apps_list() -> str:
    adb = get_adb()
    out = adb.shell(["pm", "list", "packages"])
    pkgs = [line.removeprefix("package:").strip()
            for line in out.splitlines() if line.strip().startswith("package:")]
    return json.dumps({"packages": pkgs}, ensure_ascii=False)


@drv.tool(
    "apps.launch", "启动应用（pkg 必须落在 task_scope pkg: 白名单内）",
    {"type": "object",
     "properties": {"pkg": {"type": "string", "description": "应用包名"}},
     "required": ["pkg"]},
    reversible=False, risk="medium", irreversibility_cost=1,
)
def apps_launch(pkg: str) -> str:
    adb = get_adb()
    _check_pkg(pkg)
    adb.shell(["monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])
    return f"OK launched {pkg}"


@drv.tool(
    "apps.close", "强制停止应用（pkg 必须落在 task_scope pkg: 白名单内）",
    {"type": "object",
     "properties": {"pkg": {"type": "string", "description": "应用包名"}},
     "required": ["pkg"]},
    reversible=False, risk="medium", irreversibility_cost=1,
)
def apps_close(pkg: str) -> str:
    adb = get_adb()
    _check_pkg(pkg)
    adb.shell(["am", "force-stop", pkg])
    return f"OK stopped {pkg}"


if __name__ == "__main__":
    drv.serve_forever()
