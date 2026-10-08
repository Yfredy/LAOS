# 音频事件模型 —— 小型档（参数量 < 30M）

> 口径来源：`docs/research/audio-events/00-taxonomy-and-metrics.md`（12 列表头、规模分档、AudioSet 划分口径、红线均以该文件为准）。
> 本档边界：小型 = **< 30M**（含音频编码器，量化前，左闭右开，30M 归中型）。
> 本档只做检索与核实，不做选型结论；`edge` 一栏只记录**已核到的公开证据**，且按口径文件规定由 Task 5（`05-edge-deployment.md`）回填。
> **AudioSet 引用声明**：凡预训练/评测语料为 AudioSet 的条目，其音频本体为 YouTube 视频且**官方已停止分发完整包**，实际复现只能依赖第三方镜像或官方/第三方预计算 embedding。

---

## Part 1 · 数据表

| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| YAMNet | tensorflow/models @master `research/audioset/yamnet/yamnet.h5`（MobileNetV1 主干 + 521 类 logistic 头） | 3.7 | A | AudioSet AS-2M full（本体不可直接获取，复现依赖第三方镜像或预计算 embedding） | tagging/521类 | AudioSet AS-2M full | mAP 0.306 / d′ 2.318 / lwlrap 0.393 (AudioSet AS-2M full, tagging)；69.2 MMACs/960ms ≈ 72 MMACs/s | Apache-2.0（tensorflow/models 仓库根 LICENSE） | yes | yes: TFLite INT8（Keras→TFLite 官方导出路径；具体 runtime 与实测由 Task 5 回填） | https://github.com/tensorflow/models/tree/master/research/audioset/yamnet |
| EfficientAT-mn04_as | `mn04_as`，MobileNetV3 width_mult=0.4，ImageNet 预训练后 ImageNet→AudioSet，PaSST 离线蒸馏 | 0.983 | A | AudioSet AS-2M full + ImageNet（同上本体不可直接获取） | tagging/527类 | AudioSet AS-2M full | mAP 0.432 (AudioSet AS-2M full, tagging)；0.11 GMACs/10s ≈ 11 MMACs/s（论文 MACs 按 10 秒片段口径） | MIT | yes | unknown(未找到公开转换案例) | https://github.com/fschmid56/EfficientAT；https://arxiv.org/abs/2211.04772 |
| EfficientAT-mn05_as | `mn05_as`，MobileNetV3 width_mult=0.5 | 1.43 | A | AudioSet AS-2M full + ImageNet | tagging/527类 | AudioSet AS-2M full | mAP 0.443 (AudioSet AS-2M full, tagging)；0.16 GMACs/10s ≈ 16 MMACs/s | MIT | yes | unknown(未找到公开转换案例) | https://github.com/fschmid56/EfficientAT；https://arxiv.org/abs/2211.04772 |
| EfficientAT-mn10_as | `mn10_as`，MobileNetV3 width_mult=1.0 | 4.88 | A | AudioSet AS-2M full + ImageNet | tagging/527类 | AudioSet AS-2M full | mAP 0.471 (AudioSet AS-2M full, tagging)；0.54 GMACs/10s ≈ 54 MMACs/s | MIT | yes | unknown(未找到公开转换案例) | https://github.com/fschmid56/EfficientAT；https://arxiv.org/abs/2211.04772 |
| EfficientAT-mn20_as | `mn20_as`，MobileNetV3 width_mult=2.0 | 17.91 | A | AudioSet AS-2M full + ImageNet | tagging/527类 | AudioSet AS-2M full | mAP 0.478 (AudioSet AS-2M full, tagging)；2.06 GMACs/10s ≈ 206 MMACs/s | MIT | yes | unknown(未找到公开转换案例) | https://github.com/fschmid56/EfficientAT；https://arxiv.org/abs/2211.04772 |
| EfficientAT-dymn04_as | `dymn04_as`，Dynamic MobileNet（Dy-Conv+Dy-ReLU+Coordinate Attention）width_mult=0.4 | 1.97 | A | AudioSet AS-2M full + ImageNet | tagging/527类 | AudioSet AS-2M full | mAP 0.450 (AudioSet AS-2M full, tagging)；0.12 GMACs/10s ≈ 12 MMACs/s | MIT | yes | unknown(未找到公开转换案例) | https://github.com/fschmid56/EfficientAT；https://arxiv.org/abs/2310.15648 |
| EfficientAT-dymn10_as | `dymn10_as`，Dynamic MobileNet width_mult=1.0 | 10.57 | A | AudioSet AS-2M full + ImageNet | tagging/527类 | AudioSet AS-2M full | mAP 0.477 (AudioSet AS-2M full, tagging)；0.58 GMACs/10s ≈ 58 MMACs/s | MIT | yes | unknown(未找到公开转换案例) | https://github.com/fschmid56/EfficientAT；https://arxiv.org/abs/2310.15648 |
| PANNs-CNN6 | Table I/XI/XII 的 CNN6（4,837,455 参数；默认 `full_train` + balanced 采样） | 4.84 | A | AudioSet AS-2M full（同上本体不可直接获取） | tagging/527类 | AudioSet AS-2M full | mAP 0.343 (AudioSet AS-2M full, tagging)；21.99 G multi-adds/10s ≈ 2199 MMACs/s（按 multi-add≈MAC 折算） | GitHub 仓库未包含 LICENSE 文件（许可未明示） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/1912.10211；https://github.com/qiuqiangkong/audioset_tagging_cnn |
| PANNs-CNN10 | Table I/XI/XII 的 CNN10（5,219,279 参数） | 5.22 | A | AudioSet AS-2M full | tagging/527类 | AudioSet AS-2M full | mAP 0.380 (AudioSet AS-2M full, tagging)；28.17 G multi-adds/10s ≈ 2817 MMACs/s | GitHub 仓库未包含 LICENSE 文件（许可未明示） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/1912.10211；https://github.com/qiuqiangkong/audioset_tagging_cnn |
| PANNs-MobileNetV1 | Table XI/XII 的 MobileNetV1（4,796,303 参数） | 4.80 | A | AudioSet AS-2M full | tagging/527类 | AudioSet AS-2M full | mAP 0.389 (AudioSet AS-2M full, tagging)；3.61 G multi-adds/10s ≈ 361 MMACs/s | GitHub 仓库未包含 LICENSE 文件（许可未明示） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/1912.10211；https://github.com/qiuqiangkong/audioset_tagging_cnn |
| PANNs-MobileNetV2 | Table XI/XII 的 MobileNetV2（4,075,343 参数） | 4.08 | A | AudioSet AS-2M full | tagging/527类 | AudioSet AS-2M full | mAP 0.383 (AudioSet AS-2M full, tagging)；2.81 G multi-adds/10s ≈ 281 MMACs/s | GitHub 仓库未包含 LICENSE 文件（许可未明示） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/1912.10211；https://github.com/qiuqiangkong/audioset_tagging_cnn |
| PANNs-LeeNet11 | Table XI/XII 的 LeeNet11（748,367 参数，本档最小） | 0.748 | A | AudioSet AS-2M full | tagging/527类 | AudioSet AS-2M full | mAP 0.266 (AudioSet AS-2M full, tagging)；4.74 G multi-adds/10s ≈ 474 MMACs/s | GitHub 仓库未包含 LICENSE 文件（许可未明示） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/1912.10211；https://github.com/qiuqiangkong/audioset_tagging_cnn |
| PANNs-LeeNet24 | Table XI/XII 的 LeeNet24（10,003,791 参数） | 10.00 | A | AudioSet AS-2M full | tagging/527类 | AudioSet AS-2M full | mAP 0.336 (AudioSet AS-2M full, tagging)；26.37 G multi-adds/10s ≈ 2637 MMACs/s | GitHub 仓库未包含 LICENSE 文件（许可未明示） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/1912.10211；https://github.com/qiuqiangkong/audioset_tagging_cnn |
| DCASE2025 Task1 baseline（简化 CP-Mobile） | `dcase2025_task1_baseline`；61,148 参数，推理时转 fp16（122,296 B），PyTorch+Lit 训练，Freq-MixStyle | 0.0611 | A | 无外部预训练（TAU Urban 2022 Mobile train，仅 25% 标签） | ASC/10类 | DCASE2025 Task1（TAU Urban Acoustic Scenes 2022 Mobile） | 53.24% 宏平均准确率 (DCASE2025 Task1, ASC)；29.42 MMACs/1s；fp16 权重 122,296 B | GitHub 仓库未包含 LICENSE 文件（许可未明示） | yes | unknown(未找到公开转换案例) | https://github.com/CPJKU/dcase2025_task1_baseline；https://dcase.community/challenge2025/task-low-complexity-acoustic-scene-classification-with-device-information-results |
| CP-Mobile（设备感知蒸馏，DCASE2025 Task1 官方第 1 名） | `MALACH25_4`（CP-Mobile 学生；CP-ResNet+BEATs 教师贝叶斯集成蒸馏；CochlScene 域内预训练；逐设备全量微调） | 0.0611 | A | CochlScene（外部 ASC 数据）+ AudioSet 预训练 PaSST 教师 | ASC/10类 | DCASE2025 Task1（TAU Urban Acoustic Scenes 2022 Mobile） | 61.47% 宏平均准确率 (DCASE2025 Task1, ASC)；29.42 MMACs/1s；fp16 122 kB | 未找到公开权重/显式许可（仅有官方技术报告与榜单） | no | unknown(未找到公开转换案例) | https://arxiv.org/abs/2505.01747；https://dcase.community/challenge2025/task-low-complexity-acoustic-scene-classification-with-device-information-results |
| Tan_SNTLNTU（DCASE2025 Task1 官方第 2 名，CNN-GRU） | 低算力提交，架构 CNN-GRU；116,342 参数，官方 Size 116,342 B（≈1 B/参数）；Complexity management 标注 precision_16 + network design | 0.1163 | A | IR（脉冲响应增强，非外部预训练语料） | ASC/10类 | DCASE2025 Task1（TAU Urban Acoustic Scenes 2022 Mobile） | 59.94% 宏平均准确率 (DCASE2025 Task1, ASC)；10.90 MMACs/1s（本表 ASC 段唯一远低于 30 MMACs 上限却仍列前二的系统） | 未找到公开权重/显式许可（仅有官方技术报告与榜单） | no | unknown(未找到公开转换案例) | https://arxiv.org/abs/2505.01747；https://dcase.community/challenge2025/task-low-complexity-acoustic-scene-classification-with-device-information-results |
| DynaCP（Luo_CQUPT，DCASE2025 Task1 官方第 3 名） | `cquptlyd/DynaCP`；61,650 参数 fp16（123,300 B），约 28.94 MMACs | 0.0617 | A | DCASE2025 官方允许的外部数据 + 知识蒸馏 | ASC/10类 | DCASE2025 Task1（TAU Urban Acoustic Scenes 2022 Mobile） | 59.58% 宏平均准确率 (DCASE2025 Task1, ASC)；28.94 MMACs/1s；fp16 123 kB | GitHub 仓库未包含 LICENSE 文件（许可未明示） | yes | unknown(未找到公开转换案例) | https://github.com/cquptlyd/DynaCP；https://arxiv.org/abs/2505.01747 |
| CP-Mobile（Schmid_CPJKU，DCASE2023 Task1 **官方榜首** 系统） | `task1_2`；12,310 参数（Memory use 12,310 B，≈1 B/参数）；复杂度管理标注 knowledge distillation + weight quantization | 0.0123 | A | 无外部预训练（TAU Urban 2022 Mobile train） | ASC/10类 | DCASE2023 Task1（TAU Urban Acoustic Scenes 2022 Mobile） | 58.7% 宏平均准确率 / logloss 1.256 (DCASE2023 Task1, ASC)；4.35 MMACs/1s | GitHub 仓库未包含 LICENSE 文件（许可未明示） | yes | unknown(未找到公开转换案例) | https://github.com/roboav8r/cpjku_dcase23；https://dcase.community/challenge2023/task-low-complexity-acoustic-scene-classification-results |
| CP-Mobile 高算力变体（同队 `task1_4`，DCASE2023 当年最高准确率） | `task1_4`（同一代码库，加宽/结构化剪枝配置）；54,182 参数 int8 | 0.0542 | A | 无外部预训练（TAU Urban 2022 Mobile train） | ASC/10类 | DCASE2023 Task1（TAU Urban Acoustic Scenes 2022 Mobile） | 62.7% 宏平均准确率 / logloss 1.117 (DCASE2023 Task1, ASC)；16.80 MMACs/1s | GitHub 仓库未包含 LICENSE 文件（许可未明示） | yes | unknown(未找到公开转换案例) | https://github.com/roboav8r/cpjku_dcase23；https://dcase.community/challenge2023/task-low-complexity-acoustic-scene-classification-results |

