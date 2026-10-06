#!/usr/bin/env python
"""corpus/venue_expansion/filter_laos_relevant.py — laos 相关性过滤（Task 5）。

对 venue_expansion 全部抓取产物（*.jsonl，行 schema
{title,year,venue,authors,url,doi,abstract}，abstract 可为 None）按 laos
三主线正则词表过滤：标题+摘要（若有）拼串 casefold 后匹配，命中即标
laos_topic（多命中取 TOPICS 迭代序首个）。联合卷跨文件重复（同 doi 或同
title casefold）在输出中只保留首现，去重计数单独统计。

用法：
  python filter_laos_relevant.py            # 全过滤 -> laos_relevant.jsonl
  python filter_laos_relevant.py --stats    # 另打 venue×topic 交叉计数表
                                            # 与总命中/去重计数

写行沿用 fetch_anthology.write_jsonl 纪律：U+2028/U+2029/U+0085 转义成
\\u2028 形（JSON 值不变，但读方 splitlines 不再被内嵌行分隔符劈行）。
venue×topic 交叉表的 venue 键取源文件 stem（anthology_acl 等），比条目里
逐年漂移的 container-title 更稳定，直接供 Task 6 交叉分析用。
零第三方依赖（argparse/json/re/sys/collections/pathlib，纯 stdlib）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# laos 相关三主线（Task 5 brief 照抄；dict 迭代序 = 多命中时的取标签优先级）
TOPICS = {
    "agent-os":   r"(agent).{0,40}(operating system|sandbox|syscall|kernel|governan|resource|quota|isolation)|(llm|language model).{0,30}(agent)",
    "audio-speech": r"(wake[- ]?word|keyword spotting|vad|voice activity|always[- ]?on|speech recognition|asr|tts|diariz|far[- ]?field|echo cancell)",
    "spatial-privacy": r"(binaural|spatial audio|beamform|acoustic camera|speech privacy|audio watermark)",
}

_TOPIC_RES = [(t, re.compile(p)) for t, p in TOPICS.items()]


def is_relevant(entry: dict) -> tuple[bool, str | None]:
    """标题+摘要（若有）拼串 casefold 后按 TOPICS 匹配。

    返回 (True, topic)——多命中取 TOPICS 迭代序首个——或 (False, None)。
    abstract 为 None/空时只匹配标题；全空文本直接判否。
    """
    text = " ".join(part for part in (entry.get("title") or "",
                                      entry.get("abstract") or "") if part)
    text = text.casefold()
    if not text:
        return (False, None)
    for topic, rx in _TOPIC_RES:
        if rx.search(text):
            return (True, topic)
    return (False, None)


def _dedup_keys(entry: dict) -> tuple[str, str]:
    """(doi casefold, title casefold)；缺省字段返回空串（不参与去重）。"""
    doi = (entry.get("doi") or "").strip().casefold()
    title = (entry.get("title") or "").strip().casefold()
    return doi, title


def _dumps_line(row: dict) -> str:
    s = json.dumps(row, ensure_ascii=False)
    return (s.replace("\u2028", "\\u2028")
             .replace("\u2029", "\\u2029")
             .replace("\x85", "\\u0085"))


def run_filter(in_files, out_path) -> dict:
    """逐文件逐行过滤写 out_path，返回统计 dict。

    in_files 有序（文件序+行序 = 输出行保序）。命中行写出 = 原行全部字段 +
    "laos_topic"；跨文件同 doi（casefold）或同 title（casefold）的命中只保留
    首现，重复计入 dup_hits。0 行占位文件天然贡献 0 行、不进 cross 表。
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total_in = hits = dup_hits = written = 0
    per_topic: Counter = Counter()
    cross: defaultdict = defaultdict(Counter)  # 文件 stem -> topic -> n
    seen_doi: set = set()
    seen_title: set = set()
    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        for path in map(Path, in_files):
            venue = path.stem
            with path.open("r", encoding="utf-8") as rf:
                for line in rf:
                    line = line.strip()
                    if not line:
                        continue
                    total_in += 1
                    entry = json.loads(line)
                    ok, topic = is_relevant(entry)
                    if not ok:
                        continue
                    hits += 1
                    doi, title = _dedup_keys(entry)
                    if (doi and doi in seen_doi) or (title and title in seen_title):
                        dup_hits += 1
                        continue
                    if doi:
                        seen_doi.add(doi)
                    if title:
                        seen_title.add(title)
                    fh.write(_dumps_line({**entry, "laos_topic": topic}) + "\n")
                    written += 1
                    per_topic[topic] += 1
                    cross[venue][topic] += 1
    return {"total_in": total_in, "hits": hits, "dup_hits": dup_hits,
            "written": written, "per_topic": dict(per_topic),
            "cross": {v: dict(c) for v, c in cross.items()}}


def print_stats(stats: dict) -> None:
    """venue×topic 交叉计数表（去重后写出行为准）+ 总命中/去重计数。"""
    topics = list(TOPICS)
    cross = stats["cross"]
    wcol = max([len("venue")] + [len(v) for v in cross])
    print("venue × topic 交叉计数（去重后写出行为准）")
    print("  ".join(["venue".ljust(wcol)]
                    + [t.rjust(16) for t in topics] + ["total".rjust(7)]))
    for v in sorted(cross, key=lambda v: (-sum(cross[v].values()), v)):
        cells, rowtot = [v.ljust(wcol)], 0
        for t in topics:
            n = cross[v].get(t, 0)
            rowtot += n
            cells.append(str(n).rjust(16) if n else ".".rjust(16))
        cells.append(str(rowtot).rjust(7))
        print("  ".join(cells))
    tot = ["TOTAL".ljust(wcol)] + [str(stats["per_topic"].get(t, 0)).rjust(16)
                                   for t in topics] + [str(stats["written"]).rjust(7)]
    print("  ".join(tot))
    print(f"输入行 {stats['total_in']} | 命中 {stats['hits']} | "
          f"跨文件去重剔除 {stats['dup_hits']} | 写出 {stats['written']}")


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(
        description="laos 相关性过滤：venue_expansion 全部 *.jsonl -> "
                    "laos_relevant.jsonl（原行 + laos_topic，跨文件去重）")
    ap.add_argument("--ve-dir", default=str(here), help="输入目录（默认脚本所在）")
    ap.add_argument("--out", default=str(here / "laos_relevant.jsonl"),
                    help="输出 jsonl 路径")
    ap.add_argument("--stats", action="store_true",
                    help="另打 venue×topic 交叉计数表与总命中/去重计数")
    args = ap.parse_args(argv)
    ve_dir, out = Path(args.ve_dir), Path(args.out)
    in_files = sorted(p for p in ve_dir.glob("*.jsonl") if p.name != out.name)
    if not in_files:
        print(f"no input *.jsonl under {ve_dir}", file=sys.stderr)
        return 1
    stats = run_filter(in_files, out)
    print(f"{len(in_files)} 个输入文件 -> {out}（写出 {stats['written']} 行，"
          f"命中 {stats['hits']}，跨文件去重剔除 {stats['dup_hits']}）")
    if args.stats:
        print_stats(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
