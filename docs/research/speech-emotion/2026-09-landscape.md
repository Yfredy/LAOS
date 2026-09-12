# 声学情感模型 Landscape：规模档 × {edge, multimodal}

> 调研时间：2026-09-12 ｜ 口径来源：[`00-taxonomy-and-metrics.md`](00-taxonomy-and-metrics.md)（**唯一口径来源**，含 6 条裁定）
> 数据基础：`01-small-models.md`（17 条）+ `02-medium-models.md`（18 条）+ `03-large-models.md`（11 条）= **46 条记录**，全部通过 `scripts/check_ser_table.py` 校验。
> 本文只做交叉与收敛，不新增记录；所有数字均带基准数据集名，**不同基准不可直接比较**。

---

## 0. 三条先立的口径事实（交叉表的地基）

1. **分档左闭右开**：小型 `[0, 30M)`、中型 `[30M, 500M)`、大型 `[500M, +∞)`。
   因此 **30M 归中型、500M 归大型**，`wav2vec2 / HuBERT / WavLM / UniSpeech-SAT` 的 **316M 级全部在中型档**（裁定 1），
   `emotion2vec_plus_large`（164M，官方标称 ~300M 存在冲突，裁定 2）也在中型档。
   大型档（>500M）几乎被**语音大模型 / LLM 路线**占满，纯卷积-Transformer 编码器很少超过 500M。
2. **「大型档普遍是多模态」不成立**（裁定 3 的连带结论）。裁定 3 规定「模态列记**推理时**的输入通道」：
   端到端 Audio-LLM（音频编码器直连 LLM，中间不产出转写文本）记 **`A`**。据此大型档里真正记 `A+T+V` 的
   **只剩 Qwen2.5-Omni-7B、Emotion-LLaMA、Phi-4-multimodal-instruct 三条**，多数是端到端纯音频 LLM。
3. **`edge` 的 `unknown(未找到公开转换案例)` 是合法值，不等于 `no`，也不等于 TBD。**
   它表示"没有证据"，不是"不行"。本表单独统计，不并入 `no`。

> **留痕（不改 03，待裁）**：`03-large-models.md` 主表里 **SALMONN-7B / SALMONN-13B 的模态列仍记 `A+T`**，
> 与 `05-multimodal.md` §8 交叉引用表的 `A（见裁定 3）` 不一致。按裁定 3（二者是端到端 Audio-LLM，
> 内部有 Whisper 编码器≠有 T 通道），**本表按 `A` 统计**。若按 03 表内字面值，大型档为 `A` 3 / `A+T` 5 / `A+T+V` 3、
> 多模态合计 8 —— 这一处差异不影响"真 `A+T+V` 只剩 3 条"这条结论。

---

## 1. 交叉表：规模档 × {edge, multimodal}

> **读法**：两列各自是对 46 条的**完整划分**（不是两个子集），同一条记录会同时出现在左右两列。
> 每格四项：模型数量 → 代表模型 → 典型 UAR 区间（必带基准）→ 典型延迟/内存。

### 1.1 主交叉表（3 × 2）

