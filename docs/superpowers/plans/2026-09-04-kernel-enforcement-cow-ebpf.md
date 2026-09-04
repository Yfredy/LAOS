# 强制层演进：seccomp + COW 分支 + eBPF profiling 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 README §6 "还差什么" 里三个 C/Rust 方向落进 laos：① 把 seccomp BPF 过滤器与 cgroup 真正接入驱动/proc.exec 启动路径 ② 用 hardlink COW 把分支 fork 的数据拷贝降到零（BranchFS 的用户态等价物）③ 用 bpftrace 集成 eBPF 语义 profiling，让审计日志里的"声称 syscall"能和内核里的"真实 syscall"对照。

**Architecture:** 三部分相互独立、可单独执行，都遵守"不修改内核、强制力来自 Linux 已有原语"的项目原则。Part A 用 ctypes 调 `prctl(PR_SET_NO_NEW_PRIVS)` + `seccomp(SECCOMP_SET_MODE_FILTER)` 装经典 BPF 过滤器（零第三方依赖），经 `subprocess.Popen(preexec_fn=...)` 注入驱动进程——seccomp 过滤器随 fork/execve 继承，所以 `proc.exec` 的孙子进程自动被同一策略覆盖，一行驱动代码都不用改。Part B 用硬链接共享数据块实现 COW fork（fork = 只复制目录项，零字节拷贝），配套 `laos/cow.py` 写时断链原语（temp + `os.replace`，绝不原地改写共享 inode），commit 改用 CoW 写避免破坏兄弟分支。Part C 用 `bpftrace -e 'syscalls:sys_enter_*'` 通配探针按 pid/ppid 采集驱动进程树的真实 syscall 分布，落盘 `audit.jsonl` 并提供 `laosctl prof` 回放。三者在非 Linux / 无特权环境一律降级并在报告中说明，与项目既有哲学一致。

**Tech Stack:** Python 3.10+ 标准库（`ctypes`/`subprocess`/`unittest`），零第三方依赖。seccomp 用经典 BPF（BPF_LD/JEQ/RET 手工组装）；分支用 `os.link` + `os.replace`；profiling 用外部 `bpftrace` 二进制（可选，缺席自动降级）。全平台测试：seccomp 组装、COW、解析器均为纯 Python，Windows 上可测；真正的内核行为（seccomp 拦截、bpftrace）用 `skipUnless(Linux)` 集成测试。

**Spec:** `README.md` §6（路线图，本计划实现其前两行 + eBPF 部分）；前序计划 `docs/superpowers/plans/2026-08-31-laos-aios-mechanisms.md`（调度/校验/不可逆预算已落地，本计划不碰这些）。

## Global Constraints

- 零第三方依赖，禁止引入 fusepy/pyfuse3/bcc 等任何 pip 包；内核交互只走 `ctypes` 标准库与既有命令行工具（`unshare`/`bpftrace`）。
- **不修改内核**：seccomp 只装过滤器，不写内核模块；分支不用 FUSE（见下"范围外"）。
- 非 Linux / 无特权环境必须自动降级且不抛错：seccomp 关闭、cgroup 返回 None、profiler 报告 unavailable 原因。
- 不破坏既有 46 项测试（`python -m unittest discover -s tests`，基线已于 2026-09-04 验证全绿）；新增测试放独立文件 `tests/test_seccomp.py`、`tests/test_cow.py`、`tests/test_profiling.py`，分支相关新增用例加进 `tests/test_laos.py` 的 `TestBranch`。
- errno 原样透传；新增失败用 `EINVAL`（参数）/ `EACCES`（越权）/ `ENOSYS`（平台不支持）。
- 本机（Windows）可用的解释器：`C:\Users\yaoyue\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`。**不要用 `py` 启动器**（它指向不存在的 `C:\Python311\python.exe`），`python` 是 Microsoft Store 占位符（无输出）。下文统一用 `$PY` 指代；Linux 上用 `python3`。
- 每次 commit 一个 task，消息形如 `feat(laos): <task 名>`。
- seccomp 过滤器安装失败必须 fail-closed（让 Popen 抛错、内核启动失败），绝不允许静默裸奔。

### 范围外（明确不做）

- **FUSE BranchFS 守护进程**：README §6 提到"接 BranchFS（FUSE）**或 overlayfs**"。本计划选 hardlink COW 而不是 FUSE/overlayfs，理由：① 目标是"fork O(1) 语义"（零数据拷贝 + 写时复制 + commit ∝ 变更量），hardlink COW 在用户态即可达成，fork 只复制目录项、数据块全共享；② 裸写 /dev/fuse 协议或绑定 libfuse 是 ~800 行的独立子系统且必须引入第三方依赖或 setuid helper；③ overlayfs 非特权挂载依赖发行版策略（Debian 禁止 userns overlay），且 whiteout 的 mknod 语义与跨 mount-namespace 的 commit 合并把复杂度转移到了语义层。论文（arXiv:2602.08199）自己强调"非 root 可用"——hardlink COW 是这一精神下零依赖的等价实现。FUSE 仍是长期项，接口上 `BranchContext` 保持不变即可日后替换。

---

## 现状关键事实（执行者必读）

- `laos/kernel.py:147-157` `load_driver()` **已经**在用 `self.sandbox.wrap(argv)` 包驱动启动命令（README §6 第一行"未接入"已过时）；缺的是 seccomp 过滤器和 cgroup 挂接。
- `laos/sandbox.py:63-72` `Sandbox.wrap()` 只是给 argv 前缀 `unshare --mount --pid --fork --map-root-user`；`make_cgroup()`/`attach()`（`sandbox.py:88-110`）实现了但**从未被调用**。
- `laos/mcp.py:203-227` `MCPClient.start()` 用 `subprocess.Popen` 拉驱动，不支持额外 Popen 参数。
- `drivers/drv_proc.py:74-102` `proc_exec` 用 `subprocess.run(cmd, shell=True)`，无任何内核级约束（只有白名单 + 字符串黑名单）。
- `laos/branch.py:57-71` `fork()` 用 `shutil.copytree`（全量数据拷贝）；`commit()`（`branch.py:142-147`）用 `shutil.copy2` 覆盖父分支文件——**如果父分支文件被兄弟分支硬链接共享，copy2 会原地截断共享 inode**，这是 Part B 必须修掉的坑。
- `bin/laosd.py:48-60` `boot_kernel()` 加载 3 个驱动；`bin/laosctl.py:107-119` 子命令表只有 `audit/trace/denied/top/ps`。
- 测试基线 46 项全绿（README 写的 26 已过时，C3 任务修正）。

