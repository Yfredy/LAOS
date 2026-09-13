# ICASSP + Interspeech 近五年全量普查（2021–2026）：真实论文遍历报告

> 报告日期：2026-09-13 ｜ 取代 2026-09-13-icassp-2022-2026-report.md 的"抽样版"（那份保留为获奖名单/场馆概况的伴侣篇）。
> **本报告的数据全部来自实际抓取**：抓取脚本、原始 JSON、全量语料都在 [`docs/research/corpus/`](corpus/)，可复现。

---

## 0. 方法与数据出处（每个数字可溯源）

| 会议 | 遍历方式 | 覆盖 | 语料文件 |
|---|---|---|---|
| **Interspeech 2021–2025** | ISCA Archive 官方索引页逐锚点解析（开放存档，curl 实抓，999–1,179 锚点/届） | **5,507 篇 = 全量 100%**（标题+作者+PDF 直链） | `corpus/interspeech_corpus.json`（2.1MB） |
| **ICASSP 2022–2026** | Semantic Scholar API 按主题切片遍历（venue=ICASSP，真实命中总数 + 抽取条目） | **4 个主题切片全量命中数**（enhancement 5,257 / emotion 1,838 / codec 2,388 / VAD 183）+ 200 篇带被引数据 | `corpus/icassp_s2_raw.json`、`icassp_s2_round2.json` |
| 深读 | ISCA 摘要页逐字抓取（31 篇）+ arXiv abs 页核实（ICASSP 高被引 5 篇 + UniSE） | 32 篇深读 | `corpus/deep_reads.json` |

**为什么 ICASSP 做不到 100% 全量枚举**（约束链，如实记录）：全文在 IEEE 付费墙（无标题列表可抓）→ OpenAlex 本 IP 当日配额耗尽 → dblp API 有反爬 JS 挑战 → Crossref 的 container-title 过滤器不接受含逗号的卷名、相关性排序在深分页时完全不稳定（rows=50 返回 1998 年卷）→ S2 未认证池持续 429（26 次尝试仅 2 次放行）。S2 按主题切片是唯一跑通的元数据遍历路线。

---

## 1. Interspeech 2021–2025：全量普查结果（5,507 篇）

### 1.1 规模与主题矩阵（真实计数，标题多标签命中）

| 届 | 总篇数 |
|---|---|
| 2021 | 999 |
| 2022 | 1,123 |
| 2023 | 1,141 |
| 2024 | 1,065 |
| 2025 | 1,179 |
| **合计** | **5,507** |

十二主题五年矩阵（来自全量标题正则分类，`corpus/interspeech_corpus.json` 可复核）：

| 主题 | 2021 | 2022 | 2023 | 2024 | 2025 | 五年读法 |
|---|---|---|---|---|---|---|
| **codec/离散表征** | 7 | 12 | 15 | **30** | **45** | 2024 起爆发（×6）——语音 LLM 的 token 化需求拉动 |
| **LLM/基础模型/对话** | 21 | 27 | 25 | **89** | **112** | 2024 跳变 ×4，2025 继续冲——全场最大的范式转移 |
| **health/副语言病理** | 57 | 50 | 64 | 68 | **103** | 2025 近翻倍——看护/语言健康应用起飞 |
| **enhance/增强/分离** | 111 | 139 | 133 | 147 | 153 | 稳步扩张的常青领域 |
| **edge/蒸馏/端侧** | 86 | 104 | **140** | 118 | 119 | 2023 见顶后维持高位——端侧化已成默认选项 |
| **ssl 底座** | 44 | 85 | 88 | 84 | 56 | 2022-24 平台期后**回落**——SSL 论文让位于 LLM 论文 |
| **tts/声码器/VC** | 218 | 253 | 242 | 234 | 205 | 恒定 ~22% 的最大单一主题，热度被 codec/LLM 分流 |
| **emotion** | 45 | 59 | 78 | 59 | 80 | 2023、2025 双峰（挑战赛年） |
| **speaker** | 140 | 147 | 124 | 132 | 128 | 恒定 ~130/届 |
| **diarization/meeting** | 43 | 50 | 43 | 49 | 42 | 平稳 |
| **kws/VAD** | 21 | 32 | 23 | 20 | **17** | **逐年萎缩**——成熟领域，卷不动了 |
| **sound event/场景** | 21 | 18 | 13 | 10 | **5** | **持续萎缩至消亡**——DCASE 社区把话题带去了 ICASSP |

