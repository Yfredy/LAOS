"""enforcement —— 强制隔离后端层（OSAL，CherryUSB 模式）。

`select()` 是 Kconfig 思想的运行时版：默认按 `sys.platform` 自动选后端；
调用方（laos/sandbox.py）也可显式传 override（来自 LAOS_ENFORCEMENT，
取值 auto|linux|android|stub）。核心内核只依赖 `EnforcementBackend`
契约——换平台 = 换一个后端文件。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .android import AndroidBackend
from .base import EnforcementBackend, IsolationReport
from .linux import LinuxBackend
from .stub import StubBackend

__all__ = [
    "AndroidBackend",
    "EnforcementBackend",
    "IsolationReport",
    "LinuxBackend",
    "StubBackend",
    "select",
]


def _is_android() -> bool:
    """Android/Termux 探测：sys.platform 在 Termux 上是 "linux" 而非 "android"，
    需要 getprop（Android 属性工具，Termux PATH 里有）或 com.termux 前缀识别。"""
    if sys.platform == "android":
        return True
    if sys.platform != "linux":
        return False
    return "com.termux" in sys.prefix.lower() or shutil.which("getprop") is not None


def select(enabled: bool, seccomp_mode: str, workdir: Path,
           override: str | None = None) -> EnforcementBackend:
    """选择并构造（构造即探测）强制隔离后端。

    override 为空或 "auto" 时自动选择（Android/Termux→Android / 其他
    linux→Linux / 其余→Stub）。显式指定的后端若与宿主平台不符：
    尊重选择但降级为 stub 行为，并在 report.reasons 里记录原因
    （Android 后端是 Linux 后端的特化，两宿主相通即拿真后端）；
    非法值按 auto 处理并记录。
    """

    def _auto() -> EnforcementBackend:
        if _is_android():
            return AndroidBackend(enabled, seccomp_mode, workdir)
        if sys.platform == "linux":
            return LinuxBackend(enabled, seccomp_mode, workdir)
        return StubBackend(enabled, seccomp_mode, workdir)

    if not override or override == "auto":
        return _auto()

    if override == "stub":
        return StubBackend(enabled, seccomp_mode, workdir)

    if override in ("linux", "android"):
        if sys.platform == "linux" or _is_android():
            cls = LinuxBackend if override == "linux" else AndroidBackend
            return cls(enabled, seccomp_mode, workdir)
        # 显式指定与宿主平台不符：降级 stub，原因可见
        backend: EnforcementBackend = StubBackend(enabled, seccomp_mode, workdir)
        backend.report.reasons.append(
            f"显式指定 {override} 后端但宿主为 {sys.platform}——降级 stub"
        )
        return backend

    # 非法值：按 auto 处理，但在报告里留痕
    backend = _auto()
    backend.report.reasons.append(
        f"无效的 LAOS_ENFORCEMENT 值 '{override}'，按 auto 处理"
    )
    return backend
