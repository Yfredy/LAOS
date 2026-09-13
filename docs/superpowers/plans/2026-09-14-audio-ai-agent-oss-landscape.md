# 音频 / AI / Agent 开源项目星标调研实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 GitHub Search API 真实抓取音频、语音 AI、语音/多模态 Agent 三个方向的高星开源项目，建立可复核的星标榜，并给出对 laos 四段漏斗（常驻检测 → 触发捕获 → 即时蒸馏 → 原音频即焚）的适配结论。

**Architecture:** 多 query 分片抓取（topic + 关键词，按 stars 排序）→ 合并去重 → 分类打标 → 与 laos 需求映射 → 报告。所有原始数据落 `docs/research/oss/`，脚本落 `scripts/`，报告落 `docs/research/` + `docs/*.html`。

**Tech Stack:** Python 3.11（仅标准库 `urllib`／`json`）／GitHub Search API v3（未认证）

**Spec:** 无既有 spec；本计划自身即规格。参照 `docs/research/speech-emotion/00-taxonomy-and-metrics.md` 的口径惯例（尤其"左闭右开分档"与"不编造数字"）。

---

## Global Constraints

1. **GitHub API 实测结论（2026-09-14 实测，不得凭记忆改写）：**
   - ✅ `GET https://api.github.com/search/repositories` **可用**，返回真实 JSON。
   - ⚠️ **未认证限额：`search` 10 次／分钟；`core` 60 次／小时（实测当时剩余 0/60，已被前期探测耗尽）。** 因此：**只用 search 端点**，每请求后 `sleep 7`；**禁止**调用 `/repos/{owner}/{repo}`、`/rate_limit` 等 core 端点补充字段。
   - search 端点单次响应已含本任务所需的全部字段：`full_name` / `stargazers_count` / `description` / `language` / `license.spdx_id` / `html_url` / `created_at` / `pushed_at` / `updated_at` / `forks_count` / `open_issues_count` / `topics[]` / `archived` / `default_branch`。**不需要 core 端点。**
   - ❌ 单 query 最多返回 **1000 条**（`offset + per_page ≤ 1000`），且 `offset` 深分页成本高 → **不追求全量，按 stars 降序取每片 top 即可**（本任务目标本来就是"star 多的"）。
2. **实测 topic 规模（决定 query 选取，勿用其他名字）：**
   `topic:audio` 17996 ｜ `topic:speech-recognition` 8575 ｜ `topic:text-to-speech` 9260 ｜ `topic:voice` 3490 ｜ `topic:llm-agent` 2530 ｜ `topic:ai-agent` 31037 ｜ **`topic:audio-llm` 仅 3**（该 topic 名几乎无人使用，**不要**用它做主力 query）。
3. **必须过滤**：`archived:true` 的仓库与 fork。search 请求统一加 `fork:false`；落盘后再按 `archived == True` 剔除并单独计数。
4. **不编造数字。** star 数、license、语言一律取 API 返回值；`license` 为 `NOASSERTION` 时原样记录，不得猜测具体许可证。
5. **抓取时间必须落盘**（`crawled_at`，ISO 日期），star 数是时变量，报告中须标注。
6. **Bash 环境残缺（已踩坑）：** `dirname` / `cd` / `ls` / `head` / `tail` 全部 command not found，反引号被当命令替换。一律用绝对路径调 `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe`，脚本加 `-u` 防缓冲。
7. **文件读写一律 UTF-8。**
8. **不执行 git commit**（由主会话统一提交）。
9. **不得修改** `docs/research/speech-emotion/`、`audio-events/`、`auto-gain/` 下任何既有文件。
10. **已有语料（2026-09-14 审计，必须复用，不得重复抓取）：** `docs/research/corpus/oss_corpus.json` 已有 **3529 个仓库**（`repos[]` 含 `full_name` / `stars` / `topics` / `description` / `language` / `url` / `pushed_at` / `slices`），由 `corpus/crawl_github_oss.py` 的 10 个切片抓得。实测各切片音频相关率：
    - **8 个 `topic:` 切片 100% 相关**：`audio` 651 / `tts` 539 / `asr` 479 / `speech` 193 / `voice-assistant` 156 / `diarization` 100 / `enhancement` 97 / `audio-processing` 96，**合计 2311 条** → **直接复用为语料主体**。
    - **2 个关键词切片噪声爆炸**：`audio-llm`（query = `audio LLM in:name,description,readme stars:>300`，1000 条仅 **20%** 相关）与 `voice-agent`（`voice agent in:... stars:>100`，1000 条仅 **15%** 相关）。根因：GitHub 把短语拆词匹配，混入大量通用 LLM/Agent 高星仓库（噪声样例：`public-apis/public-apis` 479673、`vinta/awesome-python` 320390、`awesome-selfhosted/awesome-selfhosted` 318968、`avelino/awesome-go` 184019）。→ **必须去噪后使用，不得原样入榜**。
    - **补抓纪律**：新增 query 必须用**引号短语**（如 `"audio language model"`）或 `topic:` 过滤，**禁止再用裸关键词全文检索**。

