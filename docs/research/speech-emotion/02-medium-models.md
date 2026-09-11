# 中型模型（30M–500M）

> 口径以 `00-taxonomy-and-metrics.md` 为准：参数量**量化前、含音频编码器**；边界**左闭右开**，
> 30M 归本档、500M 归大型档。本文件只负责**规模 = 中型**这一条线；
> `edge`（端侧可部署）与多模态标记由别的文件回填，本表的 `edge` 列只写我查到的证据。
> 表格 schema 由 `scripts/check_ser_table.py` 机器校验。

---

## 1. 数据表

| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| wav2vec 2.0 | `facebook/wav2vec2-base` | 95.04 | A | LibriSpeech-960 | 情感表征（下游线性头 4 类） | IEMOCAP | UA 58.27 (IEMOCAP) | Apache-2.0 | yes | yes: ONNX Runtime INT8 | arxiv.org/abs/2406.07162; huggingface.co/facebook/wav2vec2-base |
| HuBERT | `facebook/hubert-base-ls960` | 94.68 | A | LibriSpeech-960 | 情感表征（下游线性头 4 类） | IEMOCAP | UA 63.87 (IEMOCAP) | Apache-2.0 | yes | yes: ONNX Runtime INT8 | arxiv.org/abs/2406.07162; huggingface.co/facebook/hubert-base-ls960 |
| WavLM | `microsoft/wavlm-base-plus`（speaker-capable） | 94.70 | A | Mix-94k（LibriLight-60k + GigaSpeech-10k + VoxPopuli-24k） | 情感表征（下游线性头 4 类） | IEMOCAP (SUPERB ER) | ACC 68.65 (IEMOCAP) | other（microsoft/UniSpeech LICENSE，非 SPDX，内容类 CC BY-SA 3.0；商用需法务确认） | yes | yes: ONNX Runtime INT8 | arxiv.org/abs/2305.14546; huggingface.co/microsoft/wavlm-base-plus |
| UniSpeech-SAT | `microsoft/unispeech-sat-base`（speaker-capable） | 94.68 | A | LibriSpeech-960 | 情感表征（下游线性头 4 类） | IEMOCAP (SUPERB ER) | ACC 66.04 (IEMOCAP) | other（microsoft/UniSpeech LICENSE，非 SPDX，内容类 CC BY-SA 3.0；商用需法务确认） | yes | yes: ONNX Runtime INT8 | arxiv.org/abs/2110.05752; huggingface.co/microsoft/unispeech-sat-base |
| UniSpeech-SAT | `UniSpeech-SAT Large`（speaker-capable；316M 级，见下方「分档边界争议」） | 316.61 | A | Mix-94k | 情感表征（下游线性头 4 类） | IEMOCAP (SUPERB ER) | ACC 70.68 (IEMOCAP) | other（microsoft/UniSpeech LICENSE，非 SPDX） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2110.05752; github.com/microsoft/UniSpeech |
| data2vec | `facebook/data2vec-audio-base-960h` | 93.75 | A | LibriSpeech-960 | 情感表征（下游线性头 4 类） | IEMOCAP | UA 54.19 (IEMOCAP) | Apache-2.0 | yes | yes: ONNX Runtime INT8 | arxiv.org/abs/2406.07162; huggingface.co/facebook/data2vec-audio-base-960h |
| emotion2vec | `iic/emotion2vec_base`（base 变体，唯一有论文原始参数表的版本） | 93.79 | A | LibriSpeech-960 + Emo-262（纯英文） | 9 类情感 / 768 维表征 | IEMOCAP | WA 71.79 (IEMOCAP) | other（FunASR 模型开源协议 v1.1，需署名；官方声明"仅供学习参考"，商用条款不明确） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2312.15185; github.com/ddlBoJack/emotion2vec |
| emotion2vec+ | `iic/emotion2vec_plus_base`（4788h 伪标注微调） | 93 | A | emotion2vec + 4788h 伪标注情感数据 | 9 类情感 / 768 维表征 | IEMOCAP | 56.3 (IEMOCAP，原文未标指标名，仅同表横向可比) | other（FunASR 模型开源协议 v1.1，同上） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2506.06820; huggingface.co/emotion2vec/emotion2vec_plus_base |
| emotion2vec+ | `iic/emotion2vec_plus_large`（42526h 伪标注微调；官方标称 ~300M，实测约 164M，见下方核对） | 164 | A | emotion2vec + 42526h 伪标注情感数据 | 9 类情感 / 768 维表征 | IEMOCAP | 63.8 (IEMOCAP，原文未标指标名，仅同表横向可比) | other（FunASR 模型开源协议 v1.1，同上） | yes | yes: ONNX（FunASR 官方导出，648,972,628 B，误差 6.20e-6；导出的是帧级特征，非情感标签） | arxiv.org/abs/2506.06820; huggingface.co/emotion2vec/emotion2vec_plus_large |
| Chinese-HuBERT | `TencentGameMate/chinese-hubert-base` | 95 | A | WenetSpeech L（1 万小时中文） | 768 维表征（下游线性头） | MER2024 | WAF 72.67 (MER2024) | MIT | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2408.10500; huggingface.co/TencentGameMate/chinese-hubert-base |
| SenseVoice | `iic/SenseVoiceSmall`（SAN-M encoder-only + CTC） | 234 | A | 40 万小时+ 多语（含中文） | 7 类情感 + 转写 + 音频事件标签 | CASIA / MER2023 / IEMOCAP | WA 70 (CASIA); WA 68 (MER2023); WA 70 (IEMOCAP) | other（权重许可指向 FunASR 模型开源协议 v1.1；仓库代码 Apache-2.0） | yes | yes: ONNX Runtime INT8（sherpa-onnx 导出 ~228MB）/ GGUF Q8_0（llama.cpp ~254MB） | arxiv.org/abs/2407.04051; github.com/FunAudioLLM/SenseVoice |
| wav2vec 2.0 | `wav2vec 2.0 Large`（316M 级，见下方「分档边界争议」） | 317.38 | A | LibriLight-60k | 情感表征（下游线性头 4 类） | IEMOCAP | WA 65.64 (IEMOCAP) | Apache-2.0 | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2312.15185; github.com/pytorch/fairseq |
| HuBERT | `HuBERT Large`（316M 级，见下方「分档边界争议」） | 316.61 | A | LibriLight-60k | 情感表征（下游线性头 4 类） | IEMOCAP | UA 67.42 (IEMOCAP) | Apache-2.0 | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2406.07162; huggingface.co/facebook/hubert-large-ls960-ft |
| WavLM | `microsoft/wavlm-large`（speaker-capable；316M 级，见下方「分档边界争议」） | 316.62 | A | Mix-94k | 情感表征（下游线性头 4 类） | IEMOCAP | UA 69.47 (IEMOCAP) | other（microsoft/UniSpeech LICENSE，非 SPDX） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2406.07162; huggingface.co/microsoft/wavlm-large |
| HiCMAE-S | cross-attention 融合（MHCA 跨模态融合编码器）；VoxCeleb2 自监督权重 | 46 | A+V | VoxCeleb2（无标注音视频，掩码重建 + 层级对比） | 4/6 类情绪（融合特征 + 线性头） | IEMOCAP | UAR 67.46 (IEMOCAP)；WAR 64.06 (IEMOCAP 仅音频分支 18M) | MIT | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2401.05698; github.com/sunlicai/HiCMAE |
| HiCMAE-B | cross-attention 融合（MHCA）；VoxCeleb2 自监督权重 | 81 | A+V | VoxCeleb2（无标注音视频，掩码重建 + 层级对比） | 4/6 类情绪（融合特征 + 线性头） | IEMOCAP | UAR 68.21 (IEMOCAP)；WAR 65.23 (IEMOCAP 仅音频分支 32M) | MIT | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2401.05698; github.com/sunlicai/HiCMAE |
| AV-HuBERT（Base） | early fusion（音视频逐帧拼接后入 Transformer）+ modality dropout；speaker-capable | 103 | A+V | LRS3 + VoxCeleb2(En)，掩码多模态聚类预测 | 帧级音视频表示；情感需下游微调头 | IEMOCAP | WAR 58.54 (IEMOCAP 仅音频分支 90M)；WAR 46.45 (IEMOCAP A+V 融合) | other（AV-HuBERT LICENSE AGREEMENT，Meta，仅限非商业研究用途；商业化需另行授权） | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2201.02184; github.com/facebookresearch/av_hubert |
| Self-MM | 拼接融合头 + 三个单模态子任务头（late + 中间混合）；参数量 103 为二手综述值（含 BERT 文本编码器），音频/视觉用预抽取特征、**无音频编码器** | 103 | A+T+V | BERT（中文/英文）+ COVAREP 声学特征 + Facet 视觉特征（均为预抽取，非端到端） | 情感极性（回归 + 2/3/5 分类）+ 单模态子任务头 | CH-SIMS | Acc-2 80.04 (CH-SIMS)；Acc-5 41.53 (CH-SIMS) | MIT | yes | unknown(未找到公开转换案例) | arxiv.org/abs/2102.04830; github.com/thuiar/Self-MM |

