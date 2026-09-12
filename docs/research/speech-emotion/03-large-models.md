# 大型档（参数量 > 500M）

> 口径来源：`00-taxonomy-and-metrics.md`（分档、指标、schema、红线）。
> 分档按**量化前、含音频编码器**的参数量，左闭右开：500M 归大型。
> 本表由 `scripts/check_ser_table.py` 机器校验。
>
> 本档要特别区分的两条路线：
> - **纯音频大模型**：音频编码器（或直接是语音基座）直出情感，或 audio encoder → LLM 端到端；
> - **ASR + LLM 两段式**：先转写成文本，再让 LLM 判情感。参数量按口径写**两段之和**，
>   延迟结构（自回归两次）、成本结构（两个模型驻留）、失败模式（ASR 错误 + LLM 幻觉叠加）都不同。

## 数据表

| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Qwen2-Audio-7B | Qwen/Qwen2-Audio-7B；端到端（非 ASR+LLM 两段式，见裁定 3） | 8000 | A | Qwen2 文本语料 + 多任务音频数据（ASR / S2TT / 音频理解） | 自由文本（可给出情感类别与理由） | IEMOCAP, AIR-Bench | ACC 54.0 (IEMOCAP)；AIR-Bench Speech 69.7 (AIR-Bench) | Apache-2.0 | yes | no | arXiv:2407.10759 https://huggingface.co/Qwen/Qwen2-Audio-7B |
| Qwen2.5-Omni-7B | Qwen/Qwen2.5-Omni-7B | 10700 | A+T+V | Qwen2.5 文本语料 + 音视频多任务预训练 | 自由文本（可给出情感类别与理由） | EmotionHallucer | ACC 18.65 (EmotionHallucer 全量，随机基线 25.0)；ACC 25.44 (EmotionHallucer NoAudio 子集) | Apache-2.0 | yes | no | arXiv:2503.20215 https://huggingface.co/Qwen/Qwen2.5-Omni-7B |
| SALMONN-7B | tsinghua-ee/SALMONN-7B；端到端（非 ASR+LLM 两段式，见裁定 3）；speaker-capable | 7000 | A | Whisper + BEATs 编码器；OpenAQA-5M 指令微调 | 自由文本（情感类别 / 描述） | IEMOCAP | WF1 75.8 (IEMOCAP-4) | Apache-2.0 | yes | no | arXiv:2310.13289 https://github.com/bytedance/SALMONN |
| SALMONN-13B | tsinghua-ee/SALMONN-13B；端到端（非 ASR+LLM 两段式，见裁定 3）；speaker-capable | 13000 | A | Whisper + BEATs 编码器；OpenAQA-5M 指令微调 | 自由文本（情感类别 / 描述） | IEMOCAP | WF1 72.9 (IEMOCAP-4) | Apache-2.0 | yes | no | arXiv:2310.13289 https://huggingface.co/tsinghua-ee/SALMONN-13B |
| SenseVoice-Large | iic/SenseVoiceLarge（Large 权重未公开发布，仅 Small 可下载） | 1587 | A | 多任务弱标注语音（ASR / 语种 / 事件 / 情感联合训练） | 情感 + 事件 + 语种标签（自回归 token） | CASIA | WA 95.0 (CASIA)；WA 69.0 (MER2023) | MIT（FunAudioLLM/SenseVoice 代码）；Large 权重未发布 | no | no | arXiv:2407.04051 https://github.com/FunAudioLLM/SenseVoice |
| Emotion-LLaMA | ZebangCheng/Emotion-LLaMA | 7000 | A+T+V | LLaMA-2 文本语料 + HuBERT/EVA/MAE/VideoMAE 编码器 + MER2023 等情感指令数据 | 自由文本描述（细粒度情感） | MER2023 | F1 90.36 (MER2023) | Apache-2.0（HF 模型卡）；MER2023 数据仅限研究用途 | yes | no | arXiv:2406.11161 https://huggingface.co/ZebangCheng/Emotion-LLaMA |
| WavLLM | microsoft/SpeechT5 → WavLLM；端到端（非两段式，见裁定 3）；speaker-capable | 7550 | A | Whisper-large-v2（语义）+ WavLM-base（声学）编码器 + LibriSpeech 等多任务数据 | 自由文本（情感类别） | IEMOCAP | ACC 59.8 (IEMOCAP) | MIT（SpeechT5 仓库 LICENSE）；基座 LLaMA-2-7B-chat 另受 LLaMA-2 社区许可约束 | yes | no | arXiv:2404.00656 https://github.com/microsoft/SpeechT5 |
| Phi-4-multimodal-instruct | microsoft/Phi-4-multimodal-instruct | 5600 | A+T+V | Phi-4-Mini 文本语料 + 语音 / 视觉编码器预训练数据 | 自由文本 | IEMOCAP | ACC 41.0 (IEMOCAP) | MIT | yes | unknown(未找到公开转换案例) | arXiv:2503.01743 https://huggingface.co/microsoft/Phi-4-multimodal-instruct |
| Cascade（Whisper + Llama-3） | ASR+LLM 两段式（Whisper-large-v3 转写 → Llama-3-8B-Instruct 判情感） | 9550 | A+T | Whisper-large-v3（680k h 弱监督 ASR）+ Llama-3-8B 文本语料 | 情感类别 | IEMOCAP, MELD | ACC 46.7 (IEMOCAP)；ACC 36.8 (MELD-ER) | Whisper MIT；Llama-3 社区许可 | yes | no | https://arxiv.org/abs/2506.06820 |
| R3 流水线（7B） | ASR+LLM 两段式（Whisper-large 转写 → Llama-2-7b-chat-hf 判情感） | 8550 | A+T | Whisper-large（680k h 弱监督 ASR）+ Llama-2 文本语料 | 4 类（angry/happy/neutral/sad） | IEMOCAP | UA 64.67 (IEMOCAP，LoRA 指令微调)；UA 49.72 (IEMOCAP，零样本) | Whisper MIT；LLaMA-2 社区许可 | yes | no | https://arxiv.org/abs/2409.15551 |
| R3 流水线（13B） | ASR+LLM 两段式（Whisper-large 转写 → Llama-2-13b-chat-hf 判情感） | 14550 | A+T | Whisper-large（680k h 弱监督 ASR）+ Llama-2 文本语料 | 4 类（angry/happy/neutral/sad） | IEMOCAP | UA 52.27 (IEMOCAP，零样本) | Whisper MIT；LLaMA-2 社区许可 | yes | no | https://arxiv.org/abs/2409.15551 |

