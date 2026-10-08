#!/usr/bin/env python3
"""mood_report —— 听觉日志情感周报（纯 stdlib 字符图）。

    python bin/mood_report.py [--days 7] [--memory var/memory.jsonl]

消费 journal 记忆（tags 里的情感标签）——按日聚合 → 字符堆叠条形图 +
趋势一句话。"你感觉最近状态不好"之前，数据先说话（vocal biomarkers 思路）。
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

EMOTION_GLYPHS = {"HAPPY": "█", "SAD": "▓", "ANGRY": "▒", "FEARFUL": "░",
                  "NEUTRAL": "·", "DISGUSTED": ":", "SURPRISED": "▚"}
EMOTIONS = list(EMOTION_GLYPHS)


def build_report(memory, days: int = 7) -> dict:
    """聚合最近 N 天的 journal 记忆情感标签。

    返回 {"days": {"MM-DD": {emotion: count}}, "by_emotion": {...},
    "total": int, "summary": str}。"""
    cutoff = datetime.now() - timedelta(days=days)
    per_day: dict[str, Counter] = {}
    total_by_emotion: Counter = Counter()
    total = 0
    for rec in memory._records:  # 直读全量（时间过滤不能走 recall 的相关度排序）
        if rec.get("kind") != "journal":
            continue
        ts = datetime.fromtimestamp(rec.get("ts", 0))
        if ts < cutoff:
            continue
        day = ts.strftime("%m-%d")
        emotion = next((t for t in rec.get("tags", []) if t in EMOTIONS), "NEUTRAL")
        per_day.setdefault(day, Counter())[emotion] += 1
        total_by_emotion[emotion] += 1
        total += 1

    days_sorted = {d: dict(per_day[d]) for d in sorted(per_day)}
    if total == 0:
        summary = "暂无听觉日志数据——先跑 rec.start + bin/journal.py"
    else:
        top = total_by_emotion.most_common(1)[0]
        summary = f"近 {days} 天共 {total} 段语音记录，主导情绪 {top[0]}（{top[1]} 段）"
    return {"days": days_sorted, "by_emotion": dict(total_by_emotion),
            "total": total, "summary": summary}


def render(report: dict, days: int) -> str:
    lines = [f"== 情绪周报（近 {days} 天）==", report["summary"], ""]
    if not report["days"]:
        return "\n".join(lines)
    max_n = max(sum(d.values()) for d in report["days"].values())
    for day, counts in report["days"].items():
        bar = "".join(EMOTION_GLYPHS[e] * n for e, n in
                      sorted(counts.items(), key=lambda kv: -kv[1]))
        lines.append(f"  {day} │{bar:<{max_n}}│ {sum(counts.values())} 段")
    lines.append("")
    lines.append("  图例 " + "  ".join(f"{g}={e}" for e, g in EMOTION_GLYPHS.items()))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="听觉日志情感周报")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--memory", default=str(REPO / "var" / "memory.jsonl"))
    args = ap.parse_args()

    from laos.memory import MemoryStore
    memory = MemoryStore(Path(args.memory))
    print(render(build_report(memory, args.days), args.days))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
