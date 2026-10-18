# 端侧音频智能综述：硬件档位、前处理瓶颈与 2026 年的新边界（2017–2026）

> 方法：LitReview S0–S8 九步（`docs/research/2026-10-18-litreview-skill-workflow.md` §4）。
> 证据附录：`docs/research/2026-10-19-on-device-audio-survey-evidence.md`（检索日志、筛选台账、单篇卡片、叙事大纲、溯源记录、未核实清单）。
> 证据等级见 §2.3；未核实内容统一在 §9。

## 1. 摘要与结论

本文纳入 29 篇文献（编号 S01–S29，覆盖 2020–2026 年，重点 2022–2026；检索、筛选与排除见 §2–§3，逐篇卡片见证据附录 §4），围绕五个问题组织：「端」分哪几档；端侧音频的瓶颈到底在哪；五条降本路线各换来什么；部署后如何在域移下不退化；2026 年的新边界在哪。七条结论：

1. **「端侧」不是一个词，是四个量级**。无加速器的 $5 MCU（[S01] ESP32-S3：240 MHz 双核、512 KB SRAM、无 NPU）、带集成 NPU 的 MCU（[S08] MCXN947）、移动 SoC/NPU（[S28] CLAP >300 MB 体积）、通用 AP（[S16] 树莓派）四档之间差 3–4 个数量级。**报"端侧"而不写平台，等于没报**——[S08] 的 59× 加速完全来自片上 NPU，[S01] 的 13M 参数则是在没有 NPU 的前提下做到的，两者不可比。
2. **能耗大头不在模型，在采集与前处理。** [S03] 用模拟二值特征提取替换数字前处理，使数据采集与前处理的能耗降低 **29×**、占系统份额从 **85% 降到 16%**。这意味着"把模型再缩小"打的是小头。[S06] 从另一面印证：把 MFCC 到推理的整条流水线一起评测时，**"哪个模型最优"这个结论会变**。[S05] 则量化了选型本身的误差——用 MACs 当代理，能量与延迟预测误差分别可被降低 **3×** 与 **6.5×**。
3. **五条降本路线省的不是同一种资源。** NAS（[S04]）、架构与算子重设计（[S11]/[S07]/[S13]）、量化与剪枝（[S12]/[S08]）、换计算范式（[S09] SNN、[S03] BNN）、专用硅（[S08]/[S18]）——有的省内存（[S07] 峰值内存 −83.0%）、有的省算力（[S08] 59×）、有的省能量（[S03] 29×）、有的只是省选型试错（[S05] 采集量 −100×）。**混称"模型压缩"会掩盖这一点。**
4. **参数量达标 ≠ 端侧有产物。** [S23] EfficientAT 的 0.983M 参数 / 11 MMACs/s 在预算内，但**只有官方 PyTorch 权重、未见公开 INT8 发布**；[S22] YAMNet 则有完整的 TFLite / TFLite Micro 官方导出路径。本仓 AED 域表的原话是"真实缺口：论文给约束（128K 参数 / 30 MMACs），但部署产物少见"。
5. **部署后的自适应决定模型寿命，三条路径的差别是要不要标签与要不要反向传播。** [S14] 用 **100 条标注**恢复 5% 精度、代价 **806 mJ / 14 s**（内存 <10 kB）；[S15] 用**伪标签**做到无标注、提升 **+19.2% / +16.0%**；[S09] 用**局部可塑性**做到无反向传播的持续自适应。
6. **真机失效是纸面测不到的。** [S16] 在树莓派上发现**持续 CPU 使用导致升温、触发自动降频、进而影响推理延迟**；[S26] GTCRN 的仓库实测（48.2K 参数 / 33.0 MMACs）与论文口径（23.7K / 39.6 MMACs）**不自洽**。两条都指向同一件事：端侧选型要看导出产物与真实硬件，不能只看论文表格。
7. **2026 年的新边界是开放词表下端，但"能跑"与"能实时跑"还差 2×。** 开放词表从 [S28] 的 >300 MB 压到 [S02] Samsone-134M（小型音频语言模型），再压到 [S01] Oído——**13M 参数 Conformer-CTC 跑在 $5 无 NPU MCU 上，LibriSpeech WER 3.70% / 8.23%**。代价是实板测得 **1.97× 时长**（约 2 倍慢于实时）。所以正确表述不是"端侧能做开放词表了"，而是"**端侧能做开放词表，但暂时只能说完再转**"。

边界声明：本综述 29 篇里**只有 [S29] 一篇读到全文**，[S01]–[S21] 为摘要口径，其数字只作量级与方向证据、不参与跨行比较；硬件档位的功耗阶梯引用本仓既有域表的表格核实口径，未逐篇回原文复核（§9）。

## 2. 范围、检索与筛选方法

时间窗 2017-01-01 至 2026-10-19，重点 2022–2026。纳入标准：给出参数量/算力/延迟/功耗并在明确硬件上测量、给出端侧 runtime 或量化导出证据、给出常驻场景能耗或自适应证据、给出端侧音频的隐私或系统设计结论，四者居其一。排除：纯云端大模型、纯音乐生成、纯 ASR（不涉及端侧约束）、纯视觉、只有营销口径的产品稿。

**这篇综述不写什么**：不写"如何在某个具体芯片上移植模型"的操作手册（那是 runbook 不是综述）；不重跑 benchmark；不做采购建议。

### 2.1 检索日志

检索执行于 2026-10-19（本地时间）。两条通道：①arXiv API（`export.arxiv.org/api/query`，注意该端点返回 301，**必须跟随重定向**才拿得到内容）；②本仓既有领域表（`audio-events/` / `auto-gain/` / `always-on-recording/`）的表格核实记录。