### 填表口径说明（不写进表，但影响怎么读表）

1. **参数量来源**：优先取论文或 HF 模型卡明确写的总量。
   Qwen2-Audio-7B 的 HF 卡写 `Model size 8B params`（含音频编码器）；
   WavLLM 论文 Appendix G 写"总参数 7.55B，可训练 76.6M"；
   Phi-4-multimodal 模型卡写 5.6B；
   Emotion-LLaMA 的 HF 卡写 `7B params`。
   两段式的三段数字由**两阶段组件公开参数量相加**得到（Whisper-large-v3 1550 + Llama-3-8B 8000 = 9550 等），
   论文本身未给系统总量，因此这是**下界口径**。
2. **指标不可跨行直接比**：Qwen2-Audio / WavLLM / Phi-4-Multimodal / Cascade 的 IEMOCAP 数字
   同取自 arXiv:2506.06820 的 Table 5（同一评测协议，可比）；WavLLM 自家论文在 IEMOCAP Session5
   上另报 ER Acc 0.72，协议不同，**不与 59.8 直接比较**。
   SALMONN 的 WF1 来自 CARE 论文（arXiv:2409.05566）的 IEMOCAP-4 协议，与前者不同基准。
3. **speaker-capable**：SALMONN（含说话人验证任务）、WavLLM（含 SV 任务）具备说话人相关能力。
   按红线 1，仅在此标注，**不参与任何选型结论**。
4. **「模态」列记推理时的输入通道，不记内部结构**（`00` 裁定 3）。
   本表已据此把 **Qwen2-Audio-7B / SALMONN-7B / SALMONN-13B / WavLLM 由 `A+T` 改为 `A`**——
   它们是**端到端 Audio-LLM**：音频编码器（Whisper / BEATs / WavLM）直接接入 LLM，
   中间**不产生转写文本**；内部有 Whisper 编码器不等于有 T 通道，指令 prompt 也不算模态。
   只有 **Cascade 与 R3** 这两条真正的 ASR+LLM 两段式流水线保留 `A+T`。
   改完后本表里 `A+T+V`（真多模态）只剩 Qwen2.5-Omni-7B、Emotion-LLaMA、Phi-4-multimodal-instruct 三条——
   **「大型档普遍是多模态」这个印象不成立**，大型档的多数是端到端纯音频 LLM。
   这一区别对架构有直接含义：端到端模型**不需要 ASR 前置**，两段式才需要。

