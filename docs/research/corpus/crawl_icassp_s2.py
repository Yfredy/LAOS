#!/usr/bin/env python3
"""S2 ICASSP 遍历：轮询所有查询直到成功或超时（本地代理/S2 池均不稳，用耐心换覆盖）。"""
import json, time, subprocess, urllib.parse, io, os, datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
QUERIES = ["speech enhancement", "speaker diarization", "keyword spotting",
           "neural codec", "text to speech", "sound event detection",
           "self-supervised speech", "streaming speech recognition",
           "speech language model", "paralinguistic",
           "emotion recognition", "voice activity detection"]
FIELDS = "title,year,venue,citationCount,externalIds,abstract"
DEADLINE = time.time() + 35 * 60
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
            return None  # 429 包装或其他错误
        except json.JSONDecodeError:
            return None
    return None

while time.time() < DEADLINE and len(done) < len(QUERIES):
    progressed = False
    for q in QUERIES:
        if q in done or time.time() > DEADLINE:
            continue
        attempts += 1
        d = s2(q)
        if d and d.get("data") is not None:
            papers = d["data"]
            total = d.get("total", len(papers))
            # 再翻一页
            if total > 100:
                time.sleep(75)
                d2 = s2(q, offset=100)
                if d2 and d2.get("data"):
                    papers += d2["data"]
            done[q] = {"total": total, "papers": papers}
            print(f"[OK] {q}: total={total} fetched={len(papers)}  ({datetime.datetime.now():%H:%M:%S})", flush=True)
            progressed = True
        else:
            print(f"[..] {q} 429/miss  ({datetime.datetime.now():%H:%M:%S})", flush=True)
        time.sleep(75)
    if not progressed:
        time.sleep(60)

io.open("icassp_s2_round2.json", "w", encoding="utf-8").write(
    json.dumps(done, ensure_ascii=False))
print(f"DONE: {len(done)}/{len(QUERIES)} queries, {attempts} attempts", flush=True)
