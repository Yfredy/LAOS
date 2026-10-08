# 自动增益 —— 经典 DSP 档

> 口径来源：`docs/research/auto-gain/00-taxonomy-and-metrics.md`（作用点 / 控制对象 / 12 列 schema / 编号化自测口径，均以该文件为准）。
> 本文件定位：AGC 的**实际主力形态**（反馈环与测量算法，`参数量(M)` 一律 `n/a(非神经)`），
> 并回答 **`00` 文件红线一"二次增益"**——这个问题决定后续所有 AGC Task 的走向。
> 本文件只做检索、核实与判定，**不做落地推荐**（推荐在 `07-adoption.md`）。

---

## Part 0 · 二次增益：本文件的判定点

**结论（三选一，不许含糊）：不确定 —— 需真机验证。**

补充一句不许被略读的话：**laos 现状（proot Ubuntu 经 Termux）连"选择 AudioSource"的能力都没有，
因此在实际可走的路径上等价于"无法绕过"；"可绕过"只在走出 proot、做成原生 App 之后才成立。**

### 0.1 三层检索与证据链

**(a) Android AudioSource / HAL 是否默认施加 AGC —— 框架不默认挂，是否挂由厂商配置文件决定**

| 层 | 证据（逐字） | 出处 |
|---|---|---|
| SDK 常量语义 | `VOICE_COMMUNICATION`：**"Microphone audio source tuned for voice communications such as VoIP. It will for instance take advantage of echo cancellation or automatic gain control if available."** | AOSP `platform/frameworks/base`，`media/java/android/media/MediaRecorder.java`（main 分支，`AudioSource` 内部类）。经 AOSP 官方 GitHub 镜像核对 |
| 框架默认来源 | **"针对各个 AudioSource 实例请求的默认预处理效果在 /vendor/etc/audio_effects.xml 文件中指定"** | AOSP 官方《配置预处理效果》（页面末次更新 2026-09-15） |
| 强制项边界 | **"AudioSource 调谐对音频增益或音频处理没有明确的要求，但语音识别（VOICE_RECOGNITION）除外"**；VOICE_RECOGNITION 的要求含 **"效果 / 预处理默认处于停用状态"** | 同上 |
| 官方示例挂法 | 官方 XML 示例把 `agc` 挂在 **camcorder**，`voice_communication` 只挂 `aec` + `ns`；`MIC` / `DEFAULT` 在示例里不挂任何效果 | 同上 |
| CDD 口径 | **"当使用 VOICE_COMMUNICATION 进行捕获时，实现应在捕获路径上提供回声消除器（AEC）"** —— 只强制 AEC，**没有对 AGC 的强制要求** | 同上（"Android 10 版本存在下列要求"） |

读法：**AOSP 框架本身既不默认开启也不禁止 AGC**，它做的是"按 AudioSource 请求、由厂商在 vendor 分区声明"。
所以"Android 是否默认施加 AGC"这个问题的诚实答案只能是"**取决于该机型的 /vendor/etc/audio_effects.xml 与 HAL/ADSP 固件，且厂商没有义务公开它**"。
`VOICE_COMMUNICATION` 是 AGC 最常见的挂载点（javadoc 明写），而 `MIC` —— **laos 实际在用的那一档** ——
在 AOSP 示例里不挂效果，但示例不等于真机：厂商完全可以在自己的 XML 里给 `MIC` 挂 `agc`。

**(b) 走 `UNPROCESSED` 能否绕过 —— 只能在"设备声明支持"时绕过，且 laos 现在走不到**

| 项 | 证据（逐字） | 出处 |
|---|---|---|
| 常量语义 | `UNPROCESSED`：**"Microphone audio source tuned for unprocessed (raw) sound if available, behaves like DEFAULT otherwise."** | `MediaRecorder.java`（同 (a)） |
| 能力查询 | `AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED`：**"Used as a key for getProperty to determine if the unprocessed audio source is available and supported with the expected frequency range and level response."** | AOSP `platform/frameworks/base`，`media/java/android/media/AudioManager.java` |
| 回退语义 | 不支持时 **"behaves like DEFAULT otherwise"** —— 即退回默认源，而不是报错 | 同上 |

