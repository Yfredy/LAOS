#!/usr/bin/env python3
"""drv_screen —— 屏幕"设备驱动"（MCP Server，adb 通道）。

把 Android 屏幕的理解与操控封装成 syscall：

    screen.dump   读取控件树（uiautomator dump）+ 前台包名（只读）
    screen.tap / swipe / text / back   操控（reversible=False，计风险 1 点）
    screen.shot   截屏到 var/screen/（只读）

安全模型（纵深防御）：
    第一层  内核 pkg 作用域——task_scope 含 `pkg:<package>` 时，操控类调用
            的 pkg 参数必须落在白名单内，越界 EACCES（kernel.syscall 强制）
    第二层  驱动前台校验——每次操控前 dumpsys 取前台包名，与 pkg 不符
            拒绝（EACCES: foreground package mismatch），防状态漂移
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402
from screen_adb import Adb, parse_current_focus, parse_uiautomator_xml  # noqa: E402

drv = MCPServer("drv_screen", version="0.1.0")

_adb: Adb | None = None


def set_adb(adb: Adb | None) -> None:
    """注入 adb 传输（测试用 FakeAdb；生产留 None 惰性构造默认 Adb）。"""
    global _adb
    _adb = adb


def get_adb() -> Adb:
    global _adb
    if _adb is None:
        _adb = Adb()
    return _adb


def _dump(adb: Adb) -> dict:
    raw = adb.exec_out(["uiautomator", "dump", "/dev/tty"]).decode("utf-8", errors="replace")
    return parse_uiautomator_xml(raw)


def _focus_package(adb: Adb) -> str | None:
    return parse_current_focus(adb.shell(["dumpsys", "window"]))


def _require_pkg(adb: Adb, pkg: str) -> str:
    """纵深防御第二层：操控前校验前台包名与 pkg 一致。"""
    current = _focus_package(adb)
    if current != pkg:
        raise PermissionError(
            f"EACCES: foreground package mismatch (focus={current}, expected={pkg})")
    return current


@drv.tool("screen.dump", "读取控件树与前台包名（只读）",
          {"type": "object", "properties": {}})
def screen_dump() -> str:
    adb = get_adb()
    data = _dump(adb)
    return json.dumps({
        "current_package": _focus_package(adb) or data["package"],
        "nodes": data["nodes"][:80],
    }, ensure_ascii=False)


@drv.tool(
    "screen.tap", "点击坐标（pkg 必须与 task_scope/前台一致）",
    {"type": "object",
     "properties": {"x": {"type": "integer"}, "y": {"type": "integer"},
                    "pkg": {"type": "string", "description": "目标 App 包名"}},
     "required": ["x", "y", "pkg"]},
    reversible=False, risk="medium", irreversibility_cost=1,
)
def screen_tap(x: int, y: int, pkg: str) -> str:
    adb = get_adb()
    _require_pkg(adb, pkg)
    adb.shell(["input", "tap", str(x), str(y)])
    return f"OK tapped ({x},{y}) in {pkg}"


@drv.tool(
    "screen.swipe", "滑动",
    {"type": "object",
     "properties": {"x1": {"type": "integer"}, "y1": {"type": "integer"},
                    "x2": {"type": "integer"}, "y2": {"type": "integer"},
                    "ms": {"type": "integer"}, "pkg": {"type": "string"}},
     "required": ["x1", "y1", "x2", "y2", "pkg"]},
    reversible=False, risk="medium", irreversibility_cost=1,
)
def screen_swipe(x1: int, y1: int, x2: int, y2: int, ms: int = 300, pkg: str = "") -> str:
    adb = get_adb()
    if pkg:
        _require_pkg(adb, pkg)
    adb.shell(["input", "swipe", str(x1), str(y1), str(x2), str(y2), str(ms)])
    return f"OK swiped ({x1},{y1})->({x2},{y2})"


@drv.tool(
    "screen.text", "输入文本（空格以 %s 转义）",
    {"type": "object",
     "properties": {"text": {"type": "string"}, "pkg": {"type": "string"}},
     "required": ["text", "pkg"]},
    reversible=False, risk="medium", irreversibility_cost=1,
)
def screen_text(text: str, pkg: str) -> str:
    adb = get_adb()
    _require_pkg(adb, pkg)
    adb.shell(["input", "text", text.replace(" ", "%s")])
    return f"OK text input ({len(text)} chars)"


@drv.tool(
    "screen.back", "返回键",
    {"type": "object", "properties": {"pkg": {"type": "string"}}, "required": ["pkg"]},
    reversible=False, risk="low", irreversibility_cost=1,
)
def screen_back(pkg: str) -> str:
    adb = get_adb()
    _require_pkg(adb, pkg)
    adb.shell(["input", "keyevent", "4"])
    return f"OK back in {pkg}"


@drv.tool("screen.shot", "截屏并保存（只读）", {"type": "object", "properties": {}})
def screen_shot() -> str:
    adb = get_adb()
    out_dir = Path("var") / "screen"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"shot-{int(time.time())}.png"
    out.write_bytes(adb.exec_out(["screencap", "-p"]))
    return f"OK shot -> {out}"


if __name__ == "__main__":
    drv.serve_forever()