| 检索日 | 库 | 检索式 | 年份窗 | 命中 | 纳入候选 |
|---|---|---|---|---|---|
| 2026-10-19 | arXiv | abs:"on-device" AND abs:audio | 不限（实得 2016–2026） | 40 | 11 |
| 2026-10-19 | arXiv | abs:"keyword spotting" AND abs:microcontroller | 不限（实得 2020–2026） | 20 | 9 |
| 2026-10-19 | arXiv | abs:"edge" AND abs:"audio" AND abs:"inference" | 不限（实得 2023–2026） | 40 | 2 |
| 2026-10-19 | arXiv | id_list 批量取摘要（21 篇候选逐条核实） | 2020–2026 | 21 | 21 |
| 2026-10-19 | 本仓领域表 | audio-events/05-edge-deployment.md §1–§2 | 2017–2026 | 12 | 4 |
| 2026-10-19 | 本仓领域表 | auto-gain/02-small-models.md + 05-edge-deployment.md | 2017–2026 | 16 | 3 |
| 2026-10-19 | 本仓领域表 | ISCA Interspeech 2026（v2 补检已入库 [S29]） | 2026 | 1 | 1 |

口径说明：**「命中」是命令实际返回条数，「纳入候选」是进入标题/摘要筛选的条数**，两者不等是检索噪声。arXiv 三条检索式合计 100 条命中，重叠严重（同一批 MCU/KWS 论文被多式命中），去重后取 21 篇逐条读摘要；领域表通道取 8 篇。**硬件档位的功耗阶梯不在此表内**——它引用 `always-on-recording/hardware-power.md` §3 的既有表格核实口径，按本仓约定"直接引用，不另起一套、不重算"。

### 2.2 证据等级

四级：**全文**（读过方法与结果表）、**表格核实**（域表逐字段与官方仓库/文档核对）、**摘要**（只到标题与摘要）、**二手**（媒体或第三方转述）。本综述分布：全文 1 篇（[S29]）、表格核实 7 篇（[S22]–[S28]）、摘要 21 篇（[S01]–[S21]）、二手 0 篇。

三条可比规则：①**摘要口径的数字不参与跨行比较**——[S01]–[S21] 的数字只作量级与方向证据。②**同指标、同硬件、同条件才可横比**——[S08] 的 59× 是"NPU vs 同芯片 CPU"，[S01] 的 1.97× 是"实板 vs 实时"，两者不同轴，不可相减。③**参数量、MACs、内存、延迟四者互不折算**——[S29] 只报 49M MACs 与 55 KB 内存，**参数量写"未给出"**，禁止用内存反推（本仓 `auto-gain/00` 裁定 4 的同一条纪律）。

## 3. 筛选与纳入

| 编号 | 文献 | 年份 | 决定 | 理由 |
|---|---|---|---|---|
| C01 | Oído: Open-Vocabulary ASR on a $5 MCU without a Neural Accelerator | 2026 | 纳入 S01 | 端侧证据：无 NPU MCU 上的开放词表 ASR，有实板测量与 WER |
| C02 | Samsone: A Family of Open Small Audio Language Models for On-Device Inference | 2026 | 纳入 S02 | 端侧证据：小型音频语言模型 + 移动端 checkpoint + 开源 Android 演示 |
| C03 | Sub-mW Keyword Spotting on an MCU: Analog Binary Feature Extraction and BNN | 2022 | 纳入 S03 | 端侧证据：前处理能耗份额 85%→16%，直接支撑"瓶颈不在模型" |
| C04 | MicroNets: NAS for TinyML on Commodity Microcontrollers | 2020 | 纳入 S04 | 方法证据：op count 作延迟代理的 NAS 范式 |
| C05 | InstMeter: Instruction-Level Prediction of Energy and Latency on MCUs | 2026 | 纳入 S05 | 方法证据：量化了粗代理的误差（3× / 6.5× / 100×） |
| C06 | End-to-End Efficiency in Keyword Spotting（TKWS） | 2025 | 纳入 S06 | 端侧证据：整条流水线评测，14.4k 参数 / 92.4% F1，三块 STM32 |
| C07 | MambaLite-Micro: Memory-Optimized Mamba Inference on MCUs | 2025 | 纳入 S07 | 端侧证据：峰值内存 −83.0%，ESP32S3 + STM32H7 双平台 |
| C08 | KWS on the MCUX947 MCU with Integrated NPU | 2025 | 纳入 S08 | 端侧证据：NPU 59× / 97.06% / 30.58 KB，界定"有加速 vs 无加速"档 |
| C09 | EdgeSpike: SNN for Low-Power Autonomous Sensing in Edge IoT | 2026 | 纳入 S09 | 端侧证据：SNN 换计算范式，91.4% 且与 INT8 CNN 只差 1.2 pp |
| C10 | Embedded ML for Microcontroller-Class Edge Devices | 2026 | 纳入 S10 | 方法证据：系统导向综合，前处理与工程决策的骨架来源 |
| C11 | LiCo-Net: Linearized Convolution Network for Hardware-efficient KWS | 2022 | 纳入 S11 | 方法证据：算子级降本（推理用 int8 linear） |
| C12 | KWS System and Evaluation of Pruning and Quantization on STM32F7 | 2022 | 纳入 S12 | 端侧证据：每 37 ms 一次分类（Cortex-M7 @216 MHz + 512 KB SRAM 单平台口径） |
| C13 | DiTMoS: Diverse Tiny-Model Selection on Microcontrollers | 2024 | 纳入 S13 | 方法证据：反压缩路线（弱模型集成） |
| C14 | On-Device Domain Learning for KWS on Low-Power Extreme Edge | 2024 | 纳入 S14 | 端侧证据：100 条标注 / 806 mJ / 14 s / <10 kB |
| C15 | Self-Learning for Personalized KWS on Ultra-Low-Power Audio Sensors | 2024 | 纳入 S15 | 端侧证据：无标注伪标签，+19.2% / +16.0% |
| C16 | Environmental Sound Classification on An Embedded Hardware Platform | 2023 | 纳入 S16 | 端侧证据：热降频影响推理延迟，真机失效的头号样本 |
| C17 | Tiny-Align: Bridging ASR and LLM on the Edge | 2024 | 纳入 S17 | 端侧证据：边缘 ASR-LLM 与端上个性化训练 |
| C18 | NeuralAids: Wireless Hearables With Programmable Speech AI Accelerators | 2025 | 纳入 S18 | 端侧证据：极端体积/功耗档的端侧实时增强 |
| C19 | Towards Privacy-Preserving Audio Classification Systems | 2024 | 纳入 S19 | 系统证据：端侧处理的合理论证 |
| C20 | Robust Wake-Up Word Detection by Two-stage Multi-resolution Ensembles | 2023 | 纳入 S20 | 系统证据：端云两级分工与特征上云 |
| C21 | Selective Attention System: Device-Addressed Speech Detection | 2026 | 纳入 S21 | 端侧证据：转发路由可量化（F1 0.86 → 0.95） |
| C22 | YAMNet（3.7M，TFLite Micro 官方导出） | 2017 | 纳入 S22 | 端侧证据：完整的 TFLite / TFLite Micro 导出路径 |
| C23 | EfficientAT mn10_as（0.983M / 11 MMACs/s） | 2022 | 纳入 S23 | 反例证据：参数达标但无公开量化产物 |
| C24 | DCASE2025 Task 1 baseline（低复杂度 ASC） | 2025 | 纳入 S24 | 端侧证据：10 类约束下的四年天花板 53.24% |
| C25 | RNNoise（0.085M / <10 MFLOPS） | 2017 | 纳入 S25 | 端侧证据：常驻降噪的体积与算力地板 |
| C26 | GTCRN（0.048M，ONNX Runtime Mobile INT8） | 2023 | 纳入 S26 | 端侧证据 + 口径冲突样本（论文 vs 仓库不自洽） |
| C27 | Silero VAD（约 2 MB / 30 ms chunk <1 ms） | 2021 | 纳入 S27 | 端侧证据：常驻门控的事实标准 |
| C28 | CLAP（约 86M+ / >300 MB，开放词表） | 2022 | 纳入 S28 | 端侧证据：开放词表在移动 SoC 档的体积代价 |
| C29 | WaveNorm AGC（Interspeech 2026，49M MACs / 55 KB） | 2026 | 纳入 S29 | 端侧证据：唯一"纯增益闭环 + 因果 + 端侧画像"的现代样本 |
| C30 | 纯云端大音频语言模型一批（数十亿参数、无端侧路径） | 2023–2026 | 排除 | 无端侧路径，与"资源受限设备"不同轴 |
| C31 | 纯音乐生成 / 纯视觉 TinyML 工作 | 2020–2026 | 排除 | 非音频判别任务，与本综述三类任务不同轴 |

