# 音频事件识别模型调研（Audio Event Detection Landscape）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 摸清音频事件识别（AED / SED / ASC / 开放词表）模型全景，按**规模**（小型 / 中型 / 大型）分档，并标出每条记录的**端侧可部署**与**多模态**两个跨切标签，最终回答一个具体问题：**laos 四段漏斗的第一段「常驻检测」能否从 VAD 能量门升级为事件级检测，代价多大，值不值。**

**Architecture:** 调研型计划，不是代码型计划。产出是 `docs/research/audio-events/` 下 8 个 markdown + 1 个 HTML 全景；"测试"不是一个 pytest，而是 `scripts/check_aed_table.py`——解析 markdown 表格并强制每条记录都带可核验来源、参数量、许可、指标的校验器。先立口径与任务类型划分（Task 1），再分三条规模线收录（Task 2/3/4），再补两个跨切轴（Task 5/6），最后收敛（Task 7）并落地（Task 8）。

**Tech Stack:** Python 3 stdlib（`scripts/table_lint.py` 通用核心 + `scripts/check_aed_table.py` 薄 CLI）、WebSearch / WebFetch、arXiv API、`docs/` 下零依赖单文件 HTML（沿用 `docs/always-on-recording.html` 的深色单文件风格）。

**Spec:** 本次对话的用户需求（5 类划分，已按 Scope Check 重构为 3 档 × 2 标记）+ `docs/research/2026-09-11-aed-agc-model-landscape.md`（既有速览版，作**输入素材**）+ `docs/research/speech-emotion/` 已建立的口径惯例。

**与 SER 计划的关系（"同理"的具体所指）：** 沿用 `docs/superpowers/plans/2026-09-11-speech-emotion-models.md` 的骨架——00 定口径、01/02/03 分档、04/05 跨切轴、机器校验器、landscape + HTML、落地篇。三项适配见下方 Scope Check 与 Task 1。

---

## Scope Check（为什么是 3 档 × 2 标记）

用户原始划分是「支持端侧部署 / 多模态 / 大型 / 中型 / 小型」五类并列，与 SER 请求同构，同因同解：

- **规模**（小型 / 中型 / 大型）是互斥分档，一个模型只能落一档；
- **端侧可部署**是能力标记，与规模相关但不等价；
- **多模态**是输入模态标记，与规模正交。

按 5 类平行收录会让同一模型在多个文件各写一遍、指标口径打架。因此：**3 档定主键 + 2 个布尔标记**，交叉结论在 Task 7 出。

### 相对 SER 计划的三项适配

1. **多一个主键维度：任务类型。** AED 不是一个任务，至少是四个：多标签 tagging（AudioSet）、SED（含起止时间定位）、ASC（场景分类，独占一类）、开放词表/零样本。**跨任务类型的指标不可比**（mAP ≠ PSDS ≠ 准确率）。因此 `输出` 列必须写明任务类型，且 Task 1 要给出一张「任务类型 × 主指标」的映射表，跨档对比一律在同任务类型内进行。
2. **基准口径必须区分数据规模。** AudioSet 有 AS-20K 与 AS-2M(full) 两个常用划分，同一模型在两者上 mAP 差距可达 15+ 点（AS-20K 上 0.3+ 属常见，AS-2M full 上 0.50 已是 SOTA）。`基准` 列必须写清是哪一个。这是 AED 独有且最容易抄错的点。
3. **中文场景大概率是空白。** SER 有 MER2023/2024/2025、M3ED、CHEAVD 等中文基准；AED 领域**没有同等的中文数据集**。要求在 Task 7 如实记录这个空白及其后果（AudioSet 源自英文 YouTube，中文家庭环境事件分布不同），**不得用英文基准的结论冒充中文可用性**。

---

## Global Constraints

