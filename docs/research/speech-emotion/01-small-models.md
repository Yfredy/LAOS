# 声学情感模型 —— 小型档（参数量 < 30M）

> 口径来源：`docs/research/speech-emotion/00-taxonomy-and-metrics.md`（分层边界、12 列表头、红线均以该文件为准）。
> 本档边界：小型 = **< 30M**（含音频编码器，量化前，左闭右开，30M 归中型）。
> 本档只做检索与核实，不做推荐结论；`edge` 一栏只记录**已核到的公开证据**，不是可行性判断。

---

## Part 1 · 数据表

| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| YAMNet | tensorflow/models v1（AudioSet 权重） | 3.7 | A | AudioSet（521 类音频事件） | 521 类事件 logits / 1024-d embedding，非情感专用 | SERAB（9 数据集跨库平均）、IEMOCAP | Acc 56.1 (IEMOCAP 4类)，55.1 (SERAB 跨库平均) | Apache-2.0 | yes | yes: TFLite / ONNX / QNN，w8a8 + w8a16 档齐全（AI Hub 实测 0.096–0.699 ms） | arxiv.org/abs/2110.04621 表1（3.7M）；arxiv.org/abs/2110.03414 表3（指标）；github.com/tensorflow/models |
| openSMILE ComParE_2016 + 线性分类器 | opensmile 3.0 / ComParE_2016 特征集（6,373 维） | n/a(非神经) | A | 无（纯信号处理特征，不需预训练语料） | 6,373 维声学特征，下游接线性 SVM | SERAB、IEMOCAP、MER2024 | Acc 62.1 (IEMOCAP 4类)，70.2 (SERAB 跨库平均)；WAF 39.68 (MER2024 中文，eGeMAPS 88 维版本) | 双许可：非商业/研究/教育免费，商业产品需另获授权 | yes | yes: 原生 C++ 库，无需量化，MCU 可直接运行 | github.com/audeering/opensmile；arxiv.org/abs/2110.03414 表3；arxiv.org/abs/2408.10500 |
| TRILL | layer19 / Resnetish50（nonsemantic-speech-benchmark） | 24.5 | A | AudioSet 语音子集（自监督时序邻近） | 2048-d 帧级 embedding（layer19 为 12,288 维拼接） | SERAB、NOSS | Acc 57.7 (IEMOCAP 4类)，69.0 (SERAB 跨库平均)；55.4 (IEMOCAP, NOSS)，65.7 (CREMA-D, NOSS) | Apache-2.0 | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2110.04621 表1；arxiv.org/abs/2110.03414 表3；github.com/google-research/google-research |
| FRILL | frill/1（TF Hub；MobileNetV3 alpha=2.0 + GAP） | 10.1 | A | AudioSet 语音子集（约 90 万条），蒸馏自 TRILL | 2048-d 帧级 embedding | NOSS | Acc 70.9 (CREMA-D)，67.5 (SAVEE) | Apache-2.0 | yes | yes: TFLite fp32 38.5 MB / QAT INT8，Pixel 1 单次 8.5 ms | arxiv.org/abs/2011.04609；arxiv.org/abs/2110.04621 表1（10.1M） |
| TRILLsson 1 | trillsson1（ResNetish，TF Hub） | 5.0 | A | 公开语料蒸馏自 CAP12（2 秒 log-mel 窗） | 1024-d utterance embedding | NOSS | Acc 68.5 (IEMOCAP)，81.3 (CREMA-D) | Apache-2.0 | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2203.00236 表3 |
| TRILLsson 2 | trillsson2（EfficientNetV2） | 8.1 | A | 公开语料蒸馏自 CAP12（2 秒 log-mel 窗） | 1024-d utterance embedding | NOSS | Acc 69.8 (IEMOCAP)，82.6 (CREMA-D) | Apache-2.0 | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2203.00236 表3 |
| TRILLsson 3 | trillsson3（EfficientNetV2） | 21.5 | A | 公开语料蒸馏自 CAP12（2 秒 log-mel 窗） | 1024-d utterance embedding | NOSS | Acc 70.3 (IEMOCAP)，83.2 (CREMA-D) | Apache-2.0 | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2203.00236 表3 |
| DistilHuBERT | ntu-spml/distilhubert（去掉预测头） | 23.49 | A | LibriSpeech 960h，蒸馏自 HuBERT Base（94.68M→23.49M，保留 25%） | 768-d 帧级隐层 | SUPERB ER、IEMOCAP LOSO、RAVDESS | Acc 63.02 (SUPERB ER / IEMOCAP 4类)；UAR 61.4 (IEMOCAP LOSO, INT8)；Acc 46.64 (RAVDESS 跨库) | Apache-2.0 | yes | unknown(INT8 体积 23 MB 已核实，未检索到 runtime 与实测时延) | huggingface.co/ntu-spml/distilhubert；arxiv.org/abs/2110.01900 表1；arxiv.org/abs/2512.23435 |
| modified CPC | s3prl upstream | 1.84 | A | LibriSpeech 960h | 256-d 帧级隐层 | SUPERB ER | Acc 60.96 (SUPERB ER / IEMOCAP 4类) | Apache-2.0（s3prl 主体；Facebook 著权文件为 CC-BY-NC） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2105.01051 表1、表2；github.com/s3prl/s3prl |
| APC | s3prl upstream | 4.11 | A | LibriSpeech 960h | 512-d 帧级隐层 | SUPERB ER | Acc 59.33 (SUPERB ER / IEMOCAP 4类) | Apache-2.0（s3prl 主体；Facebook 著权文件为 CC-BY-NC） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2105.01051 表1、表2；github.com/s3prl/s3prl |
| PASE+ | s3prl upstream | 7.83 | A | LibriSpeech 960h | 2,560-d 帧级隐层 | SUPERB ER | Acc 57.86 (SUPERB ER / IEMOCAP 4类) | Apache-2.0（s3prl 主体；Facebook 著权文件为 CC-BY-NC） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2105.01051 表1、表2；github.com/s3prl/s3prl |
| NPC | s3prl upstream | 19.38 | A | LibriSpeech 360h/960h | 帧级隐层 | SUPERB ER | Acc 59.08 (SUPERB ER / IEMOCAP 4类) | Apache-2.0（s3prl 主体；Facebook 著权文件为 CC-BY-NC） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2105.01051 表1、表2；github.com/s3prl/s3prl |
| TERA | s3prl upstream | 21.33 | A | LibriSpeech 960h | 768-d 帧级隐层 | SUPERB ER | Acc 56.27 (SUPERB ER / IEMOCAP 4类) | Apache-2.0（s3prl 主体；Facebook 著权文件为 CC-BY-NC） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2105.01051 表1、表2；github.com/s3prl/s3prl |
| BYOL-A (2048-d) | AudioNTT2020-BYOLA-64x96d2048 | 6.33 | A | AudioSet（BYOL 自监督，2 层卷积） | 2048-d utterance embedding | SERAB | Acc 62.8 (IEMOCAP 4类)，72.8 (SERAB 跨库平均) | 仅限论文评测用途（官方 LICENSE 声明） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2110.03414 表3；arxiv.org/abs/2204.07402 表I（6,333,376 参数）；github.com/nttcslab/byol-a |
| ECAPA-TDNN (C=512) | C=512，**speaker-capable**（具备说话人确认能力） | 6.2 | A | VoxCeleb1+2（说话人识别语料） | 192-d 说话人 embedding，可接情感分类头 | VoxCeleb1（说话人）、IEMOCAP（情感） | EER 1.01 (VoxCeleb1)；Acc 65.7 (IEMOCAP, SpeechBrain recipe) | Apache-2.0（SpeechBrain） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2005.07143 表1（6.2M / EER 1.01）；github.com/speechbrain/speechbrain |
| Moonshine-tiny | UsefulSensors/moonshine-tiny（ASR，非情感模型，供两段式流水线参考） | 27 | A | 英文 ASR 数据（蒸馏自 base；官方未完整公开语料构成） | 英文文本转写，不含情感标签 | LibriSpeech | WER 4.55 (LibriSpeech test-clean)，11.68 (LibriSpeech other) | MIT | yes | yes: GGUF Q8_0 34 MB / ONNX，CPU 约 11.2x 实时 | huggingface.co/UsefulSensors/moonshine-tiny；arxiv.org/abs/2410.15608 |

