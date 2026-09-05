# Irreversibility Budget 2.0（车队级风险记账与准入控制）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 laos 现有的"每 syscall 计 1 的全局不可逆计数"升级为论文《The Irreversibility Budget: Fleet-Level Risk Accounting and Admission Control for Agent Operating Systems》（AgenticOS @ SOSP 2026，MPI-SWS）的核心机制：**按工具加权的风险定价、agent/车队两级账本、spawn 时准入控制（保留水位）**，并配 `laosctl budget` 观测面。

**Architecture:** 新增 `FleetLedger`（车队账本：总预算、保留水位、已花、按 pid/按 tool 两个直方图）挂在 `AgentKernel.risk`；`ToolSpec` 增加 `irreversibility_cost` 字段（驱动用装饰器参数标注）；`kernel.syscall` 的不可逆闸门改为三层检查——车队剩余 ≥ cost → agent 风险帽 ≥ 已花+cost → high risk 人类确认——全部通过才按 cost 记账（kill/abort 不退款：kill 不能撤销已发生的不可逆副作用，这正是"不可逆"的定义）；`kernel.spawn` 增加准入检查（剩余 ≤ 保留水位时拒绝新进程并写审计）。`irreversibility_budget` 旧属性保留为兼容 property（读写映射到 FleetLedger），现有 `tests/test_irreversibility.py` 三项测试不改一字继续通过。

**Tech Stack:** Python 3.10+ 标准库，零第三方依赖。复用现有 `mcp.py`（ToolSpec/MCPServer.tool）、`kernel.py`（syscall 网关/审计/spawn）、`bin/laosctl.py`（records 驱动的子命令模式）。测试 `unittest`，`python -m unittest discover -s tests`。

**Spec:** `docs/research/2026-09-05-agentos-next-steps.md` §一.2/§二#1（本计划的调研依据）；论文名单见 [AgenticOS @ SOSP 2026](https://os-for-agent.github.io/)。前序计划：`docs/superpowers/plans/2026-09-05-*` 系列首篇。

## Global Constraints

- 零第三方依赖，stdlib only。
- 不破坏既有 **68** 项测试（`python -m unittest discover -s tests`，master 28d1a3e 基线全绿）；新增测试放独立文件 `tests/test_risk.py`，`tests/test_irreversibility.py` **一个字都不能改**（它是兼容契约）。
- errno 原样透传；新增失败码：`EACCES`（agent 风险帽 / 车队预算 / 准入拒绝）。
- 非 Linux 降级原则不受影响（本计划与平台无关）。
- 本机（Windows + Git Bash）解释器：`/c/Users/yaoyue/AppData/Roaming/uv/python/cpython-3.12.14-windows-x86_64-none/python.exe`（`python`/`py` 不可用），下文记 `$PY`。
- commit 粒度：每 task 一个 commit，消息 `feat(laos): <task 名>`。
- 测试总数预期每 task 递增（68 → 78），以实测为准（lesson from R7）。

---

## 现状关键事实（执行者必读）

- `laos/mcp.py:34-52`：`ToolSpec(name, description, input_schema, reversible=True, risk="low")`；`MCPServer.tool` 装饰器（`mcp.py:86-99`）签名 `(name, description, schema=None, reversible=True, risk="low")`。
- `laos/kernel.py:70-88`：`PCB` 字段 pid/name/caps/state/parent/created_at/ctx/stats/branch/budget；`stats = {"syscalls": 0, "denied": 0, "tokens": 0}`；`to_dict()` 弹出 ctx 并覆写 caps。
- `laos/kernel.py:118-144`：`AgentKernel.__init__(..., irreversibility_budget=None, confirm=None)`，`self.irreversibility_budget = irreversibility_budget or int(env LAOS_IRREV_BUDGET 默认 "3")`。
- `laos/kernel.py:186-208`：`spawn(name, caps, ctx, branch=None, parent=0, budget=None)`。
- `laos/kernel.py:240-266`：不可逆闸门——`if not _spec.reversible:` 预算 ≤0 → `EACCES: irreversibility budget exhausted`；`risk=="high"` → confirm；通过后 `self.irreversibility_budget -= 1`。
- `drivers/drv_proc.py:63-74`：`proc.exec` 已标注 `reversible=False, risk="high"`。
- `tests/test_irreversibility.py`：直接构造 `PCB(pid=1, ...)` 塞进 `k.procs` 绕过 spawn；`test_budget_depletes` 通过 `self.k.irreversibility_budget = 0` 置零 —— **兼容 property 必须支持写**。
- `bin/laosctl.py:107-119`：`main()` 的 choices 列表 + 分发表模式。
- 测试基线 68（10 个测试文件），全绿，Windows 上 skipped=3（Linux-only）。

