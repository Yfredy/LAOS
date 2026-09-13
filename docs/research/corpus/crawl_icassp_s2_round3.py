#!/usr/bin/env python3
"""S2 ICASSP 遍历 round-3：剩余 8 切片，abstract 字段，40 分钟预算。"""
import json, time, subprocess, urllib.parse, io, os, datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
QUERIES = ["speaker diarization", "keyword spotting", "text to speech",
           "sound event detection", "self-supervised speech",
           "streaming speech recognition", "speech language model",
           "paralinguistic"]
FIELDS = "title,year,venue,citationCount,externalIds,abstract"
DEADLINE = time.time() + 40 * 60
done = {}
attempts = 0

def s2(q, offset=0):
    url = ("https://api.semanticscholar.org/graph/v1/paper/search?query="
           + urllib.parse.quote(q)
           + f"&venue=ICASSP&year=2022-2026&fields={FIELDS}&limit=100&offset={offset}")
    r = subprocess.run(["curl", "-s", "--max-time", "45", url], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip().startswith("{"):
        try:
            d = json.loads(r.stdout)
            if "data" in d:
                return d
        except json.JSONDecodeError:
            pass
    return None

while time.time() < DEADLINE and len(done) < len(QUERIES):
    for q in QUERIES:
        if q in done or time.time() > DEADLINE:
            continue
        attempts += 1
        d = s2(q)
        if d and d.get("data") is not None:
            papers = d["data"]
            total = d.get("total", len(papers))
            if total > 100:
                time.sleep(75)
                d2 = s2(q, offset=100)
                if d2 and d2.get("data"):
                    papers += d2["data"]
            done[q] = {"total": total, "papers": papers}
            print(f"[OK] {q}: total={total} fetched={len(papers)}  ({datetime.datetime.now():%H:%M:%S})", flush=True)
        else:
            print(f"[..] {q} 429/miss  ({datetime.datetime.now():%H:%M:%S})", flush=True)
        time.sleep(75)

io.open("icassp_s2_round3.json", "w", encoding="utf-8").write(
    json.dumps(done, ensure_ascii=False))
print(f"DONE: {len(done)}/{len(QUERIES)} queries, {attempts} attempts", flush=True)
