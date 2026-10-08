"""screen_adb —— adb 传输与 uiautomator 解析（drv_screen 的底座）。

设计（CherryUSB porting 模式）：所有 adb 交互收口在 `Adb` 类之后——
上层 drv_screen 只依赖 shell/exec_out/devices 三个原语；测试注入
FakeAdb 即可全测，无需真机。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

_CANDIDATE_ADB = (
    os.environ.get("LAOS_ADB", ""),
    "C:/Users/yaoyue/AppData/Local/Android/Sdk/platform-tools/adb.exe",
)


def _default_adb() -> str:
    for cand in _CANDIDATE_ADB:
        if cand and Path(cand).exists():
            return cand
    return shutil.which("adb") or "adb"


class Adb:
    """adb 交互的唯一收口。测试子类覆盖 `_run` 注入伪造输出。"""

    def __init__(self, adb_path: str | None = None, serial: str | None = None):
        self.adb_path = adb_path or _default_adb()
        self.serial = serial or os.environ.get("LAOS_ADB_SERIAL") or None

    def _base(self) -> list[str]:
        return [self.adb_path] + (["-s", self.serial] if self.serial else [])

    def _run(self, args: list[str], timeout: float = 30.0) -> tuple[int, str]:
        r = subprocess.run(self._base() + args, capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()

    def shell(self, args: list[str], timeout: float = 30.0) -> str:
        rc, out = self._run(["shell"] + args, timeout=timeout)
        if rc != 0:
            raise IOError(f"EIO: adb shell rc={rc}: {out[:200]}")
        return out

    def exec_out(self, args: list[str], timeout: float = 30.0) -> bytes:
        r = subprocess.run(self._base() + args, capture_output=True, timeout=timeout)
        if r.returncode != 0:
            raise IOError(f"EIO: adb exec-out rc={r.returncode}")
        return r.stdout

    def devices(self) -> list[str]:
        rc, out = self._run(["devices"])
        if rc != 0:
            return []
        serials = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serials.append(parts[0])
        return serials


def parse_uiautomator_xml(xml_text: str) -> dict:
    """解析 `uiautomator dump` 的 XML → {"package", "nodes": [...]}。

    节点字段：text/cls/package/resource_id/clickable/bounds[l,t,r,b]。
    空 hierarchy 或非法 XML → ValueError("EINVAL: ...")。
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"EINVAL: bad uiautomator dump: {exc}") from exc
    if root.tag != "hierarchy":
        raise ValueError("EINVAL: bad uiautomator dump: root is not <hierarchy>")

    nodes: list[dict] = []

    def walk(elem, is_root: bool = False) -> None:
        # 跳过合成根 <hierarchy>；容器节点（无 text/clickable/resource-id）是
        # 布局噪音，对 Agent 无意义——只收集"有意义节点"
        meaningful = (elem.get("text") or elem.get("clickable") == "true"
                      or elem.get("resource-id"))
        if not is_root and meaningful:
            b = elem.get("bounds", "")
            m = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b or "")
            bounds = [int(m.group(i)) for i in (1, 2, 3, 4)] if m else [0, 0, 0, 0]
            nodes.append({
                "text": elem.get("text", ""),
                "cls": elem.get("class", ""),
                "package": elem.get("package", ""),
                "resource_id": elem.get("resource-id", ""),
                "clickable": elem.get("clickable") == "true",
                "bounds": bounds,
            })
        for child in elem:
            walk(child)

    walk(root, is_root=True)
    # <hierarchy> 根节点无 package 属性——取第一个带 package 的节点
    package = next((n["package"] for n in nodes if n["package"]), "")
    return {"package": package, "nodes": nodes}


def parse_current_focus(dumpsys_out: str) -> str | None:
    """从 `dumpsys window` 输出提取 mCurrentFocus 的包名；无则 None。"""
    for line in dumpsys_out.splitlines():
        if "mCurrentFocus" in line:
            m = re.search(r"u0 ([\w.]+)/", line)
            if m:
                return m.group(1)
    return None
