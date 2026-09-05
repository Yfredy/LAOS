# 内核 IPC（msg.* 内建 syscall + 运行时能力委托）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补上 AgenticOS CFP 列出但无论文正面处理的空白：**多 Agent 通信**。在 laosd 内核里实现内建 syscall（不经 MCP 驱动，真·内核路径）：`msg.send/recv/list`（每 agent 信箱，带配额与审计）与 `sys.delegate`（**运行时能力委托**：把自身能力子集授予指定 pid，按调用次数 TTL、随委托者死亡撤销——深化已有的 spawn 级委派，落实"可委派不可提升"不变量到运行期）。

**Architecture:** `AgentKernel` 增加内建 syscall 层：`self._builtin_specs`（ToolSpec 表，供 caps/审计/visible_tools 复用）+ `self._builtin_impls`（实现）。`syscall()` 在 `syscall_table` 查不到工具时落入内建路径——能力检查走**有效能力**（自身 caps + 未过期委托），参数校验/审计/预算与 MCP 路径完全共用。信箱 `self._mailboxes[pid]` 上限 16 条、单条 4096 字符（ENOBUFS/EMSGSIZE）；委托 `self._delegations[to_pid]` 记录 `{caps, remaining, by}`，每次经委托使用扣一次，委托者 kill 即撤销。`visible_tools` 增加内建 syscall（按有效能力过滤），LLM 才能看到它们。demo 增 IPC 幕（直接 kernel.syscall 演示，不改 ScriptedBrain）。

**Tech Stack:** Python 3.10+ 标准库，零第三方依赖。

**Spec:** `docs/research/2026-09-05-agentos-next-steps.md` §一.2 / §二#5。

## Global Constraints

- 零第三方依赖；stdlib only。
- 不破坏执行时基线测试（以实测为准）；新增测试放独立文件 `tests/test_ipc.py`。
- errno 约定：信箱满 `ENOBUFS`、消息超长 `EMSGSIZE`、目标不存在 `ESRCH`、越权 `EPERM`、委托提升 `EPERM`。
- 解释器 `$PY`（同前）；每 task 一个 commit。
- 内建 syscall 走同一条审计通道（event 仍为 "syscall"，新增 `"builtin": true` 键）。

## 现状关键事实

- `laos/kernel.py` `syscall(pid, tool, args=None, task=False)`：`entry = self.syscall_table.get(tool)`；查不到即 `ENOSYS` ——内建层插入点。
- `CapabilitySet.delegate(subset)` 已存在（越权抛 ValueError，"可委派不可提升"）；`PCB.caps` 为 CapabilitySet。
- `visible_tools`（laos/agent.py:50-62）遍历 `syscall_table`——内建 syscall 需在此补位（否则 LLM 永远看不到）。
- `kill()`（kernel）现写审计并置状态——委托撤销挂点。
- ScriptedBrain 的脚步本硬编码——demo 用直接 kernel.syscall 演示，**不改 brain**。

---

### Task 1: 内建 syscall 层 + msg.send/recv

**Files:**
- Modify: `laos/kernel.py`（`_builtin_specs`/`_builtin_impls`/有效能力检查/syscall 分支）
- Test: `tests/test_ipc.py`（新建）

**Interfaces:**
- Produces:
  - `AgentKernel._builtin_specs: dict[str, ToolSpec]`：`msg.send`（schema: to_pid int, text string，均必填）、`msg.recv`（无参）、`msg.list`（无参）——全部 `reversible=True, risk="low"`。
  - `AgentKernel._effective_allows(pcb, tool, consume: bool = False) -> bool`：自身 caps 或某条 `remaining>0` 的委托允许该工具；`consume=True` 时对**首个**匹配的委托 `remaining -= 1`。
  - `syscall` 内建分支：syscall_table 查不到时查 `_builtin_specs`——无则维持 ENOSYS；有则走既有检查链（caps 用 `_effective_allows(pcb, tool, consume=True)`、validate_args、EDQUOT）后调 `_builtin_impls[tool](pcb, args)` 返回 CallResult；审计事件带 `"builtin": True`。
  - `msg.send(to_pid, text)`：接收者不存在 → `ESRCH`；调用者不存在 → ESRCH（gate 已挡）；`len(text) > 4096` → `EMSGSIZE`；信箱 ≥16 条 → `ENOBUFS`；成功入信箱 `{"from": pid, "text": text, "t": time.time()}`，返回 `OK sent to pid=N`。
  - `msg.recv()`：drain 自己的信箱，格式 `from=1001: <text>` 每行一条，空则 `(empty)`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ipc.py
