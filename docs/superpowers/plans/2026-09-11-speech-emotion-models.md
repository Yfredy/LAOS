# 声学情感模型调研（Speech Emotion Recognition Landscape）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 摸清当前可用的语音情感识别（SER / 声学情感）模型全景，按**规模**（小型 / 中型 / 大型）分档，并标出每条记录的**端侧可部署**与**多模态**两个跨切标签，最终给出能落进 `AlwaysOnRec-HY4` 的 `ear` 蒸馏通道的选型结论。

**Architecture:** 调研型计划，不是代码型计划。产出是 `docs/research/speech-emotion/` 下 6 个 markdown + 1 个 HTML 全景；"测试"不是一个 pytest，而是 `scripts/check_ser_table.py`——一个解析 markdown 表格并强制每条记录都带**可核验来源**（arXiv ID / HuggingFace / GitHub）、参数量、许可、指标的校验器。先立口径（Task 1），再分三条规模线并行收录（Task 2/3/4），再补两个跨切轴（Task 5/6），最后收敛（Task 7）并落地（Task 8）。

**Tech Stack:** Python 3 stdlib（`scripts/check_ser_table.py`）、WebSearch / WebFetch、arXiv API、`docs/` 下的零依赖单文件 HTML（沿用 `docs/always-on-recording.html` 的深色单文件风格）。

**Spec:** 本次对话的用户需求（5 类划分，已按 Scope Check 重构为 3×2）+ `docs/research/always-on-recording/` 下既有调研的约束结论。

## Scope Check（为什么是 3×2 而不是 5 类平行）

用户原始划分是「支持端侧部署 / 多模态 / 大型 / 中型 / 小型」五类并列。这三者不在同一维度：

- **规模轴**（小型 / 中型 / 大型）是互斥的分档，一个模型只能落一档；
- **端侧可部署**是能力标记，与规模相关但不等价（7B 量化后未必端侧可行，300M 也可能跑不动实时）；
- **多模态**是输入模态标记，与规模完全正交（有多模态小模型，也有单模态大模型）。

按 5 类平行收录会导致同一模型在多个文件里各写一遍、参数量与指标口径打架。因此改为：**3 档定主键 + 2 个布尔标记**，交叉结论在 Task 7 出。

---

## Global Constraints

1. **不存声纹。** 声纹在中国法下属敏感个人信息。模型若带说话人识别/验证能力，必须在表格"备注"列标注 `speaker-capable`，但**不参与选型**，也不写入任何落地建议。
2. **情绪标签非临床。** 最大规模的抑郁语音检测研究敏感度与特异度均仅 71%（见 `docs/research/always-on-recording/academic-papers.md`）。所有涉及健康/临床声称的模型必须显式标注"非诊断"，且不得作为落地推荐。
3. **每个模型条目必须可核验。** 来源列必须有 arXiv ID、HuggingFace repo 或 GitHub 链接之一；查不到就**删除该条**，不留"待补"。
4. **许可必须记录。** 权重许可（Apache-2.0 / MIT / CC-BY-NC / 自定义）与数据集许可都要写，商用受限的要标红。
5. **参数量统一口径。** 单位 M = 10^6；必须注明是否含音频编码器、是否为量化前数值。
6. **数字必须带出处。** 指标值后面跟基准数据集名（如 `UAR 73.4 (IEMOCAP)`），不写裸数字。
7. **中文场景必须覆盖。** 至少收录 MER2023/2024/2025、M3ED、CHEAVD、CASIA 中的中文基准结果；只讲英文数据集的调研不算完成。
8. **落地要能接回 `AlwaysOnRec-HY4`。** 跨仓库路径 `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4`，其 `aor/drivers/ear.py` 的通道常量是 `AOR_ASR_CHANNEL`（`stub` / `funasr` / `server`），选型结论必须说明接进来要动哪里。
9. **零第三方依赖交付。** HTML 全景沿用单文件深色风格，不引外部 CDN。

---

### Task 1: 定口径 —— 规模分档、指标体系、表格 schema 与校验器

