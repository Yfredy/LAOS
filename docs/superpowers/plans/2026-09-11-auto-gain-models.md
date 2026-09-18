# 自动增益模型调研（Auto Gain Control Landscape）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 摸清"自动增益"这条链路的真实构成——包括一个必须先行回答的问题：**它到底是不是一个模型问题**。目标是给出可执行的结论：laos / `AlwaysOnRec-HY4` 的捕获链路该不该加自动增益、加在哪一层、用经典 DSP 还是神经网络，以及**在什么情况下什么都不加才是对的**。

**Architecture:** 调研型计划，不是代码型计划。产出是 `docs/research/auto-gain/` 下 8 个 markdown + 1 个 HTML 全景；"测试"是 `scripts/check_agc_table.py`——解析 markdown 表格、强制每条记录带可核验来源与指标的校验器（复用 Task 1 新建的 `scripts/table_lint.py` 通用核心）。先立口径（Task 1），再按"经典 DSP 档 → 小型 → 中型 → 大型"四条线收录（Task 2–5），再补两个跨切轴（Task 6/7），最后收敛（Task 8）并落地（Task 9）。

**Tech Stack:** Python 3 stdlib（`scripts/table_lint.py` 通用核心 + `scripts/check_agc_table.py` 薄 CLI）、WebSearch / WebFetch、arXiv API、`docs/` 下零依赖单文件 HTML（沿用 `docs/always-on-recording.html` 的深色单文件风格）。

**Spec:** 本次对话的用户需求（5 类划分，已按 Scope Check 重构）+ `docs/research/2026-09-11-aed-agc-model-landscape.md`（既有速览版，作**输入素材**）+ `docs/research/speech-emotion/` 已建立的口径惯例。

---

## Scope Check

### 为什么与 AED 分成两份计划

两者只有"用户请求句式"相同，领域结构完全不同：

| | AED | AGC |
|---|---|---|
| 主力形态 | 神经网络模型 | **经典 DSP 反馈环**（WebRTC AGC2 一类） |
| 统一榜单 | 有（AudioSet mAP、DCASE） | **没有**，多数组件无公开基准 |
| 分档有效性 | 三档都有实体 | 神经模型几乎全在小型档，中/大型稀疏 |
| 多模态象限 | 有实体（A+V、A+T） | **实质为空**，需专门论证 |
| 落地形态 | 加一个推理通道 | **可能是一个开关决策，不是模型选型** |

合成一份计划会让其中一边的 Task 描述对另一边失真。因此拆开，但共用 `table_lint.py` 与同一套文档骨架。

### 为什么是「经典 DSP 档 + 3 档 × 2 标记」

用户原始划分是「支持端侧部署 / 多模态 / 大型 / 中型 / 小型」五类并列。与 SER / AED 同因同解：规模是互斥分档，端侧与多模态是正交布尔标记，5 类平行会让同一条目在多处各写一遍。

**AGC 需要一处扩展**：领域主力是**没有参数量的经典 DSP 反馈环**，它不属于任何规模档。处理方式不是新开第四档（那会破坏与 SER/AED 的可比性），而是：

- `参数量(M)` 列写 `n/a(非神经)`，与 SER 已有的非神经写法一致；
- 这些条目**集中放在 `01-classical-dsp.md`**，作为一个与三档并列的文件，在 landscape 交叉表里占独立一行；
- 三档边界仍为 `< 30M / 30M–500M / > 500M`，左闭右开。

预期结论（要由调研证实或证伪，不得预设为定论）：**AGC 的神经网络模型几乎全部落在小型档，中型稀疏，大型档只有生成式音频修复且严格说不是 AGC**。若调研结果如此，就如实写，并在 landscape 里给出解释——增益控制是一个**瞬时电平闭环问题**，不需要大参数量，参数量堆上去换不来闭环性能的同等提升。

---

## Global Constraints

