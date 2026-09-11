# 音频事件识别（AED）与自动增益（AGC）模型全景：端侧 / 多模态 / 大 / 中 / 小

> 调研时间：2026-09-11 ｜ 姊妹篇：[2026-09-11-ser-model-landscape.md](2026-09-11-ser-model-landscape.md)（语音情感）。
> 为 laos 听觉链路的另外两个模型能力做选型地图：**声音事件**（门铃/哭声/警报——Apple S12 Sound Recognition
> 已验证的场景）与**增益/降噪**（录音响度一致性与可懂度）。
> 记法：✅ 官方源已查证 ｜ 🔶 第三方/推算/经典口径 ｜ 参数量为模型卡或论文口径。

---

## 1. 一句话结论（两章合并）

1. **AED 的端侧答案早已收敛**：YAMNet（MobileNetV1，AudioSet 521 类）是 Google AI Edge 官方端侧推荐，
   DCASE Low-Complexity 赛题以十万参数级立规——**laos 的 ADSP 完全放得下**；缺的只是把"事件白名单"
   （哭声/警报/门铃）从 AudioSet 521 类里裁出来。
2. **AGC 的核心认知：它不是"模型"，是 DSP 组件**。业界常驻链路里的自动增益 99% 跑在经典 DSP
   （WebRTC AGC2 / SpeexDSP / ADSP TX-path 固件）；ML 只在两处赢：**轻量降噪**（DTLN/GTCRN，十万参数级）
   与**离线修复**（扩散生成式，分钟级批处理）。laos 若要 ML-AGC，正确位置是 journal 前置批处理，不是常驻。

### §1.1 文献跟踪后的修正（2024–2026 逐篇见 §7/§8）

- **DCASE 约束精确化**：Low-Complexity ASC 硬约束为 **128K 参数 / 30 MMACs**；DCASE 2025 Task 1 冠军
  Karasin_JKU（JKU）61.47% 准确率 @ **122,296 参数 / 29.4 MMACs**——"BEATs/PaSST 教师蒸馏进 <128K 学生"
  已是可复制的工程范式，本文 §2.1/§2.2 的"十万参数级"说法以此为准。