读法：**"if available" + "behaves like DEFAULT otherwise" 是源码级写死的兜底**。
`UNPROCESSED` 是"尽力而为"的语义，不是保证。它绕的是**框架/HAL 层的预处理**，
**绕不过 ADC 之后、ADSP 固件内的模拟增益/限幅**——那一段没有任何 SDK 开关。

**(c) proot Ubuntu 经 Termux 录音走哪条路径 —— 两条路，都从 Android AudioSource 层进入**

| 路径 | 实际链路 | 证据 |
|---|---|---|
| `termux-microphone-record`（Termux:API） | Android `MediaRecorder` → **源码默认 `AudioSource.MIC`**：`int source = intent.getIntExtra("source", MediaRecorder.AudioSource.MIC);` 只能整段启停，拿不到流 | `termux/termux-api`，`app/src/main/java/com/termux/api/apis/MicRecorderAPI.java`（master 分支）。CLI 是否把 `source` extra 暴露成参数，本次**未核实** |
| PulseAudio `module-sles-source` + TCP 转发 | proot 内 PA → OpenSL ES → Android 采集栈（同样落在某个 AudioSource 路由上） | 本仓库既有结论：`docs/research/always-on-recording/hardware-power.md` §"Termux / proot（laos 现状）"，引用 termux-app issue #2871 与 PA+proot 实操文章 |
| sounddevice / ALSA | **不可用**：Android 无内核 ALSA，root 才有 | 同上 |

读法：**无论哪条路，PCM 都是从 Android 的 AudioSource 层出来的，proot 里没有任何一层能越过它。**
并且 Termux:API 的默认源恰好是 `MIC`——正是"框架示例里不挂效果、但厂商可以挂"的那一档，也是二次增益风险最不透明的一档。

### 0.2 为什么必须判"不确定"，而不是判"已过 AGC"或"可绕过"

- 判"已过 AGC"缺证据：AOSP 示例与 CDD 都没有给 `MIC` 挂 AGC，官方示例甚至把 `agc` 挂在 camcorder；
  说"链路一定已过 AGC"是把厂商行为当成框架保证。
- 判"可绕过"缺证据：`UNPROCESSED` 有 "if available" 兜底，且 laos 现状走不到它；
  把"有个 API"写成"能绕过"会把 `07-adoption.md` 引到错误结论上。
- 所以：**不确定，且给出验证方法**。

### 0.3 真机验证方法（写出可执行的判据）

1. **线性度测试**：用外放/信号源对同一台真机灌入 1 kHz 正弦或粉噪，四档已知电平
   **-50 / -40 / -30 / -20 dBFS**，每档 10 s，同一路径录制（分别用 `MIC`、`UNPROCESSED`、
   `VOICE_COMMUNICATION` 三路同一激励各录一遍）。
2. **判据**：以 `laos.loudness` 或 libebur128 测各档输出积分响度。
   - 输入每 +10 dB、输出增量落在 **10 ± 1 dB** → **线性，该路径未施加增益控制**；
   - 输出增量 **≤ 8 dB**（出现压缩/平台化）→ **存在 AGC/压缩器**；
   - 高电平档出现真峰值被压在固定上限（如 -1 dBTP）→ **存在限幅器**。
3. **静默段行为**：`-55 dBFS` 稳态粉噪 20 s（自测口径 3 的输入条件），看输出是否被抬到 > -34 LUFS；
   被抬起说明存在"低电平自动提升"，这是二次增益最典型的泵浦源。
4. **三路对比**：若 `UNPROCESSED` 档的线性度明显好于 `MIC` 档，说明 `MIC` 档确实挂了处理，
   此时"可绕过"成立（条件：设备 `PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED` 非空）。
5. **代价记录**：即使可绕过，`UNPROCESSED` 通常伴随**增益更低、噪声底更高**（没有前端放大），
   且部分机型会退回 `DEFAULT`——把这两条写进 `07-adoption.md` 的代价栏。

### 0.4 对后续 Task 的含义

