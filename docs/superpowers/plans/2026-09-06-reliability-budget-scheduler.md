# 可靠性预算调度（Patient Bytes 启发）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `AgentScheduler` 加**每 agent 可靠性预算**：连续/累计失败（denial、EIO 等 `ok=False` 结果）消耗错误预算，耗尽即挂起（与 token 预算同机制）——让"一直把事办砸"的 agent 让出 LLM 时间片，对应《Patient Bytes: A Reliability-Budgeted Scheduler for Agentic LLM Workflows》（AgenticOS @ SOSP 2026）的预算化调度思想。

**Architecture:** `AgentScheduler.note_outcome(pid, ok)` 新增：失败递增该 pid 的可靠性消耗，达到 `err_budget`（env `LAOS_AGENT_ERR_BUDGET`，默认 3）即 `_suspended`（复用现有挂起机制，`_suspended_reason[pid]` 记录原因供观测）；成功不计费（Patient Bytes 的预算只管可靠性事件）。`kernel.syscall` 派发后调 `note_outcome`。观测：`AgentScheduler.snapshot()` 输出 per-pid 可靠性状态，demo 第 6 节打印。

**Tech Stack:** Python 3.10+ 标准库，零第三方依赖。

**Spec:** `docs/research/2026-09-05-agentos-next-steps.md` §二#6。

## Global Constraints

- 零第三方依赖；不破坏执行时基线测试（以实测为准）；新增测试放独立文件 `tests/test_relbudget.py`。
- 解释器 `$PY`（同前）；每 task 一个 commit；errno 不变。
- 兼容红线：既有测试里每个 kernel 的失败次数都远小于默认预算 3（逐一核对过：最多 1 次），挂起不得误伤。

## 现状关键事实

- `laos/scheduler.py`：`__init__` 有 `_prio/_budget/_used/_suspended/_last_served/_serve_tick`；`register(pid, priority, token_budget)`；`acquire` 检查 token 预算与轮转；`note_tokens(pid, n)` 超额挂起；`retire` 清理。
- `laos/kernel.py` `syscall` 派发后有 `result`（CallResult）与 `pcb`；`finally` 恢复 state。
- token 预算挂起先例：`note_tokens` 中 `if b is not None and self._used[pid] >= b: self._suspended.add(pid)`。

---

### Task 1: Scheduler 可靠性预算

**Files:**
- Modify: `laos/scheduler.py`
- Test: `tests/test_relbudget.py`（新建）