**Files:**
- Create: `docs/research/speech-emotion/00-taxonomy-and-metrics.md`
- Create: `scripts/check_ser_table.py`
- Test: `scripts/check_ser_table.py --selftest`

**Interfaces:**
- Produces: 表格 schema（下面所有 Task 的产出都用它）、`check_ser_table.py <file.md>` 校验器、规模分档边界常量。

- [ ] **Step 1: 写 schema 与分档定义**

`docs/research/speech-emotion/00-taxonomy-and-metrics.md` 内容骨架（直接落盘，不要留空）：

```
# 口径：规模分档 / 指标 / 记录 schema

## 规模分档（按参数量，量化前，含音频编码器）
| 档 | 参数量 | 典型部署位 | 典型延迟预算 |
| 小型 Small   | < 30M    | MCU / 手机端 CPU / 浏览器 WASM | < 100ms，可 16kHz 流式 |
| 中型 Medium  | 30M–500M | 手机端 GPU/NPU、桌面 CPU、边缘盒子 | 100ms–1s，近实时 |
| 大型 Large   | > 500M   | 服务端 GPU，或端侧仅量化后可用 | > 1s，批量 |
边界值取左闭右开（30M 归中型，500M 归大型）。

## 跨切标记
- edge: 端侧可部署 —— 需给出 runtime（TFLite/ONNX/CoreML/NCNN/MNN/RKNN/QNN）+ 量化方式 + 实测或引用的 RTF/内存。只写"理论上可以"不算。
- multimodal: 多模态 —— 需写明模态组合（A=音频, T=文本, V=视觉）与融合方式。

## 指标
- WAR/WA（加权准确率）、UAR/UA（未加权平均召回）、macro-F1
- CCC（一致性相关系数）用于 valence/arousal/dominance 维度
- RTF（实时率）、峰值 RSS、模型体积 MB、功耗 mW
每个指标值后必须跟基准数据集名。

## 记录 schema（每个模型一行，列名逐字照抄）
| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
```

- [ ] **Step 2: 写校验器**

`scripts/check_ser_table.py`：解析传入 markdown 里所有以 `| 模型 |` 开头的数据表，逐行检查：
（a）12 列齐全；（b）`参数量(M)` 是数字或 `n/a(非神经)`；（c）`来源` 含 `arxiv.org` / `huggingface.co` / `github.com` 之一；（d）`许可` 非空；（e）`指标` 含括号基准名；（f）全文无 `TBD` / `待补` / `TODO` / `?` 单独成格。
任一失败 → 打印 `file:line` 与非零退出。带 `--selftest` 时用内联样例表跑一遍正反例。

- [ ] **Step 3: 跑自检**

Run: `python scripts/check_ser_table.py --selftest`
Expected: PASS（正例通过、反例每条都被拦下）

- [ ] **Step 4: 建立"候选池"清单**

在 `00-taxonomy-and-metrics.md` 末尾加一节 `## 候选池（起点线索，逐条核实后方可入表）`，把 Task 2–4 要查的模型名先列出来，每个后面跟 `[待核实]`。起点线索至少包含：

小型线：YAMNet、OpenSMILE+ComParE、TRILLsson/FRILL、DistilHuBERT、ECAPA-TDNN(小配置)、MobileNetV3/EfficientNet-B0 + log-mel、whisper-tiny、Moonshine-tiny、LEAF+小CNN
中型线：wav2vec2-base、HuBERT-base、WavLM-base+、UniSpeech-SAT、AST-base、PANNs-CNN14、emotion2vec(base/plus)、whisper-small、SenseVoice-Small、MMS-300M、data2vec-base
大型线：whisper-large-v3、wav2vec2/HuBERT/WavLM-large、MMS-1B、emotion2vec-plus-large、Qwen2-Audio-7B、SALMONN、LTU、Audio-Flamingo、Emotion-LLaMA、AffectGPT

- [ ] **Step 5: Commit**

```bash
git add docs/research/speech-emotion/00-taxonomy-and-metrics.md scripts/check_ser_table.py
git commit -m "docs(speech-emotion): taxonomy, metrics schema and table validator"
```