- **Task 16（落地）**：在本结论被真机验证推翻之前，
  **任何"采集后"闭环增益条目都不得作为落地推荐**（`00` 红线一）。
  可备选的形态只有"**采集后只做一次性响度归一（离线、开环、不闭环）**"——
  开环归一不会与固件环互相追逐，因为它的增益由整段测量结果决定，不随时间回调。
- **Task 10（小型神经网络）**：若验证发现链路已过 AGC，神经 AGC 同样落在"采集后"，
  一样是二次增益，不因"它是神经网络"而豁免。
- **Task 13（端侧轴）**：`UNPROCESSED` 与 AudioSource 选择权**只在原生 App 层存在**，
  这又一次指向"必须走出 proot"（与 `hardware-power.md` 的结论同向）。

---

## Part 1 · 数据表

| 模型 | 版本/形态 | 参数量(M) | 输入 | 控制对象 | 作用点 | 基准 | 指标 | 许可 | 可得 | edge | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WebRTC AudioProcessing AGC2（GainController2） | 经典 DSP（模拟段 + 自适应数字段 + 限幅器） | n/a(非神经) | 48kHz/10ms/单通道（内部 RNN VAD 重采样至 12kHz、42 维特征） | 模拟增益、数字增益 | 采集前、采集后 | 自测(no public benchmark) | 增益变化率上限 3.0 dB/s、数字增益上限 30 dB、headroom 1 dB、噪声门 -50 dBFS、VAD 置信阈值 0.9（源码常量，收敛时间未实测） (自测口径 1) | BSD-3-Clause | yes | yes: 任意 CPU（C/C++ 实现，无第三方依赖） | github.com/webrtc-uwp/webrtc（WebRTC 源码 GitHub 镜像；上游 webrtc.googlesource.com） |
| WebRTC AudioProcessing AGC1（GainController1，legacy） | 经典 DSP（模拟处方 + 数字压缩级） | n/a(非神经) | 48kHz/10ms/单通道（模拟模式需耦合 OS 混音器电平） | 模拟增益、数字增益 | 采集前、采集后 | 自测(no public benchmark) | 默认目标峰值 -3 dBFS、压缩增益上限 9 dB、限幅默认开、模拟电平范围 0–255（源码默认值，收敛时间未实测） (自测口径 1) | BSD-3-Clause | yes | yes: 任意 CPU（C/C++ 实现） | github.com/webrtc-uwp/webrtc（同上） |
| SpeexDSP AGC（speex_preprocess 内） | 经典 DSP（预处理器内置 AGC，仅浮点） | n/a(非神经) | 48kHz/帧长由调用方指定/单通道 | 数字增益 | 采集后 | 自测(no public benchmark) | 源码注释：定点路径尚不支持 AGC（FIXME），无公开收敛时间数字 (自测口径 1) | BSD（Xiph COPYING，三条款式） | yes | yes: 任意 CPU（C 浮点实现） | github.com/xiph/speexdsp |
| FFmpeg loudnorm | 经典 DSP（EBU R128 响度归一 + 真峰值限幅，双通或线性模式） | n/a(非神经) | 48kHz/100ms 子帧（3s 分析窗）/多通道 | 响度(LUFS) | 离线 | 自测(no public benchmark) | 默认目标 -24 LUFS、LRA 7 LU、真峰值 -2 dBTP（源码默认值），未按自测口径 1 实测 (自测口径 1) | LGPL-2.1-or-later | yes | yes: 任意 CPU（C 实现，非实时批处理） | github.com/FFmpeg/FFmpeg |
| FFmpeg dynaudnorm | 经典 DSP（动态响度归一，单遍） | n/a(非神经) | 48kHz/500ms 帧（默认 framelen=500）/多通道 | 数字增益 | 离线 | 自测(no public benchmark) | 默认 framelen 500ms、gausssize 31、peak 0.95、maxgain 10.0（源码默认值），未按自测口径 2 实测过冲 (自测口径 2) | LGPL-2.1-or-later | yes | yes: 任意 CPU（C 实现，非实时批处理） | github.com/FFmpeg/FFmpeg |
| libebur128 | 标准/测量算法（EBU R128 响度与真峰值测量库） | n/a(非神经) | 48kHz/任意长度/多通道（含真峰值扫描） | 非AGC(相邻：响度测量) | 离线 | 自测(no public benchmark) | 实现 EBU R128 响度归一测量，v1.1.0 起含 ITU-R BS.1770-4 声道定义 (自测口径 1) | MIT | yes | yes: 任意 CPU（C 实现） | github.com/jiixyj/libebur128 |
| pyloudnorm | 标准/测量算法（ITU-R BS.1770-4 响度计量与归一，Python） | n/a(非神经) | 48kHz/任意长度/多通道 | 响度(LUFS) | 离线 | 自测(no public benchmark) | ITU-R BS.1770-4 实现，可按目标 LUFS 归一（README 示例 -12 LUFS），未按自测口径 1 实测 (自测口径 1) | MIT | yes | yes: 任意 CPU（Python，依赖 numpy） | github.com/csteinmetz1/pyloudnorm |
| laos.loudness（本仓库 BS.1770-4 响度计量） | 标准/测量算法（纯 stdlib 实现，零第三方依赖） | n/a(非神经) | 48kHz/任意长度/多通道（单声道按 G=1.0） | 非AGC(相邻：响度测量) | 离线 | 自测(no public benchmark) | 积分响度 RTF 0.043、真峰值 RTF 0.412（48kHz 单声道 30s 粉噪、conda CPython 实测） (自测口径 3) | 未标注（github.com/Yfredy/LAOS 仓库根目录无 LICENSE 文件，许可不可核实） | yes | yes: 任意 CPU（纯 stdlib） | github.com/Yfredy/LAOS（laos/loudness.py） |
| Android AutomaticGainControl（audiofx 框架 API） | 经典 DSP（框架 API，实际效果由 /vendor/etc/audio_effects.xml 挂载） | n/a(非神经) | 48kHz/由 AudioRecord 决定/单或双通道 | 模拟增益、数字增益 | 采集前 | 自测(no public benchmark) | 默认挂载由 /vendor/etc/audio_effects.xml 决定；VOICE_RECOGNITION 必须默认关闭；除 VOICE_RECOGNITION 外对增益无明确要求 (自测口径 1) | Apache-2.0（AOSP platform/frameworks/base） | API only | yes: Android SDK API（实现在 HAL/厂商侧，App 只能开关） | github.com/aosp-mirror/platform_frameworks_base（AOSP 官方 GitHub 镜像） |
| Android 厂商 TX-path 采集固件 AGC（ADSP/DSP） | 经典 DSP（厂商固件，不可得） | n/a(非神经) | 设备相关（通常 48kHz/10ms/单或双通道） | 模拟增益、数字增益 | 采集前 | 自测(no public benchmark) | 无公开指标（固件不可得，第三方 App 无法读取其参数与是否启用） (自测口径 1) | proprietary（厂商固件，无公开许可） | no（厂商固件不可得；第三方 App 拿不到 aDSP） | no | github.com/aosp-mirror/platform_frameworks_base（AudioSource/HAL 接口语义；固件实现本身不可得） |

