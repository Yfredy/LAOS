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
from dataclasses import dataclass, field
from pathlib import Path


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
    # 审计只有 t 秒精度：起点用 span.start_ns、终点用 end_ns 是当前数据下的
    # 诚实选择——不伪造比审计更细的时间粒度。
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
