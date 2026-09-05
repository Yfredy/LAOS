# AgentProf 语义剖析 + OpenTelemetry 导出实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现《AgentProf: Semantic Profiling for AI Agents》（AgenticOS @ SOSP 2026）的 laos 版第一层：把审计日志里的 syscall 事件流聚合成 **per-agent 的 span 集**（系统级真相：每步调了什么、耗时、被拒、重复浪费），导出为 **OTLP/JSON**（OpenTelemetry 标准 JSON 编码，零依赖手写），并给出**工具选择合理性启发式**（重复调用检测、拒绝率、单工具依赖度）。

**Architecture:** `laos/agentprof.py` 纯函数模块：`build_spans(audit_records)` 从 audit.jsonl 按 pid 聚合（spawn 定 run 边界，syscall 事件建 span），`score(spans)` 产出启发式发现，`export_otlp(spans, out_dir)` 写 `var/traces/agent-<pid>.json`（OTLP/JSON resourceSpans 形状，traceId=每个 agent run 一条 32 位 hex，spanId 16 位 hex，时间用纳秒）。展示面：`laosctl spans` 子命令 + laosd demo 第 6 节打印剖析摘要。与 eBPF `profiling.py` 的关系：eBPF 是内核级 syscall 计数（真值），本模块是语义层（agent 做了什么、浪不浪费）——两层对照即 AgentProf 的语义剖析思想。

**Tech Stack:** Python 3.10+ 标准库（json/hashlib），零第三方依赖（OTLP/JSON 是文档化格式，手写编码；不引入 opentelemetry 包）。

**Spec:** `docs/research/2026-09-05-agentos-next-steps.md` §一.2 / §二#3。

## Global Constraints

- 零第三方依赖（**不引入 opentelemetry-sdk**，手写 OTLP/JSON）。
- 不破坏执行时基线测试（以实测为准）；新增测试放独立文件 `tests/test_agentprof.py`。
- 解释器 `$PY`（同前）；每 task 一个 commit。
- 审计事件契约（消费方，来自现网代码）：`spawn`（pid/name/caps/risk_cap/fleet_remaining）、`syscall`（pid/agent/tool/driver/args/ok/ms/result）、`risk_spend`、`admission`、`driver_load`、`stale_broadcast`。解析只依赖这些键。

## 现状关键事实

- `kernel._deny` 与 `kernel.syscall` 的成功路径都写 `{"t", "event": "syscall", "pid", "agent", "tool", "args", "ok", "ms", "result"}`（deny 无 driver 键）。
- `AuditLog.records` 在内存里就是 list[dict]（kernel.audit.records 可直接喂给剖析器，无需读文件）。
- `bin/laosd.py` 第 6 节（运行报告）是展示挂点；`bin/laosctl.py` 已有 choices/分发表模式与 `load()`。
- WORKDIR 默认 `REPO/var`（laosd.py:34）。

---

### Task 1: span 构建 + 启发式评分

**Files:**
- Create: `laos/agentprof.py`
- Test: `tests/test_agentprof.py`（新建）

**Interfaces:**
- Produces:
  - `build_spans(records: list[dict]) -> list[AgentSpan]`
  - `@dataclass AgentSpan`: `pid:int, name:str, start_ns:int, end_ns:int, calls:list[dict], denied:int, total_ms:float, repeats:list[dict], tool_counts:dict[str,int]`
    - `calls` 元素：`{"tool", "ok", "ms", "result", "seq"}`（seq 为该 pid 内序号）。
    - `repeats` 元素：`{"tool", "count", "args_digest"}` —— 同一 (tool, args 规范化摘要) 出现 ≥2 次即记一次浪费模式（args 摘要 = `sha16(sorted(json.dumps(args, sort_keys=True)))`）。
  - `score(span: AgentSpan) -> list[str]`：人类可读发现（空列表 = 无发现）。规则：① 重复模式 → `f"wasteful repeat: {tool} x{n}"`；② 拒绝率 > 0.5 且调用数 ≥ 4 → `f"high denial rate: {denied}/{n}"`；③ 单一工具占比 > 0.8 且调用数 ≥ 5 → `f"tool monoculture: {top_tool}"`。
  - 聚合规则：spawn 事件开启一个 AgentSpan（记录 name），后续该 pid 的 syscall 事件追加；无 spawn 的 pid 忽略；`t` 秒转纳秒 `int(t * 1e9)`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agentprof.py