### 表格脚注

1. **参数量出处**：95M 档的 95.04 / 94.68 / 94.70 / 93.75 / 93.79 全部来自 emotion2vec 论文
   （arXiv 2312.15185）Table 2 的 `#Upstream Params` 列，即**含音频编码器、量化前**。
   常见二手表格把这几个数写成"95M 通用值"或混用 94.7/95.0，本表逐个照抄原表。
2. **EmoBox 数字**：UA 列取自 EmoBox（arXiv 2406.07162）Table 4，其划分是**每数据集均衡抽 240 条、
   4 类（angry/happy/neutral/sad）、统一线性下游头**。与 emotion2vec 论文 Table 2/3/4 的划分不同，
   **两者不可相减比较**。
3. **SUPERB ER**：SUPERB 的 ER 子任务用 IEMOCAP 4 类、指标为 Accuracy。
   2305.14546 的 Table 1 复现了 wav2vec2/HuBERT/WavLM 的 clean 条件数字，
   UniSpeech-SAT 的 66.04 / 68.48 / 70.68 取自 UniSpeech-SAT 论文（arXiv 2110.05752）Table 1。
4. **speaker-capable（红线 1）**：WavLM 与 UniSpeech-SAT 官方发布了 speaker verification /
   diarization 微调变体（`wavlm-base-plus-sv`、`unispeech-sat-base-sd` 等），
   UniSpeech-SAT 的预训练目标本身就含说话人判别。二者**已标注但不参与选型与推荐**。
   本系统只保留文本与情绪标签，不落声纹——即便用这类模型，也**不得**导出说话人嵌入。
