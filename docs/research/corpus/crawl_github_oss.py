#!/usr/bin/env python3
"""GitHub 音频×AI×Agent 高星开源项目全量搜索（stdlib + curl 子进程）。

用法：
  python crawl_github_oss.py search   # 10 切片搜索 → oss_corpus.json
  python crawl_github_oss.py readmes  # 前 30 深读 → oss_top30_readmes/ + oss_top30_summary.json
"""
import json, time, subprocess, urllib.parse, io, os, sys, base64

os.chdir(os.path.dirname(os.path.abspath(__file__)))
HDRS = ["-H", "Accept: application/vnd.github+json",
        "-H", "User-Agent: laos-survey/1.0"]

def gh_json(url):
    waits = [5, 15, 30, 65, 90]
    for t, w in enumerate(waits + [65] * 3):
        r = subprocess.run(["curl", "-s", "--max-time", "60"] + HDRS + [url],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip().startswith("{"):
            try:
                d = json.loads(r.stdout)
            except json.JSONDecodeError:
                d = None
            if d is not None:
                msg = str(d.get("message", ""))
                if "Not Found" in msg:
                    return {"notfound": True}          # 404 不重试：仓库已删/改名
                if "API rate limit" in msg or "Too many requests" in msg or "abuse" in msg.lower():
                    time.sleep(w); continue
                return d
        time.sleep(w)
    return None

SLICES = [
    ("audio",            "topic:audio stars:>300"),
    ("speech",           "topic:speech stars:>200"),
    ("asr",              "topic:speech-recognition stars:>100"),
    ("tts",              "topic:tts stars:>100"),
    ("diarization",      "topic:speaker-diarization stars:>20"),
    ("enhancement",      "topic:speech-enhancement stars:>50"),
    ("voice-assistant",  "topic:voice-assistant stars:>100"),
    ("audio-processing", "topic:audio-processing stars:>300"),
    ("audio-llm",        "audio LLM in:name,description,readme stars:>300"),
    ("voice-agent",      "voice agent in:name,description,readme stars:>100"),
]

def phase_search():
    per_slice, repo = {}, {}
    for name, q in SLICES:
        hits, page = 0, 1
        while page <= 10:  # 1000 上限
            url = ("https://api.github.com/search/repositories?q=" + urllib.parse.quote(q)
                   + "&sort=stars&order=desc&per_page=100&page=" + str(page))
            d = gh_json(url)
            if not d or "items" not in d:
                print(f"[{name}] page{page}: FAILED, stop slice", flush=True)
                break
            items = d["items"]
            hits += len(items)
            for it in items:
                fn = it["full_name"]
                if fn not in repo:
                    repo[fn] = {"full_name": fn, "stars": it["stargazers_count"],
                                "topics": it.get("topics", []),
                                "description": (it.get("description") or "")[:200],
                                "language": it.get("language"),
                                "url": it["html_url"],
                                "pushed_at": it.get("pushed_at", ""),
                                "slices": []}
                repo[fn]["slices"].append(name)
            print(f"[{name}] page{page}: +{len(items)} (total seen {hits})", flush=True)
            if len(items) < 100:
                break
            page += 1
            time.sleep(7)
        per_slice[name] = hits
        time.sleep(7)
    repos = sorted(repo.values(), key=lambda r: -r["stars"])
    io.open("oss_corpus.json", "w", encoding="utf-8").write(
        json.dumps({"per_slice": per_slice, "unique": len(repos), "repos": repos},
                   ensure_ascii=False))
    big = sum(1 for r in repos if r["stars"] > 10000)
    mid = sum(1 for r in repos if 1000 < r["stars"] <= 10000)
    small = sum(1 for r in repos if 100 < r["stars"] <= 1000)
    print(f"DONE search: unique={len(repos)} slices={per_slice}")
    print(f"stars: >10k={big} 1k-10k={mid} 100-1k={small}")

def laos_relevance(r):
    text = (r["full_name"] + " " + r["description"] + " " + " ".join(r["topics"])).lower()
    keys = ["speech", "voice", "audio", "tts", "asr", "whisper", "diariz",
            "emotion", "vad", "agent", "llm", "codec", "wake", "enhance"]
    return sum(1 for k in keys if k in text)

def phase_readmes(n=30, skip_existing=True):
    repos = json.load(io.open("oss_corpus.json", encoding="utf-8"))["repos"]
    os.makedirs("oss_top30_readmes", exist_ok=True)
    scored = sorted(repos, key=lambda r: (-laos_relevance(r), -r["stars"]))
    picked = scored[:n]
    summaries = []
    for i, r in enumerate(picked):
        fn = r["full_name"]
        safe = fn.replace("/", "__")
        out = f"oss_top30_readmes/{safe}.md"
        if skip_existing and os.path.exists(out):
            print(f"[{i+1}/{n}] {fn} cached", flush=True)
        else:
            d = gh_json(f"https://api.github.com/repos/{fn}/readme")
            if d and "content" in d:
                body = base64.b64decode(d["content"]).decode("utf-8", errors="replace")
                io.open(out, "w", encoding="utf-8").write(body[:120000])
                print(f"[{i+1}/{n}] {fn} ★{r['stars']} saved", flush=True)
            elif d and d.get("notfound"):
                io.open(out, "w", encoding="utf-8").write(
                    f"# {fn}\n\n> README 不可取（仓库已删除/改名，搜索索引滞后）。stars={r['stars']}")
                print(f"[{i+1}/{n}] {fn} NOTFOUND placeholder", flush=True)
            else:
                print(f"[{i+1}/{n}] {fn} README fetch failed", flush=True)
        if i < len(picked) - 1:
            time.sleep(65)  # core API 60 req/h
    io.open("oss_top30_summary.json", "w", encoding="utf-8").write(
        json.dumps([{"full_name": r["full_name"], "stars": r["stars"],
                     "description": r["description"], "language": r["language"],
                     "url": r["url"], "slices": r["slices"],
                     "laos_relevance": laos_relevance(r)} for r in picked],
                   ensure_ascii=False, indent=1))
    print("DONE readmes")

if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "search"
    {"search": phase_search, "readmes": phase_readmes}[phase]()