**表内说明**

- **跨任务类型不可直接比较。** 本表同时含 **tagging**（AudioSet mAP）与 **ASC**（DCASE 准确率）两类：mAP 与准确率不是一个量纲，**禁止放在一起比大小**。表中两类记录已分段排列，请勿跨段横向比数字。
- **AudioSet 全部按 AS-2M full 记。** 依据：PANNs 仓库训练脚本默认 `--data_type='full_train'`（配 `--balanced='balanced'` 的**类均衡采样**，不是 balanced 子集）；EfficientAT / DyMN 的训练数据为 AudioSet 全集（含 unbalanced），其 MACs 按 **10 秒**片段统计——论文原文："The number of MACs is calculated on 10-second audio recordings"。**本表未收录任何 AS-20K / balanced 子集口径的数字**，因此不存在"差 15 点"的口径混入。
- **MMACs/秒是折算值，不是原文数字。** PANNs 报的是 multi-adds（×10⁹/10 s），EfficientAT 报的是 GMACs（/10 s）。折算为 MMACs/s 时假设 **multi-add ≈ MAC**（保守，若为"乘+加=2 op"则真实 MACs 再高 2 倍）且**MACs 随时长线性**。DCASE 系列的 MMACs 是官方按 1 秒定义、torchinfo 统计的原生值，**两者不可直接等同**——PANNs/EfficientAT 的数字**不含 CUDNN/BLAS 实现开销也不含 mel 滤波器组前端**。
- **`128K` 是 128 KiB，不是 128K 个参数。** DCASE 官方规则原文："A model complexity limit of 128 KB is set for the non-zero parameters. This translates into 32768 parameters when using float32." 即：fp32 → 32,768 参数；fp16 → 65,536 参数；int8 → 131,072 参数。读本表 DCASE 段的参数列时必须同时看两个事实：(a) **同一份 128 KiB 预算能装的参数个数随存储精度差 4 倍**，孤立看"参数多少"没有意义；(b) **特征提取不进复杂度账**——DCASE2021 规则明确"特征提取阶段的计算复杂度不计入限制"，而 log-mel 前端在 1 秒 44.1 kHz 音频上本身就要几十 MMACs，落地时必须把它加回去。
- **PANNs / CPJKU / DynaCP 三个仓库都没有 LICENSE 文件**（查过 main 与 master 分支的 LICENSE / LICENSE.txt / LICENSE.md）。这不是占位符，是一条**对 Task 7 有用的负信息**：这些是本档最常被引用的权重/代码，但缺乏明示授权。
- **本档的两处空白（如实记录，不给数字）**：
  1. **SED（<30M）**：未找到同时给出「参数量 + PSDS + 许可」三项、且能被原文核实的小模型记录。DCASE2022 Task4（Sound Event Detection in Domestic Environments）官方结果页只报 PSDS1/PSDS2 与 F-score，**不含参数量列**，因此其 SED 系统（含 baseline）无法落入本 schema。
  2. **开放词表（<30M）**：本档未检索到 <30M 且带零样本 mAP/PSDS 的可核验记录；小型开放词表方向留给 Task 6（多模态线）判定。
