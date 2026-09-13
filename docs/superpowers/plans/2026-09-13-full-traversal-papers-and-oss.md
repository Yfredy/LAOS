# ICASSP 全量枚举 + 音频/AI/Agent 开源项目全量搜索 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"真实遍历"补完——① ICASSP 2022-2026 全量论文枚举（补齐 Interspeech 已完成的 100% 枚举）；② GitHub 音频×AI×Agent 高星开源项目全量搜索入库；③ 产出论文+项目双普查报告并推送。

**Architecture:** 三个独立爬虫脚本（OpenAlex → ICASSP 全量、S2 轮询 → 剩余切片、GitHub Search → 开源项目），全部写入 `docs/research/corpus/`；数据合成复用既有 `interspeech_corpus.json` 的主题矩阵口径（同一套正则），最终报告由数据程序化生成（不手写数字）。

**Tech Stack:** Python 3.12（uv 路径 `/c/Users/yaoyue/AppData/Roaming/uv/python/cpython-3.12.14-windows-x86_64-none/python.exe`）+ curl 子进程（本地 Python TLS 走代理不稳，**一律用 curl**）；GitHub REST API v3（无认证）；OpenAlex REST（无认证）。

**Spec:** docs/research/2026-09-13-icassp-interspeech-full-survey.md（已完成部分的约束链与方法论，本计划是其"剩余工作"的执行规格）。

## Global Constraints

- 一切 HTTP 用 `subprocess.run(["curl", ...])`，带 `--max-time 90`；禁止 urllib 直连（本地代理 TLS 抖动已实测）
- 失败重试退避：5s/15s/30s/60s/90s；429 特殊处理（OpenAlex 等 `retryAfter` 头，S2 等 35s）
- 所有数字必须来自抓取响应，报告中标注来源文件；抓不到的如实写"未覆盖"
- 零第三方依赖（stdlib only）
- 产物统一放 `docs/research/corpus/`，报告放 `docs/research/`
- 主库测试（253 项）与本工作无关，不修改任何 `laos/` 代码

---

### Task 1: OpenAlex 全量枚举 ICASSP 2022-2026

**Files:**
- Create: `docs/research/corpus/crawl_icassp_openalex.py`
- Create: `docs/research/corpus/icassp_oa_<year>.json` ×5（产物）
- Create: `docs/research/corpus/icassp_full_corpus.json`（合并产物）

**Interfaces:**
- Consumes: 无（独立）
- Produces: `icassp_full_corpus.json`——`{"summary": {totals, topic_matrix}, "papers": [{year,title,authors,doi,url,topics}]}`，字段与 `interspeech_corpus.json` 完全同构，供 Task 3 合并

**前置条件：** OpenAlex 日配额 UTC 午夜（08:00 北京时间）重置。执行前先探测：
`curl -s "https://api.openalex.org/sources?search=ICASSP&per-page=3"` 若返回 `Rate limit exceeded` 则本任务顺延到重置后执行。

- [ ] **Step 1: 探测配额并定位 ICASSP source ID**

```bash
cd docs/research/corpus
curl -s "https://api.openalex.org/sources?search=ICASSP&per-page=10" -o oa_sources.json
# 用 python 解析出候选 source id 列表（display_name 含 ICASSP 的，记下 works_count 最大的）
```
预期：返回 `results` 数组；ICASSP 每届可能各是一个 source（display_name 形如 "ICASSP 2024..."）或一个总 source。把所有候选 id 记入 `oa_sources.json` 供 Step 2 用。

- [ ] **Step 2: 写爬虫 `crawl_icassp_openalex.py`**

核心逻辑（完整写入脚本，不是伪码）：

