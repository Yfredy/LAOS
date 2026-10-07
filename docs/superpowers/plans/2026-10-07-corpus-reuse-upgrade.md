# 语料复用升级（corpus-reuse-upgrade）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 120,234 行扩展语料（v0.18.0）从"池子"变成 laos 的"决策与叙事资产"：强命中精炼 → 可复用查询工具 → 三条主题线的文献深读与 laos 落点对照（治理叙事 44 篇全读 / 对话听觉定向检索 / 空间隐私映射）→ 吸收进既有叙事文档 → 发版 v0.19.0。

**Architecture:** 先程序化解决 v0.18.0 遗留的 42% 弱命中问题（强命中精炼器，产出 `laos_relevant_strong.jsonl` 作为后续唯一工作集）；再落一个零依赖语料查询 CLI（后续任何波次复用）；然后三条主题线并行产出对照文档（每篇：来源｜可取之处｜laos 落点｜状态 ●◐○，capstone 同格式）；最后把结论吸收进 agentos-landscape/adoption-capstone/README 并按发版纪律收口。

**Tech Stack:** 纯 stdlib Python（miniconda3 解释器）；文档为 markdown；无新增第三方依赖。

**Spec:** 用户 2026-10-07 指令"先写项目复用升级计划"；上游资产 = `docs/research/2026-10-06-venue-expansion-survey.md`（§3 注记：audio-speech 42% 裸子串弱命中、attack-success-rate 误标 68、agent-os 宽分支 836 vs 窄治理分支 44）、`corpus/venue_expansion/laos_relevant.jsonl`（2,103 行）、`docs/research/2026-09-19-laos-adoption-capstone.md`（对照表格式范本）、`docs/research/agentos-landscape-2026-08.md`（八分类待校验）。

## Global Constraints

- **conda 红线**：只用 `C:/Users/yaoyue/miniconda3/python.exe`，禁止 pip install，脚本零第三方依赖。
- **计数口径**：引用 2,103 时必须带弱命中注记；引用精炼后工作集时用实跑 `wc -l` 新计数；测试用实跑数。
- **来源诚实**：IEEE 三刊（tpami/tmm/taslp）与部分会议 abstract 为 null——标题级映射须标注"仅标题"；摘要可得才做语义级裁决。anthology 系 abstract 覆盖率高（tacl 100%）。
- **状态标记沿用 capstone 口径**：●已落地/●已消化/◐P0–P3/○不做；文献对照不虚构落点，找不到就写 ○ 并一句话说明。
- **不动 sync_docs 锚点**：改 PPT/README 内容时只动叙述段，版本号/测试计数锚点由 release.py 管。
- 发版：新文档域+新工具 → v0.19.0，走 `release.py --apply` 全流程（AGENTS.md 纪律）。

---

### Task 1: 强命中精炼器（工作集净化）

**Files:**
- Create: `corpus/venue_expansion/curate_strong_hits.py`
- Create: `corpus/venue_expansion/laos_relevant_strong.jsonl`
- Test: `tests/test_curate_strong_hits.py`

**Interfaces:**
- Consumes: `corpus/venue_expansion/laos_relevant.jsonl`（行 schema：title/year/venue/authors/url/doi/abstract/laos_topic）。
- Produces: `is_strong(entry) -> bool`；`laos_relevant_strong.jsonl`（原字段 + `"strong": true` + `"strong_terms": [命中的强词组]`）——Task 3/4 的唯一输入工作集；CLI `--stats` 打印 topic×强/弱 计数。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_curate_strong_hits.py 核心断言
from corpus.venue_expansion.curate_strong_hits import is_strong

def test_audio_speech_bare_substring_is_weak(self):
    # 裸 asr/tts/vad 子串 = 弱（attack success rate 的 asr）
    self.assertFalse(is_strong({"title": "Boosting attack success rate (asr) of jailbreaks",
                                "abstract": None, "laos_topic": "audio-speech"}))

def test_audio_speech_phrase_is_strong(self):
    self.assertTrue(is_strong({"title": "Streaming wake word detection on device",
                               "abstract": None, "laos_topic": "audio-speech"}))
    self.assertTrue(is_strong({"title": "Noise-robust asr front-end",  # asr 邻接音频词
                               "abstract": "speech recognition pipeline", "laos_topic": "audio-speech"}))