---

### Task 1: GitHub 补抓器与 schema（服务于 Task 2 Step 3 的增量补抓）

**Files:**
- Create: `scripts/crawl_oss_repos.py`
- Create: `scripts/test_crawl_oss.py`
- Create: `docs/research/oss/`（目录）

**Interfaces:**
- Consumes: 无（独立脚本）
- Produces: `docs/research/oss/repos_fetched.jsonl`——**仅补抓增量**。语料主体来自已有 `corpus/oss_corpus.json`（2311 条干净切片），见 Global Constraints 第 10 条，Task 2 负责合并。每行一条：
  ```json
  {"full_name":"huggingface/transformers","stars":165392,"description":"...",
   "language":"Python","license":"Apache-2.0","html_url":"...","created_at":"2018-10-29",
   "pushed_at":"2026-09-13","topics":["audio","deep-learning"],"archived":false,
   "forks":34549,"open_issues":2440,"query":"topic:audio","crawled_at":"2026-09-14"}
  ```

- [ ] **Step 1: 写失败测试**

```python
# scripts/test_crawl_oss.py
import sys, os, json, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_oss_repos import (build_search_url, parse_repo, is_excluded,
                             QUERIES, sleep_between_requests)

def test_url_has_fork_false_and_sort():
    u = build_search_url("topic:audio", page=1, per_page=100)
    assert "api.github.com/search/repositories" in u
    assert "q=topic%3Aaudio" in u or "topic%3Aaudio" in u
    assert "fork%3Afalse" in u or "fork:false" in u
    assert "sort=stars" in u
    assert "order=desc" in u

def test_parse_repo_extracts_required_fields():
    raw = {"full_name": "a/b", "stargazers_count": 10, "description": "d",
           "language": "Python", "license": {"spdx_id": "MIT"},
           "html_url": "https://github.com/a/b", "created_at": "2020-01-01T00:00:00Z",
           "pushed_at": "2026-01-01T00:00:00Z", "topics": ["audio"],
           "archived": False, "forks_count": 1, "open_issues_count": 2}
    r = parse_repo(raw, "topic:audio", "2026-09-14")
    assert r["full_name"] == "a/b" and r["stars"] == 10
    assert r["license"] == "MIT" and r["language"] == "Python"
    assert r["query"] == "topic:audio" and r["crawled_at"] == "2026-09-14"
    assert r["created_at"] == "2020-01-01"      # 截断到日
    assert set(r.keys()) >= {"full_name","stars","description","language","license",
                             "html_url","created_at","pushed_at","topics","archived",
                             "forks","open_issues","query","crawled_at"}

def test_parse_repo_handles_null_license():
    r = parse_repo({"full_name": "x/y", "stargazers_count": 0, "license": None,
                    "topics": None, "description": None,
                    "created_at": "2021-05-05T00:00:00Z", "pushed_at": "2022-05-05T00:00:00Z"},
                   "q", "2026-09-14")
    assert r["license"] in (None, "NOASSERTION", "")
    assert r["topics"] == [] and r["description"] == ""

def test_archived_and_fork_excluded():
    assert is_excluded({"archived": True, "full_name": "a/b"})
    assert not is_excluded({"archived": False, "full_name": "a/b"})

def test_query_set_covers_three_domains():
    joined = " ".join(QUERIES).lower()
    for kw in ["audio", "speech", "voice", "agent", "tts"]:
        assert kw in joined, kw

def test_rate_limit_sleep_is_conservative():
    assert sleep_between_requests >= 7
```