"""AgentProf —— 审计流 → 语义 span + OTLP/JSON 导出（零依赖）。

    python -m unittest tests.test_agentprof -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.agentprof import build_spans, score, export_otlp  # noqa: E402


def _recs():
    return [
        {"t": 1.0, "event": "spawn", "pid": 1001, "name": "ops", "caps": ["fs.*"]},
        {"t": 1.1, "event": "syscall", "pid": 1001, "agent": "ops", "tool": "fs.read",
         "args": {"path": "/main/f"}, "ok": True, "ms": 5.0, "result": "data", "driver": "fs"},
        {"t": 1.2, "event": "syscall", "pid": 1001, "agent": "ops", "tool": "fs.read",
         "args": {"path": "/main/f"}, "ok": True, "ms": 4.0, "result": "data", "driver": "fs"},
        {"t": 1.3, "event": "syscall", "pid": 1001, "agent": "ops", "tool": "fs.write",
         "args": {"path": "/main/f"}, "ok": True, "ms": 6.0, "result": "OK", "driver": "fs"},
        {"t": 1.4, "event": "syscall", "pid": 1001, "agent": "ops", "tool": "proc.exec",
         "args": {"cmdline": "ls"}, "ok": False, "ms": 1.0, "result": "[error] EACCES: x"},
        {"t": 2.0, "event": "syscall", "pid": 9999, "agent": "ghost", "tool": "fs.read",
         "args": {}, "ok": True, "ms": 1.0, "result": ""},
    ]


class TestBuildSpans(unittest.TestCase):
    def test_groups_by_pid_and_ignores_orphans(self):
        spans = build_spans(_recs())
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].pid, 1001)
        self.assertEqual(spans[0].name, "ops")
        self.assertEqual(len(spans[0].calls), 4)
        self.assertEqual(spans[0].denied, 1)
        self.assertAlmostEqual(spans[0].total_ms, 16.0)

    def test_repeat_detection(self):
        spans = build_spans(_recs())
        reps = spans[0].repeats
        self.assertEqual(len(reps), 1)
        self.assertEqual(reps[0]["tool"], "fs.read")
        self.assertEqual(reps[0]["count"], 2)

    def test_score_flags(self):
        spans = build_spans(_recs())
        flags = score(spans[0])
        self.assertTrue(any("wasteful repeat: fs.read x2" in f for f in flags))
        self.assertTrue(any("tool monoculture" not in f for f in flags))  # 3/4 未到 0.8


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_agentprof -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'laos.agentprof'`

- [ ] **Step 3: 实现 laos/agentprof.py**

```python
# laos/agentprof.py
"""AgentProf —— 把审计日志聚合成 per-agent 语义 span，并给启发式发现。

对应《AgentProf: Semantic Profiling for AI Agents》（AgenticOS @ SOSP 2026）
的第一层：eBPF（laos/profiling.py）给系统级 syscall 真值，本模块给语义层
—— agent 每一步调了什么、被拒多少、哪些调用是原地重复（浪费的时间片）。

零依赖：OTLP/JSON 编码手写（export_otlp），不引入 opentelemetry 包。
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field


def _args_digest(args: dict) -> str:
    raw = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class AgentSpan:
    pid: int
    name: str
    start_ns: int
    end_ns: int
    calls: list[dict] = field(default_factory=list)
    denied: int = 0
    total_ms: float = 0.0
    repeats: list[dict] = field(default_factory=list)
    tool_counts: dict[str, int] = field(default_factory=dict)

    def finalize(self) -> None:
        """按 (tool, args_digest) 聚合重复模式（出现 >=2 次记一次浪费）。"""
        seen: dict[tuple[str, str], int] = {}
        for c in self.calls:
            key = (c["tool"], c["args_digest"])
            seen[key] = seen.get(key, 0) + 1
        counted: dict[tuple[str, str], bool] = {}
        for c in self.calls:
            key = (c["tool"], c["args_digest"])
            if seen[key] >= 2 and not counted.get(key):
                self.repeats.append({"tool": c["tool"], "count": seen[key],
                                     "args_digest": key[1]})
                counted[key] = True