---

### Task 1: FleetLedger + 加权记账（兼容层不动旧测试）

**Files:**
- Create: `laos/risk.py`
- Modify: `laos/mcp.py:34-52`（ToolSpec 加字段）、`laos/mcp.py:86-99`（tool 装饰器加参数）、`laos/kernel.py:13-26`（import）、`laos/kernel.py:118-144`（__init__ 换账本 + 兼容 property）、`laos/kernel.py:240-266`（闸门改加权）、`drivers/drv_proc.py:63-74`（exec 标价 3）
- Test: `tests/test_risk.py`（新建）

**Interfaces:**
- Produces:
  - `FleetLedger(budget: int, reserve: int = 1)`：`.remaining -> int`（property）、`.can_admit() -> bool`（remaining > reserve）、`.charge(pid: int, tool: str, cost: int) -> None`；属性 `.spent: int`、`.per_agent: dict[int,int]`、`.per_tool: dict[str,int]`。
  - `ToolSpec.irreversibility_cost: int = 1`；`MCPServer.tool(..., irreversibility_cost: int = 1)`。
  - `AgentKernel.risk: FleetLedger`；兼容 property `AgentKernel.irreversibility_budget`（get → `risk.remaining`，set → `risk.budget`）。
  - 审计新事件：`{"t", "event": "risk_spend", "pid", "tool", "cost", "agent_spent", "fleet_spent"}`。