```python
QUERIES: 对 Step 1 得到的每个 source id：
  url = (f"https://api.openalex.org/works?filter=primary_location.source.id:{sid}"
         f"&per-page=200&cursor=*&select=title,authorships,doi,publication_year,"
         f"primary_location,cited_by_count")
  while cursor:
      r = curl_json(url.replace("cursor=*", f"cursor={cursor}"))
      meta = r["meta"]
      for w in r["results"]:
          ct = (w.get("primary_location") or {}).get("source", {}) or {}
          name = ct.get("display_name", "")
          if "ICASSP" in name:            # 客户端再过滤
              yield {"year": w["publication_year"],
                     "title": w.get("title"),
                     "authors": ", ".join(a["author"]["display_name"]
                                          for a in w.get("authorships", [])[:6]),
                     "doi": w.get("doi") or "",
                     "cited_by": w.get("cited_by_count", 0)}
      cursor = meta.get("next_cursor")
      time.sleep(1.2)                     # OpenAlex 礼貌限速 10 req/s，留余量
```
每届（每年一个 source 或按 publication_year 过滤）落一个 `icassp_oa_<year>.json`。

- [ ] **Step 3: 跑爬虫并校验规模**

Run: 后台执行，完成后检查每届条数。
预期/校验口径：2022≈1,785、2023≈2,765（openaccept 已知录用数）；**误差 >25% 时在报告记录偏差原因**（OpenAlex 可能含 workshop/缺席卷），不静默丢弃。

- [ ] **Step 4: 打主题标签生成 `icassp_full_corpus.json`**

复用 `interspeech_corpus.json` 同一套 TOPICS 正则（emotion/speaker/diariz/enhance/codec/kws_vad/tts/event/ssl/edge/llm/health，从 `crawl` 后处理脚本复制），产出与 Interspeech 同构的 summary+papers。

- [ ] **Step 5: Commit**

```bash
git add docs/research/corpus/icassp_oa_*.json docs/research/corpus/icassp_full_corpus.json docs/research/corpus/crawl_icassp_openalex.py
git commit -m "docs(corpus): OpenAlex full enumeration of ICASSP 2022-2026"
```

---

### Task 2: S2 剩余 8 切片（与 Task 1 并行，不依赖配额）

**Files:**
- Create: `docs/research/corpus/crawl_icassp_s2_round3.py`
- Create: `docs/research/corpus/icassp_s2_round3.json`（产物）

**Interfaces:**
- Consumes: Task 2 既有 `icassp_s2_raw.json`（4 切片已得：enhancement 5,257 / emotion 1,838 / codec 2,388 / VAD 183）
- Produces: 其余 8 切片命中数，最终并入报告 §ICASSP 切片表

- [ ] **Step 1: 写轮询脚本**——复用 `crawl_icassp_s2.py` 全部机制，仅改 QUERIES 为剩余 8 个：`speaker diarization / keyword spotting / text to speech / sound event detection / self-supervised speech / streaming speech recognition / speech language model / paralinguistic`，FIELDS 增加 abstract，DEADLINE = 40 分钟
- [ ] **Step 2: 后台运行**（`run_in_background=true`），与 Task 1 时间重叠
- [ ] **Step 3: 合并三轮结果**（raw + round2 + round3）为 `icassp_s2_slices.json`：`{"slice": total, ...}` 12 键齐全（失败的键如实写 `"uncovered"`）
- [ ] **Step 4: Commit**：`docs(corpus): S2 remaining topic slices for ICASSP`

---

### Task 3: GitHub 音频×AI×Agent 高星项目全量搜索

**Files:**
- Create: `docs/research/corpus/crawl_github_oss.py`
- Create: `docs/research/corpus/oss_corpus.json`（产物）
- Create: `docs/research/corpus/oss_top30_readmes/`（产物，前 30 项目 README）

**Interfaces:**
- Consumes: 无
- Produces: `oss_corpus.json`——`[{"full_name","stars","topics","description","language","url","slices":[...],"pushed_at"}]`，供 Task 4 报告与 laos 选型映射

- [ ] **Step 1: 写搜索脚本**——10 个切片，每片翻页到 1000 上限或取尽：

