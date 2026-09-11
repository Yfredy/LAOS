# laos/profiling.py
"""eBPF 语义 profiling —— 用 bpftrace 采集驱动进程树的真实 syscall 分布。

审计日志记录的是 Agent **声称**的 tool call（fs.write ...），eBPF 看到
的是驱动进程在内核里**真实**发出的 syscall（openat/write/fstat ...）。
两者对照就是 AgentProf 思路里最基础的系统级真值：Agent 说它只读，
内核里却出现了 write —— 谎言在 syscall 层无处遁形。

实现是**集成**而不是依赖：laos 不绑定 eBPF 库，只在检测到
`bpftrace` 二进制（且 Linux + root）时拉起一次性 one-liner 会话；
不可用时 start() 返回 False 并把原因写进审计，绝不抛错。
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import signal
import subprocess


class BpfTraceProfiler:
    """一次 profile 窗口 = 一个 bpftrace 子进程。

    用法：start()（Agent 开跑前） -> ... 窗口内跑任务 ... -> stop()
    返回 {probe 名: 次数}，如 {"syscalls:sys_enter_openat": 17, ...}。
    """

    _PROBE_RE = re.compile(r"@\[([^\]]+)\]:\s*(\d+)")

    def __init__(self, pids: list[int]):
        self.pids = [int(p) for p in pids]
        self.reason: str = ""
        self._proc: subprocess.Popen | None = None

    # -- 能力探测 ---------------------------------------------------------
    def available(self) -> tuple[bool, str]:
        if platform.system() != "Linux":
            return False, f"bpftrace 仅 Linux（当前 {platform.system()}）"
        if shutil.which("bpftrace") is None:
            return False, "未安装 bpftrace"
        if os.geteuid() != 0:
            return False, "bpftrace 需要 root（sudo 运行 laosd 或放宽 perf_event_paranoid）"
        return True, "bpftrace"

    # -- 程序生成（纯函数，方便测试）---------------------------------------
    def script(self) -> str:
        """驱动 pid 及其直接子进程（proc.exec 的孙子，ppid 命中）全覆盖。"""
        conds = " || ".join(
            [f"pid == {p}" for p in self.pids] + [f"ppid == {p}" for p in self.pids]
        )
        # interval 周期打印快照；SIGINT 退出时 bpftrace 还会打印残余聚合，
        # parse() 对重复探针做累加，两路输出都吃
        return (
            f"syscalls:sys_enter_* /{conds}/ {{ @[probe] = count(); }} "
            f"interval:s:2 {{ print(@); clear(@); }}"
        )

    @classmethod
    def parse(cls, text: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for m in cls._PROBE_RE.finditer(text):
            out[m.group(1)] = out.get(m.group(1), 0) + int(m.group(2))
        return out

    # -- 生命周期 ---------------------------------------------------------
    def start(self) -> bool:
        ok, why = self.available()
        self.reason = why
        if not ok:
            return False
        self._proc = subprocess.Popen(
            ["bpftrace", "-e", self.script()],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return True

    def stop(self) -> dict[str, int]:
        if self._proc is None:
            return {}
        try:
            self._proc.send_signal(signal.SIGINT)  # bpftrace 优雅退出并打印聚合
            out, _ = self._proc.communicate(timeout=10)
        except Exception:
            self._proc.kill()
            out, _ = self._proc.communicate()
            self._proc = None
            return {}
        self._proc = None
        return self.parse(out or "")