纳入 29 条（S01–S29）、排除 2 条。排除理由落到两个维度：**无端侧路径**、**任务不同轴**，不写"感觉不相关"。

## 4. 「端」的四档硬件与三本预算账

> **口径声明**：本节引用的 [S01]/[S08]/[S16]/[S18] 均为**摘要口径**，[S22]–[S28] 为表格核实口径；摘要口径数字只作量级与方向参照，不参与跨行比较（§2.2）。

把 [S01]、[S08]、[S28]、[S16] 并排，"端侧"这个词立即失效——它们分属四个量级。

| 档位 | 代表平台 | 典型预算 | 本综述的锚点 | 能跑什么 |
|---|---|---|---|---|
| **A · 无加速 MCU** | ESP32-S3（240 MHz 双核、512 KB SRAM、8 MB PSRAM、**无 NPU**） | 内存数百 KB 级；体积 MB 级 | [S01] Oído | 13M 参数 Conformer（int8），但**慢于实时 2×**；30 KB 级 KWS（[S08] 在有 NPU 时） |
| **B · 带 NPU 的 MCU** | NXP MCXN947（集成 NPU） | 同上，但推理快 1–2 个数量级 | [S08] | 97.06% KWS / 30.58 KB / **NPU 59× 加速**；[S06] 的 STM32 N6 取最佳 EDP |
| **C · 移动 SoC / NPU** | 手机、助听器加速器 | 体积百 MB 级、瓦级短时 | [S28] CLAP（>300 MB）、[S18] NeuralAids | 开放词表（[S28]）、实时增强（[S18]）、小型音频语言模型（[S02] 134M） |
| **D · 通用 AP** | 树莓派、跑 Linux 的机器 | 空闲即百 mW–W 级 | [S16] | 什么都能跑，但**会热降频**（[S16]），且常驻不划算 |

**三本账必须分开算**：**mW 账**决定能不能常驻，**ms 账**决定能不能流式，**MB 账**决定能不能装进去。[S01] 是典型的三本账互相打架——MB 账过了（8.3 MB 的 int4 变体）、mW 账没报、**ms 账没过**（1.97× 时长）。[S08] 三本都过，但依赖片上 NPU。

本仓既有的功耗阶梯（引用 `always-on-recording/hardware-power.md` §3，不重算）给的是 mW 账的跨档跨度：定制 ASIC 的常驻检测 **47 nW – 1 µW**、专用音频 NPU **140 µW**、手机传感中枢 <1 mA、通用 MCU/AP 软件方案 **26–50 mW**、跑 Linux 的通用机器空闲 **400–1000 mW**——**跨档 3–4 个数量级**。这个跨度是本综述所有"能不能常驻"判断的分母。

## 5. 瓶颈不在模型：前处理、采集与真机失效