---

### Task 2: 小型模型（< 30M）

**Files:**
- Create: `docs/research/speech-emotion/01-small-models.md`
- Test: `python scripts/check_ser_table.py docs/research/speech-emotion/01-small-models.md`

**Interfaces:**
- Consumes: Task 1 的 schema 与 `check_ser_table.py <file.md>`。
- Produces: `01-small-models.md` 中的表格，供 Task 5（端侧）与 Task 7（汇总）读取。

- [ ] **Step 1: 检索**

以 Task 1 候选池的小型线为起点，逐条 WebSearch / arXiv 检索，核实参数量、预训练语料、报告指标与许可。额外补检索关键词：`tiny speech emotion recognition`、`lightweight SER edge`、`keyword spotting style emotion`、`streaming emotion recognition`、`量化 语音情感`。

- [ ] **Step 2: 建表**

按 schema 写入 `01-small-models.md`，**不少于 12 条**记录。每条必须含：参数量、是否在公开基准上报告过 UAR/WA、许可、权重可下载链接。

- [ ] **Step 3: 写"小型档的代价"小节**

用实测/引用的数字说明小模型在哪些基准上掉了多少（例如相对中型档 UAR 差多少点），并指出哪些任务（细粒度情绪、讽刺/反语）小模型结构性做不了。

- [ ] **Step 4: 跑校验器**

Run: `python scripts/check_ser_table.py docs/research/speech-emotion/01-small-models.md`
Expected: 0 条违规；若某条查不到来源 → 删掉该条重跑。

- [ ] **Step 5: Commit**

```bash
git add docs/research/speech-emotion/01-small-models.md
git commit -m "docs(speech-emotion): small SER models (<30M)"
```

---

### Task 3: 中型模型（30M–500M）

**Files:**
- Create: `docs/research/speech-emotion/02-medium-models.md`
- Test: `python scripts/check_ser_table.py docs/research/speech-emotion/02-medium-models.md`

**Interfaces:**
- Consumes: Task 1 的 schema 与校验器。
- Produces: 中型档表格，供 Task 5/6/7 引用。

- [ ] **Step 1: 检索**

核实候选池中型线，重点确认 `emotion2vec` 各版本的**精确参数量与许可**（该项目有 base / large / plus 多个变体，口径容易错，必须逐版本核对来源）。补检索：`SUPERB ER benchmark`、`wav2vec2 emotion fine-tuning UAR IEMOCAP`、`UniSpeech-SAT SER`。

- [ ] **Step 2: 建表（不少于 12 条）**

- [ ] **Step 3: 写"中型档为什么是主力"小节**

给出中型档在 IEMOCAP / MELD / RAVDESS 上的典型 UAR 区间，并与 Task 2 的小型档数字做**同基准**对比（不同基准的数字不许直接比）。

- [ ] **Step 4: 跑校验器**

Run: `python scripts/check_ser_table.py docs/research/speech-emotion/02-medium-models.md`
Expected: 0 条违规。

- [ ] **Step 5: Commit**

```bash
git add docs/research/speech-emotion/02-medium-models.md
git commit -m "docs(speech-emotion): medium SER models (30M-500M)"
```

---

### Task 4: 大型模型（> 500M，含语音大模型 / LLM 路线）

**Files:**
- Create: `docs/research/speech-emotion/03-large-models.md`
- Test: `python scripts/check_ser_table.py docs/research/speech-emotion/03-large-models.md`

**Interfaces:**
- Consumes: Task 1 的 schema 与校验器。
- Produces: 大型档表格，供 Task 6（多模态，很多大型模型同时是多模态）与 Task 7 引用。

- [ ] **Step 1: 检索**

核实候选池大型线，补检索：`speech emotion large language model`、`audio LLM emotion reasoning`、`Qwen2-Audio emotion`、`SALMONN emotion`、`emotion2vec+LLM`。注意区分**纯音频大模型**与**ASR+LLM 两段式**（后者先转写再让 LLM 判情绪，延迟与成本结构完全不同，要在备注列写明）。