### 已核实但因红线 3 排除的条目（留痕）

| 候选模型 | 排除原因 |
|---|---|
| emotion2vec-plus-large | HF 卡写"large size model (~300M)"，**< 500M，属中型档**，不进本表（候选池原列在大型线，实为错档） |
| wav2vec2-large / HuBERT-large / WavLM-large | 均为 ~316M，**属中型档**；大型线候选池里列的"large 版本"实际全部落中型 |
| MMS-1B | ~1000M 属大型档，但它是纯 ASR 基座，**检索不到情感指标**，按"指标查不到就删"排除 |
| whisper-large-v3 | 1550M 属大型档，但同上无情感指标；在本表中只作为两段式的 ASR 阶段计入参数量 |
| LTU（Listen-Think-Understand） | arXiv:2305.10790（任务书给的 2308.10882 查无此号）；仓库**未声明许可证**，按红线 3 排除 |
| AffectGPT | arXiv:2501.16566；论文未给出基座 LLM 与总参数量（仅说用 LoRA），参数量查不到 → 排除。其 MER-FG 数字见下节 |
| C2SER | arXiv:2502.18186；论文正文与仓库均**无许可证声明**，参数量只给了 LLM 主干（Qwen2-7B-Instruct）未给总量 → 排除。其幻觉分析与中文数字见下节 |

### 纯 API 的商业模型（不进主表）

GPT-4o-audio、Gemini 系列等**没有公开的量化前参数量**（厂商未披露），
`参数量(M)` 列要求数字或 `n/a(非神经)`，两者都不适用，按红线 3 不进主表，单列于此：

- **许可**：`proprietary API`；**权重可得**：`API only`；**edge**：`no`。
- **能力落点**：OmniVox（arXiv:2503.21480）零样本 IEMOCAP 音频 3 类 W-F1：GPT-4o-audio 51.8、
  Gemini 1.5 Flash 49.9、Phi-4 37.6；MELD 上 GPT-4o-audio 51.3。
  EmotionHallucer（arXiv:2505.11405）上 Gemini-2.5-Flash Overall 45.06、Gemini-2.5-Pro 44.17，
  是全部被测模型里最高的，但仍未过半。
- **备注（对本仓库关键）**：这类模型**不可端侧、不可离线**。AlwaysOnRec-HY4 是边缘优先、可离线系统，
  采用 API 路线等于把"24 小时连续录音"整段上传到第三方，直接违反系统的隐私前提，
  不只是"慢一点"的工程取舍。

---

## 大模型的收益与代价

### 1）收益：细粒度 / 上下文依赖的情感 vs 普通粗分类

**先说结论：粗分类上的收益很小，小到不值得为它破"边缘优先 / 可离线"的例。**

**（a）粗分类（IEMOCAP 4 类）——大模型没有稳定优势，甚至平均为负**

CARE（arXiv:2409.05566）在 8 个数据集上做了同协议横评，是最硬的一组对照：

| 系统（CARE 论文同协议） | 参数量 | IEMOCAP-4 WF1 | MELD WF1 | 8 数据集平均 WF1 |
|---|---|---|---|---|
| CARE | **160M（中型档）** | 69.4 | 48.1 | **66.0** |
| SALMONN-7B | 7000M | 75.8 | 53.3 | 65.2 |
| SALMONN-13B | 13000M | 72.9 | 52.6 | 65.6 |

- 单个数据集上，SALMONN-7B 比 160M 的 CARE 高 **约 6.4 个 WF1 点**（IEMOCAP-4：75.8 vs 69.4）；
- 但 **8 个数据集平均，160M 的 CARE（66.0）反超 13B 的 SALMONN（65.6）**，
  论文原话是 CARE "surpassing even the SALMONN 13B model, which has nearly 80 times more parameters"。
- 同一批实验里，7B 与 13B 之间（75.8 vs 72.9）**参数翻番反而掉点**。

再看另一个能拆"加权 vs 类平均"的对照（arXiv:2506.06820 Table 6，MELD-ER）：