- [ ] **Step 2: 运行测试确认失败**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\test_crawl_oss.py`
Expected: FAIL（ModuleNotFoundError: crawl_oss_repos）

- [ ] **Step 3: 实现抓取器**

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""GitHub 高星开源项目抓取（search 端点，未认证）。

实测约束（2026-09-14）：
  * search 限额 10 次/分钟 -> 每请求 sleep 7s
  * core 限额 60 次/小时且常为 0 -> 只用 search 端点，不补充字段
  * 单 query 上限 1000 条 -> 按 stars 降序取 top 即可（本任务只要高星的）
"""
import urllib.request, urllib.parse, json, ssl, time, sys, os, io, datetime

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "laos-research/1.0"}
sleep_between_requests = 7
OUT_DIR = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\oss"

# 三域覆盖：音频基础 / 语音 AI / Agent。规模见 Global Constraints 第 2 条。
QUERIES = [
    "topic:audio", "topic:speech-recognition", "topic:text-to-speech",
    "topic:voice", "topic:llm-agent", "topic:ai-agent",
    "topic:audio-classification", "topic:speech-synthesis",
    "topic:voice-assistant", "topic:sound",
    "speech recognition in:name,description",
    "voice assistant in:name,description",
    "audio llm in:name,description",
    "voice agent in:name,description",
    "realtime speech in:name,description",
    "keyword spotting in:name,description",
    "on-device speech in:name,description",
]


def build_search_url(query, page=1, per_page=100):
    q = query + " fork:false"
    return ("https://api.github.com/search/repositories?q=" + urllib.parse.quote(q) +
            "&sort=stars&order=desc&per_page=%d&page=%d" % (per_page, page))


def parse_repo(raw, query, crawled_at):
    lic = raw.get("license")
    lic = lic.get("spdx_id") if isinstance(lic, dict) else lic
    return {
        "full_name": raw.get("full_name", ""),
        "stars": raw.get("stargazers_count", 0),
        "description": raw.get("description") or "",
        "language": raw.get("language") or "",
        "license": lic or "",
        "html_url": raw.get("html_url", ""),
        "created_at": (raw.get("created_at") or "")[:10],
        "pushed_at": (raw.get("pushed_at") or "")[:10],
        "topics": raw.get("topics") or [],
        "archived": bool(raw.get("archived")),
        "forks": raw.get("forks_count", 0),
        "open_issues": raw.get("open_issues_count", 0),
        "query": query,
        "crawled_at": crawled_at,
    }


def is_excluded(r):
    return bool(r.get("archived"))


def fetch(url, tries=3, wait=20):
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
                return r.read()
        except Exception as e:
            sys.stderr.write("  retry%d %s\n" % (t, str(e)[:70]))
            if t < tries - 1:
                time.sleep(wait * (t + 1))
    return None


def main(pages_per_query=3):
    os.makedirs(OUT_DIR, exist_ok=True)
    crawled_at = datetime.date.today().isoformat()
    out_path = os.path.join(OUT_DIR, "repos_raw.jsonl")
    seen, excluded = {}, 0
    with io.open(out_path, "w", encoding="utf-8") as f:
        for qi, q in enumerate(QUERIES):
            for page in range(1, pages_per_query + 1):
                raw = fetch(build_search_url(q, page=page))
                if raw is None:
                    break
                try:
                    d = json.loads(raw.decode("utf-8"))
                except Exception:
                    break
                items = d.get("items") or []
                if not items:
                    break
                for it in items:
                    r = parse_repo(it, q, crawled_at)
                    if is_excluded(r):
                        excluded += 1
                        continue
                    if r["full_name"] in seen:
                        continue
                    seen[r["full_name"]] = 1
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                sys.stdout.write("  q%-2d %-42s page%d 累计%5d 剔除归档%d\n"
                                 % (qi, q[:42], page, len(seen), excluded))
                sys.stdout.flush()
                time.sleep(sleep_between_requests)
    print("DONE unique=%d archived_excluded=%d -> %s" % (len(seen), excluded, out_path))


if __name__ == "__main__":
    main(pages_per_query=int(sys.argv[1]) if len(sys.argv) > 1 else 3)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\test_crawl_oss.py`