> **口径声明**：本节引用的 [S03]/[S05]/[S06]/[S16] 均为**摘要口径**（[S22]/[S23]/[S25]/[S26] 为表格核实）；摘要口径的 29×、3×、6.5× 等倍数只作方向证据，不参与跨行比较（§2.2）。

本节三条证据指向同一个反直觉结论，它们之间是 `结论→反例` 的承接关系。

**第一条（最强）**：[S03] 把模拟二值特征提取替换数字前处理，数据采集与前处理的能耗降低 **29×**、占系统份额从 **85% 降到 16%**。如果模型是大头，这个改动不可能有 29× 的效果。**这意味着"优化模型"打的是小头**——把 [S25] RNNoise 的 0.085M 再缩小一半，对整系统的影响远小于把前处理搬进模拟域。

**第二条**：[S06] 把评测范围从"模型推理"扩展到"MFCC 到推理的整条流水线"，在 STM32 N6/H7/U5 三块板上对比 DS-CNN、LiCoNet、TENet 与 TKWS。结果是 **TKWS 以 14.4k 参数取得 92.4% F1**，且带神经加速的 N6 取得最佳 EDP。关键在于：**换了评测口径，"谁最优"会变**——只在推理段评测时最优的模型，放到整条流水线上未必还是。

**第三条**：[S05] 指出用 MACs、输入参数这类粗代理预测 MCU 上的能量与延迟会失准，改用**时钟周期**后，能量与延迟的预测误差分别降低 **3×** 与 **6.5×**，所需数据采集量减少 **100×**。这条不省任何能耗，但它说明**选型阶段就在靠错的量做决策**。

**第四条是前面三条的骨架来源**：[S10] 是一份面向 MCU 级边缘设备的系统导向综合，它把通用机器学习介绍里通常被隐藏的工程决策逐项摆出来——**采样与缓冲、特征提取即降维、类别不平衡下的验证、模型/运行时协同设计、流式部署**，并以惯性动作识别与 KWS 两个信号族贯穿。它不提出新方法、也不给单一可比基准，但正是它说明了为什么上述三条会同时成立：**端侧音频的成本大头与决策大头都在模型之外**。

**真机才有的失效**是同一件事的另一面。[S16] 在树莓派上部署大规模预训练音频 CNN，发现**持续 CPU 使用导致升温、触发自动降频机制、进而影响推理延迟**——这是纯软件评测永远测不到的失效模式。它还发现**麦克风质量与信号音量**同样影响表现：端侧音频的误差不只来自模型。

与之呼应的是"口径不自洽"：[S26] GTCRN 的仓库实测是 48.2K 参数 / 33.0 MMACs，论文口径是 23.7K / 39.6 MMACs，**两者打架**。以及 [S23] EfficientAT：0.983M 参数 / 11 MMACs/s 完全在预算内，但**只有官方 PyTorch 权重、未见公开 INT8 发布**；反观 [S22] YAMNet 有完整的 TFLite / TFLite Micro 官方导出路径。**"参数量达标"与"端侧有产物"是两件事**，本仓 AED 域表把后者称为"真实缺口"。

> **本节判断**：端侧音频的瓶颈按顺序是——**采集与前处理（[S03] 的 85%）→ 有没有专用加速（[S08] 的 59×）→ 模型本身**。只做第三步的优化，是打偏了。而"能不能落地"还取决于有没有人把量化与导出这一步做完（[S22] vs [S23]）。

## 6. 五条降本路线：各换来什么、代价是什么

> **口径声明**：本节引用的 [S03]/[S04]/[S05]/[S07]/[S08]/[S09]/[S11]/[S12]/[S13]/[S18] 全部为**摘要口径**；表内倍数与百分比只作方向证据，不参与跨行比较（§2.2）。

这是本篇的研究对比表（先成表、再叙述）。五列的「限制」一律带实验条件。

| 方法族 | 代表论文 | 主要思路 | 优势 | 限制（含实验条件） |
|---|---|---|---|---|
| **① NAS / 自动设计** | [S04] MicroNets、[S09] 硬件感知 NAS | 在内存/延迟/能量约束下自动搜架构；[S04] 用 op count 作延迟代理，[S09] 用单次推理能量与内存预算做界 | 不需要人工试错，直接把硬件约束写进搜索目标 | [S04] 的 op count 只是**近似**代理，[S05] 量化了它的误差（延迟预测误差可改进 6.5×）；[S09] 的 SNN 工具链成熟度低于 CNN |
| **② 架构与算子重设计** | [S11] LiCo-Net、[S07] MambaLite-Micro、[S13] DiTMoS | [S11] 推理只用 int8 linear、训练用流式卷积；[S07] 手写 C 算子 + 算子融合 + 内存布局优化；[S13] 反过来做弱模型集成 | 省的是**最紧的那项资源**：[S07] 峰值内存 **−83.0%** 且数值误差仅 1.7×10⁻⁵、准确率与 PyTorch 100% 一致（ESP32S3 + STM32H7） | [S07] 的 C 手写算子意味着**换架构就要重写**；[S13] 路由本身有开销，且总参数可能反而上升（省的是单次推理） |
| **③ 量化与剪枝** | [S12] STM32F7 剪枝/量化、[S08] QAT | [S12] 简化算子数 + 剪枝与量化评测；[S08] 量化感知训练在精度损失最小下压体积 | [S08] 得到 **30.58 KB / 97.06%**；[S12] 每 **37 ms** 出一次结果（Cortex-M7 @216 MHz + 512 KB SRAM，2022 年单平台口径） | [S12] 是 2022 年单平台口径；[S08] 的**模型虽小但依赖片上 NPU**，不能外推到通用 MCU |
| **④ 换计算范式** | [S09] EdgeSpike（SNN）、[S03] BNN + 模拟前端 | [S09] 事件驱动 + 混合代理梯度训练 + 局部可塑性；[S03] 二值网络 + 模拟前端 | [S09] 五任务平均 **91.4%**，与强 INT8 CNN（92.6%）**只差 1.2 pp** 且单次推理能量更低；[S03] 前处理能耗 **29×** | [S09] 的 1.2 pp 差距在安全相关任务未必可接受；[S03] 需定制模拟电路，第三方 App 拿不到；[S09] 五个任务里只有 KWS 是音频 |
| **⑤ 专用硅 / 加速器** | [S08] MCXN947 NPU、[S18] 助听器可编程加速器 | 把推理搬到专用硬件 | [S08] **59×** 加速是本篇最大的单项增益；[S18] 让电池受限的无线助听器也能跑流式语音 AI | **这是档位切换不是模型优化**——收益无法靠改模型复现；[S18] 依赖厂商开放可编程加速器 |