**表内说明**

- **WebRTC AGC2 的两段结构（必写项，逐条来自源码）**：
  ①**模拟段**改的是**采集音量**——不是对样本乘系数。`audio_processing.h` 明写
  `set_stream_analog_level(int)`「to pass the current analog level **from the audio HAL**」、
  `recommended_stream_analog_level()`「the recommended new analog level **for the audio HAL**.
  It is the user's responsibility to apply this level」，即框架只给建议值，**由调用方把它写回设备**；
  在 Android/ALSA 上就是采集音量（AGC1 的 `analog_level_minimum/maximum = 0/255`）。
  ②**数字段**是闭环：`adaptive_digital_gain_applier` + `adaptive_mode_level_estimator` +
  `noise_level_estimator` + VAD，输出的是**逐帧变化的数字增益**（`kInitialAdaptiveDigitalGainDb = 8`、
  `kMaxGainDb = 30`、变化率 `kMaxGainChangePerSecondDb = 3.0`），最后过 `limiter`（硬限幅 + 插值增益曲线）。
- **内置噪声门（必写项）**：AGC2 的"门"由两处构成——`kMaxNoiseLevelDbfs = -50`（噪声电平上限，
  与 `noise_level_estimator` 联合调参，源码注释原文）与 `kVadConfidenceThreshold = 0.9`（只有 VAD 置信度
  ≥0.9 的帧才用于更新语音电平与允许增益下降）。**注意它判的是"这一帧是不是语音/噪声"，不是"这一帧够不够响"**，
  所以它抑制的是"把噪声底当成语音抬起来"，与 §0.3 第 3 条要测的噪声提升是同一件事。
