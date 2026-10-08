# laos/seccomp.py
"""seccomp —— 用 ctypes 装经典 BPF 过滤器，把驱动的 syscall 收进笼子。

不引入任何第三方依赖：BPF 程序是纯 Python 组装的四元组列表
(code, jt, jf, k)，安装时经 ctypes 调

    prctl(PR_SET_NO_NEW_PRIVS, 1)          # 允许无特权装过滤器
    seccomp(SECCOMP_SET_MODE_FILTER, 0, &fprog)

过滤器随 fork()/execve() 继承 —— 驱动进程装一次，proc.exec 拉起的
孙子进程自动被同一策略覆盖。deny 动作用 SECCOMP_RET_ERRNO|EPERM：
调用方拿到可观察的 EPERM，而不是进程凭空消失。

deny 表是**黑名单**（block-dangerous）：黑名单挡不住未知攻击面，
但它是唯一能与"CPython 解释器自己要用的上百个 syscall"共存的模式；
白名单模式留给未来按驱动画像定制。表里绝不能出现 clone/futex/execve
（glibc 线程与解释器启动的命脉）。
"""

from __future__ import annotations

import ctypes
import platform

# -- 常量（linux/seccomp.h + linux/audit.h + linux/bpf_common.h）-----------
PR_SET_NO_NEW_PRIVS = 38
SECCOMP_SET_MODE_FILTER = 1
SYS_SECCOMP = {"x86_64": 317, "aarch64": 277}  # 各架构 seccomp(2) 的 syscall 号

AUDIT_ARCH_X86_64 = 0xC000003E
SECCOMP_RET_ALLOW = 0x7FFF0000
SECCOMP_RET_ERRNO_EPERM = 0x00050000 | 1  # SECCOMP_RET_ERRNO | EPERM

# 经典 BPF 指令编码（只用到三条）
BPF_LD_W_ABS = 0x20  # BPF_LD | BPF_W | BPF_ABS
BPF_JEQ_K = 0x15     # BPF_JMP | BPF_JEQ | BPF_K
BPF_RET_K = 0x06     # BPF_RET | BPF_K

# seccomp_data 布局：int nr; u32 arch; u64 instruction_pointer; u64 args[6]
_OFFSET_NR = 0
_OFFSET_ARCH = 4

#: 危险 syscall 黑名单（x86_64 号）。装上过滤器后这些调用一律 EPERM。
#: 注意：不含 clone/futex/execve/openat/mmap —— CPython 与 glibc 的命脉。
BLOCKED_X86_64: tuple[tuple[str, int], ...] = (
    ("mount", 165), ("umount2", 166), ("pivot_root", 155), ("chroot", 161),
    ("swapon", 167), ("swapoff", 168), ("reboot", 169), ("sethostname", 170),
    ("iopl", 172), ("ioperm", 173), ("create_module", 174),
    ("init_module", 175), ("finit_module", 313), ("delete_module", 176),
    ("kexec_load", 246), ("kexec_file_load", 320),
    ("open_by_handle_at", 304), ("bpf", 321), ("perf_event_open", 298),
    ("ptrace", 101), ("add_key", 248), ("request_key", 249), ("keyctl", 250),
    ("setns", 308), ("unshare", 272), ("mknod", 133), ("mknodat", 259),
    # 新挂载 API（open_tree/move_mount/fs*）可绕过 legacy mount 拒绝，一并封死；
    # 号码已对照 arch/x86/entry/syscalls/syscall_64.tbl 逐条核对
    ("io_uring_setup", 425), ("open_tree", 428), ("move_mount", 429),
    ("fsopen", 430), ("fsconfig", 431), ("fsmount", 432), ("fspick", 433),
)


def assemble_block_dangerous(machine: str) -> list[tuple[int, int, int, int]] | None:
    """组装 block-dangerous 经典 BPF 程序。

    流程：读 arch -> 不等于 AUDIT_ARCH_X86_64 直接 EPERM
          -> 读 nr -> 逐条与黑名单 JEQ，命中落到 RET EPERM
          -> 兜底 RET ALLOW
    返回 (code, jt, jf, k) 四元组列表；架构不支持返回 None。
    """
    if machine != "x86_64":
        return None
    prog: list[tuple[int, int, int, int]] = [
        (BPF_LD_W_ABS, 0, 0, _OFFSET_ARCH),               # A = seccomp_data.arch
        (BPF_JEQ_K, 1, 0, AUDIT_ARCH_X86_64),             # arch 不符 -> 落到下一条 RET deny
        (BPF_RET_K, 0, 0, SECCOMP_RET_ERRNO_EPERM),
        (BPF_LD_W_ABS, 0, 0, _OFFSET_NR),                 # A = seccomp_data.nr
    ]
    for _name, nr in BLOCKED_X86_64:
        # 命中（jt=0）执行下一条 RET deny；未命中（jf=1）跳过它继续比
        prog.append((BPF_JEQ_K, 0, 1, nr))
        prog.append((BPF_RET_K, 0, 0, SECCOMP_RET_ERRNO_EPERM))
    prog.append((BPF_RET_K, 0, 0, SECCOMP_RET_ALLOW))
    return prog


def install_seccomp(prog: list[tuple[int, int, int, int]]) -> None:
    """在**当前进程**安装过滤器。仅 Linux 调用。

    由 Sandbox.wrap() 的 bootstrap shim 在 unshare(1) 完成 namespace 设置
    **之后**执行（早期的 preexec_fn 设计已废弃：过滤器 deny unshare(2)，
    必须等 namespace 就绪再装）。失败抛 OSError —— shim 里任何异常都会
    让驱动起不来，而不是裸奔 exec（fail-closed）。
    """
    machine = platform.machine()
    sys_seccomp = SYS_SECCOMP.get(machine)
    if sys_seccomp is None:
        raise OSError(f"ENOSYS: seccomp syscall number unknown for {machine}")

    class SockFilter(ctypes.Structure):
        _fields_ = [
            ("code", ctypes.c_uint16),
            ("jt", ctypes.c_uint8),
            ("jf", ctypes.c_uint8),
            ("k", ctypes.c_uint32),
        ]

    class SockFprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_uint16), ("filter", ctypes.POINTER(SockFilter))]

    libc = ctypes.CDLL(None, use_errno=True)
    arr = (SockFilter * len(prog))(
        *[SockFilter(code, jt, jf, k) for code, jt, jf, k in prog]
    )
    fprog = SockFprog(len(prog), arr)

    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_NO_NEW_PRIVS) failed")
    rc = libc.syscall(sys_seccomp, SECCOMP_SET_MODE_FILTER, 0, ctypes.byref(fprog))
    if rc != 0:
        raise OSError(ctypes.get_errno(), "seccomp(SECCOMP_SET_MODE_FILTER) failed")