---

### Task 0: git 基线

**Files:**
- Create: `.gitignore`

**Interfaces:**
- Produces: 一个干净的 git 仓库，基线 commit 包含当前全部 46 项测试。

- [ ] **Step 1: 初始化仓库并验证测试基线**

```bash
cd C:/Users/yaoyue/CodeBuddy/Claw/laos
git init
```

- [ ] **Step 2: 写 .gitignore**

```gitignore
__pycache__/
*.pyc
var/
fsroot/
*.log
```

- [ ] **Step 3: 跑全量测试确认基线**

Run: `"$PY" -m unittest discover -s tests 2>&1 | tail -3`（Linux：`python3 -m unittest discover -s tests`）
Expected: `Ran 46 tests ... OK`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore(laos): baseline before kernel-enforcement/cow/ebpf work"
```

---

### Task 1: seccomp BPF 组装器（纯 Python，全平台可测）

**Files:**
- Create: `laos/seccomp.py`
- Test: `tests/test_seccomp.py`

**Interfaces:**
- Produces:
  - `BLOCKED_X86_64: tuple[tuple[str, int], ...]` —— 危险 syscall 名→号表
  - `assemble_block_dangerous(machine: str) -> list[tuple[int, int, int, int]] | None` —— 返回经典 BPF 程序 `(code, jt, jf, k)` 四元组列表；不支持的架构返回 `None`
  - `install_seccomp(prog: list[tuple[int, int, int, int]]) -> None` —— ctypes 安装，失败抛 `OSError`（仅 Linux 调用）
  - 常量 `AUDIT_ARCH_X86_64 = 0xC000003E`、`SECCOMP_RET_ALLOW = 0x7FFF0000`、`SECCOMP_RET_ERRNO_EPERM = 0x00050000 | 1`
- Consumes: 无（本任务独立，Task 2 消费它）。

**设计要点（写给实现者）：** 经典 BPF 过滤器校验 `seccomp_data.arch`（偏移 4）后加载 `nr`（偏移 0），命中 deny 表则返回 `SECCOMP_RET_ERRNO|EPERM`（可观察、不杀进程），否则 `SECCOMP_RET_ALLOW`。deny 表**绝不能含 `clone`/`clone3`**——glibc 的线程创建（asyncio 的 `to_thread` 依赖它）走 clone3，EPERM 不会触发 ENOSYS 回退，会直接弄死驱动；同理不能碰 `read/write/openat/mmap/futex/execve`。`unshare`/`setns` 在 deny 表里（驱动自己不需要再造 namespace）。

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m unittest tests.test_seccomp -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'laos.seccomp'`

- [ ] **Step 3: 实现 `laos/seccomp.py`**

```python
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
    ("mount", 165), ("umount2", 166), ("pivot_root", 218), ("chroot", 161),
    ("swapon", 167), ("swapoff", 168), ("reboot", 169), ("sethostname", 170),
    ("iopl", 172), ("ioperm", 173), ("create_module", 174),
    ("init_module", 175), ("finit_module", 273), ("delete_module", 176),
    ("kexec_load", 246), ("kexec_file_load", 320),
    ("open_by_handle_at", 304), ("bpf", 321), ("perf_event_open", 298),
    ("ptrace", 101), ("add_key", 248), ("request_key", 249), ("keyctl", 250),
    ("setns", 308), ("unshare", 272), ("mknod", 133), ("mknodat", 259),
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
    """在**当前进程**安装过滤器。仅 Linux 调用（在 preexec_fn 里跑）。

    失败抛 OSError —— 调用方（preexec_fn）必须让它炸出去：
    过滤器装不上就宁可进程起不来，也不能裸奔（fail-closed）。
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `"$PY" -m unittest tests.test_seccomp -v`
Expected: `Ran 4 tests ... OK`（`TestPopenKwargs`/`TestSeccompLinux` 尚未写入，Task 2 Step 1 追加）

- [ ] **Step 5: Commit**

```bash
git add laos/seccomp.py tests/test_seccomp.py
git commit -m "feat(laos): seccomp BPF assembler (pure-python, zero-dep)"
```

---

### Task 2: Sandbox 接线 —— popen_kwargs 注入 seccomp + cgroup 挂接 + 驱动 spawn

**Files:**
- Modify: `laos/sandbox.py`（`Sandbox.__init__`/`_probe`/新增 `popen_kwargs()`）
- Modify: `laos/mcp.py:203-227`（`MCPClient` 接受 `popen_kwargs`）
- Modify: `laos/kernel.py:147-157`（`load_driver` 传 `popen_kwargs` + 启动后挂 cgroup）
- Test: `tests/test_seccomp.py`（追加 `TestPopenKwargs` 与 `TestSeccompLinux` 两个类）

**Interfaces:**
- Consumes: Task 1 的 `assemble_block_dangerous`/`install_seccomp`/`BLOCKED_X86_64`。
- Produces:
  - `Sandbox.__init__(workdir=None, allow_network=False, enabled=True, seccomp: str | None = None)` —— `seccomp` 取 `"off"`/`"block-dangerous"`，None 时读 `LAOS_SECCOMP` 环境变量（默认 `block-dangerous`），非法值按 `off` 处理
  - `Sandbox.popen_kwargs() -> dict` —— Linux 且启用且程序组装成功时 `{"preexec_fn": <callable>}`，否则 `{}`
  - `Sandbox.seccomp_mode: str`、`Sandbox._seccomp_prog: list | None`（供报告与测试断言）
  - `MCPClient.__init__(name, argv, env=None, popen_kwargs: dict | None = None)`
  - `AgentKernel.load_driver` 审计记录新增 `"cgroup": str|None` 字段

**设计要点：** seccomp 安装与 `unshare` 无关（没有 unshare 也能装），所以 `popen_kwargs()` 只看平台/开关/程序三件事，不看 `report.level`。`preexec_fn` 里只做一件事：`install_seccomp(prog)`，抛错让它炸（fail-closed）。

- [ ] **Step 1: 在 tests/test_seccomp.py 追加两个测试类**

追加到 `TestAssemble` 类之后、`if __name__` 之前（文件顶部 import 区需补 `errno`、`os`、`platform`、`subprocess`、`sys`、`tempfile`——`sys`/`unittest`/`Path` 已有）：

```python
class TestPopenKwargs(unittest.TestCase):
    def test_off_is_empty_everywhere(self):
        from laos.sandbox import Sandbox
        self.assertEqual(Sandbox(enabled=True, seccomp="off").popen_kwargs(), {})

    @unittest.skipUnless(platform.system() == "Linux", "seccomp 仅 Linux")
    def test_linux_has_preexec(self):
        from laos.sandbox import Sandbox
        kw = Sandbox(enabled=True, seccomp="block-dangerous").popen_kwargs()
        self.assertIn("preexec_fn", kw)


