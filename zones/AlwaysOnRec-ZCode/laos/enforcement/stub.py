"""StubBackend —— 非 Linux 宿主（macOS / Windows）降级后端。

不做任何内核隔离：wrap 原样返回、cgroup 恒 None，仅依赖上层的
能力表检查，保证 AgentOS 逻辑在任意平台跑通。行为与原
Sandbox 非 Linux 分支逐字一致。
"""

from __future__ import annotations

import platform

from .base import EnforcementBackend, IsolationReport


class StubBackend(EnforcementBackend):
    name = "stub"

    def probe(self) -> IsolationReport:
        # 与原 Sandbox._probe 非 Linux 分支一致：seccomp 强制关闭
        self.seccomp_mode = "off"
        return IsolationReport(
            "none", "host",
            [f"非 Linux 宿主 ({platform.system()})，跳过内核隔离; seccomp 关闭"],
        )

    def wrap(self, argv: list[str]) -> list[str]:
        """跨平台降级：原样返回。"""
        return list(argv)
