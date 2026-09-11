"""AndroidBackend —— Termux / Android 上的强制隔离后端。

内核就是 Linux：探测与 wrap 逻辑完整继承 LinuxBackend，但探测报告
叠加 Termux 的已知限制，让"隔离为什么缩水"在日志里一眼可见。

Termux 降级矩阵（典型环境，待实测校准——docs/research §五.4）：

    user namespace   通常**不可用** —— Android W^X / seccomp 策略禁止
                     非特权 unshare(2)；社区主流替代是 proot（用户态，
                     非强制隔离，只防误伤不防恶意）
    seccomp          内核支持（prctl(PR_SET_NO_NEW_PRIVS) +
                     SECCOMP_SET_MODE_FILTER）；但黑名单表目前只有
                     x86_64，aarch64 组装为 None → 自动 seccomp=off
    cgroup v2        通常**不可写**（/sys/fs/cgroup 只读或无权限）
                     → make_cgroup 返回 None
    unshare(1)       Termux 源里无包；即便自编译也会 EPERM

即：Termux 上现实的强制力 = 能力表检查 + （未来 aarch64 表落地后的）
seccomp；namespace/cgroup 两项通常缺席。
"""

from __future__ import annotations

from .base import IsolationReport
from .linux import LinuxBackend


class AndroidBackend(LinuxBackend):
    """Linux 探测 + Termux 限制说明：wrap 同 Linux（proot 另见 research）。"""

    name = "android"

    def probe(self) -> IsolationReport:
        report = super().probe()
        report.reasons.append(
            "Termux: user namespace 受 W^X 策略限制，unshare 可能不可用"
            "——实测矩阵见 docs/research §五.4"
        )
        return report