- [ ] **Step 2: 建表（不少于 10 条）**

对 API-only 的商业模型（GPT-4o / Gemini 一类），许可列写 `proprietary API`，并标注**不可端侧、不可离线**。

- [ ] **Step 3: 写"大模型的收益与代价"小节**

必须回答三个问题，都要有数字或引用：大模型在**细粒度/上下文依赖**情绪上比中型强多少；推理延迟与显存代价；以及**幻觉风险**（把不存在的情绪强加给一段中性语音）——这条要在落地建议里被引用。

- [ ] **Step 4: 跑校验器**

Run: `python scripts/check_ser_table.py docs/research/speech-emotion/03-large-models.md`
Expected: 0 条违规。

- [ ] **Step 5: Commit**

```bash
git add docs/research/speech-emotion/03-large-models.md
git commit -m "docs(speech-emotion): large SER models and speech-LLM route"
```

---

### Task 5: 跨切轴一 —— 端侧部署（与 laos 现状对齐）

**Files:**
- Create: `docs/research/speech-emotion/04-edge-deployment.md`
- Modify: `docs/research/speech-emotion/01-small-models.md`（回填 `edge` 列）、`02-medium-models.md`（回填 `edge` 列）
- Reference: `docs/research/qnn-real-device-runbook.md`、`docs/research/2026-09-09-qnn-real-os-integration.md`

**Interfaces:**
- Consumes: Task 2/3 的表格（回填 `edge` 列）、laos 既有的 QNN 真机 runbook 与功耗调研。
- Produces: 端侧可行性结论，供 Task 7 与 Task 8 选型使用。

- [ ] **Step 1: 检索 runtime 与量化证据**

覆盖：TFLite / TFLite Micro、ONNX Runtime Mobile、CoreML、NCNN、MNN、RKNN、**QNN（Qualcomm AI Engine Direct，与 laos 现状直接相关）**。每个记录：支持的算子覆盖、INT8/INT4 量化路径、是否有公开的 SER 模型转换案例。

- [ ] **Step 2: 写"端侧预算表"**

给出目标值并注明来源：RTF 目标（流式 ≤ 0.1）、峰值内存档位、模型体积档位、功耗 mW 档位——功耗数字要**对齐** `docs/research/always-on-recording/hardware-power.md` 里已经建立好的量级阶梯，不要另起一套。

- [ ] **Step 3: 写"proot 现状"这一节（关键，别跳过）**

明确写入既有结论：当前 proot Ubuntu + Termux 架构下**拿不到 aDSP 的 <5mW**，Python 只能消费 AP 层音频流，功耗落在"通用 Linux 空闲 400–1000mW"档。因此"端侧可行"在 HY4 语境下要分两档写：**真端侧（原生 App / aDSP）** vs **proot 内可行（CPU 推理，功耗按通用 Linux 计）**。

- [ ] **Step 4: 回填 edge 列**

对 Task 2/3 表里每条给出 `edge` 值：`yes: <runtime+量化>` / `no` / `unknown(未找到公开转换案例)`。

- [ ] **Step 5: 跑校验器并 Commit**

Run: `python scripts/check_ser_table.py docs/research/speech-emotion/01-small-models.md 02-medium-models.md`
Expected: 0 条违规（`unknown(未找到公开转换案例)` 是合法值，不算 TBD）。

```bash
git add docs/research/speech-emotion/04-edge-deployment.md 01-small-models.md 02-medium-models.md
git commit -m "docs(speech-emotion): edge deployment axis with proot reality check"
```

---

### Task 6: 跨切轴二 —— 多模态情感识别

**Files:**
- Create: `docs/research/speech-emotion/05-multimodal.md`
- Modify: `docs/research/speech-emotion/03-large-models.md`（回填 `模态` 列的精确组合）

**Interfaces:**
- Consumes: Task 4 的大型表（多模态大量集中在此）。
- Produces: 多模态结论，供 Task 7 交叉分析。

- [ ] **Step 1: 检索模态组合与融合方式**