1. **每条记录必须可核验。** `来源` 列必须有 arXiv ID / HuggingFace repo / GitHub 链接之一。查不到就**删除该条**，不留"待补"。由校验器强制执行。
2. **许可必须记录。** 权重许可与数据集许可都写，商用受限（NC、自定义研究用途）要标出。AudioSet 特殊：本体与标签 CC-BY，但**音频本体是 YouTube 视频且官方已停止分发完整包**，实际使用多为第三方镜像或预计算 embedding——这一现实必须写明，不能只抄一句 "CC-BY"。
3. **参数量统一口径。** 单位 M = 10^6，量化前，含音频编码器。非神经方法写 `n/a(非神经)`。
4. **计算量必须同时记录。** AED 的端侧约束同时是参数量与 MACs 双约束——DCASE Low-Complexity ASC 的硬指标是 **128K 参数 / 30 MMACs**，只看参数量会误判。凡涉及端侧的记录，`指标` 列要带 MMACs 或等效计算量。
5. **指标必须带基准名与任务类型。** 写法如 `mAP 0.502 (AudioSet AS-2M full, tagging)`、`PSDS1 0.422 (DESED, SED)`、`61.47% (DCASE2025 Task1, ASC)`。不写裸数字。
6. **不同任务类型、不同数据规模的指标不许直接比。** 跨档对比必须同基准同任务，否则正文明说"不可直接比较"。
7. **不改动 `scripts/check_ser_table.py`。** SER 表已定稿并被 Task 7 依赖。AED 的校验器复用 Task 1 新建的 `scripts/table_lint.py` 通用核心，另建薄 CLI。
8. **既有速览版不删除。** `docs/research/2026-09-11-aed-agc-model-landscape.md` 作为输入素材保留（它的 🔶 未核实标记在 Task 1 被提取为核实清单），仅在 Task 8 给其头部加一行指向新目录的指针。
9. **零第三方依赖交付。** HTML 全景单文件深色风格，不引外部 CDN。
10. **落地要能接回 `AlwaysOnRec-HY4`。** 跨仓库路径 `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4`。选型结论必须说明接进来要动哪个文件——候选点是 `aor/drivers/ear.py` 的常驻检测段（当前是 VAD 能量门），但**具体改动点由 Task 7 结论决定，不得凭空命名**。

---

### Task 1: 定口径 —— 任务类型、规模分档、指标体系、schema 与校验器

**Files:**
- Create: `docs/research/audio-events/00-taxonomy-and-metrics.md`
- Create: `scripts/table_lint.py`（通用核心）
- Create: `scripts/check_aed_table.py`（薄 CLI）
- Test: `python scripts/check_aed_table.py --selftest`

**Interfaces:**
- Consumes: `docs/research/2026-09-11-aed-agc-model-landscape.md`（速览版，提取 🔶 核实清单）、`docs/research/speech-emotion/00-taxonomy-and-metrics.md`（口径惯例）、`scripts/check_ser_table.py`（要复用的检查逻辑，只读）。
- Produces: AED 表格 schema（后续所有 Task 共用）、`check_aed_table.py <file.md>` 校验器、任务类型映射表、规模分档边界常量。

- [ ] **Step 1: 写任务类型 × 主指标映射表与分档定义**

`docs/research/audio-events/00-taxonomy-and-metrics.md` 骨架（直接落盘，不留空）：

```
# 口径：任务类型 / 规模分档 / 指标 / 记录 schema
# 本文件是 docs/research/audio-events/ 下所有文件的唯一口径来源。

## 任务类型（AED 不是单一任务）
| 类型 | 说明 | 主指标 | 代表基准 |
| 多标签 tagging | 片段级多标签，无时间定位 | mAP（+ d'、lωlrap） | AudioSet |
| SED | 含起止时间的事件检测 | PSDS1/PSDS2、事件级 F1、ER | DESED / DCASE Task4 |
| ASC | 场景分类，独占一类，不是事件 | 准确率 | DCASE Task1（TAU Urban） |
| 开放词表 / 零样本 | 类别集在推理时给定 | 零样本 mAP、PSDS | AudioSet / DESED |

## AudioSet 基准口径（易错，必须区分）
| 划分 | 规模 | 说明 |
| AS-20K | 20K 片段 | 小子集，mAP 普遍偏高 |
| AS-2M full | ~200 万片段 | 全量；0.50 mAP 已是 SOTA |
数字一律标注用了哪个划分；未标注的不得入表。

## 规模分档（量化前，含音频编码器；左闭右开）
| 档 | 参数量 | 典型部署位 | 典型延迟预算 |
| 小型 Small  | < 30M    | MCU / 手机端 CPU / 浏览器 WASM | < 100ms，可流式 |
| 中型 Medium | 30M–500M | 手机端 GPU/NPU、桌面 CPU、边缘盒子 | 100ms–1s，近实时 |
| 大型 Large  | > 500M   | 服务端 GPU，或端侧仅量化后可用 | > 1s，批量 |
30M 归中型，500M 归大型。

## 跨切标记
- edge: yes: <runtime+量化> / no / unknown(未找到公开转换案例)
  runtime 覆盖 TFLite / TFLite Micro、ONNX Runtime Mobile、CoreML、NCNN、MNN、RKNN、QNN
  （QNN 与 laos 现状直接相关，见 docs/research/qnn-real-device-runbook.md）
  「yes」在本仓库还要再分一层：A 档·真端侧（原生 App / aDSP / Sensing Hub / 手机 NPU）
  vs B 档·proot 内（CPU 推理，功耗按通用 Linux 400–1000mW 计，拿不到 aDSP 的 mW 档）——
  见 05-edge-deployment.md
- 模态: A / A+V / A+T / A+T+V（细则见"口径裁定"节）
```

