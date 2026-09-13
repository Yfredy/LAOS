#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""合并 ICASSP / Interspeech 语料为统一 schema 的 JSONL。

统一字段（10 个，两个会议一致）：
  venue, year, doi_or_id, title, authors, url, abstract, topics[], has_abstract, source
"""
import collections
import io
import json
import os
import re

BASE = os.path.join(r"C:\Users\yaoyue\CodeBuddy\Claw\laos", "docs", "research", "corpus")
OUT = os.path.join(BASE, "papers_unified.jsonl")

# 与 Interspeech 既有 12 主题桶保持一致，便于跨会对比
TOPIC_RULES = {
    "emotion":  r"(?i)\b(emotion|affect|sentiment|mood)\b",
    "speaker":  r"(?i)\b(speaker|voiceprint|verification)\b",
    "diariz":   r"(?i)\b(diariz|who.?spoke|meeting transcription)\b",
    "enhance":  r"(?i)\b(enhance|denois|dereverberat|separation|noise reduction|speech improvement)\b",
    "codec":    r"(?i)\b(codec|vector quanti|discrete (?:speech|audio) (?:token|representation)|rvq)\b",
    "kws_vad":  r"(?i)\b(keyword spotting|wake.?word|voice activity|\bvad\b|trigger)\b",
    "tts":      r"(?i)\b(text.?to.?speech|\btts\b|vocoder|voice conversion|speech synthesis)\b",
    "event":    r"(?i)\b(sound event|audio event|audio tagging|acoustic scene|audio caption)\b",
    "ssl":      r"(?i)\b(self.?supervis|wav2vec|hubert|wavlm|pre.?train(?:ed|ing) model|representation learning)\b",
    "edge":     r"(?i)\b(on.?device|edge|streaming|low.?complexity|lightweight|quantiz|pruning|distill|real.?time|rtf)\b",
    "llm":      r"(?i)\b(\bllm\b|large language model|instruction|foundation model|generative|gpt|agent)\b",
    "health":   r"(?i)\b(patholog|dysarthr|clinical|disorder|alzheimer|parkinson|stutter|health|depression)\b",
}
COMPILED = {k: re.compile(v) for k, v in TOPIC_RULES.items()}


def classify(title, abstract):
    text = (title or "") + " " + (abstract or "")
    return [k for k, rx in COMPILED.items() if rx.search(text)]


def main():
    out = []
    for y in range(2022, 2027):
        p = os.path.join(BASE, "icassp%d_papers.json" % y)
        if not os.path.exists(p):
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        for it in d["papers"]:
            out.append({
                "venue": "ICASSP", "year": y, "doi_or_id": it["doi"],
                "title": it["title"], "authors": it.get("authors", ""),
                "url": "https://doi.org/" + it["doi"], "abstract": "",
                "topics": classify(it["title"], ""), "has_abstract": False,
                "source": "crossref",
            })
    ip = os.path.join(BASE, "interspeech_corpus.json")
    if os.path.exists(ip):
        d = json.load(io.open(ip, encoding="utf-8"))
        for it in d["papers"]:
            out.append({
                "venue": "Interspeech", "year": it["year"],
                "doi_or_id": it.get("id") or it.get("url", ""),
                "title": it["title"], "authors": it.get("authors", ""),
                "url": it.get("url", ""), "abstract": it.get("abstract", ""),
                "topics": sorted(set(classify(it["title"], it.get("abstract", ""))) |
                                 set(it.get("topics") or [])),
                "has_abstract": bool(it.get("abstract")), "source": "isca",
            })
    with io.open(OUT, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("写出 %d 条 -> %s" % (len(out), OUT))
    print("按 venue:", dict(collections.Counter(r["venue"] for r in out)))
    print("按 year :", dict(sorted(collections.Counter(r["year"] for r in out).items())))
    venue_topic = collections.Counter()
    for r in out:
        for t in r["topics"]:
            venue_topic[(t, r["venue"])] += 1
    tops = sorted({k[0] for k in venue_topic})
    print()
    print("  %-10s %8s %12s" % ("主题", "ICASSP", "Interspeech"))
    for t in tops:
        print("  %-10s %8d %12d" % (t, venue_topic[(t, "ICASSP")],
                                    venue_topic[(t, "Interspeech")]))


if __name__ == "__main__":
    main()