读这张表的方式：**同一列里省的东西不一样**。①③主要省算力与体积，②主要省内存，④主要省能量，⑤是换档位。把五族统称"模型压缩"会让读者以为它们可互换，而实际上一个缺内存的项目（进不了 SRAM）和一个缺电量的项目（常驻不了）需要的是完全不同的路线。

还有一条不属于任何一族但必须先做：**⑤′ 测量方法**（[S05] InstMeter）。它不省任何资源，但它让前面四族的**选型不再靠猜**——能量与延迟预测误差降低 3× / 6.5×，采集量减少 100×。

## 7. 部署之后与 2026 年的新边界

> **口径声明**：本节引用的 [S01]/[S02]/[S03]/[S09]/[S14]/[S15]/[S17]/[S19]/[S20]/[S21] 均为**摘要口径**（[S27]/[S28]/[S29] 为表格核实或全文）；摘要口径数字只作量级与方向参照（§2.2）。

### 7.1 部署后不退化：三条端上自适应路径

模型上线面对的是域移（新噪声、新用户、新麦克风）。三条路径的差别只有两问：**要不要标签**、**要不要反向传播**。

- **[S14] 要标签，代价可量化**：全端上域自适应，在已经很强壮的 KWS 模型上再取 **最高 14% 精度增益**；只用 **100 条标注语音**即可在自适应到复杂语音噪声后恢复 **5% 精度**；内存开销 **<10 kB**；在超低功耗 MCU 上一次自适应耗 **806 mJ、14 s**。
- **[S15] 不要标签，用伪标签**：依据与少量用户录音的相似度打分打伪标签，增量微调个性化模型；在参数量**最高 0.5M** 的模型、两个公开数据集上取得 **+19.2% / +16.0%**。代价是伪标签会**累积错误**——这是自训练的固有风险，摘要未见敏感性分析。
- **[S09] 连反向传播都不要**：轻量局部可塑性规则，支持端上持续自适应，且落在 Loihi 2 / SpiNNaker 2 / Cortex-M 的事件驱动运行时上。代价是精度比 INT8 CNN 低 **1.2 pp**。

三者的取舍很清楚：**要不要付标注成本（[S14] 100 条）＝ 要不要承担伪标签噪声（[S15]）＝ 要不要接受精度差（[S09] 1.2 pp）**。对常驻设备而言，806 mJ / 14 s 还意味着**自适应不能频繁做**。

### 7.2 2026 新边界：开放词表与小型音频语言模型

这是本篇进步最陡的一条曲线，[S28] → [S02] → [S01] 是 `能力→失效` 的承接：

- **[S28] CLAP**（2022）：音频–文本对比学习，类别集推理时给定，绕开"加类要重训"。代价是**约 86M+ 参数、体积 >300 MB**——只能进移动 SoC 档，常驻不可行。
- **[S02] Samsone**（2026）：小型音频语言模型（SALM）系列，**99M / 134M / 356M** 三个缩放点；发布训练代码、权重、**移动端优化 checkpoint** 与开源 Android 演示应用。摘要自述 134M 在该尺寸级 SOTA，但**具体基准数值未核实**（本综述不引用）。
- **[S01] Oído**（2026）：把开放词表 ASR 压到 **$5 无 NPU 的 ESP32-S3**——13M 参数 Conformer-CTC，int8 权重 + 逐帧动态 int8 激活 + int8 注意力全落在该芯片的 SIMD 上，调度围绕 flash 与 PSRAM 带宽设计。LibriSpeech test-clean/test-other WER **3.70% / 8.23%**（与全精度差 0.12 点内），加片上 1.3M LM 后 **3.33% / 7.15%**，transducer 头 **2.99% / 6.67%**，int4 变体装进 **8.3 MB**。同芯片上比厂商识别器少 **2.3–2.8×** 错误，也优于笔记本上全精度的 Whisper tiny.en 与 Moonshine tiny。

**但失效面同样明确**：实板测得固件运行速度为 **1.97× 时长**，即约 **2 倍慢于实时**。所以正确结论是——**端侧已经能做开放词表识别，但暂时只能"说完再转"，不能"边说边转"**。把 [S01] 读成"MCU 上实时 ASR 已解决"是误读；它与 [S27] Silero VAD（30 ms chunk 在 CPU 上 <1 ms）之间那道实时性鸿沟，正是下一步要填的。

### 7.3 隐私、路由与"端侧"的定义强度

三条工作给出三种强度的"端侧"：