- `edge` 列除 YAMNet 外全部为 `unknown(未找到公开转换案例)`——这是口径文件的合法值，表示"我没找到证据"，不等于"不能部署"。**按计划该文件由 Task 5 回填**，本档不越权下结论。

**因缺少可靠来源而删除的候选（不写入表）**

| 候选 | 删除原因 |
| --- | --- |
| DCASE2024 Task1 团队系统（Han_SJTUTHU / Cai_XJTLU / MALACH24_JKU 等） | 官方结果页有完整准确率与参数/MMACs，但**未找到对应的公开代码或权重仓库**；仅官方榜单数字无法满足「来源列须含 arXiv/HF/GitHub」的可核验要求。其数字改写入 Part 2 的逐年表（带官方结果页 URL） |
| DCASE2021 / 2022 Task1 团队系统（Kim_QTI、Chang_HYU 等） | 同上：只有官方榜单与技术报告 PDF（托管在 dcase.community），无可核验的 arXiv/GitHub 出处 |
| DCASE2022 / 2023 / 2024 Task1 baseline | 2024 baseline 仓库（github.com/CPJKU/dcase2024_task1_baseline）确实存在，但 **2022/2023 baseline 没有对应的公开仓库**，无法每条独立背书；且 **2024 与 2025 baseline 是同一份 61,148 参数 / 29.42 MMACs 配置**，主表只收 2025 一行以免重复计数，各年 baseline 数字统一写进 Part 2 逐年表 |
| FRILL / TRILLsson（10.1M / 5.0M / 8.1M / 21.5M） | 参数量可核（arXiv 2011.04609、2203.00236），但官方报的是 **NOSS 情感/说话人**指标，**未检索到 AudioSet tagging 的 mAP 数字**，落不进本表 `指标` 列（已在 SER 小型档 `01-small-models.md` 收录，此处不重复） |
| MicroNets（MCU NAS） | 官方任务的收益集中在 **keyword spotting / Speech Commands**，与 AED 四个任务类型都不对应，且未检索到 AudioSet tagging 数字 |
| LEAF + 小 CNN | 未检索到同时给出「<30M 参数量 + AudioSet 划分标注的指标 + 权重许可」的公开条目 |
| BC-ResNet 系（2025 榜单出现的 BC-Resnet-1 等） | 只在 DCASE2023/2025 技术报告 PDF 里出现（如 `DCASE2023_Krishna_8_t1.pdf` 报 BC-Resnet-1 49.94%），**无 arXiv/GitHub 可核验出处**；其参数写作 7.4K 且 protocol 与榜单不同，暂不收录 |
| VGGish / COALA 等 | VGGish 特征提取器参数量约 62M，按左闭右开属**中型档**，不在本文件范围；其余候选未检索到本档可核验的「参数量 + 指标 + 许可」三项 |

