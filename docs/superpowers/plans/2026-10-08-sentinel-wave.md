# Sentinel 波实施计划 —— nanoMuse 采纳（动作闸 + taint + scoped grants + 记忆溯源）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 nanoMuse 最值得学的三样——六级有序动作闸（含 taint 追踪）、scoped grants、记忆 provenance——落成 laos 零依赖核心件 `laos/sentinel.py` + kernel opt-in 接线 + MemoryStore 溯源。

**Architecture:** Sentinel 是纯 stdlib 决策核（Assessment→六步有序判定→Decision），TaintTracker 与 GrantStore 内聚其中；kernel 以 `sentinel=None` 构造参数 opt-in 接入 syscall 闸门链（caps→task_scope→**sentinel**→不可逆闸→dispatch），不传=字节级零变化（与 Jev judge 同款 opt-in 哲学，主套件 946 绿零风险）。记忆溯源在 MemoryStore 行上加 origin/origin_pid 字段，jitmem 对 origin="user" 行豁免预算与去重（"人写的一行胜过模型写的任何行"的 laos 化）。

**Tech Stack:** Python 3 stdlib only（dataclasses/fnmatch/threading）；测试 unittest（主套件 `tests/`，Windows 宿主直接跑）。

**Spec:** `docs/research/2026-10-08-nanomuse.md`（§4 对照表与 §5 裁决 #1/#2 是本计划的论证前提；执行者先读这两节）。

## Global Constraints

- 零依赖：`laos/sentinel.py` 只准 stdlib；禁止 import 第三方；不 import nanoMuse 任何代码（GPL-3.0 传染红线——只学设计，锚点引用写在文档注释里）。
- kernel opt-in：`AgentKernel(..., sentinel=None)` 缺省不装；不传时既有 syscall 行为与审计**字节级不变**（现有 946 测试是回归保障）。
- 测试进主套件：`tests/test_sentinel.py`（Windows 宿主 `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_sentinel` 直跑；全套 `discover -s tests` 必须保持全绿）。
- 每任务一个 commit（`feat(laos): ...` / `docs(research): ...`），TDD：先红后绿。
- 版本目标 v0.28.0（MINOR，T5 走发版纪律全流程：release.py --apply 真跑绿 → CHANGELOG → tag → push → GitHub Release 页）。

---

### Task 1: Sentinel 判定核（六级有序判定）

**Files:**
- Create: `laos/sentinel.py`
- Test: `tests/test_sentinel.py`

**Interfaces:**
- Consumes: 无。
- Produces（Task 2/3 依赖的精确签名）:
  - `Assessment(tool: str, risk: str = "low", reversible: bool = True, reads_private: bool = False, egress: bool = False)`（frozen dataclass）
  - `Decision(action: str, reason: str, grant_scopes: tuple)`（frozen dataclass；action ∈ {"allow","ask","deny"}；grant_scopes 例 `("once",)` 或 `("once","session","always")`）
  - `SentinelConfig(deny_tools=(), rules=(), always_allow=(), always_ask=(), mode="ask", private_tools=("mem.recall","mem.curate","mic.read"), egress_tools=("msg.send",))`（dataclass；rules 是 `{"tool_glob": str, "action": "allow"|"ask"|"deny"}` 的 tuple）
  - `Sentinel(config: SentinelConfig | None = None)`，`decide(assessment: Assessment, tainted: bool = False) -> Decision`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_sentinel.py`：

```python
# tests/test_sentinel.py —— nanoMuse Sentinel 的 laos 转译（六级有序判定+taint+grants）。
# 设计来源：docs/research/2026-10-08-nanomuse.md §3.1（只学设计，无代码拷贝，GPL 隔离）。
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.sentinel import Assessment, Decision, Sentinel, SentinelConfig  # noqa: E402


def sent(**kw) -> Sentinel:
    return Sentinel(SentinelConfig(**kw))