Expected: PASS（7 项全过）

- [ ] **Step 5: 单 query 冒烟（验证真能抓到）**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u -c "import sys; sys.path.insert(0, r'C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts'); import crawl_oss_repos as m; raw=m.fetch(m.build_search_url('topic:audio',1,5)); import json; d=json.loads(raw.decode()); print('total',d['total_count']); [print(' ',i['full_name'], i['stargazers_count']) for i in d['items'][:5]]"`
Expected: `total` ≈ 17996，输出 5 个真实仓库名与 star 数。

- [ ] **Step 6: Commit**

```bash
git add scripts/crawl_oss_repos.py scripts/test_crawl_oss.py
git commit -m "feat(scripts): GitHub star-ranked repo crawler for audio/AI/agent landscape"
```

---

### Task 2: 已有语料审计、去噪与精准补抓

**Files:**
- Create: `scripts/audit_oss.py`
- Create: `docs/research/oss/repos_raw.jsonl`（合并后的干净语料）
- Create: `docs/research/oss/noise_dropped.jsonl`（被剔除的噪声，保留以便复核）
- Create: `docs/research/oss/oss_fetch_summary.md`

**Interfaces:**
- Consumes: `docs/research/corpus/oss_corpus.json`（已有 3529 条）；`crawl_oss_repos.fetch()` / `parse_repo()`（Task 1，用于 Step 3 补抓）
- Produces: `repos_raw.jsonl`（统一 schema 的干净语料，供 Task 3/4 消费）

- [ ] **Step 1: 写审计与去噪脚本**

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""审计 + 去噪 + 归一化已有 OSS 语料（corpus/oss_corpus.json）。

背景（2026-09-14 实测）：
  * 8 个 topic: 切片 100% 相关，免检复用
  * audio-llm / voice-agent 两个裸关键词切片相关率仅 20%/15%，须逐条重筛
  * 已有语料缺 license/created_at/forks 字段 -> 置空，不得编造
"""
import json, io, os, re, collections, datetime

CORPUS = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus\oss_corpus.json"
OUT_DIR = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\oss"
RAW = os.path.join(OUT_DIR, "repos_raw.jsonl")
NOISE = os.path.join(OUT_DIR, "noise_dropped.jsonl")

AUDIO_RE = re.compile(
    r"(?i)(\baudio\b|\bsound\b|\bspeech\b|\bvoice\b|\btts\b|\basr\b|"
    r"\bacoustic\b|\bwhisper\b|\bsonic\b|\bhearing\b|\bmusic\b|"
    r"\bvoicebot\b|\bwake.?word\b|\bvad\b|\bdiariz|\bvocoder\b|"
    r"\bspectrogram\b|\bvocal\b|\bspeaker\b|\bnoise\b|\becho\b|"
    r"\bmel\b|\bwav\b|\bmp3\b|\bpcm\b|\bmicrophone\b)")
CLEAN_SLICES = {"audio", "tts", "asr", "speech", "voice-assistant",
                "diarization", "enhancement", "audio-processing"}


def audio_related(r):
    text = " ".join([r.get("full_name", ""), r.get("description") or "",
                     " ".join(r.get("topics") or [])])
    return bool(AUDIO_RE.search(text))


def norm(r, crawled_at):
    return {
        "full_name": r.get("full_name", ""),
        "stars": r.get("stars", 0),
        "description": r.get("description") or "",
        "language": r.get("language") or "",
        "license": r.get("license") or "",
        "html_url": r.get("url") or r.get("html_url", ""),
        "created_at": r.get("created_at", ""),
        "pushed_at": (r.get("pushed_at") or "")[:10],
        "topics": r.get("topics") or [],
        "archived": bool(r.get("archived")),
        "forks": r.get("forks", 0),
        "open_issues": r.get("open_issues", 0),
        "query": ",".join(r.get("slices") or []) or "corpus:oss_corpus.json",
        "crawled_at": crawled_at,
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()
    repos = json.load(io.open(CORPUS, encoding="utf-8"))["repos"]
    kept, dropped, stat = [], [], collections.defaultdict(lambda: [0, 0])
    for r in repos:
        sl = set(r.get("slices") or [])
        for s in (r.get("slices") or ["?"]):
            stat[s][0] += 1
        if sl & CLEAN_SLICES:
            kept.append(r)
            for s in sl & CLEAN_SLICES:
                stat[s][1] += 1
        elif audio_related(r):
            kept.append(r)
            for s in sl:
                stat[s][1] += 1
        else:
            dropped.append(r)
    print("=== 各切片相关率 ===")
    for s, (tot, hit) in sorted(stat.items(), key=lambda x: -x[1][0]):
        print("  %-18s 总%5d 相关%5d (%.0f%%)" % (s, tot, hit, 100.0 * hit / max(tot, 1)))
    print("\n保留 %d 条，剔除噪声 %d 条" % (len(kept), len(dropped)))
    print("噪声 star top10（请人工确认确实与音频无关）:")
    for r in sorted(dropped, key=lambda x: -x.get("stars", 0))[:10]:
        print("   %7d  %s" % (r.get("stars", 0), r.get("full_name")))
    seen = {}
    with io.open(RAW, "w", encoding="utf-8") as f, io.open(NOISE, "w", encoding="utf-8") as g:
        for r in kept:
            n = norm(r, today)
            if n["full_name"] in seen:
                continue
            seen[n["full_name"]] = 1
            f.write(json.dumps(n, ensure_ascii=False) + "\n")
        for r in dropped:
            g.write(json.dumps(norm(r, today), ensure_ascii=False) + "\n")
    print("-> %s (%d 条)\n-> %s (%d 条)" % (RAW, len(seen), NOISE, len(dropped)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑审计与去噪**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\audit_oss.py`