- [ ] **Step 2: 就"开放词表提示算不算模态"作出初始裁定并写入文件**

按 SER 的裁定 3（"模态列记推理时的输入通道"）精神延伸，在 `00` 的「口径裁定」节写入：

| 情形 | 记法 | 理由 |
|---|---|---|
| 固定 system/instruction prompt | `A` | 不携带事件信息，随输入不变 |
| 开放词表的**类别名集合**由调用方在推理时给定 | `A+T` | 类别集决定输出空间，且随调用变化 |
| 检索式/查询式 SED（query text 逐次变化） | `A+T` | 同上，文本是真实输入 |

执行时若找到反证（如某论文明确说明类别提示只作权重调制而非输入通道），**可以推翻此裁定，但必须在裁定记录里写明证据与出处**，不得静默改写。

- [ ] **Step 3: 写通用校验核心 `scripts/table_lint.py`**

从 `scripts/check_ser_table.py` 抽出与领域无关的部分，作为可复用模块，**不修改** `check_ser_table.py` 本身：

```python
# scripts/table_lint.py —— 与领域无关的 markdown 数据表校验核心
COLUMNS: list[str]          # 由各领域 CLI 覆写
NCOL = len(COLUMNS)
MIN_SCHEMA_COLS = 10        # 列数少于此值的「模型」开头表格视作对照表，跳过
PLACEHOLDERS = {"tbd", "待补", "todo", "?"}
NON_NEURAL = "n/a(非神经)"
SOURCE_HOSTS = ("arxiv.org", "huggingface.co", "github.com")

def split_row(line) -> list[str]
def is_separator(cells) -> bool
def check_text(text, columns, path, extra_rules=()) -> list[Violation]
def check_file(path, columns, extra_rules=()) -> list[Violation]
def run_cli(argv, columns, selftest_fn, description) -> int
```

`check_text` 六条通用规则（与 SER 逐条对齐）：
（a）列数 == NCOL；（b）`参数量(M)` 是数字或 `n/a(非神经)`；（c）`来源` 含三个域名之一；（d）`许可` 非空；（e）`指标` 含带基准名的括号；（f）单元格不得为占位符。

`extra_rules` 是 `Callable[[dict[str,str], int], list[Violation]]` 的序列，供各领域挂专属规则。

- [ ] **Step 4: 写 AED 薄 CLI `scripts/check_aed_table.py`**

```python
COLUMNS = ["模型", "版本/权重", "参数量(M)", "模态", "预训练语料", "输出",
           "基准", "指标", "许可", "权重可得", "edge", "来源"]
```

列名与 SER **逐字一致**（AED 与 SER 同属声学模型，`输出` 列由"类别体系"改为"任务类型+类别数"，填写规则在 `00` 里改，列名不动）。挂载一条专属规则：

- **规则 g（任务类型）**：`输出` 列必须含 `tagging` / `SED` / `ASC` / `开放词表` 之一，否则报 `task-type`。
- **规则 h（AudioSet 划分）**：`基准` 列出现 `AudioSet` 时，必须同时出现 `AS-20K` / `AS-2M` / `AS-2M full` / `full` 之一，否则报 `audioset-split`。

`--selftest` 覆盖：正例通过；反例命中 `params`/`source`/`license`/`metric`/`placeholder`/`task-type`/`audioset-split` 七类；非目标表（数据集表）不被误伤；以「模型」开头但列数远少于 schema 的对照表不被误伤；schema 表头缺列被检出。

- [ ] **Step 5: 跑自检**

Run: `python scripts/check_aed_table.py --selftest`
Expected: PASS，七类反例全部命中、三类误伤检查通过。

- [ ] **Step 6: 建候选池，并提取速览版的 🔶 核实清单**

在 `00` 末尾加两节：

`## 候选池（起点线索，逐条核实后方可入表）` —— 每个名字后跟 `[待核实]`：

小型线：YAMNet、MobileNetV3 + log-mel、EfficientNet-B0、BC-ResNet-1/3、PANNs-CNN6/CNN10、CP-Mobile、DCASE2025 Task1 冠军系统（约 122K 参数 / 29.4 MMACs）、DCASE2023/2024 Low-Complexity ASC 前序系统、FRILL/TRILLsson、LEAF + 小 CNN、MicroNets（MCU NAS）