- **[S19] 特征级隐私**：提出能分类多类音频、同时具有隐私保护性质的音频特征。它把端侧处理的理由从性能扩展到**合规**——音频能泄露谈话内容、健康状态、情绪、位置与个人偏好。
- **[S20] 两级唤醒**：端上轻量模型实时处理音频流，服务端异构集成模型精炼检测；**上云的是音频特征而非原始音频**。代价是端上结果不是最终判定，与"全端侧"诉求有张力。
- **[S21] 转发路由可量化**：把"是否转发给 ASR"建模为对交互历史的序贯路由（SDAR）而非 utterance 局部分类。在 60 小时多说话人英语留出集上，**纯音频 F1 = 0.86**（P 0.89 / R 0.83），加摄像头后 **F1 = 0.95**（P 0.97）。

[S21] 值得单独表扬的地方是它**给了绝对值**——本综述在别处反复遇到"只报显著提升、无绝对值"的写法（本仓 AED 侧同样如此），而 [S21] 让人能直接算：+0.09 F1 换一个摄像头，值不值？本综述的判断是**不值**——摄像头带来功耗与旁观者合规两笔账，而 [S21] 的纯音频 0.86 已经可用。

### 7.4 任务侧落点：门控、事件、增强、增益

端侧不是单一任务，四类任务的预算轴完全不同：

| 任务 | 端侧锚点 | 关键约束 | 现状判断 |
|---|---|---|---|
| **门控（VAD/唤醒）** | [S27] Silero VAD 约 2 MB、30 ms chunk 在 CPU 上 <1 ms；[S03] 亚毫瓦门控 | 常驻，mW 账最紧 | 已解决，且有从软件（[S27]）到专用硅的整条成本谱 |
| **音频事件（AED）** | [S22] YAMNet 3.7M / ~72 MMACs/s（有 TFLite Micro 导出）；[S23] 0.983M / 11 MMACs/s（**无量化产物**）；[S24] DCASE 10 类 / 29.42 MMACs/s / 53.24% | 词表固定，加类要重训 | **四年天花板没动**（60.8→62.7→62.1→61.5%），端侧档的瓶颈是词表与算力双约束 |
| **增强（降噪）** | [S25] RNNoise 0.085M / <10 MFLOPS；[S26] GTCRN 0.048M / ONNX Runtime Mobile INT8 | 改掩码不改电平 | 体积与功耗地板已很低，再缩收益有限（[S03] 说明大头不在模型） |
| **增益（AGC）** | [S29] WaveNorm 49M MACs / 55 KB，因果，对齐 ITU-T P.56/P.79 | 必须因果、必须防二次增益 | **唯一现代神经样本，但参数量与闭环指标双空白**，只能进观察名单 |

四类里只有**门控**真正解决了常驻问题；**AED** 卡在词表与算力的双重约束且天花板四年不动；**增强**已到地板；**增益**刚刚出现神经方案但还没在自己的尺子上报过数。

## 8. 研究空白与未来方向

> **口径声明**：本节引用的 [S01]/[S02]/[S03]/[S05]/[S06]/[S09]/[S14]/[S15]/[S16] 均为**摘要口径**；由摘要口径条目推导出的"空白"同样只作方向判断，不作为已证实的领域结论（§2.2）。

每条都追溯到具体局限，并给出验收口径。

1. **把"整条流水线"变成端侧音频的默认评测口径**（源于 [S03] 的**局限**：只给比例与倍数、无整系统绝对功耗；[S06] 的**局限**：只到 KWS 与 STM32 三块板；[S16] 的**局限**：热降频是通用 AP 档才有的现象、未给统一表）。做法：任何端侧音频论文同时报"采集+前处理+推理"三段能耗与延迟。验收：三段之和可核对，且必须声明平台有无加速器。
2. **补"参数达标 → 量化产物"这一环**（源于 [S23] 的**局限**：0.983M 参数在预算内但只有 PyTorch 权重、无公开 INT8；[S26] 的**局限**：论文与仓库的算力口径不自洽）。做法：对端侧档的论文，把"是否发布量化导出产物"作为可检索字段。验收：给出一张"参数达标 / 有导出产物"的交叉表，缺口数量化。
3. **缩小"能跑"与"能实时跑"之间那 2×**（源于 [S01] 的**局限**：实板 1.97× 时长、约 2 倍慢于实时；[S27] 的**局限**：门控已能做到 <1 ms/30 ms chunk，识别侧却慢 2×）。做法：把 [S01] 的调度与带宽优化思路与流式解码结合。验收：在同等无 NPU MCU 上做到 RTF ≤ 1，并报能耗。
4. **端上自适应的能耗账需要统一口径**（源于 [S14] 的**局限**：806 mJ / 14 s 是一次自适应的代价，频繁自适应在电池设备上不划算；[S15] 的**局限**：伪标签累积错误、无敏感性分析；[S09] 的**局限**：1.2 pp 精度差未必可接受）。做法：报"每恢复 1% 精度所需的能量与标注量"。验收：三条路径在同一数据集上给出该比值，可直接横比。
5. **开放词表的端侧下沿需要实测而非声明**（源于 [S02] 的**局限**：摘要未给具体基准数值、未给端侧实测延迟与功耗；[S28] 的**局限**：>300 MB 体积决定它只能进触发后短时档）。做法：对 99M/134M/356M 三档给出移动端实测的延迟、峰值内存与能耗。验收：三档各报三项，缺一项不算通过。
6. **真机失效清单化**（源于 [S16] 的**局限**：树莓派单平台、未给统一表；[S05] 的**局限**：预测器需按具体 MCU/软件栈标定）。做法：把热降频、麦克风质量、信号音量、量化产物缺失整理成端侧部署的检查表。验收：至少覆盖四项，每项给出探测方法。

## 9. 局限与未核实清单

### 9.1 语料与核实局限

