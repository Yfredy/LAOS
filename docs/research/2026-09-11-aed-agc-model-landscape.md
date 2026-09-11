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
