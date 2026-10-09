#!/usr/bin/env python3
"""journal —— 听觉日志管线 CLI（第 3 段：批量转写 → 记忆 → 即焚）。

    python bin/journal.py [--journal-dir DIR] [--keep-hours H] [--dry-run]

流程：扫描 var/ear/journal/rec-*.wav → 逐段转写（ear.transcribe 双通道）
→ mem.remember(kind="journal", tags=[情感]) → rec.gc（默认 6h 即焚）→
→ 每段声景特征（laos.soundscape.describe，即焚前提取）按小时聚合为
  kind="soundscape" 记忆（spectral=True 默认开；--diary 收尾生成当日日记）
打印时间线与情感统计。

零依赖：转写函数可注入（测试）；默认用 drv_ear.transcribe（驱动进程内）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))


def run_pipeline(journal_dir: Path, memory, *, transcribe=None,
                 gc_keep_hours: float | None = None,
                 spectral: bool = True) -> dict:
    """转写目录内所有分段并入记忆库。返回 {"ok": [...], "errors": [...],
    "soundscape_hours": [...]}。

    语义：转写成功的段落 mem.remember(kind="journal", tags=[emotion])；
    失败段记录错误继续（不中断批次）；gc_keep_hours 非 None 时按
    mtime 清理（0 = 立即即焚——"转写成功为前提"的默认策略由调用方控制）。
    spectral=True 时每段在即焚前提取声景特征（describe），按 (日期,小时)
    聚合，循环后逐小时 mem.remember(kind="soundscape", tags=[日期,
    "soundscape"])——特征先于 GC，音频焚毁不影响记忆。
    """
    if transcribe is None:
        import drv_ear
        transcribe = drv_ear.transcribe

    import time as _time

    from laos.soundscape import aggregate, describe, render as sc_render

    ok, errors = [], []
    _sc_feats: dict[tuple[str, str], list[dict]] = {}  # (date, hour) -> feats
    _sc_counts: dict[tuple[str, str], int] = {}
    for wav in sorted(Path(journal_dir).glob("rec-*.wav")):
        try:
            raw = transcribe(str(wav))
            item = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as exc:
            errors.append({"wav": wav.name, "error": str(exc)[:120]})
            continue
        emotion = (item.get("emotions") or [""])[0] or "NEUTRAL"
        hour_min = datetime.fromtimestamp(wav.stat().st_mtime).strftime("%H:%M")
        memory.remember(kind="journal",
                        text=f"[{hour_min}] {item.get('text', '')}",
                        tags=[emotion])
        if spectral:
            try:  # 特征失败不拖垮转写批次（坏音频已被上面 try 拦，此处防御性）
                mtime = wav.stat().st_mtime
                lt = _time.localtime(mtime)
                key = (_time.strftime("%Y-%m-%d", lt),
                       _time.strftime("%H", lt))
                _sc_feats.setdefault(key, []).append(
                    describe(wav.read_bytes()))
                _sc_counts[key] = _sc_counts.get(key, 0) + 1
            except Exception:
                pass
        ok.append({"wav": wav.name, "text": item.get("text", ""),
                   "emotions": item.get("emotions", [])})

    soundscape_hours: list[str] = []
    for (date, hour) in sorted(_sc_feats):
        text = sc_render(aggregate(_sc_feats[(date, hour)]), hour,
                         _sc_counts[(date, hour)])
        memory.remember(kind="soundscape", text=text,
                        tags=[date, "soundscape"], origin="journal")
        soundscape_hours.append(hour)

    if gc_keep_hours is not None:
        cutoff_age = gc_keep_hours
        import time
        for wav in Path(journal_dir).glob("rec-*.wav"):
            if wav.stat().st_mtime < time.time() - cutoff_age * 3600:
                wav.unlink(missing_ok=True)

    return {"ok": ok, "errors": errors,
            "soundscape_hours": soundscape_hours}


def main() -> int:
    ap = argparse.ArgumentParser(description="听觉日志管线：转写 → 记忆 → 即焚")
    ap.add_argument("--journal-dir", default=str(REPO / "var" / "ear" / "journal"))
    ap.add_argument("--memory", default=str(REPO / "var" / "memory.jsonl"))
    ap.add_argument("--keep-hours", type=float, default=None,
                    help="转写后原音频保留时长（小时）；0=立即即焚；默认读 LAOS_JOURNAL_KEEP_H")
    ap.add_argument("--dry-run", action="store_true", help="只转写打印，不写记忆不删音频")
    ap.add_argument("--diary", action="store_true",
                    help="管线跑完后生成当天日记（bin/diary.py build_diary）")
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

    if args.diary:
        from diary import DEFAULT_AUDIT, _load_audit, build_diary
        today = time.strftime("%Y-%m-%d")
        build_diary(today, _load_audit(Path(DEFAULT_AUDIT)), memory)
        print(f"[journal] 已生成当日日记（diary/{today}.md）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