|  | **edge 轴**（端侧可部署） | **multimodal 轴**（推理时输入通道 ≥2） |
|---|---|---|
| **小型**<br>`[0, 30M)`<br>17 条 | **数量**：`yes` **4** / `no` **0** / `unknown` **13**<br>**代表**：YAMNet（3.7M，`yes: TFLite / ONNX / QNN，w8a8+w8a16 档齐全`）；FRILL（10.1M，TFLite INT8，Pixel 1 **8.5 ms/次**）；openSMILE ComParE_2016（`n/a(非神经)`，原生 C++，MCU 可直接运行）；Moonshine-tiny（27M，GGUF Q8_0 34 MB / ONNX，CPU ≈11.2× 实时）<br>**典型 UAR**：**本格无可引用的 UAR 区间**——17 条中只有 DistilHuBERT 报 UAR **61.4 (IEMOCAP LOSO, INT8)**，且它属 `unknown`；4 条 `yes` 全部只报 Acc/WAF（YAMNet **Acc 56.1 (IEMOCAP 4类)** / **55.1 (SERAB 跨库平均)**；FRILL **Acc 70.9 (CREMA-D)**；openSMILE **WAF 39.68 (MER2024 中文, eGeMAPS)**）。口径不同，不可换算<br>**典型延迟/内存**：YAMNet **0.096–0.699 ms**（AI Hub 多芯片多精度，0.96 s 输入），峰值内存 **0–37 MB**；中端 CPU（骁龙 7 Gen 4）**0.615 ms / RTF 6.4×10⁻⁴**；ESP32-S3 **≈500 ms/patch（RTF ≈0.52）**，arena ≈1.2 MB。DistilHuBERT 只有 INT8 体积 **23 MB**，时延**未检索到** | **数量**：多模态 **1** / 纯 `A` **16**（`A+T` **0**、`A+T+V` **0**）<br>**代表**：HiCMAE-T（20M，`A+V`，cross-attention MHCA 融合，VoxCeleb2 自监督权重）<br>**典型 UAR**：**UAR 66.85 (IEMOCAP)**；其纯音频分支（8M）**WAR 62.70 (IEMOCAP)** —— 来自 HiCMAE 表 10，**唯一一份把「缺模态」与「全模态」放在同一张官方表里的 SER 数字**<br>**典型延迟/内存**：`edge = unknown(未找到公开转换案例)`，**无任何工程数字**<br>**结论**：小型档 **0 条接入文本通道**，全部纯声学 → 反讽 / 讽刺类任务不在射程内 |
| **中型**<br>`[30M, 500M)`<br>18 条 | **数量**：`yes` **7** / `no` **0** / `unknown` **11**<br>**代表**：SenseVoice-Small（234M，`yes: ONNX Runtime INT8（sherpa-onnx 导出 228–229 MB）/ GGUF Q8_0（254 MB）`）；95M 档 5 条（wav2vec2-base 95.04 / HuBERT-base 94.68 / WavLM-base+ 94.70 / UniSpeech-SAT-base 94.68 / data2vec-base 93.75，`yes: ONNX Runtime INT8`）；emotion2vec_plus_large（164M，`yes: ONNX（FunASR 官方导出 648,972,628 B，误差 6.20e-6；导出的是帧级特征，非情感标签）`）<br>**典型 UAR**：**UA 54.19–69.47 (IEMOCAP, EmoBox 协议)**，其中 95M 档 **54.19–63.87**、316M 档 **67.42–69.47**。SenseVoice-Small 官方只报 WA：**70 (CASIA) / 68 (MER2023) / 70 (IEMOCAP)**，与 UA 不同口径不可相减<br>**典型延迟/内存**：WavLM-base+（与 95M 档同构）20 s 音频 NPU **129.22 ms**（SD8 Elite Gen 5）/ **251.325 ms**（8 Gen 3），但**峰值内存 1057–1597 MB**；CPU/TFLite **1421.172 ms**（8 Gen 3）、**2905.625 ms**（QCS8275）；SA7255P CPU 10 s 音频 **2.85 s（RTF 2.85×10⁻¹）**。SenseVoice-Small 10 s **≈70 ms（RTF ≈7×10⁻³，官方未标设备）**<br>**定位**：**时延不是门槛，内存才是**；B 档（proot 内 CPU）触发式可用，**A 档不成立** | **数量**：多模态 **4** / 纯 `A` **14**（`A+V` **3**、`A+T+V` **1**、`A+T` **0**）<br>**代表**：HiCMAE-B（81M，`A+V`，**UAR 68.21 (IEMOCAP)**）；AV-HuBERT Base（103M，`A+V`，early fusion；**A+V 融合 WAR 46.45 (IEMOCAP) 反低于其纯音频分支 58.54** ← early fusion 在模态质量不匹配时的典型失效）；Self-MM（103M 二手值，`A+T+V`，**无音频编码器**，声学用 COVAREP 预抽取特征；**Acc-2 80.04 / Acc-5 41.53 (CH-SIMS)**）<br>**典型 UAR**：**67.46 / 68.21 (IEMOCAP，HiCMAE-S / HiCMAE-B，HiCMAE 表 10 协议)**；与 EmoBox 的 UA 划分不同，**不可相减**<br>**典型延迟/内存**：**4 条 `edge` 全为 `unknown`，未检索到任何 runtime 转换案例，无工程数字**<br>**结论**：中型档的多模态**全是视觉（V）路线**；按 `05-multimodal.md` 的立场「不引入视觉模态」，这 4 条**只作记录、不作候选** |
| **大型**<br>`[500M, +∞)`<br>11 条 | **数量**：`yes` **0** / `no` **10** / `unknown` **1**（Phi-4-multimodal-instruct 5.6B）<br>**代表**：Qwen2-Audio-7B（8000M）、SenseVoice-Large（1587M，**权重未公开发布，`权重可得 = no`**）、WavLLM（7550M）<br>**典型 UAR**：本格 11 条中只有 R3 两段式报 UA：**64.67 (IEMOCAP，LoRA 指令微调)** / **49.72 (IEMOCAP，零样本)** / **52.27 (IEMOCAP，13B 零样本)**。其余报 ACC/WF1，不可比：Qwen2-Audio **ACC 54.0 (IEMOCAP)**、WavLLM **ACC 59.8 (IEMOCAP)**、SALMONN-7B **WF1 75.8 (IEMOCAP-4)**<br>**典型延迟/内存**：SenseVoice-Large **RTF 0.110（10 s 音频 1623 ms）**，是同架构中型档 SenseVoice-Small（**RTF 0.007 / 70 ms**）的**约 23 倍**；BF16 仅权重即 Qwen2-Audio-7B **≈16 GB**、Qwen2.5-Omni-7B **≈21 GB**、WavLLM **≈15 GB**。**7B 级语音大模型的端侧实测未检索到**<br>**结论**：**0 条可进端侧**，只能服务端 GPU、批量 | **数量**：多模态 **6** / 纯 `A` **5**（`A+T` **3**、`A+T+V` **3**、`A+V` **0**）<br>**代表**：Emotion-LLaMA（7000M，`A+T+V`，**F1 90.36 (MER2023)**，闭集协议分数偏高）；Qwen2.5-Omni-7B（10700M，`A+T+V`，**ACC 18.65 (EmotionHallucer 全量，随机基线 25.0)** —— **低于随机**）；Phi-4-multimodal-instruct（5600M，`A+T+V`，**ACC 41.0 (IEMOCAP)**）<br>**典型 UAR**：**UA 49.72–64.67 (IEMOCAP，R3 两段式)**；其余无 UAR<br>**典型延迟/内存**：Qwen2.5-Omni-7B BF16 **≈21 GB**；两段式（Cascade / R3）要同时驻留 ASR 与 LLM，延迟 = 转写一遍 + 生成一遍<br>**结论**：**「大型档普遍多模态」不成立**——裁定 3 之后多数（5/11）记 `A`，是端到端纯音频 LLM；且**幻觉风险高**：Emotion-LLaMA FP Ratio **0.71**、Qwen2.5-Omni **0.44**（EmotionHallucer），在大量中性音频上会产出虚假情绪 |