1. **每条记录必须可核验。** `来源` 列必须有 arXiv ID / GitHub 链接 / 官方文档链接之一。查不到就**删除该条**。由校验器强制。
2. **"没有公开基准"不等于"可以不写指标"。** AGC 大量组件（尤其经典 DSP）没有公开基准数据集。处理方式：在 `00` 定义**编号化的自测口径**（输入电平、噪声类型、目标 LUFS、收敛判据、测量窗口），`基准` 列写 `自测(no public benchmark)` 时，`指标` 列必须引用某个自测口径编号。校验器强制。
3. **"作用点"是 AGC 的第一列语义。** 增益可以加在采集前（TX-path 固件 / ADC 后）、采集后（用户态）、播放前（RX）、离线。**加错层的后果不是效果差，是削波与增益泵浦**。每条记录必须写明作用点。
4. **参数量对扩散类方法失效，必须同时记计算量。** 生成式音频修复的多数值 < 500M，但推理成本由采样步数决定。大型档记录必须同时给出 NFE（函数评估次数）或 RTF，否则不得入表。
5. **许可必须记录。** 经典 DSP 组件多为 BSD / Apache-2.0 / MIT，但也有厂商固件（无许可、不可得）。不可得的写 `可得: no` 并注明原因。
6. **不改动 `scripts/check_ser_table.py`。** SER 表已定稿。AGC 复用 `table_lint.py` 另建薄 CLI。
7. **既有速览版不删除。** `docs/research/2026-09-11-aed-agc-model-landscape.md` 保留为素材（其 🔶 标记在 Task 1 被提取为核实清单），仅在 Task 9 给头部加指针。
8. **零第三方依赖交付。** HTML 单文件深色风格，不引外部 CDN。
9. **落地结论允许是"什么都不加"。** 本计划的目标是给出可执行结论，不是推销一个模型。若调研表明在 Android/proot 现状下用户态加增益是二次增益且有害，那么"不加"就是正确结论，必须能被写出来并通过验收。
10. **落地要能接回 `AlwaysOnRec-HY4`。** 跨仓库路径 `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4`，具体改动文件由 Task 8 结论决定，**不得凭空命名**。

---

### Task 1: 定口径 —— 作用点、控制对象、自测口径、schema 与校验器

**Files:**
- Create: `docs/research/auto-gain/00-taxonomy-and-metrics.md`
- Reuse: `scripts/table_lint.py`（由 AED 计划 Task 1 Step 3 创建；若尚未创建，本 Task 先按其规格创建它）
- Create: `scripts/check_agc_table.py`（薄 CLI）
- Test: `python scripts/check_agc_table.py --selftest`

**Interfaces:**
- Consumes: `docs/research/2026-09-11-aed-agc-model-landscape.md`（速览版，提取 🔶 核实清单）、`scripts/table_lint.py`、`docs/research/speech-emotion/00-taxonomy-and-metrics.md`（口径惯例）。
- Produces: AGC 表格 schema（后续所有 Task 共用）、`check_agc_table.py <file.md>`、自测口径定义、规模分档边界。

- [ ] **Step 1: 写作用点与控制对象定义**

`docs/research/auto-gain/00-taxonomy-and-metrics.md` 骨架（直接落盘，不留空）：

```
# 口径：作用点 / 控制对象 / 规模分档 / 自测口径 / 记录 schema
# 本文件是 docs/research/auto-gain/ 下所有文件的唯一口径来源。

## 作用点（AGC 的第一列语义）
| 作用点 | 位置 | 谁能做 | 关键约束 |
| 采集前 | ADC 之后、音频 HAL 之前（TX-path 固件 / ADSP） | SoC 厂商、固件 | 第三方 App 通常改不了 |
| 采集后 | App / proot 拿到的 PCM 之后 | 应用层 | 若固件已做过，此处再增益 = 二次增益 |
| 播放前 | 解码之后、DAC 之前（RX-path） | 系统 / 播放器 | 与"录音"无关，不参与选型 |
| 离线   | 对已存文件批处理 | 任意 | 与"原音频即焚"架构的兼容性要单独论证 |

## 控制对象（这一列把 AGC 与相邻领域分开）
| 值 | 含义 |
| 数字增益 | 对 PCM 样本乘系数 |
| 模拟增益 | 调 ADC/PGA 前端放大倍数（需要硬件通路） |
| 响度(LUFS) | 以 ITU-R BS.1770 响度为目标量的闭环 |
| 降噪掩码 | 频点/时频掩码，本质是增强不是增益，但常与 AGC 同一模块 |
| 联合(SE+AGC) | 增强与响度控制联合优化 |
| 非AGC(相邻：修复·超分) | 严格不是 AGC，收录时必须注明理由 |

## 规模分档（量化前；左闭右开）
| 档 | 参数量 | 说明 |
| 经典 DSP 档 | n/a(非神经) | 反馈环/测量算法，见 01-classical-dsp.md |
| 小型 Small  | < 30M    | 轻量神经网络降噪与增益 |
| 中型 Medium | 30M–500M | 预期稀疏，不得为凑数灌水 |
| 大型 Large  | > 500M   | 生成式修复；必须同时记 NFE 或 RTF |
30M 归中型，500M 归大型。
```

- [ ] **Step 2: 定义编号化自测口径（本 Task 最关键的一步）**

在 `00` 中定义至少 3 个自测口径，编号 `自测口径 1` / `自测口径 2` / `自测口径 3`，每个写明：输入电平范围、噪声类型与 SNR、目标响度（LUFS）、收敛判据、测量窗口长度、报告哪些量（收敛时间 / 稳态误差 / 增益波动 / 削波率 / PESQ / STOI / SI-SDR / DNSMOS）。

示例骨架（数值必须查标准后填，不许编）：