中型线：PANNs-CNN14、AST-base、HTS-AT、PaSST、BEATs（iter3 / iter3+）、CED、SSLAM、ATST、M2D、EAT、AudioMAE、MAE-AST、Whisper-AT、Dasheng-Base

大型线：Dasheng-0.6B / 1.2B、AudioFlamingo / AudioFlamingo-2、Qwen2-Audio-7B、SALMONN-7B/13B、LTU / LTU-AS、Pengi、APE、MiDashengLM-7B、Qwen2.5-Omni-7B、Uniaudio、Kimi-Audio

多模态线：CLAP（LAION）、AudioCLIP、Wav2CLIP、ImageBind、LanguageBind、VATT、DASM（开放词表 SED，arXiv 2507.16343）

`## 速览版核实清单` —— 逐个列出 `docs/research/2026-09-11-aed-agc-model-landscape.md` 中带 🔶 未核实标记的断言（至少覆盖 §2.1–§2.5 与 §7 的 AED 部分），每条后跟 `[待核实]`，注明其在速览版中的小节号。这一节是 Task 2–6 的**必查项**，不是可选项。

- [ ] **Step 7: Commit**

```bash
git add docs/research/audio-events/00-taxonomy-and-metrics.md scripts/table_lint.py scripts/check_aed_table.py
git commit -m "docs(audio-events): task-type taxonomy, metrics schema and table validator"
```

---

### Task 2: 小型模型（< 30M）

**Files:**
- Create: `docs/research/audio-events/01-small-models.md`
- Test: `python scripts/check_aed_table.py docs/research/audio-events/01-small-models.md`

**Interfaces:**
- Consumes: Task 1 的 schema、校验器、候选池小型线、速览版核实清单的 §2.2/§2.1 部分。
- Produces: 小型档表格，供 Task 5（端侧）与 Task 7（汇总）读取。

- [ ] **Step 1: 检索**

逐条核实候选池小型线。补检索关键词：`low-complexity acoustic scene classification`、`DCASE2025 task1`、`tiny audio event detection MCU`、`keyword-sized sound event detection`、`sub-100k parameter audio tagging`、`MMACs audio tagging`。

- [ ] **Step 2: 建表（不少于 12 条）**

每条必须含：参数量、**MMACs 或等效计算量**（有则必填）、任务类型、基准、指标、许可、权重链接。DCASE Low-Complexity ASC 系列**必须收录**，因为它是唯一带硬约束（128K 参数 / 30 MMACs）的公开赛道，是端侧档的事实标准。

- [ ] **Step 3: 写"128K 参数约束下能做什么"小节**

必须回答：在 DCASE 硬约束下，ASC 准确率从哪一年到哪一年提升到了多少；这个约束下的模型能否迁移到 tagging/SED（ASC 是独占单类，tagging 是多标签，不能直接套）；以及**参数量与 MMACs 哪个才是真瓶颈**（给出引用或自己的推导，推导要写明假设）。

- [ ] **Step 4: 跑校验器**

Run: `python scripts/check_aed_table.py docs/research/audio-events/01-small-models.md`
Expected: 0 条违规；查不到来源的条目删掉重跑。

- [ ] **Step 5: Commit**

```bash
git add docs/research/audio-events/01-small-models.md
git commit -m "docs(audio-events): small AED models under the 128K/30-MMACs constraint"
```

---

### Task 3: 中型模型（30M–500M）

**Files:**
- Create: `docs/research/audio-events/02-medium-models.md`
- Test: `python scripts/check_aed_table.py docs/research/audio-events/02-medium-models.md`

**Interfaces:**
- Consumes: Task 1 的 schema 与校验器。
- Produces: 中型档表格，供 Task 5/6/7 引用。

- [ ] **Step 1: 检索**

核实候选池中型线，重点是 **AudioSet AS-2M full 上的 mAP 排序**（这是唯一能横向比较的口径）。补检索：`AudioSet AS-2M full mAP state of the art`、`audio tagging transformer benchmark`、`BEATs CED SSLAM comparison`、`PANNs vs AST vs PaSST mAP`。

已知待核实的起点线索（速览版与检索交叉所得，均须独立核实后方可入表）：SSLAM 88M 约 50.2 mAP、CED 86M 约 50.0 mAP、SPEARs+a XLarge 约 50.0 mAP、BEATs iter3+ 约 48.6 mAP——**这四个数字都要找到出处，找不到就删**。

- [ ] **Step 2: 建表（不少于 12 条）**

必须区分 AS-20K 与 AS-2M full，同一模型若两处都有报告，优先记 full 并在备注里带 20K 值。

- [ ] **Step 3: 写"中型档是 AED 的精度甜点"小节**

