"""Sandbox —— 把内核强制隔离原语包装成 AgentOS 的“保护环”。

设计原则：**不修改内核**。AgentOS 只做编排，真正的强制隔离交给
enforcement 后端层（laos/enforcement/，CherryUSB OSAL 模式——
换平台 = 换一个后端文件）：

    namespaces (unshare)  -> 每个 Agent 一套 pid/mount/net 视图
    cgroups v2            -> CPU / 内存 / PID 数量上限
    landlock / seccomp    -> 文件系统与 syscall 白名单
    overlayfs / BranchFS  -> 写时复制的工作区

非 Linux 或无特权环境自动降级为“仅能力表检查”，并在 kernel 日志里标记
`isolation=none`，方便在 macOS / Windows 上跑通逻辑。

本模块是薄委托层：公共 API（Sandbox / PathJail / IsolationReport）
与拆分前逐字兼容，kernel / drivers / tests 的调用点零改动。
"""

from __future__ import annotations

import os
from pathlib import Path

from . import enforcement
from .enforcement.base import EnforcementBackend, IsolationReport


class Sandbox:
    def __init__(self, workdir: Path | None = None, allow_network: bool = False,
                 enabled: bool = True, seccomp: str | None = None):
        self.workdir = Path(workdir) if workdir else Path(".")
        self.allow_network = allow_network
        self.enabled = enabled
        seccomp_mode = seccomp or os.environ.get("LAOS_SECCOMP", "block-dangerous")
        if seccomp_mode not in ("off", "block-dangerous"):
            seccomp_mode = "off"
        self._backend = enforcement.select(enabled, seccomp_mode, self.workdir)
        self._backend.allow_network = allow_network
        self.report = self._backend.report

    # -- 委托后端（probe 已在 select 构造时完成）---------------------------
    @property
    def seccomp_mode(self) -> str:
        return self._backend.seccomp_mode

    @seccomp_mode.setter
    def seccomp_mode(self, value: str) -> None:
        self._backend.seccomp_mode = value

    @property
    def _seccomp_prog(self) -> list[tuple[int, int, int, int]] | None:
        return self._backend._seccomp_prog

    # -- 命令包装 ---------------------------------------------------------
    def wrap(self, argv: list[str]) -> list[str]:
        """把一个命令包进隔离环境（委托后端）。"""
        return self._backend.wrap(argv)

    def estimate(self) -> IsolationReport:
        """当前强制隔离状态快照：active 表示内核原语真正生效。"""
        return self._backend.estimate()

    # -- cgroup -----------------------------------------------------------
    def make_cgroup(self, name: str, cpu_max: str = "50", mem_max: str = "512M") -> Path | None:
        """创建一个 cgroup v2 叶子节点。无权限时返回 None。"""
        return self._backend.make_cgroup(name, cpu_max, mem_max)

    @staticmethod
    def attach(cgroup: Path | None, pid: int) -> None:
        EnforcementBackend.attach(cgroup, pid)


# --------------------------------------------------------------------------
# 路径越狱防护：无论隔离是否生效，内核这一层都要挡住
# --------------------------------------------------------------------------
class PathJail:
    """把驱动的可见根目录限制在 jail 内，等价于 chroot 的语义。"""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, virt_path: str) -> Path:
        p = (self.root / virt_path.lstrip("/")).resolve()
        if not (p == self.root or self.root in p.parents):
            raise PermissionError(f"EACCES: path escapes jail: {virt_path}")
        return p

    def unresolve(self, real_path: Path) -> str:
        return "/" + str(Path(real_path).resolve().relative_to(self.root)).replace("\\", "/")