- **一个容易记错的口径**：AGC2 的目标量是 **dBFS 电平 + headroom（1 dB）+ 饱和保护**，
  **不是 ITU-R BS.1770 的 LUFS**。所以 AGC2 不能直接当"-24 LKFS 响度归一"用；
  要落 GY/T 282-2014 的 -24 LKFS，必须外接响度闭环或离线归一（loudnorm / pyloudnorm / laos.loudness）。
- **AGC2 不是"纯 DSP"**：它的 VAD 是 `rnn_vad::RnnBasedVad`，一个 12 kHz、42 维特征、
  `kFullyConnectedLayersMaxUnits = 24` / `kRecurrentLayersMaxUnits = 24` 的 RNN。
  这是"经典 DSP 环里嵌了极小神经网络"的实例，**不改变本档 `n/a(非神经)` 的判定**
  （环本身无参数量、无训练权重），但在 §Part 2 的算力估算里必须把它算进去。
- **SpeexDSP AGC 只做数字增益**（`speex_compute_agc` 在 `preprocess.c` 内、浮点实现），
  不写模拟增益：它没有 `stream_analog_level` 那样的设备耦合接口。
- **两个 `非AGC(相邻：响度测量)` 条目（libebur128、laos.loudness）的收录理由**：
  它们只测量、不施加增益，按 `00` 口径不能记成增益控制；收录是因为**响度目标是本调研自测口径的判据来源**，
  没有可核验的测量实现，"-24 LKFS"这条判据就是空的。`laos.loudness` 更是本仓库已在用的实现。
- **`laos.loudness` 的许可列写"未标注"是如实填写**：仓库根目录没有 LICENSE 文件，
  本调研不去猜一个许可。它是我们自己的代码，可得性不受影响。
- `edge` 列按 `00` 口径：经典 DSP 条目可写 `yes: 任意 CPU`，但**"能跑"不等于拿到低功耗档**——
  laos 现状是 B 档（proot 内通用 Linux CPU，空闲 400–1000 mW 量级），拿不到 aDSP 的 mW 档。

**因缺少可核验来源而删除的候选（不写入表）**

| 候选 | 删除原因 |
|---|---|
| Apple AVAudioSession 的 `automaticGainControl` / iOS 采集 AGC | 只有官方文档，无 `github.com` / `arxiv.org` / `huggingface.co` 可核验源码仓库，且 iOS 不在 laos 路径上 |
| SoX `gain` / `norm` | 官方仓库在 SourceForge（git://git.code.sf.net/p/sox/code），GitHub 上未找到官方镜像，来源规则不满足 |
| PulseAudio `module-sles-source`、`PipeWire` 相关模块 | 官方仓库在 gitlab.freedesktop.org，非 schema 允许的三个来源域；且 sles-source 的 OpenSL ES 录制预设参数本次未核实到源码 |
| ReplayGain 2.0（-18 LUFS 参考） | 社区规范（Hydrogenaudio wiki），无官方仓库，且 -18 LUFS 不是任何广播/网络视听标准的目标值 |
| Opus/Ogg 的 `R128_TRACK_GAIN`（RFC 7845 §5.2.1） | RFC 文本已核实（Q7.8 dB、参考 EBU R128），但它是**容器标签规范**、不是增益控制实现，且未找到可核验的 GitHub 实现仓库，故只在 §Part 3 标准小节引用，不入表 |
| WaveNorm AGC（Interspeech 2026，49M MACs / 55KB） | **神经网络**，属小型档，归 Task 10 收录；本文件只在 §Part 2 作为算力对照引用 |
| NN3A（arXiv:2110.08437） | 神经网络（AEC/NS/AGC 联合），归 Task 10 |
| Android `VOICE_RECOGNITION` / `UNPROCESSED` 本身 | 是路由与调谐档位，不是增益控制实现 |

