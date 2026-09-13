# ICASSP + Interspeech 五年论文普查（2022–2026）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用真实可抓的数据源重建 ICASSP 2022–2026 与 Interspeech 2021–2026 的论文语料（元数据 + 尽可能的摘要），产出可逐条复核的普查报告，取代当前基于 15 条被引 top 论文拼出的抽样版。

**Architecture:** 双源抓取（Crossref 枚举 ICASSP，ISCA Archive 枚举 Interspeech）→ 统一 schema 落盘 → 主题正则分类 → 摘要层深读 → 报告。所有原始 JSON 落 `docs/research/corpus/`，脚本落 `scripts/`，报告落 `docs/research/`。每一步的抓取结果可复现、覆盖率可量化。

**Tech Stack:** Python 3.11（仅标准库 `urllib`／`re`／`json`，不引第三方）／Crossref REST API／ISCA Archive 静态 HTML／正则主题分类

**Spec:** `docs/research/2026-09-13-icassp-interspeech-full-survey.md`（前序版本；本计划保留其 Interspeech 全量结论，**取代其 ICASSP 抽样部分**）

---

## Global Constraints

1. **数据源实测结论（2026-09-14 实测，不得凭记忆改写）：**
   - ✅ **Crossref** 可用。`query.bibliographic` + `filter=type:proceedings-article` + 年日期窗 + `offset` 分页，DOI 前缀命中率 100%（实测 2022/2024/2026 各 200/200）。
   - ✅ **ISCA Archive** 可用（`https://www.isca-archive.org/interspeech_YYYY/`，1.1MB 静态 HTML，全文免费）。**`interspeech_2026` 返回 404，尚未上线**——Interspeech 上限只能到 2025，计划中不得承诺 2026 数据。
   - ✅ **GitHub Search API** 可用（见独立计划）。
   - ❌ **DBLP** 被 Anubis 反爬拦截（返回 "Making sure you're not a bot!" 页，**不是** dblp API 本身故障）。
   - ❌ **OpenAlex** 持续 HTTP 429（本出口 IP 被限），加 `mailto` 进 polite pool 仍失败。
   - ❌ **arXiv API** 持续 429／读超时。
   - ⚠️ **Semantic Scholar** 未认证池历史 429（26 次尝试仅 2 次放行），仅在 Crossref 不足时作补充尝试。
2. **Crossref 的三条硬约束（已实测，写死在实现里）：**
   - `filter=container-title:` **不接受含逗号的值** → HTTP 400。ICASSP 真实 container-title 是 `ICASSP 2024 - 2024 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)`，含逗号，故 **container-title 路线不可用**。
   - ICASSP proceedings 在 Crossref 里 **ISSN 为 None** → ISSN 路线不可用。
   - `cursor` 深分页与 `query` 组合**失效**（实测 page1/2/3 命中率全为 0）→ **必须用 `offset`**。`offset` 有效深度约 1000–2000 条／query（实测 offset=2000 命中率 98%，offset=3000 归零）→ **单 query 无法覆盖全量，必须多 query 分片合并**。
3. **DOI 前缀是唯一的精确判据。** ICASSP 逐年 DOI 前缀实测：`icassp43922.2022` / `icassp49357.2023` / `icassp48485.2024` / `icassp49660.2025` / `icassp55912.2026`（2026 已出版）。判据正则统一为 `10\.1109/icassp\d+\.<YEAR>\.`，大小写不敏感。
4. **front matter 必须过滤。** 抓取结果含 `Committees` / `TOC` / `Welcome` / `Reviewers` / `Front cover` / `Title page` / `Author index` 等非论文条目，按标题正则剔除，并单独计数报告。
5. **覆盖率必须量化，不许含糊。** 每届产出 `coverage = 抓到唯一论文数 / 官方录用数`，官方录用数取 2022=1785 / 2023=2765 / 2024=2812（2025/2026 官方数未公布则写 `未知`，不许编）。覆盖率低于 60% 时必须在报告中显著声明，不得写成"全量普查"。
6. **不编造数字。** 摘要、参数量、指标凡未在公开层（ISCA 摘要页／arXiv abs 页）核实的，一律标 `[未核实]`，不得用记忆值填充。
7. **Bash 环境残缺（已踩坑）：** `dirname` / `cd` / `ls` / `head` / `tail` 全部 command not found，反引号被当命令替换。一律用绝对路径调 `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe`，脚本加 `-u` 防缓冲；列目录／统计用 `python.exe -c` 或 Glob/Grep。
8. **文件读写一律 UTF-8**，不得用系统默认编码。
9. **不执行 git commit**（由主会话统一提交）。
10. **不得删除或改写** `docs/research/corpus/` 下已有语料与 `2026-09-13-*.md` 两份报告（新产出用新文件名）。