覆盖 A+T（音频+ASR 文本，最常见）、A+V（音视频）、A+T+V（三模态）。融合方式要分：early / late / hybrid、cross-attention、gating。检索词：`multimodal emotion recognition survey`、`audio-visual emotion AV-HuBERT`、`MER2025 multimodal`、`CH-SIMS`。

- [ ] **Step 2: 建多模态数据集表（不少于 8 条）**

每条含：语言、模态组合、规模、标注体系（类别/维度）、**许可**。必须包含中文数据集：MER2023/2024/2025、M3ED、CHEAVD、CH-SIMS。英文至少要 IEMOCAP、MELD、CMU-MOSEI、CMU-MOSI。

- [ ] **Step 3: 写"多模态的收益从哪来"小节**

用可引用的对比数字说明：相对单模态 A，加入文本模态在 UAR 上通常提升多少；在**噪声/远场**条件下视觉模态的贡献；以及多模态在**隐私问题**上的代价（视觉模态在中国法下的合规成本远高于音频，这一条直接约束 HY4 是否该引入视觉）。

- [ ] **Step 4: 跑校验器并 Commit**

Run: `python scripts/check_ser_table.py docs/research/speech-emotion/05-multimodal.md`
Expected: 0 条违规。

```bash
git add docs/research/speech-emotion/05-multimodal.md 03-large-models.md
git commit -m "docs(speech-emotion): multimodal emotion recognition axis"
```

---

### Task 7: 收敛 —— landscape + 交叉表 + HTML 全景

**Files:**
- Create: `docs/research/speech-emotion/2026-09-landscape.md`
- Create: `docs/speech-emotion-models.html`

**Interfaces:**
- Consumes: Task 1–6 的全部表格。
- Produces: 选型输入，供 Task 8 使用。

- [ ] **Step 1: 写交叉表**

`2026-09-landscape.md` 核心是一张 **规模档 × {edge, multimodal}** 的交叉表，每格给出：模型数量、代表模型、典型 UAR 区间、典型延迟/内存。再补一张"按场景推荐"表：常驻低功耗 / 近实时日记 / 事后批量分析，各推荐哪一档。

- [ ] **Step 2: 写"选型决策树"**

输入是部署约束（能不能出端、有没有 NPU、要不要实时、允不允许联网），输出是推荐的档位与具体模型。每一步都写清判据。

- [ ] **Step 3: 生成 HTML 全景**

`docs/speech-emotion-models.html`：深色单文件、零外部依赖、sticky 导航，沿用 `docs/always-on-recording.html` 的结构（SVG 图 + 表 + 分节）。至少含：3×2 交叉矩阵图、三档参数量/延迟对比表、多模态数据集表、端侧 runtime 对比表。

- [ ] **Step 4: 跑全量校验器**

Run: `python scripts/check_ser_table.py docs/research/speech-emotion/*.md`
Expected: 0 条违规，并打印总记录数（应 ≥ 42）。

- [ ] **Step 5: Commit**

```bash
git add docs/research/speech-emotion/2026-09-landscape.md docs/speech-emotion-models.html
git commit -m "docs(speech-emotion): landscape synthesis and HTML panorama"
```

---

### Task 8: 落地 —— 接回 AlwaysOnRec-HY4 的 ear 通道