def test_agent_os_narrow_only(self):
    self.assertTrue(is_strong({"title": "Kernel-level sandboxing of LLM agents",
                               "abstract": None, "laos_topic": "agent-os"}))
    self.assertFalse(is_strong({"title": "A survey of llm agent tool use",  # 宽分支
                                "abstract": None, "laos_topic": "agent-os"}))

def test_spatial_privacy_kept(self):
    self.assertTrue(is_strong({"title": "Binaural localization with beamforming",
                               "abstract": None, "laos_topic": "spatial-privacy"}))
```

- [ ] **Step 2: 跑测试确认失败**（ModuleNotFoundError）
- [ ] **Step 3: 实现**：强命中规则——audio-speech 须命中**多词短语**（wake[- ]?word / keyword spotting / speech recognition / voice activity / echo cancell / far[- ]?field / text[- ]?to[- ]?speech / speech translation / spoken dialogue / voice agent / audio-visual speech / diarization 等）或裸词 asr/tts/vad 与音频语境词同现（speech/audio/voice/acoustic 前后 60 字符内）；agent-os 只认窄分支（agent 与 OS/sandbox/syscall/kernel/governan/resource/isolation 同现），宽分支（仅 llm+agent）判弱；spatial-privacy 全保（词表本身即短语级）。输出与统计同 Task 接口。
- [ ] **Step 4: 单测绿 → 全量跑**：预期 audio-speech 大幅缩水（强命中应 ≈600±100）、agent-os ≈44±5、spatial-privacy 114 不变；`wc -l laos_relevant_strong.jsonl` 计数写报告草稿；attack-success-rate 68 篇须 0 残留（`grep -ci "attack success" laos_relevant_strong.jsonl` == 0）
- [ ] **Step 5: Commit** `feat(corpus): strong-hit refiner — curated working set for reuse waves`

### Task 2: 语料查询 CLI（复用基础设施）

**Files:**
- Create: `scripts/query_corpus.py`
- Test: `tests/test_query_corpus.py`

**Interfaces:**
- Consumes: `corpus/venue_expansion/*.jsonl`（含 laos_relevant[_strong].jsonl）。
- Produces: `query(opts) -> list[dict]`；CLI：`--topic agent-os|audio-speech|spatial-privacy --strong-only --venue PREFIX --year A[-B] --grep PATTERN --limit N [--json]`，默认人读表格（year/venue/title 截断 80 列）。

- [ ] **Step 1: 写失败测试**（--topic 过滤、--strong-only 只取 strong=true、--year 2023-2025 区间含端点、--grep 大小写不敏感、--limit 截断、空结果返回 []）——用 tempfile 造 3 行 fixture jsonl 注入
- [ ] **Step 2: 确认失败** → **Step 3: 实现**（argparse + json 逐行读 + 过滤链；纯 stdlib）
- [ ] **Step 4: 单测绿 + 冒烟**：`python scripts/query_corpus.py --topic agent-os --strong-only --limit 10`（应 ≤44 行且全窄分支观感）
- [ ] **Step 5: Commit** `feat(scripts): corpus query CLI — reusable retrieval across venue-expansion jsonl`

### Task 3: 治理叙事文献对照（agent-os 44 篇全读）

**Files:**
- Create: `docs/research/2026-10-07-agentos-governance-literature.md`
- Create: `docs/research/corpus/venue_expansion/agent_os_narrow.tsv`（title/year/venue/doi 三列导出，供文档表格与后续复核）

**Interfaces:**
- Consumes: Task 1/2 工作集与查询 CLI。
- Produces: 对照文档（capstone 同格式四列：来源｜可取之处｜laos 落点｜状态）；对 agentos-landscape 八分类的**校验结论节**（新形态有/无，有则列名）。

- [ ] **Step 1: 导出全清单**：`python scripts/query_corpus.py --topic agent-os --strong-only --json > var/agent_os_strong.json`，`wc -l` 核对 ≈44
- [ ] **Step 2: 逐篇裁决**——每篇读 title+abstract（IEEE 无摘要素标注"仅标题"），写四列对照；44 篇全量无遗漏（文档含核对句"44/44 全覆盖，来源计数=X"）；落点对照 laos 现有能力面（syscall 闸门/seccomp 强制层/FleetLedger/MCP Tasks/判断层/audit）
- [ ] **Step 3: 八分类校验节**：对照 agentos-landscape-2026-08.md 的 L0–L3 光谱与八含义，写"新形态/确认/修正"三小节
- [ ] **Step 4: Commit** `docs(research): agent-os narrow-branch governance literature mapping (44 papers)`

### Task 4: 对话听觉与空间隐私定向检索

**Files:**
- Create: `docs/research/2026-10-07-dialog-spatial-retrieval.md`

**Interfaces:**
- Consumes: Task 2 查询 CLI（--grep 定向）。
- Produces: 文档两章：对话调度线（duplex/interrupt/barge-in/wake[- ]?word/keyword spotting/voice activity 定向，各子题列 ≤8 篇强命中 + 一句话与 laos 对话调度/KWS 实测的关系）；空间隐私线（spatial-privacy 114 全览分类计数：binaural/beamform/watermark/privacy 四小类 + 各小类代表 3 篇 + 与 binaural.py/foa.py/隐私红线的关系）。

- [ ] **Step 1: 定向检索跑通**：`python scripts/query_corpus.py --strong-only --grep "barge|interrupt|full-duplex|turn-taking" --json | wc -l` 等子题逐个跑，计数入文档
- [ ] **Step 2: 写文档**（两章；每子题一句话裁决 ●◐○；KWS 子题须回指 voicenpu 报告 §六 的 sherpa-onnx 实测项）
- [ ] **Step 3: Commit** `docs(research): dialog & spatial targeted retrieval from strong-hit corpus`

### Task 5: 叙事吸收与文档升级

**Files:**
- Modify: `docs/research/agentos-landscape-2026-08.md`（文末追加"2026-10 校验附注"一节，引 Task 3 文档）
- Modify: `docs/research/2026-09-19-laos-adoption-capstone.md`（资产表追加 2 行：本波两份新文档）
- Modify: `README.md`（§文献/调研段一句话提及 120,234 行语料与两份对照文档；**不碰 sync_docs 锚点**）
- Modify: `docs/research/INDEX.md`（主报告 +2 行，头部计数 74→76、主报告 26→28）

- [ ] **Step 1: 四处修改**（附注节 ≤10 行、资产表 2 行、README 一句话、INDEX 两行+计数）
- [ ] **Step 2: 核对**：`git diff` 确认未触碰任何锚点（grep 版本号/测试计数行与改前一致）
- [ ] **Step 3: Commit** `docs: absorb governance-literature & retrieval findings into narrative docs`

### Task 6: 发版 v0.19.0

- [ ] **Step 1**: `python -m unittest discover -s tests -q` 全绿（634+新增）
- [ ] **Step 2**: `python scripts/release.py --apply`（新工具+新文档域 → v0.19.0，14 介绍文档自动同步）→ CHANGELOG 誊写（关键数：强命中工作集 N 行/44 篇对照/两份文档）→ commit → `git tag -a v0.19.0` → push + Release 页（TUN 断窗则 var/ 重试脚本后台跑，v0.17.0 模式）
- [ ] **Step 3**: 交付说明（版本表 + 三条主题线一句话结论）

## Self-Review

- 用户意图覆盖：强命中净化（解 42% 弱命中）✅ 复用工具 ✅ 44 篇对照 ✅ 定向检索 ✅ 叙事吸收 ✅ 发版 ✅。
- 占位符：Task 3/4 为文献阅读型任务，步骤给的是抽取命令+文档模板结构（评审按"全量覆盖与格式"验收），代码任务 1/2 有完整测试代码与实现规则。✅
- 类型一致：jsonl schema 全程 {…,"laos_topic",…,+strong/strong_terms}；CLI 参数在各任务引用一致。✅
- 冲突检查：Task 5 改 README/INDEX 与 release.py sync_docs 的锚点无重叠（锚点仅版本/测试计数行）；Task 1 精炼不改原 laos_relevant.jsonl（只新增文件）。✅