| 编号 | 场景 | 输入 | 目标 | 报告量 |
|---|---|---|---|---|
| 自测口径 1 | 远场语音，稳态 | -40 ~ -20 dBFS，白噪 SNR 10dB | -16 LUFS（需核实目标值出处） | 收敛时间、稳态误差、PESQ |
| 自测口径 2 | 电平突变 | -35 dBFS 跳变到 -10 dBFS | 同上 | 过冲 dB、增益泵浦次数 |
| 自测口径 3 | 低电平噪声底 | -55 dBFS 纯噪声 | 同上 | 噪声提升量 dB、削波率 |

响度目标值必须查标准后填：**ITU-R BS.1770-4**（LUFS 定义）、**EBU R128**（-23 LUFS 广播目标）、**ATSC A/85**、以及**中国的对应标准**（检索 GY/T 系列是否有数字音频响度标准，核实编号后再写）。每个目标值后跟标准出处。

- [ ] **Step 3: 写 AGC 薄 CLI `scripts/check_agc_table.py`**

```python
COLUMNS = ["模型", "版本/形态", "参数量(M)", "输入", "控制对象", "作用点",
           "基准", "指标", "许可", "可得", "edge", "来源"]
```

在 `table_lint.py` 六条通用规则之外，挂四条 AGC 专属规则：

- **规则 g（作用点）**：`作用点` 列必须含 `采集前` / `采集后` / `播放前` / `离线` 之一，否则报 `stage`。
- **规则 h（控制对象）**：`控制对象` 列必须含 `数字增益` / `模拟增益` / `响度(LUFS)` / `降噪掩码` / `联合(SE+AGC)` / `非AGC(相邻` 之一，否则报 `control-target`。
- **规则 i（非神经须标形态）**：`参数量(M)` 为 `n/a(非神经)` 时，`版本/形态` 必须含 `经典 DSP` 或 `标准/测量算法`，否则报 `non-neural-form`。
- **规则 j（自测须引口径）**：`基准` 列含 `自测(no public benchmark)` 时，`指标` 列必须匹配 `自测口径\s*\d+`，否则报 `selftest-ref`。

`--selftest` 覆盖：正例通过；反例命中 `params`/`source`/`license`/`metric`/`placeholder`/`stage`/`control-target`/`non-neural-form`/`selftest-ref` 九类；非目标表不被误伤；以「模型」开头但列数远少于 schema 的对照表不被误伤；schema 表头缺列被检出。

- [ ] **Step 4: 跑自检**

Run: `python scripts/check_agc_table.py --selftest`
Expected: PASS，九类反例全部命中。

- [ ] **Step 5: 建候选池，并提取速览版的 🔶 核实清单**

在 `00` 末尾加两节，均标 `[待核实]`：

`## 候选池`

经典 DSP 线：WebRTC AGC2（数字+模拟双段，含内置 VAD 与噪声门）、WebRTC AGC1（legacy）、SpeexDSP AGC、ffmpeg `loudnorm`（EBU R128 双通）、ffmpeg `dynaudnorm`、SoX `gain`/`norm`、libebur128、Apple AVAudioSession AGC、Android audio HAL / ADSP TX-path AGC（厂商固件，不可得）、PipeWire / PulseAudio 相关模块

小型 ML 线：RNNoise、PercepNet、NSNet / NSNet2、DTLN、DeepFilterNet2 / 3、GTCRN、CRUSE、TFCN、FRCRN、CMGAN、SEMamba、FSPEN、**SE-AGCNet**（arXiv 2606.25959，Interspeech 2026，端到端联合 SE + LUFS 响度控制——**最贴近"自动增益模型"字面含义的一条，必须核实**）

中型线：MossFormer2-SE、TF-GridNet、SpatialNet、BigVGAN（声码器，非 AGC，需标注）

大型线：AudioSR、NuWave2、SGMSE+、StoRM、BBED、flow-matching 类语音增强

多模态线：audio-visual speech enhancement（用唇部视频辅助）、视觉辅助说话人距离/朝向估计驱动增益、视频会议设备的音视频联合归一（产品级，无公开模型）

`## 速览版核实清单` —— 逐个列出 `docs/research/2026-09-11-aed-agc-model-landscape.md` 中 §3.1–§3.5 与 §8 里带 🔶 的断言，注明小节号。这是 Task 2–7 的**必查项**。

- [ ] **Step 6: Commit**

```bash
git add docs/research/auto-gain/00-taxonomy-and-metrics.md scripts/check_agc_table.py scripts/table_lint.py
git commit -m "docs(auto-gain): stage/control-target taxonomy, selftest protocols and validator"
```

---

### Task 2: 经典 DSP 档（AGC 的主力，必须先做）

**Files:**
- Create: `docs/research/auto-gain/01-classical-dsp.md`
- Test: `python scripts/check_agc_table.py docs/research/auto-gain/01-classical-dsp.md`

**Interfaces:**
- Consumes: Task 1 的 schema、自测口径、候选池经典 DSP 线、速览版核实清单 §3.1。
- Produces: 经典 DSP 档表格，供 Task 6/7/8/9 使用。

