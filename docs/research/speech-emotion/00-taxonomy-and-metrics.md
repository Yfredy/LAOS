# 口径：规模分档 / 指标 / 记录 schema

> 本文件是 `docs/research/speech-emotion/` 下所有文件的**唯一口径来源**。
> 表格 schema 由 `scripts/check_ser_table.py` 机器校验，改动前先跑
> `python scripts/check_ser_table.py --selftest`。

## 为什么是 3 档 × 2 标记，而不是 5 类平行

原始需求把语音情感模型分成「支持端侧部署 / 多模态 / 大型 / 中型 / 小型」五类，
但这五类**不在同一维度**：

- **规模**（小型 / 中型 / 大型）是**互斥分档**，一个模型只能落一档；
- **端侧可部署**是能力标记，与规模相关但不等价——7B 模型量化后也未必端侧可行，
  300M 模型也可能跑不到实时；
- **多模态**是输入模态标记，与规模**完全正交**——有多模态小模型，也有单模态大模型。

按 5 类平行收录会让同一个模型在多个文件里各写一遍，参数量与指标口径必然打架。
因此：**规模定主键，端侧与多模态作为每条记录的布尔标记**，交叉结论在
`2026-09-landscape.md` 出。

## 规模分档

按**量化前、含音频编码器**的参数量划分。边界值**左闭右开**：30M 归中型，500M 归大型。

| 档 | 参数量 | 典型部署位 | 典型延迟预算 |
|---|---|---|---|
| 小型 Small | < 30M | MCU / 手机端 CPU / 浏览器 WASM | < 100ms，可 16kHz 流式 |
| 中型 Medium | 30M–500M | 手机端 GPU/NPU、桌面 CPU、边缘盒子 | 100ms–1s，近实时 |
| 大型 Large | > 500M | 服务端 GPU，或端侧仅量化后可用 | > 1s，批量 |

口径说明（三条，写数时必须遵守）：

1. **含音频编码器**：两段式（ASR 转写 + LLM 判情绪）的系统，参数量要写**两段之和**，
   并在"版本/权重"列注明 `ASR+LLM 两段式`，否则大型档会系统性偏低估。
2. **量化前为准**：INT8/INT4 后的体积写进 `edge` 列，不改写 `参数量(M)`。
3. 纯特征工程方法（如 openSMILE + SVM）无神经参数量，写 `n/a(非神经)`。

## 跨切标记

### `edge`（端侧可部署）

合法取值：

| 值 | 含义 |
|---|---|
| `yes: <runtime>` | 有公开转换案例或官方端侧导出路径；必须带 runtime 名与量化方式，例：`yes: TFLite INT8` |
| `no` | 需要服务端 GPU，或参数量/显存明显超出端侧 |
| `unknown(未找到公开转换案例)` | 没有证据，不等于不行——这是合法值，不算 TBD |

runtime 覆盖：TFLite / TFLite Micro、ONNX Runtime Mobile、CoreML、NCNN、MNN、RKNN、
**QNN（Qualcomm AI Engine Direct，与 laos 现状直接相关）**。

**重要**：本仓库语境下 `yes` 还要再分一层，见 `04-edge-deployment.md` 的
「proot 现状」一节——在 proot Ubuntu 里能跑，不等于拿到 aDSP 的低功耗档。

### `模态`

用字母组合，不用中文描述：

- `A` = 音频（声学）
- `T` = 文本（ASR 转写稿或原始字幕）
- `V` = 视觉（人脸/表情/姿态）

例：`A`（纯声学）、`A+T`、`A+V`、`A+T+V`。

## 指标

每个指标值**后面必须跟基准数据集名**，不写裸数字：

- `WAR` / `WA`：加权准确率（weighted accuracy）
- `UAR` / `UA`：未加权平均召回（unweighted average recall）——类别不平衡时以它为准
- `macro-F1`：宏平均 F1
- `CCC`：一致性相关系数，用于 valence / arousal / dominance 维度回归
- 工程指标另记：`RTF`（实时率）、峰值 RSS、模型体积 MB、功耗 mW

写法示例：`UAR 73.4 (IEMOCAP)`、`CCC 0.62 (CMU-MOSEI valence)`。