5. **emotion2vec+ 两行指标**：arXiv 2506.06820 Table 3 是"双编码器 + LLM 多任务"下的
   编码器对比，原文未给出该列的确切指标名（只标任务为 ER）。这两个数**只用于同表内横比**，
   不可与其它行的 UAR/WA 直接比较。
6. **未入表的候选池条目及原因（红线 3：参数量/指标/许可任一项查不到可靠来源即删除）**：
   - `AST-base`（87M）：只找到 AudioSet / ESC-50 / Speech Commands 等通用音频指标，
     未找到可核验的 SER 指标；权重许可在官方仓库与 HF 卡上表述不一致。**删除**。
   - `PANNs-CNN14`（80.75M）：同上，只有 AudioSet mAP 0.431，无 SER 指标；
     官方仓库未给出明确权重许可。**删除**。
   - `whisper-small`（编码器 88M / 含解码器 241.7M）：未找到可核验的独立 SER 指标
     （可查到的数字都混在双编码器或 ASR 评测里）。**删除**。
   - `MMS-300M`：权重许可为 CC-BY-NC 4.0（非商用）这一点可核验，但官方未给出精确参数量
     （"300M"为架构族名，实际为 wav2vec2-large 规模）。**删除**，其非商用属性在正文记录。
7. **`edge = yes` 不等于能进端侧预算。** 95M 档 5 条的 `yes: ONNX Runtime INT8` 指的是
   「ONNX 是官方唯一支持的导出后端（TFLite / CoreML 明确把该家族列在不支持清单）+ ORT 提供通用
   INT8 PTQ」，**不代表有实测证据**：同构的 WavLM-Base-Plus 在 Qualcomm AI Hub 上**只有 float 档、
   无 w8a8 / w8a16**，且峰值内存报到 **1.0–1.6 GB**。「真端侧」与「proot 内可行」两档的区分与
   逐条判定见 [`04-edge-deployment.md`](04-edge-deployment.md) §5；本档的结论是
   **B 档（proot 内 CPU）触发式可用，A 档不成立**。