class TestSeccompLinux(unittest.TestCase):
    """真实内核行为：装上过滤器后 swapon 必须得到 EPERM，正常代码不受影响。"""

    @unittest.skipUnless(platform.system() == "Linux", "seccomp 仅 Linux")
    def test_blocks_swapon_with_eperm(self):
        from laos.sandbox import Sandbox
        sb = Sandbox(enabled=True, seccomp="block-dangerous")
        kw = sb.popen_kwargs()
        if "preexec_fn" not in kw:
            self.skipTest("当前环境（无 unshare/未知架构）seccomp 未启用")
        # swapon = 167：驱动与普通 Python 都不需要它
        code = (
            "import ctypes\n"
            "libc = ctypes.CDLL(None, use_errno=True)\n"
            "r = libc.syscall(167, b'/tmp/laos-swapon-probe', 0)\n"
            "raise SystemExit(0 if r == 0 else ctypes.get_errno())\n"
        )
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(
                [sys.executable, "-c", code], capture_output=True,
                cwd=td, timeout=15, **kw,
            )
        self.assertEqual(r.returncode, errno.EPERM)

    @unittest.skipUnless(platform.system() == "Linux", "seccomp 仅 Linux")
    def test_normal_code_survives_filter(self):
        from laos.sandbox import Sandbox
        sb = Sandbox(enabled=True, seccomp="block-dangerous")
        kw = sb.popen_kwargs()
        if "preexec_fn" not in kw:
            self.skipTest("当前环境 seccomp 未启用")
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(
                [sys.executable, "-c",
                 "import os; os.mkdir('d'); open('d/f','w').write('x'); print('ok')"],
                capture_output=True, text=True, cwd=td, timeout=15, **kw,
            )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ok", r.stdout)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m unittest tests.test_seccomp -v`
Expected: FAIL —— `TypeError: __init__() got an unexpected keyword argument 'seccomp'`

- [ ] **Step 3: 修改 `laos/sandbox.py`**

文件顶部 import 增加：

```python
from .seccomp import BLOCKED_X86_64, assemble_block_dangerous, install_seccomp
```

`Sandbox.__init__`（现 `sandbox.py:36-41`）替换为：

```python
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
```

`_probe`（现 `sandbox.py:44-60`）替换为：

```python
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
```

在 `wrap()` 方法（现 `sandbox.py:63-72`）之后新增：

```python
    def popen_kwargs(self) -> dict:
        """subprocess.Popen 额外参数：Linux 且 seccomp 启用时注入 preexec。

        过滤器随 fork/execve 继承 —— 驱动进程装一次，
        proc.exec 拉起的孙子进程自动被同一策略覆盖。
        非 Linux / off / 程序未组装成功时返回 {}（跨平台降级）。
        """
        if platform.system() != "Linux" or self.seccomp_mode != "block-dangerous":
            return {}
        prog = self._seccomp_prog
        if prog is None:
            return {}

        def _preexec() -> None:
            # fail-closed：装不上就炸掉这次 spawn，绝不允许裸奔运行
            install_seccomp(prog)

        return {"preexec_fn": _preexec}
```

- [ ] **Step 4: 修改 `laos/mcp.py` 的 MCPClient**

`__init__`（现 `mcp.py:203-210`）替换为：

```python
    def __init__(self, name: str, argv: list[str], env: dict | None = None,
                 popen_kwargs: dict | None = None):
        self.name = name
        self._argv = argv
        self._env = env
        self._popen_kwargs = popen_kwargs or {}
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._id = 0
        self.tools: dict[str, ToolSpec] = {}
```

`start()` 里的 `Popen` 调用（现 `mcp.py:218-227`）末尾追加解包：

```python
        self._proc = subprocess.Popen(
            self._argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
            **self._popen_kwargs,
        )
```

- [ ] **Step 5: 修改 `laos/kernel.py` 的 load_driver**

现 `kernel.py:147-157` 替换为：

```python
    def load_driver(self, name: str, argv: list[str], env: dict | None = None) -> MCPClient:
        # 驱动子进程经 sandbox 包装启动（Linux 上 unshare 隔离，跨平台降级原样）
        # seccomp 过滤器经 preexec_fn 注入，随 fork/execve 继承到 proc.exec 的子进程
        client = MCPClient(
            name, self.sandbox.wrap(argv), env=env,
            popen_kwargs=self.sandbox.popen_kwargs(),
        )
        client.start()
        # cgroup v2 资源上限：仅 root + cgroupfs 可写时生效，否则 None（降级）
        cgroup = self.sandbox.make_cgroup(f"drv-{name}")
        Sandbox.attach(cgroup, client.pid)
        self.drivers[name] = client
        for tool in client.tools.values():
            self.syscall_table[tool.name] = (name, tool)
        self.audit.write(
            {
                "t": time.time(),
                "event": "driver_load",
                "driver": name,
                "tools": len(client.tools),
                "cgroup": str(cgroup) if cgroup else None,
            }
        )
        return client
```

