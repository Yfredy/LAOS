# Stale Context 检测实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现《When Agent Context Goes Stale: Incoherence in Volatile Agent Context》（AgenticOS @ SOSP 2026, HKU）的 laos 版：上下文里"读过的文件"被外部修改后，内核精确知道哪些观察已陈旧，并在 agent 下一步思考前注入内核通告强制重读。

**Architecture:** laos 的独有优势是 branch diff 机制天然知道"世界变了什么"。设计三层：① `ContextManager` 增加观察簿（`observe(path, digest)` 记录读时的内容摘要、`invalidate(path)` 标记陈旧、`drain_notices()` 一次性取走待通告列表）；② `kernel.syscall` 在 `fs.read` 成功后记录观察（内容 sha256 前 16 位），在 `fs.write/fs.append` 成功后把该路径在**其他所有** agent 的观察簿里标记陈旧（写者自己对刚写的内容是知情的——论文的 incoherence 指的是"相信了与现实不符的记忆"）；③ `Agent.run` 每步思考前 drain 通告并以 user 角色（带 `[kernel-notice]` 前缀）注入窗口。branch commit 的批量失效经 `kernel.on_branch_committed()` 由 laosd 显式触发。

**Tech Stack:** Python 3.10+ 标准库（hashlib），零第三方依赖。测试 unittest。

**Spec:** `docs/research/2026-09-05-agentos-next-steps.md` §一.2 / §二#2；论文见 [AgenticOS @ SOSP 2026](https://os-for-agent.github.io/)。

## Global Constraints

- 零第三方依赖；stdlib only（新增 hashlib）。
- 不破坏执行时基线的全部测试（以实测为准，R103）；新增测试放独立文件 `tests/test_stale.py`。
- errno 约定不变；本特性不产生新 errno（陈旧是通告不是拒绝）。
- 解释器 `/c/Users/yaoyue/AppData/Roaming/uv/python/cpython-3.12.14-windows-x86_64-none/python.exe`（记 `$PY`）。
- commit 粒度：每 task 一个 commit，`feat(laos): <task 名>`。
- ⚠️ 设计红线：`ContextManager.append(role="system")` 会**替换**系统提示（context.py:79-83）——内核通告绝不能用 system 角色注入，必须走新增的 `notice()` 方法（user 角色加前缀）。

## 现状关键事实

- `laos/context.py:79-88`：`append(role, content, **meta)`，system 角色替换 `self._system`；`stats` 有 turns/total_tokens。
- `laos/kernel.py` syscall 闸门（caps → validate → EDQUOT → 风险闸门 → 驱动调用）；`CallResult.ok`/`.text` 可用；`self.procs: dict[int, PCB]` 全局可见。
- `laos/agent.py:90-100`：`Agent.run` 的 for 步循环，`tools = self.visible_tools` 后进入 think；这是通告注入点。
- `laos/branch.py` `BranchContext.commit()`（hardlink 后端）返回 applied 条数；laosd 的 demo 在第 5 节调用 `exp_a.commit()`。

---

### Task 1: ContextManager 观察簿

**Files:**
- Modify: `laos/context.py`（新增观察簿三方法 + stats 字段）
- Test: `tests/test_stale.py`（新建）

