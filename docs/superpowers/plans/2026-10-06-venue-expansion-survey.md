# 顶会语料扩展普查（venue-expansion）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 laos 论文语料从 ICASSP+Interspeech（19,792 篇）与 35-venue 普查（9,908 条）扩展到用户给出的顶会全清单（NLP/ML/CV/语音/多媒体/交叉约 40 个新 venue，2021–2026 窗口），并按 laos 双主线（Agent 治理 / 听觉语音）过滤出相关论文清单。

**Architecture:** 双主通道抓取——ACL Anthology 官方 bib dump 一包覆盖 NLP 全家（NAACL/COLING/CoNLL/TACL/CL/EMNLP/ACL），Crossref ISSN/容器名游标分页覆盖 IEEE/ACM/Springer 期刊与会议集（TASLP/TPAMI/IJCV/TMM/TOMM/JMLR/AAAI/IJCAI/ICCV/SIGIR/KDD/WWW/WSDM/RecSys/ICMR/MMSys/ICME/PCM/ICIP/WASPAA/CHiME/GlobalSIP/EURASIP JASMP/NeurIPS 书目系列）。DBLP 与 OpenReview **已实测被 JS 反爬挑战拦截（2026-10-06）**，仅作服务器侧 webReader 点状降级。统一产出 `corpus/venue_expansion/*.jsonl`（与 papers_unified.jsonl 同 schema：title/year/venue/authors/doi/url/abstract?）。

**Tech Stack:** 纯 stdlib Python（urllib.request + json/csv/re），miniconda3 解释器，curl 仅用于 HEAD 探测；测试走 unittest（仓库既有口径）。

**Spec:** 用户 2026-10-06 指令（顶会全清单按领域分组 + CCF 口径注）；基线资产 `docs/research/2026-09-29-multivenue-survey.md`（35 venue 普查方法论：Crossref↔ACL Anthology↔PMLR 覆盖边界、AAAI 解锁=ISSN 2159-5399 精确过滤）。

## Global Constraints

- **conda 红线**：只用 `C:/Users/yaoyue/miniconda3/python.exe`，不 pip install；脚本零第三方依赖。
- **网络现实**（2026-10-06 实测）：Crossref `api.crossref.org` ✅；ACL Anthology `aclanthology.org` ✅；DBLP `dblp.org` ❌（"Making sure you're not a bot!" JS 挑战，带浏览器 UA 仍拦截）；OpenReview `api.openreview.net` ❌（ChallengeRequiredError）；GitHub/TUN 间歇断窗——所有抓取脚本必须带**指数退避重试 + 断点续抓**（逐 venue 落盘，重跑跳过已存在文件）。
- **不重复原则**：已有语料（ICASSP/Interspeech/35-venue 普查含 TASLP/ASRU/SLT/AAAI 等）只做**增量年份**，不重抓；registry 测试强制对照 `docs/research/corpus/` 已有清单去重。
- **来源诚实**：报告必须写明每个 venue 的数据源、被反爬拦截的降级路径与覆盖缺口（如 ICML=PMLR 无 DOI、OpenReview 不可达时 ICLR 增量缺失）。
- **口径**：CCF 分级照用户清单抄录；计数用实跑 `wc -l`，不引用宣称值。
- 发版：语料扩展+新报告=新文档域 → 完成后 `release.py --apply`（预计 v0.18.0），14 个介绍文档自动同步（AGENTS.md 纪律）。

---

### Task 1: venue 注册表 + 去重校验

**Files:**
- Create: `corpus/venue_expansion/venues.csv`（列：`venue,ccf,dblp_stream,crossref_issn,crossref_container,anthology_prefix,years,source,notes`）
- Create: `corpus/venue_expansion/make_registry.py`
- Test: `tests/test_venue_registry.py`

**Interfaces:**
- Produces: `load_registry(path) -> list[dict]`；后续所有抓取任务按行的 `source` 列分派（anthology / crossref_journal / crossref_container）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_venue_registry.py
"""venue 注册表校验：schema/去重/年窗/来源分派。"""
import csv, unittest
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "corpus/venue_expansion/venues.csv"
HAVE = {"icassp", "interspeech", "taslp", "asru", "slt", "aaai", "iclr"}  # 已有语料 venue（小写）