**不同基准的数字不许直接比。** 跨档对比时必须同基准，否则在正文里明说"不同基准，不可直接比较"。

## 记录 schema（12 列，列名逐字照抄）

| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
|---|---|---|---|---|---|---|---|---|---|---|---|

各列填写规则：

| 列 | 规则 |
|---|---|
| 模型 | 官方名，不写昵称 |
| 版本/权重 | 具体 checkpoint；两段式写 `ASR+LLM 两段式` |
| 参数量(M) | 数字，或 `n/a(非神经)`；区间写 `24–95` |
| 模态 | `A` / `A+T` / `A+V` / `A+T+V` |
| 预训练语料 | 如 AudioSet、LibriSpeech、WenetSpeech；无预训练写 `-` |
| 输出 | 类别体系（如 4 类 / 6 类 / Ekman）或维度（V/A/D） |
| 基准 | 评测数据集 |
| 指标 | 必带括号基准名 |
| 许可 | 权重许可；商用受限要写明（如 `CC-BY-NC`）；API-only 写 `proprietary API` |
| 权重可得 | `yes` / `no`（仅论文无权重）/ `API only` |
| edge | 见上表三值 |
| 来源 | 必须含 `arxiv.org` / `huggingface.co` / `github.com` 之一 |

**查不到来源的条目直接删除**，不留"待补"。这一条由校验器强制执行。

## 红线（三条，所有文件通用）

1. **不存声纹。** 声纹在中国法下属敏感个人信息。带说话人识别/验证能力的模型，
   在"版本/权重"列标注 `speaker-capable`，但**不参与选型**。
2. **情绪标签非临床。** 最大规模的抑郁语音检测研究敏感度与特异度均仅 71%
   （见 `docs/research/always-on-recording/academic-papers.md`）。任何健康/临床声称
   必须标注"非诊断"，且不得进入落地推荐。
3. **中文场景必须覆盖。** 至少收录 MER2023/2024/2025、M3ED、CHEAVD、CASIA 中的两个。

---

## 候选池（起点线索，逐条核实后方可入表）

> 以下只是**检索起点**，不是结论。每条都必须经检索核实参数量/许可/指标后，
> 才能写进 `01/02/03-*.md`；核实不了的删掉。标记含义：`[待核实]` = 尚未验证。

### 小型线（Task 2）

YAMNet `[待核实]`、openSMILE + ComParE（非神经基线）`[待核实]`、TRILLsson / FRILL `[待核实]`、
DistilHuBERT `[待核实]`、ECAPA-TDNN（小配置）`[待核实]`、MobileNetV3 / EfficientNet-B0 + log-mel `[待核实]`、
whisper-tiny `[待核实]`、Moonshine-tiny `[待核实]`、LEAF + 小 CNN `[待核实]`、
TinySER 一类"蒸馏到关键词级"的工作 `[待核实]`

### 中型线（Task 3）

wav2vec2-base `[待核实]`、HuBERT-base `[待核实]`、WavLM-base+ `[待核实]`、UniSpeech-SAT `[待核实]`、
AST-base `[待核实]`、PANNs-CNN14 `[待核实]`、emotion2vec（base / plus 各版本）`[待核实]`、
whisper-small `[待核实]`、SenseVoice-Small `[待核实]`、MMS-300M `[待核实]`、data2vec-base `[待核实]`

> ⚠️ `emotion2vec` 有 base / large / plus 多个变体，参数量与许可口径容易错，
> **必须逐版本核对来源**，不许从别的表格里抄。

### 大型线（Task 4）

whisper-large-v3 `[待核实]`、wav2vec2 / HuBERT / WavLM 的 large 版本 `[待核实]`、
MMS-1B `[待核实]`、emotion2vec-plus-large `[待核实]`、Qwen2-Audio-7B `[待核实]`、
SALMONN `[待核实]`、LTU（Listen-Think-Understand）`[待核实]`、Audio-Flamingo `[待核实]`、
Emotion-LLaMA `[待核实]`、AffectGPT `[待核实]`

> 大型线要特别注意区分**纯音频大模型**与**ASR + LLM 两段式**：后者先转写再让 LLM
> 判情绪，延迟结构、成本结构、失败模式都不同，必须在"版本/权重"列写明。
