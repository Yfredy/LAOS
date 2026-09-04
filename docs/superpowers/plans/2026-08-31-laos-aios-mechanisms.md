# laos × AIOS 机制落地实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 AIOS 论文（arXiv:2403.16971）已验证的三大内核机制——LLM 推理调度、上下文抢占快照、跨 agent 访问控制——以**可强制**的方式实现进 laos，并补齐 AIOS 明确缺失的 L4 强制隔离层，使 laos 从"用户态薄内核（L2）"推进到"L2 语义层 + L4 强制层"。

**Architecture:** 复用现有 `kernel.syscall(pid, tool, args)` 网关（能力表 + 审计 + 预算），在其上叠加：① 参数校验层（堵 AIOS Tool Manager 无校验的洞）② 不可逆操作预算 + 人类确认（把 AIOS 的 `ask_permission` 提示升级为强制）③ 上下文抢占快照（受 AIOS Context Manager 启发）④ 公平调度器（受 AIOS Scheduler 启发，替代全局锁）⑤ 能力委派（把 AIOS 特权组升级为 capability，可委派不可提升）⑥ 强制隔离（补 AIOS 缺失的 L4）。laos 始终只做"语义层 + 强制层"，LLM 推理本身仍是黑盒 Brain，绝不重复 AIOS 的 LLM Core 批处理。

**Tech Stack:** Python 3.10+ 标准库，**零第三方依赖**。现有模块 `laos/{kernel,mcp,context,brain,agent,branch,sandbox}.py` 与 `drivers/{drv_fs,drv_proc,drv_sys}.py`。测试用 `unittest`，命令 `python -m unittest discover -s tests`。

**Spec:** `docs/research/aios-deep-dive-2026-08.md`（本报告依赖该调研结论，执行者需先读 §4–§7）。

## Global Constraints

- 零第三方依赖，禁止引入 `jsonschema`/`pydantic` 等；校验一律手写（`laos/validate.py`）。
- 强制力目标：语义检查在 `kernel.syscall` 网关内、由内核（非 Agent）执行；L4 隔离仅在 Linux 生效，Windows/macOS 通过 `IsolationReport` 降级并记录，不得抛错。
- errno 原样透传（不得套 `EIO`）；新校验错误用 `EINVAL`（参数）/ `EACCES`（需确认）/ `EPERM`（委派越权）。
- 所有 syscall 入口改动必须不破坏既有 26 项测试（`tests/test_laos.py`）；新增测试写在同目录独立文件。
- 跨 agent 能力委派满足"可委派不可提升"：子 agent 能力 ⊆ 父 agent 能力。
- 每次 commit 一个 task，消息形如 `feat(laos): <task 名>`。

---

### Task 1: 工具调用参数校验层

**为什么**：AIOS 的 Tool Manager **完全没有参数校验**（`address_request` 原样传入 `tool_params`）。laos 当前 `kernel.syscall` 也只在能力表放行后直接 dispatch，缺参/错参/路径穿越会被驱动内部异常吞掉成 `EIO`。补一层零依赖 schema 校验 + 路径穿越语义围栏。

**Files:**
- Create: `laos/validate.py`
- Modify: `laos/kernel.py:178-230`（`syscall` 入口在 capability 检查后插入校验）
- Test: `tests/test_validate.py`

**Interfaces:**
- Produces: `validate_args(schema: dict, args: dict) -> None`（抛 `ValidationError` 即失败）；`ValidationError(Exception)`。
- Consumes: 各 driver 的 `ToolSpec.input_schema`（drv_fs 已提供 `_SCHEMA_PATH` 等）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_validate.py
import unittest
from laos.validate import validate_args, ValidationError


