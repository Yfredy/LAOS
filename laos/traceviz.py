"""traceviz —— 审计日志 → mermaid 时序图："架构、调用链一张图看懂"。

方法论源自 Karpathy 2026-10-02 帖（x.com/karpathy/status/2105819303471976479）
第二阶梯：向模型要图表而不是文字——图表"a lot easier to process, parse,
and understand"。laos 的对应物不是让模型画图，而是把**内核自己的权威
调用链记录**（audit.jsonl 的 event:"syscall" 行）转成 mermaid
sequenceDiagram：

    participant K as kernel
    participant P1 as ear(1)
    P1->>K: mic.open
    K-->>P1: ok
    K--xP1: EPERM

治理姿势：这是审计的**只读派生视图**——不美化、不改写、不回写审计；
审计永远是权威源（派生物与原始的双层结构，与 ste 的 check-only 同一
原则族）。失败调用用 --x 箭头显式标出，直奔"哪里被治理面拦下"。

CLI：python -m laos.traceviz <audit.jsonl> [--tail N]（默认 40 条最近
syscall）；laosctl traceviz --file ... 同入口。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_TAIL = 40

_BAD_CHARS = str.maketrans({":": " ", ";": " ", "\n": " ", "\r": " "})


def _safe(name: object, fallback: str) -> str:
    """mermaid 参与者/消息里会破坏语法的字符一律换成空格。"""
    s = str(name if name not in (None, "") else fallback).translate(_BAD_CHARS).strip()
    return s or fallback


def to_mermaid(records: list[dict], tail: int = DEFAULT_TAIL) -> str:
    """把审计记录转成 mermaid sequenceDiagram 文本。

    只认 event=="syscall" 且带 pid/tool 的行；tail 取最近 N 条（None/
    0/负数 = 不截断）。agent 名取记录的 agent 字段，缺省 "?"。
    """
    calls = [r for r in records
             if r.get("event") == "syscall"
             and isinstance(r.get("pid"), int) and r.get("tool")]
    if tail and tail > 0:
        calls = calls[-tail:]

    lines = ["sequenceDiagram"]
    if not calls:
        return "\n".join(lines)

    # 参与者按首次出现顺序：内核在最前，agent 其后
    order: list[int] = []
    names: dict[int, str] = {}
    for r in calls:
        pid = r["pid"]
        if pid not in names:
            order.append(pid)
            names[pid] = _safe(r.get("agent"), "?")
    lines.append("    participant K as kernel")
    for pid in order:
        lines.append(f"    participant P{pid} as {names[pid]}({pid})")

    for r in calls:
        pid = r["pid"]
        tool = _safe(r.get("tool"), "?")
        lines.append(f"    P{pid}->>K: {tool}")
        if r.get("ok"):
            lines.append(f"    K-->>P{pid}: ok")
        else:
            err = _safe(r.get("result") or r.get("error"), "fail")
            lines.append(f"    K--xP{pid}: {err}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="laos.traceviz",
        description="audit.jsonl → mermaid sequenceDiagram（只读派生视图，审计权威）")
    ap.add_argument("file", help="审计 JSONL 路径")
    ap.add_argument("--tail", type=int, default=DEFAULT_TAIL,
                    help=f"最近 N 条 syscall（默认 {DEFAULT_TAIL}；0=不截断）")
    args = ap.parse_args(argv)

    records: list[dict] = []
    with Path(args.file).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # 崩溃半行跳过（与 MemoryStore._load 同语义）
    print(to_mermaid(records, tail=args.tail))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