给出中型档在 AS-2M full 上的 mAP 区间，并与 Task 2 小型档做**同基准同任务**对比（如 YAMNet 0.306 vs 中型档 0.45–0.50，都要核实）。同时说明代价：参数量涨 20 倍、MMACs 涨多少、能否实时。

- [ ] **Step 4: 跑校验器**

Run: `python scripts/check_aed_table.py docs/research/audio-events/02-medium-models.md`
Expected: 0 条违规。

- [ ] **Step 5: Commit**

```bash
git add docs/research/audio-events/02-medium-models.md
git commit -m "docs(audio-events): medium AED models on AudioSet AS-2M full"
```

---

### Task 4: 大型模型（> 500M，含音频大模型路线）

**Files:**
- Create: `docs/research/audio-events/03-large-models.md`
- Test: `python scripts/check_aed_table.py docs/research/audio-events/03-large-models.md`

**Interfaces:**
- Consumes: Task 1 的 schema 与校验器。
- Produces: 大型档表格，供 Task 6（多模态，大量大型模型同时是多模态）与 Task 7 引用。

**关键待验证假设（必须在本 Task 内给出结论，无论成立与否）：** 与 SER 篇同构——SER 的结论是"大型档几乎被语音大模型占满，纯编码器很少超过 500M"。AED 的对应假设是：**音频大模型（audio LLM）在 AudioSet tagging 这类判别任务上明显不如同代专用编码器**。检索得到的初始证据倾向支持：paperswithcode AudioSet 榜上 SSLAM(88M) 约 50.2 mAP 居首，而 MiDashengLM-7B 在该榜仅约 0.09 mAP。**这两个数字都要核实到原始出处**，然后明确写出：是"audio LLM 不做 tagging"还是"做了但做不好"，两者的架构含义完全不同。

- [ ] **Step 1: 检索**

核实候选池大型线。补检索：`audio LLM audio tagging benchmark`、`audio language model vs specialized audio encoder`、`open-vocabulary sound event detection LLM`、`zero-shot SED CLAP DESED PSDS`、`DASM open-vocabulary SED`。

- [ ] **Step 2: 建表（不少于 10 条）**

大型档要区分三种结构，在 `版本/权重` 列写明：
- 编码器 + 标签头（纯判别，如 Dasheng 系列加线性探测）
- 端到端音频大模型（音频编码器直连 LLM，不产生中间文本）
- 两段式（ASR/caption 模型 + LLM 判定）

API-only 商业模型：`许可` 列写 `proprietary API`，并标注不可端侧、不可离线。

- [ ] **Step 3: 写"大型档在 AED 上换了什么"小节**

必须回答三个问题，都要有数字或引用：
（a）大型档的**真正增量是不是开放词表**——固定 521 类 vs 任意类别集，在 DESED 一类的零样本/开放词表基准上，DASM 一类方法相对监督 CRNN 的 PSDS 是多少（初始线索：DESED 零样本 PSDS1 约 42.2，须核实）；
（b）**延迟与成本结构**：7B 级模型推理一段 10 秒音频的耗时/显存量级；
（c）**失败模式**：开放词表模型对"不在提示集里的真实事件"是静默漏检还是误报（这条直接决定它能不能做常驻检测）。

- [ ] **Step 4: 跑校验器**

Run: `python scripts/check_aed_table.py docs/research/audio-events/03-large-models.md`
Expected: 0 条违规。

- [ ] **Step 5: Commit**

```bash
git add docs/research/audio-events/03-large-models.md
git commit -m "docs(audio-events): large AED models and the open-vocabulary tradeoff"
```

---

### Task 5: 跨切轴一 —— 端侧部署（与 laos 现状对齐）

**Files:**
- Create: `docs/research/audio-events/05-edge-deployment.md`
- Modify: `docs/research/audio-events/01-small-models.md`（回填 `edge` 列）、`02-medium-models.md`（回填 `edge` 列）
- Reference: `docs/research/qnn-real-device-runbook.md`、`docs/research/2026-09-09-qnn-real-os-integration.md`、`docs/research/speech-emotion/04-edge-deployment.md`

**Interfaces:**
- Consumes: Task 2/3 的表格、SER 04 已建立的功耗阶梯与 proot 结论（**引用，不重算**）。
- Produces: 端侧可行性结论，供 Task 7/8 使用。

- [ ] **Step 1: 检索 runtime 与量化证据**

覆盖 TFLite / TFLite Micro、ONNX Runtime Mobile、CoreML、NCNN、MNN、RKNN、**QNN（与 laos 现状直接相关）**。每个记录：算子覆盖、INT8/INT4 量化路径、是否有公开的 AED 模型转换案例。