- [ ] **Step 1: 先回答"二次增益"这个前置问题（本 Task 的核心）**

在动手建表前，先检索并明确写出：**Android / Termux / proot 链路下，App 与 proot 拿到的 PCM 是否已经经过硬件或 TX-path 的 AGC**。

要查的三层：（a）Android AudioSource 与 HAL 层是否默认施加 AGC（含 `VOICE_COMMUNICATION` 与 `MIC`/`UNPROCESSED` 的区别——`UNPROCESSED`/`AudioSource.UNPROCESSED` 与 `AudioFormat` 的 RAW 相关标记是关键线索）；（b）若走 `UNPROCESSED` 能否绕过；（c）proot Ubuntu 通过 Termux / AudioTrack 录音时走的是哪条路径。

结论三种可能，都要如实写：
- 若**已过 AGC** → 用户态再加就是二次增益，会导致削波与增益泵浦，此结论直接决定 Task 9 的落地是"不加"或"只做响度归一不做闭环增益"；
- 若**可绕过** → 写明绕过条件与代价；
- 若**不确定** → 写明"需真机验证"并给出验证方法（录一段已知电平的扫频/白噪，看输出电平是否随输入线性）。

**不许含糊带过**——这一条的结论形态决定了后面所有 Task 的走向。

- [ ] **Step 2: 建表（不少于 8 条）**

按 schema 收录经典 DSP 档。每条必须含：作用点、控制对象（数字/模拟/响度）、许可、来源（官方仓库或 RFC/标准文档）、以及**是否可得**（厂商固件写 `no`）。WebRTC AGC2 必须收录且要写清它的两段结构（模拟段改采集音量、数字段做响度闭环）与内置噪声门。

- [ ] **Step 3: 写"经典 DSP 为什么仍是主力"小节**

用数字说明：CPU 占用（MCPS 量级，要查）、内存（状态变量字节数量级）、延迟（帧长与 lookahead）、以及在**收敛时间/稳态误差**这类闭环指标上神经网络方案是否有公开证据能赢。要引用 WebRTC AGC2 一类实现的实测或官方数据。

- [ ] **Step 4: 写"标准与合规"小节**

列出并核实：ITU-R BS.1770-4、EBU R128、ATSC A/85、中国对应标准（检索 GY/T 系列）。每条给出：标准号（核实后再写，不许编）、目标响度值、适用范围（广播 / 流媒体 / 终端）。这是"目标 LUFS 该设多少"的唯一合法依据。

- [ ] **Step 5: 跑校验器**

Run: `python scripts/check_agc_table.py docs/research/auto-gain/01-classical-dsp.md`
Expected: 0 条违规（`n/a(非神经)` 与 `自测口径 N` 是合法写法）。

- [ ] **Step 6: Commit**

```bash
git add docs/research/auto-gain/01-classical-dsp.md
git commit -m "docs(auto-gain): classical DSP stage and the double-gain question"
```

---

### Task 3: 小型神经网络增益与增强（< 30M）

**Files:**
- Create: `docs/research/auto-gain/02-small-models.md`
- Test: `python scripts/check_agc_table.py docs/research/auto-gain/02-small-models.md`

**Interfaces:**
- Consumes: Task 1 的 schema 与自测口径、Task 2 的二次增益结论。
- Produces: 小型档表格，供 Task 6/7/8 使用。

- [ ] **Step 1: 检索**

核实候选池小型线。补检索：`neural AGC`、`learned gain control speech`、`SE-AGCNet`、`RNNoise MCU deployment`、`DeepFilterNet RTF`、`lightweight speech enhancement DNS challenge`、`GTCRN parameters`。

重点核实 **SE-AGCNet**（arXiv 2606.25959）：它是目前唯一明确把"语音增强 + LUFS 响度控制"端到端联合的工作，参数量、许可、是否有权重、指标都要找到出处。

- [ ] **Step 2: 建表（不少于 10 条）**

每条必须含参数量、作用点、控制对象（多数是 `降噪掩码` 或 `联合(SE+AGC)`，要如实区分——**降噪不等于增益控制，不能混记**）、许可、来源。

- [ ] **Step 3: 写"神经网络在这里换来了什么"小节**

必须回答，要有数字：
（a）小型神经网络相对经典 DSP，在**噪声场景**下的增益是多少（PESQ / STOI / SI-SDR / DNSMOS 提升）；
（b）在**纯电平调整**（无噪声、只是说话声小）这一 AGC 本职任务上，神经网络是否有证据优于经典反馈环——这一条是本计划的判决定性点，**若没有证据就写"没有证据"，不许用噪声场景的数字替代**；
（c）代价：RTF、内存、模型体积，以及在常驻场景下的功耗。

- [ ] **Step 4: 跑校验器**

Run: `python scripts/check_agc_table.py docs/research/auto-gain/02-small-models.md`
Expected: 0 条违规。

- [ ] **Step 5: Commit**