| 系统（MELD-ER，arXiv:2506.06820 Table 6） | Weighted Avg | Unweighted Avg |
|---|---|---|
| emotion2vec+ Large（300M，中型档） | 44.7 | **29.7** |
| AudioLLM（Whisper-L-v3 + Llama-3-8B，9.55B） | **53.0** | 29.2 |

大模型在**加权**准确率上 +8.3 点，但**类平均（UAR）几乎不动（29.7 → 29.2）**。
也就是说：多出来的 8 个点基本来自 neutral 这类大样本类，
disgust（8.0 vs 2.0）、fear（13.2 vs 6.0）、sadness（15.9 vs 32.2）等少数类依旧接近崩塌。
对 24/7 录音场景这是一条坏消息：稀有情绪恰恰是最值得记录的事件，
而大模型的"平均指标提升"并不兑现到这些类上。

**（b）细粒度 / 上下文依赖（反讽、隐含情绪）——大模型是质变，但绝对水平仍很低**

闭集的中型模型根本无法输出"细粒度情感描述"这个任务形态（它只能吐固定标签），
所以这里**不是同一个基准上的分数差，而是任务能力的有无**，数字不可直接相减。

绝对水平（MER2025 MER-FG 细粒度赛道基线，arXiv:2504.19423）：

| 系统（MER2025 MER-FG 细粒度） | S1 | S2 | Avg |
|---|---|---|---|
| AffectGPT（MER-Caption+） | 57.36 | 36.35 | **46.86** |
| Chat-UniVi | 43.33 | 23.90 | 33.62 |
| SALMONN | 41.33 | 22.50 | 31.92 |
| Qwen-Audio | 28.22 | 16.27 | 22.25 |

最好的大模型在细粒度上也只有 ~47 分，且 S1→S2（跨集/跨年）掉 21 个点。
**结论：大模型给你的是"从不能做到勉强能做"，不是"做得好"。**
如果 AlwaysOnRec-HY4 的目标只是日记级别的粗情绪（中性/开心/低落/烦躁），这条质变用不上。

### 2）代价：延迟、显存、成本

- **延迟**：SenseVoice 论文（arXiv:2407.04051）Table 7 给了同族大小对照——
  SenseVoice-Small（234M，中型档）**RTF 0.007，10 s 音频 70 ms**；
  SenseVoice-Large（1587M，大型档）**RTF 0.110，10 s 音频 1623 ms**。
  大型档比同架构中型档慢约 **23 倍**，且 1.6 s/10 s 已经不是"近实时"，只能批量跑。
- **显存**（BF16 约 2 bytes/参数，仅权重）：Qwen2-Audio-7B 8B → **约 16 GB**；
  Qwen2.5-Omni-7B 10.7B → **约 21 GB**（与官方卡给出的一致）；
  WavLLM 7.55B → 约 15 GB。这几档都需要服务端 GPU。
- **两段式额外代价**：要同时驻留 ASR 与 LLM 两个模型，且 LLM 侧自回归出 token，
  延迟是"转写一遍 + 生成一遍"的叠加；R3 论文还报告提示词措辞极其敏感——
  把 "Predict the emotion" 换成 "Select the emotion"，准确率掉约 3 个点，
  这类脆弱性在无人值守的 24/7 流水线里没有兜底手段。
- **单次请求金钱成本**：**未检索到针对 SER 的公开 per-request 成本评测**，
  不给估算数字。可引用的量级只有上面的显存与 RTF。

### 3）幻觉风险：会不会给中性语音强加情绪？

**这是本项目最该警惕的一条，而最想要的那个数字恰恰没人测过。**

- **未检索到**"中性语音被误标为有情绪"的**公开假阳率评测**（以中性音频为输入、统计输出非中性标签的比例）。
  这一点不编数字。
- **最接近的替代证据**是 EmotionHallucer（arXiv:2505.11405），首个 MLLM 情绪幻觉基准：
  2,742 条对抗式二值问答，音频取自 RAVDESS 等，评测 38（后扩到 41）个模型。
  核心结果：**所有开源模型在含音频的全量集上都没超过 25% 的随机猜测线。**

  | 系统（EmotionHallucer 全量集） | Overall | FP Ratio（接受植入假情绪的比例） |
  |---|---|---|
  | Qwen2.5-Omni-7B | 18.65 | 0.44 |
  | Emotion-LLaMA | 15.43 | **0.71** |
  | Gemini-2.5-Pro | 44.17 | 0.52 |
  | Gemini-2.5-Flash | 45.06 | — |

  Emotion-LLaMA 的 Basic 子集 72.88、Hallucinated 子集只有 33.45，
  配合 FP Ratio 0.71，说明它**倾向于把被植入的、不存在的情绪当成真的**。