**Files:**
- Modify: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4\aor\drivers\ear.py`（新增通道分支）
- Modify: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4\README.md`（补选型理由）
- Create: `docs/research/speech-emotion/06-adoption.md`
- Test: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4` 下 `python -m unittest discover -s tests -t .`（必须仍全绿，147 个）

**Interfaces:**
- Consumes: `AOR_ASR_CHANNEL`（`stub` / `funasr` / `server`，定义于 `aor/drivers/ear.py` 的 `channel()`）、`classify_mood(dbfs, dur_ms)`、Task 7 的选型结论。
- Produces: 一条新的情绪通道，与既有"粗粒度唤醒度"标签的边界划分。

- [ ] **Step 1: 写落地建议**

`06-adoption.md` 必须回答：

1. 在 proot Ubuntu 现状下（Task 5 的结论），哪几款模型是**当下真能跑**的；
2. 情绪通道与现有 `classify_mood()` 的**职责边界**——现有函数只输出"高唤醒/平稳/低唤醒/短促"，新通道是否替换它，还是作为 `emotions` 字段的补充来源；
3. **不做什么**：写死三条——不引入说话人识别（红线 1）、不输出临床结论（红线 2）、多模态里的**视觉模态不进 HY4**（隐私成本，见 Task 6）。

- [ ] **Step 2: 改 ear.py 加通道分支**

在 `channel()` 已支持的三值之外按选型结论新增一个分支（具体名字由 Task 7 结论决定，不得凭空命名），保持惰性导入与缺依赖静默降级到 `stub` 的既有行为。

```python
def channel() -> str:
    return os.environ.get("AOR_ASR_CHANNEL") or os.environ.get("LAOS_ASR_CHANNEL") \
        or DEFAULT_CHANNEL
```

- [ ] **Step 3: 跑 HY4 全量测试（跨仓库）**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4 && python -m unittest discover -s tests -t .`
Expected: 147 tests OK；新增分支不得让既有测试变红（缺依赖时走降级路径）。

- [ ] **Step 4: 分别 Commit（两个仓库）**

```bash
# laos 仓库
git add docs/research/speech-emotion/06-adoption.md
git commit -m "docs(speech-emotion): adoption plan for AlwaysOnRec-HY4 ear channel"

# AlwaysOnRec-HY4 仓库
cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4
git add aor/drivers/ear.py README.md
git commit -m "feat(ear): <channel-name> emotion channel behind AOR_ASR_CHANNEL"
```

- [ ] **Step 5: 回写索引**

在 `docs/research/speech-emotion/` 下确认 6 篇 + landscape 齐备，并在 `docs/research/always-on-recording/` 的 landscape 里加一行交叉引用（情感模型选型不是独立话题，它是"原音频即焚 → 只留文本与情绪"这条链路的一环）。

---

## 验收清单（全部完成后）

- [ ] `python scripts/check_ser_table.py docs/research/speech-emotion/*.md` 零违规，总记录 ≥ 42
- [ ] 三档各有独立文件，且分档边界按 Task 1 的左闭右开执行（30M 归中型、500M 归大型）
- [ ] 每条记录都有可核验来源；查不到来源的条目已从表中删除
- [ ] 中文基准（MER2023/2024/2025、M3ED、CHEAVD、CASIA）至少覆盖 2 个
- [ ] `edge` 列区分了"真端侧"与"proot 内可行"，并写了 proot 拿不到 aDSP 功耗的现实
- [ ] 多模态表覆盖了 A+T / A+V / A+T+V 三种组合，且明确写了视觉模态的隐私代价
- [ ] 落地建议显式写了"不做什么"三条（不存声纹 / 非临床 / 不引视觉模态）
- [ ] `AlwaysOnRec-HY4` 测试仍 147 全绿
- [ ] 每个 Task 一个 commit（共 8 个，laos 仓库 7 个 + HY4 仓库 1 个）

## 自检记录（写完即核）

- **Spec 覆盖**：用户 5 类划分 → Task 2/3/4（规模三档）+ Task 5（端侧）+ Task 6（多模态），并按 Scope Check 重构为 3×2；Global Constraints 9 条在 Task 1（3/4/5/6）、Task 5（1/2 的功耗口径）、Task 8（1/2/8）分别有落点。
- **占位符扫描**：无 `TBD` / `待补` / `TODO`；校验器会把它们判为违规；候选池的 `[待核实]` 是**输入线索**标记，不是产出占位，且必须在入表时消除。
- **类型/命名一致**：`check_ser_table.py <file.md>` 在 Task 1–8 中逐字一致；表格 12 列名在 Task 1 定义后不再改写；`AOR_ASR_CHANNEL`、`channel()`、`classify_mood()` 与 HY4 现有代码逐字一致。
- **既有接口不破坏**：`channel()` 新增分支带默认值，既有 `stub`/`funasr`/`server` 行为不变；HY4 既有 147 测试必须保持通过。