**表内说明**

- SERAB（arXiv 2110.03414）报告的是 **test accuracy**，即 WAR（按样本数加权），**不是 UAR**；UM 是其 9 个数据集（英/法/德/希/意/波斯，6 种语言）准确率的等权平均。跨表比较时不要把 SERAB 的 Acc 和别处的 UAR 直接相减。
- 同一模型在不同论文里的 IEMOCAP 数字不可直接横比：SUPERB ER 是冻结特征 + 线性头、4 类、官方划分；SERAB 的 IEM 也是 4 类但划分不同；NOSS 的 IEMOCAP 又是另一套划分。
- ECAPA-TDNN 一栏标注 `speaker-capable`：它具备说话人确认能力，按红线一**不得进入任何推荐或结论**；此处仅作为"6M 量级编码器在 IEMOCAP 上能到多少"的参照。
- `edge` 列只记**已核到的公开证据**，且按 `00-taxonomy-and-metrics.md` 的规矩，`yes` **必须点名 runtime**。「真端侧（原生 App / aDSP）」与「proot 内可行（CPU 推理）」两档的区分与逐条判定，见 [`04-edge-deployment.md`](04-edge-deployment.md) §5——本轮回填中 **DistilHuBERT 因"只报了 INT8 体积、未点名 runtime"被降级为 `unknown(...)`**，这是口径收紧，不是新增否定。
- 涉及健康/情感状态的任何表述均为**非诊断**用途。