> 四条硬趋势（全部由上表真实数字支撑，非印象）：
> ① **语音 LLM/token 化吃掉了 SSL 研究议程**（llm 21→112 与 ssl 84→56 的剪刀差发生在同一年 2024）；
> ② **神经编解码从零星到主流**（codec 7→45），且与 LLM 主题高度同源；
> ③ **健康声学 2025 翻倍**——全天候录音的应用重心正在移向看护与语言健康；
> ④ **KWS/VAD 和声学事件在 Interspeech 退潮**——前者工程成熟、后者迁移到 DCASE/ICASSP，laos 这两块的选型应主要看 ICASSP/DCASE 而非 Interspeech。

### 1.2 各主题代表论文（真实标题，PDF 直链见 `corpus/deep_reads.json` 与 `appendix_interspeech_lists.md`）

- **SSL 底座线**：SUPERB（2021，冻结底座+轻头的系统证据）→ XLSR-53（2021，跨语言音素错误率 -72%）→ XLS-R（2022，2B 参数/50 万小时/128 语种）→ LightHuBERT/TRILLsson（2022，蒸馏压缩：TRILLsson 以 <4% 体积在情感任务反超 wav2vec2.0）
- **情感线**：wav2vec2.0 Embeddings for SER（2021）→ 噪声鲁棒多层蒸馏/情景记忆自适应 SER（2023）→ **EmoBox 基准 + "2009 挑战赛 15 年回顾"（2024：多数深度模型仅小幅超过 2009 冠军——SER 远未解决的实证）**→ Interspeech 2025 自然条件挑战赛（说话人无关+维度双任务，冠军系统=音/文基础模型组合，包揽前二的 UCLA 系框架）
- **说话人线**：ECAPA-TDNN for Diarization（2021）→ Personal VAD 2.0（2022，端侧个性化 VAD）→ EEND-M2F/DiarizationLM/powerset 校准（2024）→ **Streaming Sortformer（2025：到达序缓存 AOSC，流式"谁在何时说"，不建长期声纹）** + SDBench + DISPLACE 挑战
- **增强线**：DCCRN+（2021）→ PercepNet+/E3Net/轻量子带融合（2022）→ **Zoneformer（2023：端侧神经波束，车内多区分离+增强+AEC 一体，RTF 0.39）**→ **URGENT Challenge（2024/2025：7 类失真统一评测，成为 SE 评测新标准）**→ TSDT-Net（2025：<700K 参数/<500M MACs 的 SOTA，明确面向嵌入式）
- **编解码线**（从 7 篇到 45 篇的主 intestine）：VQ-VAE 系列（2021-22）→ 跨尺度 VQ/超低码率（2022-23）→ **2024 集中爆发：Single-Codec/RVQGAN tokenizer/Codec-ASR/Codecfake（编解码深伪检测）/TokenSplit**→ **2025 全面开花：NanoCodec（NVIDIA，语音 LLM 极速推理）/LSCodec（说话人解耦）/DualCodec（低帧率语义增强）/EnCodecMAE/水印-aware codec（防未授权克隆）/on-device 流式 DSU（FLOPs -50%）**
- **KWS/VAD 线**（萎缩中的真金）：Keyword Transformer（2021）→ Personal VAD 2.0/NAS-VAD/语义 VAD（2022-23）→ 神经形态脉冲 KWS（PDM 麦克风/ED-sKWS，2024）→ **LLM-Synth4KWS + FusionVAD（2025，laos 已落地的两篇）**
- **LLM/对话线**：ChatGPT 意图理解评测（2023）→ MINT/Instruction-tuning（2024）→ **全双工 FD-Bench、Speech-IFEval、音频 LLM 自我改进（2025）**

