"""Sandbox —— 把 Linux 内核已有的隔离原语包装成 AgentOS 的“保护环”。

设计原则：**不修改内核**。AgentOS 只做编排，真正的强制隔离交给 Linux：

    namespaces (unshare)  -> 每个 Agent 一套 pid/mount/net 视图
    cgroups v2            -> CPU / 内存 / PID 数量上限
    landlock / seccomp    -> 文件系统与 syscall 白名单
    overlayfs / BranchFS  -> 写时复制的工作区

非 Linux 或无特权环境自动降级为“仅能力表检查”，并在 kernel 日志里标记
`isolation=none`，方便在 macOS / Windows 上跑通逻辑。
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .seccomp import BLOCKED_X86_64, assemble_block_dangerous


@dataclass
class IsolationReport:
    level: str  # "full" | "partial" | "none"
    backend: str
    reasons: list[str]
    active: bool = False

    def __str__(self) -> str:
        return f"{self.level} ({self.backend}): {'; '.join(self.reasons) or 'n/a'}"


class Sandbox:
    def __init__(self, workdir: Path | None = None, allow_network: bool = False,
                 enabled: bool = True, seccomp: str | None = None):
        self.workdir = Path(workdir) if workdir else Path(".")
        self.allow_network = allow_network
        self.enabled = enabled
        self.seccomp_mode = seccomp or os.environ.get("LAOS_SECCOMP", "block-dangerous")
        if self.seccomp_mode not in ("off", "block-dangerous"):
            self.seccomp_mode = "off"
        self._seccomp_prog: list[tuple[int, int, int, int]] | None = None
        self.report = self._probe()

    # -- 能力探测 ---------------------------------------------------------
    def _probe(self) -> IsolationReport:
        reasons: list[str] = []
        if platform.system() != "Linux":
            self.seccomp_mode = "off"
            return IsolationReport(
                "none", "host",
                [f"非 Linux 宿主 ({platform.system()})，跳过内核隔离; seccomp 关闭"],
            )

        have_unshare = shutil.which("unshare") is not None
        have_cgroup = Path("/sys/fs/cgroup/cgroup.controllers").exists()
        if have_unshare:
            reasons.append("unshare 可用")
        if have_cgroup:
            reasons.append("cgroup v2 可用")

        # seccomp 与 unshare 无关：没有 namespace 也能装过滤器
        if self.seccomp_mode == "off":
            reasons.append("seccomp=off")
        else:
            prog = assemble_block_dangerous(platform.machine())
            if prog is None:
                self.seccomp_mode = "off"
                reasons.append(f"seccomp 不可用（未知架构 {platform.machine()}）")
            else:
                self._seccomp_prog = prog
                reasons.append(f"seccomp=block-dangerous ({len(BLOCKED_X86_64)} 条 deny)")

        if have_unshare and os.geteuid() == 0:
            return IsolationReport("full", "namespace+cgroup", reasons)
        if have_unshare:
            reasons.append("非 root，仅 user namespace 映射")
            return IsolationReport("partial", "user-namespace", reasons)
        return IsolationReport("none", "host", ["缺少 unshare，仅依赖能力表"])

    # -- 命令包装 ---------------------------------------------------------
    def _seccomp_shim(self) -> list[str]:
        """bootstrap：先装 seccomp 过滤器，再 execvp 真正的命令。

        过滤器 deny 了 unshare(2)，所以安装必须发生在 unshare(1) 完成
        namespace 设置**之后**——这就是为什么不能用 preexec_fn。
        shim 崩溃 = 驱动起不来 = fail-closed。
        """
        repo = Path(__file__).resolve().parents[1]
        shim = (
            "import os, sys; sys.path.insert(0, r'" + str(repo) + "'); "
            "from laos.seccomp import assemble_block_dangerous, install_seccomp; "
            "prog = assemble_block_dangerous(os.uname().machine); "
            "prog is not None and install_seccomp(prog); "
            "os.execvp(sys.argv[1], sys.argv[1:])"
        )
        return [sys.executable, "-c", shim]

    def wrap(self, argv: list[str]) -> list[str]:
        """把一个命令包进隔离环境。

        namespace 前缀（unshare）在最外层；seccomp bootstrap shim 在
        namespace 里、真正命令之前——顺序不可颠倒：过滤器 deny
        unshare(2)，必须等 unshare(1) 干完活再装。非 Linux 或 disabled
        时原样返回（跨平台降级）。
        """
        if not self.enabled or platform.system() != "Linux":
            return list(argv)

        use_ns = self.report.level in ("full", "partial")
        use_shim = (
            self.seccomp_mode == "block-dangerous" and self._seccomp_prog is not None
        )

        out = list(argv)
        if use_shim:
            out = [*self._seccomp_shim(), *out]
        if use_ns:
            ns = [] if self.allow_network else (["--net"] if os.geteuid() == 0 else [])
            prefix = ["unshare", "--mount", "--pid", *ns, "--fork", "--map-root-user"]
            out = [*prefix, "--", *out]
        return out

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
        """创建一个 cgroup v2 叶子节点。无权限时返回 None。"""
        if self.report.level == "none" or platform.system() != "Linux":
            return None
        root = Path("/sys/fs/cgroup")
        leaf = root / "laos" / name
        try:
            leaf.mkdir(parents=True, exist_ok=True)
            (leaf / "cpu.max").write_text(f"{cpu_max} 100000\n")
            (leaf / "memory.max").write_text(f"{mem_max}\n")
            (leaf / "pids.max").write_text("64\n")
            return leaf
        except Exception:
            return None

    @staticmethod
    def attach(cgroup: Path | None, pid: int) -> None:
        if not cgroup:
            return
        try:
            (cgroup / "cgroup.procs").write_text(str(pid))
        except Exception:
            pass


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