- **29 篇里只有 1 篇读到全文**（[S29] WaveNorm）。[S01]–[S21] 全部是**摘要口径**，其数字只作量级与方向证据，**不参与跨行比较**（§2.2）。
- **未做硬件实测。** 所有延迟、功耗、RTF 均为原文或本仓域表转引；本综述未在真实设备上测量任何一项。
- **硬件档位功耗阶梯引用本仓既有域表**（`always-on-recording/hardware-power.md` §3 与三个领域表），按本仓约定"直接引用、不另起一套、不重算"，**未逐篇回原文复核**。
- **arXiv 三条检索式重叠严重**（合计 100 条命中，去重后 21 篇），检索面偏向 MCU/KWS 一族；移动 SoC 与专用硅两侧主要靠本仓域表与单篇补充，覆盖不均。
- **机器门禁的适用边界（必须声明）**：本综述用 `scripts/check_survey.py` 校验，但**该校验器是为 2026-10-18 的《音频智能体技术综述》定制的**——它按 `## 3.`–`## 7.` 的节号硬编码检查 APP / SER / AED / AGC / CROSS 五张固定列名矩阵。本篇按 LitReview S4 的规格用的是**方法族五列矩阵**（§6）与**任务侧四行表**（§7.4），结构与那五张表不同，因此残留 5 条 `matrix` 规则告警**属规则不适用，非内容缺失**；其余规则（检索日志、筛选台账、引用闭合、摘要口径声明、指标带条件、未来方向溯源、参考文献表计数 29=29）全部 0 违规。**不为凑绿而补五张无关矩阵**——那会让机器门禁失去意义。

### 9.2 未核实清单

- **[S02] Samsone 的基准数值**：摘要只有"该尺寸级 SOTA"的表述，**本综述不引用其任何数值**。
- **[S05] InstMeter 的音频任务数字**：只在"不同场景/MCU/软件设置"下评估，无单一音频任务数字；本综述只引用 3× / 6.5× / 100× 三个相对量。
- **[S09] EdgeSpike 的能量降低倍数**：摘要在该处被截断，具体倍数未取得；本综述只引用"91.4%、与 INT8 CNN 差 1.2 pp"。
- **[S13] DiTMoS 的数值**：摘要未给全，本综述不引用。
- **[S17] / [S18] / [S19] 的数值**：摘要口径且未给具体数值，本综述只引用其方法与结论方向。
- **[S26] GTCRN 的算力口径冲突**：仓库 48.2K 参数 / 33.0 MMACs 与论文 23.7K / 39.6 MMACs 不自洽，本综述**并列不裁决**。
- **[S29] 的参数量与每帧延迟**：论文只报 49M MACs 与 55 KB 内存，按本仓 `auto-gain/00` 裁定 4 **未做任何折算**；闭环指标（收敛时间、稳态误差、削波率）一项未报。

## 10. 参考文献

读法：文献、链接、年份取自 §3 台账与证据附录 §4 卡片；局限取自卡片 `局限` 字段。核验层级：`全文` 1 篇、`表格核实` 7 篇、`摘要` 21 篇。

