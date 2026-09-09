"""enforcement —— 强制隔离后端层（OSAL，CherryUSB 模式）。

`select()` 是 Kconfig 思想的运行时版：默认按 `sys.platform` 自动选后端；
调用方（laos/sandbox.py）也可显式传 override（来自 LAOS_ENFORCEMENT）。
核心内核只依赖 `EnforcementBackend` 契约——换平台 = 换一个后端文件。
"""

from __future__ import annotations

import sys
from pathlib import Path

from .base import EnforcementBackend, IsolationReport
from .linux import LinuxBackend
from .stub import StubBackend

__all__ = [
    "EnforcementBackend",
    "IsolationReport",
    "LinuxBackend",
    "StubBackend",
    "select",
]


def select(enabled: bool, seccomp_mode: str, workdir: Path,
           override: str | None = None) -> EnforcementBackend:
    """选择并构造（构造即探测）强制隔离后端。

    override 为空或 "auto" 时按 `sys.platform` 自动选择；
    显式指定的后端若与宿主平台不符：尊重选择但降级为 stub 行为，
    并在 report.reasons 里记录原因；非法值按 auto 处理并记录。
    """
    notes: list[str] = []

    def _auto() -> EnforcementBackend:
        if sys.platform == "linux":
            return LinuxBackend(enabled, seccomp_mode, workdir)
        return StubBackend(enabled, seccomp_mode, workdir)

    if not override or override == "auto":
        return _auto()
    if override == "stub":
        return StubBackend(enabled, seccomp_mode, workdir)
    if override == "linux":
        if sys.platform == "linux":
            return LinuxBackend(enabled, seccomp_mode, workdir)
    else:
        # 非法值：按 auto 处理，但在报告里留痕
        backend = _auto()
        backend.report.reasons.append(
            f"无效的 LAOS_ENFORCEMENT 值 '{override}'，按 auto 处理"
        )
        return backend

    # 显式指定与宿主平台不符：降级 stub，原因可见
    backend: EnforcementBackend = StubBackend(enabled, seccomp_mode, workdir)
    backend.report.reasons.append(
        f"显式指定 {override} 后端但宿主为 {sys.platform}——降级 stub"
    )
    return backend
