# 证据附录

## 1. 范围合同

### 1.1 主题与核心问题
- 主题：音频智能体（agentic audio）在端侧/边缘的可用技术栈。
- Q1：AgentOS 语境下，音频是“传感器 + 动作面”还是独立能力？已有系统把它放在哪一层？
- Q2：全天候录音的产品与学术证据，对端侧音频栈给出哪些硬约束（功耗/触发/留存）？
- Q3：多模态（音+视）在 SER/AED/AGC 三个任务里，真实增量与合规代价各是什么？
- Q4：AED 的端侧/多模态/大中小如何拆成可比较维度？每档的代表系统与硬数字是什么？
- Q5：AGC 的模型化边界在哪？经典 DSP、神经增强、多模态各自解决什么问题？

### 1.2 时间窗与读者
- 检索窗：2017-01-01 至 2026-10-18；重点 2023–2026。
- 读者：laos/nanoLAOS 的技术评审与路线评审；默认读者懂 Python 与端侧部署，不默认懂音频领域。
- 交付物：综述正文 + 证据附录 + 机器校验器；不交付 benchmark 重跑与产品选型报价。

### 1.3 纳入标准
- 同行评审论文、arXiv 预印本、官方技术报告/挑战赛榜单、可核验的开源权重仓库。
- 与六个领域之一直接相关，且至少满足一条：给出参数量/算力/延迟/功耗；给出可复现指标与条件；给出端侧部署证据；给出合规/社会接受度实证。

### 1.4 排除标准
- 纯音乐生成、纯语音识别（不涉及情感/事件/增益/常驻采集）、纯视觉、纯 NLP。
- 只有营销口径没有可核数字的产品稿；无法定位原文的二手转述（除非作为“二手”证据并标注）。
- 与端侧/常驻/治理无关的纯云端大模型榜单。

### 1.5 这篇综述不写什么
- 不对 123,271 条 venue 元数据做全量全文精读（`docs/research/papers/` 仅 147 个 PDF，索引口径 115 篇）。
- 不重跑任何 benchmark；所有数字均为原文/官方榜单口径，并附条件。
- 不做临床有效性、法律合规意见或采购建议。

### 1.6 证据基座（开工前盘点）
| 基座 | 数量 | 位置 | 用途 |
| --- | --- | --- | --- |
| SER 记录 | 46 条 | `docs/research/speech-emotion/` | §4 主证据 |
| AED 记录 | 58 条 | `docs/research/audio-events/` | §5 主证据 |
| AGC 记录 | 35 条 schema 记录（另 3 条多模态） | `docs/research/auto-gain/` | §6 主证据 |
| 全天候录音学术线 | 41 篇 | `docs/research/always-on-recording/academic-papers.md` | §3 约束 |
| AgentOS 窄分支 | 49 篇 | `docs/research/2026-10-07-agentos-governance-literature.md` | §3 分层 |
| venue 元数据 | 123,271 条 | `corpus/venue_expansion/*.jsonl` | 补检候选 |
| 论文 PDF | 147 个 PDF（索引口径 115 篇） | `docs/research/papers/` + `docs/research/papers_index.md` | 全文核验 |

## 2. 检索日志

检索执行于 2026-10-18（本地时间）。三条通道：①六组语料查询（`corpus/venue_expansion/*.jsonl`，经 `scripts/query_corpus.py`，AGC 按放宽式计合计 207 行）；②arXiv API（`export.arxiv.org/api/query`）；③既有领域表（SER/AED/AGC/全天候/AgentOS 五组，逐行取候选）。

| 检索日 | 库/通道 | 检索式 | 年份窗 | 命中 | 纳入候选 |
| --- | --- | --- | --- | --- | --- |
| 2026-10-18 | corpus/audio-speech·AED | audio event\|sound event\|acoustic event\|DCASE | 2017-2026 | 2 | 0 |
| 2026-10-18 | corpus/audio-speech·AGC | gain control\|AGC\|loudness\|dynamic range\|normaliz\|gain adjustment | 2017-2026 | 15 | 0 |
| 2026-10-18 | corpus/audio-speech·SER | emotion\|affect\|valence\|arousal | 2017-2026 | 49 | 0 |
| 2026-10-18 | corpus/spatial-privacy·always-on | always-on\|wearable\|continuous\|lifelog\|lifelogging\|recording | 2017-2026 | 5 | 2 |
| 2026-10-18 | corpus/agent-os | (topic=agent-os，无 grep) | 2017-2026 | 49 | 9 |
| 2026-10-18 | corpus/audio-speech·multimodal | multimodal\|multi-modal\|audio-visual\|audiovisual | 2017-2026 | 87 | 2 |
| 2026-10-18 | arXiv·agentOS×audio | abs:"agent operating system" AND (abs:audio OR abs:speech) | 不限（实得空集） | 0 | 0 |
| 2026-10-18 | arXiv·always-on | abs:"always-on" AND abs:audio AND abs:recording | 不限（实得 2016–2026） | 26 | 2 |
| 2026-10-18 | arXiv·SED on-device | abs:"sound event detection" AND abs:"on-device" | 不限（实得 2019–2026） | 13 | 10 |
| 2026-10-18 | arXiv·AGC | abs:"automatic gain control" AND abs:audio | 不限（实得 2026） | 1 | 0 |
| 2026-10-18 | arXiv·SER on-device | abs:"speech emotion recognition" AND abs:"on-device" | 不限（实得 2020–2026） | 20 | 9 |
| 2026-10-18 | arXiv·AV×event | abs:"audio-visual" AND abs:"sound event" | 不限（实得 2017–2026） | 27 | 17 |
| 2026-10-18 | 领域表·speech-emotion/ | (六表逐行，00–06) | 2017-2026 | 46 | 6 |
| 2026-10-18 | 领域表·audio-events/ | (六表逐行，00–07) | 2017-2026 | 58 | 17 |
| 2026-10-18 | 领域表·auto-gain/ | (六表逐行，00–07) | 2017-2026 | 38 | 12 |
| 2026-10-18 | 领域表·always-on-recording/ | (academic-papers.md 41 行 + 产品史) | 2004-2026 | 41 | 25 |
| 2026-10-18 | 领域表·agentos-governance | (49 行窄分支) | 2016-2026 | 49 | 0 |

口径说明（与「命中」列一一对应）：

- **命中**：命令实际输出条数（语料 = JSONL 行数；arXiv = `<entry>` 数；领域表 = 表内数据行数）。**纳入候选**：进入 §3 标题/摘要筛选的条数；两者不等是检索噪声，不是筛选遗漏。
- **AGC 语料式两次命中**：首跑 `automatic gain|gain control|AGC|dynamic range|loudness` 只回 1 条（语料里 AGC 工作多以 enhancement/restoration 命名），按预案放宽一次为 `gain control|AGC|loudness|dynamic range|normaliz|gain adjustment`，得 15 条。表中记放宽后的 15，首跑 1 条如实记在此处。
- **arXiv 通道状态**：六条查询全部 curl exit 0，合计 87 条 `<entry>`，无证书/网关错误，未触发降级预案。其中 `abs:"agent operating system" AND (abs:audio OR abs:speech)` 返回空集（totalResults=0）——「AgentOS × 音频」在 arXiv 摘要层尚无成型文献，该维度只能由 AgentOS 通用文献与音频侧文献两侧夹逼。
- **语料通道的零候选**：AED/AGC/SER 三条命中 2/15/49 条，但 `laos_topic` 是 venue 级粗标，命中项多为波束成形、HRTF、TTS 等相邻主题，逐条筛后 0 条进 §3——语料只到标题/摘要层，模型级证据必须回领域表。
- **领域表命中口径**：speech-emotion 46 / audio-events 58 / auto-gain 35 条 schema + 3 条多模态（合计 38）/ always-on 41（六表数据行）/ agentos-governance 49（窄分支），与 §1.6 盘点一致，非本次新增。

## 3. 筛选与排除

按 §1.3/§1.4 逐条筛：候选 C001–C111（111 条），纳入 80 条，排除 31 条。排除理由一律落到五个维度之一（端侧证据/指标条件/常驻约束/合规/多模态），不写「不相关」。

编号块（块内年份倒序；与 §4 卡片、§5 大纲、§10 参考文献逐号对齐）：

- S01–S20：AgentOS / 全天候录音 / 多模态应用侧（20 条）
- S21–S40：SER + AED 小型/中型（20 条）
- S41–S60：AED 大型 + AGC 全档（20 条）
- S61–S80：全天候 / 端侧 / 补充（20 条）