- Consumes: 现有 `ToolSpec.reversible/risk`、`kernel._deny`、审计通道。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_risk.py
"""Irreversibility Budget 2.0 —— 车队级风险记账（加权、两级账本、准入控制）。

    python -m unittest tests.test_risk -v
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.kernel import AgentKernel, CapabilitySet, PCB  # noqa: E402
from laos.mcp import ToolSpec  # noqa: E402
from laos.risk import FleetLedger  # noqa: E402


def _spec(name: str = "proc.exec", cost: int = 3, risk: str = "low") -> ToolSpec:
    return ToolSpec(name, "desc",
                    {"type": "object", "properties": {"x": {"type": "string"}}},
                    reversible=False, risk=risk, irreversibility_cost=cost)


class TestFleetLedger(unittest.TestCase):
    def test_remaining_and_admission(self):
        led = FleetLedger(budget=5, reserve=1)
        self.assertEqual(led.remaining, 5)
        self.assertTrue(led.can_admit())
        led.charge(pid=1, tool="proc.exec", cost=3)
        self.assertEqual(led.remaining, 2)
        self.assertEqual(led.spent, 3)
        self.assertEqual(led.per_agent, {1: 3})
        self.assertEqual(led.per_tool, {"proc.exec": 3})
        led.charge(pid=2, tool="proc.exec", cost=2)
        self.assertFalse(led.can_admit())  # remaining=0 <= reserve=1

    def test_charge_accumulates(self):
        led = FleetLedger(budget=10)
        led.charge(1, "t1", 1)
        led.charge(1, "t2", 2)
        led.charge(2, "t1", 3)
        self.assertEqual(led.spent, 6)
        self.assertEqual(led.per_agent, {1: 3, 2: 3})
        self.assertEqual(led.per_tool, {"t1": 4, "t2": 2})


class TestWeightedGate(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.k = AgentKernel(Path(self.td.name) / "var", audit_mode="w",
                             confirm=lambda op: True)

    def tearDown(self):
        self.k.shutdown()
        self.td.cleanup()

    def _mount(self, spec: ToolSpec):
        self.k.syscall_table[spec.name] = ("proc", spec)
        self.k.procs[1] = PCB(pid=1, name="a", caps=CapabilitySet(["proc.*"]),
                              budget=None)

    def test_default_cost_is_one(self):
        self.assertEqual(ToolSpec("x", "d", {}).irreversibility_cost, 1)
        self.assertEqual(ToolSpec("x", "d", {}, irreversibility_cost=3).irreversibility_cost, 3)

    def test_weighted_charge(self):
        self._mount(_spec(cost=3))
        asyncio.run(self.k.syscall(1, "proc.exec", {"x": "y"}))
        self.assertEqual(self.k.risk.spent, 3)          # 按标注价记账，不是 1
        self.assertEqual(self.k.risk.per_tool["proc.exec"], 3)
        self.assertEqual(self.k.procs[1].stats["risk"], 3)

    def test_fleet_exhaustion_denies(self):
        self.k.risk.budget = 2
        self._mount(_spec(cost=3))
        res = asyncio.run(self.k.syscall(1, "proc.exec", {"x": "y"}))
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)
        self.assertIn("fleet risk budget exhausted", res.error)
        self.assertEqual(self.k.risk.spent, 0)          # 拒绝不计费

    def test_risk_spend_audit_event(self):
        self._mount(_spec(cost=3))
        asyncio.run(self.k.syscall(1, "proc.exec", {"x": "y"}))
        events = [r for r in self.k.audit.records if r.get("event") == "risk_spend"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["cost"], 3)
        self.assertEqual(events[0]["fleet_spent"], 3)
        self.assertEqual(events[0]["agent_spent"], 3)

    def test_legacy_budget_property_roundtrip(self):
        # 兼容契约：test_irreversibility.py 通过该属性置零预算
        self.k.irreversibility_budget = 0
        self.assertEqual(self.k.risk.budget, 0)
        self.assertEqual(self.k.irreversibility_budget, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_risk -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'laos.risk'`（且 ToolSpec 无 `irreversibility_cost`）

- [ ] **Step 3: 实现 laos/risk.py**

```python
# laos/risk.py
"""FleetLedger —— 车队级不可逆风险账本。

对应《The Irreversibility Budget: Fleet-Level Risk Accounting and Admission
Control for Agent Operating Systems》（AgenticOS @ SOSP 2026, MPI-SWS）：
不可逆操作按工具定价，agent/车队两级记账，spawn 时做准入控制
（剩余预算必须高于保留水位，留给已准入 agent 应急）。

记账语义：kill/abort **不退款** —— 不可逆操作的定义就是"无法通过
终止进程撤销"；退款只属于显式回滚机制（分支 abort 只回滚分支内
可逆写，而那些写在写时就没有计费）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FleetLedger:
    """车队总预算 + 保留水位 + 两级（pid / tool）支出直方图。"""

    budget: int
    reserve: int = 1
    spent: int = 0
    per_agent: dict[int, int] = field(default_factory=dict)
    per_tool: dict[str, int] = field(default_factory=dict)

    @property
    def remaining(self) -> int:
        return self.budget - self.spent

    def can_admit(self) -> bool:
        """准入控制：剩余预算必须严格高于保留水位。"""
        return self.remaining > self.reserve

    def charge(self, pid: int, tool: str, cost: int) -> None:
        self.spent += cost
        self.per_agent[pid] = self.per_agent.get(pid, 0) + cost
        self.per_tool[tool] = self.per_tool.get(tool, 0) + cost