**因缺少可靠来源而删除的候选（不写入表）**

| 候选 | 删除原因 |
| --- | --- |
| Light-SERNet（约 0.46M，IEMOCAP WA 79.87 / UA 70.78） | GitHub 仓库无 LICENSE 文件，许可不可核实（arxiv.org/abs/2110.03435、github.com/AryaAftab/LIGHT-SERNET） |
| COLA（EfficientNetB0，4.0M） | 参数量可核（arXiv 2110.04621 表1），但未检索到公开情感基准指标与许可 |
| whisper-tiny | 39M，**≥30M 属中型档**（左闭右开），不在本档范围 |
| TRILLsson 4 / 5 | 63.4M / 88.6M，属中型档 |
| Wav2Vec2 Small（HF 公开权重） | 93.4M，属中型档 |
| TRILL-Distilled | 论文只说">26M 参数"，无确切数字 |
| LEAF + 小 CNN | 未检索到同时给出参数量、情感指标、许可的公开条目 |
| MobileNetV3-Small / EfficientNet-B0 + log-mel | 作为 backbone 的参数量只在非可核验来源（期刊页）找到，且无对应情感指标条目 |

---

## Part 2 · 小型档的代价

### 2.1 同基准下，小型档比中型档差多少

**SUPERB ER（IEMOCAP 4 类，冻结特征 + 线性头，官方划分；数据来自 arXiv 2105.01051 表1、表2；DistilHuBERT 来自 arXiv 2110.01900 表1）**

| 对比项 | 参数量(M) | ER Acc | 与 HuBERT Base 之差 |
| --- | --- | --- | --- |
| modified CPC | 1.84 | 60.96 | -3.96 |
| APC | 4.11 | 59.33 | -5.59 |
| PASE+ | 7.83 | 57.86 | -7.06 |
| NPC | 19.38 | 59.08 | -5.84 |
| TERA | 21.33 | 56.27 | -8.65 |
| DistilHuBERT | 23.49 | 63.02 | -1.90 |
| **小型档平均（上 6 项）** | — | **59.42** | **-5.50** |
| HuBERT Base（中型） | 94.68 | 64.92 | 0 |
| wav2vec 2.0 Base（中型） | 95.04 | 63.43 | -1.49 |
| HuBERT Large（大型） | 316.61 | 67.62 | +2.70 |

结论：**在同基准、同评测协议下，小型档平均比中型档 HuBERT Base 低 5.5 个点**；小型档里最好的 DistilHuBERT（23.49M）只差 **1.9 个点**，代价是它已经是小型档里参数量最大的一档（是 HuBERT Base 的 25%）。中型档里较弱的 wav2vec 2.0 Base（63.43）只比小型档平均高 4.0 个点，但比小型档里除 DistilHuBERT 外的所有成员都高。

**CREMA-D / IEMOCAP（NOSS，TRILLsson 系列，同一蒸馏配方下只有规模不同；arXiv 2203.00236 表3）**

| 对比项 | 参数量(M) | CREMA-D | IEMOCAP |
| --- | --- | --- | --- |
| TRILLsson 1（小型） | 5.0 | 81.3 | 68.5 |
| TRILLsson 2（小型） | 8.1 | 82.6 | 69.8 |
| TRILLsson 3（小型） | 21.5 | 83.2 | 70.3 |
| TRILLsson 4（中型） | 63.4 | 86.2 | 73.2 |
| TRILLsson 5（中型） | 88.6 | 86.1 | 72.7 |

同配方下：5.0M → 63.4M（12.7 倍参数）换 **CREMA-D +4.9 点 / IEMOCAP +4.7 点**；21.5M → 63.4M（3 倍参数）换 **+3.0 / +2.9 点**。也就是说在蒸馏路线里，**参数每翻一倍大约换不到 1.5 个点**，这是小型档最划算、也是最快见顶的一段。

**规模不是唯一变量：预训练目标更关键（SERAB 跨库平均，arXiv 2110.03414 表3）**