**Interfaces:**
- Produces: `ContextManager.observe(path: str, digest: str) -> None`、`invalidate(path: str) -> None`、`drain_notices() -> list[str]`、`notice(content: str) -> Message`；`ContextStats` 增加 `stale_marks: int = 0`。
- 语义：`observe` 记录（重复 observe 同路径覆盖旧摘要并从 stale 集移除——重读即愈合）；`invalidate` 只对观察过的路径生效并计数；`drain_notices` 返回"当前陈旧的路径列表"并**清除陈旧集**（通告一次性）；`notice` 以 user 角色 append，内容加 `[kernel-notice] ` 前缀。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_stale.py
"""Stale context —— 观察簿与内核级陈旧检测（HKU, AgenticOS @ SOSP 2026）。

    python -m unittest tests.test_stale -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.context import ContextManager  # noqa: E402


class TestObservationBook(unittest.TestCase):
    def test_observe_then_invalidate(self):
        ctx = ContextManager(system_prompt="s")
        ctx.observe("/main/workspace/hosts", "digest-1")
        ctx.invalidate("/main/workspace/hosts")
        self.assertEqual(ctx.drain_notices(), ["/main/workspace/hosts"])
        self.assertEqual(ctx.drain_notices(), [])  # 一次性

    def test_invalidate_unknown_path_is_noop(self):
        ctx = ContextManager(system_prompt="s")
        ctx.invalidate("/never/observed")
        self.assertEqual(ctx.drain_notices(), [])

    def test_reobserve_heals(self):
        ctx = ContextManager(system_prompt="s")
        ctx.observe("/p", "d1")
        ctx.invalidate("/p")
        ctx.observe("/p", "d2")  # 重读即愈合
        self.assertEqual(ctx.drain_notices(), [])

    def test_notice_uses_user_role_and_prefix(self):
        ctx = ContextManager(system_prompt="s")
        msg = ctx.notice("STALE: /p")
        self.assertEqual(msg.role, "user")
        self.assertTrue(msg.content.startswith("[kernel-notice] "))
        # notice 不得替换系统提示
        self.assertEqual(ctx.messages[0]["content"], "s")

    def test_invalidate_counts_stats(self):
        ctx = ContextManager(system_prompt="s")
        ctx.observe("/p", "d")
        ctx.invalidate("/p")
        self.assertEqual(ctx.stats.stale_marks, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_stale -v`
Expected: FAIL —— `AttributeError: 'ContextManager' object has no attribute 'observe'`

- [ ] **Step 3: 实现（laos/context.py）**

`ContextStats` 增加 `stale_marks: int = 0`；`ContextManager.__init__` 末尾（`self._window = []` 之后）增加：

```python
        # 观察簿：path -> 读时内容摘要（Stale Context 检测，HKU/AgenticOS'26）
        self._observations: dict[str, str] = {}
        self._stale: set[str] = set()
```

类末尾（`resume` 之后）新增三个方法：

```python
    # -- Stale Context：观察簿 --------------------------------------------
    def observe(self, path: str, digest: str) -> None:
        """记录一次 fs.read 观察：读到的内容摘要。重读即愈合。"""
        self._observations[path] = digest
        self._stale.discard(path)

    def invalidate(self, path: str) -> None:
        """该路径被外部修改：观察过它的上下文从此陈旧。"""
        if path in self._observations and path not in self._stale:
            self._stale.add(path)
            self.stats.stale_marks += 1

    def drain_notices(self) -> list[str]:
        """取走当前陈旧路径列表（一次性，取走即清）。"""
        out = sorted(self._stale)
        self._stale.clear()
        return out

    def notice(self, content: str) -> Message:
        """内核通告：以 user 角色注入（append('system') 会替换系统提示，勿用）。"""
        return self.append("user", f"[kernel-notice] {content}")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m unittest tests.test_stale -v`
Expected: `Ran 5 tests ... OK`

- [ ] **Step 5: 全量回归 + Commit**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿，总数 = 实测基线 + 5）

```bash
git add laos/context.py tests/test_stale.py
git commit -m "feat(laos): context observation book (stale-context detection core)"
```

---

### Task 2: 内核接线 —— fs.read 观察 / fs.write·append 失效他人

**Files:**
- Modify: `laos/kernel.py`（syscall 驱动调用成功后增加观察/失效钩子；新增 `_digest` 静态方法）
- Test: `tests/test_stale.py`（追加）

**Interfaces:**
- Consumes: Task 1 的三方法。
- Produces: kernel 内部行为——`fs.read` 成功 → `pcb.ctx.observe(args["path"], sha16(result.text))`；`fs.write`/`fs.append` 成功（args["path"]=P）→ 对**除调用者外**每个 `pcb2.ctx` 存在 `P` 的执行 `invalidate(P)`。`sha16(text) = hashlib.sha256(text.encode()).hexdigest()[:16]`。仅当 `pcb.ctx` 具有 `observe` 方法时执行（ctx 可能是 `object()` 测试桩——用 `hasattr` 守卫）。

- [ ] **Step 1: 追加失败测试**

```python
class TestKernelStaleWiring(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {
            "PYTHONPATH": str(REPO),
            "PYTHONIOENCODING": "utf-8",
            "LAOS_FS_ROOT": str(self.workdir / "branches"),
        }
        self.kernel.load_driver("fs", [sys.executable, str(REPO / "drivers" / "drv_fs.py")], env=env)
        self.kernel.load_driver("sys", [sys.executable, str(REPO / "drivers" / "drv_sys.py")], env=env)
        self.main = self.kernel.branches.create_root("main")
        (self.main.workspace / "workspace").mkdir(parents=True, exist_ok=True)
        (self.main.workspace / "workspace" / "hosts").write_text(
            "127.0.0.1 localhost\n", encoding="utf-8")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, name, caps):
        from laos.context import ContextManager
        ctx = ContextManager(system_prompt="t", max_tokens=2000,
                             swap_dir=self.workdir / "swap")
        return self.kernel.spawn(name=name, caps=caps, ctx=ctx, branch="main")

    def test_read_records_observation(self):
        pcb = self._spawn("reader", ["fs.*"])
        res = asyncio.run(self.kernel.syscall(pcb.pid, "fs.read",
                                              {"path": "/main/workspace/hosts"}))
        self.assertTrue(res.ok)
        self.assertIn("/main/workspace/hosts", pcb.ctx._observations)

    def test_writer_invalidates_other_readers_only(self):
        reader = self._spawn("reader", ["fs.*"])
        writer = self._spawn("writer", ["fs.*"])
        asyncio.run(self.kernel.syscall(reader.pid, "fs.read",
                                        {"path": "/main/workspace/hosts"}))
        asyncio.run(self.kernel.syscall(writer.pid, "fs.read",
                                        {"path": "/main/workspace/hosts"}))
        res = asyncio.run(self.kernel.syscall(writer.pid, "fs.append",
                                              {"path": "/main/workspace/hosts",
                                               "content": "# changed\n"}))
        self.assertTrue(res.ok)
        # 写者豁免（对刚写的内容知情），读者被标陈旧
        self.assertNotIn("/main/workspace/hosts", writer.ctx._stale)
        self.assertIn("/main/workspace/hosts", reader.ctx._stale)

    def test_object_stub_ctx_never_crashes(self):
        pcb = self.kernel.spawn(name="stub", caps=["fs.*"], ctx=object())
        res = asyncio.run(self.kernel.syscall(pcb.pid, "fs.read",
                                              {"path": "/main/workspace/hosts"}))
        self.assertTrue(res.ok)  # ctx 无 observe 方法时静默跳过
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_stale -v`
Expected: 新类 3 项 FAIL（观察簿无记录 / 无失效）

- [ ] **Step 3: 实现（laos/kernel.py）**

文件 import 增加 `import hashlib`。`AgentKernel` 增加静态方法：

```python
    @staticmethod
    def _digest(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
```

在 syscall 的驱动调用返回之后、`elapsed_ms = ...` 之前插入钩子（`result` 为 CallResult，`pcb`/`args`/`driver_name` 在作用域内）：

```python
        # Stale Context：fs.read 记录观察；fs.write/append 失效其他 agent 的观察
        if result.ok and hasattr(pcb.ctx, "observe"):
            if tool == "fs.read" and "path" in args:
                pcb.ctx.observe(args["path"], self._digest(result.text))
            elif tool in ("fs.write", "fs.append") and "path" in args:
                for other in self.procs.values():
                    if other.pid != pcb.pid and hasattr(other.ctx, "invalidate"):
                        other.ctx.invalidate(args["path"])
```

- [ ] **Step 4: 跑全量测试**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿 = 实测基线 + 8）

- [ ] **Step 5: Commit**

```bash
git add laos/kernel.py tests/test_stale.py
git commit -m "feat(laos): kernel wiring for stale-context observation and invalidation"
```

---

### Task 3: Agent 通告注入 + branch commit 失效钩子

**Files:**
- Modify: `laos/agent.py`（run 循环注入）、`laos/kernel.py`（`on_branch_committed`）、`bin/laosd.py`（demo 第 5 节调用钩子）
- Test: `tests/test_stale.py`（追加）

**Interfaces:**
- Produces: `AgentKernel.on_branch_committed(branch: str, paths: list[str]) -> None` —— 对 branch 上（及所有）agent 的 ctx invalidate 这些路径（按虚拟前缀 `/main/...` 前缀匹配）；`Agent.run` 在每步循环开头 drain 通告并对每条调用 `ctx.notice(f"STALE: {p} 已被外部修改，请重新 fs.read")`。
- 前缀匹配规则：commit 的 `paths` 是分支内相对路径（如 `workspace/hosts`），虚拟化为 `/{branch}/{path}`；对每个 pcb 若 `pcb.branch == branch` 或观察簿含 `/​{branch}/{path}` 键则失效。实现取简：直接按完整虚拟路径失效（观察簿 key 就是虚拟路径）。

- [ ] **Step 1: 追加失败测试**

```python
class TestNoticeInjection(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8",
               "LAOS_FS_ROOT": str(self.workdir / "branches")}
        self.kernel.load_driver("fs", [sys.executable, str(REPO / "drivers" / "drv_fs.py")], env=env)
        self.main = self.kernel.branches.create_root("main")
        (self.main.workspace / "workspace").mkdir(parents=True, exist_ok=True)
        (self.main.workspace / "workspace" / "hosts").write_text(
            "127.0.0.1 localhost\n", encoding="utf-8")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def test_branch_commit_invalidates_observers(self):
        from laos.context import ContextManager
        ctx = ContextManager(system_prompt="t", max_tokens=2000,
                             swap_dir=self.workdir / "swap")
        pcb = self.kernel.spawn(name="r", caps=["fs.*"], ctx=ctx, branch="main")
        asyncio.run(self.kernel.syscall(pcb.pid, "fs.read",
                                        {"path": "/main/workspace/hosts"}))
        self.kernel.on_branch_committed("main", ["workspace/hosts"])
        self.assertIn("/main/workspace/hosts", ctx.drain_notices())

    def test_agent_injects_notice_before_next_think(self):
        from laos.context import ContextManager
        from laos.brain import ScriptedBrain
        from laos.agent import Agent
        ctx = ContextManager(system_prompt="t", max_tokens=2000,
                             swap_dir=self.workdir / "swap")
        pcb = self.kernel.spawn(name="r", caps=["fs.*", "sys.*"], ctx=ctx, branch="main")
        asyncio.run(self.kernel.syscall(pcb.pid, "fs.read",
                                        {"path": "/main/workspace/hosts"}))
        ctx.invalidate("/main/workspace/hosts")
        agent = Agent(self.kernel, pcb,
                      ScriptedBrain(branch="main"), max_steps=8)
        res = asyncio.run(agent.run("read and verify hosts"))
        notices = [m for m in pcb.ctx.messages
                   if m["role"] == "user" and str(m.get("content", "")).startswith("[kernel-notice]")]
        self.assertGreaterEqual(len(notices), 1)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_stale -v`
Expected: 新类 FAIL（无 `on_branch_committed`；无通告注入）

- [ ] **Step 3: 实现**

3a. `laos/kernel.py` `AgentKernel` 新增：

```python
    # -- Stale Context：branch commit 批量失效 -----------------------------
    def on_branch_committed(self, branch: str, paths: list[str]) -> None:
        """分支提交改变了父分支内容：所有观察过这些路径的上下文失效。"""
        for virt in (f"/{branch}/{p}".replace("\\", "/") for p in paths):
            for pcb in self.procs.values():
                if hasattr(pcb.ctx, "invalidate"):
                    pcb.ctx.invalidate(virt)
        self.audit.write(
            {"t": time.time(), "event": "stale_broadcast", "branch": branch,
             "paths": len(paths)}
        )
```

3b. `laos/agent.py` `run()` 的 `for step in range(1, self.max_steps + 1):` 循环体第一行（`tools = self.visible_tools` 之前）插入：

```python
                # Stale Context：内核通告注入（HKU: 当上下文与现实不符时强制重读）
                for stale_path in self.pcb.ctx.drain_notices() if hasattr(self.pcb.ctx, "drain_notices") else []:
                    self.pcb.ctx.notice(
                        f"STALE: {stale_path} 已被外部修改，之前的读取结果不可信，请重新 fs.read"
                    )
```

3c. `bin/laosd.py` 第 5 节：`applied = exp_a.commit()` 之后（`print(f"  exp-A 提交 ...")` 之前）插入：

```python
    kernel.on_branch_committed("main", [e["path"] for e in exp_a.diff()])
```

- [ ] **Step 4: 跑全量测试**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿 = 实测基线 + 10）

- [ ] **Step 5: Commit**

```bash
git add laos/agent.py laos/kernel.py bin/laosd.py tests/test_stale.py
git commit -m "feat(laos): stale-context notices injected into agent loop + commit hook"
```

---

### Task 4: README + 收尾

**Files:**
- Modify: `README.md`（§6 上下文一致性行、§7 目录行）

- [ ] **Step 1: README §6「上下文一致性」行替换为**

| **上下文一致性** | ~~只看 token 水位~~ → **Stale Context 检测**：fs.read 观察簿 + fs.write/append 失效他人 + branch commit 批量失效，内核通告注入 agent 窗口 | 跨驱动（非 fs 类）副作用的一致性追踪 |

- [ ] **Step 2: README §7 laos/ 段 `context.py` 行的说明改为**

```
    context.py    Context Manager：窗口 / 摘要压缩 / swap / 观察簿（stale 检测）
```

- [ ] **Step 3: 全量回归 + Commit**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿）

```bash
git add README.md
git commit -m "docs(laos): stale-context detection in README"
```

## 验收清单

- [ ] 全量测试全绿（基线 + 10）
- [ ] `tests/test_irreversibility.py`、`tests/test_risk.py` 等既有文件零改动
- [ ] demo 管道运行 `风险账本`/`隔离能力` 行为不变；`grep "stale_broadcast" var/audit.jsonl` 在 commit 后出现
- [ ] 本计划恰 4 个 commit
