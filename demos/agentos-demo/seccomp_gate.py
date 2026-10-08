#!/usr/bin/env python3
"""seccomp_gate —— agent 进程的自装强制层（demo 版）。

复刻自 laos/seccomp.py（Apache-2.0 同仓）的 prctl+seccomp(2) 直调模式，
缩小为两条规则：execve/execveat 与 socket 族返回 EPERM，其余放行。
装在 agent.py 进程内——演示"能力表管得到许可，seccomp 管得到物理"：
即使 kernel 有 bug 放行了越权 op，agent 进程也生不出新进程/网络连接。
"""
from __future__ import annotations

import ctypes
import ctypes.util
import platform
import struct

PR_SET_NO_NEW_PRIVS = 38
SECCOMP_SET_MODE_FILTER = 1
SECCOMP_RET_ALLOW = 0x7FFF0000
SECCOMP_RET_ERRNO = 0x00050000
EPERM = 1

# linux/audit.h：x86_64 AUDIT_ARCH_X86_64 = 0xC000003E
AUDIT_ARCH_X86_64 = 0xC000003E

# 经典 BPF 指令编码（laos/seccomp.py 同款三条）
BPF_LD_W_ABS = 0x20   # BPF_LD | BPF_W | BPF_ABS
BPF_JEQ_K = 0x15      # BPF_JMP | BPF_JEQ | BPF_K
BPF_RET_K = 0x06      # BPF_RET | BPF_K

# seccomp_data 布局：int nr; u32 arch; u64 instruction_pointer; u64 args[6]
_OFFSET_NR = 0
_OFFSET_ARCH = 4

# syscall 号（x86_64）：execve=59, execveat=322, socket=41, socketpair=53,
# connect=42 —— aarch64 号不同，非 x86_64 直接不装（demo 主场 WSL x86_64）。
BLOCKED = {59: "execve", 322: "execveat", 41: "socket", 53: "socketpair", 42: "connect"}

_DENY = SECCOMP_RET_ERRNO | EPERM


def _filter() -> bytes:
    """手搓 BPF 程序：load arch → 校验 → load nr → 逐条比对 → 默认 ALLOW。

    指令流复刻 laos/seccomp.py 的交错布局：每条 JEQ 紧跟自己的 RET
    （jt=0 命中落 deny、jf=1 未命中跳过继续比），跳距只有 0/1——
    从构造上排除"集中 deny 块"需要手算偏移的 off-by-one 风险。
    """
    prog: list[tuple[int, int, int, int]] = [
        (BPF_LD_W_ABS, 0, 0, _OFFSET_ARCH),          # A = seccomp_data.arch
        (BPF_JEQ_K, 1, 0, AUDIT_ARCH_X86_64),        # arch 不符 → 落到下一条 deny
        (BPF_RET_K, 0, 0, _DENY),
        (BPF_LD_W_ABS, 0, 0, _OFFSET_NR),            # A = seccomp_data.nr
    ]
    for nr in BLOCKED:
        prog += [
            (BPF_JEQ_K, 0, 1, nr),                   # 命中 → 下一条 RET deny
            (BPF_RET_K, 0, 0, _DENY),
        ]
    prog.append((BPF_RET_K, 0, 0, SECCOMP_RET_ALLOW))
    return b"".join(struct.pack("<HBBI", *insn) for insn in prog)


def install() -> bool:
    """装 filter；成功 True，环境不支持（非 Linux/非 x86_64）False 不炸。"""
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        return False
    libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        return False
    prog = _filter()

    class Flock(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]

    flock = Flock(len(prog) // 8, ctypes.cast(prog, ctypes.c_void_p))
    return libc.syscall(317, SECCOMP_SET_MODE_FILTER, 0, ctypes.byref(flock)) == 0