---

## Part 2 · 128K 参数 / 30 MMACs 约束下能做什么

> 本节三问的答案都建立在**官方 DCASE 榜单**（task description + Results + System complexity 三页）与**原论文表格**上；
> 逐年数字来自不同年份的不同规则，**跨年不可直接比**，逐年表已把每年的规则差异写在备注列。

### 2.1 该约束下 ASC 准确率逐年变化

| 年份·任务设定 | Baseline 准确率 | 当年最高准确率 | 最高/榜首系统（参数 · MMACs） | 备注（为何跨年不可比） |
| --- | --- | --- | --- | --- |
| 2021 Task1A 低复杂度 ASC 多设备 | 45.6%（46,246 参数，90.3 KB） | **76.1%**（Kim_QTI `ResNorm_QTI2`） | 95,472 非零参数（总 630,042，稀疏度 84.8%） | 数据集为 **TAU 2020 Mobile**（10 秒片段），与 2022 起的 TAU 2022 Mobile（1 秒片段）不同；当年**不统计 MMACs** |
| 2022 Task1 低复杂度 ASC | 44.2%（46,512 参数 / 29.23 MMACs） | **60.8%**（Chang_HYU `JH_PM_HYU1`） | 126,580 参数 / 26.76 MMACs | 换成 TAU 2022 Mobile；**强制 8-bit 量化** |
| 2023 Task1 低复杂度 ASC（泛化） | 44.8%（46,512 参数 / 29.23 MMACs） | **62.7%**（Schmid_CPJKU `task1_4`） | 54,182 参数 / 16.80 MMACs | 官方名次是「准确率序 + memory 序 + MACs 序」的平均秩，**第 1 名（58.7%）不是准确率最高的那一版** |
| 2024 Task1 数据高效低复杂度 ASC | 56.8%（100% 子集；61,148 参数 / 29.42 MMACs） | **62.1%**（Cai_XJTLU `TFSN t=3`，100% 子集） | 126,858 参数 / 29.42 MMACs | 主打 5 个训练子集（5/10/25/50/100%），官方名次靠 **Rank score**；团队第 1（Han_SJTUTHU）100% 子集 61.8% |
| 2025 Task1 带设备信息的低复杂度 ASC | 53.2%（61,148 参数 / 29.42 MMACs） | **61.5%**（Karasin_JKU `MALACH25_4`） | 61,148 参数 / 29.42 MMACs | **只给 25% 标签**，推理时给设备 ID；可用公开外部数据 |