8. **表末 4 行（HiCMAE-S / HiCMAE-B / AV-HuBERT / Self-MM）来自多模态轴**，
   是本轮 `05-multimodal.md` 调研中新增的条目，按参数量落在中型档，故归档于此。
   相关口径与证据等级：
   - **HiCMAE 两行**的参数量（46 / 81M）与指标取自 arXiv 2401.05698（Information Fusion 2024，
     **同行评审**）Table 10（IEMOCAP 4 类，session-independent）。该表同时给出 A / V / A+V 三种输入的
     参数量与 UAR/WAR，是本次找到的**唯一一份把「缺模态」与「全模态」放在同一张官方表里的 SER 数字**。
     A+V 参数量（46/81M）大于其任一支（18/32M），符合「含两个编码器」的口径。
   - **AV-HuBERT 103M** 有两个独立出处：VatLM 论文原文写「AV-HuBERT base 与 large 分别为 103M 与 325M」
     （arXiv 2211.11275），HiCMAE Table 10 亦标 103M（**同行评审 + 交叉验证**）。
     其情感指标是 HiCMAE 论文在自己协议下复现的（**二手实测**）。
     注意其 **A+V 融合 WAR 46.45 反低于纯音频分支 58.54**——这是 early fusion 在模态质量不匹配时的
     典型失效，不要只读融合后的数字。
   - **Self-MM 的 103M 是二手值**（含 BERT 文本编码器），且它**没有音频编码器**
     （声学用 COVAREP 预抽取特征），与 `00` 的「参数量含音频编码器」口径**名义冲突**：
     该 103M 不含音频前端，落地时 COVAREP 需另算。CH-SIMS 的 Acc-2 80.04 / Acc-5 41.53 亦为转引
     （转引自 Mao et al. 2022 及官方 GitHub）。
   - 四行的 `edge` 全为 `unknown(未找到公开转换案例)`：未检索到任一模型有 TFLite /
     ONNX Runtime Mobile / CoreML / NCNN / MNN / RKNN / QNN 的公开转换或实测案例。
   - **AV-HuBERT 标 `speaker-capable`**（VoxCeleb2 说话人语料预训练 + 下游 SV 微调用法），
     按红线 1 标注，**不参与任何推荐**。
   - 多模态轴的整体结论是「**不引入视觉模态**」；这 4 行**不是落地推荐**，
     只是把「多模态模型在这个参数量级上能做到多少」记录在案。见 [`05-multimodal.md`](05-multimodal.md)。

### 分档边界争议（需人工裁定）

`00-taxonomy-and-metrics.md` 的候选池把 `wav2vec2 / HuBERT / WavLM 的 large 版本` 和
`emotion2vec-plus-large` 列在**大型线**，但按同一文件的数值边界（大型 > 500M、左闭右开），
316M 与 164M 都落在**中型档**。本表按**数值边界**收录（`规模定主键`，一个模型只落一档），
并在「版本/权重」列显式标注 `316M 级`。若最终决定按候选池归类，请从本表删除这 4 行
（wav2vec2 Large / HuBERT Large / WavLM Large / UniSpeech-SAT Large），
避免与 `03-large-models.md` 重复收录导致口径打架。

---

## 2. emotion2vec 变体参数量逐版本核对