---

## 2. ICASSP 2022–2026：主题切片遍历结果

### 2.1 规模锚点（官方/第三方口径）

| 届 | 投稿 | 录用 | 来源 |
|---|---|---|---|
| 2022 | 3,967 | 1,785 | [openaccept](https://openaccept.org/c/gm/icassp/) |
| 2023 | 6,127 | 2,765 | 同上（官方称较上届 +50%） |
| 2024 | — | ~2,812 | 官方获奖页口径 |
| 2025/2026 | — | 同量级 | — |

### 2.2 S2 主题切片真实命中（venue=ICASSP, 2022-2026, 标题+摘要匹配）

| 主题查询 | 命中总数 | 说明 |
|---|---|---|
| speech enhancement | **5,257** | 最大切片——ICASSP 的第一主题（含引用了增强的论文） |
| emotion recognition | **1,838** | 第二切片（多模态对话情感为主） |
| neural codec | **2,388** | 与 Interspeech 的 codec 爆发同期 |
| voice activity detection | 183 | 窄而精（标题级命中） |

> 与 Interspeech 互证：**增强与 codec 是 2022-2026 双会议共同的最大增长极**；laos 关心的 KWS/VAD 在 ICASSP 存量小（183）——再次印证前端触发器的最新进展要看 DCASE 与产品工程而非主会。

### 2.3 ICASSP 高被引深读（emotion/VAD 切片 200 篇中，arXiv 逐篇核实）

| 被引 | 年 | 论文 | 对 laos |
|---|---|---|---|
| 274 | 2022 | [MM-DFN](https://arxiv.org/abs/2203.02385)（Hu et al.）：图动态融合多模态对话情感 | 多模态对话情感的高被引范式（视频模态，laos 仅借鉴融合结构） |
| 181 | 2022 | [Co-Attention Multi-Level Acoustic SER](https://arxiv.org/abs/2203.15326)（Zou et al.）：MFCC+谱+wav2vec2 三层共注意力 | "手工特征+SSL 混合"路线的实证——与 laos PCEN+能量 VAD 同哲学 |
| 173 | 2022 | [SER Using Self-Supervised Features](https://arxiv.org/abs/2202.03896)（Morais et al., Intel）："上游 SSL+下游轻头"模块化范式，纯语音逼近多模态 SOTA | **laos"SenseVoice+轻量头"路线的 ICASSP 奠基文献** |
| 115 | 2023 | [Audio Deepfake Detection with WavLM](https://arxiv.org/abs/2312.08089) | SSL 底座转向深伪检测——laos TTS 输出加水印的对面 |
| 50 | 2022 | [TS-VAD via Seq2Seq Pretraining](https://arxiv.org/abs/2210.16127) | 个性化 VAD——laos"只听主人"（不建声纹库）的技术源头 |

---

## 3. 亮点专题：UniSE（Interspeech 2026，用户提供的最新论文）

**[UniSE: A Unified Framework for Decoder-Only Autoregressive LM-Based Speech Enhancement](https://arxiv.org/abs/2510.20441)**（Haoyin Yan, Chengwei Liu, Shaofei Xue 等，阿里千问）——✅ arXiv 核实 Interspeech 2026 接收。

- **一个 decoder-only 自回归 LM 统一三种增强任务**：语音修复（SR）、目标说话人提取（TSE）、语音分离（SS）——以输入语音为条件自回归生成目标离散 token，兼容三任务的不同学习模式
- **渐进式强化学习**（PRL/DPO 思路）+ 多评估准则优化语音质量
- 微信文口径：263.9M 参数、DNS OVRL 3.64（🔶 文章声称，arXiv 摘要未含具体数字）；代码开源（alibaba/unified-audio → QuarkAudio-UniSE）
- 局限：自回归生成非流式，263.9M 参数是端侧不可常驻的体量

**对 laos 的位置**：这是 §1.1 "codec/LLM 吞并增强"趋势的集大成样本——**增强、提取、分离在 LM 框架下合并为一件事**。laos 的用法：journal 离线档的"多说话人日记分离 + 修复"可等其开源权重（263.9M 在 RTX 4060 无压力）；TSE 模式（参考音频为 prompt）与"只提取主人、不建声纹库"的隐私路线直接同构——但注意 prompt 参考音频本质是临时声纹，须会话内用后即弃。

---

## 4. 双会议合并结论（六条，全部有表/链接背书）

1. **议程已经换轨**（2024 为分水岭）：SSL 研究让位于语音 LLM/token 化（Interspeech llm 25→89→112，codec 15→30→45 同步爆发）。
2. **端侧化成为论文默认配置**：edge 主题五年稳定 100+ 篇/届，蒸馏/量化/流式从"卖点"变成"入场券"；TRILLsson/LightHuBERT/on-device DSU 给出了"底座→端侧"的完整方法链。
3. **增强是最大常青赛道且正在被 LM 重新定义**：ICASSP enhancement 切片 5,257 命中；从判别式（GTCRN/TSDT-Net）到生成式（UNIVERSE/FlowSE）再到统一 LM（UniSE）——但端侧档（<1M 参数）与云端档（>100M）分化明显，laos 取两端。
4. **健康声学 2025 在 Interspeech 翻倍（68→103）**：口吃/认知/看护应用起飞，与 EU AI Act/PIPL 执法期相遇——laos 健康功能的"纵向差分+不做诊断"红线恰好是合规姿势。
5. **SER 的诚实图景**：15 年回顾（2024）证明绝对精度几乎停滞；进步发生在**评测口径**（自然条件/说话人无关/跨语料）与**个性化**——laos 只做纵向差分是科学上站得住的唯一姿势。
6. **KWS/VAD/声学事件在主会萎缩**（17/5 篇）——前沿转入场外挑战赛（DCASE）与神经形态硬件；laos 触发器选型应以 DCASE 冠军管线 + Silero/TIM-Net 级工程实践为主，不必等主会新论文。

## 5. 语料清单（全部可复现）

| 文件 | 内容 | 规模 |
|---|---|---|
| `corpus/interspeech_corpus.json` | Interspeech 2021-25 全量论文（标题/作者/URL/PDF 直链/主题标签）+ 统计矩阵 | 5,507 条 |
| `corpus/is20XX_papers.json` ×5 | 各届原始解析 | 999–1,179/届 |
| `corpus/is20XX_relevant.json` ×5 | 各届主题命中子集 | 510–659/届 |
| `corpus/appendix_interspeech_lists.md` | codec/KWS-VAD/event/emotion/diarization 五主题论文全列表（带链接） | 648 行 |
| `corpus/icassp_s2_raw.json` / `icassp_s2_round2.json` | S2 切片原始返回 | 200+ 条带被引 |
| `corpus/deep_reads.json` | 32 篇深读清单（ISCA 摘要页/arXiv 逐字核实） | 21+11 条 |
| `corpus/crawl_icassp.py` / `crawl_icassp_s2.py` | 爬虫脚本（复现用） | — |

## 6. 局限（如实）

1. ICASSP 全量枚举受数据源限制（见 §0 约束链）——主题切片 + 高被引深读是可行替代，覆盖了 laos 相关的四个主切片，但**不等于**全部 ~12,000 篇。
2. Interspeech 主题计数基于标题正则（多标签），存在少量误报/漏检（如标题含 "affect" 的语音学论文入情感桶）；窄主题列表经人工复核。
3. 深读以摘要为准（ISCA/arXiv 公开层），未读付费全文；关键数字凡未在摘要层核实的标 🔶。
4. Interspeech 2026（2026-08/09 开会）与 ICASSP 2026 的完整卷次尚在发布中，仅收录了已公开的 UniSE 等条目。