重点核实：DCASE Low-Complexity 赛道获奖系统是否有公开的量化/部署产物（多数只有 PyTorch 权重，这是端侧档的真实缺口）。

- [ ] **Step 2: 写"端侧预算表"**

目标值并注明来源：RTF（常驻检测要求流式 ≤ 0.1）、峰值内存、模型体积、功耗 mW、MMACs/秒。**功耗数字直接引用 SER 04 与 `docs/research/always-on-recording/` 已建立的量级阶梯**，不另起一套。

- [ ] **Step 3: 写"proot 现状"这一节（关键）**

沿用 SER 04 已确立的 A/B 两档写法并落到 AED：**A 档·真端侧**（原生 App / aDSP / Sensing Hub / 手机 NPU，mW 档）vs **B 档·proot 内**（CPU 推理，通用 Linux 空闲 400–1000 mW，拿不到 aDSP）。

必须回答的 AED 专属问题：**常驻 AED 在 B 档是否可接受**——即"持续 CPU 跑一个几 M 参数的 tagging 模型"的实测或估算功耗是多少，与"常驻 VAD 能量门"相比增量多大。给不出实测就给估算并写明假设，**不许含糊带过**，因为这一条直接决定 Task 8 的落地结论。

- [ ] **Step 4: 回填 edge 列**

对 Task 2/3 每条给出 `yes: <runtime+量化>` / `no` / `unknown(未找到公开转换案例)`，并按 A/B 两档标注。

- [ ] **Step 5: 跑校验器并 Commit**

Run: `python scripts/check_aed_table.py docs/research/audio-events/01-small-models.md 02-medium-models.md`
Expected: 0 条违规（`unknown(未找到公开转换案例)` 是合法值）。

```bash
git add docs/research/audio-events/05-edge-deployment.md 01-small-models.md 02-medium-models.md
git commit -m "docs(audio-events): edge deployment axis with proot reality check"
```

---

### Task 6: 跨切轴二 —— 多模态音频事件模型

**Files:**
- Create: `docs/research/audio-events/06-multimodal.md`
- Modify: `docs/research/audio-events/03-large-models.md`（回填 `模态` 列精确组合）

**Interfaces:**
- Consumes: Task 4 的大型表（多模态大量集中在此）、Task 1 的开放词表裁定。
- Produces: 多模态结论，供 Task 7 交叉分析。

- [ ] **Step 1: 检索模态组合**

覆盖 `A+V`（视觉辅助事件定位，如 AVE / VGGSound / LLP）、`A+T`（开放词表与检索式 SED，见 Task 1 裁定）、`A+T+V`。检索词：`audio-visual event localization`、`audio-visual sound event detection`、`CLAP zero-shot sound event detection`、`VGGSound audio visual benchmark`。

- [ ] **Step 2: 建数据集表（不少于 8 条）**

每条含：语言、模态组合、规模、标签粒度、**许可**。至少含 VGGSound、AVE、LLP、AudioSet（含视频模态但常用纯音频）、AudioCaps、Clotho、DESED、DCASE Task3（SELD，含空间信息）。

- [ ] **Step 3: 写"多模态在 AED 上换来了什么"小节**

必须回答，且要有可引用数字：
（a）`A+V` 相对纯 `A` 在**事件定位**（不只是分类）上提升多少——定位是视觉真正的增量，分类上视觉贡献通常很小；
（b）`A+T`（开放词表）相对固定词表在**未见类别**上的表现，代价是什么；
（c）**隐私代价**：视觉模态在中国法下的合规成本（个保法 §26 公共场所图像"只能用于维护公共安全的目的"、§28/29/30 人脸属敏感个人信息需单独同意、国务院令 799 号 §17 视频保存 ≥30 日——与 laos「原音频即焚」架构直接互斥）。

延续 SER 05 已给出的立场：视觉模态不进 HY4。本 Task 要在 AED 语境下**独立复核**这个结论（AED 的视觉用法与 SER 不同：SER 用视觉看表情，AED 用视觉做定位），并写出一致或推翻的理由。

- [ ] **Step 4: 跑校验器并 Commit**

Run: `python scripts/check_aed_table.py docs/research/audio-events/06-multimodal.md`
Expected: 0 条违规。

```bash
git add docs/research/audio-events/06-multimodal.md 03-large-models.md
git commit -m "docs(audio-events): multimodal axis — visual adds localization, not classification"
```

---

### Task 7: 收敛 —— landscape + 交叉表 + HTML 全景

**Files:**
- Create: `docs/research/audio-events/2026-09-landscape.md`
- Create: `docs/audio-event-models.html`

**Interfaces:**
- Consumes: Task 1–6 全部表格。
- Produces: 选型输入，供 Task 8 使用。