这是本次调研唯一被明确点名的高风险项，网上二手表格（例如某些中文技术博客把 seed/base 写成
3.5 亿、把 large 写成 10 亿）与官方口径不一致。逐版本核对如下：

| 变体 | 官方说法 | 本文采信值 | 依据 |
|---|---|---|---|
| emotion2vec（base） | 论文 Table 2 `#Upstream Params = 93.79M` | **93.79M** | arXiv 2312.15185 Table 2；ACL 2024 Findings 同表 |
| emotion2vec+ seed | 官方未单独给出数字 | **≈93M**（base-size） | 官方 README 只写 base ~90M / large ~300M，seed 未列；由 checkpoint 体积反推（见下） |
| emotion2vec+ base | 官方 README / ModelScope：`base size model (~90M)` | **≈93M** | 官方口径 ~90M；checkpoint 体积反推 93.2M；arXiv 2506.06820 独立标注 `Emotion2Vec+ base (93M)` |
| emotion2vec+ large | 官方 README / ModelScope：`large size model (~300M)` | **≈164M（与官方标称冲突）** | 见下 |

**`emotion2vec+ large` 的 300M vs 164M 冲突如何处理：**

1. 官方 README 与 ModelScope 卡都写 `~300M`——这是**作者自述**，但 LOGO 式约数，且
   ModelScope 的 seed 页面明显是复制粘贴错误（把 large 的 `~300M` 抄到了 seed 页）。
2. 用 checkpoint 体积反推：以已知 93.79M 的 `emotion2vec_base`（HF usedStorage 1,127,454,818 B）
   做标定，得到 **12.02 字节/参数**（fp32 权重 + Adam 一/二阶动量，FunASR 的 `model.pt` 形态）。
   同一标定下：
   - `emotion2vec_plus_seed`：1,121,181,659 B → 93.3M
   - `emotion2vec_plus_base`：1,120,094,487 B → 93.2M
   - `emotion2vec_plus_large`：1,947,639,063 B → **162M**
3. 第三方交叉验证：IJCNLP 2025 主会论文（arXiv 2506.06820）Table 3 直接标注
   `Emotion2Vec+ Large (164M)` 与 `Emotion2Vec+ base (93M)`，与体积反推吻合。
4. 架构侧证：`emotion2vec_plus_large` 的 `config.yaml` 为 `depth 8 / embed_dim 1024 /
   mlp_ratio 4 / heads 16`，按此配置的量级在 100–170M 区间，**撑不到 300M**。

结论：**对外引用请用 164M，并注明官方 README 标称 ~300M。** 本表按 164 记录。
无论取哪个值，它都落在中型档（< 500M），**不属于大型档**。

---

## 3. 中型档为什么是主力

### 3.1 同基准横向对比（SUPERB ER = IEMOCAP 4 类，Accuracy）

这是唯一一套把三档模型放在**完全相同的数据划分、相同的冻结编码器 + 线性下游协议**下的公开数字。

| 档 | 模型 | 参数量(M) | ER ACC (IEMOCAP) |
|---|---|---|---|
| 小型 <30M | TERA | 21.3 | 56.27 |
| 小型 <30M | NPC | 19.4 | 59.08 |
| 小型 <30M | modified CPC | 1.8 | 60.96 |
| 小型 <30M | DistilHuBERT | 23.5 | 63.02 |
| **中型** | wav2vec 2.0 Base | 95.04 | 63.43 |
| **中型** | HuBERT Base | 94.68 | 64.92 |
| **中型** | UniSpeech-SAT Base | 94.68 | 66.04 |
| **中型** | UniSpeech-SAT Base+ | 94.68 | 68.48 |
| **中型** | WavLM Base+ | 94.70 | **68.65** |
| **中型（316M 级）** | HuBERT Large | 316.61 | 67.62 |
| **中型（316M 级）** | WavLM Large | 316.62 | 70.62 |
| **中型（316M 级）** | UniSpeech-SAT Large | 316.61 | **70.68** |
| 大型 >500M | Whisper large-v3 encoder | 635 | 73.54 |