Expected: 8 个 topic 切片显示 100%；`audio-llm` ≈20%、`voice-agent` ≈15%；保留约 2311+355 ≈ **2666 条**，剔除约 863 条。**人工扫一眼噪声 top10**，若发现真·音频项目被误杀（如描述为英文但用了生僻词），补进 `AUDIO_RE` 后重跑。

- [ ] **Step 3: 用引号短语精准补抓（补回被噪声稀释的相关项目）**

```python
# 补抓：全部使用引号短语或 topic: 过滤，禁止裸关键词全文检索
import sys, json, io, time, os
sys.path.insert(0, r"C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts")
import crawl_oss_repos as m

REFETCH = [
    '"audio language model" in:name,description stars:>100',
    '"speech language model" in:name,description stars:>100',
    '"voice agent" in:name,description stars:>100',
    '"voice assistant" in:name,description stars:>50',
    '"realtime voice" in:name,description stars:>50',
    '"on-device speech" in:name,description stars:>30',
    'topic:audio-llm', 'topic:voice-ai', 'topic:speech-synthesis',
    'topic:audio-classification', 'topic:keyword-spotting',
]
OUT = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\oss\repos_fetched.jsonl"
today = __import__("datetime").date.today().isoformat()
seen, got = set(), 0
with io.open(OUT, "w", encoding="utf-8") as f:
    for q in REFETCH:
        for page in (1, 2):
            raw = m.fetch(m.build_search_url(q, page=page))
            if raw is None:
                break
            d = json.loads(raw.decode("utf-8"))
            items = d.get("items") or []
            if not items:
                break
            for it in items:
                r = m.parse_repo(it, q, today)
                if m.is_excluded(r) or r["full_name"] in seen:
                    continue
                seen.add(r["full_name"])
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                got += 1
            print("  %-52s page%d 累计%d" % (q[:52], page, got))
            time.sleep(m.sleep_between_requests)
print("DONE 补抓 %d 条 -> %s" % (got, OUT))
```

Run: 保存为 `scripts/refetch_oss.py` 后执行（10 query × 2 页 × 7s ≈ 2.5 分钟）。

Expected: 补抓 200–800 条，其中 audio-llm / voice-agent 方向真正相关的项目被找回。

- [ ] **Step 4: 合并补抓结果进 `repos_raw.jsonl`**

Run:
```python
import json, io, os
OSS = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\oss"
RAW = os.path.join(OSS, "repos_raw.jsonl")
FET = os.path.join(OSS, "repos_fetched.jsonl")
rows = [json.loads(l) for l in io.open(RAW, encoding="utf-8") if l.strip()]
seen = {r["full_name"] for r in rows}
add = 0
for l in io.open(FET, encoding="utf-8"):
    if not l.strip():
        continue
    r = json.loads(l)
    if r["full_name"] in seen:
        continue
    seen.add(r["full_name"])
    rows.append(r)
    add += 1
with io.open(RAW, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("合并后 %d 条（新增 %d）" % (len(rows), add))
```

