#!/usr/bin/env python3
"""ICASSP 2022-2026 全量枚举（Crossref，container-title 精确过滤，curl 子进程 + 指数退避）。"""
import json, time, subprocess, urllib.parse, io, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
MAILTO = "laos-survey@example.com"
CT_PREFIX = {
    2022: "ICASSP 2022 - 2022 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)",
    2023: "ICASSP 2023 - 2023 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)",
    2024: "ICASSP 2024 - 2024 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)",
    2025: "ICASSP 2025 - 2025 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)",
    2026: "ICASSP 2026 - 2026 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)",
}

def curl_json(url, tries=5):
    waits = [5, 15, 30, 60, 90]
    for t in range(tries):
        r = subprocess.run(["curl", "-s", "--max-time", "90", url],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip().startswith("{"):
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                pass
        if t < tries - 1:
            time.sleep(waits[t])
    return None

for year, ct in CT_PREFIX.items():
    cursor, items, guard = "*", [], 0
    while True:
        url = ("https://api.crossref.org/works?filter=container-title:" + urllib.parse.quote(ct)
               + f"&rows=1000&cursor={urllib.parse.quote(cursor)}"
               + "&select=title,author,DOI&mailto=" + MAILTO)
        d = curl_json(url)
        if d is None or "message" not in d:
            print(f"{year}: fetch FAILED at page {guard}, saving partial", flush=True)
            break
        msg = d["message"]
        batch = msg.get("items", [])
        for it in batch:
            authors = ", ".join(
                f"{a.get('given','')} {a.get('family','')}".strip()
                for a in (it.get("author") or [])[:6])
            items.append({"title": (it.get("title") or [""])[0].strip(),
                          "authors": authors,
                          "doi": it.get("DOI", ""), "year": year,
                          "url": f"https://doi.org/{it.get('DOI','')}"})
        nxt = msg.get("next-cursor")
        guard += 1
        print(f"{year}: page{guard} +{len(batch)} cum={len(items)} of {msg.get('total-results')}", flush=True)
        if not nxt or not batch or guard >= 8:
            break
        cursor = nxt
        time.sleep(2)
    io.open(f"icassp{year}_papers.json", "w", encoding="utf-8").write(
        json.dumps(items, ensure_ascii=False))
    print(f"== ICASSP {year}: saved {len(items)} ==", flush=True)
    time.sleep(3)
print("DONE", flush=True)