出处：SUPERB（arXiv 2105.01051）+ arXiv 2305.14546 Table 1 + arXiv 2110.05752 Table 1 +
EmoBox（arXiv 2406.07162）Table 4（Whisper large-v3 行为 UA 73.54，此处并列仅示位置，指标不同不可直接比较）。

**读出来的三件事：**

1. **中型档的典型区间**：在 SUPERB ER 上，**95M 档 63.4–68.7**，**316M 档 67.6–70.7**。
   EmoBox 划分下（均衡 240 样本、4 类、统一线性头）IEMOCAP UA 则是
   **95M 档 54.2–63.9**（data2vec-base 54.19 → HuBERT-base 63.87）、**316M 档 67.4–69.5**。
   两套划分不可互通，但**内部排序一致**：95M 档之间最大相差约 10 个 UAR 点，选模型比选规模更重要。
2. **相对小型档的收益，比想象中小。** DistilHuBERT（23.5M，63.02）几乎打平 wav2vec 2.0 Base
   （95M，63.43）。中型档真正的收益不来自"参数更多"，而来自**同参数预算下可做情感专用预训练**：
   emotion2vec（93.79M）在同论文的 IEMOCAP WA 上拿到 71.79–77.64，而同为 93–95M 的通用 SSL
   只有 63.43–68.58；同样 93.79M，专用预训练比通用预训练高约 **+4.4 到 +9 个点**（同基准、同协议）。
3. **相对大型档的代价，比想象中大。** 从 95M 涨到 316M（参数 ×3.3）在 SUPERB ER 上只换来
   **约 +2 到 +4 个点**（63.43→65.64、64.92→67.42、68.65→70.62）。而真正跨过 500M 的
   Whisper large-v3 编码器（635M）才出现明显台阶——但它已不在端侧预算内。

### 3.2 MELD / RAVDESS 上的区间

两套划分不可互通，分别列出：

- **emotion2vec 论文 Table 3**（原数据集划分，UA）：
  MELD **16.75–28.03**（WavLM-base+ 16.75 → emotion2vec 28.03）；
  RAVDESS **38.40–82.86**（WavLM-base+ 38.40 → emotion2vec 82.86）。
- **EmoBox Table 4**（均衡 240 样本、4 类，UA）：
  MELD **20.06–28.18**（wav2vec2-base 20.06 → WavLM-large 28.18）；
  RAVDESS **54.33–72.00**（wav2vec2-base 54.33 → WavLM-large 72.00）。

两点对本项目有意义：**MELD 上所有中型模型的 UAR 都只有 20–28**（多说话人、电视对白、噪声），
说明"对话式电视语音"这条数据分布上中型档还没解决任何问题；
**RAVDESS 上可达 72–83**，但 RAVDESS 是实验室朗读、演员表演，与本项目的真实录音分布差距最大，
不应作为选型依据。

### 3.3 延迟 / 显存 / 功耗：诚实说明

**未找到同基准（同硬件、同输入长度、同批次）的中型 vs 大型档延迟/显存/功耗对比**，
不同论文的硬件与测量方式不一致，直接相减没有意义。以下为各自报告值，**不可互相比较**：

- 参数量倍率是可核实的：95M → 316M 为 **3.3×**；95M → Whisper large-v3 编码器 635M 为 **6.7×**。
  FP32 权重体积同理：约 380MB → 1.3GB → 2.5GB。
- SenseVoice-Small 官方 README：**10 秒音频 70ms** 推理，同参数量级下
  **比 Whisper-Small 快 5 倍以上、比 Whisper-Large 快 15 倍**。
  这是本次调研找到的唯一一条官方、成对、同设置的效率声明；
  它说明**架构（非自回归 encoder-only）比参数量更能决定延迟**。
- 量化后体积（有公开转换案例的）：SenseVoice-Small **ONNX INT8 ≈ 228MB**、**GGUF Q8_0 ≈ 254MB**。
  95M 档 SSL 编码器 INT8 后约 95MB 量级——这是**权重体积**层面中型档还能谈端侧的主要理由。
  但**体积不是门槛**：[`04-edge-deployment.md`](04-edge-deployment.md) §2 与 §4 给出的结论是，
  在 proot 现状下中型档只能走 CPU，而同构的 WavLM-Base-Plus 实测**峰值内存 1.0–1.6 GB**
  （Qualcomm AI Hub 官方 profile，20 s 输入），且在 AI Hub 上**没有 w8a8 / w8a16 量化档**。
  即：**B 档（proot 内 CPU）触发式可用，A 档（真端侧 / 低功耗）不成立。**