Expected: `repos_raw.jsonl` 最终 2800–3400 条。

- [ ] **Step 5: 生成抓取摘要**

```python
import json, io, os, collections
P = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\oss\repos_raw.jsonl"
rows = [json.loads(l) for l in io.open(P, encoding="utf-8") if l.strip()]
print("总条数", len(rows))
print("star 分布: >=10000: %d | 1000-9999: %d | 100-999: %d | <100: %d" % (
    sum(1 for r in rows if r["stars"] >= 10000),
    sum(1 for r in rows if 1000 <= r["stars"] < 10000),
    sum(1 for r in rows if 100 <= r["stars"] < 1000),
    sum(1 for r in rows if r["stars"] < 100)))
print("语言 top10:", collections.Counter(r["language"] for r in rows).most_common(10))
print("星级 top20:")
for r in sorted(rows, key=lambda x: -x["stars"])[:20]:
    print("  %8d  %-40s %s" % (r["stars"], r["full_name"], (r["description"] or "")[:50]))
```

Expected: 输出写入 `oss_fetch_summary.md`。**注意：已有语料无 `license` 字段，许可 top10 会全为空——摘要中须说明"许可信息缺失，需另行核实"，不得留空假装无数据。**

- [ ] **Step 6: 抽查 5 条真实性**

Expected: 取 top20 中 5 条打开 `html_url` 核对 star 数。**若差异 >10%，说明已有语料抓取时间过早**（`oss_corpus.json` 无 `crawled_at`，需按 `pushed_at` 推断并在报告中标注"star 数为抓取时刻快照，可能已过时"）。

- [ ] **Step 7: Commit**

```bash
git add scripts/audit_oss.py scripts/refetch_oss.py docs/research/oss/repos_raw.jsonl docs/research/oss/noise_dropped.jsonl docs/research/oss/oss_fetch_summary.md
git commit -m "docs(oss): audit existing corpus, drop noisy slices, refetch with quoted phrases"
```

---

### Task 3: 分类打标与 laos 适配映射

**Files:**
- Create: `scripts/classify_oss.py`
- Create: `docs/research/oss/repos_classified.jsonl`

**Interfaces:**
- Consumes: `repos_raw.jsonl`（Task 2）
- Produces: `repos_classified.jsonl`（在 raw 基础上追加 `category` 与 `laos_fit` 两字段）

- [ ] **Step 1: 实现分类器（可选多标签，不许强行单标签）**

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""按名称/描述/topics 给仓库打分类标签，并评估 laos 适配度。

category 可多标签；laos_fit 取值：
  core     - 直接可作为 laos 链路组件（能进四段漏斗）
  ref      - 参考/借鉴（架构或评测口径可抄，组件本身不落地）
  unrelated- 与 laos 无关
