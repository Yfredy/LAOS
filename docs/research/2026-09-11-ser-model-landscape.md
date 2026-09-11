# 语音情感识别（SER）模型全景：端侧 / 小型 / 中型 / 大型 / 多模态

> 调研时间：2026-09-11 ｜ 定位：为 laos 听觉链路的**情感标签能力**做模型选型地图。
> 与 [always-on-recording/academic-papers.md](always-on-recording/academic-papers.md) §5（情感的临床应用/vocal biomarkers 线）互补：
> 那篇回答"情感数据能用来做什么"，本篇回答"用什么模型算出情感"。
>
> 记法：✅ 官方源已查证 ｜ 🔶 第三方/媒体/推算声称 ｜ 参数量均为模型卡或论文口径。

---

## 1. 一句话结论

1. **SER 已经分裂成三个物种**：专用判别模型（90M–317M，IEMOCAP 上微调精度最高）、
   一体化语音底座（SenseVoice 类，ASR+情感一次推理，延迟最低）、音频原生 LLM（7B 级，零样本可比微调）。
   **没有单一赢家——选型由"跟谁一起算"决定**：laos 的 journal 管线里情感和转写同源（SenseVoice 一石二鸟），
   这条路是对的；单独升级情感精度时才换 emotion2vec+。
2. **多模态是另一个联赛**：MELD/MER2023 的 SOTA（Emotion-LLaMA F1 0.9036）全部依赖视频+音频+文本三模态。
   laos 是纯听觉系统，**多模态 SOTA 数字不能作为 laos 的对标线**（任务不同：对话情感 vs 旁观语音）。
3. **对 laos 真正重要的结论来自 OmniVox**（arXiv:2503.21480）：omni-LLM **零样本** SER 在 IEMOCAP 上
   比肩甚至偶超微调专用模型——意味着"语义级情感理解"不必训模型，将来接 7B 音频 LLM 即得，
   但这属于**充电/批量档**的算力，ADSP 常驻仍只能靠小型判别模型。

## 2. 五类模型全景表

### 2.1 支持端侧部署的模型（"能跑在哪"维度，跨参数量）