### 1.2 `edge` 三值计数（未知单独统计，不并入 `no`）

| 档 | 记录数 | `yes: <runtime>` | `no` | `unknown(未找到公开转换案例)` |
|---|---|---|---|---|
| 小型 | 17 | **4** | **0** | **13** |
| 中型 | 18 | **7** | **0** | **11** |
| 大型 | 11 | **0** | **10** | **1** |
| **合计** | **46** | **11（23.9%）** | **10（21.7%）** | **25（54.3%）** |

> `unknown` 占一半以上，是本次调研最该被记住的一个数：**"能不能端侧"这个问题，一半以上的模型没有公开证据**。
> 其中 13+11 条是"未找到公开转换案例"，另有 DistilHuBERT 属特例——它的 INT8 体积 23 MB 已核实，
> 但**未点名 runtime**，按"`yes` 必须带 runtime"降级为 `unknown`（见 `04-edge-deployment.md` §5.2）。

### 1.3 模态分布（裁定 3 口径）

| 档 | 记录数 | `A` | `A+T` | `A+V` | `A+T+V` | 多模态合计 |
|---|---|---|---|---|---|---|
| 小型 | 17 | 16 | 0 | 1 | 0 | **1** |
| 中型 | 18 | 14 | 0 | 3 | 1 | **4** |
| 大型 | 11 | 5 | 3 | 0 | 3 | **6** |
| **合计** | **46** | **35** | **3** | **4** | **4** | **11（23.9%）** |

- **真三模态（`A+T+V`）只有 4 条**：Self-MM（中型，103M 二手值）、Qwen2.5-Omni-7B、Emotion-LLaMA、Phi-4-multimodal-instruct。
  按 `05-multimodal.md` §6.1 的立场（**不引入视觉模态，默认永久不做**），这 4 条连同 4 条 `A+V` 全部**不进候选**。
- `A+T` 的 3 条全部是 **ASR + LLM 两段式**（Cascade、R3-7B、R3-13B），参数量按口径写了两段之和；
  端到端 Audio-LLM（Qwen2-Audio、SALMONN、WavLLM）记 `A`。

---

## 2. 按场景推荐

