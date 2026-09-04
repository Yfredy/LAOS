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
        # [1] 校验 AUDIT_ARCH_X86_64：匹配（jt=1）跳过下一条 deny RET；
        #     不匹配则**落入**下一条 RET EPERM（fall-through，非跳转）
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

    def test_blocked_nr_mapping_matches_linux_table(self):
        # 对照 arch/x86/entry/syscalls/syscall_64.tbl 逐条核对过的映射。
        # 曾经写错：pivot_root 被误标 218（实为 set_tid_address，glibc 启动
        # 路径，EPERM 会弄死驱动启动）、finit_module 被误标 273（实为
        # set_robust_list，glibc 线程创建基础设施；273 是它的 aarch64 号）。
        by_name = {name: nr for name, nr in BLOCKED_X86_64}
        self.assertEqual(by_name.get("pivot_root"), 155)
        self.assertEqual(by_name.get("finit_module"), 313)
        blocked = set(by_name.values())
        # 这两个号是 glibc 命脉，绝不能进黑名单
        self.assertNotIn(218, blocked)  # set_tid_address
        self.assertNotIn(273, blocked)  # set_robust_list


if __name__ == "__main__":
    unittest.main(verbosity=2)