| 编号 | 文献 | 年份 | 发表 venue | 链接 | 核验层级 | 局限 |
|---|---|---|---|---|---|---|
| S01 | Oído: Open-Vocabulary Speech Recognition on a $5 Microcontroller without a Neural Accelerator | 2026 | arXiv | https://arxiv.org/abs/2610.13447 | 摘要 | 约 2 倍慢于实时（1.97× 时长），不能流式；英文单语；ESP32-S3 单平台；未给整系统功耗 |
| S02 | Samsone: A Family of Open Small Audio Language Models for On-Device Inference | 2026 | arXiv | https://arxiv.org/abs/2609.21666 | 摘要 | 基准数值未核实；134M 进不了 MCU 档，"端侧"实指移动 SoC；未给端侧实测延迟与功耗 |
| S03 | Sub-mW Keyword Spotting on an MCU: Analog Binary Feature Extraction and Binary Neural Networks | 2022 | arXiv | https://arxiv.org/abs/2201.03386 | 摘要 | 需定制模拟电路，第三方 App 不可达；只到 KWS；未给整系统绝对功耗 |
| S04 | MicroNets: Neural Network Architectures for Deploying TinyML Applications on Commodity Microcontrollers | 2020 | arXiv | https://arxiv.org/abs/2010.11267 | 摘要 | 2020 年工作，工艺与工具链已迭代；op count 只是近似代理；无单一音频任务数字 |
| S05 | InstMeter: An Instruction-Level Method to Predict Energy and Latency of DL Model Inference on MCUs | 2026 | arXiv | https://arxiv.org/abs/2603.04134 | 摘要 | 预测器不降低任何能耗；需按具体 MCU/软件栈标定；无音频任务独立数字 |
| S06 | End-to-End Efficiency in Keyword Spotting: A System-Level Approach for Embedded Microcontrollers | 2025 | arXiv | https://arxiv.org/abs/2509.07051 | 摘要 | F1 的数据集与划分未明示；N6 依赖片上加速；只到 KWS |
| S07 | MambaLite-Micro: Memory-Optimized Mamba Inference on MCUs | 2025 | arXiv | https://arxiv.org/abs/2509.05488 | 摘要 | 只验证 KWS 与 HAR；未给延迟与能耗实测；C 手写算子换架构要重写 |
| S08 | Implementing Keyword Spotting on the MCUX947 Microcontroller with Integrated NPU | 2025 | arXiv | https://arxiv.org/abs/2506.08911 | 摘要 | 依赖片上 NPU，不可外推到通用 MCU；数据集未明示；只到 KWS |
| S09 | EdgeSpike: Spiking Neural Networks for Low-Power Autonomous Sensing in Edge IoT Architectures | 2026 | arXiv | https://arxiv.org/abs/2604.27004 | 摘要 | SNN 工具链成熟度低；1.2 pp 精度差未必可接受；五任务中只有 KWS 是音频；能量倍数摘要未给全 |
| S10 | Embedded Machine Learning for Microcontroller-Class Edge Devices | 2026 | arXiv | https://arxiv.org/abs/2606.18122 | 摘要 | 综合/教程性质，无独立实验；未给跨任务量化表 |
| S11 | LiCo-Net: Linearized Convolution Network for Hardware-efficient Keyword Spotting | 2022 | arXiv | https://arxiv.org/abs/2211.04635 | 摘要 | 2022 年；只到 KWS；"硬件效率"无统一量纲数字 |
| S12 | Keyword Spotting System and Evaluation of Pruning and Quantization Methods on Low-power Edge Microcontrollers | 2022 | arXiv | https://arxiv.org/abs/2208.02765 | 摘要 | 37 ms 为单平台口径（Cortex-M7 @216 MHz）；数据集未明示；未给量化后精度损失 |
| S13 | DiTMoS: Delving into Diverse Tiny-Model Selection on Microcontrollers | 2024 | arXiv | https://arxiv.org/abs/2403.09035 | 摘要 | 数值未核实；路由有额外开销；多分类器总参数可能反而上升 |
| S14 | On-Device Domain Learning for Keyword Spotting on Low-Power Extreme Edge Embedded Systems | 2024 | arXiv | https://arxiv.org/abs/2403.10549 | 摘要 | 冷启动仍需 100 条标注；806 mJ / 14 s 意味着不能频繁自适应；只到 KWS |
| S15 | Self-Learning for Personalized Keyword Spotting on Ultra-Low-Power Audio Sensors | 2024 | arXiv | https://arxiv.org/abs/2408.12481 | 摘要 | 伪标签累积错误；0.5M 参数上限；相似度阈值无敏感性分析 |
| S16 | Environmental Sound Classification on An Embedded Hardware Platform | 2023 | arXiv | https://arxiv.org/abs/2306.09106 | 摘要 | 树莓派属通用 AP 档，外推有限；未给统一精度/延迟表 |
| S17 | Tiny-Align: Bridging Automatic Speech Recognition and Large Language Model on the Edge | 2024 | arXiv | https://arxiv.org/abs/2411.13766 | 摘要 | "边缘"档位未明示；端上训练能耗未给；数值未核实 |
| S18 | Wireless Hearables With Programmable Speech AI Accelerators（NeuralAids） | 2025 | arXiv | https://arxiv.org/abs/2503.18698 | 摘要 | 数值未核实；助听器档可迁移性待验；依赖厂商开放可编程加速器 |
| S19 | Towards Privacy-Preserving Audio Classification Systems | 2024 | arXiv | https://arxiv.org/abs/2404.18002 | 摘要 | "隐私保护"定义与可验证性需明确；未给与不保护基线的精度差 |
| S20 | Robust Wake-Up Word Detection by Two-stage Multi-resolution Ensembles | 2023 | arXiv | https://arxiv.org/abs/2310.11379 | 摘要 | 无具体数值；端上结果不是最终判定；仍需上云（哪怕只传特征） |
| S21 | Selective Attention System (SAS): Device-Addressed Speech Detection for Real-Time On-Device Voice | 2026 | arXiv | https://arxiv.org/abs/2604.08412 | 摘要 | 加摄像头换 0.09 F1，功耗与旁观者合规代价未计；60 小时英语单语 |
| S22 | YAMNet（3.7M，MobileNetV1 + 521 类头） | 2017 | 官方仓库（Google AI Edge） | https://github.com/tensorflow/models/tree/master/research/audioset/yamnet | 表格核实 | 521 类固定词表，加类要重训；~72 MMACs/s 在常驻档偏贵；mAP 需标 AS-20K 或 AS-2M full |
| S23 | EfficientAT（mn10_as，0.983M / 11 MMACs/s） | 2022 | 官方仓库 | https://github.com/fschmid56/EfficientAT | 表格核实 | **只有官方 PyTorch 权重、未见公开 INT8 发布**——"参数达标 ≠ 端侧有产物" |
| S24 | DCASE2025 Task 1 baseline（低复杂度 ASC） | 2025 | 官方仓库（DCASE baseline） | https://github.com/CPJKU/dcase2025_task1_baseline | 表格核实 | 10 类 ASC 不是事件检测，不可与 mAP/PSDS 同表；53.24% 的 split 未在 README 复现；25% 标签使精度与标签效率混在一起 |
| S25 | RNNoise（0.085M，C 定点） | 2017 | 官方仓库 | https://github.com/xiph/rnnoise | 表格核实 | 输出掩码不改整体电平（非 AGC）；42 维特征单通道 |
| S26 | GTCRN（0.048M，ONNX Runtime Mobile INT8） | 2023 | 官方仓库 | https://github.com/Xiaobin-Rong/gtcrn | 表格核实 | 8 kHz 以上高频事件救不回；**仓库 48.2K/33.0 MMACs 与论文 23.7K/39.6 MMACs 不自洽** |
| S27 | Silero VAD（约 2 MB，ONNX） | 2021 | 官方仓库 | https://github.com/snakers4/silero-vad | 表格核实 | 是门控不是识别器；阈值需按场景标定；"CPU"未指明具体型号 |
| S28 | CLAP（音频–文本对比学习，约 86M+） | 2022 | 官方仓库（LAION） | https://github.com/LAION-AI/CLAP | 表格核实 | 体积 >300 MB，只能进触发后短时档、不能常驻；开放词表精度通常低于同规模闭集 |
| S29 | WaveNorm: A Low-Complexity Time-Domain Neural Adaptive Gain Control | 2026 | Interspeech | https://www.isca-archive.org/interspeech_2026/ijjada26_interspeech.html | 全文 | **参数量与每帧延迟实测均未给出**；闭环指标零报告；实验在文件级语料上做，未验证真实采集链路的二次增益风险 |
