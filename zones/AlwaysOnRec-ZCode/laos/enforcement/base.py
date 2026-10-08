"""EnforcementBackend —— 强制隔离后端契约（OSAL，CherryUSB 模式）。

核心内核（kernel.py / Sandbox）只依赖这一小撮原语：
"换平台 = 换一个后端文件"，调用方零改动。dsp-override 式的
select() 工厂（见包 __init__）负责在运行时挑后端。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class IsolationReport:
    level: str  # "full" | "partial" | "none"
    backend: str
    reasons: list[str]
    active: bool = False

    def __str__(self) -> str:
        return f"{self.level} ({self.backend}): {'; '.join(self.reasons) or 'n/a'}"


class EnforcementBackend:
    """强制隔离后端契约：能力探测 / 命令包装 / cgroup 管理。

    构造即探测：`__init__` 末尾调用 `self.probe()`，之后
    `report` / `seccomp_mode` / `_seccomp_prog` 三者随之确定
    （probe 允许回写 seccomp_mode 与 _seccomp_prog，与原
    Sandbox._probe 语义一致）。
    """

    name = "base"

    def __init__(self, enabled: bool, seccomp_mode: str, workdir: Path):
        self.enabled = enabled
        self.seccomp_mode = seccomp_mode
        self.workdir = workdir
        # 是否保留 net namespace：由 Sandbox 透传（不在构造签名里，保持契约最小）
        self.allow_network = False
        self._seccomp_prog: list[tuple[int, int, int, int]] | None = None
        self.report: IsolationReport = self.probe()

    # -- 能力探测 ---------------------------------------------------------
    def probe(self) -> IsolationReport:
        raise NotImplementedError

    # -- 命令包装 ---------------------------------------------------------
    def wrap(self, argv: list[str]) -> list[str]:
        """把一个命令包进隔离环境。默认降级：原样返回。"""
        return list(argv)

    def popen_kwargs(self) -> dict:
        """subprocess.Popen 的额外参数（如 preexec_fn）；默认无。"""
        return {}

    def estimate(self) -> IsolationReport:
        """当前强制隔离状态快照：active 表示内核原语真正生效。"""
        if not self.enabled:
            return IsolationReport(
                "none", "host", ["sandbox disabled，仅依赖能力表"], active=False
            )
        return IsolationReport(
            level=self.report.level,
            backend=self.report.backend,
            reasons=list(self.report.reasons),
            active=self.report.level in ("full", "partial"),
        )

    # -- cgroup -----------------------------------------------------------
    def make_cgroup(self, name: str, cpu_max: str = "50", mem_max: str = "512M") -> Path | None:
        """创建一个 cgroup v2 叶子节点。无权限/不支持时返回 None。"""
        return None

    @staticmethod
    def attach(cgroup: Path | None, pid: int) -> None:
        if not cgroup:
            return
        try:
            (cgroup / "cgroup.procs").write_text(str(pid))
        except Exception:
            pass