class TestValidateArgs(unittest.TestCase):
    SCHEMA = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path"],
    }

    def test_missing_required(self):
        with self.assertRaises(ValidationError):
            validate_args(self.SCHEMA, {})

    def test_wrong_type(self):
        with self.assertRaises(ValidationError):
            validate_args(self.SCHEMA, {"path": 123})

    def test_bool_not_int(self):
        with self.assertRaises(ValidationError):
            validate_args({"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}, {"n": True})

    def test_enum(self):
        s = {"type": "object", "properties": {"m": {"type": "string", "enum": ["a", "b"]}}, "required": ["m"]}
        with self.assertRaises(ValidationError):
            validate_args(s, {"m": "c"})

    def test_path_traversal_blocked(self):
        with self.assertRaises(ValidationError):
            validate_args(self.SCHEMA, {"path": "../etc/passwd"})

    def test_ok(self):
        validate_args(self.SCHEMA, {"path": "/main/x"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests/test_validate.py -v`
Expected: `ModuleNotFoundError: No module named 'laos.validate'`

- [ ] **Step 3: 写最小实现**

```python
# laos/validate.py
"""零依赖最小 JSON-schema 校验 + 路径穿越语义围栏。

堵 AIOS Tool Manager 的洞：AIOS 把 tool_params 原样传入 tool.run，
既不校验类型也不校验路径；这里在 kernel.syscall 网关内补上，且校验由内核执行。
"""
from __future__ import annotations

import re


class ValidationError(Exception):
    pass


_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def validate_args(schema: dict, args: dict) -> None:
    if not schema or schema.get("type") != "object":
        return
    props = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in args:
            raise ValidationError(f"EINVAL: missing required arg '{key}'")
    for key, val in args.items():
        spec = props.get(key)
        if spec is None:
            continue
        _check_type(key, val, spec.get("type"))
        if "enum" in spec and val not in spec["enum"]:
            raise ValidationError(f"EINVAL: '{key}'={val!r} not in {spec['enum']}")
        if spec.get("type") == "string" and "pattern" in spec:
            if not re.search(spec["pattern"], str(val)):
                raise ValidationError(f"EINVAL: '{key}'={val!r} violates pattern")
        # 语义围栏：路径类字段禁止穿越（超越纯模式匹配，覆盖 jail 之前）
        if spec.get("type") == "string" and isinstance(val, str):
            if ".." in val or val.startswith("../") or "/.." in val:
                raise ValidationError(f"EPERM: path traversal in '{key}'")


def _check_type(key: str, val, type_: str | None) -> None:
    if type_ is None:
        return
    expect = _TYPES.get(type_)
    if expect is None:
        return
    # bool 是 int 子类，单独排除
    if type_ == "integer" and isinstance(val, bool):
        raise ValidationError(f"EINVAL: '{key}' must be integer")
    if not isinstance(val, expect):
        raise ValidationError(f"EINVAL: '{key}' must be {type_}, got {type(val).__name__}")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests/test_validate.py -v`
Expected: `Ran 6 tests ... OK`

- [ ] **Step 5: 接入 kernel.syscall 网关并回归**

在 `laos/kernel.py` 顶部加 `from .validate import validate_args, ValidationError`。
在 `syscall` 方法里，capability 检查之后、budget 检查之前插入（约 kernel.py:200 后）：

```python
        _, spec = entry
        try:
            validate_args(spec.input_schema, args)
        except ValidationError as ve:
            return self._deny(pcb, tool, args, started, str(ve))
```

Run: `python -m unittest discover -s tests`
Expected: `Ran 26 tests ... OK`（既有测试仍过，因所有 driver 的 schema 已含 required）

- [ ] **Step 6: Commit**

```bash
git add laos/validate.py laos/kernel.py tests/test_validate.py
git commit -m "feat(laos): add zero-dep syscall arg validation + path-traversal fence"
```

---

### Task 2: 上下文抢占快照（save / restore）

**为什么**：AIOS Context Manager 证明"LLM 生成中途挂起零质量损失"可行（表 7 BLEU=1.0）。laos 的 `ContextManager` 只有窗口换页，没有按 agent 的快照/恢复。本任务加 `save_snapshot` / `load_snapshot`，使 agent 在预算耗尽时被挂起、让位给别人、再恢复。

**Files:**
- Modify: `laos/context.py`（`ContextManager` 加 `save_snapshot` / `load_snapshot` / `suspend` / `resume`）
- Test: `tests/test_context.py`（追加 3 个 case）

**Interfaces:**
- Consumes: `ContextManager.__init__` 已有 `swap_dir`（用作快照落盘目录）。
- Produces: `save_snapshot() -> Path`、`load_snapshot(Path) -> None`、`suspend()` 标记挂起、`resume()` 恢复。

- [ ] **Step 1: 写失败测试（追加到 tests/test_context.py）**

```python
    def test_save_restore_snapshot(self):
        ctx = ContextManager(system_prompt="s", max_tokens=4000, swap_dir=self.root / "swap")
        ctx.append("user", "msg-1")
        ctx.append("user", "msg-2")
        snap = ctx.save_snapshot()
        self.assertTrue(snap.exists())
        ctx.append("user", "msg-3")
        self.assertEqual(len(ctx._window), 3)
        ctx.load_snapshot(snap)
        self.assertEqual(len(ctx._window), 2)
        self.assertEqual(ctx._window[-1].content, "msg-2")

    def test_suspend_resume_marks_state(self):
        ctx = ContextManager(system_prompt="s", max_tokens=4000)
        ctx.append("user", "a")
        ctx.suspend()
        self.assertTrue(ctx.suspended)
        ctx.resume()
        self.assertFalse(ctx.suspended)
```

注意：`tests/test_context.py` 现有 `setUp` 已建 `self.root = Path(tempfile.mkdtemp())`，直接复用。

- [ ] **Step 2: 运行确认失败**

Run: `python -m unittest tests/test_context.py -v`
Expected: `ERROR test_save_restore_snapshot` / `ERROR test_suspend_resume_marks_state`（AttributeError: no attribute 'save_snapshot'）

- [ ] **Step 3: 写最小实现**

在 `laos/context.py` 的 `ContextManager` 中追加（放在 `dump` 方法之后）：

```python
    # -- 抢占快照（受 AIOS Context Manager 启发，但作用于 Agent 上下文窗口）----
    def save_snapshot(self) -> Path:
        """把当前完整上下文序列化到 swap_dir，等价于进程挂起时的寄存器/内存落盘。"""
        if not self.swap_dir:
            raise RuntimeError("save_snapshot requires swap_dir")
        self.swap_dir.mkdir(parents=True, exist_ok=True)
        path = self.swap_dir / f"snap-{int(time.time() * 1000)}.json"
        payload = {
            "system": self._system.content,
            "summary": self._summary,
            "window": [m.to_dict() for m in self._window],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def load_snapshot(self, path: Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self._system = Message("system", data.get("system", ""))
        self._summary = data.get("summary", "")
        self._window = [Message(m["role"], m["content"], meta=m) for m in data.get("window", [])]
        self.stats.window_tokens = self.window_tokens

    @property
    def suspended(self) -> bool:
        return getattr(self, "_suspended", False)

    def suspend(self) -> None:
        self._suspended = True

    def resume(self) -> None:
        self._suspended = False
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m unittest tests/test_context.py -v`
Expected: 既有 case + 新增 2 case 全 OK

- [ ] **Step 5: 回归全量**

Run: `python -m unittest discover -s tests`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add laos/context.py tests/test_context.py
git commit -m "feat(laos): add context save/restore snapshots for agent preemption"
```

---

### Task 3: LLM 推理调度器（优先级 + 预算轮转）

**为什么**：AIOS Scheduler 把多 agent 的 LLM 调用公平排队（RR 比 FIFO p90 更低）。laos 当前是 `kernel.scheduler_ctx()` 一把全局 `asyncio.Lock`，无优先级、无预算。本任务用 `AgentScheduler` 替代，支持按 priority 选下一个可思考的 agent，超 token 预算者挂起（调 Task 2 的 `suspend`）。

**Files:**
- Create: `laos/scheduler.py`
- Modify: `laos/agent.py:63-67`（`_do_syscall` 用新调度器替代 `scheduler_ctx()`）
- Modify: `laos/kernel.py:252-254`（`scheduler_ctx` 改为返回 `AgentScheduler` 实例；`__init__` 里构造）
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Produces: `AgentScheduler.register(pid, priority=0, token_budget=None)`、`acquire(pid) -> bool`（轮到且未超预算返回 True，否则 False）、`release(pid)`、`note_tokens(pid, n)`。
- Consumes: `ContextManager.suspend()`（Task 2）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scheduler.py
import unittest
from laos.scheduler import AgentScheduler


class TestAgentScheduler(unittest.TestCase):
    def test_fair_round_robin(self):
        s = AgentScheduler()
        s.register(1, priority=0)
        s.register(2, priority=0)
        order = []
        for _ in range(4):
            for pid in (1, 2):
                if s.acquire(pid):
                    order.append(pid)
                    s.release(pid)
        self.assertEqual(order, [1, 2, 1, 2])  # 公平交替

    def test_token_budget_suspends(self):
        s = AgentScheduler()
        s.register(7, priority=0, token_budget=10)
        self.assertTrue(s.acquire(7))
        s.note_tokens(7, 10)  # 用尽预算
        s.release(7)
        self.assertFalse(s.acquire(7))  # 超额挂起，不让思考

    def test_priority_preempts(self):
        s = AgentScheduler()
        s.register(1, priority=0)
        s.register(2, priority=1)  # 高优先级
        self.assertTrue(s.acquire(2))
        s.release(2)
        self.assertEqual(s.next_pid(), 2)  # 高优先级优先


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m unittest tests/test_scheduler.py -v`
Expected: `ModuleNotFoundError: No module named 'laos.scheduler'`

- [ ] **Step 3: 写最小实现**

```python
# laos/scheduler.py
"""多 Agent 公平复用 Brain（LLM 是最贵资源）。

受 AIOS Scheduler 启发：AIOS 用 FIFO/RR 给 LLM 推理请求排队，RR 的 p90 等待更低。
这里把"全局锁"升级为带 priority 的时间片轮转 + 每 agent token 预算，超额自动挂起。
"""
from __future__ import annotations

import heapq


class AgentScheduler:
    def __init__(self) -> None:
        self._prio: dict[int, int] = {}
        self._budget: dict[int, int | None] = {}
        self._used: dict[int, int] = {}
        self._suspended: set[int] = set()

    def register(self, pid: int, priority: int = 0, token_budget: int | None = None) -> None:
        self._prio[pid] = priority
        self._budget[pid] = token_budget
        self._used[pid] = 0

    def next_pid(self) -> int | None:
        alive = [p for p in self._prio if p not in self._suspended]
        if not alive:
            return None
        return max(alive, key=lambda p: (self._prio[p], -self._used[p]))

    def acquire(self, pid: int) -> bool:
        if pid in self._suspended:
            return False
        b = self._budget.get(pid)
        if b is not None and self._used.get(pid, 0) >= b:
            self._suspended.add(pid)
            return False
        return self.next_pid() == pid

    def release(self, pid: int) -> None:
        self._used[pid] = self._used.get(pid, 0)

    def note_tokens(self, pid: int, n: int) -> None:
        self._used[pid] = self._used.get(pid, 0) + n
        b = self._budget.get(pid)
        if b is not None and self._used[pid] >= b:
            self._suspended.add(pid)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m unittest tests/test_scheduler.py -v`
Expected: `Ran 3 tests ... OK`

- [ ] **Step 5: 接入 agent 与 kernel**

`laos/agent.py` 的 `_do_syscall` 改为：

```python
    async def _do_syscall(self, call) -> str:
        sched = self.kernel.scheduler
        # 思考（Brain）+ 调用都走调度器，确保公平复用
        while not sched.acquire(self.pcb.pid):
            await asyncio.sleep(0.01)
        try:
            res = await self.kernel.syscall(self.pcb.pid, call.name, call.arguments)
            sched.note_tokens(self.pcb.pid, self.pcb.ctx.stats.total_tokens)
            return res.text
        finally:
            sched.release(self.pcb.pid)
```

`laos/kernel.py`：`AgentKernel.__init__` 末尾加 `from .scheduler import AgentScheduler` + `self.scheduler = AgentScheduler()`；将 `scheduler_ctx()` 改为：

```python
    def scheduler_ctx(self):
        return self.scheduler
```

并在 `spawn` 成功后调用 `self.scheduler.register(pcb.pid, priority=getattr(pcb, "priority", 0), token_budget=self._agent_token_budget)`（budget 来自 env `LAOS_AGENT_TOKENS`，默认 None=不限）。

- [ ] **Step 6: 回归全量**

Run: `python -m unittest discover -s tests`
Expected: `OK`（并发 agent 测试仍过）

- [ ] **Step 7: Commit**

```bash
git add laos/scheduler.py laos/agent.py laos/kernel.py tests/test_scheduler.py
git commit -m "feat(laos): fair LLM scheduler with priority + per-agent token budget"
```

---

### Task 4: 跨 agent 能力委派（capability，可委派不可提升）

**为什么**：AIOS Access Manager 用"特权组"做跨 agent 权限，但本质是"同组即可见"，且文档标 TBD。laos 用 capability 模型更合适：父 agent spawn 子 agent 时只能委派自己能力的子集，子不能提升。复用现有 `spawn(parent=...)`。

**Files:**
- Modify: `laos/kernel.py:31-46`（`CapabilitySet` 加 `delegate`）
- Modify: `laos/agent.py`（`Agent` 加 `fork_child`）
- Test: `tests/test_capability.py`（追加 3 个 case）

**Interfaces:**
- Produces: `CapabilitySet.delegate(subset: list[str]) -> CapabilitySet`（结果 ⊆ self，否则 `ValueError`）；`Agent.fork_child(name, caps_subset, branch) -> Agent`。
- Consumes: `kernel.spawn(name, caps, ctx, branch, parent=...)`（已支持 parent）。

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_capability.py
    def test_delegate_subset_ok(self):
        parent = CapabilitySet(["fs.*", "sys.*"])
        child = parent.delegate(["sys.*"])
        self.assertTrue(child.allows("sys.info"))
        self.assertFalse(child.allows("fs.read"))

    def test_delegate_cannot_escalate(self):
        parent = CapabilitySet(["sys.*"])
        with self.assertRaises(ValueError):
            parent.delegate(["fs.*", "proc.*"])  # 父没有，不可委派
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m unittest tests/test_capability.py -v`
Expected: `ERROR test_delegate_subset_ok`（`CapabilitySet` has no attribute `delegate`）

- [ ] **Step 3: 写最小实现**

`laos/kernel.py` 的 `CapabilitySet` 内追加：

```python
    def delegate(self, subset: list[str]) -> "CapabilitySet":
        """委派子集：结果必须 ⊆ 自身能力，越权即 ValueError（可委派不可提升）。"""
        cand = CapabilitySet(subset)
        for pat in cand.patterns:
            # 该模式必须能被 self 覆盖：要么 self 含 '*'，要么 self 含该模式，
            # 要么 self 含其驱动通配（如委派 fs.read 需 self 有 fs.* 或 fs.read）
            if "*" in self.patterns:
                continue
            if pat in self.patterns:
                continue
            driver = pat.split(".", 1)[0]
            if f"{driver}.*" in self.patterns:
                continue
            raise ValueError(f"cannot delegate {pat!r}: not granted to parent")
        return cand
```

`laos/agent.py` 追加 `fork_child`（需 `brain` 用同一类构造；为测试简单，`fork_child` 接收子 brain）：

```python
    def fork_child(self, name: str, caps_subset: list[str], branch: str, child_brain) -> "Agent":
        child_caps = self.pcb.caps.delegate(caps_subset)
        ctx = ContextManager(
            system_prompt=self.pcb.ctx._system.content,
            max_tokens=self.pcb.ctx.max_tokens,
            swap_dir=self.kernel.workdir / "swap",
        )
        child_pcb = self.kernel.spawn(
            name=name, caps=child_caps.patterns, ctx=ctx,
            branch=branch, parent=self.pcb.pid, budget=self.pcb.budget,
        )
        return Agent(self.kernel, child_pcb, child_brain, max_steps=self.max_steps)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m unittest tests/test_capability.py -v`
Expected: 既有 + 新增 case 全 OK

- [ ] **Step 5: 集成测试（子 agent 越权被内核拒）**

在 `tests/test_laos.py` 的 `KernelTestCase` 加：

```python
    def test_fork_child_cannot_escalate(self):
        parent = self.spawn("parent", ["sys.*"])
        child = parent.fork_child("child", ["sys.*"], "main", ScriptedBrain(branch="main"))
        # 子只有 sys.*，调 fs.read（父也没有）必须经内核 EPERM
        res = asyncio.run(self.kernel.syscall(child.pcb.pid, "fs.read",
                                              {"path": "/main/workspace/hosts"}))
        self.assertFalse(res.ok)
        self.assertIn("EPERM", res.error)
```

- [ ] **Step 6: 回归全量 + commit**

Run: `python -m unittest discover -s tests`
Expected: `OK`
```bash
git add laos/kernel.py laos/agent.py tests/test_capability.py tests/test_laos.py
git commit -m "feat(laos): capability delegation, child agent cannot escalate"
```

---

### Task 5: 不可逆操作预算 + 人类确认准入

**为什么**：AIOS 的 `ask_permission` 是**提示性**的（不可逆操作弹窗问用户，不自动拒绝）。laos 应升级为**强制**：每条 tool 标 `reversible/risk`，不可逆操作消耗 irreversibility budget，超预算或 `risk=high` 必须人类一次性确认（mock 可测），拒绝则 `EACCES`。

**Files:**
- Modify: `laos/mcp.py:34-47`（`ToolSpec` 加 `reversible: bool = True`、`risk: str = "low"`；`to_dict` 透传；`MCPServer.tool` 装饰器加透传参数）
- Modify: `laos/kernel.py`（`syscall` 入口加不可逆检查；`__init__` 加 `irreversibility_budget` 与 `confirm` 回调）
- Modify: `drivers/drv_proc.py`（`proc.exec` 标 `reversible=False, risk="high"`）
- Test: `tests/test_irreversibility.py`

**Interfaces:**
- Produces: `ToolSpec(name, description, input_schema, reversible=True, risk="low")`；`AgentKernel.__init__(workdir, ..., irreversibility_budget=3, confirm=None)`，`confirm(op: dict) -> bool`（默认 CLI 输入，测试注入 mock）。
- Consumes: Task 1 的校验已就位；`CallResult.fail` 已有。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_irreversibility.py
import asyncio
import unittest
from pathlib import Path
from laos.kernel import AgentKernel
from laos.mcp import CallResult  # noqa


class IrrevTest(unittest.TestCase):
    def setUp(self):
        self.td = Path(__file__).resolve().parents[1]
        # 用最小内存测试替身，避免真起驱动；直接测 syscall 的不可逆分支
        self.k = AgentKernel(self.td / "var" / "irrev", audit_mode="w")

    def tearDown(self):
        self.k.shutdown()

    def _spawn_denied_proc(self):
        from laos.kernel import CapabilitySet, PCB
        self.k.procs[999] = PCB(pid=999, name="x", caps=CapabilitySet(["proc.*"]),
                                budget=None)
        self.k.syscall_table["proc.exec"] = ("proc", _StubIrrev())
        # 直接塞一个不可逆 spec
        from laos.mcp import ToolSpec
        self.k.syscall_table["proc.exec"] = ("proc", ToolSpec("proc.exec", "x", {}, reversible=False, risk="high"))


class _StubIrrev:
    pass


if __name__ == "__main__":
    unittest.main()
```

（上述为骨架；正式测试见 Step 3 集成进 kernel 的不可逆分支，直接调用 `kernel.syscall` 并断言 `EACCES`。）

- [ ] **Step 2: 运行确认失败**

Run: `python -m unittest tests/test_irreversibility.py -v`
Expected: 因 `ToolSpec` 无 `reversible` 字段 / `syscall` 无不可逆分支 → 测试逻辑不满足

- [ ] **Step 3: 写最小实现**

`laos/mcp.py` 的 `ToolSpec`：

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    reversible: bool = True
    risk: str = "low"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "reversible": self.reversible,
            "risk": self.risk,
        }
```

`MCPServer.tool` 签名改为 `def tool(self, name, description, schema=None, reversible=True, risk="low")` 并在构造 `ToolSpec` 时透传。

`laos/kernel.py`：
- `__init__` 加 `self.irreversibility_budget = int(os.environ.get("LAOS_IRREV_BUDGET", "3"))`；`self.confirm = confirm or self._cli_confirm`。
- `syscall` 在 Task 1 校验之后、budget 检查之前插入：

```python
        if not spec.reversible:
            if self.irreversibility_budget <= 0 or spec.risk == "high":
                if not self.confirm({"tool": tool, "args": args, "risk": spec.risk}):
                    return self._deny(pcb, tool, args, started,
                                      "EACCES: irreversible operation requires confirmation")
            self.irreversibility_budget = max(0, self.irreversibility_budget - 1)
```

- 加 `def _cli_confirm(self, op): return input(f"allow {op['tool']}? [y/N] ").lower() == "y"`。

`drivers/drv_proc.py` 的 `proc.exec` 装饰器改为 `@drv.tool("proc.exec", "...", _SCHEMA_EXEC, reversible=False, risk="high")`。

- [ ] **Step 4: 写完整测试（替换 Step 1 骨架）**

```python
# tests/test_irreversibility.py
import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from laos.kernel import AgentKernel, CapabilitySet, PCB  # noqa: E402
from laos.mcp import ToolSpec  # noqa: E402


class TestIrreversibility(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.k = AgentKernel(Path(self.td.name) / "var", audit_mode="w",
                             irreversibility_budget=1, confirm=lambda op: False)

    def tearDown(self):
        self.k.shutdown()
        self.td.cleanup()

    def _proc_pcb(self):
        self.k.syscall_table["proc.exec"] = ("proc",
            ToolSpec("proc.exec", "exec", {"type": "object",
                     "properties": {"cmdline": {"type": "string"}}, "required": ["cmdline"]},
                     reversible=False, risk="high"))
        pcb = PCB(pid=1, name="a", caps=CapabilitySet(["proc.*"]), budget=None)
        self.k.procs[1] = pcb
        return pcb

    def test_high_risk_blocked_without_confirm(self):
        self._proc_pcb()
        res = asyncio.run(self.k.syscall(1, "proc.exec", {"cmdline": "rm -rf /"}))
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)

    def test_confirm_true_allows(self):
        self.k.confirm = lambda op: True
        self._proc_pcb()
        res = asyncio.run(self.k.syscall(1, "proc.exec", {"cmdline": "echo hi"}))
        # 这里只有 spec 没有真驱动，会走到 ENOSYS/驱动失败，但确认分支应通过（不返回 EACCES）
        self.assertNotIn("EACCES", res.error)

    def test_budget_depletes(self):
        self.k.confirm = lambda op: True
        self.k.irreversibility_budget = 0  # 预算耗尽
        self._proc_pcb()
        res = asyncio.run(self.k.syscall(1, "proc.exec", {"cmdline": "echo hi"}))
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m unittest tests/test_irreversibility.py -v`
Expected: `Ran 3 tests ... OK`

- [ ] **Step 6: 回归全量 + commit**

Run: `python -m unittest discover -s tests`
Expected: `OK`
```bash
git add laos/mcp.py laos/kernel.py drivers/drv_proc.py tests/test_irreversibility.py
git commit -m "feat(laos): irreversibility budget + human-confirm gate for risky syscalls"
```

---

### Task 6: 强制隔离接入（补 AIOS 缺失的 L4）

**为什么**：AIOS 全仓库无 namespace/cgroup/seccomp。laos 的 `sandbox.py` 已有 `Sandbox`/`IsolationReport`/路径 jail，但没真正包住驱动子进程与 `proc.exec`。本任务把隔离落到执行路径，使强制力达 L4（Linux 生效，跨平台降级不报错）。

**Files:**
- Modify: `laos/sandbox.py`（`Sandbox.wrap(cmd) -> list` 真正产出 `unshare` + cgroup 包装命令；`estimate()` 真实探测）
- Modify: `laos/kernel.py`（`load_driver` 用 `self.sandbox.wrap` 包装启动命令）
- Modify: `laos/agent.py`（`_do_syscall` 中 `proc.exec` 走 sandbox，复用 Task 5 的 `syscall` 已含 risk 检查）
- Test: `tests/test_sandbox.py`

**Interfaces:**
- Produces: `Sandbox.wrap(cmd: list[str]) -> list[str]`（Linux 返回 `[unshare, --map-root-user, --net, ...] + cmd`；非 Linux 返回原 cmd）；`IsolationReport.active: bool`。
- Consumes: `kernel.load_driver(name, cmd, env)` 的 `cmd`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_sandbox.py
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from laos.sandbox import Sandbox, IsolationReport  # noqa: E402


class TestSandbox(unittest.TestCase):
    def test_wrap_downgrades_off_linux(self):
        sb = Sandbox(enabled=True)
        cmd = ["python", "-c", "print(1)"]
        if os.uname().sysname != "Linux":
            self.assertEqual(sb.wrap(cmd), cmd)  # 跨平台降级：原样
        else:
            self.assertNotEqual(sb.wrap(cmd), cmd)  # Linux：包了 unshare

    def test_estimate_reports_active(self):
        rep = Sandbox(enabled=True).estimate()
        self.assertIsInstance(rep, IsolationReport)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m unittest tests/test_sandbox.py -v`
Expected: 依当前 `sandbox.py` 实现可能部分失败（wrap 可能未实现）

- [ ] **Step 3: 写最小实现**

`laos/sandbox.py` 现有 `Sandbox` 类补：

```python
    def wrap(self, cmd: list[str]) -> list[str]:
        """把启动命令包进 Linux 隔离原语；非 Linux 或 disabled 时原样返回。"""
        if not self.enabled or os.uname().sysname != "Linux":
            return list(cmd)
        # user namespace + 网络隔离 + 进程/挂载隔离；能力集清空
        pre = ["unshare", "--map-root-user", "--net", "--fork",
               "capsh", "--secargs=-all", "--"]
        # 注：生产应再挂 cgroup v2 写 pids.max / memory.max；此处给出最小强制骨架
        return pre + list(cmd)

    def estimate(self) -> "IsolationReport":
        linux = os.uname().sysname == "Linux"
        return IsolationReport(
            active=self.enabled and linux,
            level="L4 (unshare+capsh)" if (self.enabled and linux) else "none (host): 非 Linux 宿主，跳过内核隔离",
        )
```

`laos/kernel.py` 的 `load_driver`：把传入 `cmd` 改为 `self.sandbox.wrap(cmd)`：

```python
        wrapped = self.sandbox.wrap(cmd)
        proc = subprocess.Popen(wrapped, stdin=PIPE, stdout=PIPE, env=env, text=True)
```

`laos/agent.py`：在 `proc.exec` 分支（drvier 内部已执行 subprocess）之外，确保 driver 进程本身由 wrapped cmd 启动即已隔离；无需在 agent 额外改（隔离在驱动进程层级生效）。

- [ ] **Step 4: 运行确认通过**

Run: `python -m unittest tests/test_sandbox.py -v`
Expected: `OK`（Windows 上两 case 均走降级分支）

- [ ] **Step 5: 端到端验证（仅 Linux 有意义；跨平台验证不崩）**

Run: `python bin/laosd.py 2>&1 | Select-String isolation`
Expected: 输出 `isolation: none (host): 非 Linux 宿主，跳过内核隔离`（Windows）或 `L4 (unshare+capsh)`（Linux）

- [ ] **Step 6: 回归全量 + commit**

Run: `python -m unittest discover -s tests`
Expected: `OK`
```bash
git add laos/sandbox.py laos/kernel.py laos/agent.py tests/test_sandbox.py
git commit -m "feat(laos): wire L4 isolation (unshare+capsh) into driver spawn path"
```

---

## Self-Review

**1. Spec coverage（对照 `aios-deep-dive-2026-08.md` 的 §7 启示）**
- §7.1 上下文抢占快照 → Task 2 ✅
- §7.1 LLM 推理调度 → Task 3 ✅
- §7.1 跨 agent 权限（capability 化）→ Task 4 ✅
- §7.1 不可逆操作准入 → Task 5 ✅
- §7.2 工具参数校验 → Task 1 ✅
- §7.2 强制隔离 L4 → Task 6 ✅
- §7.3 "不要重复 AIOS 的 LLM Core 批处理" → 全程未触碰 Brain 推理内部，遵守 ✅

**2. Placeholder 扫描**：无 TBD/TODO；每个 Step 含真实代码或精确文件路径+行号。Task 5 Step 1 的骨架已在 Step 4 被完整测试替换，不是 placeholder。

**3. 类型一致性**：`validate_args(schema, args)`（Task 1）/ `AgentScheduler.register/acquire/release/note_tokens`（Task 3）/ `CapabilitySet.delegate`（Task 4）/ `ToolSpec(reversible, risk)`（Task 5）/ `Sandbox.wrap(cmd)`（Task 6）在定义 task 与消费 task 中签名一致。`save_snapshot() -> Path`、`load_snapshot(Path)` 在 Task 2/3 一致。`confirm(op) -> bool` 在 Task 5 内部一致。

**4. 未覆盖**：BranchFS（FUSE O(1) fork）、语义可观测（OpenTelemetry）、多 Agent IPC 消息总线 —— 这些在调研 `agentos-landscape` 文档列为 P1/P2，不在本计划范围（本计划聚焦 AIOS 机制落地 + L4 强制），应另起计划。
