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

| 编号 | 文献 | 决定 | 理由 |
| --- | --- | --- | --- |
| C001 | [EcoAgent: device-cloud collaborative multi-agent framework for mobile automation](https://doi.org/10.1609/aaai.v40i35.40230) | 纳入 S01 | 端侧证据：设备-云协同自动化，端上执行器与云端编排的分工边界 |
| C002 | [TuneAgent: agentic operating system kernel tuning with RL](https://doi.org/10.1145/3770855.3817987) | 纳入 S02 | 常驻约束：Agent 直接改内核参数，给出 OS 级负载治理的可写面 |
| C003 | [TraceBrain: open-source framework for agentic trace management](https://doi.org/10.24963/ijcai.2026/975) | 纳入 S03 | 合规：运行轨迹作为可审计对象，事件级留存与回放 |
| C004 | [Optimally auditing adversarial agents](https://doi.org/10.1609/aaai.v40i20.38722) | 纳入 S04 | 合规：审计采样与预算分配，合规抽检的方法论边界 |
| C005 | [WearVox: egocentric multichannel voice assistant benchmark for wearables](https://arxiv.org/abs/2601.02391) | 纳入 S05 | 多模态：可穿戴多通道基准，佩戴者视角的采集与干扰条件 |
| C006 | [Are women really (not) more talkative than men? A registered report](https://doi.org/10.1037/pspp0000534) | 纳入 S06 | 常驻约束：全天候采集的日均语音量基线，直接决定留存与算力预算 |
| C007 | [Listen, see and track: spatio-temporal audio-visual sound event reasoning for omni-modal LMs](https://arxiv.org/abs/2608.09435) | 纳入 S07 | 多模态：音视联合事件推理进 omni-modal 模型，暴露单模态天花板 |
| C008 | [DRIFT: dynamic rule-based defense with injection isolation for securing LLM agents](https://doi.org/10.52202/085713-2791) | 纳入 S08 | 合规：规则化注入隔离，对照 laos syscall 闸门的规则面 |
| C009 | [SMART: self-aware agent for tool overuse mitigation](https://aclanthology.org/2025.findings-acl.239/) | 纳入 S09 | 常驻约束：工具过用的预算治理，对应能力管控的拒绝面 |
| C010 | [JointAVBench: benchmark for joint audio-visual reasoning evaluation](https://arxiv.org/abs/2512.12772) | 纳入 S10 | 多模态：音视联合推理评测，区分「看见」与「听出」的贡献 |
| C011 | [MeMic: towards social acceptability of user-only speech recording wearables](https://doi.org/10.1145/3613905.3650872) | 纳入 S11 | 合规：只采佩戴者语音的社会可接受度实证，给旁观者可见性设计 |
| C012 | [UniAV: unified audio-visual perception for multi-task video event localization](https://arxiv.org/abs/2404.03179) | 纳入 S12 | 多模态：统一音视感知做多任务事件定位，模态增益与代价同表 |
| C013 | [Exploring audio-visual information fusion for sound event localization in low-resource regimes](https://arxiv.org/abs/2406.15160) | 纳入 S13 | 多模态：低资源下音视融合的真实增量，非无条件收益 |
| C014 | [Overview of the L3DAS23 challenge on audio-visual extended reality](https://arxiv.org/abs/2402.09245) | 纳入 S14 | 多模态：XR 场景音视任务与榜单口径，采集条件贴近可穿戴 |
| C015 | [STARSS23: audio-visual dataset of spatial recordings of real scenes](https://arxiv.org/abs/2306.09126) | 纳入 S15 | 多模态：真实场景音视空间标注，给事件-方位联合条件 |
| C016 | [Privacy controls for always-listening devices (PhD dissertation)](https://digicoll.lib.berkeley.edu/record/273841/files/EECS-2022-249.pdf) | 纳入 S16 | 合规：常驻聆听的隐私控制设计空间，含拒绝与遗忘机制 |
| C017 | [AudioCLIP: extending CLIP to image, text and audio](https://arxiv.org/abs/2106.13043) | 纳入 S17 | 多模态：音-图-文对齐，开放词表与跨模态检索的前提 |
| C018 | [Investigating users' preferences and expectations for always-listening voice assistants](https://doi.org/10.1145/3369807) | 纳入 S18 | 合规：用户对常驻聆听的期望与拒绝边界（何时算越界） |
| C019 | [Are women really more talkative than men? (Science 2007)](https://repository.arizona.edu/bitstream/10150/623432/1/EAR%20CDPS%20in%20press.pdf) | 纳入 S19 | 常驻约束：日均词量的经典量化，常驻采集存储预算的锚点 |
| C020 | [Minimal-impact audio-based personal archives](https://doi.org/10.1145/1026653.1026659) | 纳入 S20 | 常驻约束：低开销个人音频归档的采集/留存设计 |
| C021 | [Array-aware ambisonics and HRTF encoding for binaural reproduction with wearable arrays](https://doi.org/10.1109/taslpro.2026.3671606) | 排除 | 端侧证据缺：可穿戴阵列编码算法，无模型体积/延迟数字 |
| C022 | [Binaural signal matching with wearable arrays for near-field sources](https://doi.org/10.1109/taslpro.2026.3678167) | 排除 | 常驻约束缺：近场波束成形，无常驻采集与留存证据 |
| C023 | [ToS: team of specialists ensemble for stereo SELD](https://arxiv.org/abs/2601.17611) | 排除 | 指标条件不可比：榜单集成方案，无模型体积与单次延迟 |
| C024 | [SpongeBob: sync-aware harmonious audio-visual generative editing](https://arxiv.org/abs/2605.25193) | 排除 | 多模态不支撑：生成编辑，无识别/增益轴 |
| C025 | [SyncReward: human-aligned synchronization reward for audio-visual generation](https://arxiv.org/abs/2610.16338) | 排除 | 多模态不支撑：生成侧奖励模型，非采集侧证据 |
| C026 | [Sounding highlights: dual-pathway audio encoders for audio-visual highlight detection](https://arxiv.org/abs/2602.03891) | 排除 | 多模态不支撑：视频高光检测，非音频事件识别 |
| C027 | [MMAG: multi-control mixed audio generation benchmark](https://arxiv.org/abs/2608.06900) | 排除 | 多模态不支撑：混合音频生成基准，无识别或增益控制指标 |
| C028 | [MISP-Meeting: real-world dataset with multimodal cues for long-form meeting transcription](https://aclanthology.org/2025.acl-long.753/) | 排除 | 端侧证据缺：固定阵列会议数据，无端侧延迟/功耗账 |
| C029 | [MISP-QEKS: large-scale dataset with multimodal cues for query-by-example](https://doi.org/10.1145/3746027.3758268) | 排除 | 指标条件不可比：查询式检索数据集，与事件/情感/增益指标不同轴 |
| C030 | [Spatial and semantic embedding integration for stereo SELD](https://arxiv.org/abs/2507.04845) | 排除 | 指标条件不可比：定位分数为主，无法与纯音频 AED 指标比较 |
| C031 | [HDA-SELD: hierarchical cross-modal distillation for low-resource SELD](https://arxiv.org/abs/2508.12334) | 排除 | 端侧证据缺：蒸馏提分但无端侧运行时实测 |
| C032 | [DOA-aware audio-visual self-supervised learning for SELD](https://arxiv.org/abs/2410.22803) | 排除 | 多模态不支撑：只报来向误差，无事件识别指标与端侧账 |
| C033 | [Leveraging reverberation and visual depth cues for SELD with distance estimation](https://arxiv.org/abs/2410.22271) | 排除 | 指标条件不可比：距离/混响估计指标，端侧无部署证据 |
| C034 | [Language-guided joint audio-visual editing via one-shot adaptation](https://arxiv.org/abs/2410.07463) | 排除 | 多模态不支撑：生成式编辑任务，不产出事件/情感判别指标 |
| C035 | [SAVGBench: benchmarking spatially aligned audio-video generation](https://arxiv.org/abs/2412.13462) | 排除 | 多模态不支撑：生成基准，与常驻采集/治理无关 |
| C036 | [Enhancing personalized dialogue generation with contrastive latent variables](https://aclanthology.org/2023.acl-long.1/) | 排除 | 合规冲突：人格画像与本仓库红线冲突，且无音频证据 |
| C037 | [Can you put it all together: evaluating conversational agents' ability to blend skills](https://aclanthology.org/2020.acl-main.183/) | 排除 | 常驻约束缺：对话技能混合评测，无音频传感器面 |
| C038 | [Thunder Crystal: crowdsourcing-based content distribution platform](https://doi.org/10.1145/2964284.2973822) | 排除 | 常驻约束缺：CDN 众包分发调度，无音频采集与端侧约束 |
| C039 | [PTS-SNN: prompt-tuned temporal shift spiking networks for efficient SER](https://arxiv.org/abs/2602.08240) | 纳入 S21 | 端侧证据：脉冲网络换取推理能耗，给出能效侧对照 |
| C040 | [Distilled HuBERT for mobile speech emotion recognition](https://arxiv.org/abs/2512.23435) | 纳入 S22 | 端侧证据：跨语料验证的手机端蒸馏 SER，含跨库掉点 |
| C041 | [Real-time emergency vehicle siren detection with efficient CNNs on embedded hardware](https://arxiv.org/abs/2507.01563) | 纳入 S23 | 端侧证据：嵌入式硬件实时检测，含延迟与平台条件 |
| C042 | [DASM: detect any sound (open-vocabulary AED)](https://arxiv.org/abs/2507.16343) | 纳入 S24 | 指标条件：开放词表 AED 的跨数据集口径，非大型档 |
| C043 | [Re-parameterization of lightweight transformer for on-device SER](https://arxiv.org/abs/2411.09339) | 纳入 S25 | 端侧证据：重参数化换端侧延迟，含参数量与推理条件 |
| C044 | [SenseVoice (FunAudioLLM): voice understanding foundation model](https://arxiv.org/abs/2407.04051) | 纳入 S26 | 端侧证据：234M 级、ONNX/sherpa-onnx 是手机端主路径 |
| C045 | [HiCMAE: hierarchical contrastive multimodal model for audio-visual SER](https://arxiv.org/abs/2401.05698) | 纳入 S27 | 多模态：音视情感表征的可比增量，含模态缺失条件 |
| C046 | [emotion2vec: self-supervised pre-training for speech emotion representation](https://aclanthology.org/2024.findings-acl.931/) | 纳入 S28 | 指标条件：自监督情感表征的跨库口径与线性探针协议 |
| C047 | [Dual knowledge distillation for efficient sound event detection](https://arxiv.org/abs/2402.02781) | 纳入 S29 | 端侧证据：双蒸馏压缩 SED，给小型档上限 |
| C048 | [emotion2vec+ large (FunASR 导出)](https://huggingface.co/emotion2vec/emotion2vec_plus_large) | 纳入 S30 | 端侧证据：ONNX/FunASR 可导出，手机端可跑的中型权重 |
| C049 | [EfficientAT-mn04_as (Efficient Audio Transformer, width 0.4)](https://arxiv.org/abs/2211.04772) | 纳入 S31 | 端侧证据：不足 1M 参数 + 蒸馏自 PaSST，小型档下界 |
| C050 | [EAT-base: efficient audio transformer](https://arxiv.org/abs/2306.04186) | 纳入 S32 | 指标条件：高效 Transformer 的 AudioSet 口径与 MACs 条件 |
| C051 | [CED-Base: consistent ensemble distillation for audio tagging](https://arxiv.org/abs/2308.11957) | 纳入 S33 | 指标条件：一致性蒸馏的强基线口径，作中型对照 |
| C052 | [TRILLsson: distilled universal paralinguistic representations](https://www.isca-archive.org/interspeech_2022/shor22_interspeech.html) | 纳入 S34 | 端侧证据：蒸馏到 5M 级表征，可穿戴可用的最小档 |
| C053 | [BEATs iter3+ (audio pre-training with acoustic tokenizers)](https://arxiv.org/abs/2212.09058) | 纳入 S35 | 指标条件：迭代蒸馏强基线的 AudioSet 口径 |
| C054 | [AST: audio spectrogram transformer](https://arxiv.org/abs/2104.01778) | 纳入 S36 | 指标条件：ViT 路线基准锚点，含 patch 与算力条件 |
| C055 | [PaSST-S: efficient training of audio transformers with patchout](https://arxiv.org/abs/2110.05069) | 纳入 S37 | 指标条件：patchout 效率口径，与 AST 同源可比 |
| C056 | [PANNs-CNN14 (large-scale pretrained audio neural networks)](https://arxiv.org/abs/1912.10211) | 纳入 S38 | 指标条件：CNN14 通用基线，含 multi-adds 口径 |
| C057 | [YAMNet (AudioSet MobileNetV1 tagging)](https://github.com/tensorflow/models/tree/master/research/audioset/yamnet) | 纳入 S39 | 端侧证据：TFLite/TFLite Micro 官方导出，小型档事实基准 |
| C058 | [openSMILE ComParE_2016 feature set + linear classifier](https://github.com/audeering/opensmile) | 纳入 S40 | 端侧证据：非神经特征集在 MCU 直跑，零量化成本 |
| C059 | [RealDESED: real-world domestic sound event detection benchmark](https://arxiv.org/abs/2607.16736) | 排除 | 指标条件不可比：新基准无参数量/延迟口径，暂不可横向比较 |
| C060 | [Soroll-IA: weakly labeled audio dataset for industrial port monitoring](https://arxiv.org/abs/2606.26195) | 排除 | 端侧证据缺：工业弱标签集，无模型指标与部署条件 |
| C061 | [Smartphone audio based distress detection](https://arxiv.org/abs/2608.04176) | 排除 | 合规冲突：危机干预用途，缺伦理审查与临床验证 |
| C062 | [EmotionAI: privacy-preserving speech-emotion-grounded conversation pipeline](https://arxiv.org/abs/2606.24941) | 排除 | 端侧证据缺：流水线未给端侧体积/延迟，隐私只作声明 |
| C063 | [From large-scale audio tagging to real-time explainable siren detection](https://arxiv.org/abs/2506.23437) | 排除 | 指标条件不可比：与端侧版同组工作，只保留含硬件实测的一篇 |
| C064 | [Comparison of spectrogram scaling in multi-label music genre recognition](https://arxiv.org/abs/2506.02091) | 排除 | 指标条件不可比：音乐流派识别，非语音情感轴 |
| C065 | [Musical source separation bake-off: objective metrics vs human perception](https://arxiv.org/abs/2507.06917) | 排除 | 指标条件不可比：音乐分离主观/客观对照，与增益控制不同轴 |
| C066 | [Empirical analysis of asynchronous federated learning on heterogeneous devices](https://arxiv.org/abs/2505.07041) | 排除 | 端侧证据缺：联邦异步性分析，无端侧模型体积与功耗 |
| C067 | [HiSSNet: sound event detection and speaker identification via prototypical networks](https://arxiv.org/abs/2303.07538) | 排除 | 指标条件不可比：事件+说话人混合口径，跨任务不可比 |
| C068 | [DESED-FL and URBAN-FL: federated learning datasets for SED](https://arxiv.org/abs/2102.08833) | 排除 | 端侧证据缺：联邦数据集，端侧训练开销未给 |
| C069 | [Channel compression: rethinking information redundancy among channels in CNN](https://arxiv.org/abs/2007.01696) | 排除 | 指标条件不可比：通道压缩的结构实验，无 AudioSet 全量指标与端侧延迟 |
| C070 | [Virufy: COVID-19 detection from cough sounds](https://arxiv.org/abs/2011.13320) | 排除 | 合规冲突：呼吸音诊断属临床器械语境，超出本综述范围 |
| C071 | [VOICe: sound event detection dataset for generalizable domain adaptation](https://arxiv.org/abs/1911.07098) | 排除 | 指标条件不可比：域自适应数据集，无模型算力与端侧部署 |
| C072 | [Audio Flamingo 3](https://github.com/NVIDIA/audio-flamingo) | 纳入 S41 | 指标条件：LALM 事件级基准与幻觉率口径，非 AudioSet 榜 |
| C073 | [Kimi-Audio-7B-Instruct](https://huggingface.co/moonshotai/Kimi-Audio-7B-Instruct) | 纳入 S42 | 指标条件：端到端音频 LLM 的判别口径，与 ASR 榜不可混 |
| C074 | [MiDashengLM-7B](https://arxiv.org/abs/2508.03983) | 纳入 S43 | 指标条件：编码器直连 LLM 的事件判别，注意该数字是片段准确率（非定位口径） |
| C075 | [Qwen2.5-Omni-7B](https://huggingface.co/Qwen/Qwen2.5-Omni-7B) | 纳入 S44 | 多模态：全模态 LLM 的音视融合面，含显存/延迟量级 |
| C076 | [Qwen2-Audio-7B-Instruct](https://arxiv.org/abs/2407.10759) | 纳入 S45 | 指标条件：7B 音频指令模型的 SER/AED 口径，云端量级 |
| C077 | [Dasheng-1.2B (deep audio-signal holistic encoder)](https://github.com/XiaoMi/dasheng) | 纳入 S46 | 指标条件：十亿级编码器挂标签头，大型档下界 |
| C078 | [Miipher-2 (universal speech restoration, million-hour scale)](https://arxiv.org/abs/2505.04457) | 纳入 S47 | 指标条件：生成式复原的上限，非实时、非端侧 |
| C079 | [UNIVERSE++ (generative speech restoration)](https://arxiv.org/abs/2406.12194) | 纳入 S48 | 指标条件：扩散式复原对照，增益相邻（增强）口径 |
| C080 | [AudioSR: versatile audio super-resolution at scale](https://arxiv.org/abs/2309.07314) | 纳入 S49 | 指标条件：带宽扩展的生成式上限，与增益相邻（增强） |
| C081 | [Whisper-AT: noise-robust ASR with audio tagging head](https://github.com/yuangongnd/whisper-at) | 纳入 S50 | 指标条件：ASR 骨干冻结后只加事件头，增量成本可算（非端侧） |
| C082 | [MossFormer2 (speech separation/enhancement, 55.7M)](https://arxiv.org/abs/2312.11825) | 纳入 S51 | 指标条件：中型档参数量-指标对照，非实时路径 |
| C083 | [DeepFilterNet3](https://github.com/Rikorose/DeepFilterNet) | 纳入 S52 | 端侧证据：CPU 上 0.1–0.2 实时因子，增益/降噪同栈 |
| C084 | [GTCRN (grouped temporal convolutional recurrent network)](https://github.com/Xiaobin-Rong/gtcrn) | 纳入 S53 | 端侧证据：48K 参数级，MCU 可用的小型档下限 |
| C085 | [FRCRN (frequency recurrent CRN, DNS challenge)](https://github.com/Audio-Westlake/FRCRN) | 纳入 S54 | 指标条件：10M 级增强的 DNS 榜单口径 |
| C086 | [LAION-CLAP: large-scale contrastive language-audio pretraining](https://arxiv.org/abs/2211.06687) | 纳入 S55 | 多模态：音-文对齐支撑零样本事件，检索式开放词表 |
| C087 | [RNNoise (recurrent neural network noise suppression)](https://arxiv.org/abs/1709.08243) | 纳入 S56 | 端侧证据：85K 参数定点 C，常驻降噪的功耗基准 |
| C088 | [FFmpeg loudnorm filter (EBU R128)](https://ffmpeg.org/ffmpeg-filters.html#loudnorm) | 纳入 S57 | 指标条件：离线响度归一（EBU R128 两遍测量），给统一电平口径 |
| C089 | [WebRTC audio processing AGC2](https://webrtc.googlesource.com/src/+/main/modules/audio_processing/agc2/) | 纳入 S58 | 端侧证据：手机/浏览器实时增益环的工业实现 |
| C090 | [Android AutomaticGainControl (audiofx API)](https://developer.android.com/reference/android/media/audiofx/AutomaticGainControl) | 纳入 S59 | 端侧证据：系统级 AGC 效果器的可控面与不可控边界 |
| C091 | [SpeexDSP AGC (speex_preprocess)](https://github.com/xiph/speexdsp) | 纳入 S60 | 端侧证据：定点 C 轻量增益环，MCU/DSP 可移植 |
| C092 | [Apple Watch Series 12 audio intelligence (Siri Recap)](https://www.iphoneplay.cn/2026/09/10/apple-watch-series-12-audio-intelligence-health/) | 纳入 S61 | 合规：端侧环形缓冲 + 7 天即焚 + opt-in 的克制常开（二手口径） |
| C093 | [EgoLog: ego-centric fine-grained daily log with ubiquitous wearables](https://arxiv.org/abs/2504.02624) | 纳入 S62 | 常驻约束：可穿戴全天日志的采集成本与标注负担 |
| C094 | [DCASE2025 Task 1 baseline (low-complexity acoustic scene classification)](https://github.com/CPJKU/dcase2025_task1_baseline) | 纳入 S63 | 端侧证据：61K 参数 / 128 KiB 预算下的官方基线 |
| C095 | [8.62 µW end-to-end spoken-language-understanding SoC](https://doi.org/10.1109/ISSCC49661.2025.10904788) | 纳入 S64 | 端侧证据：微瓦级端到端语音理解，常驻功耗的物理下界 |
| C096 | [Streaming Sortformer: speaker cache-based online diarization](https://arxiv.org/abs/2507.18446) | 纳入 S65 | 常驻约束：流式说话人日志的在线内存与延迟面 |
| C097 | [EgoADL: multimodal daily-life logging in free-living environments](https://doi.org/10.1145/3643553) | 纳入 S66 | 常驻约束：自由生活多模态日志的真实采集负担与脱敏成本 |
| C098 | [0.4 V 988 nW time-domain audio feature extraction for keyword spotting](https://doi.org/10.1109/ISSCC49657.2024.10454389) | 纳入 S67 | 端侧证据：纳瓦级特征前端，唤醒链路的最省电一环 |
| C099 | [TinyChirp: bird song recognition with TinyML on low-power wireless sensors](https://arxiv.org/abs/2407.21453) | 纳入 S68 | 端侧证据：TinyML 节点长期野外部署，含功耗与回传条件 |
| C100 | [Self-learning for personalized keyword spotting on ultra-low-power audio sensors](https://arxiv.org/abs/2408.12481) | 纳入 S69 | 端侧证据：微瓦级传感器上的自学习唤醒词，含片上预算 |
| C101 | [Rewind / Limitless pendant (cloud always-on recorder)](https://limitless.ai/) | 纳入 S70 | 合规：云常开路线停售停服的信任代价（二手口径） |
| C102 | [Ego-Exo4D: first- and third-person video understanding](https://arxiv.org/abs/2311.18259) | 纳入 S71 | 多模态：第一/第三人称同步采集，标注成本与对齐条件 |
| C103 | [47 nW voice activity detector with short-time CNN features](https://doi.org/10.1109/JSSC.2023.3302791) | 纳入 S72 | 端侧证据：纳瓦级 VAD 芯片，常驻触发的能耗下限 |
| C104 | [Ego4D: around the world in 3,000 hours of egocentric video](https://arxiv.org/abs/2110.07058) | 纳入 S73 | 常驻约束：三千小时级第一视角语料的采集规模与合规流程 |
| C105 | [AAD-KWS: sub-µW keyword spotting chip with acoustic activity detection](https://ieeexplore.ieee.org/document/9888232) | 纳入 S74 | 端侧证据：亚微瓦唤醒 + 活动检测联动，省掉常态推理 |
| C106 | [510 nW wake-up keyword-spotting chip (serial-FFT MFCC)](https://doi.org/10.1109/JSSC.2020.3029097) | 纳入 S75 | 端侧证据：唤醒芯片的纳瓦级功耗实测条件 |
| C107 | [Silero VAD](https://github.com/snakers4/silero-vad) | 纳入 S76 | 端侧证据：ONNX 可达的轻量 VAD，常驻门控的事实标准 |
| C108 | [Sound event detection with binary neural networks on power-constrained IoT](https://arxiv.org/abs/2101.04446) | 纳入 S77 | 端侧证据：二值网络在紧功耗 IoT 上做 SED，含片上预算 |
| C109 | [LeakyPick: IoT audio spy detector](https://arxiv.org/abs/2007.00500) | 纳入 S78 | 合规：常驻麦克风的窃听检测，对抗面证据 |
| C110 | [FSD50K: open dataset of human-labeled sound events](https://arxiv.org/abs/2010.00475) | 纳入 S79 | 指标条件：开放标注事件集的评测口径与许可条件 |
| C111 | [Self-sustaining micro-watt programmable smart audio sensor for always-on](https://ieeexplore.ieee.org/document/8752147) | 纳入 S80 | 端侧证据：自供能微瓦常驻音频传感，能量预算下界 |

读法与边界：

- 「决定」列的 `纳入 Sxx` 是后续唯一可引用编号；排除行不占号，C 号只用于本表定位。
- 文献列一律给出可解析 https 出处（arXiv / DOI / 官方仓库 / 官方文档 / 官方榜单）；二手来源在理由列标「二手口径」。
- 时间窗按 §1.2 执行（2017-01-01 至 2026-10-18）。两条早于窗的锚点保留：日均词量（2007）与个人音频归档（2004），它们给出的数量级至今无替代，且直接决定常驻采集的存储预算。
- 工具/文档类条目（S57–S60、S76）无正式论文年份，年份取「首次公开可用」的近似值：FFmpeg loudnorm 2016、WebRTC AGC 模块 2013、Android audiofx 2010、SpeexDSP 2007、Silero VAD 2021。这些值可能比对应 GitHub/文档页的首个可见提交偏早或偏晚，属口径近似，§10 定稿时逐条回官方 changelog 复核。
- 排除集中在四类：SELD/DOA 定位（指标与 AED 不可比）、音视生成（非判别任务）、音乐与分离（不同轴）、临床与健康（合规超出范围）。

## 4. 单篇卡片

## 5. 叙事大纲

## 6. 溯源核验记录

## 7. 未核实清单