- YAMNet 3.7M：**55.1**；openSMILE 手工特征（非神经）：**70.2**；BYOL-S 2048：**75.1**。
- 同为小型档，YAMNet 比 6.33M 的 BYOL-A（72.8）低 **17.7 点**，甚至比**非神经的手工特征低 15.1 点**。
- 原因不是参数量：YAMNet 的预训练目标是 AudioSet 音频事件分类，与情感无关。**"小"本身不是主要代价，"小 + 预训练目标错配"才是。**

### 2.2 小型档结构上做不到的事

1. **跨语料泛化会崩，且崩得没有规律。** DistilHuBERT INT8 量化版（arXiv 2512.23435）在 IEMOCAP LOSO 上 UAR 61.4，跨库到 RAVDESS 只剩 **Acc 46.64，掉 14.8 个点**；作者观察到的失败模式是"按唤醒度聚类"——happy 系统性地被判成 angry，sad 被判成 neutral。这对"全天候录音→只留情绪标签"的场景是直接风险：跨说话人、跨录音设备的漂移量级和模型本身的能力是同一数量级。
2. **长时上下文被架构硬性截断。** TRILLsson 全系列在**固定 2 秒 log-mel 窗**上工作（arXiv 2203.00236），其教师侧论文明确给出"2 秒上下文窗已足够"（arXiv 2110.04621）。这不是调参问题而是建模假设：任何需要超过 2 秒上下文才能判断的情绪状态，小型档在结构上就看不到。
3. **细粒度 / 连续维度几乎无公开结果。** 表内 15 个小型档条目全部是 4–8 类的粗粒度分类（IEMOCAP 4 类、CREMA-D 6 类、SERAB 5–8 类）。**本档未检索到 <30M 模型在效价-唤醒-支配（V-A-D）连续维度上以 CCC 汇报的公开结果**，无法给出该档在维度情感上的数字。
4. **反讽 / 讽刺依赖语义与对话上下文，纯声学小型档不在射程内。** 表内所有条目的输入都是声学特征（log-mel / 波形 / 手工特征），没有任何一个接入文本。**本档未检索到 <30M 纯声学模型在讽刺/反讽任务上的公开结果**，故不给数字。
5. **健康/临床相关结论一律不成立。** TRILLsson 后续工作被用于抑郁检测等健康任务，但最大规模的语音抑郁检测研究的敏感度/特异度也只有约 71%。本档所有内容均为**非诊断**用途。

---

## Part 3 · 中文与小模型

**结论：中文基准上，小型档只有"非神经"一条结果，且远低于中型档。**

| 基准 | 小型档结果 | 同基准最佳声学结果（档位） | 差 |
| --- | --- | --- | --- |
| MER2024（arXiv 2408.10500，音频单模态） | openSMILE eGeMAPS（非神经，88 维）：**WAF 39.68 / ACC 42.88** | HuBERT-large（大型）：WAF 72.77；Chinese-HuBERT（中型）：WAF 72.67 | 与最佳声学差 **33.1 点** |
| MER2023（arXiv 2304.08981） | 音轨基线为 openSMILE IS09/IS10/eGeMAPS + VGGish + wav2vec/HuBERT 融合，**未单列小型神经模型的结果** | — | — |
| MER2025（arXiv 2504.19423，声学轨） | 参与比对的声学编码器为 WavLM-base 58.62/54.55、wav2vec2.0-base 67.55/62.59、HuBERT-base 72.36/68.13、HuBERT-large 76.29/72.27，**全部为 base / large，即 ≥ 中型档** | — | — |

- MERBench（arXiv 2401.03429）明确指出声学编码器对语言敏感，中文上表现最好的声学编码器是 **HuBERT-large**（属大型档）。
- **本档未检索到 <30M 神经声学模型在 MER2023 / MER2024 / MER2025、M3ED、CHEAVD、CASIA 上的公开结果。**
- 对"全中文、全天候录音"的落地含义：中文侧目前没有可引用的小型档基线，唯一可引用的小型档数字是 openSMILE eGeMAPS 在 MER2024 的 WAF 39.68，与最佳声学编码器相差约 33 个点。若要在中文场景用小型档，只能自建评测，不能引用现成数字。

---

## 红线自检

- **声纹**：ECAPA-TDNN 已标注 `speaker-capable`，仅作参照，**未出现在任何推荐或结论中**；表内不存储、不导出的说话人向量。
- **非临床**：所有情感/健康相关表述已标注**非诊断**；抑郁检测引用 71% 敏感度/特异度上限。
- **不编造**：参数量、指标、许可三项有一项查不到可靠来源即删除，删除清单见上；无"待补"占位。