**答 1（一句话）：** 在口径可对齐的 2022–2025 四年里，128 KiB/30 MMACs 约束下的最高准确率一直在 **60.8% → 62.7% → 62.1% → 61.5%** 的窄带里，**没有趋势性提升**；真正逐年上升的是**官方基线**（44.2% → 53.2%，+9 个点）和"少标签 / 跨设备"这些附加能力，而不是天花板本身（2021 的 76.1% 属于另一数据集且不计 MACs，与本段**不可直接比较**）。

### 2.2 约束内模型能否迁移到 tagging / SED

**答 2（一句话）：不能直接用——同一个 30 MMACs 预算里早就存在可用的 tagging 模型（mn04_as 11 MMACs/s 拿到 mAP 0.432、dymn04_as 12 MMACs/s 拿到 mAP 0.450），真正卡住 tagging 的不是算力而是 128 KiB 的参数预算（0.983M 是 int8 上限 131,072 的 7.5 倍）；SED 这一侧本档找不到可核验的 <30M 记录，因此不给数字。**

三条支撑（推导都写明假设）：

1. **输出层这一笔账在 128 KiB 里就付不起。**
   假设：分类头是单层线性（忽略偏置），嵌入维度取 D。
   - ASC 头：`D×10`。DCASE2025 baseline 用一个 `Conv2d` 就把 10 类做完了（`ff_list[0]` 仅 1,040 参数），整模参数合计 61,148。
   - 换成 **527 类**：`128×527 = 67,456` 参数 → **fp16（2 B）就是 135 KB，已经超过 128 KiB 全部预算**；即使压到 **int8（1 B）也要 67 KB，占掉一半预算**，还没算主干。
   - 若保持 EfficientAT 那种较宽的嵌入（例如 1,024-d）：`1024×527 ≈ 539K` 参数 → int8 也要 539 KB，**是预算的 4 倍以上**。
   - 结论：softmax 下"10 类共用一个 1,040 参数的头"，改成 sigmoid 后类与类不再共享——**类数从 10 涨到 527，单是最后一层就从"可以忽略"变成"占满甚至撑爆预算"**。