| 场景 | 约束（判据） | 推荐档位 | 推荐模型 / 通道 | 关键数字 | 不推荐什么，为什么 |
|---|---|---|---|---|---|
| **① 常驻低功耗**<br>（漏斗①） | 无触发时也要醒着；功耗预算 **≤ 25 mW**（≈3%/天，hardware-power.md §0） | **不落在 46 条内**：A 档真端侧 + 极小型（<1M 量级） | laos 既有 **TIM-Net int8**（34,671 参数 / **0.4 MB**；蒸馏版 **~174 KB .eaix**）→ QNN aDSP/LPAI，已跑通 HTTP→JNI→QNN 闭环 | **46 条中 0 条满足常驻预算**；`04` §4.3 明确：**未检索到任何"端侧声学 SER 做到 <100 mW 常驻"的实测**。连 Edge TPU 上 1.8 MB 的 INT8 情绪模型连续推理都是 **2.5 W** | ❌ proot 内常驻（**400–1000 mW**，比 aDSP 贵 2–3 个数量级）；❌ YAMNet / openSMILE 做常驻情感（YAMNet **SERAB 跨库 Acc 55.1**；openSMILE eGeMAPS **MER2024 WAF 39.68**）——工程余量与任务精度在小型档上直接冲突 |
| **② 近实时日记**<br>（漏斗③） | 触发后运行；**RTF ≤ 0.1**（10 s 音频 ≤1 s）；**必须离线** | **中型档 · B 档（proot 内 CPU）** | **sherpa-onnx 1.13.8 + SenseVoice-Small int8（234M）**，一次前向同时出 文本 / 语种 / 情感 / 事件 | ONNX INT8 **228–229 MB**、GGUF Q8_0 **254 MB**；10 s 音频 **≈70 ms（RTF ≈7×10⁻³，官方未标设备）**，社区 RTF **0.1–0.3**；**WA 70 (CASIA)、68 (MER2023)、70 (IEMOCAP)** | ❌ `funasr` 通道（需装 torch，**GB 级内存 + 数秒加载**，唯一 RTF 证据来自 PC）；❌ 95M SSL 编码器（同构 WavLM-base+ **峰值内存 1057–1597 MB**，常驻内存先崩）；❌ 任何云 API（违反隐私前提） |
| **③ 事后批量分析**<br>（漏斗④ / 回顾） | 非实时；充电 + Wi-Fi；用户**显式授权**的回顾模式 | **中型档批量**为默认；**大型档**仅在确实需要细粒度情感描述时启用 | 默认 SenseVoice-Small 批量（限线程数比换模型更省电：wav2vec2 在 RPi 上 4 核→1 核，**2.9 W→1.1 W**）；需细粒度时 **Qwen2-Audio-7B**（8B，Apache-2.0，权重可得，端到端） | SenseVoice-Large **RTF 0.110（10 s → 1623 ms）**，为 Small 的约 **23 倍**；Qwen2-Audio-7B **ACC 54.0 (IEMOCAP)**、BF16 **≈16 GB** | ❌ 任何云 API（GPT-4o-audio / Gemini）：等于把 24 h 连续录音上传第三方，**直接违反 laos 的隐私前提**；❌ 两段式（Cascade / R3）做无人值守流水线（提示词措辞极敏感，改一个词掉约 3 个点）；❌ SenseVoice-Large（**权重未公开发布，`权重可得 = no`**） |

**中文场景的两条硬提醒**（与档位无关，但会直接改变选型）

- **中文上不要选 emotion2vec**：英文 IEMOCAP **WA 71.79**，但 MER2024 中文只有 **WAF 56.08**，被同为 95M 的 HuBERT-base（**69.26**）甩开约 13 点。原因是其预训练语料 Emo-262 是**纯英文**。
  中文侧优先 **Chinese-HuBERT（MER2024 WAF 72.67，MIT）** 或 **HuBERT-base（69.26）**。
- **量化停在 INT8，别下 INT4**：INT8 在 SER 上有同行评审的"无损"证据（**0.88 → 0.88**）；INT4 在音频任务上有"崩"的证据（Conformer WER **15.94 → 38.49**），且 SER 的 INT4 数据完全空白。

---

## 3. 选型决策树

> 输入是**部署约束**，输出是**档位 + 具体模型**。每一步都给出判据；判据里带数字的，数字即阈值。