```bash
git add docs/research/auto-gain/02-small-models.md
git commit -m "docs(auto-gain): small neural gain/enhancement models (<30M)"
```

---

### Task 4: 中型神经网络（30M–500M）

**Files:**
- Create: `docs/research/auto-gain/03-medium-models.md`
- Test: `python scripts/check_agc_table.py docs/research/auto-gain/03-medium-models.md`

**Interfaces:**
- Consumes: Task 1 的 schema。
- Produces: 中型档表格与"该档稀疏"的判定。

- [ ] **Step 1: 检索并判定该档是否稀疏**

核实候选池中型线，补检索：`speech enhancement model parameters 30M 100M`、`MossFormer2 parameters`、`TF-GridNet RTF`。

**明确规则**：若核实后该档不足 6 条，**不得为凑数灌水**（不许把相邻领域的声码器、TTS 前端塞进来充数）。改为在文件里显式写出「该档稀疏」并给出原因解释——预期原因是：增益/增强是低层信号处理任务，参数量在几十 M 以内已饱和，继续堆参数换不来闭环指标的同等提升，且实时性约束会先于精度触顶。

- [ ] **Step 2: 建表（能收多少收多少，下限 4 条）**

每条必须含参数量、RTF（有则必填）、作用点、控制对象（属于相邻领域的必须在控制对象列写 `非AGC(相邻：…)` 并注明收录理由）、许可、来源。

- [ ] **Step 3: 写"中型档稀疏说明"小节**

给出该档条目数量、能找到的代表模型、以及为什么没有更多。若结论与预期相反（即该档其实很丰富），同样如实写，并回过头在 `00` 的口径裁定节记录对预期假设的推翻。

- [ ] **Step 4: 跑校验器并 Commit**

Run: `python scripts/check_agc_table.py docs/research/auto-gain/03-medium-models.md`
Expected: 0 条违规。

```bash
git add docs/research/auto-gain/03-medium-models.md
git commit -m "docs(auto-gain): medium neural models and the sparsity finding"
```

---

### Task 5: 大型与生成式（> 500M）

**Files:**
- Create: `docs/research/auto-gain/04-large-models.md`
- Test: `python scripts/check_agc_table.py docs/research/auto-gain/04-large-models.md`

**Interfaces:**
- Consumes: Task 1 的 schema（含"参数量对扩散失效"约束）。
- Produces: 大型档表格，供 Task 7/8 使用。

- [ ] **Step 1: 检索**

核实候选池大型线。补检索：`diffusion speech enhancement NFE`、`audio super resolution model size`、`generative audio restoration real time`。

- [ ] **Step 2: 建表（不少于 6 条）**

每条**必须**同时给出参数量与 NFE（扩散步数 / 函数评估次数）或 RTF，缺一不可入表（Global Constraint 4）。`控制对象` 列几乎全部要写 `非AGC(相邻：修复·超分)`，并注明收录理由——本档存在的意义是回答"用生成式方法做增益/修复值不值"，不是选型池。

- [ ] **Step 3: 写"生成式在这里的边界"小节**

必须回答：生成式修复相对经典 DSP 在**极低质量输入**（如严重削波、带限、强噪）上提升多少；RTF 与 NFE 的量级（给出是否可能实时的明确判断）；以及**幻觉风险**——生成式方法会"补出"输入中不存在的语音内容，这在"原音频即焚 + 只留文本"的架构下意味着什么（补出的内容会进入转写与情绪判定，形成无来源的记忆）。这一条要在 Task 9 落地篇被引用。

- [ ] **Step 4: 跑校验器并 Commit**

Run: `python scripts/check_agc_table.py docs/research/auto-gain/04-large-models.md`
Expected: 0 条违规。

```bash
git add docs/research/auto-gain/04-large-models.md
git commit -m "docs(auto-gain): large/generative restoration and the hallucination boundary"
```

---

### Task 6: 跨切轴一 —— 端侧部署

**Files:**
- Create: `docs/research/auto-gain/05-edge-deployment.md`
- Modify: `docs/research/auto-gain/01-classical-dsp.md`（回填 `edge` 列）、`02-small-models.md`（回填 `edge` 列）
- Reference: `docs/research/speech-emotion/04-edge-deployment.md`、`docs/research/qnn-real-device-runbook.md`、`docs/research/2026-09-09-qnn-real-os-integration.md`

**Interfaces:**
- Consumes: Task 2/3 的表格、Task 2 的二次增益结论、SER 04 已建立的功耗阶梯（**引用，不重算**）。
- Produces: 端侧结论，供 Task 8/9 使用。

- [ ] **Step 1: 写"三处作用点的端侧可得性"表（AGC 独有）**