```

- [ ] **Step 4: 修改 laos/mcp.py（ToolSpec + 装饰器）**

`ToolSpec`（`mcp.py:34-52`）改为：

```python
@dataclass
class ToolSpec:
    """一个 MCP tool 的描述，等价于内核里的一条 syscall 声明。"""

    name: str
    description: str
    input_schema: dict
    reversible: bool = True
    risk: str = "low"
    irreversibility_cost: int = 1  # 不可逆操作的风险定价（Irreversibility Budget）

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "reversible": self.reversible,
            "risk": self.risk,
            "irreversibilityCost": self.irreversibility_cost,
        }
```

`MCPServer.tool` 装饰器（`mcp.py:86-99`）签名与 ToolSpec 构造改为：

```python
    def tool(self, name: str, description: str, schema: dict | None = None,
             reversible: bool = True, risk: str = "low",
             irreversibility_cost: int = 1):
        def deco(fn: Callable[..., str]):
            self._tools[name] = (
                ToolSpec(
                    name, description,
                    schema or {"type": "object", "properties": {}},
                    reversible=reversible, risk=risk,
                    irreversibility_cost=irreversibility_cost,
                ),
                fn,
            )
            return fn

        return deco
```

- [ ] **Step 5: 修改 laos/kernel.py（import / __init__ / 兼容 property / 闸门）**

5a. import 区（`kernel.py:22-26`）增加：

```python
from .risk import FleetLedger
```

5b. `__init__` 中（`kernel.py:138-142`）把

```python
        self.irreversibility_budget = (
            irreversibility_budget
            if irreversibility_budget is not None
            else int(os.environ.get("LAOS_IRREV_BUDGET", "3"))
        )
```

替换为：

```python
        risk_budget = (
            irreversibility_budget
            if irreversibility_budget is not None
            else int(os.environ.get("LAOS_RISK_BUDGET")
                     or os.environ.get("LAOS_IRREV_BUDGET")
                     or "3")
        )
        self.risk = FleetLedger(
            budget=risk_budget,
            reserve=int(os.environ.get("LAOS_RISK_RESERVE", "1")),
        )
```

并在 `__init__` 结束（`self.boot_at = time.time()` 之后）加兼容 property：

```python
    # -- 兼容层：旧接口 irreversibility_budget 读写映射到车队账本 -----------
    @property
    def irreversibility_budget(self) -> int:
        return self.risk.remaining

    @irreversibility_budget.setter
    def irreversibility_budget(self, v: int) -> None:
        self.risk.budget = v
```

5c. 闸门（`kernel.py:242-265`）整段替换为：

```python
        # 不可逆闸门 2.0：车队级风险记账 + 每 agent 风险帽（Irreversibility Budget）
        if not _spec.reversible:
            cost = max(1, _spec.irreversibility_cost)
            if self.risk.remaining < cost:
                return self._deny(pcb, tool, args, started,
                                  "EACCES: fleet risk budget exhausted")
            if pcb.risk_cap is not None and pcb.stats["risk"] + cost > pcb.risk_cap:
                return self._deny(pcb, tool, args, started,
                                  "EACCES: agent risk cap exceeded")
            if _spec.risk == "high" and not self.confirm(
                {"tool": tool, "args": args, "risk": _spec.risk}
            ):
                return self._deny(pcb, tool, args, started,
                                  "EACCES: irreversible operation requires confirmation")
            self.risk.charge(pcb.pid, tool, cost)
            pcb.stats["risk"] += cost
            self.audit.write(
                {"t": time.time(), "event": "risk_spend", "pid": pcb.pid,
                 "tool": tool, "cost": cost,
                 "agent_spent": pcb.stats["risk"], "fleet_spent": self.risk.spent}
            )
```

- [ ] **Step 6: 修改 PCB 与 drivers/drv_proc.py**

6a. `PCB`（`kernel.py:70-88`）：`stats` 默认值改为

```python
    stats: dict = field(default_factory=lambda: {"syscalls": 0, "denied": 0, "tokens": 0, "risk": 0})