"""内核 IPC —— msg.* 内建 syscall + 运行时能力委托。

    python -m unittest tests.test_ipc -v
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


class IPCBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.kernel = AgentKernel(Path(self._td.name) / "var", confirm=lambda op: True)

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, name, caps):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name=name, caps=caps, ctx=ctx)

    def _call(self, pid, tool, args):
        return asyncio.run(self.kernel.syscall(pid, tool, args))


class TestMsg(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.a = self._spawn("a", ["msg.*"])
        self.b = self._spawn("b", ["msg.*"])

    def test_send_recv_roundtrip(self):
        res = self._call(self.a.pid, "msg.send",
                         {"to_pid": self.b.pid, "text": "hello"})
        self.assertTrue(res.ok, res.error)
        res = self._call(self.b.pid, "msg.recv", {})
        self.assertTrue(res.ok)
        self.assertIn(f"from={self.a.pid}", res.text)
        self.assertIn("hello", res.text)
        res = self._call(self.b.pid, "msg.recv", {})
        self.assertIn("(empty)", res.text)

    def test_send_to_unknown_pid_esrch(self):
        res = self._call(self.a.pid, "msg.send", {"to_pid": 424242, "text": "x"})
        self.assertFalse(res.ok)
        self.assertIn("ESRCH", res.error)

    def test_caps_denial(self):
        c = self._spawn("c", ["sys.*"])  # 无 msg 能力
        res = self._call(c.pid, "msg.send", {"to_pid": self.a.pid, "text": "x"})
        self.assertIn("EPERM", res.error)

    def test_builtin_audited(self):
        self._call(self.a.pid, "msg.send", {"to_pid": self.b.pid, "text": "x"})
        events = [r for r in self.kernel.audit.records
                  if r.get("event") == "syscall" and r.get("builtin")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["tool"], "msg.send")

    def test_visible_tools_surface_builtins(self):
        from laos.agent import Agent
        from laos.brain import ScriptedBrain
        agent = Agent(self.kernel, self.a, ScriptedBrain(branch="main"))
        names = [t["name"] for t in agent.visible_tools]
        self.assertIn("msg.send", names)
        self.assertIn("msg.recv", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_ipc -v`
Expected: FAIL —— `msg.send` 返回 ENOSYS

- [ ] **Step 3: 实现（laos/kernel.py）**

3a. import 增加 `from typing import Any, Callable`（已有 Any 则补 Callable）。`AgentKernel.__init__` 末尾增加：

```python
        # -- 内建 syscall 层（内核直供，不经 MCP 驱动）------------------------
        from .mcp import ToolSpec
        self._builtin_specs: dict[str, ToolSpec] = {
            "msg.send": ToolSpec(
                "msg.send", "向另一个 agent 的信箱投递消息",
                {"type": "object",
                 "properties": {"to_pid": {"type": "integer"},
                                "text": {"type": "string"}},
                 "required": ["to_pid", "text"]}),
            "msg.recv": ToolSpec("msg.recv", "收取并清空自己的信箱",
                                 {"type": "object", "properties": {}}),
            "msg.list": ToolSpec("msg.list", "列出所有信箱的积压情况",
                                 {"type": "object", "properties": {}}),
        }
        self._builtin_impls: dict[str, Any] = {
            "msg.send": self._impl_msg_send,
            "msg.recv": self._impl_msg_recv,
            "msg.list": self._impl_msg_list,
        }
        self._mailboxes: dict[int, list[dict]] = {}
        self._delegations: dict[int, list[dict]] = {}
```

（`_delegations` 本 task 先占位，Task 3 使用。）

3b. `AgentKernel` 新增方法：

```python
    # -- 有效能力：自身 caps + 未过期委托（consume=True 时扣 TTL）-----------
    def _effective_allows(self, pcb: PCB, tool: str, consume: bool = False) -> bool:
        if pcb.caps.allows(tool):
            return True
        for d in self._delegations.get(pcb.pid, []):
            if d["remaining"] > 0 and d["caps"].allows(tool):
                if consume:
                    d["remaining"] -= 1
                return True
        return False

    # -- 内建实现 ----------------------------------------------------------
    MAILBOX_MAX = 16
    MSG_MAX_CHARS = 4096

    def _impl_msg_send(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        to_pid = int(args["to_pid"])
        text = str(args["text"])
        if to_pid not in self.procs:
            return CallResult.fail(f"ESRCH: no such process {to_pid}")
        if len(text) > self.MSG_MAX_CHARS:
            return CallResult.fail(f"EMSGSIZE: {len(text)} > {self.MSG_MAX_CHARS}")
        box = self._mailboxes.setdefault(to_pid, [])
        if len(box) >= self.MAILBOX_MAX:
            return CallResult.fail(f"ENOBUFS: mailbox full for {to_pid}")
        box.append({"from": pcb.pid, "text": text, "t": time.time()})
        self.audit.write({"t": time.time(), "event": "msg", "from": pcb.pid,
                          "to": to_pid, "bytes": len(text)})
        return CallResult.ok_text(f"OK sent to pid={to_pid}")

    def _impl_msg_recv(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        box = self._mailboxes.get(pcb.pid, [])
        self._mailboxes[pcb.pid] = []
        if not box:
            return CallResult.ok_text("(empty)")
        lines = [f"from={m['from']}: {m['text']}" for m in box]
        return CallResult.ok_text("\n".join(lines))

    def _impl_msg_list(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        rows = [f"pid={pid}: {len(box)} pending" for pid, box in self._mailboxes.items() if box]
        return CallResult.ok_text("\n".join(rows) or "(no pending messages)")
```

3c. `syscall` 的查表处：

```python
        entry = self.syscall_table.get(tool)
        builtin_spec = self._builtin_specs.get(tool)
        if entry is None and builtin_spec is None:
            return self._deny(pcb, tool, args, started, "ENOSYS: no such syscall")
```

其后所有 `_spec` 引用改为 `entry[1] if entry else builtin_spec`（在闸门前赋值 `spec = entry[1] if entry else builtin_spec`）；能力检查改为 `if not self._effective_allows(pcb, tool, consume=True):`（仅内建时 consume 生效，MCP 路径委托同样可用——统一语义）；`validate_args(spec.input_schema, args)` 同步替换。EDQUOT 检查后、派发前加内建分支：

```python
        if entry is None:
            result = self._builtin_impls[tool](pcb, args)
            elapsed_ms = (time.perf_counter() - started) * 1000
            pcb.stats["syscalls"] += 1
            self.audit.write(
                {"t": time.time(), "event": "syscall", "pid": pid, "agent": pcb.name,
                 "tool": tool, "args": args, "ok": result.ok,
                 "ms": round(elapsed_ms, 2), "result": result.text[:500],
                 "builtin": True}
            )
            return result
```

- [ ] **Step 4: 跑全量测试**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿 = 实测基线 + 5）

- [ ] **Step 5: Commit**

```bash
git add laos/kernel.py tests/test_ipc.py
git commit -m "feat(laos): builtin msg.send/recv/list syscalls with mailboxes"
```

---

### Task 2: 信箱配额细化 + msg.list 验收

**Files:**
- Test: `tests/test_ipc.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
class TestMailboxQuotas(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.a = self._spawn("a", ["msg.*"])
        self.b = self._spawn("b", ["msg.*"])

    def test_mailbox_overflow_enobufs(self):
        for i in range(16):
            res = self._call(self.a.pid, "msg.send",
                             {"to_pid": self.b.pid, "text": f"m{i}"})
            self.assertTrue(res.ok, res.error)
        res = self._call(self.a.pid, "msg.send", {"to_pid": self.b.pid, "text": "x"})
        self.assertIn("ENOBUFS", res.error)

    def test_oversized_message_emsgsize(self):
        res = self._call(self.a.pid, "msg.send",
                         {"to_pid": self.b.pid, "text": "x" * 4097})
        self.assertIn("EMSGSIZE", res.error)

    def test_msg_list(self):
        self._call(self.a.pid, "msg.send", {"to_pid": self.b.pid, "text": "x"})
        res = self._call(self.a.pid, "msg.list", {})
        self.assertIn(f"pid={self.b.pid}: 1 pending", res.text)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_ipc -v`
Expected: overflow 与 list 两项 FAIL 或直接通过（实现若已在 Task 1 完成——本 task 是契约收口，允许确认已绿；若 FAIL 修实现）。

- [ ] **Step 3: 全量回归 + Commit**

```bash
git add tests/test_ipc.py
git commit -m "test(laos): mailbox quota and listing contracts"
```

---

### Task 3: sys.delegate —— 运行时能力委托（TTL + 撤销）

**Files:**
- Modify: `laos/kernel.py`（`sys.delegate` spec/impl、kill 撤销、委托审计）
- Test: `tests/test_ipc.py`（追加）

**Interfaces:**
- Produces:
  - `sys.delegate(to_pid, caps_subset: list[str], ttl_calls: int)` 内建 syscall（`reversible=True`）：调用者不存在/目标不存在 → ESRCH；`ttl_calls < 1` → EINVAL；提升（`pcb.caps.delegate` 抛 ValueError）→ `EPERM: delegation elevates privilege`；成功记录 `self._delegations[to_pid].append({"caps": CapabilitySet, "remaining": ttl_calls, "by": pid})`，返回 `OK delegated {n} caps to pid=N (ttl=M calls)`，审计 `{"event": "delegate", "from", "to", "caps", "ttl"}`。
  - `kill()`：被杀者**授出**的委托全部撤销（`_drop_delegations_by(pid)`），审计 `{"event": "delegate_revoke", "by": pid}`。
  - 语义提醒：`_effective_allows(consume=True)` 在每次经委托使用时扣 1。

- [ ] **Step 1: 追加失败测试**

```python
class TestDelegation(unittest.TestCase):
    def setUp(self):
        super().setUp()
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8",
               "LAOS_FS_ROOT": str(Path(self._td.name) / "var" / "branches")}
        self.kernel.load_driver("fs", [sys.executable, str(REPO / "drivers" / "drv_fs.py")],
                                env=env)
        self.kernel.load_driver("sys", [sys.executable, str(REPO / "drivers" / "drv_sys.py")],
                                env=env)
        self.main = self.kernel.branches.create_root("main")
        (self.main.workspace / "workspace").mkdir(parents=True, exist_ok=True)
        (self.main.workspace / "workspace" / "hosts").write_text(
            "127.0.0.1 localhost\n", encoding="utf-8")
        self.ops = self._spawn("ops", ["fs.*", "sys.*", "msg.*"])
        self.guest = self._spawn("guest", ["sys.*", "msg.*"])

    def test_delegation_grants_and_expires(self):
        res = self._call(self.ops.pid, "sys.delegate",
                         {"to_pid": self.guest.pid,
                          "caps_subset": ["fs.read"], "ttl_calls": 2})
        self.assertTrue(res.ok, res.error)
        # guest 原本无 fs.read —— 委托后可用
        for _ in range(2):
            res = self._call(self.guest.pid, "fs.read",
                             {"path": "/main/workspace/hosts"})
            self.assertTrue(res.ok, res.error)
        # TTL 耗尽
        res = self._call(self.guest.pid, "fs.read",
                         {"path": "/main/workspace/hosts"})
        self.assertIn("EPERM", res.error)

    def test_delegation_cannot_elevate(self):
        res = self._call(self.guest.pid, "sys.delegate",
                         {"to_pid": self.ops.pid, "caps_subset": ["fs.*"],
                          "ttl_calls": 2})
        self.assertIn("EPERM", res.error)  # guest 自己没有 fs.*，不可授人

    def test_delegator_death_revokes(self):
        self._call(self.ops.pid, "sys.delegate",
                   {"to_pid": self.guest.pid, "caps_subset": ["fs.read"],
                    "ttl_calls": 5})
        self.kernel.kill(self.ops.pid)
        res = self._call(self.guest.pid, "fs.read",
                         {"path": "/main/workspace/hosts"})
        self.assertIn("EPERM", res.error)

    def test_delegate_unknown_target(self):
        res = self._call(self.ops.pid, "sys.delegate",
                         {"to_pid": 424242, "caps_subset": ["fs.read"],
                          "ttl_calls": 2})
        self.assertIn("ESRCH", res.error)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_ipc -v`
Expected: 新类 FAIL（`sys.delegate` ENOSYS）

- [ ] **Step 3: 实现（laos/kernel.py）**

3a. `_builtin_specs` 增：

```python
            "sys.delegate": ToolSpec(
                "sys.delegate", "把自身能力子集授予另一个 agent（TTL 按调用次数）",
                {"type": "object",
                 "properties": {"to_pid": {"type": "integer"},
                                "caps_subset": {"type": "array",
                                                "items": {"type": "string"}},
                                "ttl_calls": {"type": "integer", "minimum": 1}},
                 "required": ["to_pid", "caps_subset", "ttl_calls"]}),
```

`_builtin_impls` 增 `"sys.delegate": self._impl_sys_delegate`。

3b. 实现：

```python
    def _impl_sys_delegate(self, pcb: PCB, args: dict) -> "CallResult":
        from .kernel import CapabilitySet  # 同模块内直接引用
        from .mcp import CallResult
        to_pid = int(args["to_pid"])
        subset = list(args["caps_subset"])
        ttl = int(args["ttl_calls"])
        if to_pid not in self.procs:
            return CallResult.fail(f"ESRCH: no such process {to_pid}")
        if ttl < 1:
            return CallResult.fail("EINVAL: ttl_calls must be >= 1")
        try:
            delegated = pcb.caps.delegate(subset)
        except ValueError as exc:
            return CallResult.fail(f"EPERM: {exc}")
        self._delegations.setdefault(to_pid, []).append(
            {"caps": delegated, "remaining": ttl, "by": pcb.pid})
        self.audit.write({"t": time.time(), "event": "delegate", "from": pcb.pid,
                          "to": to_pid, "caps": sorted(delegated.patterns), "ttl": ttl})
        return CallResult.ok_text(
            f"OK delegated {len(delegated.patterns)} caps to pid={to_pid} (ttl={ttl} calls)")
```

（`from .kernel import CapabilitySet` 在同模块内写 `CapabilitySet` 即可——实现者按实际 import 组织，勿造循环导入。）

3c. `kill()` 在写审计之前加撤销：

```python
        self._drop_delegations_by(pid)
```

并新增：

```python
    def _drop_delegations_by(self, pid: int) -> None:
        """委托者死亡即撤销其授出的一切委托（可委派不可提升，亦不可遗赠）。"""
        for to_pid, lst in list(self._delegations.items()):
            kept = [d for d in lst if d["by"] != pid]
            if len(kept) != len(lst):
                self._delegations[to_pid] = kept
                self.audit.write({"t": time.time(), "event": "delegate_revoke",
                                  "by": pid, "to": to_pid})
```

- [ ] **Step 4: 跑全量测试**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿 = 实测基线 + 9）

- [ ] **Step 5: Commit**

```bash
git add laos/kernel.py tests/test_ipc.py
git commit -m "feat(laos): runtime capability delegation with TTL and revocation"
```

---

### Task 4: demo IPC 幕 + README

**Files:**
- Modify: `bin/laosd.py`（第 4 节后加 4.5 IPC 演示：直接 kernel.syscall）、`README.md`（§6 多 Agent 通信行、§7 说明）

- [ ] **Step 1: bin/laosd.py** 在第 4 节结果打印之后、第 5 节之前插入：

```python
    hr("4.5 内核 IPC：msg.* 与运行时能力委托")
    res = await kernel.syscall(ops.pcb.pid, "msg.send",
                               {"to_pid": guest.pcb.pid, "text": "exp-A 即将提交，请注意 main 变化"})
    print(f"  ops -> guest: {res.text}")
    res = await kernel.syscall(guest.pcb.pid, "msg.recv", {})
    print(f"  guest 收取: {res.text.splitlines()[0]}")
    res = await kernel.syscall(ops.pcb.pid, "sys.delegate",
                               {"to_pid": guest.pcb.pid, "caps_subset": ["fs.read"],
                                "ttl_calls": 1})
    print(f"  ops 委托 fs.read 给 guest: {res.text}")
    res = await kernel.syscall(guest.pcb.pid, "fs.read",
                               {"path": "/main/workspace/hosts"})
    print(f"  guest 经委托读取: {'OK' if res.ok else res.error}")
    res = await kernel.syscall(guest.pcb.pid, "fs.read",
                               {"path": "/main/workspace/hosts"})
    print(f"  guest 二次读取（TTL 已耗尽）: {'OK' if res.ok else res.error}")
```

- [ ] **Step 2: README §6「多 Agent 通信」行替换为**

| **多 Agent 通信** | ~~共享文件系统~~ → **内核 IPC**：`msg.send/recv/list` 信箱（配额 + 审计）+ `sys.delegate` 运行时能力委托（TTL、委托者死亡即撤销） | 消息持久化 / 组播 / 委托链路审计可视化 |

- [ ] **Step 3: README §7 laos/kernel.py 行说明改为**

```
    kernel.py     laosd 薄内核：PCB、能力表、syscall 网关、审计、分支表、内建 IPC
```

- [ ] **Step 4: 全量回归 + Commit**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿）
Run: `$PY bin/laosd.py 2>&1 | grep -A6 "4.5"`（IPC 幕输出）

```bash
git add bin/laosd.py README.md
git commit -m "docs(laos): kernel IPC demo act and README"
```

## 验收清单

- [ ] 全量测试全绿（执行时基线 + 10）
- [ ] demo 4.5 幕：send/recv 往返、委托一次有效、TTL 耗尽 EPERM
- [ ] `grep '"delegate"' var/audit.jsonl` 有记录；ops 被 kill（如有）后 guest 委托失效
- [ ] 本计划恰 4 个 commit