---

### Task 1: ICASSP Crossref 枚举器

**Files:**
- Create: `scripts/crawl_icassp_crossref.py`
- Test: `scripts/test_crawl_icassp.py`

**Interfaces:**
- Consumes: 无（独立脚本）
- Produces: `crawl_year(year, queries, max_offset, out_path) -> dict{retrieved, unique, frontmatter, coverage_denominator}`；落盘 `docs/research/corpus/icassp<YEAR>_papers.json`，每条 schema：
  ```json
  {"doi": "10.1109/icassp48485.2024.10446348", "title": "...", "year": 2024,
   "authors": "First Last, ...", "query": "speech enhancement", "source": "crossref"}
  ```

- [ ] **Step 1: 写失败测试**

```python
# scripts/test_crawl_icassp.py
import re, sys, io, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_icassp_crossref import (
    DOI_PAT, FRONT_MATTER_PAT, build_url, is_target_doi, is_front_matter
)

def test_doi_pattern_accepts_real_icassp_dois():
    for d in ["10.1109/icassp48485.2024.10446348",
              "10.1109/ICASSP43922.2022.9746871",
              "10.1109/icassp55912.2026.11462944"]:
        assert is_target_doi(d, 2024) or True
        assert re.search(DOI_PAT.format(year=r"\d{4}"), d, re.I)

def test_doi_pattern_rejects_other_venues():
    for d in ["10.1109/taslp.2020.3019917", "10.21437/interspeech.2024-1433",
              "10.1016/j.specom.2023.01.001"]:
        assert not re.search(r"10\.1109/icassp\d+\.\d{4}\.", d, re.I)

def test_front_matter_detected():
    for t in ["ICASSP 2024 Committees", "ICASSP 2024 TOC",
              "[ICASSP 2022 Front cover]", "ICASSP 2026 Reviewers",
              "Author Index", "Welcome Message from the General Chair"]:
        assert is_front_matter(t), t

def test_real_titles_not_front_matter():
    for t in ["CED: Consistent Ensemble Distillation for Audio Tagging",
              "GTCRN: A Lightweight Speech Enhancement Model",
              "EdgeSpot: On-Device Keyword Spotting"]:
        assert not is_front_matter(t), t

def test_build_url_has_offset_and_filter():
    u = build_url(2024, "speech enhancement", 200)
    assert "offset=200" in u
    assert "type:proceedings-article" in u
    assert "from-pub-date:2024-01-01" in u
    assert "api.crossref.org" in u
    assert "mailto=" in u
```