- **SER 场景内的直接证据**：C2SER（arXiv:2502.18186）明确点名 Qwen2-Audio 一类 ALM 在 SER 上产生幻觉，
  论文图 1 的实就是把一句欢快的话判成 sadness，并编造理由 "Maybe he is preparing for an exam"。
- **为什么这件事对 24/7 录音是致命的**：LISTEN（arXiv:2510.10444）测了 6 个音频大模型，
  发现它们普遍**词汇主导**——词汇线索中性时倾向直接预测 neutral，
  线索冲突时失效，纯副语言（不含语义）场景接近随机。
  也就是说模型判情绪高度依赖"说了什么"，而不是"怎么说"。
  一旦转写内容里有情绪词而说话人其实是平淡陈述，输出就会被文本牵着走。
- **综合判断**：中性音频的误标率没有公开数字；但从 FP Ratio 0.44–0.71、
  以及"线索冲突时失效"这一条看，**在大量中性音频上持续产出虚假情绪标签是高度可能的**。
  若一定要用大型档，必须先做一层"中性优先 / 低置信度即丢弃"的闸门，
  否则日记会被假情绪稀释到不可用。

---

## 中文与大型档

已检索到公开结果的中文基准：

- **CASIA**（中文，表演式）：SenseVoice-Large **WA 95.0**，SenseVoice-Small WA 70.0，
  Qwen-Audio WA 38.0，SALMONN WA 35.0（FunAudioLLM 论文 SER 对照表）。
  C2SER 零样本（Implicit CoT）CASIA **WA/UA 53.33**（arXiv:2502.18186）。
  注意 Large 与 Small 的 25 点差距、以及 Qwen-Audio 只有 38 分——
  **差的不是参数量，而是训练数据里有没有中文情感语料**。
  这一条比"用更大的模型"更能决定中文效果。
- **M3ED**（中文，多模态情感对话）：C2SER 零样本 **WA 50.57 / UA 36.68**（arXiv:2502.18186 Table 3）。
  UA 比 WA 低 14 点，说明中文上同样是"大类吃分、小类崩"。
- **MER2023 / MER2024 / MER2025**（中文）：SenseVoice-Large MER2023 WA 69.0；
  AffectGPT 在 MER-UniBench 上平均 74.77、MER2025 MER-FG 细粒度 Avg 46.86（见上文）。
  Emotion-LLaMA MER2023 F1 90.36（该数据集的闭集协议，分数偏高，不与跨集数字直接比）。
- **CHEAVD**：**未检索到**大型档（>500M）模型在 CHEAVD 上的公开评测结果。

**本节结论**：中文上大型档确实有用，但收益主要来自**中文情感训练数据**（SenseVoice 系），
而不是参数量本身；通用语音大模型（Qwen-Audio、SALMONN）在中文 CASIA 上只有 35–38 分，
远低于同等规模但见过中文情感数据的模型。若项目要覆盖中文，
"中型档 + 中文情感数据"的组合比"上大型档"更划算。

---

## 红线自检

1. **不存声纹**：SALMONN-7B / SALMONN-13B / WavLLM 已标 `speaker-capable`，
   仅作标注，**未出现在任何选型或结论性推荐里**。本档不给出落地推荐，只给客观记录。
2. **情绪标签非临床**：本文件所有数字都是情感分类指标，
   **不构成任何健康或临床判断，非诊断**。若后续要接抑郁/焦虑方向，
   最大规模抑郁语音检测研究的敏感度与特异度仅 71%，不得进入结论。
3. **不编造**：LTU、AffectGPT、C2SER 因许可或参数量查不到而**排除出表**，原因已逐条留痕；
   中性语音假阳率**明确写"未检索到"**；单次请求成本**明确写"未检索到"**，未给估算。

## 交叉引用

- 端侧可部署的最终判定不在本文件，见 `04-edge-deployment.md`（本表 `edge` 列只对大型档给出初判）。
- 跨档（小/中/大）对比结论见 `2026-09-landscape.md`。
- 中型档对照数字（CARE 160M、emotion2vec+ Large 300M、WavLM-base 等）见 `02-medium-models.md`。
