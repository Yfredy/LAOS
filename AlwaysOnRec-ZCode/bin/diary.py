#!/usr/bin/env python3
"""diary —— laos 每日日记：把审计流与记忆库固化成一篇人可读的 md。

相当于传统 OS 的 logwatch / daily report，但读的是内核审计 + 个人记忆库：

    1. 读 var/audit.jsonl 当天记录：syscall 总数 / 成功 / 被拒 / 工具 TOP5
    2. mem.recall(当天高频词) 召回相关记忆 + mem.stats 全库概览
    3. 摘要段：OPENAI_API_KEY 存在且 laos.brain 可导入 → LLM 生成一段话；
       否则（或 LLM 失败）抽取式模板——核心逻辑零依赖，LLM 只是锦上添花
    4. 写 var/diary/<date>.md，四章：今天做了什么 / 新记住的事 /
       被拒绝与原因 / 明天可以试试
    5. MemoryStore.remember(kind="diary", text=摘要, tags=[date])
       ——日记本身就是一条记忆，第二天生成时会按日期标签召回自己

用法：
    python bin/diary.py                  # 生成今天的日记
    python bin/diary.py --date 2026-09-10 --json
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.memory import MemoryStore  # noqa: E402

DEFAULT_AUDIT = REPO / "var" / "audit.jsonl"
DEFAULT_MEMORY = REPO / "var" / "memory.jsonl"

TITLE = "# laos 日记 {date}"
# 章节标题（顺序即 md 章节顺序）；单测钉住这些关键字
SECTION_TITLES = (
    "一、今天做了什么",
    "二、新记住的事",
    "三、被拒绝与原因",
    "四、明天可以试试",
    "五、今天听到的",
)
TOP_TOOLS_N = 5


# -- 审计聚合 --------------------------------------------------------------
def _day_of(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _records_of_day(records: list[dict], date: str) -> list[dict]:
    """取属于 date 当天的记录；无时间戳的记录视为当天（宽松处理）。"""
    out = []
    for r in records:
        t = r.get("t")
        out.append(r) if t is None or _day_of(float(t)) == date else None
    return out


def _aggregate(records: list[dict]) -> dict:
    syscalls = [r for r in records if r.get("event") == "syscall"]
    ok = sum(1 for r in syscalls if r.get("ok"))
    denied = len(syscalls) - ok
    tools = Counter(str(r.get("tool", "?")) for r in syscalls)
    denied_rows = [
        {"pid": r.get("pid"), "tool": r.get("tool", "?"),
         "reason": str(r.get("result", ""))[:120]}
        for r in syscalls if not r.get("ok")
    ]
    return {
        "syscalls": len(syscalls),
        "ok": ok,
        "denied": denied,
        "top_tools": tools.most_common(TOP_TOOLS_N),
        "denied_rows": denied_rows,
    }


# -- 记忆侧 ----------------------------------------------------------------
def _query_of(agg: dict, date: str) -> str:
    """mem.recall 的查询词：当天高频工具 + 日期（日期即日记条目的标签）。"""
    return " ".join([date] + [tool for tool, _ in agg["top_tools"]])


def _recent_records(store: MemoryStore, k: int) -> list[dict]:
    """最近的 k 条记忆（时间倒序）。MemoryStore 无"最近"公开接口，读其文件。"""
    try:
        lines = store.path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    recs = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            recs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(recs) >= k:
            break
    return recs


# -- 摘要段 ----------------------------------------------------------------
def _template_summary(agg: dict, mem_stats: dict, date: str) -> str:
    if not agg["syscalls"]:
        body = "今天没有 syscall 记录，内核安静地待了一天。"
    else:
        top = "、".join(f"{tool}×{n}" for tool, n in agg["top_tools"]) or "无"
        body = (f"今天共执行 {agg['syscalls']} 次 syscall"
                f"（成功 {agg['ok']}、被拒 {agg['denied']}），"
                f"最常用的工具：{top}。")
    if mem_stats.get("total"):
        body += f" 记忆库现有 {mem_stats['total']} 条记忆。"
    return body


def _make_brain():
    """LLM 路径：OPENAI_API_KEY 已设置且 laos.brain 可导入才启用。"""
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        return None
    try:
        from laos.brain import OpenAIChatBrain
        return OpenAIChatBrain()
    except Exception:
        return None


#: OpenAIChatBrain.think 失败时不抛异常，而是返回以此为前缀的 Thought.text
#: （见 laos/brain.py）——日记侧据此识别"LLM 失败"并回落模板
LLM_FAIL_MARKER = "LLM 调用失败"


def _llm_summary(brain, date: str, agg: dict, mem_stats: dict) -> str:
    """用 LLM 把当天事实写成一段话；失败/空响应返回空串（调用方回落模板）。"""
    facts = _template_summary(agg, mem_stats, date)
    denied = "; ".join(
        f"{r['tool']}({r['reason'].split(':')[0]})" for r in agg["denied_rows"][:3])
    user = (
        f"请根据以下事实，用中文写一段不超过 100 字的第一人称日记摘要"
        f"（日期 {date}），不要分点、不要标题：\n{facts}\n"
        f"被拒调用：{denied or '无'}"
    )
    thought = brain.think(
        [{"role": "system",
          "content": "你是 laos（一个 Linux AgentOS）的日记作者，文风简洁诚实。"},
         {"role": "user", "content": user}],
        [])
    text = (getattr(thought, "text", "") or "").strip()
    if not text or text.startswith(LLM_FAIL_MARKER):
        return ""  # 401 / 超时 / 空响应：一律回落抽取式模板
    return text


# -- 主流程 ----------------------------------------------------------------
def build_diary(date: str, audit_records: list[dict], memory_store: MemoryStore,
                brain=None) -> dict:
    """聚合某天的审计 + 记忆 → 写 var/diary/<date>.md → 记住这篇日记。

    brain=None 表示自动：有 OPENAI_API_KEY 且可导入 OpenAIChatBrain 就走 LLM，
    否则模板；传入具体 brain 实例则强制用它（测试注入用）。LLM 任何异常
    都回落模板——日记生成永不因 LLM 失败而失败。
    返回 dict：四个章节标题 -> 章节文本，另有 date/path/summary/markdown/stats。
    """
    day_records = _records_of_day(audit_records, date)
    agg = _aggregate(day_records)
    mem_stats = memory_store.stats()
    query = _query_of(agg, date)
    hits = memory_store.recall(query, k=TOP_TOOLS_N)
    recent = [] if hits else _recent_records(memory_store, TOP_TOOLS_N)

    # 摘要：LLM 优先（brain 显式传入 / 自动构造），失败回落模板
    summary = None
    if brain is None:
        brain = _make_brain()
    if brain is not None:
        try:
            summary = _llm_summary(brain, date, agg, mem_stats)
        except Exception:
            summary = None
    if not summary:
        summary = _template_summary(agg, mem_stats, date)

    # ---- 四章 ------------------------------------------------------------
    if agg["syscalls"]:
        lines = [f"- syscall 共 {agg['syscalls']} 次："
                 f"成功 {agg['ok']}、被拒 {agg['denied']}"]
        lines += [f"  - {tool} ×{n}" for tool, n in agg["top_tools"]]
        did = "\n".join(lines)
    else:
        did = "今天没有 syscall 记录。"

    if hits:
        memories = "\n".join(
            f"- #{h['id']} [{h['kind']}] {h['text']} (score={h['score']:.2f})"
            for h in hits)
    elif recent:
        memories = "（无相关召回，取最近几条）\n" + "\n".join(
            f"- #{h['id']} [{h['kind']}] {h['text']}" for h in recent)
    else:
        memories = "（今天没有新记住的事）"

    if agg["denied_rows"]:
        denied_txt = "\n".join(
            f"- pid={r['pid']} `{r['tool']}` → {r['reason']}"
            for r in agg["denied_rows"])
    else:
        denied_txt = "（今天没有被拒绝的 syscall）"

    tips = []
    if agg["denied"]:
        tips.append("有 syscall 被拒：多半是能力表/任务边界在执法，"
                    "要么补授权（sys.delegate），要么承认越权。")
    if not hits and not recent:
        tips.append("记忆库还是空的：用 mem.remember 记一条偏好或事实。")
    tips.append("试试把今天的高频操作固化成脚本，或用 mem.recall 验证记忆召回。")
    tomorrow = "\n".join(f"- {t}" for t in tips)

    # ---- 第五章：今天听到的（听觉日志 journal 记忆 + 情感统计）------------
    day_start = datetime.strptime(date, "%Y-%m-%d").timestamp()
    day_end = day_start + 86400
    heard = [r for r in memory_store._records
             if r.get("kind") == "journal" and day_start <= r.get("ts", 0) < day_end]
    if heard:
        from collections import Counter
        emo = Counter(next((t for t in r.get("tags", [])
                            if t.isupper()), "NEUTRAL") for r in heard)
        emo_bar = "  ".join(f"{e}:{n}" for e, n in emo.most_common())
        lines = [f"- 共听到 {len(heard)} 段语音，情感分布：{emo_bar}"]
        for r in heard[:10]:
            parts = r["text"].splitlines()
            if parts and parts[0].startswith("# "):  # Apple 式标题行
                head = parts[0][2:].strip()
                tail = parts[1].strip() if len(parts) > 1 else ""
                lines.append(f"- {head}｜{tail[:64]}" if tail else f"- {head}")
            else:
                lines.append(f"- {r['text'][:80]}")
        heard_txt = "\n".join(lines)
    else:
        heard_txt = "（今天没有听觉日志——rec.start + bin/journal.py 可以补上）"

    sections = dict(zip(SECTION_TITLES,
                        (did, memories, denied_txt, tomorrow, heard_txt)))

    # ---- 写文件 + 记住日记 ------------------------------------------------
    diary_dir = memory_store.path.parent / "diary"
    diary_dir.mkdir(parents=True, exist_ok=True)
    path = diary_dir / f"{date}.md"
    markdown = "\n\n".join(
        [TITLE.format(date=date), summary]
        + [f"## {title}\n{sections[title]}" for title in SECTION_TITLES]
    ) + "\n"
    path.write_text(markdown, encoding="utf-8")
    remembered = memory_store.remember(kind="diary", text=summary, tags=[date])

    return {
        "date": date,
        "path": str(path),
        "summary": summary,
        **sections,
        "markdown": markdown,
        "stats": {"memory": mem_stats, "consolidated": remembered,
                  "syscalls": agg["syscalls"], "ok": agg["ok"],
                  "denied": agg["denied"], "top_tools": agg["top_tools"]},
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="laos 每日日记生成器")
    ap.add_argument("--date", default=time.strftime("%Y-%m-%d"),
                    help="日记日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    ap.add_argument("--audit", type=str, default=str(DEFAULT_AUDIT),
                    help="审计 JSONL 路径")
    ap.add_argument("--memory", type=str, default=str(DEFAULT_MEMORY),
                    help="记忆库 JSONL 路径")
    args = ap.parse_args()

    records: list[dict] = []
    audit_path = Path(args.audit)
    if audit_path.exists():
        with audit_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # 崩溃残迹跳过
    result = build_diary(args.date, records, MemoryStore(Path(args.memory)))

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["markdown"])
        print(f"[diary] 已写入 {result['path']}，"
              f"并作为记忆 #{result['stats']['consolidated']['id']} 收入记忆库",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