---

## Part 2 · 经典 DSP 为什么仍是主力

### 2.1 延迟：帧长与 lookahead（由源码常量推导，非实测）

| 项 | 值 | 出处 |
|---|---|---|
| 处理帧 | `kFrameDurationMs = 10` | `agc2_common.h` |
| 帧内子帧数（限幅器增益插值） | `kSubFramesInFrame = 20` → 子帧 0.5 ms | 同上 |
| 每通道样本上限 | `kMaximalNumberOfSamplesPerChannel = 480`（= 48 kHz × 10 ms） | 同上 |
| 限幅器缓冲 | `per_sample_scaling_factors_`（480 float）+ `scaling_factors_`（21 float） | `limiter.h` |
| lookahead | **无跨帧 lookahead**：限幅器在当前帧内做子帧级插值，`480` 样本正好等于一帧 | 由上面三个常量推得 |
| 算法延迟 | **≈ 1 帧 = 10 ms**（不含采集/播放缓冲） | 同上推导 |

对照：离线响度归一（loudnorm）以 **3 s 分析窗**、**100 ms 子帧**工作（源码 `frame_size(sr, 3000)` 与
`frame_size(sr, 100)`），**根本不是为常驻链路设计的**——它要求看到整段（或至少 3 s）才能定增益。

### 2.2 内存：状态变量字节量级（由源码常量估算，非实测）

| 组成 | 规模 | 字节 |
|---|---|---|
| Limiter 逐样本缩放因子 | 480 float | 1,920 B |
| Limiter 子帧插值因子 | 21 float | 84 B |
| RNN VAD 状态 + 输出 | 2 × 24 float（另有 42 维特征向量） | ~360 B |
| Level Estimator 记忆 | `kFullBufferSizeMs = 1200`、400 ms 超帧 → 3+1 个条目 | 数十 B |
| 其余（饱和保护、噪声估计、增益器） | 若干标量 | < 100 B |
| **合计** | — | **约 2 KB 量级** |

对照：神经方案里**已知最省的一条** WaveNorm 官方自报 **55 KB**
（Interspeech 2026，ISCA 官方 proceedings 页，pp. 475–479，doi 10.21437/Interspeech.2026-2115）。
**约一个数量级以上的内存差**，且这是神经侧"为边缘优化过"的数字，不是随便挑的大模型。

### 2.3 CPU：MCPS 量级

- **未检索到 WebRTC APM 的官方 MCPS / MMACs 数字。** 本调研不替它估算一个 MCPS——那等于编数。
  可核验的下界是结构性事实：AGC2 的增益环是**标量运算**（电平估计、增益插值、限幅），
  **环内没有矩阵乘**；唯一的矩阵运算是 24 单元的 RNN VAD（12 kHz、42 维特征）。
- 对照 WaveNorm：官方自报 **49 M MACs**（同上出处）。口径提示：该页**未说明 MACs 的时间单位**
  （每帧 / 每秒 / 每次推理），**不能直接当成 MCPS 与本表其它数字做减法**；跨条目比较时必须先统一口径。
- 再对照本仓库实测：`laos.loudness` 的积分响度 **RTF 0.043**、真峰值 **RTF 0.412**
  （48 kHz 单声道 30 s 粉噪，conda CPython）——**纯 Python 的 stdlib 实现**都只用到 4% 的实时预算来测响度，
  这是"响度测量这件事本身很便宜"的直接证据（真峰值因为做 sinc 插值重构，贵一个数量级）。

### 2.4 收敛时间 / 稳态误差：神经方案有没有公开证据能赢

**结论：没有。不是经典 DSP 在这些指标上赢了，而是这一类数字根本没人公开报过。**

- 本轮检索到的神经 AGC 工作（WaveNorm，Interspeech 2026；NN3A，arXiv:2110.08437）公开的指标形态是
  **下游任务指标**：VAD 错误率、降噪量（约 6 dB）、ITU-T P.56/P.79 合规、感知质量。
  **没有任何一条给出收敛时间、稳态误差、增益波动 LU 峰峰值或增益泵浦次数**，
  也没有任何一条按 `00` 文件的自测口径 1/2/3 报数。
