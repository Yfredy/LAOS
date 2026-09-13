#!/usr/bin/env python3
"""Task 1：OpenAlex 全量枚举 ICASSP 2022-2026（配额 UTC 午夜重置后运行）。

用法：python crawl_icassp_openalex.py
产物：icassp_oa_<year>.json ×5 → icassp_full_corpus.json（与 interspeech_corpus.json 同构）
"""
import json, time, subprocess, urllib.parse, io, os, re, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
UA = "laos-survey/1.0 (mailto:laos-survey@example.com)"
TOPICS = {
    "emotion":   r"emotion|affect|sentiment|paralingu|arousal|valence|mood",
    "speaker":   r"speaker",
    "diariz":    r"diariz|meeting|conversation",
    "enhance":   r"enhanc|denois|noise|dereverb|echo|gain|loudness|packet loss|bandwidth|separation|separat",
    "codec":     r"codec|tokeniz|discrete (speech|acoustic|audio)|rvq|residual vector|quantiz",
    "kws_vad":   r"keyword spotting|wake[- ]?word|voice activity|keyword|\bVAD\b",
    "tts":       r"text-to-speech|\bTTS\b|speech synthesis|vocoder|voice conversion|speech generation|sing",
    "event":     r"sound event|acoustic scene|audio tagging|scream|cough|cry\b",
    "ssl":       r"self-supervised|wav2vec|hubert|wavlm|pre-train",
    "edge":      r"edge|on-device|lightweight|distill|compress|quantiz|low-complexity|real-time|streaming|low-latency|efficien",
    "llm":       r"\bllm\b|large language|language model|foundation model|instruction|full-duplex|dialogue system",
    "health":    r"stutter|dysarth|cough|depress|alzheimer|cognitive|parkinson|sleep|fatigue|autism|dementia|hear",
}

def curl_json(url):
    for w in (5, 15, 30, 60, 90):
        r = subprocess.run(["curl", "-s", "--max-time", "90", "-A", UA, url],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip().startswith("{"):
            try:
                d = json.loads(r.stdout)
                if "error" in d and "Rate limit" in d.get("error", ""):
                    print("quota still limited:", d.get("retryAfter"), "s"); return None
                if "results" in d:
                    return d
            except json.JSONDecodeError:
                pass
        time.sleep(w)
    return None

# Step 1: 找 ICASSP 的 source id（取 works_count 最大的命中）
d = curl_json("https://api.openalex.org/sources?search=ICASSP&per-page=10")
if not d:
    sys.exit("OpenAlex unavailable — run after UTC midnight reset")
srcs = [(s["id"].rsplit("/", 1)[-1], s["display_name"], s.get("works_count", 0))
        for s in d["results"] if "icassp" in s["display_name"].lower()]
print("candidate sources:", srcs, flush=True)
if not srcs:
    sys.exit("no ICASSP source found")

all_items = []
for sid, name, _ in srcs:
    cursor = "*"
    guard = 0
    while guard < 25:
        url = (f"https://api.openalex.org/works?filter=primary_location.source.id:{sid}"
               f"&per-page=200&cursor={urllib.parse.quote(cursor)}"
               f"&select=title,authorships,doi,publication_year,cited_by_count,primary_location")
        d = curl_json(url)
        if not d:
            print(f"{name}: page fetch failed, partial save", flush=True)
            break
        for w in d.get("results", []):
            title = (w.get("title") or "").strip()
            if not title:
                continue
            src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name", "")
            if "icassp" not in src.lower():     # 客户端精确过滤
                continue
            all_items.append({
                "year": w.get("publication_year"),
                "title": title,
                "authors": ", ".join(a["author"]["display_name"]
                                     for a in w.get("authorships", [])[:6]),
                "doi": w.get("doi") or "",
                "cited_by": w.get("cited_by_count", 0),
                "venue": src})
        nxt = (d.get("meta") or {}).get("next_cursor")
        guard += 1
        print(f"{name}: page{guard} cum={len(all_items)} of {d.get('meta',{}).get('count')}", flush=True)
        if not nxt:
            break
        cursor = nxt
        time.sleep(1.2)

by_year = {}
for it in all_items:
    y = it["year"]
    if y and 2022 <= y <= 2026:
        by_year.setdefault(y, []).append(it)
for y, items in sorted(by_year.items()):
    io.open(f"icassp_oa_{y}.json", "w", encoding="utf-8").write(json.dumps(items, ensure_ascii=False))
    print(f"saved icassp_oa_{y}.json: {len(items)}", flush=True)

# 打主题标签 + 同构 corpus
papers, topic_year = [], {}
for y, items in sorted(by_year.items()):
    for it in items:
        t = it["title"].lower()
        hits = [k for k, pat in TOPICS.items() if re.search(pat, t)]
        for k in hits:
            topic_year.setdefault(k, {}).setdefault(str(y), 0)
            topic_year[k][str(y)] += 1
        papers.append({"year": y, "title": it["title"], "authors": it["authors"],
                       "doi": it["doi"], "url": it["doi"] or "", "cited_by": it["cited_by"],
                       "topics": hits})
summary = {
    "source": "OpenAlex primary_location.source（ICASSP 卷）cursor 翻页全量",
    "crawled_at": datetime.datetime.now().isoformat(),
    "totals": {str(y): len(by_year.get(y, [])) for y in range(2022, 2027)},
    "grand_total": len(papers),
    "topic_matrix": {k: {str(y): topic_year[k].get(str(y), 0) for y in range(2022, 2027)}
                     for k in TOPICS},
}
io.open("icassp_full_corpus.json", "w", encoding="utf-8").write(
    json.dumps({"summary": summary, "papers": papers}, ensure_ascii=False))
print("DONE icassp_full_corpus.json:", summary["totals"], flush=True)