### 3.4 结论（一句话）

中型档是主力，不是因为它比小型档准很多（在 SUPERB ER 上只准 0～5 个点），
而是因为**它是"能装进端侧预算"里唯一还装得下"情感专用预训练"和"跨语种鲁棒性"的档位**：
同样 93–95M，emotion2vec 靠专用预训练把 IEMOCAP 从 63 拉到 72+；
再往上堆到 316M 只买 +2～4 个点，却要多付 3.3 倍的权重、显存与功耗。

---

## 4. 中文与中型档（本项目关键）

系统是中文场景，这一节优先于英文 SOTA。

### 4.1 EmoBox 中文子集（均衡 240 样本、4 类、UA）

| 对比模型 | 参数量(M) | CASIA (zh) | M3ED (zh) | MER2023 (zh) |
|---|---|---|---|---|
| wav2vec 2.0 base | 95.04 | 39.56 | 23.13 | 40.40 |
| data2vec base | 93.75 | 34.72 | 19.44 | 37.94 |
| WavLM base | 94.70 | 47.25 | 22.76 | 41.80 |
| HuBERT base | 94.68 | 47.23 | 23.80 | 42.56 |
| HuBERT large | 316.61 | 45.30 | 23.25 | 43.96 |
| WavLM large | 316.62 | 52.12 | 26.58 | 48.17 |
| Whisper large-v3 encoder（大型档参照） | 635 | 59.58 | 32.84 | 61.22 |

出处：arXiv 2406.07162 Table 4。

要点：**中文三个基准上，95M 档的 UA 只有 19–48**，且 **HuBERT-large（316M）在 CASIA 和 M3ED 上
不升反降**（47.23→45.30、23.80→23.25）。规模在中文上几乎不兑现收益，
只有 Whisper large-v3 这种 635M 级、又吃过多语弱监督的编码器才明显跳一档——但它是大型档。

### 4.2 MER2024 中文单模态音频（WAF / ACC）

| 对比模型 | 参数量(M) | WAF | ACC |
|---|---|---|---|
| emotion2vec | 93.79 | 56.08 | 56.48 |
| Whisper-base | 74 | 56.65 | 57.08 |
| wav2vec 2.0 base | 95.04 | 64.89 | 65.14 |
| wav2vec 2.0 large | 317.38 | 65.50 | 65.83 |
| HUBERT-base | 94.68 | **69.26** | **69.43** |
| Chinese-HuBERT | 95 | 72.67 | — |
| HUBERT-large | 316.61 | 73.02 | 73.10 |

出处：arXiv 2404.17113（MER2024）Table 5 与 arXiv 2408.10500（SZTU-CMU MER2024）第 4.1.1 节。
（Chinese-HuBERT 的 72.67 只有 WAF，原文未给 ACC。）

**这里有一条对本项目最重要的反直觉结论：emotion2vec 在中文上明显落后。**
它在英文 IEMOCAP 上是同参数量 SOTA（WA 71.79），但在 MER2024 中文上只有 WAF 56.08，
被同为 95M 的 HuBERT-base（69.26）甩开约 13 个点。原因在它的预训练语料里写得很清楚：
Emo-262 是**纯英文**（IEMOCAP + MELD + MEAD + CMU-MOSEI + MSP-Podcast，共 262 小时），
中文数据（M3ED 等）只用于下游评测、从未进预训练。
**中文场景下，与其上 emotion2vec，不如上 Chinese-HuBERT（WenetSpeech 1 万小时中文）或 HuBERT-base。**

### 4.3 SenseVoice-Small（中文场景的一体化选项）