- 其中"WaveNorm FPR 0.272 vs WebRTC 0.304（以 Silero VAD 为下游）"这一条数字来自**论文摘要博客**
  （nanless.github.io 的 Audio Paper Digest），**ISCA 官方页未给出该数字**，本调研标记为**二手、未二次核实**。
- 反向证据也要如实写：WaveNorm 摘要明确指出传统 AGC 的失败模式是
  **"clipping, delayed adaptation, noise amplification, and audible gain fluctuations"**（削波、
  适应滞后、噪声放大、可听的增益抽动）——这正是 `00` 口径 2/3 要测的东西。
  也就是说**神经方案的动机恰好打在经典 DSP 的痛处上，但它没用闭环指标证明自己**，
  只用了下游任务指标。这是一个"证据缺口"，不是"神经方案更差"的结论。
- 因此本档的结论形态是：**经典 DSP 仍是主力，因为它是唯一有可核验闭环语义（增益变化率、噪声门、
  headroom、限幅）且算力/内存可推算的一类；神经侧目前没有任何公开数字能证明它在收敛时间或稳态误差上更优。**
  这也正是 `00` 文件必须定义"编号化自测口径"的理由——没有公共榜单，就只能自己按同一口径测。

---

## Part 3 · 标准与合规

**先说适用范围的边界**：下列标准全部是**成品节目**标准（制作 / 播出 / 分发 / 接收），
**没有任何一条规定"终端语音采集端"的响度目标**。把 -24 LKFS 用作 laos 采集自测的目标值，
是本调研的**外推**（让采集结果符合成品节目标准），不是标准规定。沿用 `00` 文件的裁定 1：
以 **GY/T 282-2014（-24 LKFS / ±2 LU / -2 dBTP）为主引用**。

| 标准 | 目标响度 | 容差 | 真峰值上限 | 适用范围 | 本次核实方式与状态 |
|---|---|---|---|---|---|
| **ITU-R BS.1770-4**（2015-10） | 不规定目标值，只定义 LKFS/LUFS 与真峰值**测量算法**（K 加权、400 ms 块、绝对门 -70 LUFS、相对门 -10 LU） | — | — | 测量算法本体 | 算法细节经 libebur128 / pyloudnorm README 与二手综述确认；⚠️ **ITU 官网本次未直接打开**，版本序列（-2 2011 / -3 2012 / -4 2015 / **-5 2023-11，现行**）为二手来源确认 |
| **ITU-R BS.1770-5**（2023） | 同上（测量算法） | — | — | 现行版本 | 同上；**-4 已被 -5 取代**，本调研按计划仍以 -4 为基准，引用时须注明现行版本 |
| **EBU R128**（v5.0，2023-11） | **-23.0 LUFS** | **±0.5 LU**（直播 ±1.0 LU） | **-1 dBTP** | 欧洲广播（30+ 国家公共广播） | 二手（EBU 官方页 tech.ebu.ch/publications/r128 经引用确认）；⚠️ 版本与 -1 dBTP 未在 EBU 原文 PDF 二次核实，沿用 `00` 文件结论 |
| **ATSC A/85:2013**（+Corrigendum No.1） | **-24 LKFS** | ±2 dB | 低于 **-2 dBTP** | 北美数字电视（CALM Act 的合规测量依据） | 二手（ATSC 官方页经引用确认）；⚠️ 是否存在更新版（有第三方提及 2026 版）**未核实，不作为依据** |
| **GY/T 282-2014**（中国） | **-24 LKFS** | **±2 LU** | **-2 dBTP** | 中国数字电视节目**制作 / 播出 / 分发** | ✅ **本次直接读到标准 PDF 原文**：§4.3 目标 -24 LKFS、§4.4 容差 ±2 LU、§4.6 最大真峰值不超过 -2 dBTP；另见 NRTA 电视剧母版标准对其的规范性引用 |
| **GY/T 377-2023**（中国） | **-15 LKFS 或 -24 LKFS**（可双版本分发） | **±2 LU** | **-1 dBTP** | 中国**网络视听节目**（非直播，直播类参考执行） | ✅ **本次直接读到标准 PDF 原文**（nrta.gov.cn / gov.cn）：§5.1 a) 两种目标值与适用环境、§5.1 c) 真峰值 ≤ -1 dBTP |
| **GY/T 262-2012**（中国） | 测量算法（IDT ITU-R BS.1770-2:2011），不设目标值 | — | — | 被 GY/T 282-2014、GY/T 377-2023 **规范性引用** | ✅ 引用关系在 GY/T 377-2023 原文"规范性引用文件"中直接读到；⚠️ 对齐的是 **BS.1770-2**，不是 -4/-5 |
| **RFC 7845**（IETF，2016）§5.2.1 | 参考 EBU R128（-23 LUFS）计算增益标签 | — | — | Ogg Opus 的 `R128_TRACK_GAIN` / `R128_ALBUM_GAIN`：**播放端**按标签施加增益 | ✅ **本次直接读到 RFC 全文**：增益为 Q7.8 定点 dB，示例 -573 / 111；"若播放器使用这些标签，必须在 output gain 之上再叠加" |