class Registry(unittest.TestCase):
    def setUp(self):
        with open(REG, encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_schema_and_nonempty(self):
        need = {"venue", "ccf", "source", "years"}
        for r in self.rows:
            self.assertTrue(need <= set(r), r)
            self.assertTrue(r["venue"] and r["source"] in
                            {"anthology", "crossref_journal", "crossref_container", "deferred"}, r)

    def test_venue_unique_casefold(self):
        names = [r["venue"].casefold() for r in self.rows]
        self.assertEqual(len(names), len(set(names)))

    def test_existing_corpus_incremental_only(self):
        # 已有 venue 只允许增量年份（years 起点须 > 已覆盖终点或注明 incremental）
        for r in self.rows:
            if r["venue"].casefold() in HAVE:
                self.assertIn("incremental", r["years"] + r["notes"].casefold(), r["venue"])

    def test_user_list_covered(self):
        want = {"naacl", "coling", "conll", "tacl", "neurips", "icml", "ijcai",
                "iccv", "tpami", "ijcv", "waspaa", "chime", "eurasip-jasmp",
                "icmr", "mmsys", "icme", "pcm", "tmm", "tomm", "sigir", "kdd",
                "www", "wsdm", "recsys", "icip", "globalsip"}
        got = {r["venue"].casefold() for r in self.rows}
        self.assertEqual(want - got, set(), f"缺: {want - got}")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**（`python -m unittest tests.test_venue_registry` → FileNotFoundError）
- [ ] **Step 3: 写 venues.csv**（约 30 行；关键 ISSN：TASLP=2329-9290✅实测、TMM=1520-9210、TOMM=1551-6857、TPAMI=0162-8828、IJCV=0920-5691、JMLR=issn 1533-7928（Crossref 刊）、EURASIP JASMP=1687-4722、CL=comp-linguistics 0891-2017、AAAI=2159-5399✅已解锁；anthology_prefix：naacl/coling/conll/tacl；ICML 标 `deferred`（PMLR 无 DOI，报告注明缺口）；ICLR 标 `deferred`（OpenReview 反爬，已有 35-venue 存量）。NeurIPS 走 crossref_container="Advances in Neural Information Processing Systems"。WASPAA/CHiME/ICMR/MMSys/ICME/PCM/ICIP/GlobalSIP/SIGIR/KDD/WWW/WSDM/RecSys/IJCAI/ICCV 均走 crossref_container=官方会议集全名）
- [ ] **Step 4: 跑测试通过**
- [ ] **Step 5: Commit** `git commit -m "feat(corpus): venue-expansion registry (30 venues, dedup vs existing corpus)"`

### Task 2: ACL Anthology NLP 族一包抓取

**Files:**
- Create: `corpus/venue_expansion/fetch_anthology.py`
- Create: `corpus/venue_expansion/anthology_nlp.jsonl`
- Test: `tests/test_fetch_anthology.py`

**Interfaces:**
- Consumes: registry 行 `source=anthology`（anthology_prefix 列）。
- Produces: `parse_bib_entries(text) -> list[dict]`（title/year/venue/authors/url/abstract 可空）；jsonl 行 schema 与后续任务一致。

- [ ] **Step 1: 写失败测试**（内置 3 条 bib fixture：普通条目 / 含 abstract 条目 / 非条目噪音行，断言字段解析与噪音跳过）

```python
# tests/test_fetch_anthology.py 核心断言
def test_parse_basic_and_abstract(self):
    bib = '''
@inproceedings{naacl-2024-fake,
  title = "Agent Sandbox Study",
  author = "Zhang, Wei and Li, Ming",
  booktitle = "Proceedings of NAACL",
  year = "2024",
  url = "https://aclanthology.org/2024.naacl-1.1/"
}
@article{tacl-fake,
  title = "Always-On Listening",
  abstract = "We study privacy.",
  journal = "TACL",
  volume = "12",
  year = "2024"
}
'''
    entries = parse_bib_entries(bib)
    self.assertEqual(len(entries), 2)
    self.assertEqual(entries[0]["venue"], "Proceedings of NAACL")
    self.assertTrue(entries[1]["abstract"].startswith("We study"))
```

- [ ] **Step 2: 确认失败**（ImportError）
- [ ] **Step 3: 实现 fetch_anthology.py**：`urllib.request` + 退避重试（1s→2s→…→60s，×8）抓 `https://aclanthology.org/anthology+abstracts.bib.gz`（先 HEAD 看大小；>500MB 则改抓分卷 `https://aclanthology.org/volumes/<prefix>-<year>/` 逐卷 bib）；`gzip` 解压；`parse_bib_entries` 用逐条状态机（`@type{key,` 起、平衡大括号止），字段按行 `key = {value}` 正则剥外层括号；按 registry anthology_prefix+years 过滤venue（booktitle/journal 前缀匹配 naacl/coling/conll/transactions acl/computational linguistics）；写 jsonl（utf-8，每行一 JSON）。
- [ ] **Step 4: 跑单测通过 + 真抓冒烟**：`python corpus/venue_expansion/fetch_anthology.py --venue naacl --limit 50`，断言 ≥30 行且 year 分布合理
- [ ] **Step 5: 全量抓取**（逐 venue 落盘 `corpus/venue_expansion/anthology_<venue>.jsonl`，重跑跳过已存在文件）+ `wc -l` 计数登记到 Task 6 报告草稿
- [ ] **Step 6: Commit** `feat(corpus): ACL Anthology NLP family fetch (naacl/coling/conll/tacl/cl)`

### Task 3: Crossref 期刊族（ISSN 游标分页）

**Files:**
- Create: `corpus/venue_expansion/fetch_crossref.py`（含 `fetch_journal(issn, years) -> list[dict]` 与 `fetch_container(name, years) -> list[dict]`，`--mode journal|container`）
- Create: `corpus/venue_expansion/crossref_journal_*.jsonl`
- Test: `tests/test_fetch_crossref.py`

**Interfaces:**
- Consumes: registry 行 `source=crossref_journal`（crossref_issn 列）/ Task 2 的 jsonl 行 schema。
- Produces: `crossref_to_entry(message_item) -> dict`（title/DOI/issued→year/container-title→venue/ISSN）；Task 4 复用同一函数与 CLI。

- [ ] **Step 1: 写失败测试**（fixture：一条真实形态 Crossref item dict，断言年份取 `issued.date-parts[0][0]`、title 首元素、缺 abstract 时置 None；分页 cursor 逻辑用注入的 fake urlopen 测两页拼接）
- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**：`GET https://api.crossref.org/journals/<issn>/works?rows=1000&cursor=<c>&filter=from-pub-date:2021-01-01,until-pub-date:2026-12-31&select=DOI,title,issued,container-title,ISSN`；`next-cursor` 循环到返回 <rows；退避重试×8；`mailto=` 参数进 polite pool。
- [ ] **Step 4: 单测过 + 冒烟**：`--mode journal --issn 2329-9290 --limit 100`（TASLP 增量，应 >0 行）
- [ ] **Step 5: 跑全部期刊行**（TASLP 增量年/EURASIP JASMP/TPAMI/IJCV/TMM/TOMM/JMLR/CL），逐文件落盘+wc 计数
- [ ] **Step 6: Commit** `feat(corpus): crossref journal family fetch`

### Task 4: Crossref 会议族（container-title 查询归并）

**Files:**
- Modify: `corpus/venue_expansion/fetch_crossref.py`（container 模式已有骨架，本任务调通归并）
- Create: `corpus/venue_expansion/crossref_conf_*.jsonl`
- Test: `tests/test_fetch_crossref.py`（追加 container 用例）

**Interfaces:**
- Consumes: registry 行 `source=crossref_container`（crossref_container 列=官方容器名）。
- Produces: 与 Task 3 同 schema 的 jsonl；`venue 归并` = item 的 container-title 与容器名 casefold 相等才收（防误配）。

- [ ] **Step 1: 追加失败测试**：container 模式——注入 fake urlopen 返回两条 item（一条 container-title 匹配 "International Conference on Machine Learning"? 示例用 IJCAI 容器名匹配/一条不匹配），断言只收匹配行
- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**：`GET /works?query.container-title=<name>&filter=from-pub-date:2021-01-01,type:proceedings-article&rows=1000&cursor=...&select=DOI,title,issued,container-title`；归并规则同 Interfaces；NeurIPS 特例：容器名 "Advances in Neural Information Processing Systems"（会议论文以书目条目在库）。
- [ ] **Step 4: 单测过 + 冒烟**（`--mode container --name "IEEE/CVF International Conference on Computer Vision" --limit 100`）
- [ ] **Step 5: 跑全部会议行**（AAAI 增量/IJCAI/ICCV/SIGIR/KDD/WWW/WSDM/RecSys/ICMR/MMSys/ICME/PCM/ICIP/WASPAA/CHiME/GlobalSIP/NeurIPS），逐文件落盘+计数；**每个 venue 若归并后为 0 行，登记进报告"覆盖缺口"节**（container 名在 Crossref 可能变形，试 2–3 个官方别名后再判缺）
- [ ] **Step 6: Commit** `feat(corpus): crossref conference family fetch`

### Task 5: laos 相关性过滤

**Files:**
- Create: `corpus/venue_expansion/filter_laos_relevant.py`
- Create: `corpus/venue_expansion/laos_relevant.jsonl`
- Test: `tests/test_filter_laos_relevant.py`

**Interfaces:**
- Consumes: `corpus/venue_expansion/*.jsonl` 全部产出。
- Produces: `is_relevant(entry) -> tuple[bool, str|None]`（命中主题标签）；`laos_relevant.jsonl` 行=原行+`"laos_topic"` 字段。

- [ ] **Step 1: 写失败测试**（三主线词表各 2 个正例 + 1 个反例："LLM agent operating system constraints"→agent 治理线；"always-on audio wake word"→听觉线；"binaural localization"→空间线；"image style transfer diffusion"→False）

```python
# laos 相关三主线（写进 filter_laos_relevant.py 顶部）
TOPICS = {
    "agent-os":   r"(agent).{0,40}(operating system|sandbox|syscall|kernel|governan|resource|quota|isolation)|(llm|language model).{0,30}(agent)",
    "audio-speech": r"(wake[- ]?word|keyword spotting|vad|voice activity|always[- ]?on|speech recognition|asr|tts|diariz|far[- ]?field|echo cancell)",
    "spatial-privacy": r"(binaural|spatial audio|beamform|acoustic camera|speech privacy|audio watermark)",
}
```

- [ ] **Step 2: 确认失败** → **Step 3: 实现**（标题+摘要（若有）拼串 casefold 后按 TOPICS 正则匹配，命中即标；`--stats` 打印各主题计数）
- [ ] **Step 4: 单测过 + 全量过滤** → `wc -l laos_relevant.jsonl`，按 venue × topic 交叉计数表存 Task 6
- [ ] **Step 5: Commit** `feat(corpus): laos-relevance filter across expanded venues`

### Task 6: 汇总报告 + INDEX + 发版

**Files:**
- Create: `docs/research/2026-10-06-venue-expansion-survey.md`
- Modify: `docs/research/INDEX.md`（主报告 +1，头部计数）
- Modify: `CHANGELOG.md`（v0.18.0 段）

- [ ] **Step 1: 写报告**：每 venue 一行（数据源/年份窗/实抓计数/增量或全新）；**来源诚实节**（DBLP/OpenReview 反爬实测证据、ICML=PMLR 无 DOI 缺口、ICLR 依赖旧存量、Crossref container 归并 0 行的 venue 与尝试过的别名）；laos_relevant 交叉计数表 + 三主线各列 top 代表论文 5 篇（按年份倒序）；CCF 口径列照用户清单。
- [ ] **Step 2: INDEX 登记**（主报告行 + 头部 `共 N 份` 计数更新）
- [ ] **Step 3: 全套测试** `python -m unittest discover -s tests -q` 全绿（含 Task 1–5 新测试）
- [ ] **Step 4: 发版**：`python scripts/release.py --apply`（新文档域→v0.18.0，实跑测试数自动同步 14 文档）→ CHANGELOG 誊写 → `git tag -a v0.18.0` → push + Release 页（网络断窗则 var/ 脚本后台重试，复用 v0.17.0 模式）
- [ ] **Step 5: Commit** `docs(research): venue-expansion survey & corpus (v0.18.0)`

## Self-Review

- 用户清单覆盖：NAACL/COLING/CoNLL/TACL/CL(Task2)、NeurIPS/IJCAI/JMLR(Task3/4)、AAAI 增量(Task4)、ICML=deferred 有诚实缺口、ICCV/TPAMI/IJCV(Task4/3)、SLT/ASRU/TASLP 增量(Task3)、WASPAA/CHiME/EURASIP(Task4/3)、ACM MM 已有、ICMR/MMSys/ICME/PCM/TMM/TOMM(Task4/3)、SIGIR/KDD/WWW/WSDM/RecSys/ICIP/GlobalSIP(Task4)、ICLR=deferred(存量)——无遗漏。✅
- 无占位符；Task 2/3/5 给了核心代码与正则词表全文。✅
- schema 一致：三处 jsonl 均为 title/year/venue/authors?/doi?/url?/abstract?/laos_topic?。✅
