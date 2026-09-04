# tests/test_seccomp.py
"""seccomp BPF 组装器测试（组装是纯 Python，全平台可跑）。

    python -m unittest tests.test_seccomp -v

本任务只写 TestAssemble（自洽，不依赖 Task 2 的 Sandbox 改动）；
TestPopenKwargs / TestSeccompLinux 在 Task 2 Step 1 追加。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.seccomp import (  # noqa: E402
    AUDIT_ARCH_X86_64,
    SECCOMP_RET_ALLOW,
    SECCOMP_RET_ERRNO_EPERM,
    BLOCKED_X86_64,
    assemble_block_dangerous,
)

BPF_LD_W_ABS = 0x20
BPF_JEQ_K = 0x15
BPF_RET_K = 0x06


class TestAssemble(unittest.TestCase):
    def test_program_shape(self):
        prog = assemble_block_dangerous("x86_64")
        self.assertIsNotNone(prog)
        # [0] 读 seccomp_data.arch（偏移 4）
        self.assertEqual(prog[0], (BPF_LD_W_ABS, 0, 0, 4))
        # [1] 校验 AUDIT_ARCH_X86_64，不匹配则跳去 deny
        self.assertEqual(prog[1], (BPF_JEQ_K, 1, 0, AUDIT_ARCH_X86_64))
        # [2] 错误架构 -> ERRNO|EPERM
        self.assertEqual(prog[2], (BPF_RET_K, 0, 0, SECCOMP_RET_ERRNO_EPERM))
        # 末尾放行
        self.assertEqual(prog[-1], (BPF_RET_K, 0, 0, SECCOMP_RET_ALLOW))

    def test_every_blocked_nr_has_jeq_and_deny(self):
        prog = assemble_block_dangerous("x86_64")
        jeq_ks = {k for code, _jt, _jf, k in prog if code == BPF_JEQ_K}
        for name, nr in BLOCKED_X86_64:
            self.assertIn(nr, jeq_ks, f"{name}({nr}) 没有对应的 JEQ 指令")
        deny_rets = {k for code, _jt, _jf, k in prog if code == BPF_RET_K}
        self.assertIn(SECCOMP_RET_ERRNO_EPERM, deny_rets)

    def test_unsupported_arch_returns_none(self):
        self.assertIsNone(assemble_block_dangerous("armv7l"))

    def test_blocklist_never_blocks_thread_essentials(self):
        blocked = {nr for _name, nr in BLOCKED_X86_64}
        # clone=56（glibc 线程回退目标）、futex=202、execve=59、openat=257
        for essential in (56, 202, 59, 257):
            self.assertNotIn(essential, blocked)


if __name__ == "__main__":
    unittest.main(verbosity=2)