**未采用 / 不适用的（如实列出，避免误引）**

| 项 | 值 | 为什么不采用 |
|---|---|---|
| AES TD1004（-16 ~ -20 LKFS） | 流媒体 / 网络文件播放 | 二手引用，且 `00` 文件已查明 -16 LUFS 无广播电视/网络视听标准出处 |
| ReplayGain 2.0（-18 LUFS） | 社区规范（Hydrogenaudio wiki） | 非标准、无官方机构，仅作参考 |
| 平台归一化目标（Spotify -14 LUFS、Apple Sound Check -16 LUFS 等） | 播放端归一化 | 是**平台回放策略**，不是采集端或节目交付标准；laos 的音频只喂 ASR 与情绪蒸馏，不适用 |
| 面向"终端语音采集 / 录音 App"的响度目标标准 | — | **未检索到**。GY/T 系列只有电视节目与网络视听节目两类成品节目标准 |

---

## Part 4 · 自检与疑虑

1. **校验器覆盖性**：本文件主表的首列是 `模型`（`00` schema 逐字照抄），
   因此 `scripts/table_lint.py` **不会静默跳过**它。本文件另有 6 张说明性表格（首列不是 `模型`），
   按设计被跳过，不误报。跑校验器后须核对打印的行数是否等于文件实际表格行数（含表头与分隔行）。
2. **镜像来源的诚实声明**：WebRTC 的官方上游是 `webrtc.googlesource.com`（本次 `?format=TEXT` 抓取被截断，
   只取到 972 B），AOSP 的官方上游是 `android.googlesource.com`；本文件的源码级证据改从两者的
   **GitHub 镜像**（`webrtc-uwp/webrtc`、`aosp-mirror/*`）核对。`aosp-mirror` 是 AOSP 官方镜像组织；
   **`webrtc-uwp/webrtc` 是第三方 UWP 移植仓库**，其 `master` 分支的 AGC2 代码可能落后上游，
   `gain_controller2.h` 在该镜像中不存在（本文件未引用它）。凡引用到版本敏感处，须回上游复核。
3. **未二次核实项**：① EBU R128 与 ATSC A/85 的现行版本号与 -1/-2 dBTP 数值（官网未直开，沿用 `00`）；
   ② ITU-R BS.1770-5 的官方版本页；③ `termux-microphone-record` CLI 是否把 `source` intent extra 暴露成参数；
   ④ WaveNorm 的 VAD FPR 数字（只有二手博客）。**这些都没被写成表内数字。**
4. **估算与实测的区分**：§Part 2 的"2 KB 量级""≈10 ms"是**按源码常量推导/估算**，不是实测；
   WaveNorm 的 49 M MACs 是**官方自报**且未说明时间单位。三者都已在正文标明，不要当成实测数字引用。
5. **本文件最大的遗留风险**：二次增益结论仍是"不确定"，需真机验证（§0.3 已给出判据）。
   在验证完成前，`07-adoption.md` 不得把任何"采集后闭环增益"写成推荐——这是 `00` 红线一。