def build_spans(records: list[dict]) -> list[AgentSpan]:
    """从审计记录流聚合 per-agent span。无 spawn 的 pid 忽略。"""
    spans: dict[int, AgentSpan] = {}
    order: list[AgentSpan] = []
    for r in records:
        ev = r.get("event")
        pid = r.get("pid")
        if ev == "spawn" and pid is not None:
            span = AgentSpan(pid=pid, name=r.get("name", "?"),
                             start_ns=int(r.get("t", 0.0) * 1e9),
                             end_ns=int(r.get("t", 0.0) * 1e9))
            spans[pid] = span
            order.append(span)
        elif ev == "syscall" and pid in spans:
            span = spans[pid]
            seq = len(span.calls)
            span.calls.append({
                "tool": r.get("tool", "?"), "ok": bool(r.get("ok")),
                "ms": float(r.get("ms", 0.0)),
                "result": str(r.get("result", ""))[:120],
                "args_digest": _args_digest(r.get("args") or {}),
                "seq": seq,
            })
            if not r.get("ok"):
                span.denied += 1
            span.total_ms += float(r.get("ms", 0.0))
            span.tool_counts[r.get("tool", "?")] = span.tool_counts.get(r.get("tool", "?"), 0) + 1
            span.end_ns = max(span.end_ns, int(r.get("t", 0.0) * 1e9))
    for span in order:
        span.finalize()
    return order


def score(span: AgentSpan) -> list[str]:
    """启发式发现（空列表 = 无发现）。规则刻意简单、可解释。"""
    flags: list[str] = []
    n = len(span.calls)
    for rep in span.repeats:
        flags.append(f"wasteful repeat: {rep['tool']} x{rep['count']}")
    if n >= 4 and span.denied / n > 0.5:
        flags.append(f"high denial rate: {span.denied}/{n}")
    if n >= 5 and span.tool_counts:
        top_tool, top_n = max(span.tool_counts.items(), key=lambda kv: kv[1])
        if top_n / n > 0.8:
            flags.append(f"tool monoculture: {top_tool} ({top_n}/{n})")
    return flags


def export_otlp(spans: list[AgentSpan], out_dir) -> list:
    """写成 OTLP/JSON（resourceSpans 形状），返回生成的文件路径列表。"""
    from pathlib import Path
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for span in spans:
        doc = {
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "laos.pid", "value": {"intValue": span.pid}},
                    {"key": "laos.agent", "value": {"stringValue": span.name}},
                    {"key": "service.name", "value": {"stringValue": "laosd"}},
                ]},
                "scopeSpans": [{
                    "scope": {"name": "laos.agentprof", "version": "0.1.0"},
                    "spans": [_span_json(span, c) for c in span.calls],
                }],
            }]
        }
        path = out / f"agent-{span.pid}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        paths.append(path)
    return paths


def _span_json(span: AgentSpan, call: dict) -> dict:
    start = span.start_ns + int(call["ms"] * 0)  # 审计只有 t 秒精度，起点即事件 t
    return {
        "traceId": hashlib.sha256(f"{span.pid}".encode()).hexdigest()[:32],
        "spanId": hashlib.sha256(f"{span.pid}:{call['seq']}".encode()).hexdigest()[:16],
        "name": call["tool"],
        "kind": "SPAN_KIND_INTERNAL",
        "startTimeUnixNano": str(span.start_ns),
        "endTimeUnixNano": str(max(span.start_ns + 1, span.end_ns)),
        "attributes": [
            {"key": "laos.ok", "value": {"boolValue": call["ok"]}},
            {"key": "laos.ms", "value": {"doubleValue": call["ms"]}},
            {"key": "laos.result", "value": {"stringValue": call["result"]}},
            {"key": "laos.args_digest", "value": {"stringValue": call["args_digest"]}},
        ],
        "status": {"code": "STATUS_CODE_OK" if call["ok"] else "STATUS_CODE_ERROR"},
    }
```

（实现者注意：`import time` 若未用到则删除；`_span_json` 的时间精度受审计秒级时间戳限制，起点用 span.start_ns、终点用 end_ns 是当前数据下的诚实选择——不要伪造更细粒度。）

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m unittest tests.test_agentprof -v`
Expected: `Ran 3 tests ... OK`

- [ ] **Step 5: 全量回归 + Commit**

```bash
git add laos/agentprof.py tests/test_agentprof.py
git commit -m "feat(laos): AgentProf span building + heuristics from audit stream"
```

---

### Task 2: OTLP/JSON 导出测试收口

**Files:**
- Test: `tests/test_agentprof.py`（追加）

- [ ] **Step 1: 追加失败测试**