2. **损失函数与推理逻辑不同，不是换个 head 就行。** ASC 是独占单类 + softmax（各类互斥、argmax 取一个）；tagging 是多标签 + sigmoid + **逐类阈值**。ASC 模型在结构上被训练成"只挑一类"，把它直接当 521 路打分器用，即使把头换了，主干学到的也是"最能区分场景的特征"而不是"某个事件是否出现"，且**阈值标定要从零重做**。这一点与 00 口径 §「任务类型」的三条硬规定一致。
3. **SED 需要时间定位，成本再高一档，且本档无数据。** SED 要求输出起止时间，等于把"整段一个决策"换成"逐帧决策"，必然比 tagging 再贵一截；DCASE2022 Task4 官方结果页**只报 PSDS1/PSDS2/F-score，不报参数量**，本档找不到任何"参数量 + PSDS + 许可"三项俱全的可核验 <30M 条目。**因此本档对 SED 不给数字，不做外推。**

### 2.3 参数量与 MMACs 哪个才是真瓶颈

先给定义：**记 ρ = 一次 1 秒推理中平均每个参数被调用的次数 = MMACs / 参数个数。**

从 **DCASE2025 baseline 的官方逐层参数/MACs 表**可以直接读（这份表是逐层给的，不是估算）：

| 层 | 参数 | MACs | ρ = MACs/参数 |
| --- | --- | --- | --- |
| `in_c[0]` Conv2dNormActivation（输入 256×65 log-mel） | 88 | 304,144 | 3,456 |
| `in_c[1]` Conv2dNormActivation（输入 128×33） | 2,368 | 2,506,816 | 1,059 |
| 全模型 Sum | 61,148 | 29,419,156 | **≈ 481** |

推导（假设全部写明）：

- **假设 A**：输入为 1 秒 log-mel `[256 帧 × 65 mel]`，DCASE 的 30 MMACs 上限按 1 秒定义；MACs 由 torchinfo 统计（官方声明）。
- **假设 B**：ρ 与精度无关（同一结构下参数调用次数不变），且**近似不随模型微调改变**（用它估量级，不当精确值）。
- **假设 C**：128 KiB 存储预算下的可用参数上限为 `N_max = 131072 / (b/8) = 1048576 / b`（b = 每参数位数）。

把 `N_max` 用满时会产生 `N_max × ρ` 个 MAC，与 30 MMACs 上限对比：

| 精度 b | 允许参数 N_max | N_max × ρ（ρ≈481） | 与 30 MMACs 上限的关系 |
| --- | --- | --- | --- |
| fp32（32 bit） | 32,768 | ≈ 15.8 MMACs | MMACs 上限（30）还没到，参数先用完——**参数预算先到顶** |
| fp16（16 bit） | 65,536 | ≈ 31.5 MMACs | **两条线几乎同时到顶** |
| int8（8 bit） | 131,072 | ≈ 63.0 MMACs | 可用 **2.1 倍以上是算力富余**——**MMACs 成为唯一瓶颈** |

