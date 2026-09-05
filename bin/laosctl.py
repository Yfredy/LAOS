#!/usr/bin/env python3
"""laosctl —— AgentOS 的控制面 / 事后审计工具（类似 ps / lsmod / strace）。

laosd 的内核状态在内存里，laosctl 通过持久化的审计日志做回放与统计：

    python bin/laosctl.py audit                 # 全部审计事件
    python bin/laosctl.py trace --pid 1001      # 回放某个 Agent 的 syscall
    python bin/laosctl.py denied                # 所有被拒绝的调用
    python bin/laosctl.py top                   # 按 syscall 聚合耗时
    python bin/laosctl.py prof                  # eBPF 采集的真实 syscall 分布
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = REPO / "var" / "audit.jsonl"


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


def main() -> int:
    ap = argparse.ArgumentParser(description="laosctl —— Linux AgentOS 控制面")
    ap.add_argument("command", choices=["audit", "trace", "denied", "top", "ps", "prof",
                                        "budget"])
    ap.add_argument("--file", type=str, default=str(DEFAULT_AUDIT))
    ap.add_argument("--pid", type=int)
    ap.add_argument("--event", type=str)
    args = ap.parse_args()

    records = load(Path(args.file))
    {"audit": cmd_audit, "trace": cmd_trace, "denied": cmd_denied,
     "top": cmd_top, "ps": cmd_ps, "prof": cmd_prof,
     "budget": cmd_budget}[args.command](records, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
