#!/usr/bin/env python3
"""crawl_openalex_nlp —— 用 OpenAlex 补 Crossref 结构性缺失的会议（NLP 五会 + CHiME）。

背景（2026-09-29 波 A 实测）：ACL/EMNLP/NAACL/COLING/CoNLL 的论文在 ACL
Anthology 发布、不向 Crossref 注册 DOI → Crossref 路线 kept=0；CHiME 的
会议录 container-title 与别名集不匹配。OpenAlex 对两者都有收录，且把
**每个年份的会议录建模为独立 source**（如 "Proceedings of the 2021
Conference on Empirical Methods in Natural Language Processing"）。

路线（每 venue 两步）：
  1. sources?search=<会议名>  → 候选 source 列表，按 works_count 与
     display_name 年份启发式筛选 2021-2025 各年会议录的 source id
  2. works?filter=primary_location.source.id:ID1|ID2|...&search=<主题>
     &from_publication_date:2021-01-01 → 客户端再按 source 名模糊复核

产出与 crawl_multivenue 同形状的 docs/research/corpus/multivenue_<key>.json
（幂等：已存在即跳过）。限速 1.5s（OpenAlex polite）。
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from crawl_multivenue import (  # noqa: E402
    CORPUS_DIR, VENUE_NAMES, _venue_aliases, _norm_venue, _now,
)

MAILTO = "laos-survey@example.com"
GAP_S = 1.5
YEAR_RE = re.compile(r"\b(20\d{2})\b")
VENUE_KEYS = ["ACL", "EMNLP", "NAACL", "COLING", "CoNLL", "CHiME"]
# 与波 A NLP 分配一致的主题
TOPICS = [
    "LLM agent tool use", "agent memory", "audio language model",
    "multimodal agent", "on-device inference",
    "emotion recognition", "paralinguistic", "neural codec",
]
# CHiME 是语音挑战赛：用 12 主题全集
TOPICS_CHIME = [
    "speech enhancement", "speaker diarization", "keyword spotting",
    "neural codec", "text to speech", "sound event detection",
    "self-supervised speech", "streaming speech recognition",
    "speech language model", "paralinguistic",
    "emotion recognition", "voice activity detection",
]
FRAGMAENT_NORM = {k: _norm_venue(v) for k, v in {
    "ACL": "Annual Meeting of the Association for Computational Linguistics",
    "EMNLP": "Conference on Empirical Methods in Natural Language Processing",
    "NAACL": "North American Chapter of the Association for Computational Linguistics",
    "COLING": "International Conference on Computational Linguistics",
    "CoNLL": "Conference on Computational Natural Language Learning",
    "CHiME": "CHiME",
}.items()}


SOURCE_SEARCH = {
    "ACL": "Annual Meeting of the Association for Computational Linguistics",
    "EMNLP": "Conference on Empirical Methods in Natural Language Processing",
    "NAACL": "North American Chapter of the Association for Computational Linguistics",
    "COLING": "International Conference on Computational Linguistics",
    "CoNLL": "Conference on Computational Natural Language Learning",
    "CHiME": "CHiME",
}


def _curl_json(url: str) -> dict | None:
    r = subprocess.run(["curl", "-s", "--max-time", "45", url], capture_output=True)
    if r.returncode != 0:
        return None
    txt = r.stdout.decode("utf-8", "replace").strip()
    if not txt.startswith("{"):
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return None


FRAGMENT = {
    "ACL": "annual meeting of the association for computational linguistics",
    "EMNLP": "empirical methods in natural language processing",
    "NAACL": "north american chapter",
    "COLING": "international conference on computational linguistics",
    "CoNLL": "computational natural language learning",
    "CHiME": "chime",
}
EXCLUDE = {
    "ACL": ["north american", "european", "findings", "student", "workshop",
            "tutorial", "demonstration"],
}


def pick_sources(results: list[dict], venue_key: str) -> list[dict]:
    """从 sources?search 结果中筛出该会议的逐年会议录 source。

    会议录名形如 "Proceedings of the 61st Annual Meeting of ..."——
    **不带年份**是常态（2021 Conference 式才带），故不能靠年份启发式；
    改用归一化名含 FRAGMENT[venue]（大小写/标点不敏感）+ works_count
    落在单年会议录合理区间 [60, 12000]（CHiME 放宽到 10），并按
    EXCLUDE 排除邻居会议/Findings/Workshop 卷。取 works 最多的前 6 个。
    """
    lo = 10 if venue_key in ("CHiME", "CoNLL") else 60
    frag = FRAGMAENT_NORM[venue_key]
    excl = EXCLUDE.get(venue_key, [])
    out = []
    for s in results:
        name = s.get("display_name") or ""
        wc = s.get("works_count") or 0
        n = _norm_venue(name)
        if frag not in n:
            continue
        if any(e in n for e in excl):
            continue
        if not (lo <= wc <= 12000):
            continue
        m = YEAR_RE.search(name)
        year = int(m.group(1)) if m else 0
        out.append({"id": s["id"].rsplit("/", 1)[-1], "name": name,
                    "year": year, "works": wc})
    out.sort(key=lambda s: -s["works"])
    return out[:6]


def openalex_works(source_ids: list[str], topic: str) -> str:
    ids = "|".join(source_ids)
    return (
        "https://api.openalex.org/works"
        f"?filter=primary_location.source.id:{ids}"
        ",from_publication_date:2021-01-01"
        f"&search={quote(topic)}"
        "&per-page=100"
        "&select=title,publication_year,primary_location,cited_by_count,doi"
        f"&mailto={MAILTO}"
    )


_PROC_PREFIX_RE = re.compile(
    r"^(in\s+)?proceedings\s+of(\s+the)?\s+", re.IGNORECASE)
_YEAR_PREFIX_RE = re.compile(r"^(19|20)\d{2}\s+")


def _strip_proc_prefix(name: str) -> str:
    """反复剥 "Proceedings of the " 与前导年份，直到剥不动。"""
    prev = None
    while prev != name:
        prev = name
        name = _YEAR_PREFIX_RE.sub("", name)
        name = _PROC_PREFIX_RE.sub("", name)
    return name


def works_to_papers(results: list[dict], venue_key: str) -> list[dict]:
    frag = FRAGMAENT_NORM[venue_key]
    excl = EXCLUDE.get(venue_key, [])
    out = []
    for w in results:
        title = (w.get("title") or "").strip()
        src = ((w.get("primary_location") or {}).get("source") or {})
        name = (src.get("display_name") or "").strip()
        year = w.get("publication_year")
        if not title or not name or not isinstance(year, int):
            continue
        # 剥 "Proceedings of the ..."/年份前缀后按 FRAGMENT 子串匹配
        # （别名等值匹配对 "Conference of the North American Chapter ..."
        # 这类变体太脆；子串与 pick_sources 同源，口径一致）
        n = _norm_venue(_strip_proc_prefix(name))
        if frag not in n or any(e in n for e in excl):
            continue
        out.append({"title": title, "year": year, "venue": name,
                    "citationCount": w.get("cited_by_count", 0),
                    "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                    "authors": ""})
    return out


def main() -> int:
    for key in VENUE_KEYS:
        out_path = CORPUS_DIR / f"multivenue_{key.lower()}.json"
        if out_path.exists():
            print(f"[SKIP] {key}: 已存在", flush=True)
            continue
        time.sleep(GAP_S)
        d = _curl_json(
            "https://api.openalex.org/sources?search="
            + quote(SOURCE_SEARCH[key]) + "&per-page=50&mailto=" + MAILTO)
        if not d or "results" not in d:
            print(f"[FAIL] {key}: sources 搜索失败", flush=True)
            continue
        srcs = pick_sources(d["results"], key)
        print(f"[SRC] {key}: {len(srcs)} 个年度会议录 "
              f"({', '.join(str(s['year']) for s in srcs) or '无'})", flush=True)
        if not srcs:
            continue
        topics = TOPICS_CHIME if key == "CHiME" else TOPICS
        ids = [s["id"] for s in srcs]
        queries: dict[str, dict] = {}
        for topic in topics:
            time.sleep(GAP_S)
            d2 = _curl_json(openalex_works(ids, topic))
            if not d2 or "results" not in d2:
                queries[topic] = {"error": "openalex miss"}
                print(f"[FAIL] {key} | {topic}", flush=True)
                continue
            papers = works_to_papers(d2["results"], key)
            queries[topic] = {"total": d2["meta"]["count"], "kept": len(papers),
                              "papers": papers}
            print(f"[OK] {key} | {topic}: total={d2['meta']['count']} "
                  f"kept={len(papers)}  ({_now()})", flush=True)
        if not any("papers" in q for q in queries.values()):
            print(f"[SKIP-WRITE] {key}: 无成功查询", flush=True)
            continue
        cat = "speech_adj" if key == "CHiME" else "nlp"
        doc = {"venue": key, "category": cat, "backend": "openalex",
               "canonical_venue_string": SOURCE_SEARCH[key], "wave": "A补",
               "generated_at": _now(), "sources": srcs, "topics": topics,
               "queries": queries}
        io.open(out_path, "w", encoding="utf-8").write(
            json.dumps(doc, ensure_ascii=False, indent=1))
        print(f"[WRITE] {out_path.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