class TestDecideOrder(unittest.TestCase):
    """六级判定序：deny→规则→always 列表→风险×模式→taint→不可覆盖警告。"""

    def test_deny_tools_wins_first(self):
        d = sent(deny_tools=("shell",)).decide(Assessment("shell", risk="high"))
        self.assertEqual((d.action, d.reason), ("deny", "deny-tools"))

    def test_explicit_rule_beats_lists(self):
        d = sent(rules=({"tool_glob": "msg.*", "action": "allow"},),
                 always_ask=("msg.send",)).decide(Assessment("msg.send"))
        self.assertEqual((d.action, d.reason), ("allow", "rule"))

    def test_always_allow_and_always_ask(self):
        self.assertEqual(sent(always_allow=("time.now",)).decide(
            Assessment("time.now")).action, "allow")
        self.assertEqual(sent(always_ask=("fs.write",)).decide(
            Assessment("fs.write")).action, "ask")

    def test_risk_times_mode_matrix(self):
        a = Assessment("x.tools", risk="high", reversible=False)
        self.assertEqual(sent(mode="auto").decide(a).action, "allow")
        self.assertEqual(sent(mode="ask").decide(a).action, "ask")
        self.assertEqual(sent(mode="strict").decide(
            Assessment("y.tools", risk="low")).action, "allow")     # strict 只问非 low
        self.assertEqual(sent(mode="strict").decide(
            Assessment("z.tools", risk="medium")).action, "ask")

    def test_taint_escalates_egress_even_in_auto(self):
        # 读过隐私后出站变 ask，永不回退——auto 模式同样生效（nanoMuse 语义）
        d = sent(mode="auto").decide(Assessment("msg.send", egress=True), tainted=True)
        self.assertEqual((d.action, d.reason), ("ask", "taint-egress"))

    def test_taint_only_hits_egress_tools(self):
        d = sent(mode="auto").decide(Assessment("mem.remember"), tainted=True)
        self.assertEqual(d.action, "allow")

    def test_explicit_allow_rule_beats_taint(self):
        # egress allowlist 的 laos 化：显式规则可放行污点出站
        d = sent(mode="auto", rules=({"tool_glob": "msg.send", "action": "allow"},)
                 ).decide(Assessment("msg.send", egress=True), tainted=True)
        self.assertEqual(d.action, "allow")

    def test_warning_terminal_only_once_grantable(self):
        # 不可逆+高风险=不可覆盖警告：普通 grant 压不住，只有 once 档
        d = sent(mode="ask").decide(Assessment("pay.transfer", risk="high",
                                               reversible=False))
        self.assertEqual((d.action, d.reason, d.grant_scopes),
                         ("ask", "warning-terminal", ("once",)))

    def test_reversible_low_default_allows(self):
        self.assertEqual(sent().decide(Assessment("mem.stats")).action, "allow")

    def test_decision_default_scopes(self):
        d = sent().decide(Assessment("fs.write", reversible=False))
        self.assertEqual(d.grant_scopes, ("once", "session", "always"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑红**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_sentinel -v`
Expected: FAIL/ERROR（ModuleNotFoundError: laos.sentinel）。

- [ ] **Step 3: 实现 laos/sentinel.py（判定核部分）**

```python
"""sentinel —— 动作闸：六级有序判定 + taint 追踪 + scoped grants。

设计转译自 nanoMuse（github.com/nano-muse/nanoMuse, GPL-3.0）的
nanomuse/sentinel/{gate,policy,grants}.py——只学判定序与语义，零代码拷贝
（GPL 传染红线；锚点见 docs/research/2026-10-08-nanomuse.md §3.1）。

判定序（与 nanoMuse policy.py:72-143 同构，laos 化语义）：
    ① deny_tools 硬拒
    ② 显式规则（tool_glob，action=allow/ask/deny）——唯一能放行污点出站
       与终审警告的通道（= nanoMuse 的 egress allowlist 语义）
    ③ always_allow / always_ask 列表
    ④ 风险×模式：auto 全放 / strict 非 low 问 / ask（默认）不可逆或高风险问
    ⑤ taint 升级：污点 pid 的出站工具强制 ask（auto 也生效，永不回退）
    ⑥ 终审警告：不可逆且高风险 → ask 且仅 once 档 grant 可用
      （= nanoMuse "warnings 永不被 grant 覆盖"的 laos 化）
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Assessment:
    tool: str
    risk: str = "low"           # 对齐 ToolSpec.risk 口径（low/medium/high）
    reversible: bool = True     # 对齐 ToolSpec.reversible
    reads_private: bool = False  # 本调用是否读隐私源（供调用方事后 taint）
    egress: bool = False         # 本调用是否出站（信息离开本机/pid 域）


@dataclass(frozen=True)
class Decision:
    action: str                  # "allow" | "ask" | "deny"
    reason: str
    grant_scopes: tuple = ("once", "session", "always")


@dataclass
class SentinelConfig:
    deny_tools: tuple = ()
    rules: tuple = ()            # ({"tool_glob": str, "action": str}, ...)
    always_allow: tuple = ()
    always_ask: tuple = ()
    mode: str = "ask"            # "ask" | "auto" | "strict"
    private_tools: tuple = ("mem.recall", "mem.curate", "mic.read")
    egress_tools: tuple = ("msg.send",)


class Sentinel:
    """纯决策核：无 I/O、无线程；taint/grants 状态由本类持有（Task 2 扩展）。"""

    def __init__(self, config: SentinelConfig | None = None):
        self.cfg = config or SentinelConfig()

    def decide(self, a: Assessment, tainted: bool = False) -> Decision:
        import fnmatch
        cfg = self.cfg
        if a.tool in cfg.deny_tools:
            return Decision("deny", "deny-tools")
        for rule in cfg.rules:
            if fnmatch.fnmatch(a.tool, rule.get("tool_glob", "")):
                act = rule.get("action", "ask")
                if act == "deny":
                    return Decision("deny", "rule")
                if act == "allow":
                    return Decision("allow", "rule")
                return Decision("ask", "rule")
        if a.tool in cfg.always_allow:
            return Decision("allow", "always-allow")
        if a.tool in cfg.always_ask:
            return Decision("ask", "always-ask")
        # ④ 风险×模式
        if cfg.mode == "auto":
            pass  # auto 不在此级产生 ask（taint/警告仍可升级）
        elif cfg.mode == "strict":
            if a.risk != "low":
                return Decision("ask", "risk-mode")
        else:  # ask（默认）：不可逆或高风险才问（与 kernel 既有 confirm 口径对齐）
            if not a.reversible or a.risk == "high":
                return Decision("ask", "risk-mode")
        # ⑤ taint 升级：污点 + 出站（显式 allow 规则已在 ② 放行，到此的都是未豁免者）
        if tainted and a.egress:
            return Decision("ask", "taint-egress")
        # ⑥ 终审警告：不可逆且高风险——只有 once 档
        if not a.reversible and a.risk == "high":
            return Decision("ask", "warning-terminal", ("once",))
        return Decision("allow", "default")
```

- [ ] **Step 4: 跑绿**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_sentinel -v`
Expected: OK（10 tests）。

- [ ] **Step 5: Commit**

```bash
git add laos/sentinel.py tests/test_sentinel.py
git commit -m "feat(laos): sentinel 判定核——六级有序动作闸（nanoMuse 设计转译）"
```

---

### Task 2: GrantStore + TaintTracker

**Files:**
- Modify: `laos/sentinel.py`（追加两个类）
- Modify: `tests/test_sentinel.py`（追加 TestCase）

**Interfaces:**
- Consumes: Task 1 的 `Sentinel`。
- Produces（Task 3 依赖）:
  - `GrantStore.add(tool_glob: str, target: str | None = None, scope: str = "once") -> int`（返回 gid；scope ∈ {"once","session","always"}，非法值 ValueError）
  - `GrantStore.covers(tool: str, target: str | None = None) -> int | None`（命中返回 gid；once 档命中即消费删除；不命中 None）
  - `GrantStore.revoke(gid: int) -> bool`；`GrantStore.list_grants() -> list[dict]`
  - `Sentinel.mark_private_read(pid: int)` / `Sentinel.is_tainted(pid: int) -> bool` / `Sentinel.untaint(pid: int)`

- [ ] **Step 1: 追加失败测试**

```python
from laos.sentinel import GrantStore  # noqa: E402  （并入顶部 import 块）


class TestGrantStore(unittest.TestCase):
    def test_once_consumed_session_persists(self):
        g = GrantStore()
        gid = g.add("msg.send", scope="once")
        self.assertEqual(g.covers("msg.send"), gid)      # 首次命中并消费
        self.assertIsNone(g.covers("msg.send"))          # once 已耗
        s = g.add("fs.*", scope="session")
        self.assertEqual(g.covers("fs.write"), s)
        self.assertEqual(g.covers("fs.write"), s)        # session 可重复

    def test_target_binding_and_glob(self):
        g = GrantStore()
        gid = g.add("msg.send", target="pid:7", scope="always")
        self.assertIsNone(g.covers("msg.send", target="pid:8"))  # target 不符
        self.assertEqual(g.covers("msg.send", target="pid:7"), gid)
        self.assertEqual(g.covers("msg.send"), gid)      # 查询不带 target 视为通配命中

    def test_revoke_and_list(self):
        g = GrantStore()
        gid = g.add("shell", scope="always")
        rows = g.list_grants()
        self.assertEqual([(r["gid"], r["tool_glob"], r["scope"]) for r in rows],
                         [(gid, "shell", "always")])
        self.assertTrue(g.revoke(gid))
        self.assertFalse(g.revoke(gid))
        self.assertIsNone(g.covers("shell"))

    def test_bad_scope_rejected(self):
        with self.assertRaises(ValueError):
            GrantStore().add("x", scope="forever")


class TestTaintTracker(unittest.TestCase):
    def test_taint_never_auto_clears(self):
        s = Sentinel()
        self.assertFalse(s.is_tainted(7))
        s.mark_private_read(7)
        self.assertTrue(s.is_tainted(7))       # 只涨不清（nanoMuse：永不回退）
        s.untaint(7)                            # 唯一清除通道=进程退出
        self.assertFalse(s.is_tainted(7))

    def test_taint_per_pid(self):
        s = Sentinel()
        s.mark_private_read(1)
        self.assertFalse(s.is_tainted(2))
```

- [ ] **Step 2: 跑红**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_sentinel -v`
Expected: ERROR（ImportError: GrantStore）。

- [ ] **Step 3: 实现追加到 laos/sentinel.py**

```python
class GrantStore:
    """scoped grants：授权即能力（tool_glob+target 绑定+寿命档）。

    laos 化三档（nanoMuse 五档 once/conversation/session/24h/always 的子集，
    YAGNI）：once=单次消费、session=内核生命周期、always=同 session 但显式
    最高档（持久化留接线波）。线程安全（kernel 多线程 syscall 并发 covers）。
    """
    _SCOPES = ("once", "session", "always")

    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self._next = 1
        self._grants: dict[int, dict] = {}

    def add(self, tool_glob: str, target: str | None = None,
            scope: str = "once") -> int:
        import fnmatch
        if scope not in self._SCOPES:
            raise ValueError(f"scope must be one of {self._SCOPES}, got {scope!r}")
        fnmatch.fnmatch("", tool_glob)  # 早验 glob 合法性
        with self._lock:
            gid = self._next
            self._next += 1
            self._grants[gid] = {"gid": gid, "tool_glob": tool_glob,
                                 "target": target, "scope": scope}
            return gid

    def covers(self, tool: str, target: str | None = None) -> int | None:
        import fnmatch
        with self._lock:
            for gid, g in list(self._grants.items()):
                if fnmatch.fnmatch(tool, g["tool_glob"]):
                    if g["target"] is not None and target is not None \
                            and g["target"] != target:
                        continue
                    if g["scope"] == "once":
                        del self._grants[gid]
                    return gid
        return None

    def revoke(self, gid: int) -> bool:
        with self._lock:
            return self._grants.pop(gid, None) is not None

    def list_grants(self) -> list[dict]:
        with self._lock:
            return [dict(g) for g in self._grants.values()]
```

并扩展 `Sentinel.__init__` 与新增三个方法：

```python
    def __init__(self, config: SentinelConfig | None = None,
                 grants: GrantStore | None = None):
        self.cfg = config or SentinelConfig()
        self.grants = grants if grants is not None else GrantStore()
        import threading
        self._taint_lock = threading.Lock()
        self._tainted: set[int] = set()

    def mark_private_read(self, pid: int) -> None:
        with self._taint_lock:
            self._tainted.add(pid)

    def is_tainted(self, pid: int) -> bool:
        with self._taint_lock:
            return pid in self._tainted

    def untaint(self, pid: int) -> None:
        """进程退出时的唯一清除通道（kernel kill 路径调用）。"""
        with self._taint_lock:
            self._tainted.discard(pid)
```

- [ ] **Step 4: 跑绿**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_sentinel -v`
Expected: OK（16 tests）。

- [ ] **Step 5: Commit**

```bash
git add laos/sentinel.py tests/test_sentinel.py
git commit -m "feat(laos): GrantStore scoped 授权 + TaintTracker 污点追踪"
```

---

### Task 3: kernel opt-in 接线

**Files:**
- Modify: `laos/kernel.py`（构造参数 + syscall 闸门 + taint 钩子 + kill 清污点）
- Modify: `tests/test_sentinel.py`（追加 kernel 级 TestCase）

**Interfaces:**
- Consumes: Task 1/2 全部；kernel 既有 `self.confirm(op: dict) -> bool` 回调、`self._deny(pcb, tool, args, started, err)`、`spec.reversible/spec.risk`。
- Produces: `AgentKernel(..., sentinel: Sentinel | None = None)`；`kernel.sentinel` 属性（None 或实例）；审计新增 `event:"sentinel"` 行 `{"t","pid","tool","decision",decision.action,"reason","grant"}`。

- [ ] **Step 1: 追加失败测试（kernel 级）**

```python
class TestKernelSentinelWiring(unittest.TestCase):
    """kernel opt-in 接线：sentinel=None 字节级不变；装上后六步进闸门链。"""

    def setUp(self):
        import asyncio
        import tempfile

        from laos.context import ContextManager
        from laos.kernel import AgentKernel
        self._asyncio = asyncio
        self._td = tempfile.TemporaryDirectory()
        self._kernel_cls = AgentKernel
        self._ctx_cls = ContextManager

    def tearDown(self):
        self._td.cleanup()

    def _boot(self, sentinel=None, confirm=lambda op: True):
        k = self._kernel_cls(Path(self._td.name) / "var", confirm=confirm,
                             sentinel=sentinel)
        k.branches.create_root("main")
        pcb = k.spawn(name="a", caps=["mem.*", "msg.*"],
                      ctx=self._ctx_cls(system_prompt="t", max_tokens=2000),
                      branch="main")
        return k, pcb

    def _call(self, k, pcb, tool, args):
        return self._asyncio.run(k.syscall(pcb.pid, tool, args))

    def test_default_none_is_byte_compatible(self):
        k, pcb = self._boot()                     # 不装 sentinel
        res = self._call(k, pcb, "msg.send", {"to_pid": 1, "text": "hi"})
        self.assertTrue(res.ok, res.error)
        self.assertFalse([r for r in k.audit.records
                          if r.get("event") == "sentinel"])

    def test_ask_flow_via_confirm_and_audit(self):
        s = Sentinel(SentinelConfig(mode="ask"))   # msg.send 不可逆 → risk-mode ask
        confirms = []
        k, pcb = self._boot(sentinel=s, confirm=lambda op:
                            (confirms.append(op) or True))
        res = self._call(k, pcb, "msg.send", {"to_pid": 1, "text": "hi"})
        self.assertTrue(res.ok, res.error)
        self.assertEqual(len(confirms), 1)
        self.assertEqual(confirms[0]["sentinel"], "risk-mode")
        rows = [r for r in k.audit.records if r.get("event") == "sentinel"]
        self.assertEqual([(r["tool"], r["decision"]) for r in rows],
                         [("msg.send", "ask")])

    def test_confirm_denied_blocks(self):
        s = Sentinel(SentinelConfig(mode="ask"))
        k, pcb = self._boot(sentinel=s, confirm=lambda op: False)
        res = self._call(k, pcb, "msg.send", {"to_pid": 1, "text": "hi"})
        self.assertFalse(res.ok)
        self.assertIn("sentinel", res.error)

    def test_session_grant_skips_confirm(self):
        s = Sentinel(SentinelConfig(mode="ask"))
        s.grants.add("msg.send", scope="session")
        confirms = []
        k, pcb = self._boot(sentinel=s, confirm=lambda op:
                            (confirms.append(op) or True))
        res = self._call(k, pcb, "msg.send", {"to_pid": 1, "text": "hi"})
        self.assertTrue(res.ok, res.error)
        self.assertEqual(confirms, [])            # grant 覆盖，不再问人
        rows = [r for r in k.audit.records if r.get("event") == "sentinel"]
        self.assertEqual(rows[-1]["grant"], s.grants)  # 审计带 grant gid（见 Step 3）

    def test_private_read_taints_then_egress_asks_even_auto(self):
        s = Sentinel(SentinelConfig(mode="auto"))
        confirms = []
        k, pcb = self._boot(sentinel=s, confirm=lambda op:
                            (confirms.append(op) or True))
        self._call(k, pcb, "mem.remember",
                   {"kind": "fact", "text": "用户偏好中文", "tags": ["偏好"]})
        res = self._call(k, pcb, "mem.recall", {"query": "偏好", "k": 3})
        self.assertTrue(res.ok)
        self.assertTrue(s.is_tainted(pcb.pid))    # 隐私读 → 污点
        self._call(k, pcb, "msg.send", {"to_pid": 1, "text": "hi"})
        self.assertEqual(confirms[-1]["sentinel"], "taint-egress")  # auto 也问

    def test_kill_untaints(self):
        s = Sentinel(SentinelConfig(mode="auto"))
        k, pcb = self._boot(sentinel=s)
        self._call(k, pcb, "mem.recall", {"query": "x"})
        self.assertTrue(s.is_tainted(pcb.pid))
        k.kill(pcb.pid)
        self.assertFalse(s.is_tainted(pcb.pid))
```

（注：`rows[-1]["grant"]` 断言在 Step 3 实现后语义为 grant gid int 或 None——测试写成：`self.assertIsNotNone(rows[-1]["grant"])`。）

- [ ] **Step 2: 跑红**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_sentinel -v`
Expected: ERROR（AgentKernel 不接受 sentinel 参数）。

- [ ] **Step 3: kernel.py 三处接线**

① 构造（`kernel.py:246` 附近参数表加一行，`self.confirm` 赋值行后加）：

```python
        sentinel: "Sentinel | None" = None,      # 动作闸 opt-in（nanoMuse 采纳，
                                                 # None=字节级不变；见 laos/sentinel.py）
```
```python
        self.sentinel = sentinel
```

② syscall 闸门链——插在 task_scope 检查之后、`# 不可逆闸门 2.0` 之前：

```python
        # Sentinel 动作闸（opt-in）：六级判定在既有闸门之后、不可逆闸之前；
        # ask=走既有 confirm 回调（grants 先查，覆盖则免问）；deny=EDENIED
        if self.sentinel is not None:
            from .sentinel import Assessment
            assessment = Assessment(
                tool=tool, risk=getattr(spec, "risk", "low"),
                reversible=getattr(spec, "reversible", True),
                reads_private=tool in self.sentinel.cfg.private_tools,
                egress=tool in self.sentinel.cfg.egress_tools)
            decision = self.sentinel.decide(
                assessment, tainted=self.sentinel.is_tainted(pid))
            grant_gid = None
            if decision.action == "deny":
                return self._deny(pcb, tool, args, started,
                                  f"EDENIED: sentinel {decision.reason}")
            if decision.action == "ask":
                grant_gid = self.sentinel.grants.covers(tool)
                scopes_ok = (grant_gid is not None
                             and (decision.grant_scoses
                                  if False else decision.grant_scopes)
                             and grant_gid is not None)
                # 终审警告只认 once 档：covers 已消费 once；session/always 命中
                # 则要求该档位在 grant_scopes 内
                if grant_gid is None and "session" in decision.grant_scopes:
                    pass  # covers 返回 None 即无人覆盖
                if (grant_gid is None
                        or ("session" not in decision.grant_scopes
                            and "always" not in decision.grant_scopes)):
                    if not self.confirm({"tool": tool, "args": args,
                                         "sentinel": decision.reason}):
                        return self._deny(
                            pcb, tool, args, started,
                            "EACCES: sentinel requires confirmation")
            self.audit.write({"t": time.time(), "event": "sentinel",
                              "pid": pid, "tool": tool,
                              "decision": decision.action,
                              "reason": decision.reason, "grant": grant_gid})
```

（实现时把上面 ask 分支化简为等价的清晰版本：先 `grant_gid = self.sentinel.grants.covers(tool) if "session" in decision.grant_scopes or "always" in decision.grant_scopes else (self.sentinel.grants.covers(tool) and None)`——终审警告（grant_scopes 只含 once）时**不要**用 covers 消费 once 之外还要 confirm 的语义见测试：warnings 场景 grant 不可用，恒走 confirm。最简正确实现：

```python
            if decision.action == "ask":
                grant_gid = None
                if set(decision.grant_scopes) & {"session", "always"}:
                    grant_gid = self.sentinel.grants.covers(tool)
                if grant_gid is None and not self.confirm(
                        {"tool": tool, "args": args,
                         "sentinel": decision.reason}):
                    return self._deny(pcb, tool, args, started,
                                      "EACCES: sentinel requires confirmation")
```

③ 成功路径 taint 标记 + kill 清污点：

- `_impl_mem_recall` 与 `_impl_mem_curate` 成功返回前各加：
```python
        if self.sentinel is not None:
            self.sentinel.mark_private_read(pcb.pid)
```
- `kill()`（`_drop_delegations_by` 调用处同函数内）加：
```python
        if self.sentinel is not None:
            self.sentinel.untaint(pid)
```

- [ ] **Step 4: 跑绿 + 全量回归**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_sentinel tests.test_memory tests.test_ipc tests.test_jitmem -v` 然后 `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`
Expected: 新 22 例绿 + 全套 OK（946+22）。

- [ ] **Step 5: Commit**

```bash
git add laos/kernel.py tests/test_sentinel.py
git commit -m "feat(laos): kernel opt-in 接线 sentinel——ask 走 confirm、grants 免问、隐私读置污点、kill 清污"
```

---

### Task 4: 记忆 provenance（origin + 用户行豁免）

**Files:**
- Modify: `laos/memory.py`（remember 加 origin/origin_pid；recall 透出）
- Modify: `laos/jitmem.py`（curate 用户行豁免预算与去重）
- Modify: `laos/kernel.py`（_impl_mem_remember 传 origin="agent", origin_pid）
- Modify: `bin/diary.py`（自记日记行 origin="diary"）
- Test: `tests/test_sentinel.py` 追加 TestProvenance

**Interfaces:**
- Consumes: MemoryStore.remember 现签名 `(kind, text, tags=None, judge=None)`；jitmem.curate 预算/去重循环。
- Produces: 新行必含 `"origin": "agent"|"user"|"diary"` 与 `"origin_pid": int|None`；旧行缺字段时读取侧按 `"agent"` 处理。

- [ ] **Step 1: 追加失败测试**

```python
class TestProvenance(unittest.TestCase):
    def setUp(self):
        import tempfile

        from laos.jitmem import Curator
        from laos.memory import MemoryStore
        self._td = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self._td.name) / "m.jsonl")
        self.Curator = Curator

    def tearDown(self):
        self._td.cleanup()

    def test_remember_origin_defaults_agent(self):
        r = self.store.remember("fact", "x")
        self.assertEqual((r["origin"], r["origin_pid"]), ("agent", None))
        r2 = self.store.remember("fact", "y", origin="user")
        self.assertEqual(r2["origin"], "user")

    def test_old_rows_without_origin_read_as_agent(self):
        import json
        path = Path(self._td.name) / "m.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": 99, "ts": 1.0, "kind": "fact",
                                 "text": "旧记录", "tags": []}) + "\n")
        rows = self.store.recall("旧记录", k=5)
        self.assertEqual(rows[0].get("origin", "agent"), "agent")

    def test_curate_user_line_survives_budget_and_dedup(self):
        # "人写的一行胜过模型写的任何行"：用户行不进预算淘汰、不被近重复去重
        self.store.remember("fact", "好" * 200, origin="user",
                            tags=["甲"])          # 超预算的用户行
        self.store.remember("fact", "好" * 200, tags=["甲"])   # 近重复的 agent 行
        p = self.Curator(self.store, budget_chars=120).curate("甲事")
        texts = [(e["text"], e.get("origin")) for e in p["entries"]]
        self.assertIn(("好" * 200, "user"), texts)
        self.assertEqual(sum(1 for _, o in texts if o == "agent"), 0)  # agent 重复行被丢
```

- [ ] **Step 2: 跑红**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_sentinel.TestProvenance -v`
Expected: FAIL（remember 不接受 origin 参数）。

- [ ] **Step 3: 实现（四处小改）**

`laos/memory.py` remember 签名与行构造：

```python
    def remember(self, kind: str, text: str, tags: list[str] | None = None,
                 judge: Any | None = None, origin: str = "agent",
                 origin_pid: int | None = None) -> dict | None:
```
```python
            rec = {"id": self._next_id, "ts": time.time(), "kind": str(kind),
                   "text": str(text), "tags": [str(t) for t in (tags or [])],
                   "origin": str(origin), "origin_pid": origin_pid}
```

`laos/jitmem.py` 去重循环（预算前置的同构修改）：

```python
        for s in scored:
            rec = s["rec"]
            if str(rec.get("origin", "agent")) == "user":
                kept.append(s)          # 用户行神圣：不参与去重
                continue
            dup = any(bigram_jaccard(str(rec.get("text", "")),
                                     str(k2["rec"].get("text", "")))
                      >= self.dup_threshold for k2 in kept)
            ...
```
预算循环：

```python
        for s in kept:
            if str(s["rec"].get("origin", "agent")) == "user":
                entries.append(s)       # 用户行豁免预算（nanoMuse "永不删用户行"）
                continue
            cost = ...
```
（stats 里用户行计入 entries 正常计数，不计 budget_dropped。）

`laos/kernel.py` `_impl_mem_remember` 的 self.memory.remember(...) 调用加 `origin="agent", origin_pid=pcb.pid`。

`bin/diary.py` 找 `MemoryStore(...).remember("diary"` 处（consolidated 自记行）加 `origin="diary"`。

- [ ] **Step 4: 跑绿 + 全量**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`
Expected: OK（946+25 全绿；旧 self_check 里临时条目 remember 调用不带 origin → 默认 "agent"，行为不变）。

- [ ] **Step 5: Commit**

```bash
git add laos/memory.py laos/jitmem.py laos/kernel.py bin/diary.py tests/test_sentinel.py
git commit -m "feat(laos): 记忆 provenance——origin/origin_pid 字段 + curate 用户行豁免（人写行胜模型行）"
```

---

### Task 5: 登记 + 发版 v0.28.0

**Files:**
- Modify: `docs/research/INDEX.md`（新行 + 计数 86→87）
- Modify: `CHANGELOG.md`（v0.28.0 段）
- 全部由发版纪律工具同步其余介绍文档

**Interfaces:** Consumes: Task 1–4 全部提交。Produces: tag v0.28.0 + GitHub Release 页。

- [ ] **Step 1: INDEX 登记**

在 `2026-10-08-nanomuse` 报告行后追加（表尾，紧接 dialogflow-assembly 行）：

```markdown
| [2026-10-08-nanomuse.md](2026-10-08-nanomuse.md) | nanoMuse 学习（论文 arXiv:2610.08699+源码 33 次 API 直读）：Meta Muse 开源对照物的 Sentinel 动作闸/taint/scoped grants/记忆双线全拆解——laos 采纳落地 laos/sentinel.py + provenance | Sentinel 六级判定序+taint 永不回退+warnings 仅 once 档（20 例测试）；自认"policy 边界非特权边界"=laos caps+seccomp 的差异化定位；Muse 复刻段（seccomp+kernel taint+Sentinel 唯一权限权威）为 laos 叙事商业印证；GPL 红线=只学设计零代码拷贝 |
```
头部计数：`共 86 份`→`共 87 份`、`87 = 86`→`88 = 87`、`调研文档 64 份`→`65 份`。

- [ ] **Step 2: CHANGELOG 插段**

在 `## [Unreleased]` 后插入 v0.28.0 段（Added 两条：sentinel 波 25 例测试 + nanomuse 报告条目；写法参照 v0.27.0 段密度）。

- [ ] **Step 3: 发版全流程**

```bash
C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q   # 必须全绿
C:/Users/yaoyue/miniconda3/python.exe scripts/release.py --apply
git add -A && git commit -m "release: v0.28.0 — sentinel wave (971 tests)"
git tag -a v0.28.0 -m "v0.28.0 — nanoMuse adoption: sentinel action gate + taint + scoped grants + memory provenance; 25 new tests"
git push origin master && git push origin v0.28.0
```
再按既定 json 文件法建 GitHub Release 页（body=CHANGELOG 段 + compare 链接）。

- [ ] **Step 4: 验证**

`git status --short` 为空；`git ls-remote --tags origin | grep v0.28.0` 存在；README 首行测试计数= 实跑数（946+25=971）。

- [ ] **Step 5: Commit**

```bash
git add docs/research/INDEX.md CHANGELOG.md
git commit -m "docs(research): nanomuse 学习报告登记 + CHANGELOG v0.28.0"
```

---

## Self-Review 记录

1. **Spec 覆盖**：裁决 #1（sentinel+taint+grants）= Task 1/2/3；裁决 #2（provenance）= Task 4；登记发版 = Task 5；裁决 #5/#6（不做项）无任务对应（正确）。
2. **占位符扫描**：无 TBD；Task 3 Step 3 的第一版 ask 分支草稿刻意保留了"化简为等价清晰版本"的指引——以最简正确实现（第二段代码）为准，测试断言以 Step 1 为准（grant gid 非空断言）。
3. **类型一致性**：Assessment/Decision/SentinelConfig 字段在 Task 1 定义、Task 3 按同名使用；GrantStore.covers 返回 int|None 三处一致；remember 新参数默认值保证旧调用零变化（self_check/jitmem 旧测试不破）。