- **CED 数字修正**：balanced 集学生 49.0 mAP（10M）/ CED-3600 教师+30M 学生 ~50.0；此前表中 "~52.2"
  为不同协议口径 🔶——引用时以 [arXiv:2308.11957](https://arxiv.org/abs/2308.11957) 正文为准。
- **GTCRN 数字修正**：仓库实测 **48.2K 参数 / 33.0 MMACs/s**（论文口径 23.7K/39.6），VoiceBank-DEMAND PESQ 2.87。
- **发现一篇"ML 化 AGC"的直接对标论文**：**SE-AGCNet**（Interspeech 2026，[arXiv:2606.25959](https://arxiv.org/abs/2606.25959)）
  端到端联合 SE+响度控制（LUFS 目标）——本文 §3"AGC 主要不是 ML"的判断要加注：**联合优化刚起步，
  恰是 laos journal 管线可复现的 baseline**。
- **家庭看护声音应用已成独立赛道**：哭声检测（BP 可分离卷积边缘方案、因果时序表征+边界标注数据集）、
  辅助居住"隐私防火墙"（先滤人声、留事件）——与 laos ADSP 白名单事件几乎同一命题。

---

## 2. 音频事件识别（AED / Sound Event Detection）

### 2.1 端侧可部署

| 模型 | 参数量 | 类别数 | 部署运行时 | 备注 | 来源 |
|---|---|---|---|---|---|
| **YAMNet** | ~3.7M 🔶（MobileNetV1） | **521**（AudioSet 本体） | **TFLite / MediaPipe（Google AI Edge 官方端侧默认）** | 波形直入，逐帧输出；事实标准 | [TF Hub](https://www.tensorflow.org/hub/tutorials/yamnet) ✅ [AI Edge](https://developers.google.com/edge/mediapipe/solutions/audio/audio_classifier) ✅ |
| DCASE Low-Complexity ASC 参赛模型 | **十万参数级**（赛题以参数量/MACs 立规） | 10 类场景 | MCU 级 | 嵌入式场景分类的规则制定者 | [DCASE 2023 Task1](https://dcase.community/challenge2023/task-low-complexity-acoustic-scene-classification-results) ✅ |
| SenseVoice 内嵌 AED | （234M，与 ASR 同一次推理） | 音乐/ applause/笑声等事件标签 | FunASR / ONNX | **laos 在用**：转写时顺带出事件 | [HF](https://huggingface.co/FunAudioLLM/SenseVoiceSmall) ✅ |

### 2.2 小型（<30M）

| 模型 | 参数量 | 精度锚点 | 备注 |
|---|---|---|---|
| **HTS-AT**（层次 token-语义音频 Transformer） | **~31M** | AudioSet mAP **0.471**（当年超 AST）；ESC-50 97.6+ | 小型档精度之王：层次结构砍掉一半体积 |
| LEAN 等轻量网 | 1–5M | 对标 YAMNet 的移动端 SED | 研究阶段 |
| DCASE 参赛模型 | 0.1–0.5M | 场景分类准确率 ~75-80% 🔶 | 专用场景小而准 |

### 2.3 中型（30–120M，AudioSet 精度主力）

| 模型 | 参数量 | AudioSet mAP | 备注 | 来源 |
|---|---|---|---|---|
| **BEATs / BEATs2**（微软，ICML 2023） | ~90M | **50.6%**（集成，曾 SOTA） | 声学 tokenizer 迭代自监督预训练 | [arXiv:2212.09058](https://arxiv.org/abs/2212.09058) ✅ |
| **CED**（小米，ICASSP 2024） | ~52M 🔶 | **~52.2%**（一致性集成蒸馏，现役单模 SOTA 级） | 大教师集成蒸馏给学生 | [arXiv:2308.11957](https://arxiv.org/abs/2308.11957) ✅ |
| PaSST | ~86M 🔶 | 48.6 单模 / 49.5 集成 | Patchout 降训练成本 | [GitHub](https://github.com/kkoutini/PaSST) ✅ |
| AST | 86M | 48.5 集成 / 45.9 单模 | 第一个纯 Transformer 音频谱基线 | [arXiv:2104.01778](https://arxiv.org/abs/2104.01778) ✅ |
| PANNs CNN14 | ~80M 🔶 | 43.9（经典基线口径） | 仍是迁移学习最常用底座 | 🔶 |

### 2.4 大型（音频 LLM）

Kimi-Audio-7B（**官方任务表含 sound event/scene classification 且宣称 SOTA**，自带评测集；
[GitHub](https://github.com/MoonshotAI/Kimi-Audio) ✅）与 Qwen2.5-Omni（MMAU 音频理解强；
[arXiv:2503.20215](https://arxiv.org/abs/2503.20215) ✅）——与 SER 篇同一对选手、同一个结论：
**零样本事件问答可比专用模型，但只能进批处理档**。闭源（GPT-4o-audio）违反 laos 零云约束，不做对标。

### 2.5 多模态（音+视）

音视事件检测（AVVP 任务：画面与声音的时间对齐检测）、CLAP/AudioCLIP（音-文对齐零样本标记）、
WavCaps（音文自监督）。**laos 无摄像头，整档明确不做**——记录 SOTA 边界即可（与 SER 篇 HumanOmni 同立场）。

---

## 3. 自动增益控制（AGC）与语音增强

> 方法论警告：**"自动增益模型"在业界主要不是 ML 模型**。常驻链路的增益控制是经典 DSP 反馈环
> （峰值/RMS 检测 → 压缩器/限幅器），ML 的价值在**降噪+可懂度**（增益的"感知配套"）与**离线修复**。

### 3.1 端侧（经典 DSP，业界主流）

| 组件 | 形态 | 部署位置 | 备注 |
|---|---|---|---|
| **WebRTC AudioProcessing AGC1/AGC2** | 自适应数字增益（含语音似然门控） | VoIP 客户端标配（Chrome/Teams 等） | C 库；AGC2 是当前主流实现 🔶 |
| **SpeexDSP AGC** | 经典 RMS-AGC | 嵌入式/跨平台 | BSD 许可；always-on 调研篇已列为"高可复用" |
| Android/高通 **ADSP TX-path** | 固件级增益/降噪/限幅 | 骁龙 aDSP（laos 真机同款通路） | 录音路径硬件级处理 🔶 |
| Opus 内建分析 | 编码器前置 VAD/VBR 增益联动 | laos 存储链路（若启用 Opus） | 编码即处理 |
| 纯 Python RMS-AGC | ~20 行（帧 RMS → 目标电平映射 + 限幅） | laos 主进程 | **零依赖哲学同款**；对 journal 离线归一已够用 |

### 3.2 小型 ML（<1M，实时降噪=感知增益）

| 模型 | 参数量 | 指标 | 备注 | 来源 |
|---|---|---|---|---|
| **GTCRN** | **23.7K** / 39.6 MMACs | PESQ 2.87（VCTK-DEMAND） | 极限轻量；MCU 级实时 | [论文](https://sigport.org/sites/all/modules/pubdlcnt/pubdlcnt.php?fid=9363) ✅ |
| **DTLN**（DNS Challenge 2020 实时赛冠军） | **~243K** | 实时全带；双级 stateful LSTM | ONNX 量化成熟，边缘部署事实标准之一 | 🔶 |
| RNNoise（Xiph） | ~0.1M 级 🔶（GRU） | 经典基线；视频会议实测弱于 DFN3 | C 实现、毫秒级 | [对比研究](https://www.researchgate.net/publication/392780104) 🔶 |

### 3.3 中型 ML（1–30M）

| 模型 | 参数量 | 备注 | 来源 |
|---|---|---|---|
| **DeepFilterNet2/3** | 百万级 🔶（深滤波双级分解） | **48kHz 全带**；视频会议实测综合最优（ intelligibility+质量） | [GitHub](https://github.com/rikorose/deepfilternet) ✅ [实测](https://www.researchgate.net/publication/392780104) 🔶 |
| DCCRN / FRCRN / MossFormer（含 laos drv_audio 用的 FunASR 增强模型） | ~3–20M 🔶 | laos **已在用**：separate/AEC 通道（.venv-audio，FunASR 生态） | [ClearerVoice 生态](https://github.com/modelscope/ClearerVoice-Studio) 🔶 |
| DPDFNet（2025/2026 新） | 双路径 RNN 增强 DFN2 | 边缘 NPU 实时验证 | [arXiv:2512.16420](https://arxiv.org/html/2512.16420v2) ✅ |

### 3.4 大型（生成式修复，非实时）

score-based 扩散的**通用语音修复**：UNIVERSE（[项目页](https://serrjoa.github.io/projects/universe/) ✅）、
StoRM/SGMSE+ 🔶、Google Miipher（训练级 restoration，纯实验室口径 🔶）。共同点：**分钟级批处理、非因果**，
只适合"离线修复珍贵录音"，与 laos 常驻链路无交集——**明确不用**。

### 3.5 多模态（音+视 AGC/增强）

AVSE（唇动引导增强）：扩散式无监督 AVSE（[arXiv:2410.05301](https://arxiv.org/abs/2410.05301) ✅）、
**AVSEC 挑战赛**（COG-MHEAR 第 4 届，2025，[GitHub](https://github.com/cogmhear/avsec_challenge) ✅）、
AV2Wav（重合成式）。依赖摄像头——**laos 明确不做**（隐私红线）。

---

## 4. 对 laos 的选型映射

| laos 场景 | 现状 | 建议 | 理由 |
|---|---|---|---|
| 声音事件常驻检测（ADSP 档） | TIM-Net 只管情绪 | **裁剪版 YAMNet / DCASE 级小模型**做白名单事件（哭声/警报/门铃/玻璃破碎），事件不落音频只出标签 → `/events` → `drv_events` | Apple S12 Sound Recognition 已验证该场景价值；YAMNet TFLite 生态成熟；对应"环境理解"入口（always-on 调研 §9.3 缺口 2） |
| 事件标签（journal 档） | SenseVoice 内嵌 AED ✅ | **维持** | 转写+情感+事件一次推理，不重复造 |
| 录音响度归一（journal 前置） | 无 | **先做纯 Python RMS-AGC（~20 行）**；不够再上 DTLN ONNX 可选通道 | 零依赖哲学同款；批处理档跑 ML 无功耗压力 |
| 常驻实时降噪 | 无（ADSP 固件已有 TX-path） | **不做**——ADSP 固件已覆盖；应用层再叠 ML 是双倍功耗 | 收益只剩"再降 3dB 底噪"，不值 5mW 预算 |
| 离线修复/多模态增强 | 无 | **明确不做**（UNIVERSE/AVSE 与常驻场景无交集） | 非因果 + 摄像头依赖 |

**优先级**：声音事件白名单（ADSP）> RMS-AGC 归一（journal）> 其余不做。前者直接补上 always-on
调研点名的"环境理解"缺口，且把 App 的 `/events` 通路从"只报情绪"升级为"报世界状态"。

## 5. 可选落地项（如需执行另行确认）

1. **`laos/events.py` 白名单事件分类器**：YAMNet 类模型蒸馏/裁剪出 N 类（哭声/警报/门铃/掌声/音乐），
   纯 Python 推理或 ONNX 可选依赖；`drv_events` 增加本地事件源（现在只有真机事件流）
2. **`bin/journal.py` 前置响度归一**：`normalize_loudness(wav_bytes, target_dbfs=-20)` 纯 Python 实现，
   落盘前批处理（与即焚 GC 同一循环）
3. **App 侧调研项**：Qualcomm ADSP 是否暴露通用 SED 空位（TIM-Net 之外的第二个 LPAI 岛）——真机实验

## 6. 参考来源

[YAMNet（TF Hub）](https://www.tensorflow.org/hub/tutorials/yamnet) ｜
[Google AI Edge 音频分类](https://developers.google.com/edge/mediapipe/solutions/audio/audio_classifier) ｜
[DCASE 2023 Low-Complexity ASC](https://dcase.community/challenge2023/task-low-complexity-acoustic-scene-classification-results) ｜
[BEATs (arXiv:2212.09058)](https://arxiv.org/abs/2212.09058) ｜
[CED (arXiv:2308.11957)](https://arxiv.org/abs/2308.11957) ｜
[AST (arXiv:2104.01778)](https://arxiv.org/abs/2104.01778) ｜
[HTS-AT (arXiv:2202.00874)](https://ar5iv.labs.arxiv.org/html/2202.00874) ｜
[Kimi-Audio](https://github.com/MoonshotAI/Kimi-Audio) ｜
[GTCRN](https://sigport.org/sites/all/modules/pubdlcnt/pubdlcnt.php?fid=9363) ｜
[DeepFilterNet](https://github.com/rikorose/deepfilternet) ｜
[UNIVERSE](https://serrjoa.github.io/projects/universe/) ｜
[AVSEC 挑战赛](https://github.com/cogmhear/avsec_challenge) ｜
[扩散 AVSE (arXiv:2410.05301)](https://arxiv.org/abs/2410.05301)

---

## 7. 文献跟踪：音频事件识别（2024–2026，逐篇）

> 由文献调研子代理于 2026-09-11 执行；🔶 = 未在官方源逐字核实。

### 7.1 DCASE 挑战赛（竞赛方案与约束）

- **DCASE 2025 Task 1（Low-Complexity ASC with Device Information）冠军 Karasin_JKU（JKU Linz）**[结果页](https://dcase.community/challenge2025/task-low-complexity-acoustic-scene-classification-with-device-information-results)
  CP-Mobile 骨干 + CP-ResNet/BEATs/PaSST 教师集成蒸馏 + 逐设备微调；**61.47% 准确率 @ 122,296 参数 / 29.4 MMACs**（约束 ≈128K 参数/30 MMACs）；第 2 名 NTU 仅 10.9 MMACs 达 59.94%。→ ADSP 白名单事件检测的现实起点。
- **DCASE 2024 Task 1（Data-Efficient）任务综述**（Schmid/Tyagi 等，CPJKU）[arXiv:2405.10018](https://arxiv.org/abs/2405.10018)
  128K 参数/30 MMACs 硬约束 + 每类数十条标签的数据效率设定；最优系统 85.2%；CP-Mobile 成官方 baseline。
- **DCASE 2024 Task 4（SED with Heterogeneous Training）冠军 Schmid（CPJKU）**（综述 [arXiv:2406.08056](https://arxiv.org/abs/2406.08056)；[结果页](https://dcase.community/challenge2024/task-sound-event-detection-with-heterogeneous-training-dataset-and-potentially-missing-labels-results)）
  弱标签+合成音景；冠军 15 个 ATST/BEATs/PaSST 子系统集成：DESED eval **PSDS 0.680**（baseline 0.475）、MAESTRO mpAUC 0.739、ranking 1.42；单模型第一同为 CPJKU（0.646）。→ DESED 家用事件（炊具/吸尘器/开关）与哭声警报同域，弱标签+合成增强可直接迁移到白名单训练。
- **DCASE 2025 Task 2（First-Shot Unsupervised ASD）前名次 NU Systems**（综述 [arXiv:2506.10097](https://arxiv.org/abs/2506.10097)；[技术报告](https://dcase.community/documents/challenge2025/technical_reports/DCASE2025_Fujimura_73_t2.pdf)）
  "新机器类型零调参"首瞄异常检测；官方 harmonic-mean AUC 63.25%。→ "白名单外异常即上报 Agent"的门控设计参考。
- **DCASE 2025 Task 5（Multi-Domain Audio QA，IIT Madras+Cisco）**（综述 [arXiv:2505.07365](https://arxiv.org/abs/2505.07365)）
  SED 升级为音频问答；顶级系统用 Qwen2-Audio-R1（dev 78.18%）🔶 冠军队名未核实。→ "大模型理解+小模型触发"分工确立。

### 7.2 AudioSet 榜单与 SED 新架构

- **CED**（小米，ICASSP 2024）[arXiv:2308.11957](https://arxiv.org/abs/2308.11957)：10M 学生 **49.0 mAP**（balanced）；CED-3600 教师联合 30M 学生 ~50.0。→ AudioSet 全类检测即使 SOTA 蒸馏也要 10–30M 参数，**无法直接进 ADSP，必须缩白名单**。
- **EAT**（IJCAI 2024）[arXiv:2401.03497](https://arxiv.org/abs/2401.03497)：bootstrap 自监督+双迭代掩码+utterance-frame 联合目标；AS-2M 上报 mAP 0.861（协议与 balanced 榜不同）。→ 适合当云端教师。
- **Dual Knowledge Distillation for Efficient SED**（Xiao 等；IEEE/ACM TASLP 2024）[arXiv:2402.02781](https://arxiv.org/abs/2402.02781)
  同期+异期双教师蒸馏进轻量 CRNN，DESED 上以小模型接近大模型 PSDS。→ 与 DCASE 冠军同源的端侧化路径。
- **Detect Any Sound: Open-Vocabulary SED**（2025）[arXiv:2507.16343](https://arxiv.org/abs/2507.16343)
  文本/视觉多模态查询的开放词表 SED。→ 长期方向：用户口头新增监听类别、无需重训端侧模型。
- **Towards Open World SED**（2026）[arXiv:2605.03934](https://arxiv.org/abs/2605.03934) 🔶：1D 可变形卷积处理时序形变。→ 未知事件不崩溃是警报类产品底线。

### 7.3 端侧轻量化与零样本

- **Lightweight ASC via Contrastive Fine-Tuning + Distillation**（JKU 系，2025）[arXiv:2510.03728](https://arxiv.org/abs/2510.03728)：对比微调教师 + CRD 蒸馏进 CP-Mobile 126K 学生——现成"BEATs→126K 端侧"开源管线，可改成哭声/警报头。
- **WavCaps**（Surrey；IEEE JBHI 2024）[arXiv:2303.17395](https://arxiv.org/abs/2303.17395)：40 万条 ChatGPT 辅助清洗音频-文本对训练 CLAP；零样本 ESC-50 94.8%。→ 云端白名单挖掘，端侧仍用小模型。
- **PAT: Parameter-Free Audio-Text Aligner**（NAACL 2025）[PDF](https://aclanthology.org/2025.naacl-long.616.pdf)：训练无关对齐提升零样本分类。→ 不改模型即可改白名单语义描述。

### 7.4 家庭/看护场景（laos 同域）

- **Infant Cry Detection（BP 可分离卷积 + TF-RNN）**（Yu & Li，2025）[arXiv:2508.19308](https://arxiv.org/abs/2508.19308)：明确面向 baby monitor 边缘设备的轻量哭声检测。→ 与"ADSP 跑哭声白名单"同一命题的架构模板。
- **Infant Cry Detection via Causal Temporal Representation**（Fu 等，2025）[arXiv:2503.06247](https://arxiv.org/abs/2503.06247)：因果时序表征 + **带精确哭声边界的标注数据集**。→ 边界级标注决定"哭声→唤醒 Agent"的触发时机。
- **A Privacy Firewall for Acoustic Sensing in Assisted Living**（2026）[arXiv:2609.02376](https://arxiv.org/abs/2609.02376) 🔶：U-Net 纯合成数据训练，环境音中剥离语音、仅保留事件声。→ 常驻麦克风合规关键：先"滤人声、留事件"再检测/上报。

### 7.5 趋势与未解问题

**趋势**：① 竞赛全面转向"低复杂度+教师蒸馏"（128K/30MMACs 约束连续两届，冠军全是 BEATs/PaSST→CP-Mobile 蒸馏）；② AudioSet tagging 进入蒸馏平台期（49–53 mAP），重心转向开放词表 SED 与音频问答，"大模型理解、小模型触发"分工确立；③ 家庭看护论文普遍叠加轻量化+边界标注+语音剥离防火墙——合规与功耗约束正在塑造架构本身。

**未解**：① 白名单小模型在真实家庭噪声下的 per-hour 虚警率无公开基准（DCASE PSDS ≠ 产品指标）；② 蒸馏能否把 10–30 类白名单压到 <1 MMACs（MCU 级）无系统结论（冠军停在 ~29 MMACs）；③ 零样本 CLAP 与端侧 hard decision 之间的置信度校准/仲裁无标准做法。

### 7.6 检索记录（子代理实查）

命中：DCASE 2024/2025 Task1 结果页与 2405.10018；Task4 综述 2406.08056 + 结果页；Task2 2506.10097 + 技术报告；Task5 2505.07365；CED 2308.11957；EAT 2401.03497；TASLP 双蒸馏 2402.02781；Detect Any Sound 2507.16343；JKU 2510.03728；WavCaps 2303.17395；PAT；哭声两篇 2508.19308/2503.06247；隐私防火墙 2609.02376 🔶。未命中：DCASE 2026 官方页（未被索引）、"ATLA"（判定不存在）、QDALN。

---

## 8. 文献跟踪：AGC / 语音增强（2024–2026，逐篇）

### 8.1 竞赛与个人化降噪

- **ICASSP 2023 DNS Challenge 第 5 届**（Dubey/Cutler 等，Microsoft）[arXiv:2303.11510](https://arxiv.org/abs/2303.11510)：降噪+去混响+**个人化**（enrollment 目标说话人）双赛道；个人化/非个人化冠军盲测分 +0.145/+0.141。→ "enrollment + 说话人保真"范式可迁移到 journal 管线。
- **ICASSP 2024 Speech Signal Improvement Challenge**（Ristea/Dubey/Cutler 等）[IEEE 报告](https://ieeexplore.ieee.org/iel8/8782710/10834412/10830509.pdf)：DNS 升级为全链路信号质量改进，首次真实测试集；DNSMOS+词准确率综合排名。→ 评测趋势从"降噪量"转向"质量+可懂度"。
- **Intel N-DNS Challenge**（Timcheck 等，Intel Labs）[arXiv:2303.09503](https://arxiv.org/abs/2303.09503)：Loihi 2 神经形态硬件上数量级更低功耗的降噪。🔶 检索中"Intel NDN 2024/2025"（ICASSP 版）不存在可核实结果页。→ 与 laos ADSP 固件级功耗约束同构。
- **ICASSP 2024 AEC Challenge 冠军**（Seidel/Mowlaee/Fingscheidt，TUM）[arXiv:2404.11621](https://arxiv.org/abs/2404.11621)：线性 AEC + bark 尺度 NN 后滤波；**约 DeepVQE-S 10% 计算量**达到可比质量。→ 常驻链路若叠 AEC，小 bark 域后滤波性价比最高。
- **DiffVQE**（2026）[arXiv:2605.08189](https://arxiv.org/abs/2605.08189)：首个可复现扩散式 AEC，超 DeepVQE 🔶（增量值需读全文）。→ 生成式正吃掉传统 DSP 领地，但仍是重算力档。

### 8.2 轻量实时 SE

- **GTCRN**（Rong 等，清华；ICASSP 2024）[GitHub](https://github.com/Xiaobin-Rong/gtcrn)：论文口径 23.7K 参数/39.6 MMACs，**仓库修正 48.2K 参数/33.0 MMACs/s**；VoiceBank-DEMAND PESQ 2.87。→ **33 MMACs/s 是 MCU/ADSP 可常驻的现实预算上界**。
- **DPDFNet**（2025，期刊版 Speech Communication 2026）[arXiv:2512.16420](https://arxiv.org/abs/2512.16420)：DFN2 ERB 编码器嵌双路径块，因果实时降噪超 DFN2/DFN3；**ONNX 已被 sherpa 收录**（[文档](https://k2-fsa.github.io/sherpa/onnx/speech-enhancement/dpdfnet.html)）。→ journal 离线降噪的最快落地选项。
- **TSDT-Net**（Interspeech 2025）[ISCA](https://www.isca-archive.org/interspeech_2025/gao25_interspeech.pdf)：超低复杂度两阶段双分支 SE 🔶（指标未核实）。→ 低复杂度 SE 每年有新 SOTA，选型需年检。

### 8.3 生成式修复 / 带宽扩展

- **UNIVERSE++**（Scheibler 等，Mercari；Interspeech 2024）[arXiv:2406.12194](https://arxiv.org/abs/2406.12194)：55 类失真统一处理 + 内容保持（修复 UNIVERSE 幻觉）。
- **Miipher-2**（Google，2025）[arXiv:2505.04457](https://arxiv.org/abs/2505.04457)：conditioning-free 通用修复，面向百万小时级语料清洗；组件用 3,195h/1,642 说话人训练。→ laos 若积累大规模自有录音的离线修复模板。
- **FlowSE**（2025）[arXiv:2508.06840](https://arxiv.org/abs/2508.06840)（另有单遍直通版 [arXiv:2505.19476](https://arxiv.org/abs/2505.19476)）：流匹配替代扩散做生成式 SE，推理步数显著降低；后继 Shortcut FM（2509.21522）/FlowSE-GRPO（2601.16483）。→ journal 离线生成式修复选 FM 系，不选扩散系。
- **URGENT Challenge 2025**（Saijo 等）[arXiv:2505.23212](https://arxiv.org/abs/2505.23212)、[官网](https://urgent-challenge.github.io/urgent2025/)：7 类失真（噪声/混响/削波/**带宽受限**/丢包/编解码）统一评测；2024 冠军 Multistage USE（MOS 3.52）。→ journal 响度归一+降噪管线的任务超集与**内部评测蓝图**。
- **语音带宽扩展（SpeechSR）**[arXiv:2401.06387](https://arxiv.org/abs/2401.06387)，综述 [arXiv:2605.16681](https://arxiv.org/abs/2605.16681)、流式轻量版 StreamWSR [arXiv:2609.03381](https://arxiv.org/abs/2609.03381) 🔶：8k→宽带修复是低成本高感知收益项。

### 8.4 ML 化 AGC 与 TASLP 期刊

- **SE-AGCNet**（Zhang/Rao/Zhong/Chng；Interspeech 2026）[arXiv:2606.25959](https://arxiv.org/abs/2606.25959)
  **检索到的最直接"AGC ML 化"工作**：端到端联合 SE+响度控制，指出"先 AGC 后 SE 会放大噪声、先 SE 后 AGC 会过度压制小声语音"；提出 LUFS/短时 LUFS/LRA 响度指标 + SE-AGC-DataGen 仿真管线。→ **几乎是为 laos"常驻录音 + journal 响度归一"定制的论文，建议作为 baseline 复现**。
- **Lightweight SE via Learnable Prior**（IEEE/ACM TASLP vol.32, 2024）[DOI](https://doi.org/10.1109/TASLP.2024.3417347)：期刊级轻量 SE 候选 🔶。
- **SGMSE+ 期刊版**（TASLP 2023）[DOI](https://doi.org/10.1109/TASLP.2023.3285241)：扩散 SE 的期刊基线，离线档可引。

### 8.5 SE 对 ASR 鲁棒性（journal 管线必读）

- **Reducing the Gap between SE and ASR via Real-Speech-Trained Bridging Module**（2025）[arXiv:2501.02452](https://arxiv.org/abs/2501.02452)：预训练 SE 前端与 ASR 后端失配常导致 WER 不降反升；真实噪声语音训练桥接模块后不再劣化。→ **journal"先增强再喂 ASR"必须做 WER 回归实测**。
- **Polar Projection Diagnosis**（2026）[arXiv:2607.11157](https://arxiv.org/abs/2607.11157)：把 SE 误差分解为干扰/噪声/伪影三成分，证明感知质量提升不必然降低 WER；反例 SAM-Audio 预处理一致劣化 Whisper WER（[arXiv:2603.04710](https://arxiv.org/abs/2603.04710)）。→ "指标好看但下游变差"的诊断框架。

### 8.6 趋势与未解问题

**趋势**：① 轻量实时 SE 算力锚点下沉到 ~50K 参数/33 MMACs（GTCRN 立基线、DPDFNet 进 sherpa、RNNoise 上 STM32/Pico2）；② 生成式修复从扩散转向流匹配且评测统一化（UNIVERSE++/Miipher-2 立目标、FlowSE 压成本、URGENT 统一 7 类失真）；③ **"感知质量 ≠ 下游可用性"成共识，AGC 的 ML 化刚起步**——SE+AGC 联合优化（SE-AGCNet）正是差异化机会窗口。

**未解**：① SE+AGC 联合优化无公开 benchmark、无与 ITU-R BS.1770 对齐的评价协议（LUFS 稳定性/增益抽动伪影/音质权衡无公认指标）；② ICASSP 2025 第 6 届 AEC Challenge 官方总结与冠军论文检索不到 🔶；③ 生成式 SE 蒸馏（FINALLY, NeurIPS 2024）能否压到 <5ms 助听级延迟未被证明。

### 8.7 检索记录（子代理实查）

命中：DNS5 2303.11510；SSI 2024 IEEE 报告；Intel N-DNS 2303.09503；AEC 2024 冠军 2404.11621；DiffVQE 2605.08189；GTCRN GitHub+DOI；DPDFNet 2512.16420 + sherpa 文档；TSDT-Net ISCA；UNIVERSE++ 2406.12194；Miipher-2 2505.04457；FlowSE 2508.06840/2505.19476；URGENT 2505.23212 + 冠军 le25b；SpeechSR 2401.06387/2605.16681/2609.03381；SE-AGCNet 2606.25959（fetch 核实）；TASLP 3417347/3285241；桥接模块 2501.02452；极坐标诊断 2607.11157；ESP32/STM32 部署案例。未命中：ICASSP 2025 AEC Challenge 官方报告、"Intel NDN 2024/2025"赛道。
