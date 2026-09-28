# 多顶会论文普查扩展（NLP/ML/CV/语音/多媒体/交叉）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 ICASSP+Interspeech 全量语料（19,792 篇）基础上，按用户给定的六大类 ~30 个顶会/期刊做 **laos 相关主题的目标检索**（非全量——邻近领域全量既不可行也不必要），产出统一语料 `corpus/multivenue_corpus.json` + 普查报告 + 选型体系接入。

**Architecture:** 复用已验证的 S2 主题切片爬虫模式（`corpus/crawl_icassp_s2*.py` 的限流纪律），泛化为 `scripts/crawl_multivenue.py`（--venue × --topics 参数化；venue 精确串先探测解析）；两波爬取（语音近邻+NLP 核心优先，ML/多媒体/交叉次之，CV 三大会仅音视主题可选）；合并校验后按 12 主题矩阵出报告并接入 INDEX/capstone。

**Tech Stack:** stdlib + curl 子进程（S2 Graph API，venue 过滤 + fields=title,year,venue,citationCount,externalIds,abstract）；75s 间距轮询（round-3 验证的生存参数）；诚实标注 uncovered。

**Spec:** 用户给定会议清单（六类）+ laos 主题集（既有 12 正则 + NLP/ML 场扩展 5 查询）：
- **NLP**：ACL、EMNLP、NAACL、COLING、CoNLL；期刊 TACL、Computational Linguistics
- **ML**：ICLR、NeurIPS、ICML、AAAI、IJCAI；期刊 JMLR
- **CV**（可选低优先，仅音视主题）：CVPR、ECCV、ICCV；期刊 TPAMI、IJCV
- **语音近邻**（laos 最高优先）：SLT、ASRU、WASPAA、CHiME；期刊 IEEE/ACM TASLP、EURASIP JASMP
- **多媒体**：ACM MM、ICMR、MMSys、ICME、PCM；期刊 IEEE TMM、ACM TOMM
- **交叉**：SIGIR、KDD、WWW、WSDM、RecSys

## Global Constraints

- 每条记录必须来自 API 实际返回（title/year/venue/citationCount/DOI 或 arXiv id）；抓不到标 uncovered，禁止训练知识补数
- venue 过滤用 S2 返回的 venue 字段**客户端精确匹配**（S2 venue= 参数是模糊的，返回可能含邻居串——过滤在本地做）
- S2 限流纪律：请求间 sleep 75s；429 时等 35s 重试一次；每波预算 ≤90 请求；超预算即停并如实记录
- 年份窗口 2021-2026；主题查询集固定（12 既有 + 5 扩展：`LLM agent tool use`、`agent memory`、`audio language model`、`multimodal agent`、`on-device inference`）
- 不改动 papers_unified.jsonl（既有 19,792 语料不动）；新语料独立文件 + 独立校验
- 全量测试基线 328 全绿不得破

---

### Task 1: 爬虫泛化 `scripts/crawl_multivenue.py` + venue 串探测

**Files:**
- Create: `scripts/crawl_multivenue.py`
- Create: `docs/research/corpus/multivenue_strings.json`（venue 精确串解析结果）
- Test: `tests/test_multivenue.py`

**Interfaces:**
- Produces:
```python
VENUES: dict[str, list[str]]   # 类别 -> venue 精确串（含别名，从 S2 实测解析）
def venue_of(paper: dict) -> str | None    # paper["venue"] 匹配 VENUES 展开集
def slice_query(venue: str, topic: str) -> str  # S2 URL 构造（复用 crawl_icassp_s2 的 s2() 语义）
def merge corpora(paths) -> dict          # 去重 by (title.lower(), year)，venue 计数
# CLI: --wave A|B [--venue NAME] [--limit-requests N] [--dry-run]
```
- venue 串探测法（写进脚本 `--probe` 子命令）：对每个候选名跑一次 `query=<名> venue=<名>` 取 top5 的 venue 字段众数，人工不可介入——探测结果落 multivenue_strings.json 并提交（后续波次引用）