```

并新增字段（放在 `budget` 之后）：

```python
    risk_cap: int | None = None  # 本 agent 的风险帽（Irreversibility Budget）
```

6b. `drivers/drv_proc.py` 的 `proc.exec` 装饰器（`drv_proc.py:63-73`）加价：

```python
@drv.tool(
    "proc.exec",
    "执行一条白名单内的命令（只读倾向，禁止危险操作）",
    {
        "type": "object",
        "properties": {"cmdline": {"type": "string", "description": "要执行的命令行"}},
        "required": ["cmdline"],
    },
    reversible=False,
    risk="high",
    irreversibility_cost=3,
)
```

- [ ] **Step 7: 跑全量测试**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 74 tests ... OK`（68 旧 + 6 新；`tests/test_irreversibility.py` 三项**不改一字**必须仍然通过——兼容 property 的存在意义）。

- [ ] **Step 8: Commit**

```bash
git add laos/risk.py laos/mcp.py laos/kernel.py drivers/drv_proc.py tests/test_risk.py
git commit -m "feat(laos): FleetLedger weighted risk accounting (Irreversibility Budget 2.0)"
```

---

### Task 2: 每 agent 风险帽（spawn 参数 + 闸门联动）

**Files:**
- Modify: `laos/kernel.py:186-208`（spawn 签名 + PCB 构造）
- Test: `tests/test_risk.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `FleetLedger`、`PCB.risk_cap`、`pcb.stats["risk"]`。
- Produces: `AgentKernel.spawn(..., risk_cap: int | None = None)` —— 写入 `PCB.risk_cap`；审计 spawn 事件增加 `"risk_cap"` 字段。

- [ ] **Step 1: 追加失败测试（tests/test_risk.py 末尾新类）**

```python
class TestAgentRiskCap(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.k = AgentKernel(Path(self.td.name) / "var", audit_mode="w",
                             confirm=lambda op: True)
        self.k.syscall_table["proc.exec"] = ("proc", _spec(cost=2))
        self.td2 = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.k.shutdown()
        self.td.cleanup()
        self.td2.cleanup()

    def _spawn(self, risk_cap):
        return self.k.spawn(name="a", caps=["proc.*"], ctx=object(),
                            risk_cap=risk_cap)

    def test_cap_exceeded_denies_before_confirm(self):
        pcb = self._spawn(risk_cap=1)  # 帽 1 < cost 2
        res = asyncio.run(self.k.syscall(pcb.pid, "proc.exec", {"x": "y"}))
        self.assertFalse(res.ok)
        self.assertIn("agent risk cap exceeded", res.error)
        self.assertEqual(self.k.risk.spent, 0)

    def test_cap_boundary_allows(self):
        pcb = self._spawn(risk_cap=2)  # 帽 == cost，恰好放行
        res = asyncio.run(self.k.syscall(pcb.pid, "proc.exec", {"x": "y"}))
        self.assertNotIn("EACCES", res.error)   # 无真驱动，落到 EIO
        self.assertIn("EIO", res.error)
        self.assertEqual(pcb.stats["risk"], 2)

    def test_cumulative_spend_hits_cap(self):
        pcb = self._spawn(risk_cap=3)
        asyncio.run(self.k.syscall(pcb.pid, "proc.exec", {"x": "1"}))   # 0+2 <= 3，计 2
        res = asyncio.run(self.k.syscall(pcb.pid, "proc.exec", {"x": "2"}))
        self.assertIn("agent risk cap exceeded", res.error)  # 2+2 > 3
        self.assertEqual(self.k.risk.per_agent[pcb.pid], 2)

    def test_no_cap_is_unlimited(self):
        pcb = self._spawn(risk_cap=None)
        res = asyncio.run(self.k.syscall(pcb.pid, "proc.exec", {"x": "y"}))
        self.assertNotIn("EACCES", res.error)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_risk -v`
Expected: FAIL —— `TypeError: spawn() got an unexpected keyword argument 'risk_cap'`

- [ ] **Step 3: 实现**

`spawn`（`kernel.py:186-208`）签名加 `risk_cap: int | None = None`，PCB 构造传入 `risk_cap=risk_cap`，spawn 审计事件加 `"risk_cap": risk_cap`：

```python
    def spawn(
        self,
        name: str,
        caps: list[str],
        ctx: Any,
        branch: str | None = None,
        parent: int = 0,
        budget: int | None = None,
        risk_cap: int | None = None,
    ) -> PCB:
        self._next_pid += 1
        pcb = PCB(
            pid=self._next_pid,
            name=name,
            caps=CapabilitySet(caps),
            ctx=ctx,
            branch=branch,
            parent=parent,
            budget=budget,
            risk_cap=risk_cap,
        )
        self.procs[pcb.pid] = pcb
        self.scheduler.register(pcb.pid, token_budget=self._agent_token_budget)
        self.audit.write(
            {"t": time.time(), "event": "spawn", "pid": pcb.pid, "name": name,
             "caps": caps, "risk_cap": risk_cap}
        )
        return pcb
```

- [ ] **Step 4: 跑全量测试**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 78 tests ... OK`

- [ ] **Step 5: Commit**

```bash
git add laos/kernel.py tests/test_risk.py
git commit -m "feat(laos): per-agent risk cap on spawn"
```

---

### Task 3: spawn 准入控制（保留水位）

**Files:**
- Modify: `laos/kernel.py:186-208`（spawn 入口加准入检查）
- Test: `tests/test_risk.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `FleetLedger.can_admit()`。
- Produces: spawn 在 `remaining <= reserve` 时 **raise PermissionError**（消息含 remaining/reserve），并写审计事件 `{"t", "event": "admission", "name", "decision": "deny", "fleet_remaining"}`；正常 spawn 的审计事件加 `"fleet_remaining"`（供事后重建账本水位）。

- [ ] **Step 1: 追加失败测试**

```python
class TestAdmissionControl(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.k = AgentKernel(Path(self.td.name) / "var", audit_mode="w",
                             irreversibility_budget=2, confirm=lambda op: True)
        # remaining=2, reserve=1：2 > 1 → 首个 agent 准入

    def tearDown(self):
        self.k.shutdown()
        self.td.cleanup()

    def test_admit_when_above_reserve(self):
        pcb = self.k.spawn(name="a", caps=["sys.*"], ctx=object())
        self.assertIn(pcb.pid, self.k.procs)

    def test_deny_when_at_reserve(self):
        self.k.risk.budget = 1  # remaining=1 <= reserve=1
        with self.assertRaises(PermissionError) as cm:
            self.k.spawn(name="b", caps=["sys.*"], ctx=object())
        self.assertIn("fleet risk reserve", str(cm.exception))
        denies = [r for r in self.k.audit.records if r.get("event") == "admission"]
        self.assertEqual(len(denies), 1)
        self.assertEqual(denies[0]["decision"], "deny")

    def test_spend_then_deny(self):
        self.k.syscall_table["t.op"] = ("proc", _spec(name="t.op", cost=1))
        self.k.procs[1] = PCB(pid=1, name="a", caps=CapabilitySet(["*"]), budget=None)
        asyncio.run(self.k.syscall(1, "t.op", {"x": "y"}))  # remaining 2->1
        with self.assertRaises(PermissionError):
            self.k.spawn(name="b", caps=["sys.*"], ctx=object())  # 1 <= 1

    def test_admit_event_records_fleet_remaining(self):
        self.k.spawn(name="a", caps=["sys.*"], ctx=object())
        spawns = [r for r in self.k.audit.records if r.get("event") == "spawn"]
        self.assertEqual(spawns[0]["fleet_remaining"], 2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_risk.TestAdmissionControl -v`
Expected: FAIL —— `test_deny_when_at_reserve` 与 `test_spend_then_deny` 不抛 PermissionError；spawn 事件无 `fleet_remaining` 字段。

- [ ] **Step 3: 实现（spawn 入口）**

在 `spawn` 方法体最前（`self._next_pid += 1` 之前）插入：

```python
        if not self.risk.can_admit():
            self.audit.write(
                {"t": time.time(), "event": "admission", "name": name,
                 "decision": "deny", "fleet_remaining": self.risk.remaining}
            )
            raise PermissionError(
                f"EACCES: fleet risk reserve not met "
                f"(remaining={self.risk.remaining}, reserve={self.risk.reserve})"
            )
```

并把 spawn 审计事件改为：

```python
        self.audit.write(
            {"t": time.time(), "event": "spawn", "pid": pcb.pid, "name": name,
             "caps": caps, "risk_cap": risk_cap,
             "fleet_remaining": self.risk.remaining}
        )
```

- [ ] **Step 4: 跑全量测试**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 82 tests ... OK`（78 + 4）。**注意**：`KernelTestCase` 每次 setUp 新建 kernel（预算 3 > 保留 1），全部照常准入；若任何既有测试在 spawn 处爆 PermissionError，说明该测试在同一 kernel 上先花光了预算——不要放宽准入，检查是不是测试把不可逆调用挪到了 spawn 之后（顺序即语义）。

- [ ] **Step 5: Commit**

```bash
git add laos/kernel.py tests/test_risk.py
git commit -m "feat(laos): spawn-time admission control with fleet risk reserve"
```

---

### Task 4: laosctl budget 子命令

**Files:**
- Modify: `bin/laosctl.py:76-105`（新增 cmd_budget）、`bin/laosctl.py:107-119`（choices + 分发表）
- Test: `tests/test_risk.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `risk_spend` 审计事件、Task 3 的 `admission` 事件。
- Produces: `python bin/laosctl.py budget [--file audit.jsonl]` —— 打印车队总支出、per-pid、per-tool 三个表；无记录时打印提示。

- [ ] **Step 1: 追加失败测试**

```python
class TestLaosctlBudget(unittest.TestCase):
    def _records(self):
        return [
            {"t": 1, "event": "risk_spend", "pid": 1001, "tool": "proc.exec",
             "cost": 3, "agent_spent": 3, "fleet_spent": 3},
            {"t": 2, "event": "risk_spend", "pid": 1002, "tool": "t.op",
             "cost": 1, "agent_spent": 1, "fleet_spent": 4},
            {"t": 3, "event": "admission", "name": "late", "decision": "deny",
             "fleet_remaining": 1},
            {"t": 4, "event": "spawn", "pid": 1003, "name": "n", "caps": [],
             "risk_cap": None, "fleet_remaining": 4},
        ]

    def test_budget_report(self):
        import io
        import contextlib
        from bin.laosctl import cmd_budget  # laosctl 以脚本存放但可导入

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_budget(self._records(), None)
        out = buf.getvalue()
        self.assertIn("fleet spent: 4", out)
        self.assertIn("1001", out)
        self.assertIn("proc.exec", out)
        self.assertIn("denied admissions: 1", out)
```

注意：`bin/` 不是包（无 `__init__.py`）。在 `tests/test_risk.py` 的 import 区用路径注入：

```python
sys.path.insert(0, str(REPO / "bin"))
```

并把上面的导入改为 `from laosctl import cmd_budget`（`bin/laosctl.py` 无扩展名依赖问题，模块名即 `laosctl`）。

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_risk.TestLaosctlBudget -v`
Expected: FAIL —— `ImportError: cannot import name 'cmd_budget'`

- [ ] **Step 3: 实现（bin/laosctl.py）**

在 `cmd_ps` 之后新增：

```python
def cmd_budget(records: list[dict], args) -> None:
    """Irreversibility Budget 2.0 的车队风险账本回放。"""
    spent = 0
    per_agent: Counter = Counter()
    per_tool: Counter = Counter()
    denied_admissions = 0
    for r in records:
        if r.get("event") == "risk_spend":
            spent += r["cost"]
            per_agent[r["pid"]] += r["cost"]
            per_tool[r["tool"]] += r["cost"]
        elif r.get("event") == "admission" and r.get("decision") == "deny":
            denied_admissions += 1
    print(f"fleet spent: {spent}")
    print(f"{'pid':<10}{'risk_spent':>12}")
    for pid, s in per_agent.most_common():
        print(f"{pid:<10}{s:>12}")
    print(f"\n{'tool':<16}{'risk_spent':>12}")
    for tool, s in per_tool.most_common():
        print(f"{tool:<16}{s:>12}")
    print(f"\n  denied admissions: {denied_admissions}")
```

`main()` 的 choices 与分发表各加 `"budget"`。

- [ ] **Step 4: 跑全量测试**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 83 tests ... OK`

- [ ] **Step 5: Commit**

```bash
git add bin/laosctl.py tests/test_risk.py
git commit -m "feat(laos): laosctl budget subcommand (fleet risk ledger replay)"
```

---

### Task 5: Demo 接线 + README 收尾

**Files:**
- Modify: `bin/laosd.py`（第 6 节打印风险账本）、`README.md`（§6 不可逆预算行、§8 环境变量、§7 目录）
- Test: 全量回归（无新测试）

**Interfaces:**
- Consumes: Task 1-4 全部产物。
- Produces: demo 第 6 节打印 `风险账本`；README 与实现一致。

- [ ] **Step 1: bin/laosd.py 第 6 节**

在 `print(f"  审计记录 : ...")` 行之后插入：

```python
    print(f"  风险账本   : spent={kernel.risk.spent} remaining={kernel.risk.remaining} "
          f"(budget={kernel.risk.budget}, reserve={kernel.risk.reserve})")
```

- [ ] **Step 2: README §6「不可逆操作预算」行替换为**

| **不可逆操作预算** | ~~只有 syscall 次数预算（EDQUOT）~~ → **Irreversibility Budget 2.0**：按工具定价（`irreversibility_cost`）+ agent 风险帽 + 车队账本（`FleetLedger`）+ spawn 准入控制（保留水位） | 探索期免计费、commit 时结算（Externalization Barriers 式延迟定价） |

- [ ] **Step 3: README §8 环境变量表追加两行**

| `LAOS_RISK_BUDGET` | `LAOS_IRREV_BUDGET` 或 `3` | 车队级不可逆风险总预算 |
| `LAOS_RISK_RESERVE` | `1` | spawn 准入保留水位（剩余预算须严格高于此值） |

- [ ] **Step 4: README §7 目录结构 laos/ 段补一行**

```
    risk.py       FleetLedger：车队级不可逆风险账本（加权/两级记账/准入水位）
```

- [ ] **Step 5: 全量回归 + 手工验收**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 83 tests ... OK`

Run: `$PY bin/laosd.py 2>&1 | grep "风险账本"`
Expected: 出现 `风险账本   : spent=... remaining=... (budget=3, reserve=1)` 一行。**数字取决于 confirm 模式**：非交互运行（管道）下 `_cli_confirm` 遇 EOF 拒绝，`proc.exec` 在确认关就被拒——**拒绝不计费**（spent=0）；交互输入 `y` 才过闸并计 cost=3。这正是论文语义：admission ≠ spend。

- [ ] **Step 6: Commit**

```bash
git add bin/laosd.py README.md
git commit -m "docs(laos): Irreversibility Budget 2.0 in demo report and README"
```

---

## 验收清单（全部完成后核对）

- [ ] `python -m unittest discover -s tests` 83 项全绿（Windows；Linux 上 skipped 同为 3）
- [ ] `tests/test_irreversibility.py` 三个用例零改动通过（兼容契约）
- [ ] `bin/laosd.py` 第 6 节出现风险账本；`bin/laosctl.py budget` 能回放
- [ ] README §6/§7/§8 与实现一致
- [ ] `git log --oneline` 本计划恰 5 个 commit
