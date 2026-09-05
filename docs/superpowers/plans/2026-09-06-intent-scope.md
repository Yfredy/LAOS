# 意图→能力收窄（task_scope）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落实《Securing Agentic AI with OS-Level Intent-Driven Capabilities》（AgenticOS @ SOSP 2026 lightning, Oracle Labs）的思想：能力应随**任务意图**收窄。`spawn` 新增 `task_scope: list[str] | None`——虚拟路径前缀白名单；带 `path` 参数的 syscall（fs.*）在能力检查之后追加作用域检查，越界一律 `EACCES: outside task scope`。能力表说"能用 fs"，task_scope 说"本次任务只许碰这些路径"。

**Architecture:** `PCB.task_scope` 字段（spawn 参数，`fork_child` 一并透传——吸取 risk_cap 曾漏传的教训）；`kernel.syscall` 在能力检查后插入作用域检查（仅当 `pcb.task_scope` 非空且 `args` 含 `path`；非 fs 类工具无 path 不受影响）；`risk_cap` 的先例同样适用于 sys.delegate 授出的能力吗？——不：task_scope 是 **agent 自身**的任务边界，委托来的调用按**委托者**的 caps 走、按**使用者**的 task_scope 走（使用者的任务边界不因委托放宽）。

**Tech Stack:** Python 3.10+ 标准库，零第三方依赖。

**Spec:** `docs/research/2026-09-05-agentos-next-steps.md` §二#7。

## Global Constraints

- 零第三方依赖；不破坏执行时基线测试（以实测为准）；新增测试放独立文件 `tests/test_scope.py`。
- 解释器 `$PY`（同前）；每 task 一个 commit；新拒绝 errno：`EACCES`（消息含 `outside task scope`）。

## 现状关键事实

- `PCB`（kernel.py:75+）字段：pid/name/caps/state/parent/created_at/ctx/stats/branch/budget/risk_cap。
- `spawn(name, caps, ctx, branch=None, parent=0, budget=None, risk_cap=None)`；`fork_child`（agent.py）传 `budget=self.pcb.budget, risk_cap=self.pcb.risk_cap`。
- `syscall` 能力检查在 `kernel.py` 闸门链最前（caps → validate → EDQUOT → 风险闸门）——task_scope 检查插在 caps 之后、validate 之前（语义：先问"允许碰这个路径吗"再校验参数）。
- `msg.*` 内建与 `fs.*` 一样走同一条闸门链；`msg` 无 path 参数天然不受影响。

---

### Task 1: task_scope 字段 + spawn + 闸门 + fork_child 透传

**Files:**
- Modify: `laos/kernel.py`（PCB 字段、spawn 参数、闸门插入）、`laos/agent.py`（fork_child 透传）
- Test: `tests/test_scope.py`（新建）

**Interfaces:**
- Produces: `PCB.task_scope: list[str] | None = None`；`spawn(..., task_scope: list[str] | None = None)`；`fork_child` 透传 `task_scope=self.pcb.task_scope`；kernel 闸门新检查（位置：caps 通过之后、validate_args 之前）：