- [ ] **Step 1: TDD**——test_multivenue.py：①venue_of 精确匹配+别名 ②merge 去重（同 title 不同 venue 各计一次 venue 命中）③slice_query URL 含 venue+year+fields ④VENUES 覆盖 Spec 六类全部名字（断言类别键集）
- [ ] **Step 2:** FAIL 确认 → 实现（curl 子进程 + 75s 纪律照搬 crawl_icassp_s2_round3.py）→ PASS
- [ ] **Step 3:** 跑 `--probe`（~30 venue × 1 请求 ≈ 40 分钟后台）；探测失败的 venue 在 strings.json 标 `"unresolved"` 并给出试过的串
- [ ] **Step 4:** 全量 328+新增 绿；`git commit -m "feat(scripts): multivenue crawler + venue string probe"`

### Task 2: 爬取波 A（语音近邻 + NLP 核心——laos 最相关）

**Files:**
- Create: `docs/research/corpus/multivenue_<venue>.json` ×~12（SLT/ASRU/WASPAA/CHiME/TASLP/EURASIP/ACL/EMNLP/NAACL/COLING/CoNLL/TACL）

- [ ] **Step 1:** 后台跑 `--wave A`（12 venue × 17 主题查询，预算 90 请求：语音近邻 6 venue 全 17 主题；NLP 6 venue 仅 5 扩展主题+emotion/paralinguistic/codec 3 既有 ≈8 主题）；429/超预算如实截断
- [ ] **Step 2:** 逐 venue 抽查 3 条记录真实性（title 与 DOI/arXiv 对得上、venue 字段确为该会）；unresolved venue 记录替代方案
- [ ] **Step 3:** `git commit -m "docs(corpus): multivenue wave A — speech-adjacent + NLP core slices"`

### Task 3: 爬取波 B（ML 核心 + 多媒体 + 交叉；CV 三大会可选音视）

**Files:**
- Create: `docs/research/corpus/multivenue_<venue>.json` ×~15（NeurIPS/ICML/ICLR/AAAI/IJCAI/JMLR/ACMMM/ICMR/MMSys/ICME/PCM/TMM/TOMM/SIGIR/KDD/WWW/WSDM/RecSys；CVPR/ECCV/ICCV 仅 `audio-visual|audio language model` 两主题）

- [ ] **Step 1:** 后台跑 `--wave B`（预算 90 请求；ML 用 5 扩展主题+SSL；MM 用 audio/video 相关；交叉用 agent/memory/recsys-for-personal-memory 主题）
- [ ] **Step 2:** 同 Task 2 Step 2 抽查；commit `docs(corpus): multivenue wave B — ML/multimedia/cross slices`

### Task 4: 合并校验 + 报告 + 体系接入

**Files:**
- Create: `scripts/check_multivenue.py`（校验器：去重后总数/venue 分布/年份分布/必填字段/与 papers_unified 的重叠量——同 paper 双库出现算交叉验证成功）
- Create: `docs/research/2026-09-28-multivenue-survey.md`
- Modify: `docs/research/INDEX.md`（新报告入清单+导航）
- Modify: `docs/research/2026-09-19-laos-adoption-capstone.md`（§G 路线图表尾加一行：多顶会普查语料规模与报告链接）

- [ ] **Step 1:** 校验器 TDD（3 用例：重叠计数/必填字段/venue 归属）→ 实现 → 跑
- [ ] **Step 2:** 报告：§1 覆盖矩阵（venue × 主题命中数，uncovered 如实）§2 高被引 top20（每篇 2 句摘要，abstract 缺则标注）§3 与 ICASSP/Interspeech 12 主题矩阵的跨会对照（哪些主题在哪个会最强）§4 laos 增量启示（≤8 条，引用报告内证据）
- [ ] **Step 3:** INDEX/capstone 接入；全量 328+新增 绿；push；交付说明

## Self-Review

- 覆盖：用户六类清单全列（CV 标可选，理由：laos 无视觉线）✓ 期刊路线（S2 venue 串覆盖期刊，无需 ISSN 特殊通道——Task 1 探测兜底）✓ 既有体系复用（12 正则主题矩阵/爬虫纪律/校验器模式）✓
- 占位符：VENUES 六类键、17+5 主题集、预算数、抽查规则、报告四节全部写实 ✓
- 一致性：multivenue_corpus.json 命名与 check_multivenue 对应；不碰 papers_unified.jsonl（约束明文）✓
- 现实约束：S2 限流是最大风险——预算/截断/uncovered 纪律三重兜底；波 A/B 各 90 请求 × 75s ≈ 2 小时/波（后台跑）