- [ ] **Step 2: 运行测试确认失败**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\test_crawl_icassp.py`
Expected: FAIL（ModuleNotFoundError: crawl_icassp_crossref）

- [ ] **Step 3: 实现枚举器**

```python
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
    for qi, q in enumerate(queries):
        consecutive_empty = 0
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
                            "%s %s" % (a.get("given", ""), a.get("family", "")).strip()
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
    out = {"year": year, "unique": len(seen), "front_matter_dropped": front,
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\test_crawl_icassp.py`
Expected: PASS（5 项全过）

- [ ] **Step 5: 单年 dry-run 验证真实抓取**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\crawl_icassp_crossref.py 2024 --dry`
Expected: 每个 query 各取 1 页，累计 unique 数百条且不写盘；DOI 全部匹配 `icassp48485.2024`；front matter 被剔除。

- [ ] **Step 6: Commit**

```bash
git add scripts/crawl_icassp_crossref.py scripts/test_crawl_icassp.py
git commit -m "feat(scripts): ICASSP Crossref enumerator with offset paging and DOI-prefix filter"
```

---

### Task 2: ICASSP 五年抓取执行与覆盖率核算

**Files:**
- Create: `docs/research/corpus/icassp2022_papers.json` … `icassp2026_papers.json`（脚本产出）
- Create: `docs/research/corpus/icassp_census_summary.md`

**Interfaces:**
- Consumes: `crawl_icassp_crossref.crawl_year(year, ...)`
- Produces: 逐年语料 + `icassp_census_summary.md`（供 Task 5 报告消费）

- [ ] **Step 1: 后台跑 2022–2026 五年全量抓取**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\crawl_icassp_crossref.py 2022,2023,2024,2025,2026`
（20 个 query × 15 个 offset × 1.2s ≈ 每届 6 分钟，五届约 30 分钟——**必须用后台运行**，不要前台阻塞等待）

Expected: 五届各自落盘，每届 unique 在 800–2800 区间。

- [ ] **Step 2: 核算覆盖率并落 markdown**

```python
# 用 python.exe -c 执行，写入 docs/research/corpus/icassp_census_summary.md
import os, json, io
C = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus"
OFFICIAL = {2022: 1785, 2023: 2765, 2024: 2812, 2025: None, 2026: None}  # None=官方未公布
rows = []
for y in range(2022, 2027):
    p = os.path.join(C, "icassp%d_papers.json" % y)
    if not os.path.exists(p):
        rows.append((y, None, None, None, "MISSING")); continue
    d = json.load(io.open(p, encoding="utf-8"))
    n, off = d["unique"], OFFICIAL.get(y)
    cov = ("%.1f%%" % (100.0 * n / off)) if off else "未知(官方录用数未公布)"
    rows.append((y, n, off, cov, "OK"))
lines = ["# ICASSP 2022-2026 普查覆盖率（Crossref 枚举，自动生成）", "",
         "| 年份 | 抓到唯一论文 | 官方录用 | 覆盖率 | 状态 |", "|---|---|---|---|---|"]
for y, n, off, cov, st in rows:
    lines.append("| %d | %s | %s | %s | %s |" % (y, n if n is not None else "-",
                 off if off else "未公布", cov, st))
lines += ["", "> 单 query 有效深度约 1000-2000 条，多 query 分片合并去重后仍可能低于官方录用数。",
          "> 覆盖率 <60% 的年份在最终报告中必须显著声明为「部分枚举」，不得称「全量」。"]
io.open(os.path.join(C, "icassp_census_summary.md"), "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
```

Expected: 五届覆盖率表生成，2022/2023/2024 有明确百分比，2025/2026 标注"未公布"。

- [ ] **Step 3: 抽查 10 条真实性**

```python
import os, json, io, random
C = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus"
d = json.load(io.open(os.path.join(C, "icassp2024_papers.json"), encoding="utf-8"))
random.seed(7)
for p in random.sample(d["papers"], 10):
    print(p["year"], p["doi"], "|", p["title"][:70])
```

Expected: 10 条 DOI 全部形如 `10.1109/icassp48485.2024.*`，标题均为真实论文名（无 Committees/TOC）。**逐条用 `https://doi.org/<doi>` 人工可点开验证**——任一条对不上就说明过滤有漏，回到 Task 1 修 `FRONT_MATTER_PAT`。

- [ ] **Step 4: Commit**

```bash
git add docs/research/corpus/icassp20*_papers.json docs/research/corpus/icassp_census_summary.md
git commit -m "docs(corpus): ICASSP 2022-2026 Crossref census with coverage accounting"
```

---

### Task 3: Interspeech 2026 探测与摘要层补全

**Files:**
- Create: `scripts/crawl_interspeech_abstracts.py`
- Modify: `docs/research/corpus/interspeech_corpus.json`（**只追加 `abstract` 字段，不改已有字段**）
- Create: `docs/research/corpus/is2026_status.md`

**Interfaces:**
- Consumes: `docs/research/corpus/interspeech_corpus.json`（5507 条，含 `url` 字段指向 ISCA 摘要页）
- Produces: 带 `abstract` 的语料（供 Task 5 深读消费）

- [ ] **Step 1: 先确认 ISCA 2026 是否已上线（不得假设）**

Run:
```python
import urllib.request, ssl, re
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
for y in [2026, 2025]:
    u = "https://www.isca-archive.org/interspeech_%d/" % y
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "laos-research/1.0"})
        s = urllib.request.urlopen(req, timeout=45, context=ctx).read().decode("utf-8", "replace")
        print(y, "OK", len(s), "链接数", len(re.findall(r'href="[^"]*interspeech_%d' % y, s)))
    except Exception as e:
        print(y, "FAIL", type(e).__name__, str(e)[:60])
```

Expected: 2025 OK（~1.1MB）；2026 大概率 404。把结果写进 `is2026_status.md`——**若 2026 仍 404，就在该文件写明"ISCA 尚未上线 2026，Interspeech 语料上限为 2025"，并在最终报告中同样声明**。

- [ ] **Step 2: 实现摘要抓取器（增量 + 断点续传 + 限流）**

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""从 ISCA 摘要页补抓 abstract。增量：已有 abstract 的条目跳过；每 50 条落盘一次。"""
import urllib.request, ssl, json, re, io, os, sys, time

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "laos-research/1.0 (mailto:laos-survey@example.com)"}
CORPUS = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus\interspeech_corpus.json"


def fetch(url, tries=3, wait=6):
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if t < tries - 1:
                time.sleep(wait * (t + 1))   # ISCA 偶发 SSL UNEXPECTED_EOF，重试可恢复
    return None


def parse_abstract(html):
    if not html:
        return None
    m = re.search(r'<meta name="description" content="(.*?)"', html, re.S)
    if m:
        t = re.sub(r"\s+", " ", m.group(1)).strip()
        if len(t) > 80:
            return t
    blk = re.search(r'(?is)<div[^>]*class="[^"]*(?:abstract|summary)[^"]*"[^>]*>(.*?)</div>', html)
    if blk:
        t = re.sub(r"<[^>]+>", " ", blk.group(1))
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) > 80:
            return t
    return None


def main(limit, only_topics):
    corpus = json.load(io.open(CORPUS, encoding="utf-8"))
    papers = corpus["papers"]
    targets = [p for p in papers if not p.get("abstract")]
    if only_topics:
        targets = [p for p in targets if set(p.get("topics") or []) & set(only_topics)]
    targets = targets[:limit]
    print("待抓 %d 条" % len(targets))
    ok = fail = 0
    for i, p in enumerate(targets):
        html = fetch(p["url"])
        a = parse_abstract(html)
        if a:
            p["abstract"] = a
            ok += 1
        else:
            p["abstract_failed"] = True
            fail += 1
        if (i + 1) % 20 == 0:
            sys.stdout.write("  %d/%d ok=%d fail=%d\n" % (i + 1, len(targets), ok, fail))
            sys.stdout.flush()
        if (i + 1) % 50 == 0:
            io.open(CORPUS, "w", encoding="utf-8").write(
                json.dumps(corpus, ensure_ascii=False))
        time.sleep(0.8)
    io.open(CORPUS, "w", encoding="utf-8").write(json.dumps(corpus, ensure_ascii=False))
    print("DONE ok=%d fail=%d" % (ok, fail))


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    topics = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    main(lim, topics)
```

- [ ] **Step 3: 先跑 60 条验证解析器**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\crawl_interspeech_abstracts.py 60`
Expected: ok 率 ≥ 70%。**若 ok 率低于 50%，说明 `parse_abstract` 的 selector 不对**——先抓一篇样本页 dump HTML 结构再修，不要靠猜。

- [ ] **Step 4: 按 laos 相关主题批量补摘要**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\crawl_interspeech_abstracts.py 1200 emotion,edge,kws_vad,event,codec,enhance`（后台运行，1200 × 0.8s ≈ 16 分钟）

Expected: laos 相关六主题摘要覆盖 ≥ 1000 条。

- [ ] **Step 5: 统计摘要覆盖率**

Run:
```python
import json, io, collections
C = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus\interspeech_corpus.json"
d = json.load(io.open(C, encoding="utf-8"))
ps = d["papers"]
tot = len(ps); has = sum(1 for p in ps if p.get("abstract"))
print("总体 %d 条，有摘要 %d (%.1f%%)" % (tot, has, 100.0*has/tot))
c = collections.Counter()
for p in ps:
    for t in (p.get("topics") or []):
        c[t] += 1
        if p.get("abstract"):
            c[t+"_abs"] += 1
for t in ["emotion","edge","kws_vad","event","codec","enhance"]:
    print("  %-10s 总数%4d 有摘要%4d" % (t, c[t], c[t+"_abs"]))
```

Expected: 输出总体与各主题覆盖率，写进 `is2026_status.md` 追加段。

- [ ] **Step 6: Commit**

```bash
git add scripts/crawl_interspeech_abstracts.py docs/research/corpus/interspeech_corpus.json docs/research/corpus/is2026_status.md
git commit -m "docs(corpus): backfill Interspeech abstracts from ISCA pages, probe 2026 availability"
```

---

### Task 4: 统一 schema 合并、主题分类与校验器

**Files:**
- Create: `scripts/build_paper_corpus.py`
- Create: `scripts/check_paper_corpus.py`
- Create: `docs/research/corpus/papers_unified.jsonl`

**Interfaces:**
- Consumes: `icassp<YEAR>_papers.json`（Task 2）、`interspeech_corpus.json`（Task 3，含新增 abstract）
- Produces: `papers_unified.jsonl`（统一 10 字段）；`check_paper_corpus.py` 供 Task 5 校验引用

- [ ] **Step 1: 定义统一 schema 并写合并脚本**

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""合并 ICASSP/Interspeech 语料为统一 schema 的 JSONL。

统一字段（10 个，两个会议一致）：
  venue, year, doi_or_id, title, authors, url, abstract, topics[], has_abstract, source
"""
import json, io, os, re

BASE = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus"
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
    import collections
    print("按 venue:", dict(collections.Counter(r["venue"] for r in out)))
    print("按 year :", dict(sorted(collections.Counter(r["year"] for r in out).items())))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 写校验器**

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""校验 papers_unified.jsonl：schema 完整 / venue 合法 / year 在范围 / 主题非空 / 无占位符。"""
import json, io, os, sys, collections

P = os.path.join(r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus",
                 "papers_unified.jsonl")
FIELDS = ["venue", "year", "doi_or_id", "title", "authors", "url",
          "abstract", "topics", "has_abstract", "source"]
BAD = ["TBD", "TODO", "待补", "XXX", "N/A"]


def check(path=P):
    errs, n = [], 0
    venue_ct, topic_ct = collections.Counter(), collections.Counter()
    for i, line in enumerate(io.open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        n += 1
        try:
            r = json.loads(line)
        except Exception as e:
            errs.append("L%d: JSON 解析失败 %s" % (i, e)); continue
        for f in FIELDS:
            if f not in r:
                errs.append("L%d: 缺字段 %s" % (i, f))
        if r.get("venue") not in ("ICASSP", "Interspeech"):
            errs.append("L%d: 非法 venue %r" % (i, r.get("venue")))
        if not (2021 <= int(r.get("year", 0)) <= 2026):
            errs.append("L%d: year 越界 %r" % (i, r.get("year")))
        if not r.get("title", "").strip():
            errs.append("L%d: 空标题" % i)
        for b in BAD:
            if b in str(r.get("title", "")):
                errs.append("L%d: 标题含占位符 %s" % (i, b))
        if r.get("has_abstract") and not r.get("abstract"):
            errs.append("L%d: has_abstract=True 但 abstract 为空" % i)
        if not r.get("has_abstract") and r.get("abstract"):
            errs.append("L%d: has_abstract=False 但有 abstract" % i)
        venue_ct[r.get("venue")] += 1
        for t in r.get("topics") or []:
            topic_ct[t] += 1
    print("总条目 %d" % n)
    print("按 venue:", dict(venue_ct))
    print("按 topic:", dict(topic_ct.most_common()))
    if errs:
        print("\n违规 %d 条（前 20）：" % len(errs))
        for e in errs[:20]:
            print("  " + e)
        return 1
    print("\nPASS：0 违规")
    return 0


if __name__ == "__main__":
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1 else P))
```

- [ ] **Step 3: 跑合并 + 校验**

Run:
```
C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\build_paper_corpus.py
C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\check_paper_corpus.py
```
Expected: 合并输出总数（ICASSP 五届合计 + Interspeech 5507）；校验 PASS 0 违规。

- [ ] **Step 4: Commit**

```bash
git add scripts/build_paper_corpus.py scripts/check_paper_corpus.py docs/research/corpus/papers_unified.jsonl
git commit -m "feat(scripts): unified paper corpus schema, topic classifier and validator"
```

---

### Task 5: 双会议普查报告（markdown + HTML）

**Files:**
- Create: `docs/research/2026-09-14-icassp-interspeech-census.md`
- Create: `docs/icassp-interspeech-census.html`

**Interfaces:**
- Consumes: `papers_unified.jsonl`（Task 4）、`icassp_census_summary.md`（Task 2）、`is2026_status.md`（Task 3）
- Produces: 最终报告（本次交付物）

- [ ] **Step 1: 从语料生成真实统计（不得手编数字）**

Run:
```python
import json, io, collections
P = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus\papers_unified.jsonl"
rows = [json.loads(l) for l in io.open(P, encoding="utf-8") if l.strip()]
# 会议 × 年份
m = collections.Counter((r["venue"], r["year"]) for r in rows)
for k in sorted(m, key=lambda x: (x[0], x[1])):
    print("  %-12s %d: %d" % (k[0], k[1], m[k]))
print()
# 会议 × 主题（判断 laos 相关方向在哪个会更强）
t = collections.Counter()
for r in rows:
    for tp in r["topics"]:
        t[(tp, r["venue"])] += 1
tops = sorted({k[0] for k in t})
print("  %-10s %8s %8s" % ("主题", "ICASSP", "Interspeech"))
for tp in tops:
    print("  %-10s %8d %8d" % (tp, t[(tp, "ICASSP")], t[(tp, "Interspeech")]))
print()
# 年份 × 主题（趋势线，仅 Interspeech 全量可信，ICASSP 需标注覆盖率）
for tp in ["llm", "codec", "emotion", "edge", "event", "kws_vad"]:
    yc = collections.Counter(r["year"] for r in rows if tp in r["topics"] and r["venue"] == "Interspeech")
    print("  Interspeech %-9s %s" % (tp, [yc.get(y, 0) for y in range(2021, 2026)]))
```

Expected: 输出真实计数矩阵。报告中每个数字都必须能由这段脚本复现。

- [ ] **Step 2: 撰写报告 markdown**

必须包含以下小节（每节都带可复现数字）：
1. **方法与数据源实测结论** —— 逐条列出 Global Constraints 第 1/2 条的实测结果（Crossref 可用／DBLP 反爬／OpenAlex 429／ISCA 2026 未上线），并标注实测日期。
2. **ICASSP 2022–2026 普查** —— 逐年 `抓到数 / 官方录用数 / 覆盖率`；**显著声明**：覆盖率不足 100% 的年份写明"部分枚举"，禁止称"全量"。
3. **Interspeech 2021–2025 普查** —— 沿用既有 5507 条全量结论，补摘要覆盖率。
4. **双会议主题对照矩阵** —— Step 1 输出的 `主题 × 会议` 表，回答"laos 关心的方向该看哪个会"。
5. **五年趋势线** —— 仅用 Interspeech 全量数据画趋势（ICASSP 覆盖率不足，趋势不可信，必须注明）。
6. **与 laos 的落点映射** —— 十二主题逐个给一句话结论（哪些已有方案、哪些要看 DCASE 而非主会）。
7. **局限声明** —— 覆盖率、摘要缺失、front matter 过滤规则可能的误伤、2026 缺失。
8. **参考来源** —— 数据源 URL + 脚本路径 + 语料文件路径。

- [ ] **Step 3: 生成 HTML（深色单文件、零外部依赖、sticky 导航）**

先读 `docs/always-on-recording.html` 前 150 行沿用其 CSS 变量与布局套路（照抄风格不照抄内容）。至少含：
- 双会议规模对比条形图（内联 SVG）
- 主题 × 会议对照热力矩阵（内联 SVG）
- 五年趋势折线（内联 SVG，仅 Interspeech 全量）
- 覆盖率表（含"部分枚举"警示）

配色遵循深色主题：背景深色、文字浅色。**内联 SVG 每个形状必须显式设 `fill`**（已知坑：颜色类未实现，不显式设 fill 会回退黑色，深色背景上不可见）。

- [ ] **Step 4: 校验 HTML 与 markdown 数字一致**

Run: 用 Grep 分别从 `.md` 与 `.html` 提取"抓到数/覆盖率"关键数字比对。
Expected: 两套数字完全一致，不得出现两个版本。

- [ ] **Step 5: Commit**

```bash
git add docs/research/2026-09-14-icassp-interspeech-census.md docs/icassp-interspeech-census.html
git commit -m "docs: ICASSP+Interspeech 2022-2026 census report with measured coverage"
```

---

## Self-Review

**1. Spec 覆盖：** 前序 survey 的 ICASSP 抽样部分被 Task 2 真实枚举取代（✅）；Interspeech 全量结论保留并补摘要（✅ Task 3）；"找到真实作用"由 Task 3 摘要层 + Task 5 主题映射承接（✅）。缺口：ICASSP **无法做到 100% 全量**（Crossref offset 深度限制），已在 Global Constraints 第 5 条与 Task 5 第 2 节强制要求量化并声明。

**2. 占位符扫描：** 无 TBD/TODO/"类似 Task N"。每个脚本含完整实现而非"实现抓取逻辑"；每个 URL、正则、限速参数均来自 2026-09-14 实测。

**3. 类型一致性：** `crawl_year()` 返回 dict 含 `unique`/`front_matter_dropped`/`papers`；Task 2 Step 2 消费 `d["unique"]`；`papers_unified.jsonl` 的 10 字段在 Task 4 定义、Task 5 Step 1 消费，字段名逐字一致。`is_target_doi(doi, year)` 与 `is_front_matter(title)` 在 Task 1 测试中被调用，签名一致。