这张表的意思是：**在 fp16 这一档（赛道多数系统用的就是它），两条预算恰好同时到顶**——这也解释了为什么 2024/2025 榜单上多数系统都挤在 **61,148–63,748 参数 / 29.4 MMACs** 这个点上（fp16 允许上限是 65,536 参数）。低于这个交叉点，加参数还能涨点；高于它，每多一个参数都要多付 ρ≈481 次乘加，30 MMACs 就先红了。（例外也印证规则：2025 年第 2 名 Tan_SNTLNTU 反其道而行，把 MACs 压到 10.9 才换到 116,342 参数的预算空间，准确率仍保持在 59.94%。）

而两组"同参数 / 不同 MACs"的横向对照说明：真要二选一，**砍 MACs 的代价远大于砍参数**。

- DCASE2023，Schmid_CPJKU 同一份代码库的两个提交：官方第 1 名 `task1_2` 是 **12,310 参数 / 4.35 MMACs → 58.7%**；准确率更高的 `task1_4` 是 **54,182 参数 / 16.80 MMACs → 62.7%**，官方名次反而落到第 3（2023 的名次是"准确率序 + memory 序 + MACs 序"的平均秩）。同一训练集、同一架构下，**多花 4.4× 参数、3.9× MACs 只换来 4.0 个点**。
- DCASE2025，Han_CSU 的 `KDTF-SepN` 系列：参数 **61,148（与 baseline 完全相同）**，但只用 **0.299 MMACs**——最好成绩 **32.6%**，而同样参数量、用满 29.42 MMACs 的 baseline 是 53.2%。**参数一模一样、MACs 砍到 1/100，准确率掉 20 个点以上。**

**答 3（一句话）：这两个预算在赛道实际采用的 fp16 处恰好同时到顶（交叉点 ≈ 62K 参数 / 30 MMACs，所以所有好系统都挤在 61,148 参数上），但如果必须说谁先卡死——fp16 及以下 MMACs 是硬约束（int8 时参数预算还富余 2.1 倍却用不掉），fp32 时才轮到参数先到顶；换成 527 类多标签 tagging 则整个反转，参数才是瓶颈：mn04_as 只用 11 MMACs/s（离 30 上限还很远）参数就已经是 0.983M，是 int8 预算 131,072 的 7.5 倍。所以"128K 参数能跑到 60% ASC 准确率"推不出"128K 参数也能做 521 类 tagging"——换任务是会换瓶颈的。**

给 Task 5 / Task 7 的落地提示：**laos 若要复用这个赛道的能力，真正要问的是"在多短的分析窗里能花多少 MMACs/s"，而不是"模型有多少参数"**——因为 feature extraction 不进 DCASE 的账，而 log-mel 前端在常驻采集的场景里恰好是一笔真金白银的开销。

---

## 红线自检

- **可核验性**：19 条记录全部带 `arxiv.org` / `github.com` 链接；凡缺可核验出处、或数字无法回溯原文者一律删除，删除理由见「因缺少可靠来源而删除的候选」。
- **无裸数字**：所有指标都带「基准名 + 任务类型」；AudioSet 一律标 `AudioSet AS-2M full`，本文件未使用 AS-20K 数字。
- **跨类型不混比**：tagging 与 ASC 分段记录，并在表内说明处显式写明"禁止放在一起比大小"；Part 2 逐年表把每年的规则差异写在备注列。
- **AudioSet 现实性**：文件抬头与表格相应行都写明"本体不可直接获取，依赖第三方镜像或预计算 embedding"。
- **中文空白不冒充**：Part 1 表内说明如实记录 SED（<30M）与开放词表（<30M）两处无数据；DCASE TAU Urban 数据集为欧洲 12 城市，**不代表中文家庭环境事件分布**（后果由 Task 7 记录）。
- **声纹**：本档未引入任何带说话人识别/验证能力的模型。
- **许可诚实性**：PANNs / CPJKU / DynaCP 三个仓库确实没有 LICENSE 文件，已如实写成"仓库未包含 LICENSE 文件（许可未明示）"而非 Apache/MIT 补全。