（`Sandbox` 已在 `kernel.py:25` import，无需新增。）

- [ ] **Step 6: 跑全量测试**

Run: `"$PY" -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 54 tests ... OK`（46 旧 + 8 新；Windows 上 seccomp 集成测试自动 skip，不计入失败）。Linux 上跑同一条命令时，所有驱动都在 seccomp 过滤器下存活 —— 这本身就是本任务的集成回归。

- [ ] **Step 7: Commit**

```bash
git add laos/sandbox.py laos/mcp.py laos/kernel.py tests/test_seccomp.py
git commit -m "feat(laos): wire seccomp+cgroup into driver spawn path"
```

---

### Task 3: laos.cow —— 写时复制原语

**Files:**
- Create: `laos/cow.py`
- Test: `tests/test_cow.py`

**Interfaces:**
- Produces:
  - `is_shared(p: Path) -> bool` —— `st_nlink > 1`
  - `cow_write(p: Path, data: str | bytes, encoding: str = "utf-8") -> Path` —— 原子替换式写入（temp + `os.replace`），绝不原地改写共享 inode
  - `cow_append(p: Path, data: str, encoding: str = "utf-8") -> Path` —— 读旧内容 + 追加后原子替换
- Consumes: 无（Task 4/5 消费）。

**设计要点：** 唯一正确的姿势是**永远走 temp+replace**，不管当前 `st_nlink` 是多少——判断"是否共享"再决定写法是 TOCTOU 漏洞（判断后、写入前另一个分支 fork 出来就竞态了）。`os.replace` 原子地换掉目录项：旧 inode 上还挂着的兄弟分支链接毫发无损，新 inode 属于本分支独占。这就是 CoW 断链。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_cow.py
"""CoW 原语测试（全平台可跑：hardlink/os.replace 在 Windows/POSIX 都成立）。

    python -m unittest tests.test_cow -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.cow import cow_append, cow_write, is_shared  # noqa: E402


class TestCow(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def _hardlinked_pair(self) -> tuple[Path, Path]:
        base = self.root / "f.txt"
        base.write_text("v0", encoding="utf-8")
        child = self.root / "child" / "f.txt"
        child.parent.mkdir(exist_ok=True)
        os.link(base, child)
        return base, child

    def test_is_shared_detects_hardlink(self):
        base, child = self._hardlinked_pair()
        self.assertTrue(is_shared(base))
        self.assertTrue(is_shared(child))

    def test_write_breaks_link_and_keeps_base(self):
        base, child = self._hardlinked_pair()
        cow_write(child, "v1", "utf-8")
        self.assertEqual(base.read_text(encoding="utf-8"), "v0")
        self.assertEqual(child.read_text(encoding="utf-8"), "v1")
        self.assertFalse(is_shared(base))

    def test_append_breaks_link_and_keeps_base(self):
        base, child = self._hardlinked_pair()
        cow_append(child, "-tail", "utf-8")
        self.assertEqual(base.read_text(encoding="utf-8"), "v0")
        self.assertEqual(child.read_text(encoding="utf-8"), "v0-tail")

    def test_append_creates_missing_file(self):
        p = self.root / "new.txt"
        cow_append(p, "hello", "utf-8")
        self.assertEqual(p.read_text(encoding="utf-8"), "hello")

    def test_write_accepts_bytes_and_leaves_no_tmp(self):
        p = self.root / "bin.dat"
        cow_write(p, b"\x00\x01")
        self.assertEqual(p.read_bytes(), b"\x00\x01")
        self.assertEqual(
            [q.name for q in self.root.iterdir()], ["bin.dat"], "残留 .tmp 文件"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m unittest tests.test_cow -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'laos.cow'`

- [ ] **Step 3: 实现 `laos/cow.py`**

```python
# laos/cow.py
"""CoW —— 写时复制原语：绝不原地修改可能被硬链接共享的 inode。

BranchContext.fork 用 os.link 把父分支目录树硬链接进子分支（数据块
全共享，fork 零字节拷贝）。此后子分支的**任何**写入都必须先"断链"：

    写 temp 文件（新 inode） -> os.replace 原子换掉目录项

旧 inode 上还挂着的父分支/兄弟分支链接不受影响 —— 这就是 BranchFS
在用户态的 COW 等价物（论文把这套语义下沉到 FUSE；我们用 hardlink）。