| 模型 | 参数量 | 端侧运行时 | 实测/声称指标 | laos 现状 | 来源 |
|---|---|---|---|---|---|
| **TIM-Net**（Temporal Identity-Aware Network, ICASSP 2023） | ~0.1–0.5M 量级 🔶（时域多尺度卷积，极轻） | **QNN/Hexagon ADSP**（laos 真机已验证）、TF/ONNX | 多尺度上下文情感表征，SERBench 上与池化大模型打平 | **在用**：App 内 ADSP LPAI 岛 <5mW 常驻情感识别 | [GitHub](https://github.com/Jiaxin-Ye/TIM-Net_SER) ✅ |
| **SenseVoice-Small** | **234M** | FunASR / ONNX；手机 AP 可跑 | **10s 音频 ~70ms** 推理（非自回归）；比 Whisper-Small 快 5× | **在用**：drv_ear 转写+情感标签（4 类+事件） | [HF 模型卡](https://huggingface.co/FunAudioLLM/SenseVoiceSmall) ✅ |
| **emotion2vec_plus_base** | **~90M** | FunASR 生态（ModelScope 下载）；CPU/GPU | 9 类细粒度情感；13 数据集 10 语言验证泛化 | 备选通道（见 §3） | [HF](https://huggingface.co/emotion2vec/emotion2vec_plus_base) ✅ |
| 经典特征 + ML（eGeMAPS 88 特征 + SVM/RF） | ~0（无神经网络） | 任意 MCU/DSP | SERAB 上仍是强基线；毫秒级、零依赖 | laos 的 vad.py 同款零依赖哲学，可做兜底通道 | [SERAB](https://averageie.github.io/serab) 🔶 |

**端侧部署结论**：laos 真机路径（TIM-Net on ADSP <5mW）已是业界少见的"真·端侧常驻"实践；
AP 档 SenseVoice-Small（70ms/10s）足够 journal 蒸馏；不需要再找别的端侧模型。

### 2.2 小型模型（<30M + 经典方法）

| 模型/方法 | 规模 | 精度锚点 | 备注 |
|---|---|---|---|
| TIM-Net | ~0.1–0.5M 🔶 | SERBench 六语料平均高于 CNN/attention 同规模基线 | 小型档的**精度之王**，laos 真机模型 |
| eGeMAPS + SVM/RF | 88 维特征 | 4 分类 WA ~65–75%（语料相关）🔶 | 可解释、零训练成本、跨语料掉点快 |
| 谱图 CNN（CRNN/light） | 0.1–5M | IEMOCAP 4 类 WA ~55–65% 🔶 | 量化后 MCU 可跑；精度天花板低 |
| whisper-encoder 蒸馏小模型 | <30M | 无公认 SOTA | 研究阶段，不建议生产 |

**判断**：小型档精度天花板明显（IEMOCAP 4 类 55–75%），但**功耗成本三个数量级地便宜**。
laos 的正确姿势是小型档做**常驻差分**（情绪变化趋势），不是绝对判定——与 §5 临床线"纵向差分"结论一致。

### 2.3 中型模型（90M–400M，当前 SER 精度主力）

| 模型 | 参数量 | 9/4 类 | 精度锚点 | 许可/生态 | 来源 |
|---|---|---|---|---|---|
| **emotion2vec_plus_large** | **~300M**（4.2 万小时伪标微调） | 9 类 | 13 数据集 10 语言 SOTA；IEMOCAP 线性探测超所有同规模 SSL（ACL 2024 口径） | ModelScope/FunASR，学术友好 | [HF](https://huggingface.co/emotion2vec/emotion2vec_plus_large) ✅ |
| **emotion2vec_plus_base** | ~90M | 9 类 | 同上系列的性价比档 | 同上 | ✅ |
| wav2vec2-base SER（audeering 等） | 95M | 连续维度（valence/arousal/domination） | EmoBox 32 语料基准的常客 | MIT（audeering 卡）🔶 | [EmoBox](https://arxiv.org/abs/2406.07162) ✅ |
| wav2vec2-large SER | 317M | 分类/维度 | EmoBox 上限档 | 研究 | ✅ |
| HuBERT/wavlm 微调 SER | 95–317M | 4 类 | SUPERB/SERAB 标准基线 | 研究 | [SERAB](https://averageie.github.io/serab) 🔶 |

**基准工具**（选型必读）：
[EmoBox](https://emo-box.github.io/)（Interspeech 2024，32 数据集/14 语言/26.2 万句/10 个预训练模型统一基准，[arXiv:2406.07162](https://arxiv.org/abs/2406.07162) ✅）与
[SERAB](https://averageie.github.io/serab)（跨语料泛化适配基准）。
**任何"我的 SER 精度 xx%"的说法都应先问：哪个语料、几分类、UAR 还是 WAR**——这是本调研最重要的方法论结论。

### 2.4 大型模型（≥1B 音频原生 LLM）

| 模型 | 参数量 | 情感能力口径 | 许可 | 来源 |
|---|---|---|---|---|
| **Kimi-Audio-7B**（月之暗面） | 7B（13M+ 小时预训练） | **官方支持 SER 且宣称 SOTA**，自带 SER 评测集 | Apache-2.0（权重）/MIT（代码） | [GitHub](https://github.com/MoonshotAI/Kimi-Audio) ✅ [技术报告](https://arxiv.org/abs/2504.18425) ✅ |
| **Qwen2.5-Omni-7B**（阿里） | 7B（Thinker-Talker；Qwen3-Omni 已发布） | MMAU 音频理解强；语音情感走零样本问答 | Apache-2.0 | [HF](https://huggingface.co/Qwen/Qwen2.5-Omni-7B) ✅ [报告](https://arxiv.org/abs/2503.20215) ✅ |
| SALMONN（字节/清华） | 13B | 早期音频 LLM 情感问答 | 研究 | 🔶 |
| 商用闭源（GPT-4o-audio / Gemini 音频档） | 未公开 | 情感感知在系统卡中提及 | 闭源（违反 laos 零云约束） | — |

**关键证据**：[OmniVox（arXiv:2503.21480）](https://arxiv.org/html/2503.21480v1) ✅——
omni-LLM **零样本** SER 在 IEMOCAP/MSP-Podcast 上"不仅比肩、有时超过"微调专用模型。
**对 laos 的意义**：语义级情感（"他在压抑愤怒"）不必训练，将来在 PC GPU 档接 Kimi-Audio/Qwen-Omni 即得；
但 7B 推理是瓦级功耗，只能进 **journal 批量/充电档**，与四段漏斗的常驻档严格分开。

### 2.5 多模态情感识别模型（音+视+文）

| 模型 | 基座 | 基准成绩 | 备注 | 来源 |
|---|---|---|---|---|
| **Emotion-LLaMA**（NeurIPS 2024） | LLaMA + 情感专用音/视/文编码器 | **MER2023-SEMI F1 0.9036（冠军）**；MELD 领先；EMER 情感推理 Clue Overlap 7.83 | 多模态情感推理开创者 | [arXiv:2406.11161](https://arxiv.org/html/2406.11161v1) ✅ [GitHub](https://github.com/zebangcheng/emotion-llama) ✅ |
| **Emotion-LLaMAv2 + MMEVerse** | v2 四组件管线 | 自带 MMEVerse 基准（可复现研究底座） | 2025/2026 延续 | [arXiv:2601.16449](https://arxiv.org/html/2601.16449v2) ✅ |
| **HumanOmni**（2025） | 14M 人为中心视频指令 + **2.4M 情感标注**；有 **0.5B 小档** | 人本场景情感/表情强；R1-Omni（强化学习情感推理）以 HumanOmni-0.5B 为底 | **0.5B 档是"多模态里最像端侧"的** | [arXiv:2501.15111](https://arxiv.org/html/2501.15111v1) ✅ |
| MELD 榜单其他（DialogueMLLM 等） | MLLM | MELD WF1 68.57% | MELD 本身是困难基准（影视对话） | 🔶 |

**laos 立场**：多模态 SOTA 依赖视频（人脸/表情），laos 是纯听觉系统且隐私红线不含摄像头——
**此档为"了解边界"而非"选型对象"**。唯一例外路径：若未来 laos 用户主动授权照片/视频场景，HumanOmni-0.5B 是唯一值得看的入门档。

## 3. 对 laos 的选型映射（落地结论）

| laos 场景 | 现状 | 建议模型 | 理由 |
|---|---|---|---|
| ADSP 常驻（漏斗①/情绪事件） | TIM-Net <5mW ✅ | **维持 TIM-Net** | 小型档精度之王 + 已验证；只做情绪**差分事件**不做绝对判定 |
| journal 蒸馏（漏斗③，PC GPU / 手机 AP） | SenseVoice-Small 情感标签 ✅ | **维持 SenseVoice**（转写+情感一石二鸟，70ms/10s） | 情感与转写同源，省一次推理；4 类粒度够日记用 |
| 情绪周报精化（可选增量） | mood_report 按 4 类聚合 | **emotion2vec_plus_large（300M）批处理通道** | 9 类细粒度（surprised/disgusted/fear）让周报曲线更有信息量；300M 在 RTX 4060 批处理无压力 |
| 语义级情感理解（远期可选） | 无 | Kimi-Audio-7B / Qwen2.5-Omni（本地 GPU，充电档） | OmniVox 证明零样本可比微调；严格与常驻档分开 |
| 多模态 | 无，也不该有 | **明确不做**（摄像头违背隐私设计） | HumanOmni-0.5B 记录在案即可 |

**两条不变的红线**（承接 §5 临床线结论）：
1. 情感标签只做**纵向差分**（相对个人基线），不做绝对判定——任何模型的绝对精度都不支持临床化表述；
2. 情感模型输出的敏感度（如抑郁筛查 71% = 1/3 误报）决定了告警必须收敛为"建议关注"，不是诊断。

### §1.1 文献跟踪后的修正（2024–2026 逐篇见 §6）

- **emotion2vec+ 系列比本文 §2.3 表更细**：官方还有 `seed`/`small` 更小档（9 类标签体系统一微调），是端侧 SER 最直接的候选序列——端侧选型事实上收敛为"emotion2vec 系特征 + 轻量头"。
- **MER2025 挑战赛基线**（ACM MM 2025，[arXiv:2504.19423](https://arxiv.org/abs/2504.19423)）：三模态融合基线 WAF 78.63，靠的是 HuBERT/wav2vec2 特征 + 简单分类头——**直接验证 laos "SenseVoice/SSL 特征 + 轻量头"路线是性价比最优解**，不是妥协。
- **Interspeech 2025 自然条件 SER 挑战赛**（说话人无关 + 类别/维度双赛道，[ISCA](https://www.isca-archive.org/interspeech_2025/naini25_interspeech.html)）：这是 laos 情绪差分（连续维度、跨说话人）的**官方对标口径**。
- **新增两个必读基准**：VoxEmo（[arXiv:2603.08936](https://arxiv.org/abs/2603.08936)，2026，35 语料/15 语言的 Speech-LLM SER 基准）、AffectGPT（ICML 2025，生成式情感描述新范式）。

## 4. 可选落地项（如需执行另行确认）

1. **drv_ear 增加 `emotion2vec` 备选通道**（`LAOS_EAR_EMOTION_CHANNEL=funasr|emotion2vec`）：模仿现有 `LAOS_ASR_CHANNEL` 双通道模式，emotion2vec_plus_base 走 FunASR 生态；默认关（SenseVoice 标签已够用）
2. **mood_report 支持细粒度 9 类聚合**：EMOTION_GLYPHS 扩表 + 堆积图列序稳定
3. **EmoBox 口径写进 mood_report 文档**：声明 laos 情绪曲线"不做跨人比较、不做绝对精度声明"

## 5. 参考来源

核心（正文各表已内嵌链接，此处为最关键 eight）：
[emotion2vec (arXiv:2312.15185)](https://arxiv.org/html/2312.15185v1) ｜
[emotion2vec_plus_large 模型卡](https://huggingface.co/emotion2vec/emotion2vec_plus_large) ｜
[SenseVoiceSmall 模型卡](https://huggingface.co/FunAudioLLM/SenseVoiceSmall) ｜
[TIM-Net_SER](https://github.com/Jiaxin-Ye/TIM-Net_SER) ｜
[EmoBox (arXiv:2406.07162)](https://arxiv.org/abs/2406.07162) ｜
[Kimi-Audio 技术报告 (arXiv:2504.18425)](https://arxiv.org/abs/2504.18425) ｜
[Qwen2.5-Omni 技术报告 (arXiv:2503.20215)](https://arxiv.org/abs/2503.20215) ｜
[OmniVox (arXiv:2503.21480)](https://arxiv.org/html/2503.21480v1) ｜
[Emotion-LLaMA (arXiv:2406.11161)](https://arxiv.org/html/2406.11161v1) ｜
[HumanOmni (arXiv:2501.15111)](https://arxiv.org/html/2501.15111v1)

---

## 6. 文献跟踪（2024–2026，逐篇）

> 由三路文献调研子代理于 2026-09-11 执行；每条含贡献/关键数字/与端侧选型的关系；🔶 = 未在官方源逐字核实。

### 6.1 基座与基准演进

- **emotion2vec**（Ziyang Ma 等，阿里 FunAudioLLM；ACL 2024 Findings）[arXiv:2312.15185](https://arxiv.org/abs/2312.15185)
  首个通用语音情感表征基座（data2vec 式在线蒸馏，262h 开源情感数据预训练）；免微调特征即超主流 SSL 模型。→ laos 情感特征前端的事实标准。
- **emotion2vec+ 系列（seed/small/base/large）**（同团队，2024-05 起）[HF](https://huggingface.co/emotion2vec/emotion2vec_plus_large)、[GitHub](https://github.com/ddlBoJack/emotion2vec)
  9 类标签体系统一微调的"SER 界 Whisper"；多档尺寸给端侧留了 seed/small 入口。🔶 各档训练小时数未见独立论文。
- **Emotion2Vec-S**（经 C²SER 论文确认在演进）：emotion2vec 的半监督扩展，已进入 TASLP 正式发表管线。→ emotion2vec 谱系仍在持续，端侧特征端选它不担心断代。
- **EmoBox**（Interspeech 2024）[arXiv:2406.07162](https://arxiv.org/abs/2406.07162)、[DOI](https://doi.org/10.21437/Interspeech.2024-788)
  32 数据集/14 语言统一划分；**核心发现：intra-corpus 高分掩盖 cross-corpus 泛化差**（24 个数据集 cross-corpus 评测）。→ laos 选型必须看 cross-corpus 口径。

### 6.2 挑战赛（MER 2024/2025、Interspeech 2025）

- **MER 2024**（Lian 等，ACM MM 2024）[arXiv:2404.17113](https://arxiv.org/abs/2404.17113)
  三赛道：MER-SEMI（半监督）/ MER-NOISE（噪声鲁棒）/ MER-OV（开放词表）；样本扩至 120,625；94 支队伍。→ MER-NOISE 赛道结论直接对应"麦克风真实噪声下 SER 退化"。
- **MER 2025**（ACM MM 2025 / MRAC'25 Workshop）[arXiv:2504.19423](https://arxiv.org/abs/2504.19423)、[DOI](https://doi.org/10.1145/3746027.3762007)
  四赛道（SEMI/FG/DES/PR）；MER-SEMI 132,171 样本；三模态融合基线 **WAF 78.63±0.53**（HuBERT/wav2vec2 特征+轻量头）；MER-FG 基线 Avg=46.86 vs zero-shot MLLM 最强 36.80。🔶 各赛道最终冠军名次未公开汇总。
- **More Is Better: MoE 情感框架**（MRAC'25，MER-SEMI 亚军）[arXiv:2508.06036](https://arxiv.org/abs/2508.06036)
  多专家聚合多库特征——云端竞赛玩法，端侧只可当精度上界参考。
- **Interspeech 2025 SER Challenge（自然条件）**（Naini, Busso 等）[ISCA](https://www.isca-archive.org/interspeech_2025/naini25_interspeech.html)、[DOI](https://doi.org/10.21437/Interspeech.2025-1972)
  MSP-Podcast 说话人无关划分，类别+维度双赛道。→ **laos 情绪差分（连续维度、跨说话人）的官方对标口径**。
- **Noise-Robust SER with Shared SSL Representations + Integrated Enhancement**（NTU BIIC；Interspeech 2025）[PDF](https://lab-msp.com/MSP/publications/Tzeng_2025.pdf)、[GitHub](https://github.com/RogerTzeng/biic_IS2025_SER_Challenge)
  语音增强与 SER 共享同一 SSL 表征减缓噪声退化；🔶 作者 GitHub 自报 Valence 赛道 Top-1。→ "增强+识别共享前端"对端侧算力友好，值得 laos 借鉴。

### 6.3 生成式情感理解与音频 LLM

- **AffectGPT**（Lian 等；ICML 2025）[arXiv:2501.16566](https://arxiv.org/abs/2501.16566)
  MER-Caption+ 31,327 样本；把 SER 从离散分类推进到自由文本描述（MER-FG S1=57.36）。
- **C²SER**（西工大；IEEE TASLP 2025）[arXiv:2502.18186](https://arxiv.org/abs/2502.18186)、[DOI](https://doi.org/10.1109/TASLPRO.2025.3648793)
  音频 LLM 双编码器（Whisper 语义 + Emotion2Vec-S 声学）+ CoT + 自蒸馏抑制情感幻觉；优于 Qwen2-Audio 与 SECap 🔶（数值在正文）。
- **OmniVox**（2025，投稿 COLM）[arXiv:2503.21480](https://arxiv.org/abs/2503.21480)
  4 个 omni-LLM 零样本 SER 系统评测 + "acoustic prompting"：零样本可持平/偶超微调模型（IEMOCAP+MELD）。→ laos 取其 prompt 设计，不取模型本体。
- **VoxEmo**（2026）[arXiv:2603.08936](https://arxiv.org/abs/2603.08936)
  首个面向 Speech-LLM 的大规模 SER 基准（35 语料/15 语言/多档 prompt）。→ 可当"哪类模型值得蒸馏到端侧"的筛选器。
- **Affective Computing Has Changed: The Foundation Model Era**（Schuller；Nature 系期刊 2025）[Nature](https://www.nature.com/articles/s44387-025-00061-3)
  立场综述：基础模型正在重写情感计算范式。

### 6.4 个性化（laos 高度契合的新主线）

- **Meta-PerSER**（Interspeech 2025）[arXiv:2505.16220](https://arxiv.org/abs/2505.16220)
  元学习对单个听者/标注风格做少样本个性化适配——承认情感标注主观性。→ **端侧设备天然贴近单一用户，few-shot 用户校准与 laos 场景高度契合**。
- **Individual-aware Attention Modulation**（Fang 等；IEEE Trans. Affective Computing 16(2), 2025）[记录页](https://psycnet.apa.org/record/2026-28271-052)
  个体感知注意力调制，未见说话人仍保持判别。🔶 指标数值未在摘要级来源核实。

### 6.5 三条趋势

1. **SSL 情感基座成默认骨干、评测统一化**：emotion2vec→+→S 谱系完整，EmoBox 统一划分；端侧选型收敛为"emotion2vec 系特征+轻量头"。
2. **从分类到生成式情感理解**：MER-DES/AffectGPT/C²SER 把输出转向自由文本+思维链，可解释性成新指标；但与端侧算力的矛盾未解。
3. **自然条件与个性化并进**：Interspeech 2025 挑战（说话人无关+维度）、MER-NOISE 把战场移向 in-the-wild；Meta-PerSER/TAC 工作推动 few-shot 用户校准。

### 6.6 三个未解问题

1. 音频 LLM 零样本 SER 与专用模型的差距仍明确存在（MER-FG：zero-shot MLLM 落后 AffectGPT 约 10 个点）。
2. 跨语料/跨域一致性（EmoBox cross-corpus 大幅下滑 + MER-NOISE 噪声致命）——免微调稳定化方案开放。
3. 个性化 vs 泛化：端侧极少样本用户校准而不灾难性遗忘通用先验，无定论；MER2025 各赛道冠军成绩未见公开汇总 🔶。

### 6.7 检索记录（子代理实查）

命中：emotion2vec+/HF·GitHub；MER2024 (2504.17113)；MER2025 (2504.19423)；Interspeech 2025 挑战（isca naini25）；OmniVox (2503.21480)；EmoBox (2406.07162)；TASLP C²SER (2502.18186)；VoxEmo (2603.08936)；Meta-PerSER (2505.16220)；TAC 16(2) Fang；MoE 亚军 (2508.06036)；AffectGPT (2501.16566)；NTU BIIC IS2025。未命中/受限：ICASSP 2025 SER 专场独立条目、MER2025 冠军汇总页。