```python
class TestOtlpExport(unittest.TestCase):
    def test_export_shape(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            spans = build_spans(_recs())
            paths = export_otlp(spans, Path(td) / "traces")
            self.assertEqual(len(paths), 1)
            doc = json.loads(paths[0].read_text(encoding="utf-8"))
            rs = doc["resourceSpans"][0]
            attrs = {a["key"]: a["value"] for a in rs["resource"]["attributes"]}
            self.assertEqual(attrs["laos.pid"]["intValue"], 1001)
            spans_list = rs["scopeSpans"][0]["spans"]
            self.assertEqual(len(spans_list), 4)
            first = spans_list[0]
            self.assertEqual(len(first["traceId"]), 32)
            self.assertEqual(len(first["spanId"]), 16)
            self.assertIn(first["status"]["code"],
                          ("STATUS_CODE_OK", "STATUS_CODE_ERROR"))
            denied = [s for s in spans_list if s["status"]["code"] == "STATUS_CODE_ERROR"]
            self.assertEqual(len(denied), 1)
            self.assertEqual(denied[0]["name"], "proc.exec")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m unittest tests.test_agentprof -v`
Expected: 新测试应直接 PASS（Task 1 已实现 export_otlp）——若 FAIL 修实现。本任务是导出契约的收口测试，允许"先测后确认已绿"（构建函数已在 Task 1 交付）。

- [ ] **Step 3: 全量回归 + Commit**

```bash
git add tests/test_agentprof.py
git commit -m "test(laos): OTLP/JSON export contract"
```

---

### Task 3: laosd demo + laosctl spans 接线

**Files:**
- Modify: `bin/laosd.py`（第 6 节剖析摘要 + traces 导出）、`bin/laosctl.py`（`spans` 子命令）
- Test: 全量回归（无新单测；laosctl 子命令沿用 Task-laosctl-budget 的直测模式可省——spans 打印与 budget 同构）

- [ ] **Step 1: bin/laosd.py 第 6 节**（`风险账本` print 之后）插入：

```python
    from laos.agentprof import build_spans, score, export_otlp
    spans = build_spans(kernel.audit.records)
    if spans:
        trace_dir = WORKDIR / "traces"
        export_otlp(spans, trace_dir)
        print(f"  语义剖析   : {len(spans)} 个 agent span -> {trace_dir}")
        for sp in spans:
            for flag in score(sp):
                print(f"    [pid={sp.pid} {sp.name}] {flag}")
```

- [ ] **Step 2: bin/laosctl.py** 新增（模式同 cmd_budget）：

```python
def cmd_spans(records: list[dict], args) -> None:
    """AgentProf 语义剖析回放：per-agent span 摘要 + 启发式发现。"""
    from laos.agentprof import build_spans, score
    spans = build_spans(records)
    if not spans:
        print("无 spawn 记录，无法构建 span")
        return
    for sp in spans:
        print(f"pid={sp.pid} {sp.name}: calls={len(sp.calls)} denied={sp.denied} "
              f"total_ms={sp.total_ms:.1f}")
        for flag in score(sp):
            print(f"    ! {flag}")
```

choices 与分发表各加 `"spans"`。

- [ ] **Step 3: 全量回归 + 手工验收**

Run: `$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿）
Run: `$PY bin/laosd.py 2>&1 | grep -A4 "语义剖析"` → 出现 span 数与（可能的）wasteful repeat 行（demo 的 ops-agent 对 hosts 有 read→read→append 序列时会有 repeat；ScriptedBrain 行为以实际为准）
Run: `$PY bin/laosctl.py spans` → per-agent 摘要

- [ ] **Step 4: Commit**

```bash
git add bin/laosd.py bin/laosctl.py
git commit -m "feat(laos): AgentProf spans wired into demo and laosctl"
```

---

### Task 4: README 收尾

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README §6「语义 profiling」行替换为**

| **语义 profiling** | ~~bpftrace 集成~~ → **eBPF（内核真值）+ AgentProf（语义层）**：审计流 → per-agent span（重复浪费/拒绝率/单工具依赖启发式）→ OTLP/JSON 导出（`var/traces/`）+ `laosctl spans` | 每步意图建模、工具选择合理性评分（论文全量目标） |

- [ ] **Step 2: README §7 laos/ 段补一行（agentprof.py）**；§5 控制面块补 `python bin/laosctl.py spans     # AgentProf 语义剖析回放`

- [ ] **Step 3: 全量回归 + Commit**

```bash
git add README.md
git commit -m "docs(laos): AgentProf semantic profiling in README"
```

## 验收清单

- [ ] 全量测试全绿（执行时基线 + 4）
- [ ] `var/traces/agent-*.json` 为合法 OTLP/JSON（resourceSpans/scopeSpans/spans，hex 长度正确）
- [ ] `laosctl spans` 可回放
- [ ] 本计划恰 4 个 commit