实现上**永远**走 temp+replace，不判断 st_nlink 再决定写法：
"先判断后写入"在 fork 并发下是 TOCTOU 竞态。os.replace 在
Windows/POSIX 都是原子目录项替换。临时文件带 pid+tid，驱动进程
单线程 stdio 串行，不会互相踩。
"""

from __future__ import annotations

import os
import threading
from pathlib import Path


def is_shared(p: Path) -> bool:
    """文件是否被多个目录项共享（st_nlink > 1）。stat 失败按未共享处理。"""
    try:
        return p.stat().st_nlink > 1
    except OSError:
        return False


def _atomic_replace(p: Path, raw: bytes) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.cow-{os.getpid()}-{threading.get_ident()}.tmp")
    try:
        tmp.write_bytes(raw)
        os.replace(tmp, p)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return p


def cow_write(p: Path, data: str | bytes, encoding: str = "utf-8") -> Path:
    """覆盖写：temp + os.replace，共享 inode 上的人看不到这次写入。"""
    raw = data.encode(encoding) if isinstance(data, str) else data
    return _atomic_replace(p, raw)


def cow_append(p: Path, data: str, encoding: str = "utf-8") -> Path:
    """追加写：读旧内容（缺文件按空）+ 新内容，整体原子替换。"""
    try:
        old = p.read_bytes()
    except FileNotFoundError:
        old = b""
    return _atomic_replace(p, old + data.encode(encoding))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `"$PY" -m unittest tests.test_cow -v`
Expected: `Ran 5 tests ... OK`

- [ ] **Step 5: Commit**

```bash
git add laos/cow.py tests/test_cow.py
git commit -m "feat(laos): CoW primitives (atomic temp+replace, link-breaking writes)"
```

---

### Task 4: 分支 fork 换 hardlink COW + diff 走 inode 快路径

**Files:**
- Modify: `laos/branch.py`（模块 docstring、`fork()`、`_hardlink_tree()` 新增、`_diff_files()`、`commit()`、`BranchContext` 加 `cow` 字段）
- Test: `tests/test_laos.py`（`TestBranch` 追加 2 个用例）

**Interfaces:**
- Consumes: Task 3 的 `cow_write`。
- Produces:
  - `BranchContext.fork(name: str, copy_mode: str = "auto") -> BranchContext` —— `copy_mode`: `"auto"`（硬链接，逐文件失败自动退 `shutil.copy2`）| `"copy"`（总是 `shutil.copytree`）；`BranchContext.cow: bool` 记录 fork 是否全程硬链接
  - `commit()` 行为不变（返回 applied 条数），但内部改用 `cow_write` 写父分支

**设计要点（写给实现者）：**
1. `_hardlink_tree` 只对普通文件 `os.link`；单个文件失败（EXDEV 跨设备、EPERM 等）退 `copy2` 但不整体失败——混合模式下 `cow=False`，但 CoW 写原语保证任何混合状态都安全。
2. `commit()` 里 `shutil.copy2(dst)` 是**炸弹**：copy2 用 `open(dst,'wb')` 截断目标 inode，而该 inode 可能正被兄弟分支硬链接——必须换成 `cow_write`（读子分支字节 → temp+replace 到父分支）。
3. `_diff_files` 的 `same()` 加 inode 快路径：`st_dev+st_ino` 相同 ⇒ 内容必然相同（CoW 原语保证共享 inode 从不原地改写，这是 Task 3 建立的不变量）⇒ 跳过字节比对；inode 不同才回退字节比对（覆盖 copy 模式与提交后替换场景）。fork 后 diff 从"读全部字节"降到"只 stat"。

- [ ] **Step 1: 在 tests/test_laos.py 的 TestBranch 类末尾追加两个用例**

```python
    def test_fork_hardlinks_share_data(self):
        # COW fork：子分支文件与父分支共享 inode（数据零拷贝）
        t, main = self._tree()
        b = main.fork("b1")
        self.assertTrue(b.cow, "auto 模式默认应走硬链接（本地文件系统）")
        si = (main.workspace / "f.txt").stat()
        ci = (b.workspace / "f.txt").stat()
        if si.st_ino == 0:
            self.skipTest("文件系统无 inode 语义")
        self.assertEqual((si.st_dev, si.st_ino), (ci.st_dev, ci.st_ino))

    def test_commit_does_not_corrupt_siblings(self):
        # A 提交时父分支文件可能与 B 硬链接共享 inode：
        # commit 必须走 CoW 替换，而不是 copy2 原地截断共享 inode
        t, main = self._tree()
        a = main.fork("A")
        b = main.fork("B")
        a.explore("f.txt", "from-A")
        a.commit()
        self.assertEqual(
            (b.workspace / "f.txt").read_text(encoding="utf-8"),
            "v0",
            "兄弟分支的 inode 被 commit 改写了",
        )
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m unittest tests.test_laos.TestBranch -v`
Expected: `test_commit_does_not_corrupt_siblings` FAIL（copy2 截断共享 inode，B 看到 "from-A"）；`test_fork_hardlinks_share_data` FAIL（`AttributeError: 'BranchContext' object has no attribute 'cow'`）。既有 4 个 TestBranch 用例保持 PASS。

- [ ] **Step 3: 修改 `laos/branch.py`**

3a. 文件头 import 增加 `os`，并引入 CoW 原语（现 `branch.py:17-24` 的 import 块改为）：

```python
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cow import cow_write
```

3b. 模块 docstring 第一段（`branch.py:1-15`）末尾追加一段：

```python
实现：fork 用硬链接共享数据块（O(inode)、零字节拷贝），写入走
laos.cow 的 temp+os.replace 断链 —— 这是 BranchFS COW 在用户态的
零依赖等价物；BranchContext 接口不变，日后可整体替换为 FUSE。
```

3c. `BranchContext` 数据类（现 `branch.py:34-44`）追加一个字段（放在 `committed_at` 之后）：

```python
    cow: bool = False  # fork 是否全程硬链接（混合/纯拷贝为 False）
```

3d. `fork()`（现 `branch.py:57-71`）替换为：

```python
    def fork(self, name: str, copy_mode: str = "auto") -> "BranchContext":
        """复制出子分支。

        copy_mode="auto"：硬链接父分支整棵目录树 —— 只复制目录项，
        数据块全共享（fork 零字节拷贝）；后续写入靠 laos.cow 断链。
        单个文件链接失败（跨设备/不支持）自动退 copy2，整体仍成功。
        copy_mode="copy"：退回 shutil.copytree 全量拷贝（旧行为）。
        语义两者一致：子分支拿到独立可写视图，提交前不影响父分支。
        """
        self._assert_alive()
        child_ws = self.workspace.parent / name
        if child_ws.exists():
            shutil.rmtree(child_ws)
        child_ws.mkdir(parents=True)
        used_cow = False
        if copy_mode == "auto":
            used_cow = _hardlink_tree(self.workspace, child_ws)
        else:
            shutil.copytree(self.workspace, child_ws, dirs_exist_ok=True)
        child = BranchContext(
            name=name, base=self.workspace, workspace=child_ws,
            parent=self, cow=used_cow,
        )
        self.children.append(child)
        return child
```

3e. 在模块级（`BranchContext` 类定义之前、`BranchState` 之后）新增：

```python
def _hardlink_tree(src: Path, dst: Path) -> bool:
    """把 src 目录树硬链接到 dst。返回是否全部走硬链接。

    目录 mkdir、普通文件 os.link、符号链接与链接失败退 copy2（不整体失败）。
    硬链接共享数据块：fork 只复制目录项，后续写入靠 laos.cow 断链。
    """
    all_linked = True
    for p in src.rglob("*"):
        t = dst / p.relative_to(src)
        if p.is_dir():
            t.mkdir(parents=True, exist_ok=True)
        elif p.is_symlink():
            all_linked = False
            shutil.copy2(p, t, follow_symlinks=False)
        else:
            try:
                os.link(p, t)
            except OSError:
                all_linked = False
                shutil.copy2(p, t)
    return all_linked
```

3f. `_diff_files()` 里的 `same()`（现 `branch.py:111-117`）替换为：

```python
        def same(a: Path, b: Path) -> bool:
            try:
                sa, sb = a.stat(), b.stat()
            except OSError:
                return False
            if sa.st_size != sb.st_size:
                return False
            # inode 快路径：CoW 原语保证共享 inode 从不原地改写，
            # 同 dev+ino 即同内容，免去整文件字节比对
            if sa.st_ino and sa.st_dev == sb.st_dev and sa.st_ino == sb.st_ino:
                return True
            try:
                return a.read_bytes() == b.read_bytes()
            except OSError:
                return False
```

3g. `commit()` 的写父分支循环（现 `branch.py:142-147`）替换为：

```python
        # 父分支文件可能被兄弟分支硬链接共享 —— 必须用 CoW 替换，
        # 绝不能 shutil.copy2 原地截断共享 inode（会改写兄弟分支的内容）
        for rel in changed:
            cow_write(self.parent.workspace / rel, (self.workspace / rel).read_bytes())
        for rel in deleted:
            (self.parent.workspace / rel).unlink(missing_ok=True)
```

- [ ] **Step 4: 跑全量测试**

Run: `"$PY" -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 61 tests ... OK`（含既有 `test_fork_is_isolated` / `test_commit_applies_diff` / `test_first_commit_wins_invalidates_siblings` / `test_nested_fork` —— 它们现在守护的是 hardlink 后端下的同一套语义）。

- [ ] **Step 5: Commit**

```bash
git add laos/branch.py tests/test_laos.py
git commit -m "feat(laos): hardlink COW fork (zero data copy) + inode-fast diff"
```

---

### Task 5: 驱动写路径接 CoW + 全栈回归

**Files:**
- Modify: `drivers/drv_fs.py`（`fs_write`/`fs_append` 换 CoW 原语）
- Test: `tests/test_laos.py`（`TestDrivers` 追加 1 个全栈用例）

**Interfaces:**
- Consumes: Task 3 的 `cow_write`/`cow_append`。
- Produces: `fs.write`/`fs.append` 在硬链接共享的文件上不再污染基线 —— Agent 经 MCP 写分支文件时，父分支与其他分支的内容不受影响（纵深防御之外补上"数据层隔离"的最后一块）。

- [ ] **Step 1: 在 tests/test_laos.py 的 TestDrivers 类末尾追加全栈用例**

```python
    def test_fs_write_on_hardlinked_branch_keeps_base(self):
        # 全栈回归：fork 出的分支经 MCP fs.append 写文件，
        # main 的同源文件必须原封不动（CoW 断链发生在驱动写路径上）
        exp = self.main.fork("exp-driver")
        pcb = self.kernel.spawn(name="t", caps=["fs.*"], ctx=object())
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "fs.append",
            {"path": "/exp-driver/workspace/hosts", "content": "# taint\n"},
        ))
        self.assertTrue(res.ok, res.error)
        self.assertNotIn(
            "# taint", (self.main.workspace / "workspace" / "hosts").read_text(encoding="utf-8"),
            "写分支污染了 main（驱动写路径没有 CoW 断链）",
        )
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m unittest tests.test_laos.TestDrivers -v`
Expected: `test_fs_write_on_hardlinked_branch_keeps_base` FAIL —— 驱动 `fs.append` 用 `p.open("a")` 原地追加共享 inode，main 的 hosts 里出现 `# taint`。

- [ ] **Step 3: 修改 `drivers/drv_fs.py`**

import 块（现 `drv_fs.py:13-20`）增加一行：

```python
from laos.cow import cow_append, cow_write  # noqa: E402
```

`fs_write` 的写文件行（现 `drv_fs.py:62-63`）替换为：

```python
    p = jail.resolve(path)
    cow_write(p, content, "utf-8")
```

`fs_append` 的追加块（现 `drv_fs.py:80-83`）替换为：

```python
    p = jail.resolve(path)
    cow_append(p, content, "utf-8")
```

- [ ] **Step 4: 跑全量测试**

Run: `"$PY" -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 62 tests ... OK`

- [ ] **Step 5: Commit**

```bash
git add drivers/drv_fs.py tests/test_laos.py
git commit -m "feat(laos): CoW on driver fs write/append paths"
```

---

### Task 6: eBPF profiling —— bpftrace 集成

**Files:**
- Create: `laos/profiling.py`
- Test: `tests/test_profiling.py`

**Interfaces:**
- Consumes: 无（Task 7 消费）。
- Produces:
  - `BpfTraceProfiler(pids: list[int])`
  - `.available() -> tuple[bool, str]` —— (是否可用, 原因/后端名)
  - `.script() -> str` —— 生成的 bpftrace one-liner（纯函数，全平台可测）
  - `.parse(text: str) -> dict[str, int]`（静态方法）—— 解析 bpftrace 的 `@[probe]: N` 输出
  - `.start() -> bool` / `.stop() -> dict[str, int]` / `.reason: str`
  - 语义：按驱动 pid 及其子进程（`ppid`）过滤 `syscalls:sys_enter_*` 通配探针，每 2s 打印快照、SIGINT 退出兜底打印聚合

- [ ] **Step 1: 写失败测试**

```python
# tests/test_profiling.py
"""bpftrace 集成层测试（脚本生成与解析是纯 Python，全平台可跑；
   真实采集见 TestBpfTraceLinux，仅 Linux+root+bpftrace 执行）。

    python -m unittest tests.test_profiling -v