SenseVoice-Small（234M）在**零微调**下的 WA：CASIA (zh) **70**、MER2023 (zh) **68**、
IEMOCAP (en) **70**、MELD **58**、ESD **85**（arXiv 2407.04051 Figure 8）。
对比 4.1 节的 EmoBox 数字（同为 CASIA/MER2023，但划分不同，**不可直接相减**），
SenseVoice-Small 在中文两个基准上的绝对水平显著高于 95M 档 SSL 编码器，
且它一次前向同时出转写 + 情感 + 事件标签——对本系统"只留文本与情绪标签"的形态是天然契合的。
代价是 234M（约为 95M 档的 2.5 倍权重）与 FunASR 模型协议的商用不确定性。

### 4.4 覆盖范围与缺口

- 已覆盖中文基准：**M3ED、MER2023、MER2024、CASIA**（共 4 个，超出红线要求的 2 个）。
- **CHEAVD：未检索到中文基准上的公开结果。** emotion2vec 论文（18 个数据集）不含 CHEAVD，
  EmoBox（32 个数据集 / 14 语种）也不含 CHEAVD；本次检索未找到任何中型模型在 CHEAVD 上的
  可核验公开数字。**不编造。**
- **MER2025：未检索到中型模型的可核验公开结果。**
- 中文上还有一个共性问题：所有中文基准的 UAR 绝对值都偏低（CASIA 35–52、M3ED 19–27、
  MER2023 38–48），说明**在中文真实分布上，中型档离"可用"仍有明显距离**，
  落地时应按"粗粒度情绪倾向"而非"细粒度情绪分类"来设计产品预期。

---

## 5. 红线自检

1. **不存声纹**：WavLM、UniSpeech-SAT 已标 `speaker-capable`，**不进入任何推荐或结论**。
   本系统的形态（转写后原音频即焚、只留文本与情绪标签）本身不产出声纹。
2. **情绪标签非临床**：本文件所有指标都是**情绪分类/表征**指标，不含任何健康或临床声称。
   若后续把情绪标签用于抑郁/焦虑等推断，必须标注"**非诊断**"——
   已知最大规模抑郁语音检测研究的敏感度与特异度均仅 **71%**，不足以支撑任何临床用途。
3. **不许编造**：AST-base、PANNs-CNN14、whisper-small、MMS-300M 因指标或许可无法核验已删除，
   原因记录在 §1 脚注 6；CHEAVD / MER2025 明确写"未检索到"。
   `emotion2vec+ large` 的参数量冲突已完整披露双方证据，未单方面采信官方约数。

---

## 6. 主要参考文献（arXiv ID）

- **2312.15185** — emotion2vec: Self-Supervised Pre-Training for Speech Emotion Representation
  （ACL 2024 Findings；本档 95M 参数量的原始表、IEMOCAP/MELD/RAVDESS/SAVEE 与 M3ED 结果）
- **2406.07162** — EmoBox: Multilingual Multi-corpus Speech Emotion Recognition Toolkit and Benchmark
  （32 数据集 / 14 语种、统一协议；本文跨档与中文对比的主数据源）
- **2110.05752** — UniSpeech-SAT: Universal Speech Representation Learning with Speaker Aware Pre-Training
  （SUPERB ER 上 base/base+/large 的完整对照）
- **2110.13900** — WavLM: Large-Scale Self-Supervised Pre-Training for Full Stack Speech Processing
- **2404.17113** — MER 2024（中文场景单模态音频基线，emotion2vec 在中文上的失效证据）
- **2407.04051** — FunAudioLLM（SenseVoice 的 SER 与效率数字）
- **2408.10500** — SZTU-CMU at MER2024（Chinese-HuBERT 在中文音频单模态上的最佳 WAF）
- **2506.06820** — Beyond Classification: Towards Speech Emotion Reasoning with Multitask AudioLLMs
  （独立标注 Emotion2Vec+ base 93M / large 164M，是参数量冲突的关键交叉验证）
- **2105.01051** — SUPERB: Speech Processing Universal Performance Benchmark
- **2305.14546** — On the Adaptability and Robustness of Whisper（SUPERB ER 复现数字）