| 作用点 | 第三方 App 能否实现 | 功耗档 | 备注 |
|---|---|---|---|
| 采集前（aDSP / TX-path） | 通常不能（见 SER 04 的权限隔离结论：普通第三方 App 能用 Hexagon HTP，但**不能**用 aDSP 的 SEE/LPAI，内核 fastrpc 对未授信进程 attach audioPD 返回 -EACCES） | mW 档 | 拿不到 |
| 采集后（AP 用户态 / proot） | 能 | AP 上常驻跑模型：数十至数百 mW；跑经典 DSP：<5 MCPS | 唯一可选层 |
| 离线 | 能 | 一次性 | 与即焚架构兼容性另论 |

**沿用 SER 04 已确立的 A/B 两档**：A 档·真端侧（原生 App / aDSP / Sensing Hub / 手机 NPU）vs B 档·proot 内（CPU 推理，通用 Linux 空闲 400–1000 mW）。

- [ ] **Step 2: 检索 runtime 与量化证据**

覆盖 TFLite Micro、ONNX Runtime Mobile、CoreML、NCNN、MNN、RKNN、QNN、CMSIS-NN / Ethos-U（MCU 侧）。重点核实 **RNNoise 一类超小模型在 MCU 上的公开部署案例**（这是 AGC 领域唯一有大量端侧实测证据的分支）。

- [ ] **Step 3: 写"常驻增益控制的功耗账"**

必须给出并注明来源或假设：经典 DSP（WebRTC AGC2 一类）的 MCPS 与 mW 量级；小型神经网络（RNNoise / DTLN / GTCRN 一类）常驻的 RTF 与 mW 量级；两者相对"什么都不做"的增量。**功耗数字直接引用 SER 04 与 `docs/research/always-on-recording/` 已建立的量级阶梯**，不另起一套。

- [ ] **Step 4: 回填 edge 列**

对 Task 2/3 每条给出 `yes: <runtime+量化>` / `no` / `unknown(未找到公开转换案例)`，并按 A/B 两档标注。经典 DSP 条目通常可写 `yes: 任意 CPU（C 定点实现）`，但要在备注里说明它仍需跑在 AP 上（拿不到 aDSP）。

- [ ] **Step 5: 跑校验器并 Commit**

Run: `python scripts/check_agc_table.py docs/research/auto-gain/01-classical-dsp.md 02-small-models.md`
Expected: 0 条违规。

```bash
git add docs/research/auto-gain/05-edge-deployment.md 01-classical-dsp.md 02-small-models.md
git commit -m "docs(auto-gain): edge deployment axis — aDSP unreachable, AP is the only layer"
```

---

### Task 7: 跨切轴二 —— 多模态自动增益（预期为空，要给出证据）

**Files:**
- Create: `docs/research/auto-gain/06-multimodal.md`

**Interfaces:**
- Consumes: Task 1 的多模态候选池、Task 3/5 的表格。
- Produces: 多模态象限的**空/非空判定与论证**，供 Task 8 使用。

**本 Task 的目标不是凑出一张表，而是给一个可信的"为什么这个象限不存在"。** 若调研证伪（确实存在），则按常规建表；若证实为空，则"空"本身就是结论，同样通过验收。

- [ ] **Step 1: 检索（检索词要逐条记录进文件）**

至少覆盖：`audio-visual gain control`、`visual-assisted automatic gain control`、`multimodal loudness normalization`、`audio-visual speech enhancement`、`speaker distance estimation visual gain`、`video conferencing audio video joint normalization`、`跨模态 响度 归一`。

- [ ] **Step 2: 记录检索证据**

在文件里列出：每个检索词、命中的相关工作（有则记录，无则写 `无命中`）、以及命中项为何**不算**多模态 AGC（例如 audio-visual speech enhancement 是增强不是增益控制，其控制对象是掩码不是增益）。

- [ ] **Step 3: 写"这个象限为什么是空的"小节**

给出物理解释而不仅是"没找到"。预期论证（要由检索证据支撑，可以推翻）：增益控制是一个**瞬时电平闭环**问题，决策所需的全部信息都在音频信号本身（当前电平、目标电平、噪声底）；视觉与文本不提供任何关于瞬时电平的额外信息。唯一有物理意义的多模态输入是**说话人距离/朝向**（影响该加多少增益），但（a）距离用麦克风阵列的声学方法比视觉更直接且省电，（b）视觉方案要开摄像头，合规成本与功耗都高一个量级。因此"多模态自动增益"作为一个模型品类在本领域不成立。

- [ ] **Step 4: 若证伪则建表**

若确实找到 ≥3 条真实的多模态 AGC 工作，则按 schema 建表并跑 `check_agc_table.py`，同时回过头在 `00` 口径裁定节记录对预期假设的推翻。

- [ ] **Step 5: Commit**

```bash
git add docs/research/auto-gain/06-multimodal.md
git commit -m "docs(auto-gain): multimodal axis — empty quadrant with evidence"
```

---

### Task 8: 收敛 —— landscape + 交叉表 + HTML 全景

**Files:**
- Create: `docs/research/auto-gain/2026-09-landscape.md`
- Create: `docs/auto-gain-models.html`

