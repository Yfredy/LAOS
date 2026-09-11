# 全天候录音（Always-On Recording）全景调研 · 收敛版

> 调研时间：2026-09-11 ｜ 本文是五条调研线的**收敛结论与索引**，细节在姊妹篇中：
> - 产品 / 开源 / 技术机制：[../always-on-recording-industry-2026-09.md](../always-on-recording-industry-2026-09.md)
> - 学术论文线（六个方向 + 定量锚点）：[academic-papers.md](academic-papers.md)
> - 硬件与功耗 + 平台约束：[hardware-power.md](hardware-power.md)
> - 社会接受度 + 争议事件：[social-acceptance.md](social-acceptance.md)
>
> 记法：✅ 官方源已查证 ｜ 🔶 第三方/媒体声称 ｜ `未证实` 查不到可核验来源。

---

## 1. 一句话结论

**业界已经完成一次洗牌，结论收敛得比想象中更一致：**

- **共识（已证伪的方向）**：纯"常开被动录音 + 云端转写"这条路线在 2024–2026 被系统性证伪。Rewind→Limitless→被 Meta 收购并停服、Humane AI Pin 关停变砖、Bee 被 Amazon 收编，三条独立路径指向同一个死因——**云依赖 + 低使用价值 + 高隐私成本**。
- **共识（已验证的方向）**：活下来的产品全部是"**克制版常开**"——麦克风硬件层可以常开，但**软件层只在 VAD/按键/唤醒词触发后才编码、转写、存储**；蒸馏尽量端侧；原始音频短期留存或即焚。
- **分歧（尚未收敛）**：① 蒸馏位置（云端 vs 端侧）仍在拉锯，且直接决定成本结构与隐私卖点；② 触发模型（常录 / 唤醒词 / 人在场判定 consent mode）没有赢家；③ 记忆层形态（时间线浏览 vs 检索问答 vs 情绪曲线）分化为三种产品哲学。
- **laos 的位置**：在开源世界里，**"零云 + 内核级能力管控 + 原始音频 6 小时即焚 + Agent 记忆打通"这套组合没有第二家**（screenpipe 最接近但无能力管控与即焚；Omi 开源但默认走云）。这是 laos 唯一的、可被反证的差异化主张。

---

## 2. 分类学：四段漏斗 + 三条横向判据

业界所有分歧都发生在同一条链的四个环节上（本文统一用这四个字段描述任何产品/项目）：

```
① 常驻检测 (always-on sensing)  麦克风 → 什么条件下算"有事发生"    功耗：nW – mW 级
② 触发捕获 (capture)            留下哪一段 / 多大 / 存哪          存储：Opus 7.2–10.8 MB/h
③ 蒸馏 (distillation)           转写 / 说话人 / 情感 / 事件，在哪算 功耗：百 mW – W 级
④ 留存与消费 (retention & use)  原音频留多久、文本怎么用、谁在查   合规成本集中在这一段
```

**三条横向判据（每条记录都必须回答）：**

| 判据 | 取值 | 为什么重要 |
|---|---|---|
| `always_on` | 常开录音 / VAD 门控 / 唤醒词 / 声学事件 / 手动触发 | 决定①段功耗与社会接受度 |
| `processing` | 端侧 / 云 / 混合（写明哪段在哪） | 决定成本结构与隐私卖点是否自洽 |
| `retention` | 永久云存 / 短期云存 / 本地即焚 / 仅留文本 / 仅留事件 | 决定④段合规风险，也是用户信任的第一感知点 |

> 说明：本计划原定单独产出 `taxonomy.md`，实际执行中分类框架直接内化到本文与四条姊妹篇，字段名在全文逐字一致。

---

## 3. 全景表一：商业产品（16 个，按形态分组）