- [ ] **Step 1: 写交叉表**

`2026-09-landscape.md` 核心是 **规模档 × {edge, multimodal}** 交叉表，每格给：模型数量、代表模型、典型 mAP/PSDS 区间、典型 MMACs 与延迟。再补两张：
- 「任务类型 × 规模档」推荐表（tagging / SED / ASC / 开放词表各推哪一档）；
- 「按场景推荐」表（常驻低功耗 / 近实时 / 事后批量）。

- [ ] **Step 2: 写"中文场景空白"这一节（AED 特有，必须写）**

明确检索并记录：中文/中文环境音频事件数据集是否存在；若无，写明后果——AudioSet 本体来自英文 YouTube，中文家庭环境（电动车报警器、麻将、广场舞、燃气灶报警器等）分布不同，直接用会产生哪些具体失效。给出缓解手段（自采小样本微调 / 只做粗粒度事件 / 用 open-vocabulary 绕过固定词表）。**不得用英文基准结论冒充中文可用性。**

- [ ] **Step 3: 写"常驻检测升级"决策**

直接回答 Goal 里那个问题：漏斗第一段从 VAD 能量门升级为事件级检测，收益是什么（减少无效唤醒、事件级触发更准）、代价是什么（常驻功耗、误触发、误报的隐私含义）、在什么条件下值得做。给出明确的**做 / 不做 / 有条件做**结论与判定阈值。

- [ ] **Step 4: 写选型决策树**

输入是部署约束（能否出端、有无 NPU、是否实时、能否联网、事件类别是否固定），输出是推荐档位与具体模型。每步写清判据。

- [ ] **Step 5: 生成 HTML 全景**

`docs/audio-event-models.html`：深色单文件、零外部依赖、sticky 导航，沿用 `docs/always-on-recording.html` 结构。至少含：3×2 交叉矩阵图、任务类型 × 指标映射图、三档参数量/MMACs 对比表、AudioSet AS-2M full 榜单、多模态数据集表、端侧 runtime 对比表。

- [ ] **Step 6: 跑全量校验器**

Run: `python scripts/check_aed_table.py docs/research/audio-events/*.md`
Expected: 0 条违规，并打印总记录数（应 ≥ 40）。

- [ ] **Step 7: Commit**

```bash
git add docs/research/audio-events/2026-09-landscape.md docs/audio-event-models.html
git commit -m "docs(audio-events): landscape synthesis and HTML panorama"
```

---

### Task 8: 落地 —— 接回 AlwaysOnRec-HY4

**Files:**
- Create: `docs/research/audio-events/07-adoption.md`
- Modify: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4` 下由 Task 7 结论指定的文件（**不得凭空指定**）
- Modify: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4\README.md`（补选型理由）
- Test: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4` 下 `python -m unittest discover -s tests -t .`（必须仍全绿，147 个）

**Interfaces:**
- Consumes: Task 7 决策、Task 5 的 A/B 档结论、HY4 现有捕获链路代码。
- Produces: 一条 AED 通道或一份"暂不引入"的论证，二者必居其一。

- [ ] **Step 1: 先读 HY4 现状再动笔**

读 `aor/drivers/ear.py` 与捕获链路相关文件，确认三件事并写进 `07-adoption.md`：
（a）第一段常驻检测当前的实现位置与判据（VAD 能量门的参数）；
（b）AED 若接入，是**替换**能量门还是**在其后作二次确认**（推荐后者，理由写在文中：能量门零成本，AED 只处理被能量门放过的可疑片段，功耗可降一个量级）；
（c）`AOR_ASR_CHANNEL` 既有三值（`stub` / `funasr` / `server`）是否受影响，新增分支如何命名（名字由结论决定）。

- [ ] **Step 2: 写落地建议**

`07-adoption.md` 必须回答：
1. 在 proot Ubuntu 现状下（Task 5 B 档）哪几款模型**当下真能跑**，给出具体名字与环境要求；
2. AED 输出与既有"粗粒度唤醒度"标签的**职责边界**——事件标签进记忆的哪一层，保留多久；
3. **不做什么**（三条，逐条给理由）：
   - **不做全 521 类常驻输出**——只保留与已确定用途相关的事件子集，理由：长期事件序列聚合后可推断家庭结构与作息，属超范围画像；
   - **不引入视觉模态**——合规成本见 Task 6，且与即焚架构互斥；
   - **不让 AED 结果单独触发留存**——事件标签只能改变"是否蒸馏"，不能改变"是否留存原始音频"，否则即焚架构被绕过。

- [ ] **Step 3: 改 HY4 代码**

按 Task 7 结论执行。若结论是"暂不引入"，则**不改代码**，只在 `07-adoption.md` 写明触发条件；若引入，则按 Step 1 确认的位置加分支，保持惰性导入与缺依赖静默降级到 `stub` 的既有行为。

```python
def channel() -> str:
    return os.environ.get("AOR_ASR_CHANNEL") or os.environ.get("LAOS_ASR_CHANNEL") \
        or DEFAULT_CHANNEL