**Interfaces:**
- Consumes: Task 1–7 全部表格与结论。
- Produces: 选型输入，供 Task 9 使用。

- [ ] **Step 1: 写交叉表**

`2026-09-landscape.md` 核心是 **档位（经典 DSP / 小 / 中 / 大）× {edge, multimodal}** 交叉表，每格给：条目数量、代表实现、典型指标（PESQ/STOI 或收敛时间/稳态误差，视控制对象而定）、典型 RTF/MCPS。多模态列若全空，就写"全空（见 06）"，**不填占位符**。

- [ ] **Step 2: 写"AGC 到底是不是模型问题"这一节（本计划的结论锚点）**

用 Task 2–5 的证据给出明确判断，形态为下列之一并给出理由：**主要是 DSP 问题 / 主要是模型问题 / 分层（闭环增益是 DSP，噪声场景是模型）**。无论哪种都要引用具体数字，不许骑墙。

- [ ] **Step 3: 写"加在哪一层"决策表**

输入：当前是否已过 TX-path AGC（Task 2 结论）、能否拿 aDSP（不能，见 Task 6）、是否常驻、是否允许联网、目标是 ASR/情绪蒸馏质量还是听感。输出：加 / 不加 / 加在哪一层 / 用什么。

必须包含"什么都不加"这一行及其触发条件。

- [ ] **Step 4: 写"与即焚架构的兼容性"小节**

AGC 提升采集能力，与"最小必要"原则存在张力。要写出干净的合规论证：增益只作用于**送入推理的那份副本**，不作用于留存副本；增益参数可随原始音频一并焚毁；生成式修复因会补出输入中不存在的内容（Task 5 幻觉风险），**不得**用于会产生记忆的链路。

- [ ] **Step 5: 生成 HTML 全景**

`docs/auto-gain-models.html`：深色单文件、零外部依赖、sticky 导航，沿用 `docs/always-on-recording.html` 结构。至少含：三处作用点示意图（SVG）、档位 × edge 矩阵、经典 DSP 与小型神经网络的功耗/RTF 对比表、响度标准表、多模态空象限说明。

- [ ] **Step 6: 跑全量校验器**

Run: `python scripts/check_agc_table.py docs/research/auto-gain/*.md`
Expected: 0 条违规，并打印总记录数（应 ≥ 28；因领域主力为非神经 DSP，条目数天然少于 AED/SER，这是正常的，不是缺陷）。

- [ ] **Step 7: Commit**

```bash
git add docs/research/auto-gain/2026-09-landscape.md docs/auto-gain-models.html
git commit -m "docs(auto-gain): landscape synthesis and HTML panorama"
```

---

### Task 9: 落地 —— 接回 AlwaysOnRec-HY4

**Files:**
- Create: `docs/research/auto-gain/07-adoption.md`
- Modify: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4` 下由 Task 8 结论指定的文件（**不得凭空指定**；若结论是"不加"，则只改文档）
- Test: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4` 下 `python -m unittest discover -s tests -t .`（必须仍全绿，147 个）

**Interfaces:**
- Consumes: Task 8 决策表、Task 2 的二次增益结论、Task 6 的作用点可得性。
- Produces: 一个明确的落地动作，或一份"什么都不做"的论证。

- [ ] **Step 1: 先读 HY4 捕获链路再动笔**

读 HY4 的捕获相关代码（起点 `aor/drivers/ear.py`，按实际结构扩展），确认并写入 `07-adoption.md`：
（a）当前录音用的什么源、有没有已存在的增益/归一化处理；
（b）`classify_mood(dbfs, dur_ms)` 用的 `dbfs` 是怎么算的——**若 AGC 施加在它之前，电平被归一化后 dbfs 就失去了"这个人说话多大声"的信息**，这是个真实的副作用，必须写明；
（c）若加 AGC，是在录音写入前（影响留存）还是只在送推理前（不影响留存）。

- [ ] **Step 2: 写落地建议**

`07-adoption.md` 必须回答：
1. 按 Task 8 决策表，本仓库的具体动作是什么（加 / 不加 / 只做响度归一）；
2. 若加：用哪个实现、加在哪一层、如何避免二次增益（Task 2 结论）、如何保留 dbfs 的原始电平语义（Step 1b）；
3. **不做什么**（三条，逐条给理由）：
   - **不在采集前层做**——第三方 App 拿不到 aDSP 的 SEE/LPAI（Task 6），此层不可达；
   - **不引入生成式修复**——会补出输入中不存在的内容，污染转写与情绪记忆（Task 5）；
   - **不让增益作用于留存副本**——增益只服务于蒸馏质量，不提升留存能力（Task 8 Step 4）。

- [ ] **Step 3: 改 HY4 代码（条件执行）**

若 Task 8 结论是"加"，在 Step 1 确认的位置加分支，保持惰性导入与缺依赖静默降级的既有行为；若结论是"不加"，**不改代码**，只在文档写明触发条件（例如"若未来切换到 `AudioSource.UNPROCESSED` 或原生 App 拿到未处理 PCM，则重新评估"）。

