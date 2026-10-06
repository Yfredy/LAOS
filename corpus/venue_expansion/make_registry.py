"""corpus/venue_expansion/make_registry.py — venue 注册表加载与校验工具。

load_registry(path) -> list[dict]：读取 venues.csv 并强制校验——
列 schema、venue 去重（casefold）、source 枚举、已有语料 venue 仅允许
incremental 年份。任何违规抛 ValueError，返回干净的 list[dict]。

后续抓取任务按每行 source 列分派：
  anthology          -> Task 2（用 anthology_prefix + years）
  crossref_journal   -> Task 3（用 crossref_issn + years）
  crossref_container -> Task 4（用 crossref_container + years）
  deferred           -> 暂缓抓取（notes 说明缺口原因）

零第三方依赖（仅 stdlib）。
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

COLUMNS = [
    "venue", "ccf", "dblp_stream", "crossref_issn", "crossref_container",
    "anthology_prefix", "years", "source", "notes",
]
SOURCES = {"anthology", "crossref_journal", "crossref_container", "deferred"}

# 已有语料的 venue（小写）：注册表里只允许增量年份（注明 incremental）
HAVE = {"icassp", "interspeech", "taslp", "asru", "slt", "aaai", "iclr"}


def load_registry(path) -> list:
    """读 venues.csv -> list[dict]；校验 schema/去重/source/HAVE 增量。"""
    p = Path(path)
    with p.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        header = reader.fieldnames or []
    missing = [c for c in COLUMNS if c not in header]
    if missing:
        raise ValueError(f"{p}: missing columns {missing}")
    if not rows:
        raise ValueError(f"{p}: registry is empty")
    seen = set()
    for r in rows:
        key = (r["venue"] or "").strip().casefold()
        if not key:
            raise ValueError(f"{p}: row with empty venue: {r}")
        if key in seen:
            raise ValueError(f"{p}: duplicate venue (casefold): {key}")
        seen.add(key)
        if r["source"] not in SOURCES:
            raise ValueError(f"{p}: bad source {r['source']!r} for {key}")
        if key in HAVE and "incremental" not in (r["years"] + r["notes"]).casefold():
            raise ValueError(
                f"{p}: existing-corpus venue {key} must be incremental-only")
    return rows


def dispatch_counts(rows) -> dict:
    """按 source 列统计分派行数（给抓取任务做容量预估）。"""
    return dict(Counter(r["source"] for r in rows))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else Path(__file__).resolve().parent / "venues.csv"
    rows = load_registry(path)
    print(f"{path}: {len(rows)} venues")
    for k, v in sorted(dispatch_counts(rows).items()):
        print(f"  {k:18s} {v}")
    for r in rows:
        if r["source"] == "deferred":
            print(f"  deferred: {r['venue']} — {r['notes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