"""
from __future__ import annotations

import platform
import unittest

from laos.profiling import BpfTraceProfiler

SAMPLE_OUTPUT = """\
Attaching 5 probes...
@[syscalls:sys_enter_read]: 42
@[syscalls:sys_enter_openat]: 7
@[syscalls:sys_enter_write]: 13
"""


class TestScriptAndParse(unittest.TestCase):
    def test_script_targets_pids_and_children(self):
        s = BpfTraceProfiler(pids=[11, 22]).script()
        self.assertIn("syscalls:sys_enter_*", s)
        self.assertIn("pid == 11", s)
        self.assertIn("pid == 22", s)
        self.assertIn("ppid == 11", s)  # proc.exec 的孙子进程按 ppid 覆盖

    def test_parse_accumulates_duplicate_probes(self):
        got = BpfTraceProfiler.parse(SAMPLE_OUTPUT)
        self.assertEqual(got["syscalls:sys_enter_read"], 42)
        self.assertEqual(got["syscalls:sys_enter_openat"], 7)
        # 两份相同快照（interval 周期打印 + 退出兜底打印）应累加
        doubled = BpfTraceProfiler.parse(SAMPLE_OUTPUT + SAMPLE_OUTPUT)
        self.assertEqual(doubled["syscalls:sys_enter_read"], 84)

    def test_parse_ignores_noise(self):
        got = BpfTraceProfiler.parse("Attaching 5 probes...\n\n随机日志行")
        self.assertEqual(got, {})


class TestAvailable(unittest.TestCase):
    def test_available_returns_reason_tuple(self):
        ok, why = BpfTraceProfiler(pids=[1]).available()
        self.assertIsInstance(ok, bool)
        self.assertTrue(why)
        if platform.system() != "Linux":
            self.assertFalse(ok, "非 Linux 必须报告不可用")
            self.assertIn("Linux", why)


@unittest.skipUnless(platform.system() == "Linux", "bpftrace 仅 Linux")
class TestBpfTraceLinux(unittest.TestCase):
    def test_real_capture_of_sleep_process(self):
        import shutil
        import subprocess
        import time

        prof = BpfTraceProfiler(pids=[])
        ok, why = prof.available()
        if not ok:
            self.skipTest(why)
        child = subprocess.Popen(["sleep", "3"])
        try:
            prof2 = BpfTraceProfiler(pids=[child.pid])
            self.assertTrue(prof2.start())
            time.sleep(3.5)
        finally:
            child.wait()
        probes = prof2.stop()
        # sleep 进程至少会 clock_nanosleep -> 对应 enter 探针出现
        self.assertTrue(
            any("clock_nanosleep" in k for k in probes),
            f"未捕捉到 clock_nanosleep: {probes}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m unittest tests.test_profiling -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'laos.profiling'`

- [ ] **Step 3: 实现 `laos/profiling.py`**

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `"$PY" -m unittest tests.test_profiling -v`
Expected: Windows 上 `Ran 5 tests ... OK (skipped=1)`（`TestBpfTraceLinux` skip）；Linux+root+bpftrace 上同样 `Ran 5 tests ... OK` 且无 skip。

- [ ] **Step 5: Commit**

```bash
git add laos/profiling.py tests/test_profiling.py
git commit -m "feat(laos): bpftrace-based syscall profiling (optional, degrades cleanly)"
```

---

### Task 7: 接入 laosd demo 与 laosctl

**Files:**
- Modify: `bin/laosd.py`（demo 第 4 节前启动 profiler，第 6 节停止并打印直方图）
- Modify: `bin/laosctl.py`（新增 `prof` 子命令）
- Test: 手工验收（demo 是输出编排层，unittest 不覆盖；验收步骤见下）

**Interfaces:**
- Consumes: Task 6 的 `BpfTraceProfiler`。
- Produces:
  - 审计日志新增事件 `{"t", "event": "prof_summary", "backend": str, "probes": {probe: count}}`（LAOS_PROF=0 或不可用时记录 `"backend": "off"` / 不可用原因且无 probes）
  - `python bin/laosctl.py prof` 读取审计日志中最后一条 `prof_summary` 打印 top-15
  - 环境变量 `LAOS_PROF`：`1`（默认）/`0` 关闭

- [ ] **Step 1: 修改 bin/laosd.py 的 demo()**

4a. 在 `# ---- 执行 ----` 段（现 `laosd.py:141-145`，`hr("4. ReAct 循环...")` 之后、`results = await run_agents(...)` 之前）插入 profiler 启动：

```python
    # ---- eBPF 语义 profiling（可选，缺席自动降级）-------------------------
    prof = None
    if os.environ.get("LAOS_PROF", "1") != "0":
        from laos.profiling import BpfTraceProfiler
        prof = BpfTraceProfiler([m["pid"] for m in kernel.lsmod()])
        if not prof.start():
            print(f"  [profiler] 未启用: {prof.reason}")
            kernel.audit.write({"t": time.time(), "event": "prof_summary",
                                "backend": f"unavailable: {prof.reason}", "probes": {}})
            prof = None
```

4b. 在 `# ---- 结果 ----` 段（现 `laosd.py:170-175`，`print(f"  审计记录 ...")` 之后）插入停止与直方图：

```python
    if prof is not None:
        probes = prof.stop()
        kernel.audit.write({"t": time.time(), "event": "prof_summary",
                            "backend": prof.reason, "probes": probes})
        print("\n  eBPF: 驱动进程树真实 syscall 分布（top 10，对照上面“声称”的 tool call）:")
        for probe, n in sorted(probes.items(), key=lambda kv: -kv[1])[:10]:
            print(f"    {probe:<44}{n:>10}")
```

- [ ] **Step 2: 修改 bin/laosctl.py**

2a. 模块 docstring 的用法块（现 `laosctl.py:4-10`）追加一行：

```python
    python bin/laosctl.py prof                  # eBPF 采集的真实 syscall 分布
```

2b. 在 `cmd_ps` 之后新增：

```python
def cmd_prof(records: list[dict], args) -> None:
    profs = [r for r in records if r.get("event") == "prof_summary"]
    if not profs:
        print("无 prof_summary 记录（需要 LAOS_PROF=1 且 Linux + root + bpftrace）")
        return
    r = profs[-1]
    print(f"backend={r.get('backend')}")
    probes = r.get("probes", {})
    if not probes:
        return
    print(f"{'probe':<44}{'count':>10}")
    for name, n in sorted(probes.items(), key=lambda kv: -kv[1])[:15]:
        print(f"{name:<44}{n:>10}")
```

2c. `main()` 里的 choices（现 `laosctl.py:109`）与分发表（现 `laosctl.py:116`）各加一项：

```python
    ap.add_argument("command",
                    choices=["audit", "trace", "denied", "top", "ps", "prof"])
```

```python
    {"audit": cmd_audit, "trace": cmd_trace, "denied": cmd_denied,
     "top": cmd_top, "ps": cmd_ps, "prof": cmd_prof}[args.command](records, args)
```

- [ ] **Step 3: 全量测试 + 手工验收**

Run: `"$PY" -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 67 tests ... OK`（profiler 未接入内核路径，测试数不变）

手工验收（Windows 上验证降级路径）：

```bash
"$PY" bin/laosd.py 2>&1 | grep -A2 "profiler"
"$PY" bin/laosctl.py prof
```
Expected: demo 打印 `[profiler] 未启用: bpftrace 仅 Linux（当前 Windows）`；laosctl 打印 `backend=unavailable: bpftrace 仅 Linux（当前 Windows）`。审计日志 `var/audit.jsonl` 出现 `prof_summary` 记录。

（Linux + root 机器上：`sudo LAOS_PROF=1 python3 bin/laosd.py` 应在第 6 节看到 `syscalls:sys_enter_*` 直方图，且 openat/read/write 的量级与第 4 节 tool call 次数同数量级。）

- [ ] **Step 4: Commit**

```bash
git add bin/laosd.py bin/laosctl.py
git commit -m "feat(laos): wire eBPF profiler into demo + laosctl prof"
```

---

### Task 8: 文档收尾 + 全量回归

**Files:**
- Modify: `README.md`（§6 表、§7 目录结构、§8 环境变量、§4 测试数）

**Interfaces:**
- Consumes: Task 1-7 全部产物。
- Produces: README 与实现一致；最终基线。

- [ ] **Step 1: 更新 README §6 表的三行**

| 缺口 | 现状（新） | 该怎么做（新） |
|---|---|---|
| **强制隔离** | 驱动 spawn 已接 namespace + cgroup v2 + **seccomp block-dangerous**（`LAOS_SECCOMP`，经 preexec 注入、随 fork/execve 继承到 proc.exec 子进程） | per-agent（而非 per-driver）cgroup；seccomp 白名单模式（按驱动画像） |
| **分支的 O(1) 创建** | **hardlink COW**：fork 只复制目录项、数据块全共享、写路径 temp+replace 断链（`laos/cow.py`）；diff 走 inode 快路径 | FUSE BranchFS（真 O(1) inode 级 + 原子 rename 语义）仍是长期项 |
| **语义 profiling** | **bpftrace 集成**（`LAOS_PROF=1`）：采集驱动进程树真实 syscall 分布，`laosctl prof` 回放 | AgentProf 式语义剖析：每步意图、工具选择合理性 |

- [ ] **Step 2: 更新 README §7 目录结构**

在 `laos/` 段落 `sandbox.py` 行之后补三行：

```
    seccomp.py    seccomp 经典 BPF 组装 + ctypes 安装（block-dangerous 黑名单）
    cow.py        CoW 原语：temp + os.replace 断链写，保护 hardlink 共享 inode
    profiling.py  bpftrace 集成：驱动进程树真实 syscall 分布（可选，缺席降级）
```

- [ ] **Step 3: 更新 README §8 环境变量表**

追加两行：

| 变量 | 默认 | 说明 |
|---|---|---|
| `LAOS_SECCOMP` | `block-dangerous` | `off` 关闭；`block-dangerous` 给驱动装 seccomp 黑名单过滤器（仅 Linux） |
| `LAOS_PROF` | `1` | `0` 关闭 eBPF profiling；开启需 Linux + root + bpftrace，缺席自动降级 |

- [ ] **Step 4: 修正测试数**

`README.md` 第 13 行 `python -m unittest discover -s tests   # 26 项回归测试` 改为：

```bash
python -m unittest discover -s tests   # 67 项回归测试
```

- [ ] **Step 5: 最终全量回归 + 收尾 commit**

Run: `"$PY" -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 67 tests ... OK`（Linux 上同命令也应 OK，且 demo 在 seccomp 过滤器下正常跑完 7 幕）

```bash
git add README.md
git commit -m "docs(laos): seccomp/cow/ebpf roadmap status in README"
```

---

## 验收清单（全部完成后核对）

- [ ] `python -m unittest discover -s tests` 67 项全绿（Windows 与 Linux 各跑一次）
- [ ] Linux + root：`python3 bin/laosd.py` 第 1 节隔离报告含 `seccomp=block-dangerous (27 条 deny)`，第 6 节出现 eBPF 直方图
- [ ] Linux：`python3 -c` 探针在驱动过滤器下 `swapon` 得到 EPERM（tests/test_seccomp.py::TestSeccompLinux 覆盖）
- [ ] fork 语义回归：`test_fork_is_isolated`、`test_commit_does_not_corrupt_siblings`、`test_fs_write_on_hardlinked_branch_keeps_base` 全过 —— 证明 hardlink 后端下"隔离、first-commit-wins、兄弟不受伤"三条不变量都成立
- [ ] `git log --oneline` 恰好 9 个 commit（1 baseline + 8 feature/docs）