```python
def channel() -> str:
    return os.environ.get("AOR_ASR_CHANNEL") or os.environ.get("LAOS_ASR_CHANNEL") \
        or DEFAULT_CHANNEL
```

- [ ] **Step 4: 跑 HY4 全量测试（跨仓库）**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4 && python -m unittest discover -s tests -t .`
Expected: 147 tests OK。

- [ ] **Step 5: 给速览版加指针（不删除）**

在 `docs/research/2026-09-11-aed-agc-model-landscape.md` 头部插入一行，指向 `docs/research/auto-gain/` 并说明 AGC 部分已被取代（AED 部分另见 AED 计划）。**保留原文**，其 §8 文献跟踪仍有独立价值。

- [ ] **Step 6: 分别 Commit（两个仓库）**

```bash
# laos 仓库
git add docs/research/auto-gain/07-adoption.md docs/research/2026-09-11-aed-agc-model-landscape.md
git commit -m "docs(auto-gain): adoption plan and pointer from superseded landscape"

# AlwaysOnRec-HY4 仓库（仅当 Step 3 实际改了代码）
cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4
git add <Task 8 指定的文件>
git commit -m "feat: gain handling per auto-gain landscape decision"
```

---

## 验收清单（全部完成后）

- [ ] `python scripts/check_agc_table.py docs/research/auto-gain/*.md` 零违规，总记录 ≥ 28
- [ ] 「二次增益」问题已给出明确结论（已过 AGC / 可绕过 / 需真机验证），未含糊带过
- [ ] 每条记录都写了作用点与控制对象；降噪没有被混记为增益控制
- [ ] 自测口径已编号定义，且所有 `自测(no public benchmark)` 条目都引用了编号
- [ ] 响度目标值全部引用了标准（ITU-R BS.1770-4 / EBU R128 / ATSC A/85 / 中国标准），无编造标准号
- [ ] 经典 DSP 档独立成篇，且被论证为（或否证为）主力
- [ ] 中型档的稀疏性（或丰富性）已给出结论与原因，未为凑数灌水
- [ ] 大型档每条都有 NFE 或 RTF；幻觉风险已写入且被落地篇引用
- [ ] 多模态象限给出"空"或"非空"的明确判定，并附检索证据
- [ ] 落地结论允许且可能等于"什么都不加"，若如此已写出触发条件
- [ ] 速览版保留且头部有指针
- [ ] `AlwaysOnRec-HY4` 测试仍 147 全绿
- [ ] 每个 Task 一个 commit
- [ ] `scripts/check_ser_table.py` 未被修改

## 自检记录（写完即核）

- **Spec 覆盖**：用户 5 类划分 → Task 2（经典 DSP 档）+ Task 3/4/5（规模三档）+ Task 6（端侧）+ Task 7（多模态），按 Scope Check 重构；Global Constraints 10 条分别落在 Task 1（1/2/3/4/5）、Task 2（3 的二次增益、响度标准）、Task 5（4 的 NFE）、Task 6（aDSP 不可达）、Task 8（9 的允许"不加"、即焚兼容性）、Task 9（落地三条不做）。
- **占位符扫描**：无 `TBD` / `待补` / `TODO` / "Similar to Task N"。候选池与速览版核实清单的 `[待核实]` 是输入线索标记，入表时必须消除（校验器会拦）。"预期结论"均以"要由调研证实或证伪"的形式表述，并显式允许推翻，不是预设结论。
- **类型/命名一致**：`check_agc_table.py <file.md>` 在 Task 1–9 中逐字一致；12 列名在 Task 1 定义后不再改写；`table_lint.py` 的 `check_text(text, columns, path, extra_rules=())` 签名与 AED 计划中的定义一致；`自测口径 N` 的编号写法在 Step 2 定义后被规则 j 强制。`AOR_ASR_CHANNEL`、`channel()`、`classify_mood()` 与 HY4 现有代码逐字一致。
- **既有接口不破坏**：`check_ser_table.py` 只读不写；`table_lint.py` 若已由 AED 计划创建则复用不重写；HY4 既有 147 测试保持通过；速览版只加指针不删内容。
- **与 AED 计划的接口**：两者共用 `scripts/table_lint.py`。若 AED 计划尚未执行到其 Task 1 Step 3，本计划 Task 1 按其规格先创建 `table_lint.py`，AED 计划执行时直接复用——两边规格已对齐（同一函数签名、同一 `MIN_SCHEMA_COLS = 10`、同一六条通用规则），不会冲突。

---

## Execution Handoff

Plan 已写完并保存。执行方式二选一：

**1. Subagent-Driven（推荐）** —— 每个 Task 派一个子代理，两轮审查（先符合 spec、再代码质量），Task 间快速迭代。

**2. Inline Execution** —— 在当前会话按序执行，带检查点。

选哪种？