**Interfaces:**
- Produces: `AgentScheduler.register(pid, priority=0, token_budget=None, err_budget=None)`（新 kwarg，默认 None = 不限）；`note_outcome(pid, ok: bool) -> None`（ok=False 消耗 1，达 err_budget 挂起并记录 `_suspended_reason[pid] = "err-budget exhausted (n failures)"`）；`snapshot() -> list[dict]`（pid/priority/token_used/token_budget/err_used/err_budget/suspended/reason）；`_suspended_reason: dict[int,str]`。
- 语义：`retire(pid)` 同时清理 err 记账与 reason；`ok=True` 不消耗（但也不恢复——预算是累计的）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_relbudget.py
"""可靠性预算调度（Patient Bytes 启发）——失败耗尽即挂起。

    python -m unittest tests.test_relbudget -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.scheduler import AgentScheduler  # noqa: E402


class TestReliabilityBudget(unittest.TestCase):
    def test_failures_exhaust_budget_and_suspend(self):
        s = AgentScheduler()
        s.register(1, err_budget=2)
        s.note_outcome(1, False)
        self.assertNotIn(1, s._suspended)
        s.note_outcome(1, False)
        self.assertIn(1, s._suspended)
        self.assertIn("err-budget exhausted", s._suspended_reason[1])

    def test_success_does_not_consume(self):
        s = AgentScheduler()
        s.register(1, err_budget=1)
        for _ in range(10):
            s.note_outcome(1, True)
        self.assertNotIn(1, s._suspended)

    def test_no_budget_is_unlimited(self):
        s = AgentScheduler()
        s.register(1)  # err_budget 默认 None
        for _ in range(50):
            s.note_outcome(1, False)
        self.assertNotIn(1, s._suspended)

    def test_retire_cleans_err_bookkeeping(self):
        s = AgentScheduler()
        s.register(1, err_budget=2)
        s.note_outcome(1, False)
        s.retire(1)
        snap = {row["pid"]: row for row in s.snapshot()}
        self.assertNotIn(1, snap)

    def test_snapshot_shape(self):
        s = AgentScheduler()
        s.register(1, err_budget=3)
        s.note_outcome(1, False)
        row = s.snapshot()[0]
        self.assertEqual(row["pid"], 1)
        self.assertEqual(row["err_used"], 1)
        self.assertEqual(row["err_budget"], 3)
        self.assertFalse(row["suspended"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_relbudget -v`
Expected: FAIL —— `TypeError: register() got an unexpected keyword argument 'err_budget'`

- [ ] **Step 3: 实现（laos/scheduler.py）**

`__init__` 增加 `self._err_budget: dict[int, int | None] = {}`、`self._err_used: dict[int, int] = {}`、`self._suspended_reason: dict[int, str] = {}`；`register` 加 `err_budget: int | None = None` 并记录；`retire` 清理三处；新增：

```python
    def note_outcome(self, pid: int, ok: bool) -> None:
        """可靠性记账：ok=False 消耗 1 次错误预算，耗尽即挂起（Patient Bytes）。"""
        if pid not in self._err_used:
            return
        if ok:
            return
        self._err_used[pid] += 1
        b = self._err_budget.get(pid)
        if b is not None and self._err_used[pid] >= b:
            self._suspended.add(pid)
            self._suspended_reason[pid] = (
                f"err-budget exhausted ({self._err_used[pid]} failures)")

    def snapshot(self) -> list[dict]:
        return [
            {"pid": pid,
             "priority": self._prio.get(pid, 0),
             "token_used": self._used.get(pid, 0),
             "token_budget": self._budget.get(pid),
             "err_used": self._err_used.get(pid, 0),
             "err_budget": self._err_budget.get(pid),
             "suspended": pid in self._suspended,
             "reason": self._suspended_reason.get(pid)}
            for pid in self._prio
        ]
```

（`acquire` 的挂起检查已有——`if pid in self._suspended: return False`——无需改动。）

- [ ] **Step 4: 跑全量测试**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿 = 实测基线 + 5）

- [ ] **Step 5: Commit**

```bash
git add laos/scheduler.py tests/test_relbudget.py
git commit -m "feat(laos): per-agent reliability budget in scheduler (Patient Bytes)"
```

---

### Task 2: 内核接线 + demo + README

**Files:**
- Modify: `laos/kernel.py`（__init__ env + syscall 接线）、`bin/laosd.py`（第 6 节调度快照行）、`README.md`（§6 调度行、§7 scheduler.py 行、§8 env 行、测试数）
- Test: 全量回归

**Interfaces:**
- Consumes: Task 1 的 `note_outcome`/`snapshot`。
- Produces: `AgentKernel._agent_err_budget = int(env LAOS_AGENT_ERR_BUDGET 默认 "3") or None`（`or None` 使 "0" 表示不限）；`syscall` 派发成功返回前调 `self.scheduler.note_outcome(pid, result.ok)`（放在审计写入之后、return 之前——仅成功派发路径；`_deny` 路径不记账：能力/预算拒绝是内核裁决，不是 agent 的可靠性事件。注意：驱动返回的 `isError=True`（如 EDENIED）属于 agent 的失败尝试，`result.ok=False` 会记——这正是要的）。

- [ ] **Step 1: 实现（无新测试，全量回归守护）**

kernel.py `__init__`（`self._agent_token_budget` 行后）加：

```python
        self._agent_err_budget = int(os.environ.get("LAOS_AGENT_ERR_BUDGET", "3")) or None
```

`spawn` 的 `scheduler.register` 调用改为：

```python
        self.scheduler.register(pcb.pid, token_budget=self._agent_token_budget,
                                err_budget=self._agent_err_budget)
```

syscall 的成功派发路径（builtin 与 MCP 两条 return 之前各一次，或在审计写入后统一一处——实现者按代码实际结构选择**单一插入点**覆盖两条路径）加：

```python
        self.scheduler.note_outcome(pid, result.ok)
```

bin/laosd.py 第 6 节（`语义剖析` print 之后）加：

```python
    rows = kernel.scheduler.snapshot()
    suspended = [r for r in rows if r["suspended"]]
    print(f"  调度快照   : {len(rows)} agents, {len(suspended)} suspended")
    for r in rows:
        print(f"    pid={r['pid']} err={r['err_used']}/{r['err_budget']} "
              f"tokens={r['token_used']}{'' if not r['suspended'] else f' ({r['reason']})'}")
```

README：§6 调度行补"可靠性预算"；§7 `scheduler.py` 行改 `AgentScheduler：token/err 双预算轮转 + 快照`；§8 加 `LAOS_AGENT_ERR_BUDGET`（默认 3）行；测试数改为实测。

- [ ] **Step 2: 全量回归 + 手工验收**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿）
Run: `$PY bin/laosd.py 2>&1 | grep -A3 "调度快照"`（出现 per-pid 行）

- [ ] **Step 3: Commit**

```bash
git add laos/kernel.py bin/laosd.py README.md
git commit -m "feat(laos): reliability outcomes wired into kernel and demo report"
```

## 验收清单

- [ ] 全量测试全绿（基线 + 5）
- [ ] demo 第 6 节出现调度快照行
- [ ] 本计划恰 2 个 commit