```python
SLICES = [
    "topic:audio stars:>300",            # 音频通用
    "topic:speech stars:>200",
    "topic:speech-recognition stars:>100",
    "topic:tts stars:>100",
    "topic:speaker-diarization stars:>20",   # 窄域门槛降低
    "topic:speech-enhancement stars:>50",
    "topic:voice-assistant stars:>100",
    "topic:audio-processing stars:>300",
    "audio LLM in:name,description,readme stars:>300",   # 音频×LLM
    "voice agent in:name,description,readme stars:>100", # 语音×Agent
]
url = ("https://api.github.com/search/repositories?q=" + quote(q)
       + "&sort=stars&order=desc&per_page=100&page=" + str(page))
# 头：Accept: application/vnd.github+json + User-Agent: laos-survey
# 限速：搜索 API 10 req/min 未认证 → 每请求间 sleep 7s；403/429 时 sleep 65s
```
每条记录：`full_name, stargazers_count, topics, description, language, html_url, pushed_at`。按 full_name 去重（一片可命中多片）。

- [ ] **Step 2: 跑完后统计并落盘**——总量、每切片命中数、star 分布（>10k / 1k-10k / 100-1k），生成 `oss_corpus.json`
- [ ] **Step 3: 前 30 项目深读**——按「stars × laos 相关性」选 30 个（判据：题目/描述命中 speech/voice/audio/agent/diarization/tts/asr），拉 README：
  `curl -s -H "Accept: application/vnd.github.raw" https://api.github.com/repos/<full_name>/readme`
  存 `oss_top30_readmes/<full_name.replace('/','__')>.md`；每项目一行摘要（做什么/架构/许可/对 laos 的关系）写 `oss_top30_summary.json`
  ⚠️ core API 60 req/h 未认证——30 个 README 需 sleep 65s×若干，预计 ~40 分钟，放后台
- [ ] **Step 4: Commit**：`docs(corpus): GitHub audio×AI×agent OSS traversal (N repos, top-30 deep reads)`

---

### Task 4: 合成最终双普查报告

**Files:**
- Create: `docs/research/2026-09-14-papers-oss-full-survey.md`
- Modify: `docs/research/2026-09-13-icassp-interspeech-full-survey.md:1`（顶部加一行"ICASSP 全量枚举已由 2026-09-14 报告接管"）

**Interfaces:**
- Consumes: `interspeech_corpus.json`（已有）+ `icassp_full_corpus.json`（Task 1）+ `icassp_s2_slices.json`（Task 2）+ `oss_corpus.json` / `oss_top30_summary.json`（Task 3）
- Produces: 最终报告（用户交付物）

- [ ] **Step 1: 写报告生成脚本 `gen_final_report.py`**——所有统计数字从 corpus JSON 程序化读出（禁止手写数字），产出：
  - §1 双会议合并主题矩阵（Interspeech 全量 + ICASSP 全量，逐年逐年对照）
  - §2 ICASSP 全量规模校验（vs openaccept 录用数，偏差说明）
  - §3 OSS 全景：切片命中表、star 榜 top50、分类榜单（TTS/ASR/增强/说话人/音频LLM/Voice Agent/音频工具）
  - §4 论文↔开源对照：每个 laos 相关主题列"代表论文 + 对应最高星实现"（如 Streaming Sortformer ↔ nvidia；EmoBox ↔ emo-box；Silero VAD ↔ snakers4）
  - §5 laos 选型映射更新（哪些 OSS 直接可用、许可是什么）
- [ ] **Step 2: 人工复核一遍报告**（数字 vs JSON 抽查 5 处）
- [ ] **Step 3: Commit**：`docs(research): combined papers+OSS full survey report`

---

### Task 5: 推送与收尾

- [ ] **Step 1:** `git push origin master`（失败则等 60s 重试 ×3——本地代理抖动已知）
- [ ] **Step 2:** 向用户交付：报告路径、语料清单、三项覆盖率数字（Interspeech 100% / ICASSP OpenAlex 全量±偏差 / OSS 切片全量）、诚实声明剩余未覆盖部分

## Self-Review

- 覆盖检查：用户三点要求——ICASSP 全量（Task 1+2）✓、Interspeech 全量（已完成，报告引用）✓、音频×AI×Agent OSS 遍历（Task 3）✓、整理成报告（Task 4）✓
- 占位符扫描：所有 URL/脚本逻辑/文件名/限速值均已写实，无 TBD ✓
- 类型一致性：`icassp_full_corpus.json` 与 `interspeech_corpus.json` 字段同构（Task 1 Step 4 明确复用同一 TOPICS）✓
