# SER 落地篇 —— AlwaysOnRec-HY4 ear 通道采纳（06-adoption）

> 2026-10-08 · 消费方：[2026-09-landscape.md](2026-09-landscape.md) §3 决策树 Q6 一体化结论 + §4 落地约束
> 执行计划：[plans/2026-10-08-speech-research-closeout.md](../../superpowers/plans/2026-10-08-speech-research-closeout.md) Task 1
> 结论先行：**引入 opt-in 通道 `sherpa`（sherpa-onnx + SenseVoice-Small int8），一次前向同时产出文本与情感标签；`classify_mood()` 启发式保留为零成本兜底，二者是补充不是替换。**

## 1. HY4 ear 通道现状（Step 1 读码记录）

- **`channel()` 三值与来源**（`aor/drivers/ear.py:71`）：`AOR_ASR_CHANNEL` > `LAOS_ASR_CHANNEL` > `DEFAULT_CHANNEL="stub"`。三值分支在 `_asr()`（L84）：`stub`（零依赖兜底，把声学事实写进文本而非假装转写）/ `funasr`（惰性 `AutoModel(model="iic/SenseVoiceSmall")`，**已经在跑 SenseVoiceSmall 却只取 text 字段、丢弃情感标签，且拖 torch**）/ `server`（HTTP POST 裸 PCM）。任何异常 → `_degraded=True` + 降级 stub 文本，模块导入永不崩。
- **`classify_mood(dbfs, dur_ms)` 输入来源**（L114、L142）：`transcribe_file()` 里 `dbfs = rms_dbfs(unpack_pcm16le(pcm))`、`dur_ms` 由 PCM 长度推得；输出四值启发式标签（高唤醒/平稳/低唤醒/短促）填进记录的 `emotions` 字段，`ear.journal` 把它拼进记忆 tags。
- **新通道与 `classify_mood` 的职责边界（裁定：补充，不替换）**：启发式唤醒度标签零成本、stub 通道下也成立、已有测试覆盖（test_journal 的 tags 断言）——**保留**；模型情感作为独立字段 `emotions_model` 进入记录（sherpa 分支一次前向的副产物，无额外推理成本），`ear.journal` 的 tags 融合两者。理由：替换会让 stub/degraded 路径失去全部情绪信息，补充让两条证据链（能量启发式 / 模型判别）可对照。

## 2. proot Ubuntu（B 档）当下真能跑什么（Step 2-1）

依据 [04-edge-deployment.md](04-edge-deployment.md) A/B 档结论与 landscape §3：

| 候选 | B 档（proot CPU）可行性 | 判定 |
|---|---|---|
| **SenseVoice-Small int8 via sherpa-onnx** | ONNX INT8 228–229 MB；10 s 音频 ≈70 ms（RTF≈7×10⁻³）；官方 manylinux2014_aarch64 wheel、不依赖 torch；WA 70 (CASIA) / 68 (MER2023) / 70 (IEMOCAP) | ✅ **引入**（触发后短时 + `ear.journal` 充电批量两条路径都覆盖） |
| 同模型 via funasr | 需 torch（GB 级内存、数秒加载），唯一 RTF 证据来自 PC | 既有分支保留，文档标注不推荐 |
| Chinese-HuBERT + 自接头（95M，MIT，MER2024 WAF 72.67） | edge=unknown：无官方端侧导出、无 proot 实测；同构 WavLM-base+ 实测峰值内存 1057–1597 MB | ❌ 备选留档（中文准确率更高但内存先崩） |
| emotion2vec (95M) | MER2024 中文 WAF 56.08，被 HuBERT-base（69.26）甩开 13 点——**中文上反向** | ❌ 排除 |

中文红线提醒（landscape §0）：量化停在 INT8（同行评审"无损" 0.88→0.88），不下 INT4（音频任务有"崩"的证据）。

## 3. 通道设计（Step 3，已落地）

- **命名 `sherpa`**：由 runtime 名 + landscape 结论导出（非凭空命名）；`AOR_ASR_CHANNEL=sherpa` 启用。
- **模型目录 `AOR_SHERPA_DIR`**：须含 `model.int8.onnx` + `tokens.txt`（sherpa-onnx 官方发布物）；缺目录/缺依赖/坏模型 → 走既有降级路径（stub 文本 + `degraded=True`），与 funasr/server 同待遇。
- **API 口径**：`OfflineRecognizer.from_sense_voice(model, tokens, use_itn=True)` → `create_stream()` → `accept_waveform(sr, float32[-1,1])` → `decode_stream()` → `result.text` / `result.emotions`（按 sherpa-onnx 官方 Python 示例；`emotions` 取值经 `getattr` 防御，NEUTRAL 不入库）。**诚实声明：本仓库测试用假模块钉住集成逻辑（惰性单例/目录校验/降级/情感捕获），sherpa-onnx 真前向未在本机验证——首次真机配 `AOR_SHERPA_DIR` 时按 README 冒烟一遍再开通道。**
- **输出融合**：`transcribe_file()` 新增 `emotions_model` 字段（list[str]，通道未提供时为空）；`ear.transcribe` 文本行仅在非空时附加 `emotions_model=…`；`ear.journal` 记忆 tags = `["audio", *emotions, *emotions_model]`。`classify_mood` 输出原样保留。

## 4. 不做什么（Step 2-3，三条）

1. **不引入说话人识别（声纹红线）**：候选池里 ECAPA-TDNN/WavLM/UniSpeech-SAT 等 speaker-capable 模型全部排除；SenseVoice-Small 不产出说话人嵌入，是选它的红线原因之一（landscape §5 自检）。
2. **不输出临床结论**：最大规模抑郁语音检测研究敏感度/特异度均仅 ~71%——`emotions_model` 与 `emotions` 一样只做日记/周报氛围提示，产品侧必须写明"非诊断"（ear.py 模块 docstring 既有红线，本通道不突破）。
3. **视觉模态不进 HY4**：从 A+T 再加视觉的增量只有 +1.5~5.0 点（IEMOCAP +1.54 / MER2024-NOISE +4.88 / MER2025 +4.99），换来 3 条法律否决项（个保法 §26/§28–30、国务院令 799 号）+ 2 个数量级功耗 + 与"原音频即焚"架构直接互斥（[05-multimodal.md](05-multimodal.md) §6.2）。

## 5. 触发条件与回退

- 开通道前置：真机装 `sherpa-onnx`（aarch64 wheel）+ 下载 SenseVoice-Small int8 到 `AOR_SHERPA_DIR` + 冒烟。
- 任何时点把 `AOR_ASR_CHANNEL` 改回 `stub` 即完全回退；`emotions_model` 字段静默回空，下游 tags 断言不受影响。