```
起点：laos 情绪通道选型（46 条记录 / 3 档 × 2 标记）
│
├─ Q1 · 这个通道要不要「无触发也醒着」的常驻？
│     判据：功耗预算是否必须 ≤ 25 mW（≈3%/天）
│     ├─ 否 → 跳到 Q4（触发后运行）
│     └─ 是 → Q2
│
├─ Q2 · 能不能出端？（原生 Android App + aDSP/LPAI 授权）
│     判据：是否有高通授权 + 厂商签名。未授信进程走 fastrpc attach 音频 PD
│           直接返回 -EACCES；第三方 App 能自由使用的只有 HTP（瓦级）
│     ├─ 不能（proot Ubuntu / Termux）→ 判定【常驻否决】→ 转 Q4
│     │     理由：任何醒着的 proot 进程 400–1000 mW，比 aDSP 贵 2–3 个数量级
│     └─ 能 → Q3
│
├─ Q3 · 出端之后拿到的是哪种计算单元？
│     判据：aDSP / Sensing Hub（官方 <1 mA，mW 档）vs HTP / NPU（1–4 W，瓦档）
│     ├─ aDSP / LPAI → ✅【A 档 · 真端侧 · 极小型】
│     │     模型：TIM-Net int8（34,671 参数 / 0.4 MB；蒸馏版 ~174 KB .eaix）
│     │     ⚠ 46 条记录中 0 条有 A 档实测；本条来自 laos 既有原型，
│     │       且无 on-device RTF / 功耗实测（唯一 ≈6 ms 是 CPU 后端推算）
│     └─ 只有 HTP → 判定【常驻仍否决】（1–4 W）→ 转 Q4 触发式
│
├─ Q4 ·（触发后运行）要不要实时 / 近实时？
│     判据：RTF ≤ 0.1（10 s 音频 ≤ 1 s）且端到端在数百 ms 内返回
│     ├─ 是（漏斗③）→ Q5
│     └─ 否（批量 / 事后）→ Q7
│
├─ Q5 · 允不允许联网（出端上云）？
│     判据：laos 是边缘优先、可离线系统；联网 = 把 24 h 连续录音上传第三方
│     ├─ 允许 → 本分支结果不变：云 API 路线被隐私红线一票否决，仍落到 Q6
│     └─ 不允许（默认）→ Q6
│
├─ Q6 · 运行时形态：一体化前向，还是「声学编码器 + 自接分类头」？
│     判据：漏斗③ 本来就跑 ASR —— laos 的真实位置是 A+T 档，不是 A 档
│     ├─ 一体化（推荐）→ ✅【中型档 · B 档 proot CPU】
│     │     模型：sherpa-onnx + SenseVoice-Small int8（234M）
│     │     判据数字：ONNX INT8 228–229 MB；10 s ≈70 ms（RTF ≈7×10⁻³）
│     │               一次前向出 文本 / 语种 / 情感 / 事件
│     │               WA 70 (CASIA)、68 (MER2023)、70 (IEMOCAP)
│     │     不选 funasr：需 torch（GB 级内存 + 数秒加载），唯一 RTF 证据来自 PC
│     └─ 编码器 + 自接头（备选）→ 【中型档 · 95M 档】
│           模型：Chinese-HuBERT（95M，MIT，MER2024 WAF 72.67）+ 自接分类头
│           ⚠ edge = unknown：无官方端侧导出、无 proot 实测
│           ⚠ 同构的 WavLM-base+ 实测峰值内存 1057–1597 MB，内存先崩
│           ⚠ 中文上选 emotion2vec 是反向：MER2024 WAF 56.08 vs HuBERT-base 69.26
│
└─ Q7 ·（批量）需要细粒度情感描述吗？
      判据：粗分类中型档就够；只有「细粒度 / 上下文依赖」这一档大模型才是质变
            （但质变是「从不能做到勉强能做」，MER-FG 最好也只有 Avg 46.86）
      ├─ 不需要 → ✅【中型档 · 批量】SenseVoice-Small，充电 / Wi-Fi 时批量跑
      └─ 需要 → ✅【大型档 · 服务端 GPU】Qwen2-Audio-7B（8B，Apache-2.0，权重可得）
                ⚠ 必须加「中性优先 / 低置信度即丢弃」闸门：
                   EmotionHallucer FP Ratio 0.44–0.71；
                   中性音频被误标的假阳率**未检索到**公开评测，不给数字
                ⚠ SenseVoice-Large（1587M，CASIA WA 95.0）权重未发布，不可用
```

**判据速查（一步一阈值）**