"""
import json, io, os, re, sys

BASE = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\oss"
SRC = os.path.join(BASE, "repos_raw.jsonl")
DST = os.path.join(BASE, "repos_classified.jsonl")

CATEGORY_RULES = {
    "asr":         r"(?i)\b(asr|speech.?to.?text|transcri|whisper|recognition|stt)\b",
    "tts":         r"(?i)\b(text.?to.?speech|\btts\b|vocoder|speech synthesis|voice cloning)\b",
    "audio-llm":   r"(?i)\b(audio.?(?:llm|language model)|speech.?llm|omni|multimodal (?:audio|speech))\b",
    "enhance":     r"(?i)\b(denois|enhance|dereverberat|noise (?:reduction|suppress)|separat)\b",
    "aed":         r"(?i)\b(audio tagging|sound event|acoustic scene|audio classification|event detection)\b",
    "codec":       r"(?i)\b(codec|encodec|audio compress|opus|soundstream)\b",
    "kws-vad":     r"(?i)\b(keyword spotting|wake.?word|voice activity|\bvad\b|hotword)\b",
    "speaker":     r"(?i)\b(speaker (?:verification|diarization|identification)|voiceprint|diariz)\b",
    "agent":       r"(?i)\b(agent|assistant|conversational|voicebot|realtime (?:voice|audio)|copilot)\b",
    "serving":     r"(?i)\b(serving|inference server|runtime|onnx|tensorrt|vllm|pipeline)\b",
    "dsp-lib":     r"(?i)\b(ffmpeg|librosa|soundfile|audio (?:library|processing)|dsp|pyaudio|sox)\b",
    "music":       r"(?i)\b(music (?:generation|source)|midi|song|singing|beat)\b",
    "dataset":     r"(?i)\b(dataset|corpus|benchmark)\b",
}
CAT = {k: re.compile(v) for k, v in CATEGORY_RULES.items()}

# laos 四段漏斗直接可用组件的强信号（core 判定）
CORE_SIGNALS = re.compile(
    r"(?i)(whisper|funasr|sensevoice|sherpa|silero|webrtc|onnxruntime|"
    r"piper|kokoro|vad|keyword spotting|audio tagging|yamnet|"
    r"livekit|pipecat|daily|ultravox)")


def classify(r):
    text = " ".join([r.get("full_name", ""), r.get("description", ""),
                     " ".join(r.get("topics") or [])])
    cats = [k for k, rx in CAT.items() if rx.search(text)]
    if "llm" in (r.get("topics") or []) or "llm" in r.get("full_name", "").lower():
        if "agent" in cats:
            cats.append("agent-llm")
    return cats


def fit(r, cats):
    text = " ".join([r.get("full_name", ""), r.get("description", "")])
    if CORE_SIGNALS.search(text) and r.get("stars", 0) >= 300:
        return "core"
    if {"asr", "tts", "enhance", "aed", "kws-vad", "agent", "audio-llm",
        "codec", "speaker", "serving", "dsp-lib"} & set(cats):
        return "ref"
    return "unrelated"


def main():
    rows = [json.loads(l) for l in io.open(SRC, encoding="utf-8") if l.strip()]
    with io.open(DST, "w", encoding="utf-8") as f:
        for r in rows:
            r["category"] = classify(r)
            r["laos_fit"] = fit(r, r["category"])
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    import collections
    cc, fc = collections.Counter(), collections.Counter()
    for r in rows:
        fc[r["laos_fit"]] += 1
        for c in r["category"]:
            cc[c] += 1
    print("总条数", len(rows))
    print("适配度:", dict(fc))
    print("分类分布:", dict(cc.most_common()))
    core = sorted([r for r in rows if r["laos_fit"] == "core"],
                  key=lambda x: -x["stars"])
    print("\ncore 组件 top30:")
    for r in core[:30]:
        print("  %8d  %-40s %s" % (r["stars"], r["full_name"], ",".join(r["category"])[:34]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行分类**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\classify_oss.py`
Expected: 输出分类与适配度分布 + core top30。**人工复核 core top30：若出现明显误判（如把音乐生成库判为 core），修 `CORE_SIGNALS` 正则后重跑。**

- [ ] **Step 3: Commit**

```bash
git add scripts/classify_oss.py docs/research/oss/repos_classified.jsonl
git commit -m "feat(oss): repo classifier with laos pipeline fitness tagging"
```

---

### Task 4: 星标榜报告（markdown + HTML）

**Files:**
- Create: `docs/research/2026-09-14-audio-ai-agent-oss-landscape.md`
- Create: `docs/audio-ai-agent-oss.html`

**Interfaces:**
- Consumes: `repos_classified.jsonl`（Task 3）、`oss_fetch_summary.md`（Task 2）
- Produces: 最终报告（本次交付物）

- [ ] **Step 1: 生成榜单数据（真实排序，不得手编）**

Run:
```python
import json, io, collections
P = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\oss\repos_classified.jsonl"
rows = [json.loads(l) for l in io.open(P, encoding="utf-8") if l.strip()]
by = collections.defaultdict(list)
for r in rows:
    for c in r["category"]:
        by[c].append(r)
for c in sorted(by, key=lambda k: -len(by[k])):
    top = sorted(by[c], key=lambda x: -x["stars"])[:12]
    print("\n### %s（%d 个）" % (c, len(by[c])))
    for r in top:
        print("  %8d | %-38s | %-10s | %s" % (
            r["stars"], r["full_name"], r["license"] or "-", (r["description"] or "")[:56]))
print("\n### 总榜 top40")
for r in sorted(rows, key=lambda x: -x["stars"])[:40]:
    print("  %8d | %-38s | %-14s | %s" % (
        r["stars"], r["full_name"], r["language"], (r["description"] or "")[:56]))
```

Expected: 输出分类榜与总榜，报告中每个 star 数都能由此复现。

- [ ] **Step 2: 撰写报告 markdown**

必须包含：
1. **方法与限额说明** —— search 10/min、只取 search 端点、单 query 上限 1000、`crawled_at` 日期、archived/fork 剔除规则。
2. **总榜 top40** —— 含 star / 语言 / 许可 / 一句话用途。
3. **分类榜** —— 12 类各 top12（asr / tts / audio-llm / enhance / aed / codec / kws-vad / speaker / agent / serving / dsp-lib / music）。
4. **laos 适配结论（核心小节）** —— 对每个 `laos_fit == core` 的组件，明确写：
   - 落在四段漏斗哪一段（①常驻检测 ②触发捕获 ③即时蒸馏 ④原音频即焚）
   - 端侧可行性（能否进 proot / 功耗档位，引用 `docs/research/speech-emotion/04-edge-deployment.md` 的 A/B 档口径）
   - 许可是否允许商用
   - 与既有选型的冲突或替代关系（如 `sherpa-onnx` 优于 `funasr`，已见于 SER 04 §8）
5. **明确不推荐清单** —— 高星但不适配的（如音乐生成、云端重型 serving），写清不推荐的理由，避免"star 高就该用"的误判。
6. **局限** —— star 数时变、topic 标签由作者自填导致分类有噪声、未读源码只凭描述判定、未验证许可兼容性（非法律意见）。

- [ ] **Step 3: 生成 HTML（深色单文件、零外部依赖、sticky 导航）**

先读 `docs/always-on-recording.html` 前 150 行沿用其 CSS 变量与布局套路（照抄风格不照抄内容）。至少含：
- 分类 × 星档热力矩阵（内联 SVG）
- top40 星标条形图（内联 SVG）
- 分类榜表格（可折叠或直接分节）
- laos 适配清单（高亮 core 组件）

配色遵循深色主题。**内联 SVG 每个形状必须显式设 `fill`**（已知坑：颜色类未实现，不显式设 fill 会回退黑色，深色背景上不可见）。

- [ ] **Step 4: 一致性校验**

Run: 用 Grep 从 `.md` 与 `.html` 各抽取 top10 仓库的 star 数比对。
Expected: 两套完全一致。

- [ ] **Step 5: Commit**

```bash
git add docs/research/2026-09-14-audio-ai-agent-oss-landscape.md docs/audio-ai-agent-oss.html
git commit -m "docs: audio/AI/agent open-source star landscape with laos fitness mapping"
```

---

## Self-Review

**1. Spec 覆盖：** 用户要求的"音频、AI、Agent 三个方向 + star 数多的"由**已有 3529 条语料中的 8 个干净 topic 切片（2311 条，100% 相关）** + Task 2 Step 3 引号短语补抓共同覆盖。**去噪是相对既有语料新增的关键一步**——原 `audio-llm`/`voice-agent` 两切片相关率仅 20%/15%，若原样入榜会得出"高星项目与音频无关"的错误结论，这正是"只了解表象"的具体形态。分类与 laos 映射由 Task 3／Task 4 第 4 节承接。

**2. 占位符扫描：** 无 TBD/TODO/"类似 Task N"。所有 URL、字段名、限额数值、切片规模与相关率均来自 2026-09-14 实测；所有正则给出了完整定义。

**3. 类型一致性：** `parse_repo()`（Task 1）与 `norm()`（Task 2）输出**同一套 14 字段 schema**，已有语料缺 `license`/`created_at`/`forks` 时置空（不编造），Task 3 与 Task 4 消费时按可能为空处理。`repos_raw.jsonl` 由 Task 2 Step 2 产出、Step 4 合并补抓、Task 3 分类消费，命名全程一致；`repos_fetched.jsonl` 仅为补抓中间产物，不进入 Task 3。`sleep_between_requests` 在 Task 1 定义、被测试断言 ≥7、被 Task 2 Step 3 复用。