```python
        if pcb.task_scope and "path" in args:
            if not any(str(args["path"]).startswith(p) for p in pcb.task_scope):
                return self._deny(pcb, tool, args, started,
                                  "EACCES: outside task scope")
```

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scope.py
"""task_scope —— 意图驱动的路径级能力收窄（Oracle Labs, AgenticOS'26）。

    python -m unittest tests.test_scope -v
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.context import ContextManager  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402


class TestTaskScope(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8",
               "LAOS_FS_ROOT": str(self.workdir / "branches")}
        self.kernel.load_driver("fs", [sys.executable, str(REPO / "drivers" / "drv_fs.py")],
                                env=env)
        self.kernel.load_driver("sys", [sys.executable, str(REPO / "drivers" / "drv_sys.py")],
                                env=env)
        self.main = self.kernel.branches.create_root("main")
        ws = self.main.workspace / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "hosts").write_text("127.0.0.1 localhost\n", encoding="utf-8")
        (ws / "other.txt").write_text("other\n", encoding="utf-8")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, caps, task_scope=None):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name="a", caps=caps, ctx=ctx, branch="main",
                                 task_scope=task_scope)

    def _read(self, pid, path):
        return asyncio.run(self.kernel.syscall(pid, "fs.read", {"path": path}))

    def test_within_scope_allowed(self):
        pcb = self._spawn(["fs.*"], task_scope=["/main/workspace/"])
        res = self._read(pcb.pid, "/main/workspace/hosts")
        self.assertTrue(res.ok, res.error)

    def test_outside_scope_denied(self):
        pcb = self._spawn(["fs.*"], task_scope=["/main/workspace/hosts"])
        res = self._read(pcb.pid, "/main/workspace/other.txt")
        self.assertFalse(res.ok)
        self.assertIn("outside task scope", res.error)

    def test_prefix_must_match_from_start(self):
        pcb = self._spawn(["fs.*"], task_scope=["/main/workspace/other"])
        res = self._read(pcb.pid, "/main/workspace/hosts")
        self.assertFalse(res.ok)
        self.assertIn("outside task scope", res.error)

    def test_no_scope_unrestricted(self):
        pcb = self._spawn(["fs.*"])
        res = self._read(pcb.pid, "/main/workspace/other.txt")
        self.assertTrue(res.ok, res.error)

    def test_pathless_tools_unaffected(self):
        pcb = self._spawn(["sys.*"], task_scope=["/nowhere/"])
        res = asyncio.run(self.kernel.syscall(pcb.pid, "sys.info", {}))
        self.assertTrue(res.ok, res.error)

    def test_fork_child_inherits_scope(self):
        parent = self._spawn(["fs.*"], task_scope=["/main/workspace/hosts"])
        child = parent.fork_child("child", ["fs.*"], "main",
                                  __import__("laos.brain", fromlist=["ScriptedBrain"])
                                  .ScriptedBrain(branch="main"))
        self.assertEqual(child.pcb.task_scope, ["/main/workspace/hosts"])
        res = self._read(child.pcb.pid, "/main/workspace/other.txt")
        self.assertIn("outside task scope", res.error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_scope -v`
Expected: FAIL —— `TypeError: spawn() got an unexpected keyword argument 'task_scope'`

- [ ] **Step 3: 实现**

3a. `PCB` 增加 `task_scope: list[str] | None = None`（`risk_cap` 之后）；`spawn` 签名加 `task_scope: list[str] | None = None`，PCB 构造传入，spawn 审计事件加 `"task_scope": task_scope`。

3b. `syscall` 在能力检查（`_effective_allows`）通过后、`validate_args` 之前插入 Task 1 Interfaces 里的检查块。

3c. `laos/agent.py` `fork_child` 的 `kernel.spawn(...)` 增加 `task_scope=self.pcb.task_scope`（与 risk_cap 并列；docstring 补一句"任务边界随血统继承，不因分支放宽"）。

- [ ] **Step 4: 跑全量测试**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿 = 实测基线 + 6）

- [ ] **Step 5: Commit**

```bash
git add laos/kernel.py laos/agent.py tests/test_scope.py
git commit -m "feat(laos): intent-driven task_scope path narrowing"
```

---

### Task 2: demo + README

**Files:**
- Modify: `bin/laosd.py`（guest spawn 加 `task_scope=["/exp-A/"]` 演示——guest 本来只有 sys.*，改用 ops-agent？不动 demo 主流程：给 `new_agent` 加 `task_scope` 参数透传，guest 设 `["/exp-A/"]`，输出行打印）、`README.md`（§6 新增意图收窄说明并入能力表行、§7 spawn 说明）

- [ ] **Step 1: bin/laosd.py**：`new_agent` 增 `task_scope=None` 形参并透传 `kernel.spawn`；guest 的 `new_agent(...)` 调用加 `task_scope=["/exp-A/"]`；打印行（spawn 处）追加 `scope={pcb.task_scope}`。

- [ ] **Step 2: README**：§6 能力表相关行（或表后注）补一句"spawn 支持 `task_scope` 虚拟路径前缀白名单，能力随任务意图收窄（Oracle Labs 思想）"；§8 不加新 env（无 env）；测试数改实测。

- [ ] **Step 3: 全量回归 + 手工验收**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿）
Run: `$PY bin/laosd.py 2>&1 | grep "scope="`（guest 行出现 `scope=['/exp-A/']`）

- [ ] **Step 4: Commit**

```bash
git add bin/laosd.py README.md
git commit -m "docs(laos): task_scope demo and README"
```

## 验收清单

- [ ] 全量测试全绿（基线 + 6）
- [ ] demo guest 行显示 task_scope
- [ ] 本计划恰 2 个 commit