| 产品 | 形态 | `always_on` | `processing` | `retention` | 输出 | 2026-09 现状 | 来源 |
|---|---|---|---|---|---|---|---|
| Rewind.ai | desktop | 常开后台 | 早期纯端侧 | 本地 | 转写/检索 | **已停服**（并入 Meta） | [官方](https://rewind.ai/what-happened-to-rewind/) |
| Limitless Pendant | 胸针 | **常开被动** | **纯云** | 云端留存 | 转写/摘要/检索 | **停售**（并入 Meta） | [官方](https://limitless.ai/) |
| Omi（BasedHardware） | 项链 | 24h+ 连续 | 混合，**可自托管** | 用户自定 | 转写/摘要 | 活跃，全开源 | [docs.omi.me](https://docs.omi.me/) |
| Plaud Note / NotePin | 录音卡/胸针 | **物理按键** | 云 + 64GB 本地 | 本地为主 | 转写/摘要 | 活跃 | [plaud.ai](https://eu.plaud.ai/pages/plaud-note) |
| Bee | 腕带 | 按键 + LED | 实时转写 | **不存原始音频** | 摘要 | **被 Amazon 收购**（2025-07） | 见 industry §3.1 |
| Meta Ray-Ban（含 Display） | 眼镜 | 唤醒词常开 | 唤醒端侧 / 查询上云 | 云端 | 字幕/问答 | 活跃；LED 防篡改强制 | 见 social-acceptance ④ |
| Humane AI Pin | 别针 | 按住激活 | **纯云** | 云端 | 问答 | **已关停变砖**，HP 收 IP | 见 social-acceptance ③-1 |
| Apple（iPhone/Watch/AirPods） | 手机/手表 | 手动 + 对话感知 | 端侧 + PCC | 端侧 | 转写/回放（Live Rewind） | 活跃 | 见 industry §3.1 |
| Google Pixel Recorder | 手机 App | 手动 | **端侧 Gemini Nano** | 端侧 | 转写/摘要 | 活跃 | 见 industry §3.1 |
| Samsung Galaxy | 手机 App | 手动/通话一键 | 端侧（宣称） | 端侧 | 转写 | 活跃 | 见 industry §3.2 |
| 科大讯飞 SR 系列 / 听见 | 录音笔 | 按键 | **混合**（云端+SR702 离线） | 本地+云 | 实时转写 | 活跃 | 见 industry §3.2 |
| 华为 FreeBuds Pro 5 | TWS 耳机 | 按键/通话自动 | 鸿蒙混合 | 端侧 | 转写/纪要 | 活跃 | 见 industry §3.2 |
| 小米（眼镜 2 / 耳夹 / 手机） | 眼镜+耳机 | 长按/按键 | 云端转写 | 云 | 转写/纪要 | 活跃，**录音亮灯提醒** | 见 industry §3.2 |
| 有道 OpenPods / X8 | AI 耳机 | 一键 | 云订阅 | 云 | 转写 | 活跃 | 见 industry §3.2 |
| 安克 soundcore Work | 磁吸卡片 | 按键 | 豆包云 + 飞书 | 云 | 转写/纪要 | 活跃 | 见 industry §3.2 |
| 腾讯会议"录音笔" | 会议 App | 会议内手动 | 云端实时 | 留存本地 | 转写/纪要 | 活跃 | 见 industry §3.2 |

**读表结论**：16 个产品里 `always_on=常开被动` 的只有 **2 个**（Rewind、Limitless），且**两个都死了**；剩下的 14 个全是按键 / 唤醒词 / 通话触发。这是本调研最硬的一条行业事实。

---

## 4. 全景表二：开源项目（34 个，按漏斗分层）

### ① 常驻检测层

| 项目 | 许可证 | 关键数字 | laos 可复用性 | 来源 |
|---|---|---|---|---|
| Silero VAD | MIT | 模型 ~2MB，30ms chunk <1ms CPU，ONNX 再快 4–5×；screenpipe/omi/say 都在用 | **极高**（24/7 事实标准） | [GitHub](https://github.com/snakers4/silero-vad) |
| WebRTC VAD | BSD-3 | 20 ms 帧，4 档激进度，纯 C，准确率 ~86% | 高 | [py-webrtcvad](https://github.com/wiseman/py-webrtcvad) |
| openWakeWord | Apache-2.0（模型 CC-BY-NC） | TFLite，可自训练；Home Assistant 默认 | 高（纯 Python，可挂 MCP） | [GitHub](https://github.com/dscripka/openWakeWord) |
| Porcupine | SDK Apache-2.0 / 模型付费 | 97.3% 准确率，RPi5 CPU 0.6% | 中（许可陷阱） | [GitHub](https://github.com/Picovoice/porcupine) |
| Mycroft Precise | Apache-2.0 | **官方冻结**，社区 precise-lite | 中（已被取代） | [GitHub](https://github.com/MycroftAI/mycroft-precise) |
| Snowboy | 专有 | **2020-12 关停** | 低（不要用） | [Kitt-AI/snowboy](https://github.com/Kitt-AI/snowboy) |
| SpeexDSP | BSD-3 | AEC + NS + AGC + VAD 四位一体，专利免费 | 高（AEC 直接用） | [xiph/speexdsp](https://github.com/xiph/speexdsp) |
| RNNoise | BSD-3 | RNN 降噪，毫秒级 | 高（人声分离预处理） | [GitHub](https://github.com/xiph/rnnoise) |

### ② 触发捕获层

| 项目 | 许可证 | 关键数字 | laos 可复用性 | 来源 |
|---|---|---|---|---|
| Opus | BSD-3 + 专利免费 | 帧长 2.5–60 ms，最低 5 ms 延迟；16 kbps = 7.2 MB/h | **高**（低延迟流式编码） | [xiph/opus](https://github.com/xiph/opus) |
| OpenGlass | 开源 | <$25 BOM，ESP32-S3 + 麦 | 中（硬件参考） | [GitHub](https://github.com/BasedHardware/OpenGlass) |
| Brilliant Halo | 开源固件 | Alif Balletto + **硬件级 AAD 唤醒**，14 h | 中（低功耗常开硬件设计） | [GitHub](https://github.com/brilliantlabsAR/halo-firmware) |
| Brilliant Frame | 开源 | nRF52 + FPGA，单 MEMS 麦 | 中（BLE 音频协议） | [GitHub](https://github.com/brilliantlabsAR/frame-codebase) |
| AudioMoth | 开源硬件 | 见 hardware-power.md §3（SD 写入 17–70 mW，睡眠 80 µW） | **高**（占空比调度与功耗预算范本） | [Open Acoustic Devices](https://www.openacousticdevices.info/) |
| esp-sr（ESP32-S3） | Apache-2.0 等 | WakeNet/MultiNet；持续监听 <50 mW | 中（廉价端常开对照） | [组件页](https://components.espressif.com/components/espressif/esp-sr/) |

### ③ 蒸馏层（ASR / 说话人 / 情感）

| 项目 | 许可证 | 关键数字 | laos 可复用性 | 来源 |
|---|---|---|---|---|
| sherpa-onnx | Apache-2.0 | **一站式**：流式/非流式 ASR + VAD + diarization + 声源分离；int8 Zipformer RTF 0.078–0.123 | **极高** | [GitHub](https://github.com/k2-fsa/sherpa-onnx) |
| FunASR | MIT（代码） | Paraformer-zh-streaming（chunk 600 ms）+ FSMN-VAD + 标点 + diarization；**原生 MCP serving** | **高**（中文 + MCP 理念一致） | [GitHub](https://github.com/modelscope/FunASR) |
| SenseVoice | MIT（代码） | ASR + 情感 + 音频事件；>300k h 训练；比 Whisper-large 快 15× | **高**（laos 在用） | [GitHub](https://github.com/FunAudioLLM/SenseVoice) |
| faster-whisper | MIT | CTranslate2，4× 加速 | 高 | [GitHub](https://github.com/SYSTRAN/faster-whisper) |
| whisper_streaming | MIT | LocalAgreement / 自适应延迟；arXiv:2307.14743 | **高**（laos `ear.stream` 直接抄） | [GitHub](https://github.com/ufal/whisper_streaming) |
| Vosk | Apache-2.0 | 20+ 语言（含中文），模型 50 MB–1 GB，RPi 可跑 | 高 | [GitHub](https://github.com/alphacep/vosk-api) |
| whisper.cpp | MIT | 纯 CPU 可跑，examples/stream 经典 demo | 中 | [GitHub](https://github.com/ggml-org/whisper.cpp) |
| WhisperLive | MIT | WebSocket 近实时 | 中 | [GitHub](https://github.com/collabora/WhisperLive) |
| openai/whisper | MIT | 事实标准模型，非流式 | 低（权重） | [GitHub](https://github.com/openai/whisper) |
| SpeechBrain | LGPL-3.0 | 研究向全栈 | 中 | [GitHub](https://github.com/speechbrain/speechbrain) |
| NVIDIA NeMo | Apache-2.0 | Nemotron-3.5-ASR-Streaming-0.6B，80 ms–1 s 可调 | 中（需 GPU） | [GitHub](https://github.com/NVIDIA-NeMo/NeMo) |
| pyannote-audio | MIT | 说话人分离（"录到他人"的工程解） | 中 | [GitHub](https://github.com/pyannote/pyannote-audio) |
| Coqui STT | MPL-2.0 | **已停止维护** | 低 | [GitHub](https://github.com/coqui-ai/STT) |
| moonshine | MIT | 边缘 ASR（27M–244M） | 中 | 见 industry §4.1 |

### ④ 留存与消费层

| 项目 | 许可证 | 关键数字 | laos 可复用性 | 来源 |
|---|---|---|---|---|
| screenpipe | MIT | 24/7 屏幕+音频，本地 SQLite + mp4 + OCR + Whisper + diarization；~20k⭐ | **极高**（laos `drivers/rec` + 记忆层最接近的参照） | [GitHub](https://github.com/screenpipe/screenpipe) |
| BasedHardware/Omi | 开源（含硬件） | 24h+ 连续录音，BLE 流式到手机，15k⭐ | **高**（硬件+固件+后端全栈） | [GitHub](https://github.com/BasedHardware/Omi) |
| mem0 | Apache-2.0 | Agent 记忆层（user/session/agent 三级） | 中（记忆抽取/检索） | [GitHub](https://github.com/mem0ai/mem0) |
| LocalRecorder | 开源 | Whisper + **分层摘要 hour→day→week** + Markdown | 中（laos `journal.py` 同构） | 见 industry §4.2 |
| infinite-recall | 开源 | WhisperKit + SQLite + Omi-shaped REST API 给 MCP | 中 | 见 industry §4.2 |
| Windrecorder | 开源 | Windows 屏幕+OCR | 低 | 见 industry §4.2 |
| recall（trevhud） | 开源 | Whisper + pyannote + Ollama | 中 | 见 industry §4.2 |
| 8ta4/say | 开源 | 全天音频 + Silero VAD 预过滤 + Deepgram | 中（VAD→云 STT 样本） | 见 industry §4.2 |
| OpenVoiceOS | 开源 | 完整助手栈：mic→VAD→wakeword→STT→intent→TTS，插件化 | 中（插件化架构参考） | [GitHub](https://github.com/OpenVoiceOS/ovos-core) |
| Wyoming Satellite | 开源 | **deprecated**；卫星↔中心 JSON+音频协议 | 中（协议设计） | [GitHub](https://github.com/rhasspy/wyoming-satellite) |
| Rhasspy | 开源 | **v2 archived**，被 Home Assistant Wyoming 吸收 | 低 | [GitHub](https://github.com/rhasspy/rhasspy) |
| CLAAP / CLAP 系 | 开源 | audio↔text 同嵌入空间（跨模态检索） | 中（记忆跨模态检索） | 见 academic-papers.md §2 |

---

## 5. 全景表三：关键论文（21 篇，按六个方向分组）

> 完整表格（含研究方法/数据集/对 laos 的关系）见 [academic-papers.md](academic-papers.md)。

**① 低功耗 always-on 音频**：VAD ASIC **47 nW**（[JSSC 2023](https://doi.org/10.1109/JSSC.2023.3302791)）｜AAD 门控 KWS **0.36–0.8 µW**（[JSSC 2022](https://ieeexplore.ieee.org/document/9888232)）｜KWS SoC **0.51 µW**（[JSSC 2021](https://doi.org/10.1109/JSSC.2020.3029097)）｜TD-FEx **988 nW**（[ISSCC 2024](https://doi.org/10.1109/ISSCC49657.2024.10454389)）｜端到端 SLU SoC **8.62 µW**（[ISSCC 2025](https://doi.org/10.1109/ISSCC49661.2025.10904788)）｜含麦克风整机 **63 µW**（[IEEE 2019](https://ieeexplore.ieee.org/document/8752147)）｜TinyChirp 少写 90%、续航 ×4（[arXiv:2407.21453](https://arxiv.org/abs/2407.21453)）｜SF-KWS 综述（[arXiv:2506.11169](https://arxiv.org/abs/2506.11169)）
**② 可穿戴长期录音真实世界研究**：EgoLog（[arXiv:2504.02624](https://arxiv.org/abs/2504.02624)）｜Ego4D 情景记忆基准（[arXiv:2110.07058](https://arxiv.org/abs/2110.07058)）｜Ego-Exo4D 7-mic（[arXiv:2311.18259](https://arxiv.org/abs/2311.18259)）
**③ 声学事件与场景理解**：DCASE 2024 Task 4（best PSDS 0.604）（[arXiv:2406.08056](https://arxiv.org/abs/2406.08056)）｜CLAP（[arXiv:2211.06687](https://arxiv.org/abs/2211.06687)）｜AudioCLIP 零样本 69.4% vs 微调 97.15%（[arXiv:2106.13043](https://arxiv.org/abs/2106.13043)）｜FSD50K（[arXiv:2010.00475](https://arxiv.org/abs/2010.00475)）｜PaSST（[arXiv:2110.05069](https://arxiv.org/abs/2110.05069)）
**④ 真实场景说话人日志**：DIHARD III 真实域 DER 35–45%（[arXiv:2012.01477](https://arxiv.org/abs/2012.01477)）｜VoxConverse（[arXiv:2007.01216](https://arxiv.org/abs/2007.01216)）｜AISHELL-4（[arXiv:2104.03603](https://arxiv.org/abs/2104.03603)）｜AliMeeting（[arXiv:2110.07393](https://arxiv.org/abs/2110.07393)）｜AVA-AVD 离屏说话人（[arXiv:2111.14448](https://arxiv.org/abs/2111.14448)）｜Streaming Sortformer DER 18.97%@1s（[arXiv:2507.18446](https://arxiv.org/abs/2507.18446)）
**⑤ 语音情感与 vocal biomarkers**：emotion2vec（[ACL 2024](https://aclanthology.org/2024.findings-acl.931/)）｜SenseVoice（[arXiv:2407.04051](https://arxiv.org/abs/2407.04051)）｜抑郁筛查 71% 敏感度/特异度（[arXiv:2605.09908](https://arxiv.org/abs/2605.09908)）｜纵向稳定性 8 周（[JAD 2026](https://doi.org/10.1016/j.jad.2026.121374)）｜每日采样 Interspeech 2025（[DOI](https://doi.org/10.21437/Interspeech.2025-2556)）｜JMIR 2017 AUC 0.74–0.83（[JMIR](https://jmir.org/2017/3/e75)）
**⑥ 隐私与社会接受度**：MeMic N=168（[CHI EA 2024](https://doi.org/10.1145/3613905.3650872)）｜178 人 always-listening 调查（[IMWUT 2019](https://doi.org/10.1145/3369807)）｜UCB 隐私控制博士论文（[EECS-2022-249](https://digicoll.lib.berkeley.edu/record/273841/files/EECS-2022-249.pdf)）｜lifelogging 田野研究（[CHI 2010](https://doi.org/10.1145/1753326.1753351)）｜旁观者隐私综述（[Research Ethics 2021](https://doi.org/10.1177/17470161211054021)）

---

## 6. 硬件与功耗量级表（收敛）

完整推导与来源见 [hardware-power.md](hardware-power.md)；此处只留对照（电池基准 5000 mAh × 3.85 V = 19.25 Wh）：

| 漏斗段 | 定制 ASIC | 专用音频 NPU | 手机传感中枢/aDSP | 通用 MCU/AP（软件） | 折算耗电 |
|---|---|---|---|---|---|
| ① 常驻检测 | 47 nW – 1 µW | **140 µW** | **<1 mA**（高通官方） | 26–50 mW | 5 mW ≈ **0.62%/天** |
| ② 触发捕获 | — | — | 未证实 | SD 写入 17–70 mW；占空 9% → 整机 ≈5 mW | 100 mW ≈ 12.5%/天 |
| ③ 蒸馏 | 8.62 µW | 未证实 | NPU 1–4 W；实测整机 4.3–5 W | CPU 1.2 W / GPU 0.9 W | 只能短时突发 |
| ④ 留存 | Opus 16 kbps = 7.2 MB/h；AAC 32 kbps = 14.4 MB/h；PCM = 115 MB/h | | | | 存储不是瓶颈，合规才是 |

---

## 7. 隐私合规 checklist + 风险场景黑名单

完整法律查证（中国 / GDPR / 美国两方同意州）与社会接受度实证见 [social-acceptance.md](social-acceptance.md)。

**最低合规集合（一页 checklist）**

- [ ] **可见指示**：录音中必须有硬件/系统级可见信号（LED / 通知 / 状态栏），且不可被软件关闭（Meta 已因 LED 防篡改被强制固件）
- [ ] **显式触发**：默认不常录；常开需用户显式开启且可随时一键停止
- [ ] **全局禁录开关**：等价 laos 的 `LAOS_REC=0`
- [ ] **默认短期留存 + 自动删除**：用户期待自动删除（UCB 实证），行业默认却是永久存储——这是最大的认知错位
- [ ] **原始音频与派生数据分级**：原始即焚、文本长留、向量中留
- [ ] **审计日志可回放**：每一次录音调用（无论成败）可查（`laosctl mic`）
- [ ] **旁观者（bystander）处理策略**：录音里有不在场的第三方说话人是常态，需有"不确定归属不打标签"的兜底
- [ ] **中国法域单独同意**：敏感个人信息（含声纹）需单独同意；不建声纹库

**风险场景黑名单（建议主动放弃）**

1. 秘密录音 / 隐蔽采集（无指示）
2. 以声纹或说话人身份做长期画像（中国法下声纹=敏感个人信息）
3. 看护场景中被看护人无法表达同意的持续录音
4. 把原始音频永久云端留存作为默认

---

## 8. 失败案例复盘（5 个）

| 案例 | 死因一句话 | 对 laos 的教训 |
|---|---|---|
| **Humane AI Pin** | 纯云依赖 + 续航/散热失控，$699 在 11 个月内变砖 | 端侧优先不是卖点而是生存条件 |
| **Rewind → Limitless → Meta** | "数据永不出设备"→转向云→被广告公司收购，信任链断裂 | 一旦架构允许上云，商业压力必然把它推上云；laos 应把"零云"写进内核约束而非文档承诺 |
| **Microsoft Recall** | 默认开启 + 全量留存，隐私争议导致推迟与默认关闭 | 默认必须收紧；能力要分级、最高级需人类一次性释放 |
| **Friend 吊坠** | 营销把"录音"包装成"监控"，公众反噬 | 命名与营销措辞是产品风险面（laos 文档应统一用"听觉记忆"而非"监控/监听"） |
| **Rabbit R1** | 工程能力不足以支撑演示承诺，信任崩塌 | 只宣称能在目标硬件上稳定跑出的能力 |

---

## 9. 对 laos 的反向映射

### 9.1 已做对、且业界稀缺（差异化卖点）

1. **内核级能力阶梯**（`mic.listen → mic.record → mic.transcribe → mic.always_on`，高层含低层、默认收紧）——开源世界里**没有第二家**把录音做成受内核闸门管控的系统资源。
2. **原始音频 6 小时即焚 + 每次调用写审计 + `LAOS_REC=0` 全局禁录**——同时命中 UCB 实证（用户期待自动删除）与最低合规集合三条。
3. **驱动模块加载不启动录音线程、录音只能被显式 syscall 拉起**——直接规避了 Recall 类"默认开启"的死法。
4. **端到端零云**（本地 VAD → 本地 SenseVoice → 本地记忆）——对标 Humane/Limitless 的死因。
5. **听觉产物直接进入 Agent 记忆与消费层**（`journal` / `diary` / `mood_report`）——业界只有时间线或检索问答，laos 是"检索 + 情绪曲线 + 日记"三合一。

### 9.2 可以抄（落到具体模块）

| laos 模块 | 抄谁 | 抄什么 |
|---|---|---|
| `laos/vad.py` | Silero VAD / WebRTC VAD | 保持零依赖自研作为兜底，但提供"外接 ONNX VAD"适配点（30 ms chunk <1 ms CPU 是硬指标） |
| `drivers/drv_rec.py` | Opus + AudioMoth 占空比 | 16 kbps 默认（7.2 MB/h）；常开模式提供 duty-cycle 档（9% 占空 → 续航 ~12×） |
| `drivers/drv_ear.py` | whisper_streaming（LocalAgreement） | `ear.stream` 的自适应分片策略直接抄 arXiv:2307.14743 |
| `drivers/drv_ear.py` | sherpa-onnx / FunASR | 端侧流式 ASR 的一站式替代通道（含 diarization） |
| `bin/journal.py` | LocalRecorder 分层摘要 | hour→day→week 已规划，与业界一致，可直接对齐 schema |
| 记忆层 | screenpipe SQLite schema + mem0 事实抽取 | `audio_transcriptions(timestamp, speaker, text, offset)` 字段级对齐 |

### 9.3 现有缺口（对照业界）

| 缺口 | 业界参照 | 判断 |
|---|---|---|
| **说话人分离** | DIHARD III 真实域 DER 35–45%；sherpa-onnx CAM++ / pyannote | **真缺口**，但必须按真实域 DER 设置信度阈值，"谁说的"只能作为弱标签 |
| **声学事件检测（第二个小模型）** | DCASE 2024 best PSDS 0.604；TinyChirp | 建议做，但放在 ADSP/低功耗层做**事件级**检测（不落音频），这是"环境理解"的入口 |
| **情感标签粒度** | emotion2vec / SenseVoice；抑郁筛查 71% | 情感必须是**纵向差分**（相对个人基线），不能给绝对分数；71% 意味着 1/3 误报，禁止临床表述 |
| **长时记忆检索** | Ego4D 情景记忆基准 | 缺评测口径：laos 应定义自己的"听觉记忆检索"评测集 |
| **可见指示（真机）** | MeMic N=168 实证 + Android 保活必需 | **真缺口且是合规硬要求**：真机上必须有常驻通知/指示灯 |
| **常开（always_on）可用性** | Android 14 后台 mic FGS 直接 SecurityException | 见下 |

### 9.4 建议路线：3 个月内能落地的 3 件事

1. **把能力阶梯与状态指示做完并落地到真机控制面**（`MIC_CAP_LEVELS` / `mic_state` / `laosctl mic` + Android 常驻通知），让"是否正在录音"永远可查可见——这是唯一同时解决合规、接受度与调试问题的动作。
2. **存储与调度：Opus + 配额 FIFO + 占空比档位**（`rec.start(encoding=...)` / `LAOS_REC_MAX_BYTES` / `mic.always_on_start(duty=...)`），把"24/7"从口号变成可测量的 %/天。
3. **蒸馏侧只做一件加法：`ear.stream`（LocalAgreement）+ 情感标签改为纵向差分**，其余（diarization、声学事件）标记为实验特性，等真机 NPU 通路打通再上（因为③段是瓦级，当前架构下只能在充电/批量时跑）。

> **必须先做的一次架构选择**：继续 proot Ubuntu → 常驻成本落在数百 mW（跑 Linux 的机器空闲就 400–1000 mW），`mic.always_on` 在手机上不成立；要进 mW 档必须做原生 App 走 aDSP/Sensing Hub。README 应明确写出这个分界（见 [hardware-power.md §7](hardware-power.md)）。

---

## 10. 参考来源总表

**姊妹篇（本文的事实底座）**
- 产品/开源/机制：../always-on-recording-industry-2026-09.md ｜ 学术：academic-papers.md ｜ 硬件功耗：hardware-power.md ｜ 社会接受度：social-acceptance.md

**官方 / 厂商**：[Qualcomm 888 AI PDF](https://www.qualcomm.com/media/documents/files/snapdragon-888-ai-blog-post-by-jeff-gehlhaar-vp-of-technology-hsin-i-hsu-senior-product-manager.pdf) ｜ [Infineon IM68D128B](https://www.infineon.com/assets/row/public/documents/24/49/infineon-im68d128b-datasheet-en.pdf) ｜ [TDK AAD 麦克风](https://invensense.tdk.com/news-media/blog/high-performance-mems-microphones-enable-user-friendly-ai) ｜ [Syntiant NDP120](https://www.syntiant.com/?p=7959/) ｜ [Android FGS 限制](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start) ｜ [docs.omi.me](https://docs.omi.me/) ｜ [plaud.ai](https://eu.plaud.ai/pages/plaud-note) ｜ [rewind.ai](https://rewind.ai/what-happened-to-rewind/)

**开源仓库**：[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) ｜ [FunASR](https://github.com/modelscope/FunASR) ｜ [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) ｜ [silero-vad](https://github.com/snakers4/silero-vad) ｜ [whisper_streaming](https://github.com/ufal/whisper_streaming) ｜ [whisper.cpp](https://github.com/ggml-org/whisper.cpp) ｜ [faster-whisper](https://github.com/SYSTRAN/faster-whisper) ｜ [vosk-api](https://github.com/alphacep/vosk-api) ｜ [screenpipe](https://github.com/screenpipe/screenpipe) ｜ [BasedHardware/Omi](https://github.com/BasedHardware/Omi) ｜ [mem0](https://github.com/mem0ai/mem0) ｜ [openWakeWord](https://github.com/dscripka/openWakeWord) ｜ [Porcupine](https://github.com/Picovoice/porcupine) ｜ [OpenVoiceOS](https://github.com/OpenVoiceOS/ovos-core) ｜ [pyannote-audio](https://github.com/pyannote/pyannote-audio) ｜ [SpeexDSP](https://github.com/xiph/speexdsp) ｜ [Opus](https://github.com/xiph/opus) ｜ [RNNoise](https://github.com/xiph/rnnoise) ｜ [OpenGlass](https://github.com/BasedHardware/OpenGlass) ｜ [halo-firmware](https://github.com/brilliantlabsAR/halo-firmware) ｜ [esp-sr](https://components.espressif.com/components/espressif/esp-sr/)

**论文**：见 [academic-papers.md](academic-papers.md) §"建议归档的论文"（含 25 条 arXiv/DOI 直链）与 [hardware-power.md §8](hardware-power.md)。

**社区 / 二手（已标注）**：[termux-app #2871](https://github.com/termux/termux-app/issues/2871) ｜ [Android 14 mic FGS 复盘](https://widget-chat.com/blog/flutter-microphone-foreground-service-securityexception-android-14) ｜ [Android 14 关屏休眠实测](https://blog.lilydjwg.me/tag/android) ｜ [AudioMoth 社区功耗测量](https://www.wildlabs.net/comment/10412)