```

- [ ] **Step 4: 跑 HY4 全量测试（跨仓库）**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4 && python -m unittest discover -s tests -t .`
Expected: 147 tests OK；新增分支不得让既有测试变红（缺依赖时走降级路径）。

- [ ] **Step 5: 给速览版加指针（不删除）**

在 `docs/research/2026-09-11-aed-agc-model-landscape.md` 头部插入一行，指向新目录并说明其 AED 部分已被 `docs/research/audio-events/` 取代（AGC 部分另见 AGC 计划）。**保留原文**，因为它的 §7 文献跟踪仍有独立价值。

- [ ] **Step 6: 分别 Commit（两个仓库）**

```bash
# laos 仓库
git add docs/research/audio-events/07-adoption.md docs/research/2026-09-11-aed-agc-model-landscape.md
git commit -m "docs(audio-events): adoption plan and pointer from superseded landscape"

# AlwaysOnRec-HY4 仓库（仅当 Step 3 实际改了代码）
cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4
git add <Task 7 指定的文件> README.md
git commit -m "feat: AED channel per audio-events landscape decision"
```

---

## 验收清单（全部完成后）

- [ ] `python scripts/check_aed_table.py docs/research/audio-events/*.md` 零违规，总记录 ≥ 40
- [ ] 三档各有独立文件，分档边界按左闭右开执行（30M 归中型、500M 归大型）
- [ ] 每条含任务类型；跨任务类型的数字没有被互相比较
- [ ] 所有 AudioSet 数字都标注了 AS-20K 还是 AS-2M full
- [ ] 每条记录有可核验来源；查不到的已删除
- [ ] 端侧档同时记了参数量与 MMACs，DCASE 128K/30 MMACs 约束被显式讨论
- [ ] `edge` 列区分 A 档真端侧与 B 档 proot 内，并写了 B 档常驻功耗的估算与假设
- [ ] 中文场景空白一节已写，且没有用英文基准冒充中文可用性
- [ ] 多模态节独立复核了"不引视觉模态"的结论，写明一致或推翻的理由
- [ ] 落地篇显式写了"不做什么"三条
- [ ] 速览版保留且头部有指针，未被删除
- [ ] `AlwaysOnRec-HY4` 测试仍 147 全绿
- [ ] 每个 Task 一个 commit（laos 仓库 8 个 + HY4 仓库至多 1 个）
- [ ] `scripts/check_ser_table.py` 未被修改（SER 表未受影响）

## 自检记录（写完即核）

- **Spec 覆盖**：用户 5 类划分 → Task 2/3/4（规模三档）+ Task 5（端侧）+ Task 6（多模态），按 Scope Check 重构为 3×2；Global Constraints 10 条分别落在 Task 1（1/2/3/4/5/7/8）、Task 2（4）、Task 5（4 的功耗口径）、Task 6（视觉合规）、Task 7（中文空白）、Task 8（落地三条不做）。
- **占位符扫描**：无 `TBD` / `待补` / `TODO` / "Similar to Task N"。候选池与速览版核实清单里的 `[待核实]` 是**输入线索**标记，不是产出占位，入表时必须消除（校验器会拦）。Task 3 中"约 50.2 mAP"等数字以"待核实的起点线索"形式出现并明确写了"找不到就删"，属于线索而非结论。
- **类型/命名一致**：`check_aed_table.py <file.md>` 在 Task 1–8 中逐字一致；12 列名与 SER 逐字一致（只有填写规则不同）；`table_lint.py` 的函数签名在 Step 3 定义后不再改写；`AOR_ASR_CHANNEL`、`channel()` 与 HY4 现有代码逐字一致。
- **既有接口不破坏**：`check_ser_table.py` 只读不写；`channel()` 若新增分支带默认值，`stub`/`funasr`/`server` 行为不变；HY4 既有 147 测试保持通过；速览版只加指针不删内容。

---

## Execution Handoff

Plan 已写完并保存。执行方式二选一：

**1. Subagent-Driven（推荐）** —— 每个 Task 派一个子代理，两轮审查（先符合 spec、再代码质量），Task 间快速迭代。

**2. Inline Execution** —— 在当前会话按序执行，带检查点。

选哪种？