| 步骤 | 判据 | 阈值 / 判据数字 | 通过走 | 不通过走 |
|---|---|---|---|---|
| Q1 | 是否常驻 | 预算 ≤ 25 mW | Q2 | Q4 |
| Q2 | 能否出端 | 有 aDSP/LPAI 授权（不是 root，是签名授权） | Q3 | Q4（常驻否决） |
| Q3 | 计算单元类别 | aDSP <1 mA（mW 档）vs HTP 1–4 W | A 档 TIM-Net | Q4（常驻否决） |
| Q4 | 是否近实时 | RTF ≤ 0.1 | Q5 | Q7 |
| Q5 | 能否联网 | 隐私红线：24 h 录音不得上传第三方 | 结果不变 → Q6 | Q6 |
| Q6 | 是否复用 ASR 前向 | laos 已在 A+T 档，T 的边际成本为零 | 一体化 SenseVoice-Small | 编码器 + 自接头（Chinese-HuBERT） |
| Q7 | 是否要细粒度 | 粗分类 = 4–9 类标签；细粒度 = 自由文本描述 | 大型档 Qwen2-Audio-7B | 中型档批量 |

---

## 4. 与 Task 8 落地的关系

1. **`04-edge-deployment.md` §8 已论证候选通道 `sherpa-onnx` 优于 `funasr`**：sherpa-onnx 有官方 `manylinux2014_aarch64`
   与 `android_arm64-v8a` wheel、不依赖 torch、**一个前向同时产出文本 / 语种 / 情感 / 事件**；而 funasr 路径要装 torch
   （GB 级内存、数秒加载），且唯一 RTF 证据来自 PC。这条把决策树 Q6 的"一体化"分支钉死了。
2. **laos 当前真实位置是 `A+T` 档**（漏斗③ 已有 ASR），不是 `A` 档。按 `05-multimodal.md` §6.2，
   从 `A+T` 再往前加视觉的增量只有 **+1.5 ~ +5.0 点**（IEMOCAP +1.54 / CMU-MOSEI +1.63 / MER2024-SEMI +2.67 /
   MER2024-NOISE +4.88 / MER2025 +4.99），换来的却是 3 条法律否决项 + 2 个数量级的功耗 + 与"原数据即焚"的架构互斥。
3. **这两条如何约束选型**：它们把问题从"挑一个 SER 模型"改写成"**挑一条能复用 ASR 前向的通道**"。
   于是 46 条里的 11 条多模态记录全部退化为**排除项**（不进候选），选型空间压到 `A` / `A+T` 两类，
   而 `A+T` 里真正可用的只有"一次前向出文本 + 情感"的一体化形态 —— 答案因此收窄到
   **中型档 SenseVoice-Small（sherpa-onnx）**。
4. **留给 Task 8 的两件事**（本文不动代码）：① 通道命名建议取 **`sherpa`**（由 runtime 名 + 本文结论导出，
   非凭空命名），最终以 Task 8 为准；② 新通道与既有 `classify_mood()`（只输出高唤醒/平稳/低唤醒/短促）
   的职责边界，由 Task 8 在 `06-adoption.md` 里划定。

---

## 5. 红线自检

- **不存声纹**：ECAPA-TDNN、WavLM、UniSpeech-SAT、AV-HuBERT、SALMONN、WavLLM 已标 `speaker-capable`，
  **未出现在任何推荐分支里**；推荐的 SenseVoice-Small 不产出说话人嵌入。
- **情绪标签非临床**：本文所有指标均为情绪分类/表征指标，**非诊断**；健康方向的上限（敏感度与特异度均约 71%）
  已在 `00` 记录，未进入任何结论。
- **不编造**：UAR 缺数字的格写"本格无可引用的 UAR 区间"并说明理由；延迟/内存缺的写"未检索到"；
  中性音频假阳率、SER 的 INT4 数据均明确写 `未检索到`，**不给估算**。

## 6. 交叉引用

- 口径与 6 条裁定：[`00-taxonomy-and-metrics.md`](00-taxonomy-and-metrics.md)
- 规模轴：[`01-small-models.md`](01-small-models.md) / [`02-medium-models.md`](02-medium-models.md) / [`03-large-models.md`](03-large-models.md)
- 端侧轴（proot 两档、runtime 对比、实测预算）：[`04-edge-deployment.md`](04-edge-deployment.md)
- 多模态轴（不引入视觉模态的论证）：[`05-multimodal.md`](05-multimodal.md)
- HTML 全景：[`../../speech-emotion-models.html`](../../speech-emotion-models.html)
