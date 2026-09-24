#!/usr/bin/env python3
"""laosctl —— AgentOS 的控制面 / 事后审计工具（类似 ps / lsmod / strace）。

laosd 的内核状态在内存里，laosctl 通过持久化的审计日志做回放与统计：

    python bin/laosctl.py audit                 # 全部审计事件
    python bin/laosctl.py trace --pid 1001      # 回放某个 Agent 的 syscall
    python bin/laosctl.py denied                # 所有被拒绝的调用
    python bin/laosctl.py top                   # 按 syscall 聚合耗时
    python bin/laosctl.py prof                  # eBPF 采集的真实 syscall 分布
    python bin/laosctl.py budget                # 车队风险账本回放（Irreversibility Budget 2.0）
    python bin/laosctl.py spans                 # AgentProf 语义剖析回放
    python bin/laosctl.py selfcheck             # memory 存储自检（scratch store，不碰 var/memory.jsonl）
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = REPO / "var" / "audit.jsonl"
sys.path.insert(0, str(REPO))  # cmd_spans 需要 import laos.agentprof（同 laosd.py）


def load(path: Path) -> list[dict]:
    if not path.exists():
        print(f"审计日志不存在: {path}", file=sys.stderr)
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def cmd_audit(records: list[dict], args) -> None:
    for r in records:
        if args.event and r.get("event") != args.event:
            continue
        print(json.dumps(r, ensure_ascii=False))


def cmd_trace(records: list[dict], args) -> None:
    for r in records:
        if r.get("event") != "syscall":
            continue
        if args.pid and r.get("pid") != args.pid:
            continue
        flag = "OK " if r["ok"] else "ERR"
        print(f"[{flag}] pid={r['pid']} {r['tool']}({r.get('args', {})}) -> {r['result'][:200]}")


def cmd_denied(records: list[dict], args) -> None:
    n = 0
    for r in records:
        if r.get("event") == "syscall" and not r["ok"]:
            n += 1
            print(f"pid={r['pid']} {r['tool']} -> {r['result']}")
    print(f"\n共 {n} 次被拒绝")


def cmd_top(records: list[dict], args) -> None:
    cnt: Counter = Counter()
    dur: dict[str, float] = defaultdict(float)
    for r in records:
        if r.get("event") != "syscall":
            continue
        cnt[r["tool"]] += 1
        dur[r["tool"]] += r.get("ms", 0)
    print(f"{'syscall':<16}{'count':>8}{'total_ms':>12}{'avg_ms':>10}")
    for tool, c in cnt.most_common():
        print(f"{tool:<16}{c:>8}{dur[tool]:>12.2f}{dur[tool] / c:>10.2f}")


# 内核层拒绝的 errno（区别于"到达驱动但被驱动拒绝"）
KERNEL_ERRNO = ("EPERM", "EACCES", "ENOSYS", "EDQUOT", "ESRCH")


def cmd_ps(records: list[dict], args) -> None:
    procs: dict = {}
    for r in records:
        if r.get("event") == "spawn":
            procs[r["pid"]] = {
                "name": r["name"],
                "caps": r["caps"],
                "syscalls": 0,
                "denied": 0,
                "failed": 0,
            }
        elif r.get("event") == "syscall" and r["pid"] in procs:
            if r["ok"]:
                procs[r["pid"]]["syscalls"] += 1
            elif str(r.get("result", "")).startswith(KERNEL_ERRNO):
                procs[r["pid"]]["denied"] += 1  # 内核能力表拦下
            else:
                procs[r["pid"]]["failed"] += 1  # 到达驱动，被驱动拒绝
    print(f"{'pid':<8}{'name':<16}{'syscalls':>10}{'denied':>8}{'failed':>8}  caps")
    for pid, p in procs.items():
        print(
            f"{pid:<8}{p.get('name', '?'):<16}{p['syscalls']:>10}"
            f"{p['denied']:>8}{p['failed']:>8}  {p.get('caps')}"
        )
    print("\n  syscalls=成功执行  denied=内核能力表拒绝  failed=驱动拒绝")


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


def cmd_selfcheck(args) -> int:
    """MemoryStore 自检：scratch store 上写临时条目→验证五项→finally 删光。

    五项 = ①JSONL 完整性（每行可解析且必含 id/kind/text/ts）②重复 id
    ③全/半角括号 recall 健壮性 ④recall 空 query 不炸 ⑤临时条目清理。
    模式参考 jev-chat-jarvis KbSelfCheck.kt（MIT,
    github.com/jev-chat/jev-chat-jarvis）。

    默认在 tempfile scratch store 上跑，不碰用户 var/memory.jsonl；
    显式 --file <memory.jsonl> 则对该 store 跑（先打 stderr 警告：自检
    会短暂注入坏行验证检测能力，结尾走原子重写清理——检出的既有坏行
    随之被移除，建议先备份）。"""
    import tempfile

    from laos.memory import MemoryStore

    if args.file == str(DEFAULT_AUDIT):  # 未显式指定 --file → scratch store
        with tempfile.TemporaryDirectory() as td:
            failures = MemoryStore(Path(td) / "memory.jsonl").self_check()
    else:
        print(f"warning: selfcheck 结尾将原子重写并移除既有坏行，建议先备份 {args.file}",
              file=sys.stderr)
        failures = MemoryStore(Path(args.file)).self_check()
    if failures:
        print(f"memory 自检失败 {len(failures)} 项:")
        for f in failures:
            print(f"  ! {f}")
        if any("自检前文件已有完整性问题" in f for f in failures):
            print("  注意: 检出的坏行已被本次运行移除（结尾原子重写）")
        return 1
    print("memory 自检通过（①JSONL 完整性 ②重复 id ③全/半角括号 ④空 query ⑤临时条目清理）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="laosctl —— Linux AgentOS 控制面")
    ap.add_argument("command", choices=["audit", "trace", "denied", "top", "ps", "prof",
                                        "budget", "spans", "selfcheck"])
    ap.add_argument("--file", type=str, default=str(DEFAULT_AUDIT))
    ap.add_argument("--pid", type=int)
    ap.add_argument("--event", type=str)
    args = ap.parse_args()

    if args.command == "selfcheck":
        return cmd_selfcheck(args)  # 自检不读审计日志，走 scratch memory store
    records = load(Path(args.file))
    {"audit": cmd_audit, "trace": cmd_trace, "denied": cmd_denied,
     "top": cmd_top, "ps": cmd_ps, "prof": cmd_prof,
     "budget": cmd_budget, "spans": cmd_spans}[args.command](records, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
