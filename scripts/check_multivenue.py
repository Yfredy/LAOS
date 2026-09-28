#!/usr/bin/env python3
"""check_multivenue —— 多顶会语料校验器（对齐 scripts/check_paper_corpus.py 的角色）。

检查项：
  1. 必填字段：title/year/venue/citationCount/doi 至少 title+year 非空
  2. venue 归属：每条 paper 的 venue 归一化后必须属于其文件声明的 venue 键
     的别名集（防串文件）
  3. 与 papers_unified.jsonl 的交叉验证：title+year 重叠计数（同一论文双库
     出现 = 双源互证成功）
  4. 去重后总数 / venue 分布 / 年份分布（2021-2026 越界即报错）

用法：python scripts/check_multivenue.py [--no-unified]
"""
from __future__ import annotations

import glob
import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from crawl_multivenue import _venue_aliases, container_matches  # noqa: E402

CORPUS_GLOB = str(REPO / "docs" / "research" / "corpus" / "multivenue_*.json")
UNIFIED = REPO / "docs" / "research" / "corpus" / "papers_unified.jsonl"
_YEAR_PREFIX_RE = re.compile(r"^(19|20)\d{2}\s+")
_PROC_PREFIX_RE = re.compile(r"^(in\s+)?proceedings\s+of(\s+the)?\s+",
                             re.IGNORECASE)


def load_venue_file(path: str) -> dict:
    d = json.load(io.open(path, encoding="utf-8"))
    if "venue" not in d or "queries" not in d:
        raise SystemExit(f"{path}: 缺 venue/queries 字段")
    return d


def papers_of(doc: dict) -> list[dict]:
    out = []
    for q in doc["queries"].values():
        out.extend(q.get("papers", []))
    return out


def strip_variants(name: str) -> str:
    prev = None
    while prev != name:
        prev = name
        name = _YEAR_PREFIX_RE.sub("", name)
        name = _PROC_PREFIX_RE.sub("", name)
    name = re.sub(r"\s*\([^)]{2,12}\)\s*$", "", name)
    return name


def main(check_unified: bool = True) -> int:
    violations: list[str] = []
    venue_counts: dict[str, int] = {}
    year_counts: dict[int, int] = {}
    seen: set[tuple[str, int]] = set()
    dup_count = 0
    total = 0

    for path in sorted(glob.glob(CORPUS_GLOB)):
        if "strings" in path or "observed" in path:
            continue
        doc = load_venue_file(path)
        key = doc["venue"]
        aliases = _venue_aliases(key)
        for p in papers_of(doc):
            total += 1
            title = (p.get("title") or "").strip()
            year = p.get("year")
            if not title or not isinstance(year, int):
                violations.append(f"{key}: 空标题或非法年份 {p!r:.80}")
                continue
            if not 2021 <= year <= 2026:
                violations.append(f"{key}: 年份越界 {year} ({title[:40]})")
            vn = p.get("venue", "")
            if not container_matches(vn, key, aliases):
                violations.append(f"{key}: venue 串不属别名集 {vn!r:.60}")
            k = (title.casefold(), year)
            if k in seen:
                dup_count += 1
            seen.add(k)
            venue_counts[key] = venue_counts.get(key, 0) + 1
            year_counts[year] = year_counts.get(year, 0) + 1

    cross = 0
    if check_unified and UNIFIED.exists():
        unified_keys = set()
        for line in io.open(UNIFIED, encoding="utf-8"):
            u = json.loads(line)
            t = (u.get("title") or "").strip().casefold()
            if t:
                unified_keys.add((t, u.get("year")))
        cross = len(seen & unified_keys)

    print(f"总条目 {total}（含跨主题重复 {dup_count}）")
    print(f"venue 分布: {json.dumps(venue_counts, ensure_ascii=False)}")
    print(f"年份分布: {json.dumps(dict(sorted(year_counts.items())), ensure_ascii=False)}")
    if check_unified:
        print(f"与 papers_unified.jsonl 交叉验证重叠: {cross}")
    if violations:
        print(f"\n违规 {len(violations)} 条（前 10 条）：")
        for v in violations[:10]:
            print(" -", v)
        return 1
    print("\nPASS：0 违规")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check_unified="--no-unified" not in sys.argv))