| 编号 | 文献 | 年份 | 决定 | 理由 |
| --- | --- | --- | --- | --- |
| C001 | [EcoAgent: device-cloud collaborative multi-agent framework for mobile automation](https://doi.org/10.1609/aaai.v40i35.40230) | 2026 | 纳入 S01 | 端侧证据：设备-云协同自动化，端上执行器与云端编排的分工边界 |
| C002 | [TuneAgent: agentic operating system kernel tuning with RL](https://doi.org/10.1145/3770855.3817987) | 2026 | 纳入 S02 | 常驻约束：Agent 直接改内核参数，给出 OS 级负载治理的可写面 |
| C003 | [TraceBrain: open-source framework for agentic trace management](https://doi.org/10.24963/ijcai.2026/975) | 2026 | 纳入 S03 | 合规：运行轨迹作为可审计对象，事件级留存与回放 |
| C004 | [Optimally auditing adversarial agents](https://doi.org/10.1609/aaai.v40i20.38722) | 2026 | 纳入 S04 | 合规：审计采样与预算分配，合规抽检的方法论边界 |
| C005 | [WearVox: egocentric multichannel voice assistant benchmark for wearables](https://arxiv.org/abs/2601.02391) | 2026 | 纳入 S05 | 多模态：可穿戴多通道基准，佩戴者视角的采集与干扰条件 |
| C006 | [Are women really (not) more talkative than men? A registered report](https://doi.org/10.1037/pspp0000534) | 2026 | 纳入 S06 | 常驻约束：全天候采集的日均语音量基线，直接决定留存与算力预算 |
| C007 | [Listen, see and track: spatio-temporal audio-visual sound event reasoning for omni-modal LMs](https://arxiv.org/abs/2608.09435) | 2026 | 纳入 S07 | 多模态：音视联合事件推理进 omni-modal 模型，暴露单模态天花板 |
| C008 | [DRIFT: dynamic rule-based defense with injection isolation for securing LLM agents](https://doi.org/10.52202/085713-2791) | 2025 | 纳入 S08 | 合规：规则化注入隔离，对照 laos syscall 闸门的规则面 |
| C009 | [SMART: self-aware agent for tool overuse mitigation](https://aclanthology.org/2025.findings-acl.239/) | 2025 | 纳入 S09 | 常驻约束：工具过用的预算治理，对应能力管控的拒绝面 |
| C010 | [JointAVBench: benchmark for joint audio-visual reasoning evaluation](https://arxiv.org/abs/2512.12772) | 2025 | 纳入 S10 | 多模态：音视联合推理评测，区分「看见」与「听出」的贡献 |
| C011 | [MeMic: towards social acceptability of user-only speech recording wearables](https://doi.org/10.1145/3613905.3650872) | 2024 | 纳入 S11 | 合规：只采佩戴者语音的社会可接受度实证，给旁观者可见性设计 |
| C012 | [UniAV: unified audio-visual perception for multi-task video event localization](https://arxiv.org/abs/2404.03179) | 2024 | 纳入 S12 | 多模态：统一音视感知做多任务事件定位，模态增益与代价同表 |
| C013 | [Exploring audio-visual information fusion for sound event localization in low-resource regimes](https://arxiv.org/abs/2406.15160) | 2024 | 纳入 S13 | 多模态：低资源下音视融合的真实增量，非无条件收益 |
| C014 | [Overview of the L3DAS23 challenge on audio-visual extended reality](https://arxiv.org/abs/2402.09245) | 2024 | 纳入 S14 | 多模态：XR 场景音视任务与榜单口径，采集条件贴近可穿戴 |
| C015 | [STARSS23: audio-visual dataset of spatial recordings of real scenes](https://arxiv.org/abs/2306.09126) | 2023 | 纳入 S15 | 多模态：真实场景音视空间标注，给事件-方位联合条件 |
| C016 | [Privacy controls for always-listening devices (PhD dissertation)](https://digicoll.lib.berkeley.edu/record/273841/files/EECS-2022-249.pdf) | 2022 | 纳入 S16 | 合规：常驻聆听的隐私控制设计空间，含拒绝与遗忘机制 |
| C017 | [AudioCLIP: extending CLIP to image, text and audio](https://arxiv.org/abs/2106.13043) | 2021 | 纳入 S17 | 多模态：音-图-文对齐，开放词表与跨模态检索的前提 |
| C018 | [Investigating users' preferences and expectations for always-listening voice assistants](https://doi.org/10.1145/3369807) | 2019 | 纳入 S18 | 合规：用户对常驻聆听的期望与拒绝边界（何时算越界） |
| C019 | [Are women really more talkative than men? (Science 2007)](https://repository.arizona.edu/bitstream/10150/623432/1/EAR%20CDPS%20in%20press.pdf) | 2007 | 纳入 S19 | 常驻约束：日均词量的经典量化，常驻采集存储预算的锚点 |
| C020 | [Minimal-impact audio-based personal archives](https://doi.org/10.1145/1026653.1026659) | 2004 | 纳入 S20 | 常驻约束：低开销个人音频归档的采集/留存设计 |
| C021 | [Array-aware ambisonics and HRTF encoding for binaural reproduction with wearable arrays](https://doi.org/10.1109/taslpro.2026.3671606) | 2026 | 排除 | 端侧证据缺：可穿戴阵列编码算法，无模型体积/延迟数字 |
| C022 | [Binaural signal matching with wearable arrays for near-field sources](https://doi.org/10.1109/taslpro.2026.3678167) | 2026 | 排除 | 常驻约束缺：近场波束成形，无常驻采集与留存证据 |
| C023 | [ToS: team of specialists ensemble for stereo SELD](https://arxiv.org/abs/2601.17611) | 2026 | 排除 | 指标条件不可比：榜单集成方案，无模型体积与单次延迟 |
| C024 | [SpongeBob: sync-aware harmonious audio-visual generative editing](https://arxiv.org/abs/2605.25193) | 2026 | 排除 | 多模态不支撑：生成编辑，无识别/增益轴 |
| C025 | [SyncReward: human-aligned synchronization reward for audio-visual generation](https://arxiv.org/abs/2610.16338) | 2026 | 排除 | 多模态不支撑：生成侧奖励模型，非采集侧证据 |
| C026 | [Sounding highlights: dual-pathway audio encoders for audio-visual highlight detection](https://arxiv.org/abs/2602.03891) | 2026 | 排除 | 多模态不支撑：视频高光检测，非音频事件识别 |
| C027 | [MMAG: multi-control mixed audio generation benchmark](https://arxiv.org/abs/2608.06900) | 2026 | 排除 | 多模态不支撑：混合音频生成基准，无识别或增益控制指标 |
| C028 | [MISP-Meeting: real-world dataset with multimodal cues for long-form meeting transcription](https://aclanthology.org/2025.acl-long.753/) | 2025 | 排除 | 端侧证据缺：固定阵列会议数据，无端侧延迟/功耗账 |
| C029 | [MISP-QEKS: large-scale dataset with multimodal cues for query-by-example](https://doi.org/10.1145/3746027.3758268) | 2025 | 排除 | 指标条件不可比：查询式检索数据集，与事件/情感/增益指标不同轴 |
| C030 | [Spatial and semantic embedding integration for stereo SELD](https://arxiv.org/abs/2507.04845) | 2025 | 排除 | 指标条件不可比：定位分数为主，无法与纯音频 AED 指标比较 |
| C031 | [HDA-SELD: hierarchical cross-modal distillation for low-resource SELD](https://arxiv.org/abs/2508.12334) | 2025 | 排除 | 端侧证据缺：蒸馏提分但无端侧运行时实测 |
| C032 | [DOA-aware audio-visual self-supervised learning for SELD](https://arxiv.org/abs/2410.22803) | 2024 | 排除 | 多模态不支撑：只报来向误差，无事件识别指标与端侧账 |
| C033 | [Leveraging reverberation and visual depth cues for SELD with distance estimation](https://arxiv.org/abs/2410.22271) | 2024 | 排除 | 指标条件不可比：距离/混响估计指标，端侧无部署证据 |
| C034 | [Language-guided joint audio-visual editing via one-shot adaptation](https://arxiv.org/abs/2410.07463) | 2024 | 排除 | 多模态不支撑：生成式编辑任务，不产出事件/情感判别指标 |
| C035 | [SAVGBench: benchmarking spatially aligned audio-video generation](https://arxiv.org/abs/2412.13462) | 2024 | 排除 | 多模态不支撑：生成基准，与常驻采集/治理无关 |
| C036 | [Enhancing personalized dialogue generation with contrastive latent variables](https://aclanthology.org/2023.acl-long.1/) | 2023 | 排除 | 合规冲突：人格画像与本仓库红线冲突，且无音频证据 |
| C037 | [Can you put it all together: evaluating conversational agents' ability to blend skills](https://aclanthology.org/2020.acl-main.183/) | 2020 | 排除 | 常驻约束缺：对话技能混合评测，无音频传感器面 |
| C038 | [Thunder Crystal: crowdsourcing-based content distribution platform](https://doi.org/10.1145/2964284.2973822) | 2016 | 排除 | 常驻约束缺：CDN 众包分发调度，无音频采集与端侧约束 |
| C039 | [PTS-SNN: prompt-tuned temporal shift spiking networks for efficient SER](https://arxiv.org/abs/2602.08240) | 2026 | 纳入 S21 | 端侧证据：脉冲网络换取推理能耗，给出能效侧对照 |
| C040 | [Distilled HuBERT for mobile speech emotion recognition](https://arxiv.org/abs/2512.23435) | 2025 | 纳入 S22 | 端侧证据：跨语料验证的手机端蒸馏 SER，含跨库掉点 |
| C041 | [Real-time emergency vehicle siren detection with efficient CNNs on embedded hardware](https://arxiv.org/abs/2507.01563) | 2025 | 纳入 S23 | 端侧证据：嵌入式硬件实时检测，含延迟与平台条件 |
| C042 | [DASM: detect any sound (open-vocabulary AED)](https://arxiv.org/abs/2507.16343) | 2025 | 纳入 S24 | 指标条件：开放词表 AED 的跨数据集口径，非大型档 |
| C043 | [Re-parameterization of lightweight transformer for on-device SER](https://arxiv.org/abs/2411.09339) | 2024 | 纳入 S25 | 端侧证据：重参数化换端侧延迟，含参数量与推理条件 |
| C044 | [SenseVoice (FunAudioLLM): voice understanding foundation model](https://arxiv.org/abs/2407.04051) | 2024 | 纳入 S26 | 端侧证据：234M 级、ONNX/sherpa-onnx 是手机端主路径 |
| C045 | [HiCMAE: hierarchical contrastive multimodal model for audio-visual SER](https://arxiv.org/abs/2401.05698) | 2024 | 纳入 S27 | 多模态：音视情感表征的可比增量，含模态缺失条件 |
| C046 | [emotion2vec: self-supervised pre-training for speech emotion representation](https://aclanthology.org/2024.findings-acl.931/) | 2024 | 纳入 S28 | 指标条件：自监督情感表征的跨库口径与线性探针协议 |
| C047 | [Dual knowledge distillation for efficient sound event detection](https://arxiv.org/abs/2402.02781) | 2024 | 纳入 S29 | 端侧证据：双蒸馏压缩 SED，给小型档上限 |
| C048 | [emotion2vec+ large (FunASR 导出)](https://huggingface.co/emotion2vec/emotion2vec_plus_large) | 2024 | 纳入 S30 | 端侧证据：ONNX/FunASR 可导出，需量化+蒸馏后才可能进手机 |
| C049 | [EfficientAT-mn04_as (Efficient Audio Transformer, width 0.4)](https://arxiv.org/abs/2211.04772) | 2023 | 纳入 S31 | 端侧证据：不足 1M 参数 + 蒸馏自 PaSST，小型档下界 |
| C050 | [EAT-base: efficient audio transformer](https://arxiv.org/abs/2306.04186) | 2023 | 纳入 S32 | 指标条件：高效 Transformer 的 AudioSet 口径与 MACs 条件 |
| C051 | [CED-Base: consistent ensemble distillation for audio tagging](https://arxiv.org/abs/2308.11957) | 2023 | 纳入 S33 | 指标条件：一致性蒸馏的强基线口径，作中型对照 |
| C052 | [TRILLsson: distilled universal paralinguistic representations](https://www.isca-archive.org/interspeech_2022/shor22_interspeech.html) | 2022 | 纳入 S34 | 端侧证据：蒸馏到 5M 级表征，可穿戴可用的最小档 |
| C053 | [BEATs iter3+ (audio pre-training with acoustic tokenizers)](https://arxiv.org/abs/2212.09058) | 2022 | 纳入 S35 | 指标条件：迭代蒸馏强基线的 AudioSet 口径 |
| C054 | [AST: audio spectrogram transformer](https://arxiv.org/abs/2104.01778) | 2021 | 纳入 S36 | 指标条件：ViT 路线基准锚点，含 patch 与算力条件 |
| C055 | [PaSST-S: efficient training of audio transformers with patchout](https://arxiv.org/abs/2110.05069) | 2021 | 纳入 S37 | 指标条件：patchout 效率口径，与 AST 同源可比 |
| C056 | [PANNs-CNN14 (large-scale pretrained audio neural networks)](https://arxiv.org/abs/1912.10211) | 2020 | 纳入 S38 | 指标条件：CNN14 通用基线，含 multi-adds 口径 |
| C057 | [YAMNet (AudioSet MobileNetV1 tagging)](https://github.com/tensorflow/models/tree/master/research/audioset/yamnet) | 2017 | 纳入 S39 | 端侧证据：TFLite/TFLite Micro 官方导出，小型档事实基准 |
| C058 | [openSMILE ComParE_2016 feature set + linear classifier](https://github.com/audeering/opensmile) | 2016 | 纳入 S40 | 端侧证据：非神经特征集在 MCU 直跑，零量化成本 |
| C059 | [RealDESED: real-world domestic sound event detection benchmark](https://arxiv.org/abs/2607.16736) | 2026 | 排除 | 指标条件不可比：新基准无参数量/延迟口径，暂不可横向比较 |
| C060 | [Soroll-IA: weakly labeled audio dataset for industrial port monitoring](https://arxiv.org/abs/2606.26195) | 2026 | 排除 | 端侧证据缺：工业弱标签集，无模型指标与部署条件 |
| C061 | [Smartphone audio based distress detection](https://arxiv.org/abs/2608.04176) | 2026 | 排除 | 合规冲突：危机干预用途，缺伦理审查与临床验证 |
| C062 | [EmotionAI: privacy-preserving speech-emotion-grounded conversation pipeline](https://arxiv.org/abs/2606.24941) | 2026 | 排除 | 端侧证据缺：流水线未给端侧体积/延迟，隐私只作声明 |
| C063 | [From large-scale audio tagging to real-time explainable siren detection](https://arxiv.org/abs/2506.23437) | 2025 | 排除 | 指标条件不可比：与端侧版同组工作，只保留含硬件实测的一篇 |
| C064 | [Comparison of spectrogram scaling in multi-label music genre recognition](https://arxiv.org/abs/2506.02091) | 2025 | 排除 | 指标条件不可比：音乐流派识别，非语音情感轴 |
| C065 | [Musical source separation bake-off: objective metrics vs human perception](https://arxiv.org/abs/2507.06917) | 2025 | 排除 | 指标条件不可比：音乐分离主观/客观对照，与增益控制不同轴 |
| C066 | [Empirical analysis of asynchronous federated learning on heterogeneous devices](https://arxiv.org/abs/2505.07041) | 2025 | 排除 | 端侧证据缺：联邦异步性分析，无端侧模型体积与功耗 |
| C067 | [HiSSNet: sound event detection and speaker identification via prototypical networks](https://arxiv.org/abs/2303.07538) | 2023 | 排除 | 指标条件不可比：事件+说话人混合口径，跨任务不可比 |
| C068 | [DESED-FL and URBAN-FL: federated learning datasets for SED](https://arxiv.org/abs/2102.08833) | 2021 | 排除 | 端侧证据缺：联邦数据集，端侧训练开销未给 |
| C069 | [Channel compression: rethinking information redundancy among channels in CNN](https://arxiv.org/abs/2007.01696) | 2020 | 排除 | 指标条件不可比：通道压缩的结构实验，无 AudioSet 全量指标与端侧延迟 |
| C070 | [Virufy: COVID-19 detection from cough sounds](https://arxiv.org/abs/2011.13320) | 2020 | 排除 | 合规冲突：呼吸音诊断属临床器械语境，超出本综述范围 |
| C071 | [VOICe: sound event detection dataset for generalizable domain adaptation](https://arxiv.org/abs/1911.07098) | 2019 | 排除 | 指标条件不可比：域自适应数据集，无模型算力与端侧部署 |
| C072 | [Audio Flamingo 3](https://github.com/NVIDIA/audio-flamingo) | 2025 | 纳入 S41 | 指标条件：LALM 事件级基准与幻觉率口径，非 AudioSet 榜 |
| C073 | [Kimi-Audio-7B-Instruct](https://huggingface.co/moonshotai/Kimi-Audio-7B-Instruct) | 2025 | 纳入 S42 | 指标条件：端到端音频 LLM 的判别口径，与 ASR 榜不可混 |
| C074 | [MiDashengLM-7B](https://arxiv.org/abs/2508.03983) | 2025 | 纳入 S43 | 指标条件：编码器直连 LLM 的事件判别，注意该数字是片段准确率（非定位口径） |
| C075 | [Qwen2.5-Omni-7B](https://huggingface.co/Qwen/Qwen2.5-Omni-7B) | 2025 | 纳入 S44 | 多模态：全模态 LLM 的音视融合面，含显存/延迟量级 |
| C078 | [Miipher-2 (universal speech restoration, million-hour scale)](https://arxiv.org/abs/2505.04457) | 2025 | 纳入 S45 | 指标条件：生成式复原的上限，非实时、非端侧 |
| C076 | [Qwen2-Audio-7B-Instruct](https://arxiv.org/abs/2407.10759) | 2024 | 纳入 S46 | 指标条件：7B 音频指令模型的 SER/AED 口径，云端量级 |
| C077 | [Dasheng-1.2B (deep audio-signal holistic encoder)](https://github.com/XiaoMi/dasheng) | 2024 | 纳入 S47 | 指标条件：十亿级编码器挂标签头，大型档下界 |
| C079 | [UNIVERSE++ (generative speech restoration)](https://arxiv.org/abs/2406.12194) | 2024 | 纳入 S48 | 指标条件：扩散式复原对照，增益相邻（增强）口径 |
| C080 | [AudioSR: versatile audio super-resolution at scale](https://arxiv.org/abs/2309.07314) | 2024 | 纳入 S49 | 指标条件：带宽扩展的生成式上限，与增益相邻（增强） |
| C081 | [Whisper-AT: noise-robust ASR with audio tagging head](https://github.com/yuangongnd/whisper-at) | 2023 | 纳入 S50 | 指标条件：ASR 骨干冻结后只加事件头，增量成本可算（非端侧） |
| C082 | [MossFormer2 (speech separation/enhancement, 55.7M)](https://arxiv.org/abs/2312.11825) | 2023 | 纳入 S51 | 指标条件：中型档参数量-指标对照，非实时路径 |
| C083 | [DeepFilterNet3](https://github.com/Rikorose/DeepFilterNet) | 2023 | 纳入 S52 | 端侧证据：CPU 上 0.1–0.2 实时因子，增益/降噪同栈 |
| C084 | [GTCRN (grouped temporal convolutional recurrent network)](https://github.com/Xiaobin-Rong/gtcrn) | 2023 | 纳入 S53 | 端侧证据：48K 参数级，MCU 可用的小型档下限 |
| C085 | [FRCRN (frequency recurrent CRN, DNS challenge)](https://github.com/Audio-Westlake/FRCRN) | 2022 | 纳入 S54 | 指标条件：10M 级增强的 DNS 榜单口径 |
| C086 | [LAION-CLAP: large-scale contrastive language-audio pretraining](https://arxiv.org/abs/2211.06687) | 2022 | 纳入 S55 | 多模态：音-文对齐支撑零样本事件，检索式开放词表 |
| C087 | [RNNoise (recurrent neural network noise suppression)](https://arxiv.org/abs/1709.08243) | 2017 | 纳入 S56 | 端侧证据：85K 参数定点 C，常驻降噪的功耗基准 |
| C088 | [FFmpeg loudnorm filter (EBU R128)](https://ffmpeg.org/ffmpeg-filters.html#loudnorm) | 2016 | 纳入 S57 | 指标条件：离线响度归一（EBU R128 两遍测量），给统一电平口径 |
| C089 | [WebRTC audio processing AGC2](https://webrtc.googlesource.com/src/+/main/modules/audio_processing/agc2/) | 2013 | 纳入 S58 | 端侧证据：手机/浏览器实时增益环的工业实现 |
| C090 | [Android AutomaticGainControl (audiofx API)](https://developer.android.com/reference/android/media/audiofx/AutomaticGainControl) | 2010 | 纳入 S59 | 端侧证据：系统级 AGC 效果器的可控面与不可控边界 |
| C091 | [SpeexDSP AGC (speex_preprocess)](https://github.com/xiph/speexdsp) | 2007 | 纳入 S60 | 端侧证据：定点 C 轻量增益环，MCU/DSP 可移植 |
| C092 | [Apple Watch Series 12 audio intelligence (Siri Recap)](https://www.iphoneplay.cn/2026/09/10/apple-watch-series-12-audio-intelligence-health/) | 2026 | 纳入 S61 | 合规：端侧环形缓冲 + 7 天即焚 + opt-in 的克制常开（二手口径） |
| C093 | [EgoLog: ego-centric fine-grained daily log with ubiquitous wearables](https://arxiv.org/abs/2504.02624) | 2025 | 纳入 S62 | 常驻约束：可穿戴全天日志的采集成本与标注负担 |
| C094 | [DCASE2025 Task 1 baseline (low-complexity acoustic scene classification)](https://github.com/CPJKU/dcase2025_task1_baseline) | 2025 | 纳入 S63 | 端侧证据：61K 参数 / 128 KiB 预算下的官方基线 |
| C095 | [8.62 µW end-to-end spoken-language-understanding SoC](https://doi.org/10.1109/ISSCC49661.2025.10904788) | 2025 | 纳入 S64 | 端侧证据：微瓦级端到端语音理解，常驻功耗的物理下界 |
| C096 | [Streaming Sortformer: speaker cache-based online diarization](https://arxiv.org/abs/2507.18446) | 2025 | 纳入 S65 | 常驻约束：流式说话人日志的在线内存与延迟面 |
| C097 | [EgoADL: multimodal daily-life logging in free-living environments](https://doi.org/10.1145/3643553) | 2024 | 纳入 S66 | 常驻约束：自由生活多模态日志的真实采集负担与脱敏成本 |
| C098 | [0.4 V 988 nW time-domain audio feature extraction for keyword spotting](https://doi.org/10.1109/ISSCC49657.2024.10454389) | 2024 | 纳入 S67 | 端侧证据：纳瓦级特征前端，唤醒链路的最省电一环 |
| C099 | [TinyChirp: bird song recognition with TinyML on low-power wireless sensors](https://arxiv.org/abs/2407.21453) | 2024 | 纳入 S68 | 端侧证据：TinyML 节点长期野外部署，含功耗与回传条件 |
| C100 | [Self-learning for personalized keyword spotting on ultra-low-power audio sensors](https://arxiv.org/abs/2408.12481) | 2024 | 纳入 S69 | 端侧证据：微瓦级传感器上的自学习唤醒词，含片上预算 |
| C101 | [Rewind / Limitless pendant (cloud always-on recorder)](https://limitless.ai/) | 2024 | 纳入 S70 | 合规：云常开路线停售停服的信任代价（二手口径） |
| C102 | [Ego-Exo4D: first- and third-person video understanding](https://arxiv.org/abs/2311.18259) | 2023 | 纳入 S71 | 多模态：第一/第三人称同步采集，标注成本与对齐条件 |
| C103 | [47 nW voice activity detector with short-time CNN features](https://doi.org/10.1109/JSSC.2023.3302791) | 2023 | 纳入 S72 | 端侧证据：纳瓦级 VAD 芯片，常驻触发的能耗下限 |
| C104 | [Ego4D: around the world in 3,000 hours of egocentric video](https://arxiv.org/abs/2110.07058) | 2022 | 纳入 S73 | 常驻约束：三千小时级第一视角语料的采集规模与合规流程 |
| C105 | [AAD-KWS: sub-µW keyword spotting chip with acoustic activity detection](https://ieeexplore.ieee.org/document/9888232) | 2022 | 纳入 S74 | 端侧证据：亚微瓦唤醒 + 活动检测联动，省掉常态推理 |
| C106 | [510 nW wake-up keyword-spotting chip (serial-FFT MFCC)](https://doi.org/10.1109/JSSC.2020.3029097) | 2021 | 纳入 S75 | 端侧证据：唤醒芯片的纳瓦级功耗实测条件 |
| C107 | [Silero VAD](https://github.com/snakers4/silero-vad) | 2021 | 纳入 S76 | 端侧证据：ONNX 可达的轻量 VAD，常驻门控的事实标准 |
| C108 | [Sound event detection with binary neural networks on power-constrained IoT](https://arxiv.org/abs/2101.04446) | 2021 | 纳入 S77 | 端侧证据：二值网络在紧功耗 IoT 上做 SED，含片上预算 |
| C109 | [LeakyPick: IoT audio spy detector](https://arxiv.org/abs/2007.00500) | 2020 | 纳入 S78 | 合规：常驻麦克风的窃听检测，对抗面证据 |
| C110 | [FSD50K: open dataset of human-labeled sound events](https://arxiv.org/abs/2010.00475) | 2020 | 纳入 S79 | 指标条件：开放标注事件集的评测口径与许可条件 |
| C111 | [Self-sustaining micro-watt programmable smart audio sensor for always-on](https://ieeexplore.ieee.org/document/8752147) | 2019 | 纳入 S80 | 端侧证据：自供能微瓦常驻音频传感，能量预算下界 |

读法与边界：

- 「决定」列的 `纳入 Sxx` 是后续唯一可引用编号；排除行不占号，C 号只用于本表定位。
- C001–C111 为固定候选号，跟着论文走、不跟着行号走：本次年份修正使块内重排后，C078（Miipher-2）在表内升到 C076 之前，块内 C 序允许局部非单调。
- 「年份」列口径：正式发表年（会议/期刊卷期年）；无正式发表的预印本/仓库/文档取首次公开可用年。个别条目比 arXiv 首次提交年晚一年（EfficientAT 2022→2023、PANNs 2019→2020、Ego4D 2021→2022、AudioSR 2023→2024 的正式版年），是本口径的正常结果。
- 文献列一律给出可解析 https 出处（arXiv / DOI / 官方仓库 / 官方文档 / 官方榜单）；二手来源在理由列标「二手口径」。
- 时间窗按 §1.2 执行（2017-01-01 至 2026-10-18），另有 7 条例外（见 §7 [U01]）：日均词量（2007）、个人音频归档（2004）、openSMILE ComParE_2016 特征集（2016）、FFmpeg loudnorm（2016）、WebRTC AGC（2013）、Android audiofx AGC（2010）、SpeexDSP AGC（2007）。它们是经典 DSP 基线与端侧事实标准，给出的量级/接口至今无替代，直接决定常驻采集的存储预算与增益控制基线。
- 工具/文档类条目（FFmpeg loudnorm = S57、WebRTC AGC = S58、Android audiofx = S59、SpeexDSP = S60、Silero VAD = S76）无正式论文年份，年份取「首次公开可用」的近似值：FFmpeg loudnorm 2016、WebRTC AGC 模块 2013、Android audiofx 2010、SpeexDSP 2007、Silero VAD 2021。这些值可能比对应 GitHub/文档页的首个可见提交偏早或偏晚，属口径近似，§10 定稿时逐条回官方 changelog 复核。
- 排除集中在四类：SELD/DOA 定位（指标与 AED 不可比）、音视生成（非判别任务）、音乐与分离（不同轴）、临床与健康（合规超出范围）。

## 4. 单篇卡片

编号与 §3 的 `纳入 Sxx` 一一对应，不重排、不增删。六字段固定：问题 / 方法 / 数据 / 指标与条件 / 局限 / 对话。数字一律带数据集·指标·硬件或延迟条件；来源未给数字写 `未给出（口径）`；二手条目标 `二手口径`；`局限` 兼收作者自述与本文核对发现，§10 的「局限」列从此字段抄录。

### [S01] EcoAgent: device-cloud collaborative multi-agent framework for mobile automation
- 问题：端云协同的手机自动化里，哪些判断必须留在端侧、云端只做编排。
- 方法：设备-云协同多 agent 框架：端上执行器 + 云端编排，把"验证所需截图"留在端侧。
- 数据：未给出（AgentOS 窄分支表未列任务规模与设备型号，仅记手机自动化场景）。
- 指标与条件：未给出（对照表无量化指标；可引用的是"验证截图不上云"这一隐私分工结论，不是性能数字）。
- 局限：只有架构与隐私分工的定性结论，无端侧延迟/功耗/成功率数字；"截图留端"是设计声明而非实测合规证据；且属手机 GUI 自动化域，不含音频链路。
- 对话：与 S03 构成"端侧执行→轨迹可审计"的接力；与 S16/S18 的同意边界对照，说明"数据留在端侧"不等于"用户知情"。

### [S02] TuneAgent: agentic operating system kernel tuning with RL
- 问题：能否用强化学习让 Agent 直接调优操作系统内核参数，替代人工调参。
- 方法：agentic kernel tuning：Agent 在内核参数空间做 RL 搜索与试跑。
- 数据：未给出（仅标题条目，语料无摘要，未取正文）。
- 指标与条件：未给出（仅标题口径；未读到吞吐、延迟或内核版本的评测条件）。
- 局限：仅标题级证据，基线内核版本与负载不可核验；"改内核"与 laos 用户态薄内核路线正交，能力不可移植；无回滚/失败代价讨论。
- 对话：与 S01 的端云分工对照——一个把 Agent 放端侧执行，一个把 Agent 放进内核调参面；与 S09 的"预算治理"构成能力→代价的两端。

### [S03] TraceBrain: open-source framework for agentic trace management
- 问题：Agent 运行轨迹如何从被动日志升格为可治理、可回放的资产。
- 方法：开源 agentic trace 管理框架，框架无关 OTLP delta schema，把 trace 作为治理与适配的输入。
- 数据：未给出（AgentOS 对照表未列 trace 条数、schema 字段数与接入框架数）。
- 指标与条件：未给出（无量化指标；可引用的是"OTLP delta schema + 开源框架"这一结构事实）。
- 局限：只解决记录与回放，不含留存期限、脱敏与访问控制；粒度到事件级，音频这类连续媒体的采样率与即焚策略未涉及。
- 对话：与 S04 的审计采样构成"全量 trace → 选择性审计"的方法→代价；与 S16 的"自动删除期待"构成结论→反例（可审计不等于可长期保存）。

### [S04] Optimally auditing adversarial agents
- 问题：面对对抗性 Agent，审计资源有限时"审谁、何时审、如何罚"如何最优分配。
- 方法：机制设计：委托方先承诺审计策略，代理方再据此选均衡。
- 数据：未给出（AgentOS 对照表未列实验规模与对抗策略集合）。
- 指标与条件：未给出（无量化指标；结论为"审计策略化是最优机制设计问题"）。
- 局限：理论机制，未给真实 Agent 负载下的抽样成本与漏审率；假设代理方理性，对 prompt 注入这类外部操纵不覆盖；惩罚函数未落地。
- 对话：与 S03 的全量 trace 构成方法→代价；与 S08 的规则化防御互补——一个管事后查，一个管事前挡。

### [S05] WearVox: egocentric multichannel voice assistant benchmark for wearables
- 问题：可穿戴（AI 眼镜）第一视角多通道语音助手在真实噪声与侧谈下到底有多难。
- 方法：基准构建：AI 眼镜多麦克风采集，5 类任务（搜索问答、闭卷问答、侧谈拒识、工具调用、语音翻译），每条附位置/距离/环境元数据。
- 数据：3,842 段多通道第一视角录音；63% 室外 / 31% 室内；58% 噪声 / 42% 安静；13 类噪声；含佩戴者、对话者、旁观者三类说话人角色。
- 指标与条件：实时 SLLM 准确率 29%–59%（WearVox 五任务，摘要口径；室外噪声段显著下降）；多通道相对单通道提升鲁棒性与设备指向语音的区分（案例研究，未给统一数字）。
- 局限：只评语音助手任务准确率，不含功耗/延迟账；数据来自单一厂商眼镜，佩戴姿态与阵列几何不外推；中文场景未覆盖。
- 对话：与 S07/S10 构成"单模态基准→多模态基准"的递进；与 S61 的端侧常开产品对照：基准里的侧谈拒识正是旁观者隐私的工程面。

### [S06] Are women really (not) more talkative than men? A registered report
- 问题：人一天到底说多少话，性别差异在大样本下是否成立。
- 方法：注册报告；EAR（Electronically Activated Recorder）环境录音，22 个样本组合并分析。
- 数据：2,197 名参与者、631,030 段环境录音；年龄跨度 10–94；多国样本。
- 指标与条件：男性 11,950 词/天、女性 13,349 词/天（JPSP 卷期口径，EAR 全天断续录音）；个体跨度 100→120,000 词/天；25–64 岁组性别差 3,275 词/天（d=0.32）。
- 局限：词量是 ASR 负载的代理量，不等于有效语音时长；个体差异跨三个数量级，均值不能用于容量规划；EAR 断续采样会低估连续语音。
- 对话：与 S19（2007 原始研究）构成"经典值→大样本修正"（16,000 vs 12,000–13,000 词/天）；与 S20 的归档设计、S73 的语料规模共同锚定常驻采集量级。

### [S07] Listen, see and track: spatio-temporal audio-visual sound event reasoning for omni-modal LMs
- 问题：全模态 LM 能否把"听出事件"与"看见事件"在时空上对齐，单模态天花板在哪。
- 方法：时空音视事件推理任务 + ST-OmniQA 数据 + ST-Omni-R1 模型（摘要口径）。
- 数据：ST-OmniQA：40K 视频、400K 问答对（摘要口径；视频来源与许可未在摘要说明）。
- 指标与条件：平均语义准确率 77.83%（ST-Omni-R1，ST-OmniQA）；最佳对比基线 37.28%（同基准，摘要口径）。
- 局限：增益集中在"有视频"的条件，纯音频链路拿不到；语义准确率不等于事件定位精度；40K 视频的采集条件未披露。
- 对话：与 S10（JointAVBench 65.3%）构成同题不同基准的对照；与 S13 的"低资源下音视融合增量有限"构成能力→失效。

### [S08] DRIFT: dynamic rule-based defense with injection isolation for securing LLM agents
- 问题：如何用规则化注入隔离守住 LLM Agent 的提示注入面。
- 方法：动态规则防御 + 注入隔离（injection isolation），把不可信内容与执行上下文隔开。
- 数据：未给出（AgentOS 对照表未列攻击样本集与注入类型）。
- 指标与条件：未给出（无量化指标；可引用的是"规则化注入隔离"这一机制形态）。
- 局限：规则面需持续维护，规则冲突与绕过率无公开数字；只隔离"话里被塞了什么"，不解决工具越权（那属闸门层）；仅标题级细节。
- 对话：与 S04 的审计机制互补（事前隔离 vs 事后审计）；与 S01 的端云分工构成"注入面在云端编排时更大"的反例压力。

### [S09] SMART: self-aware agent for tool overuse mitigation
- 问题：Agent 的工具过用（tool overuse）能否靠元认知自省压下去。
- 方法：元认知自省：能用参数知识就不调工具，以减少无效调用。
- 数据：未给出（AgentOS 对照表未列工具调用日志规模与任务集）。
- 指标与条件：未给出（无量化指标；结论为"自觉路线可压 tool overuse"）。
- 局限：依赖 Agent 自觉，无强制力；未给误拒率（该调而不调）；与内核配额路线互斥，不能作为治理保证。
- 对话：与 S02 的"Agent 改内核"同属把权力交给 Agent 的一侧；与 S03/S04 的外部记账构成方法→代价对照。

### [S10] JointAVBench: benchmark for joint audio-visual reasoning evaluation
- 问题：音视联合推理的评测如何区分"看见"与"听出"各自的贡献。
- 方法：联合音视推理基准（任务与指标设计见原文）。
- 数据：未给出（摘要未列样本量、类别数与数据来源）。
- 指标与条件：平均准确率 65.3%（JointAVBench，摘要口径；未注明被测模型集合与划分）。
- 局限：只给聚合准确率，缺分模态消融，无法据此判断音频单独可做到多少；摘要未说明数据来源与许可。
- 对话：与 S07（ST-OmniQA 77.83%）构成同题基准间不可直接横比的反例；与 S12 的统一音视感知互为评测与方法两面。

### [S11] MeMic: towards social acceptability of user-only speech recording wearables
- 问题："只录佩戴者自己"能否提升持续录音的社会接受度。
- 方法：self-VAD 可穿戴（加速度计感知自己发声才开麦）+ 可见指示灯；实验室对照 + 在线问卷。
- 数据：实验室 N=12；在线 N=168；形态因素含吊坠、胸针等。
- 指标与条件：检测错误率 0.09±0.03（实验室 N=12，self-VAD）；"自录"相对"持续录音"显著降低社交顾虑与隐私担忧（在线 N=168）；吊坠项链最受欢迎（同调查）。
- 局限：实验室仅 12 人，错误率置信区间宽；在线问卷测态度而非长期行为；未测"只录自己"对第三方语音的漏检代价。
- 对话：与 S18（N=178 情境化同意）构成同一结论的两份实证；与 S61 的"无声 Recap"构成反例——可见指示做了才有效。

### [S12] UniAV: unified audio-visual perception for multi-task video event localization
- 问题：能否用统一音视感知同时做多任务视频事件定位，而不是一任务一模型。
- 方法：统一音视感知框架，多任务事件定位（分类 + 时序定位）。
- 数据：ActivityNet 1.3、DESED、UnAV-100（摘要口径）。
- 指标与条件：未给出（摘要口径；摘要未列 mAP/F1 数值）。
- 局限：多任务统一常以单任务精度为代价，摘要未给逐任务掉点；数据以英文视频为主，纯音频子集不适用；需摄像头。
- 对话：与 S10 的基准评测互为"方法→评测"两面；与 S13 的低资源融合共同说明音视增量有条件。

### [S13] Exploring audio-visual information fusion for sound event localization in low-resource regimes
- 问题：低资源条件下音视融合对声事件定位有多少真实增量。
- 方法：音视信息融合用于 SELD（低资源设定）。
- 数据：DCASE 2023 挑战赛数据集（摘要口径）。
- 指标与条件：未给出（摘要口径；摘要仅称 SELD 性能"显著提升"，未给定位误差数值）。
- 局限：SELD 指标（定位误差）与 AED 分类指标不同轴，不能折算成事件识别增益；未给"数据量-增益"曲线；需视频。
- 对话：与 S12/S14 构成"融合方法→榜单口径"链条；与 S07 的 omni-modal 结论对照：定位增益不等于分类增益。

### [S14] Overview of the L3DAS23 challenge on audio-visual extended reality
- 问题：XR 场景下的音视任务如何定义，榜单口径如何对齐。
- 方法：挑战赛综述：任务设定 + 数据集 + 榜单。
- 数据：未给出（摘要口径；摘要未列小时数、通道数与场景数）。
- 指标与条件：未给出（摘要口径；榜单分数未在摘要列出）。
- 局限：挑战赛口径随年份变动，跨届不可比；XR 采集几何与可穿戴不同，迁移需重标定；任务偏定位。
- 对话：与 S15（STARSS23 数据集）构成"任务→数据"配对；与 S13 共同支撑"音视增益集中在定位"。

### [S15] STARSS23: audio-visual dataset of spatial recordings of real scenes
- 问题：真实场景的音视空间录音如何标注，才能同时评事件与方位。
- 方法：数据集构建：真实场景音视空间录音 + 事件/方位标注。
- 数据：未给出（摘要口径；摘要未列时长、通道数与类别数）。
- 指标与条件：未给出（摘要口径；无基线分数）。
- 局限：标注以方位为主，事件类别覆盖有限；与纯音频 AED 的 527 类词表不对齐，不能直接并入；需视频与阵列。
- 对话：与 S14 的挑战赛口径配对；与 S79（FSD50K）构成"空间标注 vs 类别标注"的两种评测面。

### [S16] Privacy controls for always-listening devices (PhD dissertation)
- 问题：常驻聆听设备的隐私许可系统应如何设计（用户中心视角）。
- 方法：浏览器扩展把用户自己真实的助手录音嵌入问卷；问卷 + 用户研究 + 原型评测。
- 数据：未给出（领域表未列样本量）；被试使用自己的真实录音，而非实验室语料。
- 指标与条件：近一半参与者不知道交互被永久存储；对超过一半的录音认为"永久存储不可接受"；多数支持自动删除（UCB EECS-2022-249，问卷口径，N 未列）。
- 局限：样本量与地域未量化，结论是态度分布而非行为；"自动删除"未做期限参数扫描；未覆盖音频之外的传感模态。
- 对话：与 S18 的情境化同意构成"控制权→同意粒度"两级；与 S61 的 7 天即焚、S70 的停服构成产品侧正反例。

### [S17] AudioCLIP: extending CLIP to image, text and audio
- 问题：把 CLIP 扩到音频后，零样本环境声分类离有监督有多远。
- 方法：ESResNeXt 音频头接入 CLIP，AudioSet 训练；音-图-文联合嵌入。
- 数据：AudioSet（训练）；ESC-50、UrbanSound8K（评测）。
- 指标与条件：ESC-50 97.15%（微调）/ 69.40%（零样本）；UrbanSound8K 90.07% / 68.78%（零样本）（AudioCLIP，ICASSP 2022）。
- 局限：零样本与微调差约 28 个点；开放词表依赖文本编码器常驻，端侧成本未给；类别名敏感，中文标签需另做对齐。
- 对话：与 S55（LAION-CLAP 零样本 PSDS1 22.8）构成"分类零样本→检测零样本"的失效链；与 S79 的开放标注集互为数据面。

### [S18] Investigating users' preferences and expectations for always-listening voice assistants
- 问题：用户对常驻聆听助手的期待与数据共享意愿由什么决定。
- 方法：在线问卷（N=178），围绕下一代常驻助手的使用场景与共享条件。
- 数据：N=178 在线问卷；参与者多为既有语音助手用户。
- 指标与条件：N=178；同意共享与"内容不敏感 + 感知有益 + 已拥有独立助手"正相关（IMWUT 2019，问卷口径）。
- 局限：态度自报而非长期行为；样本以英语地区为主；未测"无声常开"这一形态（当时产品尚无）。
- 对话：与 S16 构成"控制权→情境化同意"的实证对；与 S11 的 self-VAD 设计互为"同意粒度→硬件约束"。

### [S19] Are women really more talkative than men? (Science 2007)
- 问题：男女说话量是否真的不同（EAR 方法学奠基）。
- 方法：EAR 环境录音：每 12.5 分钟自动录 30 秒，清醒时段全程佩戴约 17 h/天。
- 数据：396 名大学生；研究跨度 1998–2004。
- 指标与条件：男女均约 16,000 词/天；最健谈 47,016 vs 最沉默 695 词/天（跨度 46,000）；性别差 546 词（Science 2007，EAR 口径）。
- 局限：采样密度低（约 5–6 次/小时），短时窗外推全天词量有系统误差；样本为大学生，不外推到老年与多语种。
- 对话：与 S06（N=2,197 复现）构成"经典值→大样本修正"；与 S20 的归档设计共同给出存储预算锚点。

### [S20] Minimal-impact audio-based personal archives
- 问题：连续个人音频档案能否以最小侵扰采集与组织。
- 方法：长时间连续佩戴录音 + 无监督分割/聚类，与人工资境标签比对。
- 数据：未给出（领域表未列时长与人数）；连续佩戴采集。
- 指标与条件：与人工标注的环境/情境标签达成"good agreement"（CARPE 2004，原文未给具体数值）。
- 局限：只有定性一致性，无准确率/召回；2004 年硬件与今日端侧不可比；未涉及留存期限与旁观者同意。
- 对话：与 S19/S06 的采集量级、S73 的语料规模构成"个人档案→大规模语料"的尺度链；与 S16 的即焚诉求构成结论→反例（档案价值 vs 删除期待）。

### [S21] PTS-SNN: prompt-tuned temporal shift spiking networks for efficient SER
- 问题：端侧语音情感识别要压到微瓦—毫瓦级能耗，稠密网络做不到，脉冲网络是否可行。
- 方法：prompt 调优 + temporal shift 的脉冲神经网络（SNN），用事件稀疏性换推理能耗。
- 数据：IEMOCAP（摘要口径，未给说话人划分与折数）。
- 指标与条件：IEMOCAP 准确率 73.34%、参数量 1.19M（摘要口径）；单样本 0.35 mJ 为摘要给出的能耗量级，未注明是仿真估算还是芯片实测，不能当作端侧实测值。
- 局限：能效数字缺硬件平台与测量方法，SNN 的收益高度依赖事件稀疏度与时间步长；只在 IEMOCAP 单库验证，跨库与噪声条件未给；脉冲编码对长时窗（>数秒）的情绪累积在结构上不友好。
- 对话：与 S22 的"蒸馏 + INT8"构成两条端侧降本路线（改计算范式 vs 改数值精度）；与 S30 的"大权重导出"对照，说明端侧约束首先淘汰的是参数量而非精度。

### [S22] Distilled HuBERT for mobile speech emotion recognition
- 问题：HuBERT 类自监督表征太重，能否蒸馏到手机可跑的规模而不丢失情感判别力。
- 方法：以 HuBERT 为教师做知识蒸馏，学生模型按移动端预算裁剪，并给 INT8 量化路径。
- 数据：IEMOCAP（LOSO 说话人独立划分）+ RAVDESS 跨库测试。
- 指标与条件：IEMOCAP LOSO UAR 61.4（INT8 量化后）、参数量 23.49M、权重 23 MB；RAVDESS 上 46.64，跨库掉点 −14.8。
- 局限：跨库掉 14.8 个点，说明表演语料上学到的韵律线索不能直接迁到真实场景；23.49M 仍在"小型档"上沿（<30M），但手机常驻还需与 VAD/AGC 共享预算；只报 UAR，未给 4 类混淆矩阵， neutrality 与低唤醒类的混淆不可见。
- 对话：与 S34 的 TRILLsson 同属"蒸馏到 5–25M"的最小档，但 S34 是通用副语言表征、S22 是情感专用学生；与 S28 的 emotion2vec 构成"专用预训练 vs 通用蒸馏"的精度—体积对照。

### [S23] Real-time emergency vehicle siren detection with efficient CNNs on embedded hardware
- 问题：救护车/警笛这类安全关键声音，能否在嵌入式硬件上实时检出而不上云。
- 方法：高效 CNN 做二类（警笛/非警笛）检测，按嵌入式平台约束裁剪，报告实时推理路径。
- 数据：未给出（摘要口径：未列语料名、小时数与正负样本配比）。
- 指标与条件：未给出（摘要口径；延迟与目标平台在正文表格，本次未读到具体数值，故不引用）。
- 局限：二类闭集任务，正类单一，遇到多源混响与近场音乐时误报率未知；"实时"缺平台主频/帧长说明；无跨城市录音的泛化证据，安全关键场景下漏检代价未被量化。
- 对话：与 S24 的开放词表 AED 构成"窄闭集高可靠 vs 宽开放词表"的两端；专用二类模型是否在单一安全事件上优于 S39 的 YAMNet（521 类通用），待同条件对比后可判定——本卡数据与指标均未给出，不能先下"仍占优"结论。

### [S24] DASM: detect any sound (open-vocabulary AED)
- 问题：闭集 AED 的类别表写死在训练集里，如何按文本查询检出任意目标声音。
- 方法：把音频检测拆成"文本—音频对齐 + 检测头"，用 CLAP 类双塔做开放词表查询，再在目标域微调。
- 数据：DESED（合成强标注训练 + 真实弱标注/无标注），零样本对照用 CLAP / MGA-CLAP。
- 指标与条件：DESED PSDS1 42.2（vs CRNN 基线 36.4，+5.8）；同域微调后 58.8；零样本 CLAP 22.8、MGA-CLAP 24.6（PSDS1，同一评测脚本）。
- 局限：开放词表的零样本水平（22.8）仍远低于全监督（58.8），"任意声音"目前只在少数常见类上可用；DESED 的合成数据与真实录音存在域隙；参数量与推理成本高于闭集小模型，端侧部署需另行压缩。
- 对话：与 S55 的 LAION-CLAP 是同一对齐范式的上游；与 S23 的闭集 CNN 构成"开放词表换覆盖率、闭集换精度"的取舍；为 S41–S43 的 LALM 事件问答提供"可查询但不可定位"的中间形态。

### [S25] Re-parameterization of lightweight transformer for on-device SER
- 问题：轻量 Transformer 的训练期多分支结构在推理期太慢，能否重参数化合并为单路。
- 方法：训练时用多分支（含卷积/注意力并行）提升表征，推理前把分支折叠进单一卷积/线性算子。
- 数据：未给出（摘要口径：未列语料名与规模）。
- 指标与条件：未给出（摘要口径：正文给参数量与端侧延迟，本次未读到具体数值，故不引用）。
- 局限：重参数化只降推理开销，不降参数量与内存占用；折叠后失去训练期的多尺度感受野，长时窗情绪线索可能受损；缺同一硬件上"折叠前/后"的成对延迟测量。
- 对话：与 S21 的 SNN、S22 的量化并列，是端侧降本的第三条路（改图结构）；与 S32/S33 的高效 Transformer 对照，说明"高效"在论文里常指训练成本而非推理延迟。

### [S26] SenseVoice (FunAudioLLM): voice understanding foundation model
- 问题：一个模型同时做转写、语种识别、情感与音频事件，是否比"专用小模型拼接"更划算。
- 方法：SAN-M encoder-only + CTC 的多任务语音理解模型，情感/事件作为附加分类头，随转写一起输出。
- 数据：40 万小时以上多语语音（含中文）；情感评测用 CASIA、MER2023、IEMOCAP 零微调。
- 指标与条件：参数量 234M；零微调 WA：CASIA 70、MER2023 68、IEMOCAP 70；官方称 10 秒音频推理 70 ms，同参数量级下比 Whisper 快 5×、15×（官方口径，未标硬件）；ONNX INT8 ≈228 MB、GGUF Q8_0 ≈254 MB。
- 局限：情感头是 7 类粗粒度，与 IEMOCAP 4 类不齐，跨表比较需重映射；234M 对 MCU 不友好，手机常驻要与 VAD 抢内存；训练数据未公开、不可复现，中文强项之外的语种情感精度未系统报告。
- 对话：与 S28 的 emotion2vec（专用情感表征）构成"一体多任务 vs 单任务专精"；与 S22 的 23 MB 学生对照，说明 228 MB 的 INT8 权重只能进应用处理器、进不了常驻传感前端；为 S42/S46 的 LALM 提供"轻量前端"位置。

### [S27] HiCMAE: hierarchical contrastive multimodal model for audio-visual SER
- 问题：音视双模态情感识别里，视觉到底带来多少可核验的增量，模态缺失时还剩多少。
- 方法：层级对比学习（掩码重建 + 跨模态对比）在 VoxCeleb2 无标注音视频上预训练，MHCA 跨模态融合后接线性情感头。
- 数据：VoxCeleb2（无标注预训练）、IEMOCAP（4/6 类情感，线性探针）。
- 指标与条件：T/S/B 三档总参数 20/46/81M（仅音频分支 8/18/32M），IEMOCAP UAR 66.85/67.46/68.21、WAR 62.70/64.06/65.23。
- 局限：必须成对音视频，纯音频链路无法直接使用；只在 IEMOCAP 一个库上验证 4/6 类；表中指标是 HiCMAE 论文按其自身协议复现的（二手实测），与各家原报数不可直接横比；模态缺失（遮挡、离开画面）下的退化曲线未给。
- 对话：与 S12/S13 的音视融合条目同轴，但落在 SER 而非 SELD；与 S28 的单模态 emotion2vec 对照，量化"加视觉"的净增益；为 S05 的穿戴多通道采集提示"视频通道是否值得常开"的成本问题。

### [S28] emotion2vec: self-supervised pre-training for speech emotion representation
- 问题：通用语音自监督表征（wav2vec/HuBERT）对情感并不最优，能否做情感专用预训练。
- 方法：在语音上做自监督预训练（掩码 + 话语级对比），产出 768 维话语/帧级表征，下游线性头或少样本微调。
- 数据：LibriSpeech-960 + Emo-262（纯英文，合计 262 小时情感相关无标注语音）；评测 IEMOCAP、MER2024 等。
- 指标与条件：base 参数量 93.79M；IEMOCAP WA 71.79（线性探针协议）；中文 MER2024 单模态音频 WAF 56.08，同表 HuBERT-base 69.26。
- 局限：预训练语料是纯英文，中文上明显落后通用 HuBERT（56.08 vs 69.26），不能用"情感专用"直接推中文；9 类标签体系与 IEMOCAP 4 类需重映射，跨表数字不可直接比；线性探针成绩不等于端到端微调成绩。
- 对话：与 S30 的 emotion2vec+ large 是同一路线的放大版；与 S26 的 SenseVoice 构成"表征专用 vs 任务一体"；其"中文失效"是 S26 被选为中文主路径的直接理由。

### [S29] Dual knowledge distillation for efficient sound event detection
- 问题：SED 要同时出类别与起止时间，蒸馏时"帧级定位"和" clip 级分类"两个目标如何一起传给学生。
- 方法：双路蒸馏——教师的事件级/帧级输出与学生对齐，同时约束分类与定位，压缩学生规模。
- 数据：DESED（合成强标注 + 真实弱标注/无标注，DCASE Task 4 口径）。
- 指标与条件：未给出（摘要口径：只给"参数量降至约三分之一"的相对结论，未给绝对 PSDS1/PSDS2 数值，故不引用）。
- 局限：只有相对压缩比、没有绝对定位分数，无法判断"三分之一参数"换来多少 PSDS 损失；DESED 合成域与真实家庭录音仍有域隙；双蒸馏的额外教师前向只在训练期，推理收益需与基线同表核对。
- 对话：与 S24 的 DASM 同为"压缩/迁移"路线，但 S29 保定位、S24 换开放词表；与 S51/S52 的分离/降噪小模型并列，说明 SED 的"小"目前仍停在数百万参数级。

### [S30] emotion2vec+ large (FunASR 导出)
- 问题：emotion2vec 放大到 large 后精度与体积如何权衡，能否经 ONNX 进端侧。
- 方法：在 emotion2vec 上追加 42,526 小时伪标注情感数据微调，FunASR 导出 ONNX，输出 9 类情感与 768 维帧级表征。
- 数据：emotion2vec 预训练语料 + 42,526 小时伪标注情感数据；评测 IEMOCAP。
- 指标与条件：官方标称 ~300M，checkpoint 体积反推约 164M（config 为 depth 8 / embed_dim 1024，与 164M 吻合）；IEMOCAP 63.8（原文未标指标名，仅同表横向可比）；ONNX 权重 648,972,628 B；只导出帧级特征，话语级需自行池化。
- 局限：官方"~300M"与实测 164M 冲突，引用时必须两口径并列；63.8 低于 base 的 71.79，是评测协议不同（非同一线性探针）所致，不能读成"放大变差"；按 300M 级看待时手机端必须量化+蒸馏，本轮未读到手机实测延迟，不能写"手机端可跑"。
- 对话：与 S28 同一路线的大小两端；与 S26 的 228 MB INT8 对照，说明"情感专用大权重"在体积上并不比多任务模型省；其帧级导出为 S45 类修复/增强链路的表征复用留了口子。

### [S31] EfficientAT-mn04_as (Efficient Audio Transformer, width 0.4)
- 问题：AED 的小型档下界能压到多小，还能保住多少 AudioSet 精度。
- 方法：MobileNetV3 width_mult=0.4 主干，ImageNet 预训练后 ImageNet→AudioSet 迁移，再用 PaSST 做离线蒸馏。
- 数据：AudioSet AS-2M full + ImageNet（AudioSet 本体官方已停止分发，复现依赖第三方镜像）。
- 指标与条件：参数量 0.983M；AS-2M full tagging mAP 0.432；计算量 0.11 GMACs/10 s ≈ 11 MMACs/s（论文按 10 秒片段口径）；MIT 许可。
- 局限：不足 1M 参数下 mAP 0.432，比中型档下沿（PANNs-CNN14 0.431）几乎不差，但这是蒸馏+ImageNet 迁移的红利，换域后是否仍成立未知；官方无端侧转换案例（edge 列 unknown）；527 类输出头本身就占参数预算的大头。
- 对话：与 S39 的 YAMNet（3.7M / 0.306）构成"小 4 倍、高 12 点"的直接对照，是小型档的事实下界；与 `audio-events/01-small-models.md` 的 mn10/mn20 形成同一配方下的规模阶梯，用来分离"参数量"与"蒸馏配方"的贡献。

### [S32] EAT-base: efficient audio transformer
- 问题：ViT 类音频 Transformer 的预训练太贵，能否用更少 epoch 达到同级 mAP。
- 方法：Efficient Audio Transformer，ViT-B 骨干，改进自监督预训练目标（ utterance 级判别 + 掩码），10 epoch 与 30 epoch 两版。
- 数据：AudioSet AS-2M full（自监督预训练 + 有监督微调）。
- 指标与条件：参数量 88M；AS-2M full tagging mAP 0.486（10 epoch）、0.489（30 epoch）；AS-20K 对应 0.403 / 0.413。
- 局限：mAP 与 BEATs iter3+（0.486）持平，说明 85–90M 窄带上的差异主要来自配方而非结构；ViT-B 的单帧算力与内存对手机不友好，论文未给 RTF 或单帧 MMACs 实测；AS-20K 掉到 0.40 一线，说明训练集规模对结果影响大于结构。
- 对话：与 S35 的 BEATs、S33 的 CED 同处 86–90M 窄带，三者构成本综述"中型档精度天花板"的一组锚点；与 S31 的小型档对照，量化 ×90 参数换 +5.4 点 mAP 的边际收益。

### [S33] CED-Base: consistent ensemble distillation for audio tagging
- 问题：多个大模型的集成精度最高但无法部署，能否把集成蒸馏进单个中等模型。
- 方法：一致性集成蒸馏（CED），用 5 路大模型集合作教师，学生为 ViT 风格 Base（86M），蒸馏目标对齐教师集成输出。
- 数据：AudioSet AS-2M full；教师集成 AS-2M 约 50.1 mAP。
- 指标与条件：学生 86M；AS-2M full tagging mAP 0.500；AS-20K 对应 0.440；教师集成约 50.1（同表口径）。
- 局限：0.500 已接近教师集成，剩余空间很小，说明这条路线的收益接近饱和；学生仍依赖 AudioSet 全量标签，域外迁移未验证；86M + ViT 结构在端侧无公开转换案例。
- 对话：与 S32/S35 同带对照，是"蒸馏配方"红利的上沿；与 S31 的 0.983M/0.432 并列，给出"参数 ×87 换 +6.8 点"的定价；为 S38 的纯监督 CNN 下沿（0.431）提供同表锚点。

### [S34] TRILLsson: distilled universal paralinguistic representations
- 问题：副语言（情感、说话人、语调）表征能否蒸馏到 5M 级，供可穿戴常驻使用。
- 方法：从 CAP12 教师蒸馏出非语义语音表征（ResNetish / EfficientNetV2 两族），固定 2 秒 log-mel 窗，输出 1024 维话语 embedding。
- 数据：公开语料蒸馏自 CAP12；评测 IEMOCAP 与 CREMA-D（NOSS 协议）。
- 指标与条件：TRILLsson1 5.0M：IEMOCAP Acc 68.5、CREMA-D 81.3；TRILLsson3 21.5M：IEMOCAP 70.3、CREMA-D 83.2（arXiv 2203.00236 表 3，2 秒窗）。
- 局限：架构硬性截断在 2 秒窗，超过 2 秒才能判断的情绪状态在结构上看不到；IEMOCAP 68.5 与专用 emotion2vec（71.79）有 3 点差距；未找到公开的端侧转换案例（edge 列 unknown），"可穿戴可用"是参数量推断而非实测。
- 对话：与 S22 的 23.49M 学生同属最小档，但 S34 是通用副语言、S22 是情感专用；与 S28 的 93.79M 构成"×19 参数换 +3 点"的对照；2 秒窗限制直接约束 S61 类穿戴设备的判定节流设计。

### [S35] BEATs iter3+ (audio pre-training with acoustic tokenizers)
- 问题：音频自监督的离散 tokenizer 能否迭代自改进，从而把表征质量再推一档。
- 方法： acoustic tokenizer 与 Transformer 交替迭代训练（iter3），iter3+ 再用微调后的模型作 tokenizer 教师；90M ViT 骨干。
- 数据：AudioSet AS-2M full（自监督无标签预训练，再有监督微调评测）。
- 指标与条件：90M；AS-2M full tagging mAP 0.486（单模型）；AS-20K 0.389；集成 0.504 / 0.506（多模型集成，与单模型不可直接比）；arXiv 2022-12 首发，正式发表于 ICML 2023。
- 局限：单模型 0.486 与 EAT-base 持平，迭代 tokenizer 的增益主要体现在集成；90M + ViT 的端侧成本高，无公开手机实测；AudioSet 本体不可获取，复现依赖镜像，跨库迁移未系统报告。
- 对话：与 S32/S33 构成中型档三锚点；与 S31 的 0.983M 对照给出规模—精度曲线斜率；年份需双写（2022 arXiv / 2023 ICML），避免与 S33 的 2023 混淆排序。

### [S36] AST: audio spectrogram transformer
- 问题：把 ViT 直接套到音频频谱图上能否超过 CNN 基线，代价是什么。
- 方法：Audio Spectrogram Transformer，DeiT-B w/ Distill（ImageNet 预训练）作骨干，频谱图切 patch（fstride=tstride=10，384 输入），纯注意力无卷积。
- 数据：ImageNet + AudioSet AS-2M full。
- 指标与条件：87M；AS-2M full tagging mAP 0.459（单模型带 weight averaging）；AS-20K 对应 0.347；集成 0.485。
- 局限：0.459 已被同门 PaSST-S（0.471）与后续蒸馏模型超过，作为"锚点"而非"最优"；ViT-B 的算力/内存在端侧无可行路径；AS-20K 仅 0.347，说明数据规模对 Transformer 尤其关键。
- 对话：与 S37 的 PaSST-S 是同源可比的一对（patchout 效率改进）；与 S38 的 CNN14 构成"注意力 vs 卷积"的经典对照；为 S31–S35 的蒸馏路线提供教师侧的起点。

### [S37] PaSST-S: efficient training of audio transformers with patchout
- 问题：AST 训练慢、对 patch 顺序敏感，能否用 patchout 降训练成本且不掉点。
- 方法：Patchout（训练时随机丢弃 patch 及其位置编码）+ DeiT-B/384 骨干（S16,14 配置），结构化 patchout 进一步加速。
- 数据：ImageNet + AudioSet AS-2M full；另评 ESC-50、FSD50K、DCASE2020。
- 指标与条件：87M；AS-2M full tagging mAP 0.471（单模型）、集成 0.496；ESC-50 96.8%、FSD50K mAP 0.653、DCASE2020 76.3%（微调 <5 分钟，单卡口径）。
- 局限：仍是 87M ViT，patchout 省的是训练时间不是推理算力；ESC-50 96.8% 属小样本闭集，不能外推到开放场景；<5 分钟微调的硬件条件为单卡，未给端侧。
- 对话：与 S36 的 AST 同源，patchout 是"训练效率"而非"部署效率"的改进——这一点常被误读；与 S31 的 mn04（0.983M/0.432）对照，给出 ×88 参数换 +3.9 点的定价；其 ESC-50/FSD50K 数字为 S79 的 FSD50K 口径提供横向参照。

### [S38] PANNs-CNN14 (large-scale pretrained audio neural networks)
- 问题：大规模 AudioSet 预训练的 CNN 能否作为通用音频 tagging 的可复现基线。
- 方法：CNN14（80,753,615 参数，2048 维 embedding），Wavegram-Logmel-CNN 主干，AudioSet 全量有监督预训练。
- 数据：AudioSet AS-2M full（本体不可直接获取，复现依赖第三方镜像）。
- 指标与条件：80.75M；AS-2M full tagging mAP 0.431、mAUC 0.973、d′ 2.732；计算量 4222 MMACs/s（multi-adds 折算，假设 multi-add ≈ MAC）。
- 局限：0.431 是中型档下沿，却要 4222 MMACs/s——比 S31 的 11 MMACs/s 贵约 380 倍，是"参数不大但算力很贵"的典型；仓库无 LICENSE 文件，商用授权状态不明；纯监督、无蒸馏，已被同参数带的自监督/蒸馏模型拉开 7 个点。
- 对话：与 S31 的 mn04 构成"算力效率"的极端对照；与 S39 的 YAMNet 同属 TensorFlow 生态的事实基线；其 mAUC/d′ 口径为 S36/S37 只报 mAP 的条目提供补充维度。

### [S39] YAMNet (AudioSet MobileNetV1 tagging)
- 问题：手机/微控制器上做 521 类音频事件 tagging，最小可用的官方基线是什么。
- 方法：MobileNetV1 深度可分离卷积骨干 + 521 类 logistic 头，帧级 960 ms 输入，官方提供 TFLite / TFLite Micro 导出。
- 数据：AudioSet（官方 README 记 balanced 口径，域表按 AS-2M full 记属表级推断，见下）；情感侧另在 IEMOCAP 与 SERAB 上做过特征/微调评测。
- 指标与条件：3.7M 参数；每 960 ms 帧 69.2M multiplies（官方 README 逐字）；mAP 0.306（README 原文称 "balanced mAP"，以此为准；域表的 AS-2M full 标注为表级推断，非源文档明示）；另 d′ 2.318、lwlrap 0.393；SER 侧 IEMOCAP 56.1、SERAB 55.1。
- 局限：mAP 0.306 在 2026 年属低精度，只适合做"有无/粗类"门控；README 的 balanced 口径与域表推断的 full 口径不统一，直接横比会失真；521 类输出头对 MCU 仍偏大（int8 下仅头就占数百 KB）；SER 55–56 的水平说明它不能当情感模型用。
- 对话：与 S31 的 mn04 是"同预算不同时代"的一对（3.7M/0.306 vs 0.98M/0.432）；作为 S76 类 VAD 之上的"事件门控"层，与 S23 的专用警笛检测构成通用/专用的取舍；其官方 TFLite/TFLite Micro 导出与 S76 的 ONNX 导出并列，是 S63 端侧预算讨论的起点之一。

### [S40] openSMILE ComParE_2016 feature set + linear classifier
- 问题：不做神经预训练，纯手工声学特征 + 线性头在情感任务上还能到什么水平。
- 方法：openSMILE 提取 ComParE_2016 特征集（6,373 维：能量、频谱、F0、抖动、共振峰、MFCC 及其统计量），接线性 SVM/逻辑回归。
- 数据：评测 IEMOCAP、SERAB；中文侧 MER2024 用 eGeMAPS 子集做单模态基线。
- 指标与条件：6,373 维；IEMOCAP 62.1、SERAB 70.2（线性头协议）；MER2024 中文 eGeMAPS 单模态 WAF 39.68；特征提取为纯 DSP，可在 MCU 直跑、零量化成本。
- 局限：62.1 比 emotion2vec（71.79）低近 10 点，手工特征的天花板明确；6,373 维在 MCU 上要压成 eGeMAPS（88 维）才现实，压完精度进一步下降（MER2024 39.68 即此档）；openSMILE 为双许可，商用需 audiERING 授权，不能默认免费。
- 对话：与 S28/S30 的神经表征构成"手工 vs 自监督"的十年跨度对照；作为 S76（VAD）/S58（AGC）之外的"零神经"常驻路径，为 MCU 预算提供下界；其 eGeMAPS 中文 39.68 是"中文情感不能靠通用声学特征"的直接证据。

### [S41] Audio Flamingo 3
- 问题：通用音频大模型能否直接回答"刚才有没有这个声音"，以及它会不会凭空说出不存在的事件。
- 方法：AF-Whisper 统一音频编码器 + 7B LM（LLaVA 式架构），仅用开源音频数据做音频-文本对齐训练。
- 数据：仅开源音频数据，约 5,000 万音频-文本对。
- 指标与条件：参数量 8267M；TACOS 开放词表事件检测 Event F1 0.27、幻觉率 11.6%；显存 30.8 GB（MTEB 模型记录，bf16 量级）；对抗音频注入下攻击成功率 95.35%（同表 Gemini 3 Pro 79.65%）。
- 局限：Event F1 0.27 远低于判别式 AED（S33 的 0.50 mAP 不是同一指标，但量级差已足够说明问题），幻觉率 11.6% 意味着约每 8 次回答就有 1 次编造；权重为 NVIDIA OneWay 非商用许可，laos 商用不可直接采用；30.8 GB 显存排除端侧。归类 `非AGC(相邻：事件判别)`，收录理由是它代表"生成式事件问答"的上限与失效模式。
- 对话：与 S43/S44 的 7B 级 LALM 构成同一档的三条对照；与 S24 的开放词表判别式检测形成"生成 vs 判别"的分工；其 95.35% 注入成功率直接支撑"模型自述不能作为存证"的治理结论。

### [S42] Kimi-Audio-7B-Instruct
- 问题：端到端音频 LLM 在统一 tokenizer 下能否同时做转写、字幕与事件理解。
- 方法：12.5 Hz 音频 tokenizer（Whisper 连续特征 + 离散语义 token）+ Qwen2.5-7B 解码，端到端多任务指令微调。
- 数据：超过 1,300 万小时语音/声音/音乐混合语料。
- 指标与条件：参数量 9766M；AudioCaps 开放词表字幕 FENSE 49.00；官方模型卡只列 SEC/ASC 的任务覆盖，无可核验的事件检测数字。
- 局限：唯一可核验的精度是字幕 FENSE，属生成质量指标，不能当事件检测精度用；9.77B 参数 BF16 权重约 20 GB 量级（由参数量推算，非实测），服务端 GPU 专属；官方卡未标显存。归类 `非AGC(相邻：事件判别)`，收录理由是"无事件数字"本身是重要证据——榜单覆盖不等于能力可核验。
- 对话：与 S41/S44 同档，但 S41 至少给了 Event F1 与幻觉率；与 S50 的"冻结 ASR 骨干 + 小事件头"对照，说明 7B 端到端并不必然优于轻量专用头；其"任务覆盖≠指标"的缺口是 §7 未核实清单的典型样本。

### [S43] MiDashengLM-7B
- 问题：把音频编码器直连 LLM 解码器（不做音频 tokenizer 量化）能否降低首 token 延迟。
- 方法：Dasheng 音频编码器（5 Hz 帧率）直连 Qwen2.5-Omni-7B 的 Thinker 解码器，跨模态对齐后做指令微调。
- 数据：ACAVCaps 等公开音频-文本数据（含 AudioSet、FSD50k 等）。
- 指标与条件：参数量 8282M；吞吐 0.65 样本/秒、TTFT 40 ms（30 s 音频 + 100 输出 token，80 GB GPU bf16，batch=1）；其音频编码器 X-Ares 在 DESED 上准确率 53.7（片段级准确率，非 PSDS 定位口径）。
- 局限：53.7 是片段准确率，与 S24 的 PSDS1 42.2 不可比，混引会得出错误结论；TTFT 40 ms 是"编码器帧率低"带来的结构性优势，不代表整体交互延迟；8.28B 仍需 80 GB GPU。归类 `非AGC(相邻：事件判别)`，收录理由是它给出 LALM 侧最完整的一段"延迟—吞吐"实测。
- 对话：与 S44 的 Qwen2.5-Omni 是同一论文内的对照（TTFT 40 vs 160 ms，吞吐 0.65 vs 0.45）；与 S47 的 Dasheng-1.2B 共用编码器家族，可分离"编码器能力"与"LLM 解码"的贡献；其片段准确率口径提醒 §4 全表不得跨指标横比。

### [S44] Qwen2.5-Omni-7B
- 问题：全模态（音/视/文）LLM 在统一 Thinker-Talker 架构下，音频事件的漏检有多严重。
- 方法：Whisper-large-v3 音频编码器 + Qwen2.5-7B（Thinker 理解 + Talker 生成），全模态预训练。
- 数据：Qwen2.5 多模态预训练数据（官方技术报告，未逐项披露配比）。
- 指标与条件：参数量 10732M；吞吐 0.45 样本/秒、TTFT 160 ms（30 s 音频 + 100 token，80 GB GPU bf16，batch=1）；batch=16 时在 80 GB GPU 上 OOM；AHA 诊断给出事件遗漏率 >40%（Fig. 2）。
- 局限：事件遗漏率 >40% 是硬伤——十次里有四次以上"没听见"，不能用于任何需要召回的场景；batch 提到 16 即 OOM，说明显存换吞吐的空间很小；"全模态"的视觉通道对纯音频链路是纯成本。归类 `非AGC(相邻：事件判别)`，收录理由是它是"漏检"这一失效模式的最强反证。
- 对话：与 S43 同论文对照，量化"编码器帧率/架构"对 TTFT 的 4× 影响；与 S41 的幻觉率 11.6% 互补——一个多报、一个漏报，共同说明 LALM 不能直接当事件检测器；为 S05 的穿戴多通道数据提供"上大模型不等于更准"的边界。

### [S45] Miipher-2 (universal speech restoration, million-hour scale)
- 问题：百万小时级的语音修复（降噪、去混响、去失真）能否做到"不改说话人与情绪"。
- 方法：冻结的 USM 2B 主干 + 20M 可训练并行适配器 + WaveFit 声码器；用 USM 第 13 层特征，不需要文本或说话人 ID 条件。
- 数据：未给出（论文未在摘要列训练集名称与小时数；域表记"训练级批处理"口径）。
- 指标与条件：总参数 2000M（其中可训练 20M）；RTF 0.0078（TPU v4i，8 GB 显存）；100 颗芯片处理百万小时约 3 天；16 kHz / 25 ms 帧率。
- 局限：代码与权重均不公开，数字不可复现；需 TPU v4i，CPU/手机路径不存在；生成式修复会改写音素与音色（官方 demo 自述 Miipher-1 曾"完全改变说话人和风格"），在记忆生产链上属于不可接受的证据污染；非流式。该条归类为 `非AGC(相邻：修复·超分)`：它给出"生成式修复"的效率上限，用来判断该不该把修复放进记忆链。
- 对话：与 S48/S49 的扩散式修复并列，三者共同支撑"生成式复原不进存证链"的红线；与 S52/S53 的判别式降噪对照，说明"修复"与"增强"在证据风险上不同级；其"不改情绪"的宣称正是本综述要求独立核验的那类声明。

### [S46] Qwen2-Audio-7B-Instruct
- 问题：7B 级音频指令模型能否零样本完成情感识别与声音事件问答。
- 方法：Whisper 音频编码器直连 Qwen-7B，音频-文本多任务指令微调（ASR/S2TT/SER/VSC/AIR-Bench）。
- 数据：Qwen-7B 文本基座 + 音频-文本多任务数据（arXiv 2407.10759，配比未逐项披露）。
- 指标与条件：参数量 8397M；AIR-Bench Chat-Sound 6.99/10（开放词表音频问答，GPT-4 评分）；VocalSound ACC 0.9392（6 类人声事件，ASC 口径）。
- 局限：6.99/10 是 GPT-4 打分，评分器本身不可复现、不可审计；VocalSound 的 0.9392 是 6 类闭集，不能外推到 527 类；8.4B 参数属服务端。归类 `非AGC(相邻：事件判别)`，收录理由是它是"判别任务被改写成问答"后指标口径失真的典型。
- 对话：与 S41 的 TACOS Event F1 对照，说明"问答评分"与"事件 F1"不可互换；与 S28 的专用 SER 表征（71.79 WA）对照，7B 模型在人声情感上并无量级优势；为 S26 的 234M 一体模型提供"大即更强"的反例。

### [S47] Dasheng-1.2B (deep audio-signal holistic encoder)
- 问题：十亿级音频编码器冻结后接线性头，能在通用环境声任务上到什么水平。
- 方法：Dasheng 自监督音频编码器（0.6B / 1.2B）冻结，接线性分类头在 HEAR 基准上评测。
- 数据：VGGSound + AudioSet + MTG-Jamendo + ACAV100M，合计 272,356 小时。
- 指标与条件：Dasheng-1.2B 参数量 1134M；HEAR 环境声域线性评测 83.2（多任务均值）；同族 0.6B 为 82.4；两个大模型均无公开的 AudioSet mAP（只有 86M 的 Base 报 0.497，AS-2M full）。
- 局限：HEAR 是 19 项任务的平均分，不是 AudioSet mAP，不能与 S31–S38 的 mAP 同表比较；0.6B→1.2B 只 +0.8 分，规模收益已明显递减；服务端 GPU，无端侧转换案例。归类 `非AGC(相邻：事件判别)`，收录理由是它是"大型档下界"的锚点。
- 对话：与 S33 的 CED-Base（86M/0.500 mAP）构成"×13 参数、不同指标"的对照，说明大模型的优势在广覆盖而非单榜；与 S43 共用 Dasheng 编码器，可把"编码器能力"与"LLM 解码"分开看；其 272,356 小时语料是 S73/S79 之外最大的公开音频预训练规模记录。

### [S48] UNIVERSE++ (generative speech restoration)
- 问题：用扩散模型做通用语音复原（降噪/去混响/超分/去削波），主观听感能否超过判别式方法。
- 方法：分数扩散 + 对抗训练 + 内容微调；推理 8 步、ε=1.3；非迭代掩码，直接生成波形。
- 数据：16 kHz、55 种畸变链组合（训练期合成）。
- 指标与条件：参数量 107.5M（训练期 HiFi-GAN 判别器另加 41.4M）；推理 8 步；RTF 0.015（RTX 4090，另一篇独立论文实测，二手口径）；同系列 UNIVERSE 的 12 方听音中，生成式相对同容量回归版获 88% 偏好（二手口径，非 UNIVERSE++ 自身指标）。
- 局限：论文明确写"扩散过程无法为流式适配"，这是根本限制而非工程问题；RTF 0.015 是 RTX 4090 数字，端侧无路径；88% 偏好是主观听音、非事件/内容保真度指标，且对照的是神经网络回归而非经典 DSP；生成式复原可能"补"出原音里没有的内容。该条归类为 `非AGC(相邻：修复·超分)`：量化"生成式复原值不值"的主观收益。
- 对话：与 S45 的 USM 修复、S49 的超分共同构成"生成式复原"三件套，支撑不进记忆链的红线；与 S52/S53 的判别式掩码降噪对照，区分"改电平/改频谱"与"改内容"；其非因果性与 S45 的离线修复同侧，和 S58 的实时增益环形成"离线/生成 vs 实时/因果"的对照。

### [S49] AudioSR: versatile audio super-resolution at scale
- 问题：把 2–16 kHz 带宽的音频"脑补"到 48 kHz，生成式超分的实际代价与风险是什么。
- 方法：潜空间扩散超分（AudioLDM 式）：VAE + Transformer U-Net + HiFi-GAN 声码器，DDIM 采样 50 步，5.12 s 块处理。
- 数据：未给出（论文未在摘要列训练集名称与小时数）。
- 指标与条件：参数量 672M（二手口径：由第三方 INT4 移植模型卡分项加总 223M + 258M + 190M，非论文自报）；DDIM 50 步；INT4 MLX 移植实测 RTF 1.87（Apple Silicon M 系列，10.24 s 片段，同属二手口径）；约 6 GB 显存。
- 局限：RTF 1.87 即处理 1 秒音频要 1.87 秒，连实时都做不到，端侧更无可能；论文与仓库许可冲突（MIT vs CC-BY-NC-4.0），商用状态不明；官方文档自述强噪声或混响会降低性能；超分本质是生成缺失频带，不能作为证据链的一环。该条归类为 `非AGC(相邻：修复·超分)`：它给出"超分能否实时"的否定答案。
- 对话：与 S48 的扩散复原同属非因果生成路线；与 S57 的响度归一对照，说明"改带宽"与"改电平"是两类完全不同的操作；其许可冲突是 §10 核验层级要标"二手/冲突"的直接案例。

### [S50] Whisper-AT: noise-robust ASR with audio tagging head
- 问题：已有 ASR 骨干时，加一个事件标签头的增量成本有多小，能否顺带得到事件信息。
- 方法：冻结 Whisper-Large 编码器（655M），仅训练 TL-Tr512 标签头（7M）在 AudioSet 上做多标签分类。
- 数据：Whisper 680k 小时标注语音（骨干预训练）；标签头在 AudioSet 上训练。
- 指标与条件：总参数 662M（655M 冻结 + 7M 头）；AS-2M full tagging mAP 0.415；AS-20K mAP 0.328；BSD-2-Clause。
- 局限：mAP 0.415 明显低于同表 86–90M 的音频专用模型（0.50 一线），因为骨干是为语音 ASR 训练的，对音乐/环境声表征不足；仍要 655M 骨干常驻，端侧不可行；标签头只给 clip 级标签、无起止时间。归类 `非AGC(相邻：事件判别)`，收录理由是"增量成本可算"这一工程事实。
- 对话：与 S26 的"转写+情感+事件一体"思路同源，但 S50 把增量压到 7M；与 S39 的 YAMNet 对照，说明"蹭 ASR 骨干"在环境声上并不划算；其 0.415 与 S33 的 0.500 同为 AS-2M full tagging mAP，是同一指标下不同骨干的落差，不是两套指标口径。

### [S51] MossFormer2 (speech separation/enhancement, 55.7M)
- 问题：单通道语音分离在中等参数量下，能把混叠语音的 SI-SDR 提到多高。
- 方法：Transformer + FSMN 的混合架构，时域分离，MossFormer2 主体 55.7M（另有 S 版 37.8M）。
- 数据：WSJ0-2mix（两人仿真混合，闭集）。
- 指标与条件：SI-SDRi 24.1 dB（WSJ0-2mix，55.7M）；S 版 37.8M 为 23.2 dB；RTF 0.036–0.053（V100 GPU）。
- 局限：WSJ0-2mix 是仿真混合、两人闭集，真实重叠语音的 SI-SDRi 会显著下降；RTF 数字是 V100 上的，CPU 实时性标 unknown；分离输出两路，落地要选路/拼接，会引入新的错误源；55.7M 对常驻链路偏重。该条归类为 `非AGC(相邻：分离)`：分离是"多人说话"场景下增益/降噪之外必须比较的相邻手段。
- 对话：与 S52/S53 的降噪同属"采集后"处理，但目标从"压噪声"变成"拆人声"，不可互相替代；与 S63 的端侧预算对照，说明 55.7M 进不了 MCU；其闭集仿真口径是 §4 强调"指标必须带数据条件"的示例。

### [S52] DeepFilterNet3
- 问题：48 kHz 全带降噪能否在 CPU 上以 0.1–0.2 的实时因子跑，供桌面/边缘常驻。
- 方法：ERB 频带特征 + DeepFilter 滤波（改进版），输出频带增益与滤波器系数；48 kHz / 20 ms 帧。
- 数据：VoiceBank-DEMAND（仿真加噪的 48 kHz 语音）。
- 指标与条件：参数量 2.5M；PESQ 约 3.1（VoiceBank-DEMAND；二手口径——同架构 DF2 报 3.04，DF3 未在论文单列）；RTF 0.1–0.2（桌面 CPU）、0.5–0.8（RPi4）；Apache-2.0。
- 局限：PESQ 是仿真失真度指标，与主观听感/事件保真度不完全一致；DF3 的 3.1 是"同架构未单列"的二手口径，不能当论文实测；RPi4 上 0.5–0.8 的 RTF 已接近实时边界，手机低端核会更紧；输出掩码不改变整体电平，不能替代 AGC。该条归类为 `非AGC(相邻：增强)`：降噪常被误当增益控制，必须明确它只改掩码不改电平。
- 对话：与 S53 的 48K 参数极简版构成"质量—体积"两端；与 S56 的 85K 定点 C 对照，说明 2.5M 已属"小型档上沿"；与 S58 的 AGC2 串联时须先降噪后测电平，否则噪声门会误判。

### [S53] GTCRN (grouped temporal convolutional recurrent network)
- 问题：MCU 级预算（数十 KB 参数）下，降噪能否仍有可用质量。
- 方法：分组时序卷积 + 循环结构，16 kHz / 10 ms 帧，输出降噪掩码；极简参数量。
- 数据：VoiceBank-DEMAND（16 kHz）。
- 指标与条件：参数量 0.048M（论文记 23.7K 主体 / 39.6 MMACs，仓库口径 48K）；PESQ 2.87（VoiceBank-DEMAND）；ONNX Runtime Mobile INT8 可跑；MIT。
- 局限：16 kHz 窄带，对 8 kHz 以上（如烟雾报警器高频成分）无能为力；PESQ 2.87 是 2023 年的中档水平，比 S52 低约 0.2；48K 参数的容量决定了它只能处理稳态噪声，非稳态事件易被误抑；掩码不改电平。该条归类为 `非AGC(相邻：增强)`：它是"增强"在 MCU 上的体积下界。
- 对话：与 S56 的 RNNoise（85K、48 kHz）构成"窄带更小 vs 全带稍大"的取舍；与 S52 的 2.5M 形成三个数量级的阶梯；其 ONNX INT8 路径与 S76 的 ONNX 导出同属 S63 端侧预算讨论中"可部署"的一环。

### [S54] FRCRN (frequency recurrent CRN, DNS challenge)
- 问题：DNS 挑战赛路线的 10M 级增强网络，在官方榜单口径下能到多少。
- 方法：频率维循环的卷积循环网络（CRN），16 kHz 输入，输出复数掩码做增强。
- 数据：VoiceBank-DEMAND（DNS 挑战赛常用集）。
- 指标与条件：参数量 10.27M；PESQ 3.21（VoiceBank-DEMAND）；16 kHz。
- 局限：权重非商用，laos 不能直接用；无公开端侧转换案例，10.27M 比 S53 贵约 200 倍而 PESQ 只高 0.34，边际收益很低；16 kHz 窄带；PESQ 提升不等于事件可懂度提升。该条归类为 `非AGC(相邻：增强)`，收录理由是"10M 级增强的榜单口径"这一档位需要锚点。
- 对话：与 S53 的 0.048M/2.87 构成"×214 参数换 +0.34 PESQ"的定价；与 S52 的 2.5M/3.1 说明中等体积已能到 3.1；其非商用权重是 §10 许可列必须标红的案例。

### [S55] LAION-CLAP: large-scale contrastive language-audio pretraining
- 问题：音-文对比学习能否让"用一句话查声音"成立，零样本检测的实际水平如何。
- 方法：音频编码器与文本编码器做对比学习对齐，推理时用文本提示做零样本匹配（检索式开放词表）。
- 数据：大规模音-文对（LAION 系），具体小时数未在域表列出。
- 指标与条件：零样本 DESED PSDS1 22.8（同表监督 CRNN 基线 36.4，差 −13.6）；参数量未给出（域表未列双塔总参数）；仅 clip 级匹配、无起止时间。
- 局限：零样本比同表微调低 13.6 点，且文献普遍报告零样本与微调有 10–20 点落差；双塔含文本编码器，体积远大于 YAMNet 类；只给"像不像"的相似度，不给时间定位与置信校准；文本提示的措辞会显著改变结果，不可复现。该条归类为 `非AGC(相邻：检索)`，收录理由是"检索式开放词表"是事件发现的前置手段，与增益链无直接关系。
- 对话：与 S24 的 DASM 是同一对齐范式的"未微调 vs 微调"对照（22.8 vs 58.8）；与 S41–S43 的生成式问答构成"检索→生成"的两级；其 22.8 是 S24 表格中"开放词表不能直接上线"的直接证据。

### [S56] RNNoise (recurrent neural network noise suppression)
- 问题：常驻降噪能否用不到 0.1M 参数、定点 C 在任意 CPU/MCU 上跑。
- 方法：3 层 GRU 在 42 维频带特征上预测频带增益，48 kHz / 20 ms 帧，定点 C 实现。
- 数据：DNS4 blind test（真实录制的盲测集）。
- 指标与条件：参数量 0.085M；DNSMOS OVLMOS 3.38（DNS4 blind）；算力 <10 MFLOPS；48 kHz / 20 ms / 单通道；BSD-3-Clause；Cortex-A53 单核可实时。
- 局限：指标是 DNSMOS（主观质量的自动代理），不是 PESQ，也不是事件保真度；0.085M 的容量只能处理稳态噪声，对突发事件的抑制/误抑都不可控；输出增益掩码不改整体电平；DNS4 与 VoiceBank-DEMAND 的分数不可横比。该条归类为 `非AGC(相邻：增强)`：它是常驻降噪的功耗/体积基准。
- 对话：与 S53 的 GTCRN 构成 MCU 档的两个事实标准；与 S52 的 DFN3 是"0.085M vs 2.5M"的 30 倍阶梯；其 <10 MFLOPS 是 S76（VAD）与 S58（AGC2，未给出 MCPS；01 §2.3 明确拒绝估算）之外第三条常驻链路的算力锚点。

### [S57] FFmpeg loudnorm filter (EBU R128)
- 问题：离线批量音频如何统一到可比的响度电平，而不靠人耳试听。
- 方法：EBU R128 响度测量 + 真峰值限幅，双通（先分析后归一）或线性模式；3 s 分析窗、100 ms 子帧。
- 数据：不适用（算法/工具，非数据集评测）。
- 指标与条件：默认目标 −24 LUFS、LRA 7 LU、真峰值 −2 dBTP（源码默认值）；48 kHz / 100 ms 子帧 / 3 s 分析窗；LGPL-2.1-or-later；离线。
- 局限：必须预先分析整段音频，不能进实时采集环；目标是 LUFS，与 S58 的 dBFS 目标不可混用；双通会整体抬/降电平，若下游还有 AGC 就构成"二次增益"，是记忆链要避免的；对超短片段（<3 s）统计不稳。
- 对话：与 S58 的 AGC2 是"离线响度"与"实时电平"的两套口径，§4 全表反复强调不可互换；与 S60 的 SpeexDSP 对照，说明离线工具反而比实时环更可控；其"二次增益"风险直接对应综述的红线条款。

### [S58] WebRTC audio processing AGC2
- 问题：浏览器/手机通话里，实时增益环如何在不等幅削波的前提下把电平拉进可用区间。
- 方法：GainController2：模拟段（调 PGA，需硬件通路）+ 自适应数字段 + 限幅器；内部 RNN VAD（12 kHz、42 维、24 单元）驱动语音段判定。
- 数据：自测（无公开 benchmark，官方未发布标准集成绩）。
- 指标与条件：48 kHz / 10 ms 帧 / 单通道；增益变化率上限 3.0 dB/s、数字增益上限 30 dB、headroom 1 dB、噪声门 −50 dBFS；目标是 dBFS 电平而非 LUFS；BSD-3-Clause；算法延迟约 10 ms（由 10 ms 帧长推导）、状态约 2 KB（估算）。
- 局限：控制目标是 dBFS + headroom，不能直接当 −24 LKFS 响度归一来用；模拟段需硬件通路，第三方 App 通常只碰得到数字段；官方无公开精度/收敛数据，3.0 dB/s 的慢变率对突发大声压（关门、鸣笛）响应滞后；与降噪串联时噪声门阈值会被掩码改变。
- 对话：与 S59 的 Android 系统 AGC 是"可调参数 vs 只能开关"的对照；与 S57 的 loudnorm 构成实时/离线两套响度口径；与 S56 的 RNNoise 串联顺序（先降噪后测电平）是落地必须固定的细节。

### [S59] Android AutomaticGainControl (audiofx API)
- 问题：Android 系统级 AGC 效果器对应用暴露了哪些可控面，边界在哪。
- 方法：audiofx 框架 API，实际效果由 `/vendor/etc/audio_effects.xml` 挂载的厂商实现提供；应用侧只能开关。
- 数据：自测（无公开 benchmark）。
- 指标与条件：48 kHz / 帧长由 AudioRecord 决定 / 单或双通道；`VOICE_RECOGNITION` 场景必须默认关闭；除开关外无参数可调；Apache-2.0。
- 局限：参数完全不透明，不同厂商/机型行为不一致，无法作为可复现基线；`VOICE_RECOGNITION` 默认关闭意味着语音识别链路拿不到系统 AGC；采集后处理，前端削波无法补救；无任何公开指标。
- 对话：与 S58 的 AGC2（参数可读、源码可审）构成"可控 vs 不可控"的极端；与 S60 的 SpeexDSP 同属"轻量但能力有限"的一档；其不透明性直接支撑"常驻采集不能依赖系统效果器"的工程结论。

### [S60] SpeexDSP AGC (speex_preprocess)
- 问题：定点 DSP 上能否用极轻的增益环做电平拉平，供 MCU 移植。
- 方法：Speex 预处理器内置 AGC，按帧估计电平后施加数字增益；仅浮点实现。
- 数据：自测（无公开 benchmark）。
- 指标与条件：48 kHz / 帧长由调用方指定 / 单通道；只做数字增益（采集后）；源码注释明确"定点路径尚不支持 AGC（FIXME）"；无公开收敛时间数字；BSD（Xiph 三条款式）。
- 局限：只做数字增益，前端削波与过低信噪比都救不回来；浮点依赖使其在无 FPU 的 MCU 上不可用（与"S60 可移植到 MCU"的常见说法冲突，需按 FIXME 修正）；无公开收敛/稳态误差数据，无法评估对语音动态的损伤。
- 对话：与 S58 的 AGC2 是"有 VAD/噪声门/限幅"与"只有增益"的能力差；与 S57 的 loudnorm 对照，说明离线归一反而更适合做基准；其定点缺口是 §7 未核实清单里"工具类年份/能力近似"的第二例。

### [S61] Apple Watch Series 12 audio intelligence (Siri Recap)
- 问题：消费级巨头要在手腕上做"全天环境聆听"，如何同时给出留存期限、旁观者提示与端侧处理承诺。
- 方法：S11 芯片划出安全隔离区做临时音频处理；Siri Recap 全天聆听后生成标题+摘要+要点，Live Rewind 用环形缓冲回放最近 15 秒；两项功能各自独立 opt-in。
- 数据：不适用（产品能力，非数据集评测）。
- 指标与条件：二手口径：摘要 7 天不保存自动删除、可查看/编辑/删除、iCloud 端到端加密同步；原始音频"完全不可访问，连 Apple 也不行"；Recap 全天聆听无提示音/无指示灯，Live Rewind 每次触发有 chime；明确不识别说话人身份；可按时间/地点排程（2026-09-10 发布，Series 12 / Ultra 4）。
- 局限：全部为二手口径（科技媒体 + Apple 支持文档），无独立审计或第三方渗透测试；"原始音频不存在"是不可证伪的架构声明；Recap 无声无灯意味着旁观者无从知情，"opt-in"只覆盖佩戴者本人；不识别说话人，多人场景下的归属无法区分；仅两款硬件。
- 对话：与 S70 的云常开路线构成"端侧即焚 vs 云端留存"的成败对照；与 S76 的 VAD 门控、S05 的穿戴多通道采集同属常驻链路；其 15 秒环形缓冲与 7 天摘要留存，是 §2 留存梯度里最接近 laos"原始音频即焚、文本长留"的工业实现。

### [S62] EgoLog: ego-centric fine-grained daily log with ubiquitous wearables
- 问题：耳机/眼镜这类"已经戴在身上"的设备，能否用音频+IMU 做细粒度日常日志而不加新硬件。
- 方法：音频-IMU 双路融合（时域场景聚合 + 运动补偿的声源定位），先用 LLM 做场景推理，再把能力蒸馏回端上模型。
- 数据：可穿戴（耳机/眼镜）麦克风 + IMU 采集；未给出（域表未列参与者数、时长与场景数）。
- 指标与条件：活动识别超基线 12%、场景识别超基线 15%（域表口径，相对提升；未标数据集规模与绝对精度）。
- 局限：只有相对提升，没有绝对精度与混淆矩阵，无法判断是否够用；LLM 参与标注/推理意味着离线可复现性差；未给功耗、存储与常驻时长；未讨论旁观者同意与音频留存。
- 对话：与 S66 的 EgoADL 同为"非视觉传感做日常日志"，但 S62 用可穿戴、S66 用口袋手机；与 S05 的 WearVox 构成"采集能力"与"任务收益"的两面；其"LLM 蒸馏回端上"与 S26/S43 的蒸馏路线同构。

### [S63] DCASE2025 Task 1 baseline (low-complexity acoustic scene classification)
- 问题：128 KiB 参数、30 MMACs 的官方预算下，声学场景分类的官方基线到底能做到多少。
- 方法：简化 CP-Mobile（MobileNet 系）卷积网络，PyTorch + Lightning 训练，Freq-MixStyle 增强，推理时转 fp16；无外部预训练。
- 数据：TAU Urban Acoustic Scenes 2022 Mobile（10 类城市场景），仅用 25% 标签训练。
- 指标与条件：61,148 参数（fp16 122,296 B）；DCASE2025 Task1 宏平均准确率 53.24%；约 29.42 MMACs/1 s；预算为 128 KiB / 30 MMACs（fp16 上限 65,536 参数、int8 上限 131,072 参数）。
- 局限：53.2% 是 10 类场景分类，不是事件检测，不能与 mAP/PSDS 同表；61K 参数是 fp16 折算值，换 int8 才有 131K 空间，但输出头一换 527 类就吃掉一半预算（int8 下 67 KB）；城市场景、域内设备，跨设备/跨城市未验证；只有 25% 标签，标签效率的收益与精度上限混在一起。
- 对话：与 S31 的 mn04（11 MMACs/s、mAP 0.432）说明"同算力预算下 tagging 与 ASC 是两条赛道"；与 S53 的 48K 参数降噪同处"几十 KB"档；其 128 KiB 口径是 S77 的 512 kB 与 S39 的 3.7M 之间的预算锚点。

### [S64] 8.62 µW end-to-end spoken-language-understanding SoC
- 问题：从麦克风到"理解"的整条链路，功耗能否压到个位数微瓦。
- 方法：通道级 AGC + 时间稀疏性感知的流式 RNN，把特征提取与理解做成一颗 SoC；动态范围 75 dB。
- 数据：未给出（摘要口径：未列词表、任务与评测集）。
- 指标与条件：端到端 SLU 8.62 µW；动态范围 75 dB；论文指出传统 ADC+DSP 方案中 AFE + 数字特征提取合计占系统功耗 >50%。
- 局限：任务与词表规模未披露，"端到端 SLU"很可能是小词表命令词，不能外推到开放语音；定制芯片，工艺与工具链不可复现；通道级 AGC 是为该前端专门设计的，不是通用 AGC；75 dB DR 是模拟指标，与识别精度无关。
- 对话：与 S67/S72/S75 的纳瓦级前端构成"特征提取→VAD→KWS→理解"的功耗阶梯；与 S58 的 AGC2 对照，说明 AGC 放在模拟前端比放在采集后省得多；其"AFE+FEx 占一半功耗"直接支撑"先压前端"的优化顺序。

### [S65] Streaming Sortformer: speaker cache-based online diarization
- 问题：说话人日志能否在线做，且跨 chunk 保持身份一致、延迟压到秒级。
- 方法：Arrival-Order Speaker Cache（AOSC）+ FIFO 队列 + 当前 chunk；用 Sort Loss 学到到达时间顺序，规避排列问题。
- 数据：DIHARD III（真实多域录音）；训练用 7,000+ 小时（5,150 h 合成 + 2,030 h 真实，含 AISHELL-4）。
- 指标与条件：DER 18.97%（约 1 s 延迟）、19.32%（0.32 s 延迟），DIHARD III；训练数据 7,000+ 小时。
- 局限：DER 约 19% 意味着近五分之一的说话时间归属错误，只能做"粗归属"不能做证据级归属；说话人数量上限与内存占用未在域表列出；7,000 小时训练数据不可由个人设备复现；NVIDIA 服务端实现，无端侧路径。
- 对话：与 S11 的 MeMic 误差 0.09（不同任务：说话人计数/日志）不可直接比；与 S51 的分离构成"先分离再归属"与"直接归属"两条路；其 0.32 s 延迟是 §2 实时性梯度里"准实时"的代表点。

### [S66] EgoADL: multimodal daily-life logging in free-living environments
- 问题：不用相机，只靠口袋里的手机（音频+CSI+运动）能否记录自由生活中的日常活动。
- 方法：智能手机作多模态传感中枢，音频 + Wi-Fi CSI + IMU 融合，采集后在自由生活环境中标注 ADL。
- 数据：采集 120 小时多模态数据，标注其中 20 小时；覆盖 221 个 ADL、70 种物体交互、91 个动作（IMWUT 8(1) Article 17, 2024）。
- 指标与条件：未给出（域表只列采集/标注规模，未列识别精度或 F1）；标注率 20/120 ≈ 1/6。
- 局限：标注只覆盖六分之一，长尾活动几乎没有正样本；CSI 需要设备与路由器配合，不是纯音频方案；口袋姿态对声音是天然低通，高频事件（水壶鸣笛）可能衰减；未给隐私处理与旁观者同意流程。
- 对话：与 S62 的 EgoLog（可穿戴）构成"手机 vs 穿戴"两种载体；与 S73 的 Ego4D 是"小规模自由生活"与"三千小时第一视角"的尺度对照；其"音频比视频更适合日常日志"的三条理由（姿态不敏感、文件小、覆盖广）是常驻音频的选型依据。

### [S67] 0.4 V 988 nW time-domain audio feature extraction for keyword spotting
- 问题：唤醒链路里最费电的特征提取，能否用注入锁定振荡器在 0.4 V 下做到纳瓦级。
- 方法：注入锁定振荡器（ILO）做时域特征提取（TD-FEx），65 nm、0.4 V 供电，适配 <0.5 V 能量采集。
- 数据：未给出（摘要口径：10 词 KWS 任务，未列语料名）。
- 指标与条件：988 nW；面积 0.15 mm²（同节点下比先前工艺至少小 3.5×）；10 词 KWS 准确率 91%；比环形振荡器 TD-FEx 能效高 9×。
- 局限：只做特征前端，不含分类器，91% 是"前端 + 后端"整链结果还是前端单独结果未在域表区分；10 词闭集；0.4 V 近阈值工作对温度/工艺角敏感；定制 65 nm，不可在通用 MCU 上复现。
- 对话：与 S75 的串行 FFT MFCC（510 nW、97.3%）是两条特征前端路线（时域振荡器 vs 频域 FFT）；与 S72 的 47 nW VAD 构成"先 VAD 再提特征"的级联；其 9× 能效比是"模拟前端优于数字 DSP"的量化证据。

### [S68] TinyChirp: bird song recognition with TinyML on low-power wireless sensors
- 问题：野外长期监测能否"在端上筛、只回传有价值的片段"，而不是全录后取。
- 方法：nRF52840（Cortex-M4）上做 TinyML：8-bit 训练后量化 + Partial Convolution，时域模型与语谱模型对比。
- 数据：鸟鸣音频（具体物种数/小时数未在域表列出）。
- 指标与条件：精度 >0.98；SD 卡写入减少 90%；单节电池续航 2 周 → 8 周（×4）；MCU RAM 预算约 500 KB 量级；语谱图计算在 MCU 上可达 2.4 s，超过推理本身。
- 局限：单一任务（鸟鸣）且精度是闭集；2.4 s 的语谱图计算比推理更贵，说明"前端特征"才是瓶颈；>0.98 未给混淆类别与野外噪声条件；节点仍需 SD 卡与无线回传，不是"零留存"。
- 对话：与 S63 的 128 KiB 预算、S77 的 512 kB 平台构成 MCU 内存三档；与 S62/S66 的"端上筛选"结论同向；其"少写 90% → 续航 ×4"是 §2 "落盘比听更贵"的最强实证。

### [S69] Self-learning for personalized keyword spotting on ultra-low-power audio sensors
- 问题：唤醒词模型部署后无法拿到标注，能否用伪标签在端上增量个性化。
- 方法：用少量用户录音做相似度打分，给新采集帧打伪标签，在 MCU 上增量微调 KWS；利用 MCU 异构处理引擎跑常驻标注。
- 数据：两个公开数据集（域表未列名称与规模）；模型规模上限 0.5M 参数。
- 指标与条件：相对预训练模型准确率提升最多 +19.2% 与 +16.0%；标注任务在低功耗麦克风 + MCU 上实时，平均功耗最高 8.2 mW；片上训练能耗估算比标注低 10×（DS-CNN-S 每 6.1 s、DS-CNN-M 每 18.8 s 采一条新语料时）。
- 局限：+19.2% 是相对提升，基线越低越容易做出大数字；伪标签依赖"少量用户录音"的质量，用户不配合即退化；8.2 mW 是标注任务的功耗，不是常驻功耗；训练能耗是"按采样间隔估算"，非整机实测。
- 对话：与 S75 的固定词表 KWS 构成"静态 vs 自学习"两端；与 S68 的端上筛选同属"把学习/判断推到最边缘"；其 8.2 mW 与 S67 的 988 nW 相差近四个数量级，说明"自学习"的代价必须单列。

### [S70] Rewind / Limitless pendant (cloud always-on recorder)
- 问题：纯云常开的"记录一切"产品路线，商业与信任上能否持续。
- 方法：Rewind 桌面端常开后台录制 + 本地索引（早期全本地）；2024 改名 Limitless 推出 Pendant 吊坠，转写转向云端。
- 数据：不适用（产品史，非数据集评测）。
- 指标与条件：二手口径：2022 年 Rewind 承诺 "your data never leaves your device"；2024 年 Pendant 隐私政策写明 "we will receive audio recordings"；2025-12-05 Meta 宣布收购 Limitless，Pendant 即日停售；2025-12-19 Rewind 应用禁用全部屏幕捕获与音频捕获功能。
- 局限：二手口径（官方公告 + 媒体报道），停服/停售的商业原因不能单归因于隐私；没有用户留存率、使用频次等一手数据；产品史不含任何技术指标，不能用于选型；"被收购即停服"是可重复的行业模式而非个案。
- 对话：与 S61 的 Apple 端侧路线构成"云 vs 端"的成败对照；与 S18 的佩戴者意愿、S16 的旁观者同意构成"承诺—反悔"的信任链断裂案例；其"一旦架构允许上云，商业压力必然推上云"是综述把"零云"写成内核约束而非文档承诺的直接理由。

### [S71] Ego-Exo4D: first- and third-person video understanding
- 问题：同步的第一/第三人称视角 + 多麦克风阵列，能采集多大规模、标注成本多高。
- 方法：第一视角（眼镜）+ 第三人称多机位同步采集，配 7 麦克风阵列、IMU、gaze、3D 点云与专家解说。
- 数据：740 名参与者、13 个城市、123 个场景；1,286.3 小时、5,035 个 take、单段 1–42 分钟；7-mic array。
- 指标与条件：规模指标为 1,286.3 h / 5,035 takes / 740 人 / 7 麦克风；年份双写：arXiv 2023（2311.18259），正式发表 CVPR 2024（另有 IJCV 2025 版本）。
- 局限：技能性活动（烹饪、修车等）为主，不是日常闲聊，情感/对话分布偏斜；7 麦克风同步采集的硬件与标注成本个人设备无法复现；以视频理解为主，音频事件标注有限；采集涉及大量旁观者，同意流程不可直接复用。
- 对话：与 S73 的 Ego4D 是同一团队的两代语料（单视角 vs 音视同步）；与 S12/S13 的音视融合条目共享"多通道空间先验"；其 7-mic 配置是 S05 穿戴多通道采集之外的"阵列"参照。

### [S72] 47 nW voice activity detector with short-time CNN features
- 问题：常驻 VAD 的功耗地板在哪里，是否真需要神经网络。
- 方法：短时 CNN 特征提取 + RNN 分类器，权重存于非易失电容 ROM（免上电预加载），65 nm。
- 数据：GSCD 与 TIMIT（关键词/语音活动评测）。
- 指标与条件：47 nW；面积 0.022 mm²；VAD 参数仅 45 个；GSCD/TIMIT 整体命中率 94% / 91%；0.9–1.3 V、0–60 °C 无显著退化。
- 局限：45 参数意味着只能学"有声/无声"的粗边界，对音乐、键盘等非语音有声段无法区分；94%/91% 是命中率，虚警率与远端噪声条件未列；定制 65 nm，通用 MCU 上无法达到该功耗；无长时连续运行的漂移数据。
- 对话：与 S76 的 Silero VAD（~2 MB、30 ms <1 ms CPU）相差约五个数量级，是"专用硅 vs 通用核"的极端对照；与 S67/S75 的 KWS 前端构成"VAD→特征→唤醒"的功耗阶梯；其 45 参数是"VAD 不需要深度网络"的实证。

### [S73] Ego4D: around the world in 3,000 hours of egocentric video
- 问题：第一视角日常活动的大规模语料能到多大，情景记忆检索如何评测。
- 方法：931 名佩戴者在真实环境中长时间佩戴采集，含 audio / gaze / 3D mesh / 多机位；设 5 个 benchmark，含 Episodic Memory（自然语言查询）与 AV Diarization。
- 数据：3,670 小时、931 人、74 个地点、9 个国家、约 7 TB；单次佩戴 1–10 小时。
- 指标与条件：3,670 h / 931 人 / 74 地点 / 9 国 / 约 7 TB；年份双写：arXiv 2021（2110.07058），CVPR 2022。
- 局限：以视频为主，音频不是主标注对象，事件级标签稀少；7 TB 的规模对个人设备不现实；采集同意与伦理流程依赖机构 IRB，个人产品无法照搬；Episodic Memory 的 NLQ 指标与本综述的事件 mAP/PSDS 不可比。
- 对话：与 S71 的 Ego-Exo4D 是同一路线的两代；与 S19/S20 的个人音频归档构成"个人规模 vs 语料规模"的尺度链；其 Episodic Memory 是 S62/S66 类日志系统最接近的公开评测口径。

### [S74] AAD-KWS: sub-µW keyword spotting chip with acoustic activity detection
- 问题：唤醒词芯片能否用"声学活动检测"先门控，省掉常态的神经网络推理。
- 方法：非重叠帧串行 MFCC + 零成本 AAD（用 MFCC 一阶输出门控 NN 与后处理）+ 可调检测窗；28 nm、0.4 V。
- 数据：GSCD 双词任务。
- 指标与条件：安静场景 0.36 µW / 常态 0.8 µW；其中 MFCC 电路仅 170 nW；AAD 漏检率 0；双词准确率 97.8%。
- 局限：双词闭集，开放词表不可用；"漏检率 0"是在特定检测窗与信噪比下的结果，不能外推；28 nm 定制 + 0.4 V，通用硬件无法复现；AAD 门控会漏掉弱起音，对短指令词有结构性风险。
- 对话：与 S72 的 47 nW VAD 是"活动检测"的两种实现（RNN vs MFCC 一阶门控）；与 S75 的串行 FFT MFCC 同源但目标不同（门控 vs 识别）；其两级门控架构与 S76 的 VAD→ASR 分层完全同构。

### [S75] 510 nW wake-up keyword-spotting chip (serial-FFT MFCC)
- 问题：唤醒芯片的功耗能压到多低，代价是哪一档准确率。
- 方法：串行 FFT MFCC + 二值化深度可分离 CNN + 逐帧增量计算 + 近阈值电压；28 nm。
- 数据：未给出（摘要口径：单词/双词闭集任务，未列语料名）。
- 指标与条件：0.51 µW（40 kHz / 0.41 V）；面积 0.23 mm²（28 nm）；单词准确率 97.3%、双词 94.6%。
- 局限：闭集小词表；0.41 V 近阈值工作对工艺角与温度敏感，量产一致性未知；只报准确率，未报虚警率与功耗分解；二值化 CNN 的表达能力限制了词表扩展。
- 对话：与 S74 的 AAD-KWS（0.36/0.8 µW、97.8%）是同一预算带的两条设计；与 S67 的 988 nW 时域前端构成"频域串行 FFT vs 时域振荡器"；其 97.3% 是"微瓦级也能做到可用精度"的锚点。

### [S76] Silero VAD
- 问题：通用 CPU 上能否有一个足够轻、足够稳的 VAD，做 24/7 门控的事实标准。
- 方法：小型神经网络 VAD，官方提供 ONNX 导出；按 30 ms chunk 流式推理。
- 数据：未给出（官方仓库未给统一评测集与 DER 口径）。
- 指标与条件：MIT 许可；模型约 2 MB；30 ms chunk 在 CPU 上 <1 ms；ONNX 比原实现再快 4–5×；被 screenpipe / omi / say 等常驻项目采用。
- 局限：约 2 MB 与 47 nW ASIC（S72）差约五个数量级，只适合应用处理器；无公开 DER/虚警率基准，"事实标准"来自采用度而非精度证据；依赖 torch/onnxruntime，冷启动与内存占用未列；30 ms 帧对极短事件（门响、玻璃碎）可能整帧漏掉。
- 对话：与 S72 的 47 nW VAD 构成"软件通用 vs 专用硅"的两端；与 S58 的 AGC2 内置 RNN VAD 是同一角色的两种实现；其 30 ms/<1 ms 是 S63 类端侧预算里"门控几乎免费"的依据。

### [S77] Sound event detection with binary neural networks on power-constrained IoT
- 问题：SED 模型放不进 IoT 节点的 SRAM 时，二值化能否既装得下又保住精度。
- 方法：把 SED CNN 的滤波器与激活二值化，部署到 RISC-V 的 GAP8（8+1 核）MCU 上；Mel 预处理也在片上完成。
- 数据：未给出（摘要口径：未列数据集名与指标定义）。
- 指标与条件：原 CNN 占用 815 kB，超过平台 512 kB 内存；BNN 权重 58 kB（少 7.2×）、总内存 262 kB（少 2.4×）；准确率 77.9%，比全精度低 7%；峰值 4.6 GMAC/s、含 Mel 预处理的整网 1.5 GMAC/s；能效 67.1 / 31.3 GMAC/s/W；比 ARM Cortex-M4 实现快 10.3×、能效高 51.1×。
- 局限：77.9% 的数据集与指标定义摘要未标，不能与其他 SED 的 PSDS/F1 同表；7% 的掉点是二值化的固有代价；262 kB 仍高于 DCASE 的 128 KiB 预算；二值网络对域移与量化误差更敏感，跨设备未验证。
- 对话：与 S63 的 128 KiB 预算、S68 的 500 KB RAM 构成端侧内存三档；与 S53 的 48K 参数降噪说明"二值化"与"缩结构"是两条压缩路线；其 51.1× 能效比是"专用加速 vs 通用核"的量化证据。

### [S78] LeakyPick: IoT audio spy detector
- 问题：家里的智能音箱/电视是否在未经同意时把录音传上云，用户能否自己检测。
- 方法：独立设备周期性"探针"周围设备，监听网络流量统计特征，判断是否发生音频上传。
- 数据：8 台带语音助手能力的设备（品牌未在摘要列出）。
- 指标与条件：原型基于 Raspberry Pi，物料 < 40 美元；对 8 台设备的音频传输检测准确率 94%；用其发现 Amazon Echo Dot 会把 89 个词误判为唤醒词并触发上传。
- 局限：8 台设备的闭集，新设备/新固件需重新标定；依赖流量统计，全加密 + 恒定码率上传时特征会退化；94% 是"是否上传"的检测，不含内容与说话人；对抗者可主动伪装流量模式。
- 对话：与 S16 的旁观者同意、S18 的佩戴者意愿构成"合规承诺需要外部可验证"的三段论；与 S61 的"原始音频不可访问"形成对照——前者是声明，S78 是外部探测；其 89 个误唤醒词说明"唤醒词"本身不是可靠的采集边界。

### [S79] FSD50K: open dataset of human-labeled sound events
- 问题：需要一个许可清晰、类别足够多的事件集，替代不可分发的 AudioSet。
- 方法：从 Freesound 采集并众包标注，多标签、层级类别（144 叶节点 + 56 中间节点），按 AudioSet 本体组织。
- 数据：51,197 段片段、108.3 小时、200 类（144 叶 + 56 中间）。
- 指标与条件：51,197 clips / 108.3 h / 200 类；ICASSP 2022（arXiv 2020）；开放许可（CC），是少数可商用的事件集。
- 局限：200 类远少于 AudioSet 527 类，家庭长尾事件（玻璃碎、婴儿咳）覆盖不足；片段来自 Freesound，录制设备与场景分布偏"作品化"，不是常驻佩戴录音；众包标注有噪声，多标签一致性未在域表量化；与 AudioSet 训练的模型不可直接混评。
- 对话：与 S38/S39 的 AudioSet 训练模型构成"许可可用 vs 规模更大"的取舍；与 S37 的 PaSST-S FSD50K mAP 0.653 是同一评测口径；其 200 类层级本体是 S24/S55 开放词表落地时的标签骨架。

### [S80] Self-sustaining micro-watt programmable smart audio sensor for always-on
- 问题：不含电池、靠室内光供能，常驻音频传感能否自维持。
- 方法：混合信号事件驱动前端，最多 128 路时频特征 + 模式识别；室内光伏供能，含商用 MEMS 麦克风与能量采集子系统。
- 数据：未给出（摘要口径：两类音频流检测演示，未列语料规模）。
- 指标与条件：always-on 特征提取 26.89 µW；含 MEMS 麦克风与能量采集的整机 63 µW；两类音频流检测准确率 100%。
- 局限：两类音频流、100% 准确率是小规模演示，不能当泛化精度；依赖室内光照，暗处即失效；128 路特征 + 模板式模式识别，不是深度模型，类别扩展性差；2019 年工艺，面积/效率已被后续工作超越。
- 对话：与 S64 的 8.62 µW SLU、S67 的 988 nW 前端构成"自供能整机 → 端到端理解 → 单点前端"的功耗谱；与 S72 的 47 nW VAD 说明"检测"与"供电"是两笔账；其 63 µW 整机是 §2 里"常驻链路可以做到无电池"的唯一公开证据。

## 5. 叙事大纲

每行 = 正文一个 H3。「为什么这几篇放在一起」只允许四类关系：`能力→失效`、`方法→代价`、`结论→反例`、`同任务不同条件`，每行至少命中一类并写明机制。`代表文献` 覆盖 §4 全部 80 篇（S01–S80），同一篇可出现在多行（不同小节用它不同的侧面）。

| 小节 | 回答的问题 | 为什么这几篇放在一起 | 读者带走的一句判断 | 代表文献 |
| --- | --- | --- | --- | --- |
| §2.1 六领域与维度 | 六个领域为什么不能平行成六章，靠哪两个维度加任务类型对齐？ | `能力→失效`：规模主键上从 0.983M（[S31]）到 1134M（[S47]）不是同一条曲线，[S38] 的 4222 MMACs/s 说明「参数不大但算力贵」也会失效；[S63] 是 ASC、[S24] 是开放词表、[S27] 是多模态标记，三者各占一根不同的轴。 | 先按规模主键分档、再打 edge/multimodal 标记，AED 另加任务类型；否则矩阵会把不同任务塞进同一列。 | [S31] [S38] [S47] [S63] [S24] [S27] |
| §2.2 检索与筛选 | 80 篇从哪来，哪些「没有漂亮数字」的条目凭什么保留？ | `结论→反例`：[S42] 官方卡只给字幕 FENSE，作为「榜单覆盖≠能力可核验」的反例保留；[S23] 只有摘要、[S57] 只有工具文档，靠「缺失本身是证据」入册；[S80] 两类音频流 100% 只作功耗谱端点。 | 纳入标准不是「有漂亮数字」，而是「能定位原文 + 能说清缺什么」。 | [S42] [S23] [S57] [S80] |
| §2.3 证据等级与可比规则 | 四种核验层级怎么用，哪些数字能同表、哪些只能并列？ | `同任务不同条件`：[S43] 的 53.7 是片段准确率、[S24] 的 42.2 是 PSDS1，同表会造出假结论；[S50] 的 0.415 与 [S33] 的 0.500 同为 AS-2M full mAP 才可横比；[S57] 的 LUFS 与 [S58] 的 dBFS 是两套电平语言。 | 同指标、同定义、同数据划分才可横比，否则只并列并标条件。 | [S43] [S24] [S50] [S57] |
| §3.1 AgentOS | AgentOS 一词在文献里指什么，音频站在哪一层？ | `能力→失效`：[S01] 把执行放端侧、[S02] 把 Agent 放进内核调参面，Agent 权力越大越先撞上 [S03] 的可审计、[S04] 的审计预算、[S08] 的注入隔离、[S09] 的工具过用。 | 现有 AgentOS 没有内核级音频层，音频只是工具调用/传感器；治理面必须外挂，不能指望模型自觉。 | [S01] [S02] [S03] [S04] [S08] [S09] |
| §3.2 全天候录音 | 常驻录音的产品与学术证据，对端侧音频栈给出哪些硬约束？ | `方法→代价`：[S19]/[S06] 给出日均词量与三个数量级的个体差，[S20] 给出归档设计，[S11]/[S16]/[S18] 说明同意粒度，[S61]/[S70]/[S78] 是端侧即焚、云常驻停售、外部探测三种结局；功耗阶梯由 [S80]/[S72]/[S74]/[S75] 到 [S76]，[S65]/[S68] 补上在线内存与落盘代价。 | 触发、功耗、留存三笔账必须同时算；「零云」是架构约束，不是文档承诺。 | [S06] [S11] [S16] [S18] [S19] [S20] [S61] [S65] [S68] [S70] [S72] [S74] [S75] [S78] [S80] |
| §3.3 多模态 | 音频为主、视觉为例外的判断，证据是什么？ | `同任务不同条件`：[S27] 的 AV-SER 三档 UAR 只从 66.85 走到 68.21，且必须成对音视频；[S07]/[S10] 的 AV 事件增益只在「有视频」条件成立；[S44] 的全模态视觉通道对纯音频链路是纯成本；[S71] 的 7 麦克风加多机位采集个人设备复现不了。 | 视觉的增量在定位与「有视频」条件，分类与常驻链路上默认不做。 | [S07] [S10] [S27] [S44] [S71] |
| §3.4 应用矩阵 | 已落地的系统各自把音频放在哪、靠什么触发、留多久？ | `方法→代价`：[S61] 用 15 秒环缓 + 7 天即焚换常开，[S70] 的云常驻以停售收场，[S66]/[S62] 用手机/穿戴换日常日志，[S73] 用 3,670 小时语料换评测口径，[S76] 用 VAD 门控把常驻成本压到近零。 | 能长期活的都是「端侧处理 + 有限留存 + 明确触发」，其余形态都付出了信任或成本代价。 | [S61] [S62] [S66] [S70] [S73] [S76] |
| §4.1 任务/指标陷阱 | SER 的数字为什么经常不能横比？ | `同任务不同条件`：[S28] 的 71.79 是线性探针，[S30] 的 63.8 换了协议，[S27] 的三档是论文自复现协议，[S39] 的 0.306 是 balanced 口径，[S46] 的 6.99 是 GPT-4 打分，[S43] 的 53.7 是片段准确率。 | 读 SER 数字先问三件事——标签集、划分协议、指标名，缺一项就只能并列。 | [S28] [S30] [S27] [S39] [S46] [S43] |
| §4.2 三档规模与端侧 | SER 的规模—精度曲线长什么样，三条端侧降本路线各买到什么？ | `方法→代价`：[S40]（手工特征）→[S34]（5M）→[S22]（23.5M）→[S28]（93.8M）→[S30]/[S26]（164–234M）→[S46]（8.4B）是精度阶梯；[S21] 改计算范式、[S22] 改数值精度、[S25] 改图结构，三条路各自只解决一段。 | 手机常驻的甜点在 5–25M；再往上必须量化或蒸馏，且跨库掉点要单独记账。 | [S21] [S22] [S25] [S26] [S28] [S30] [S34] [S40] [S46] |
| §4.3 多模态 SER 增量 | 加视觉对 SER 到底值多少？ | `能力→失效`：[S27] 声称音视融合提升 SER，但 T/S/B 三档（20/46/81M）的 UAR 只从 66.85 走到 68.21，模态缺失消融未给，跨协议又不能与单模态 71.79 相比；[S12] 的统一音视以单任务精度为代价；[S13] 的融合增益落在定位而非分类；[S44] 的全模态反而漏检 >40%。 | 视觉对 SER 的净增量至今没有被单独测出来，双路采集与合规的代价却是确定的，不能作为常驻链路的前提。 | [S27] [S12] [S13] [S44] |
| §4.4 SER 矩阵判断 | 给定 laos 的端侧与中文约束，SER 放哪一档、选谁做基线？ | `结论→反例`：[S28] 的「情感专用」在中文上落后通用 HuBERT（56.08 对 69.26），使 [S26] 的 234M 一体模型反成中文主路径；[S27] 的 AV 多模态也没有换来高于单模态的 UAR；[S34] 的 2 秒窗与 [S40] 的 6373 维给出一上一下两个边界。 | SER 只做辅助信号：中文主路径选 234M 一体模型，端侧下界用 5–25M 蒸馏表征。 | [S22] [S26] [S27] [S28] [S30] [S34] [S40] |
| §5.1 维度拆解 | AED 的几类标签为什么不能并列成一张表？ | `同任务不同条件`：[S63] 的 53.24% 是 10 类 ASC，[S31] 的 0.432 是 527 类 tagging，[S24] 的 42.2 是 PSDS1，[S47] 的 83.2 是 HEAR 19 项均值，[S55] 的 22.8 是零样本 PSDS1；规模、edge、多模态是标记位，不是同一根轴。 | AED 表必须先分任务类型再分档，跨任务类型只并列、不折算。 | [S63] [S31] [S24] [S47] [S55] [S38] |
| §5.2 小型档 DCASE | 几十 KB 到几 M 参数这一档，AED 的真实上限在哪？ | `方法→代价`：[S63] 的 61K 参数在 128 KiB 预算下拿 53.24%，[S31] 的 0.983M 拿 0.432 mAP 靠 ImageNet 迁移加蒸馏，[S39] 的 3.7M 只有 0.306，[S23] 二类闭集但无同条件数字，[S29] 只给相对压缩比，PSDS 损失未测。 | 小型档的精度红利来自蒸馏与任务窄化，不来自结构：[S31] 的 0.432 靠迁移+蒸馏，[S63] 的 53.24% 是 10 类 ASC 的窄任务口径；128 KiB 档只能做场景与门控。 | [S63] [S31] [S39] [S23] [S29] |
| §5.3 中型档甜点 | 86–90M 这一带为什么是甜点，甜点的价码是多少？ | `同任务不同条件`：[S33]（0.500）、[S32]/[S35]（0.486）、[S37]（0.471）、[S36]（0.459）、[S38]（0.431）全在同一 AS-2M full mAP 口径上；[S50] 用 662M 只拿 0.415，[S37] 在 FSD50K 上的 0.653（数据集见 [S79]）是另一套数据口径。 | 0.49–0.50 mAP 是中型档天花板，再加参数只买到覆盖广度；「蹭 ASR 骨干」不划算。 | [S32] [S33] [S35] [S36] [S37] [S38] [S50] [S79] |
| §5.4 大型档开放词表 | 大型档与开放词表各解决了什么，代价与失效模式是什么？ | `能力→失效`：[S24] 零样本 22.8 对微调 58.8，[S55] 的 22.8 是同范式未微调，[S17] 零样本比微调低约 28 点；[S41] 的 Event F1 0.27 加幻觉 11.6%，[S44] 的事件遗漏 >40%，[S42] 干脆没有可核验事件数字；[S43]/[S46]/[S47] 给出延迟与口径但仍在服务端量级。 | 开放词表「查得到」但「定不准」，问答式大模型不能替代判别式 AED。 | [S17] [S24] [S41] [S42] [S43] [S44] [S46] [S47] [S55] |
| §5.5 端侧 runtime | 把 AED/SER 放进手机或 MCU，实测的 runtime 与体积是什么量级？ | `方法→代价`：[S26] 的 234M 导出 ONNX INT8 约 228 MB，[S30] 的 checkpoint 649 MB，[S53] 的 48K 参数可走 ONNX Runtime Mobile INT8，[S52] 在 RPi4 上 RTF 0.5–0.8，[S77] 的 BNN 262 kB 上 GAP8，[S69] 的端上自学习标注要 8.2 mW。 | MB 级模型只进应用处理器，常驻链路只能放 KB 级门控；runtime 账要按平台分开记。 | [S26] [S30] [S52] [S53] [S69] [S77] |
| §5.6 多模态定位 | 音视融合在 AED 里的真实增量落在哪个子任务？ | `结论→反例`：[S12] 的统一音视以单任务精度为代价，[S13] 的低资源融合只报「显著提升」无绝对值，[S14]/[S15] 的榜单口径偏方位，[S10] 只给聚合准确率缺分模态消融，[S05] 的多通道提升也只是案例研究。 | 视觉增量集中在事件定位与方位，分类增益没有被证明；常驻链路不该为定位常开摄像头。 | [S05] [S10] [S12] [S13] [S14] [S15] |
| §5.7 AED 矩阵判断 | 给定 25 mW 常驻预算与 527 类需求，AED 该怎么选型？ | `能力→失效`：[S33] 的 0.500 与 [S31] 的 0.432 都进不了常驻前端，[S63] 的 128 KiB 档只能做场景，[S77] 的 262 kB 仍超预算，[S24]/[S55] 的开放词表在零样本下不可用，[S41]/[S44] 的问答式模型漏检与幻觉双向失控。 | 常驻只做事件驱动的 KB 级门控，527 类识别放事件触发后的应用处理器。 | [S24] [S31] [S33] [S41] [S44] [S55] [S63] [S77] |
| §6.1 经典 DSP 档 | 不训练神经模型，AGC 能做到什么程度？ | `同任务不同条件`：[S57] 的 loudnorm 是离线 LUFS 两遍测量，[S58] 的 AGC2 是实时 dBFS 环（3.0 dB/s、10 ms 帧），[S59] 的 Android 系统效果器只能开关，[S60] 的 SpeexDSP 定点路径缺 AGC，[S64] 把通道级 AGC 放进 8.62 µW 的模拟前端。 | AGC 的基线是 DSP 环；离线归一与实时环是两套目标，不能互换。 | [S57] [S58] [S59] [S60] [S64] |
| §6.2 三档模型 | AGC 的神经模型在哪几档存在，与相邻的增强/修复怎么划界？ | `方法→代价`：[S52]（2.5M）与 [S53]（48K）是降噪掩码，[S56]（85K）是常驻降噪，[S54]（10.27M）是 DNS 榜单口径，[S51]（55.7M）做分离；[S45]/[S48]/[S49] 是生成式修复与超分，都会改内容，只能标 `非AGC(相邻)`。 | AGC 专用神经模型几乎都是「增强+增益」联合，纯增益神经模型稀缺；改内容的一律不进记忆链。 | [S45] [S48] [S49] [S51] [S52] [S53] [S54] [S56] |
| §6.3 端侧延迟/功耗 | 增益与增强环放进端侧，延迟和功耗的现实边界在哪？ | `方法→代价`：[S58] 的 10 ms 帧推导出约 10 ms 算法延迟，[S52] 桌面 CPU RTF 0.1–0.2 而 RPi4 到 0.5–0.8，[S53] 只到 16 kHz，[S56] 的 <10 MFLOPS 是常驻降噪算力地板，[S64] 说明 AGC 放模拟前端远比放采集后省。 | 48 kHz 实时环在低端核上只剩 0.5–0.8 RTF 的余量；先压前端，再谈模型。 | [S52] [S53] [S56] [S58] [S64] |
| §6.4 多模态 AGC | 多模态对 AGC 有没有直接证据？ | `结论→反例`：没有任何一篇给出音视联合增益控制的指标；[S27] 的 AV-SER 三档 UAR 66.85–68.21 未与同协议纯音频对照，[S13] 的融合增益在定位，[S44] 的全模态视觉通道是成本，[S71] 的 7 麦克风阵列采集个人设备复现不了。 | 多模态 AGC 目前只有相邻领域证据，判定「非空但薄」，默认不做。 | [S13] [S27] [S44] [S71] |
| §6.5 AGC 矩阵判断 | 给定「采集后、因果、防二次增益」的约束，AGC 链怎么搭？ | `能力→失效`：[S58] 有 VAD/噪声门/限幅但目标是 dBFS，[S60] 只有增益且定点路径缺失，[S59] 参数不透明，[S57] 的离线双通一旦与实时环串联就是二次增益，[S52]/[S56] 必须先降噪后测电平。 | 主链用实时 AGC 环，离线只用 loudnorm 做基准，禁止两条增益链串联。 | [S52] [S56] [S57] [S58] [S59] [S60] [S64] |
| §7.1 跨领域指标可比性 | mAP、PSDS1、ASC 准确率、UAR、SI-SDRi、PESQ、LUFS 之间怎么摆？ | `同任务不同条件`：[S31]/[S33] 在同一 mAP 轴，[S24]/[S55] 的 22.8–42.2 是 PSDS1，[S63] 是 ASC 准确率，[S28]/[S30] 是 WA/UAR，[S51] 是 SI-SDRi，[S58] 是 dBFS；把 Event F1 0.27 与 mAP 0.50 并排就是量级误导。 | 跨领域只允许并列成「能力档位」，不允许折算成同一分数。 | [S28] [S30] [S31] [S33] [S51] [S55] [S58] [S63] |
| §7.2 端侧预算的三种语言 | mW、ms、MB 三种预算语言怎么落到同一条选型线？ | `方法→代价`：[S64]（8.62 µW）/ [S67]（988 nW）/ [S72]（47 nW）/ [S80]（63 µW 整机）是功耗谱，[S58] 的 10 ms 与 [S52] 的 RTF 是延迟谱，[S26] 的 228 MB 与 [S30] 的 649 MB 是体积谱；三者不同轴，任一项超预算即淘汰。 | 常驻链路按 mW 选，交互链路按 ms 选，模型体积按 MB 选；三者不能互相折算。 | [S26] [S30] [S52] [S58] [S64] [S67] [S72] [S80] |
| §7.3 多模态的三种结局 | 多模态在三个任务里为什么结局不同？ | `同任务不同条件`：[S27] 疑似增量但未单独测出（SER，AV 三档 66.85–68.21，档位差与参数量同增，无纯音频对照），[S13] 薄（AED 定位，无绝对值），[S07] 只在有视频时有效而 [S44] 的全模态反而 >40% 漏检——同一「加视觉」动作，三个任务三种结局。 | 多模态的准入条件按任务写死：SER 增量未测出，按可有可无处理；AED 只用于定位，AGC 默认不做。 | [S07] [S13] [S27] [S44] |
| §8 研究空白与未来方向 | 六个领域拼起来还缺什么？ | `能力→失效`：每条未来方向都由一张卡的失效面定义——[S02] 的 Agent 改内核无回滚、[S63] 的 128 KiB 档做不了 527 类、[S28] 的中文失效、[S58] 的 dBFS/LUFS 断层、[S24] 的零样本不可用、[S78] 的合规承诺需要外部探测。 | 六条未来方向不是「再做更大的模型」，而是补治理面、补端侧档位、补跨库与可验证性。 | [S02] [S24] [S28] [S58] [S63] [S78] |

## 6. 溯源核验记录

## 7. 未核实清单

- [U01] 7 条早于 2017-01-01 检索窗的纳入条目（按名称登记，编号随重排可能变动）：Are women really more talkative than men?（2007）、Minimal-impact audio-based personal archives（2004）、openSMILE ComParE_2016 特征集（2016）、FFmpeg loudnorm（2016）、WebRTC APM AGC2（2013）、Android audiofx AutomaticGainControl（2010）、SpeexDSP AGC（2007）— 保留理由：经典 DSP 基线与端侧事实标准，日均词量/存储量级与实时增益环接口至今无等价替代 — 读者如何对待：只作基线对照与量级锚点，不与窗内神经模型的指标直接横比；工具类年份为首次公开可用年，§10 定稿前逐条回官方 changelog 复核 — 影响 §3、§6、§10
- [U02] 代指行：wav2vec 2.0 base、SALMONN-7B/13B、Emotion-LLaMA 在 80 篇语料内没有独立卡片；§4 矩阵的 `代表文献` 取同档最近卡片（[S22]、[S46]）代指，数字取自领域表 `docs/research/speech-emotion/02-medium-models.md`、`03-large-models.md` 的表格核实口径，未回原文逐表核对（代指关系本身使数字归属不可逐项追溯）— 影响 §4（§4.4 矩阵与读表说明）、§7.1（代指行不参与折算）— 读者如何对待：只作量级参照，永不参与 §7 的跨领域折算
- [U03] STEPX Neo（2026-10 发布）：只有产品稿二手口径，无论文、无卡片；§3.1 与 §3.4 用 [S05]/[S61] 作最接近的代指，产品稿未给功耗或延迟数字（无法核到系统调用语义）— 影响 §3（§3.1 判断、§3.4 应用矩阵第 2 行）— 读者如何对待：当二手产品色彩读，不能当作"音频系统调用面存在"的证据
- [U04] DCASE Task 1 年度最高分 60.8%（2022 Chang_HYU）/ 62.7%（2023 CPJKU）/ 62.1%（2024 Cai_XJTLU）/ 61.5%（2025 Karasin_JKU）与官方基线 44.2% → 53.2%：取自官方结果页，经 `docs/research/audio-events/01-small-models.md` §2.1 汇总，本综述未为榜单另立卡片（榜单条目无法逐条对应到可引原文）— 影响 §5.2 — 读者如何对待：当赛事记录读，不当同行评审测量；年度间训练子集不同（2024 多子集、2025 仅 25% 标签），只能看窄带、不看趋势
- [U05] emotion2vec+ large 参数量两口径冲突：实测/checkpoint 反推 164M（config depth 8 / embed_dim 1024）对官方标称 ~300M（[S30]），未拆层核对哪一口径含帧级头 — 影响 §4.2、§4.4 — 读者如何对待：两口径并列引用，按 300M 记手机端代价，不能只取其一
- [U06] SALMONN 的 7B/13B 取自 HF 卡标称，未逐层加总双编码器（Whisper + BEATs）；AED 领域表因总参数无法钉死而把它排除在外 — 影响 §4（矩阵大型档）、§7（折算排除）— 读者如何对待：大型档只按名义量级读，不当作可核到参数量的条目
- [U07] DASM 总参数原文未公布（领域表 `audio-events/03-large-models.md` 估为'百万级'；若按字面 <30M 应入小型档）；§5.4 矩阵按族（CLAP 双塔 + 检测头）登记为中型，不是核到总数后的分档 — 影响 §5.4 — 读者如何对待：档位是临时值，核到总数应改档；42.2 是 PSDS1，不与任何 mAP 相减
- [U08] 部分字段只到摘要口径的条目（[S05]、[S07]、[S10]、[S12]、[S13]、[S14]、[S15]、[S21]、[S23]、[S25]、[S29]、[S64]、[S67]、[S75]、[S77]、[S80]）：这些条目的数据集、划分或指标定义只在摘要层面可读，未回正文表格逐项核对 — 影响 §3、§4、§5、§6、§7、§8 — 读者如何对待：当方向性结论读，不参与跨行比较
- [U09] 语料外的多模态 AGC：AV-NeuroAMP 论文（助听器场景联合 SE + 放大 + 动态范围压缩，AVSEC-2/TMSV 评测，作者自述"未为可穿戴因果运行设计"）与 2 项专利（Nuance 2011 申请、Intel 2021 授权），无卡片、不进矩阵，论文无权重、专利无实现 — 影响 §6.4（"非空但薄"的边界）、§7.3（"只有语料外存在性"）、§8（第 2 条合规前置）— 读者如何对待：只作存在性证明（想法存在），不说明它能上常驻链路，也不作准入理由
- [U10] 来源内部功耗断言自相矛盾：`docs/research/always-on-recording/hardware-power.md` §3 正文称写盘比"听"贵"1–2 个数量级"，同节表格给的是写 SD 17–70 mW 对端上分类 ≤25 mW、约 0.7–2.8 倍（同量级），来源内部无法裁决 — 影响 §1（结论 6）、§3.2（三条硬约束之 3）、§7.1（功耗陷阱）— 读者如何对待：用表格数（17–70 mW 对 ≤25 mW），不用正文的"1–2 个数量级"
