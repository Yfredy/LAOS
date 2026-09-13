#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""ICASSP 逐年枚举（Crossref query.bibliographic + offset + DOI 前缀判据）。

实测约束（2026-09-14），实现不得偏离：
  * filter=container-title 含逗号 -> HTTP 400，不可用
  * ICASSP proceedings 在 Crossref 无 ISSN，ISSN 路线不可用
  * cursor + query 组合失效（命中率 0），必须用 offset
  * 单 query 有效深度约 1000-2000 条，故必须多 query 分片
"""
import urllib.request, urllib.parse, json, re, ssl, time, sys, os, io

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "laos-research/1.0 (mailto:laos-survey@example.com)"}
MAILTO = "laos-survey@example.com"

DOI_PAT = r"10\.1109/icassp\d+\.{year}\."
FRONT_MATTER_PAT = re.compile(
    r"(?i)\b(committees?|toc|table of contents|welcome|reviewers?|"
    r"front cover|back cover|title page|author indexx?|author index|"
    r"organizing committee|technical program committee|sponsors?|"
    r"preface|keynote|tutorial|plenary|banquet|registration|"
    r"copyright|blank page|cover page)\b"
)
BASE_QUERY = "ICASSP {year} IEEE International Conference on Acoustics Speech and Signal Processing"
# 12 个分片 query，与 Interspeech 侧既有主题桶对齐，便于跨会对比
TOPIC_QUERIES = [
    "speech enhancement", "speech recognition", "speech emotion recognition",
    "speaker verification", "speaker diarization", "audio tagging",
    "sound event detection", "neural audio codec", "keyword spotting",
    "voice activity detection", "speech synthesis", "speech language model",
    "audio language model", "voice conversion", "speech separation",
    "self-supervised speech", "model compression quantization",
    "on-device edge inference", "microphone array beamforming",
    "acoustic echo cancellation",
]


def build_url(year, query, offset, rows=200):
    q = urllib.parse.quote(query if query else BASE_QUERY.format(year=year))
    if query:
        q = urllib.parse.quote(
            "ICASSP %d %s" % (year, query))
    return ("https://api.crossref.org/works?query.bibliographic=" + q +
            "&filter=type:proceedings-article,from-pub-date:%d-01-01,until-pub-date:%d-12-31"
            "&rows=%d&offset=%d&select=DOI,title,author&mailto=%s"
            % (year, year, rows, offset, MAILTO))


def is_target_doi(doi, year):
    return bool(re.search(DOI_PAT.format(year=year), doi, re.I))


def is_front_matter(title):
    return bool(FRONT_MATTER_PAT.search(title or ""))


def fetch(url, tries=3, wait=8):
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=50, context=CTX) as r:
                return r.read()
        except Exception as e:
            sys.stderr.write("  retry%d %s\n" % (t, str(e)[:70]))
            if t < tries - 1:
                time.sleep(wait * (t + 1))
    return None


def crawl_year(year, queries=None, max_offset=3000, step=200, out_dir=None, dry=False):
    queries = [None] + list(queries or TOPIC_QUERIES)
    seen, front = {}, 0
    per_query = {}   # query -> 该分片去重后贡献的唯一论文数
    for qi, q in enumerate(queries):
        consecutive_empty = 0
        before = len(seen)
        for off in range(0, max_offset, step):
            raw = fetch(build_url(year, q, off, step))
            if raw is None:
                break
            try:
                items = json.loads(raw.decode("utf-8"))["message"].get("items") or []
            except Exception:
                break
            hits = [i for i in items if is_target_doi(i.get("DOI", ""), year)]
            if not hits:
                consecutive_empty += 1
                if consecutive_empty >= 2:   # 连续两页零命中 -> 该 query 到底
                    break
                continue
            consecutive_empty = 0
            for it in hits:
                doi = it.get("DOI", "")
                title = (it.get("title") or [""])[0].strip()
                if is_front_matter(title):
                    front += 1
                    continue
                if doi not in seen:
                    seen[doi] = {
                        "doi": doi, "title": title, "year": year,
                        "authors": ", ".join(
                            ("%s %s" % (a.get("given", ""), a.get("family", ""))).strip()
                            for a in (it.get("author") or [])[:8]),
                        "query": q or "__base__", "source": "crossref",
                    }
            sys.stdout.write("  y%d q%-28s off=%-5d 页内%3d 累计%5d\n"
                             % (year, str(q)[:28], off, len(hits), len(seen)))
            sys.stdout.flush()
            time.sleep(1.2)          # Crossref 礼貌间隔
            if dry:
                break
        time.sleep(1.5)
        per_query[q or "__base__"] = len(seen) - before
    out = {"year": year, "unique": len(seen), "front_matter_dropped": front,
           "per_query": per_query,
           "papers": sorted(seen.values(), key=lambda x: x["doi"])}
    if out_dir and not dry:
        p = os.path.join(out_dir, "icassp%d_papers.json" % year)
        io.open(p, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
        print("  -> %s (%d 条)" % (p, len(seen)))
    return out


if __name__ == "__main__":
    years = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [2024]
    dry = "--dry" in sys.argv
    od = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus"
    for y in years:
        r = crawl_year(y, max_offset=600 if dry else 3000, out_dir=od, dry=dry)
        print("== ICASSP %d: unique=%d front_matter=%d ==" % (y, r["unique"], r["front_matter_dropped"]))
        if dry:
            print("-- per-query 去重贡献分布 --")
            tot = 0
            for q, n in r["per_query"].items():
                tot += n
                print("   %-32s +%d" % (q, n))
            print("   合计(各分片贡献之和)=%d  去重后 unique=%d" % (tot, r["unique"]))
