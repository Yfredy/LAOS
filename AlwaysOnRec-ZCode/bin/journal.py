#!/usr/bin/env python3
"""journal —— 听觉日志管线 CLI（第 3 段：批量转写 → 记忆 → 即焚）。

    python bin/journal.py [--journal-dir DIR] [--keep-hours H] [--dry-run]

流程：扫描 var/ear/journal/rec-*.wav → 逐段转写（ear.transcribe 双通道）
→ mem.remember(kind="journal", tags=[情感]) → rec.gc（默认 6h 即焚）→
打印时间线与情感统计。

零依赖：转写函数可注入（测试）；默认用 drv_ear.transcribe（驱动进程内）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))


def _title_of(text: str, limit: int = 20) -> str:
    """取转写文本首句前 limit 字作标题（Apple Siri Recap 式：标题+原文）。

    无句界（。！？；）或文本更短时回退为全文前 limit 字；空文本返回空串。
    """
    body = text.strip()
    if not body:
        return ""
    first_sentence = re.split(r"[。！？；\n]", body)[0]
    return (first_sentence or body)[:limit]


def run_pipeline(journal_dir: Path, memory, *, transcribe=None,
                 gc_keep_hours: float | None = None,
                 archive=None) -> dict:
    """转写目录内所有分段并入记忆库。返回 {"ok": [...], "errors": [...]}。

    语义：转写成功的段落 mem.remember(kind="journal", tags=[emotion])；
    失败段记录错误继续（不中断批次）；gc_keep_hours 非 None 时按
    mtime 清理（0 = 立即即焚——"转写成功为前提"的默认策略由调用方控制）。
    """
    if transcribe is None:
        import drv_ear
        transcribe = drv_ear.transcribe

    ok, errors = [], []
    for wav in sorted(Path(journal_dir).glob("rec-*.wav")):
        try:
            raw = transcribe(str(wav))
            item = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as exc:
            errors.append({"wav": wav.name, "error": str(exc)[:120]})
            continue
        emotion = (item.get("emotions") or [""])[0] or "NEUTRAL"
        hour_min = datetime.fromtimestamp(wav.stat().st_mtime).strftime("%H:%M")
        body = item.get("text", "")
        title = _title_of(body)
        # 三段 schema：# 标题 首行，正文行带时间戳前缀（Apple Siri Recap 式）
        text = f"# {title}\n[{hour_min}] {body}" if title else f"[{hour_min}] {body}"
        memory.remember(kind="journal", text=text, tags=[emotion])
        if archive is not None:
            # 留存档（默认关）：即焚前留压缩副本，磁盘占用降一个数量级
            archive.store(wav.name, wav.read_bytes())
        ok.append({"wav": wav.name, "title": title,
                   "text": body, "emotions": item.get("emotions", [])})

    if gc_keep_hours is not None:
        cutoff_age = gc_keep_hours
        import time
        for wav in Path(journal_dir).glob("rec-*.wav"):
            if wav.stat().st_mtime < time.time() - cutoff_age * 3600:
                wav.unlink(missing_ok=True)

    return {"ok": ok, "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser(description="听觉日志管线：转写 → 记忆 → 即焚")
    ap.add_argument("--journal-dir", default=str(REPO / "var" / "ear" / "journal"))
    ap.add_argument("--memory", default=str(REPO / "var" / "memory.jsonl"))
    ap.add_argument("--keep-hours", type=float, default=None,
                    help="转写后原音频保留时长（小时）；0=立即即焚；默认读 LAOS_JOURNAL_KEEP_H")
    ap.add_argument("--dry-run", action="store_true", help="只转写打印，不写记忆不删音频")
    args = ap.parse_args()

    import os
    keep = args.keep_hours if args.keep_hours is not None else float(
        os.environ.get("LAOS_JOURNAL_KEEP_H", "6"))

    from laos.memory import MemoryStore
    memory = MemoryStore(Path(args.memory))

    result = run_pipeline(Path(args.journal_dir), memory,
                          gc_keep_hours=None if args.dry_run else keep)

    print("== 听觉日志时间线 ==")
    for item in result["ok"]:
        print(f"  {item['wav']}  {item['emotions']}  {item['text'][:60]}")
    if result["errors"]:
        print("== 失败段 ==")
        for e in result["errors"]:
            print(f"  {e['wav']}: {e['error']}")
    print(f"\n共 {len(result['ok'])} 段入记忆，{len(result['errors'])} 段失败"
          f"{'' if args.dry_run else f'，原音频保留 {keep}h'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
