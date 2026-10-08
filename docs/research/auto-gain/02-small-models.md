# 小型神经网络档（< 30M）—— 增益控制领域的「主力」与「误认」

> 本文件是 `docs/research/auto-gain/` 的**小型档**（参数量 < 30M，左闭）。
> 表格 schema 由 `scripts/check_agc_table.py` 机器校验（12 列，规则 g/h/i/j + 通用 6 条）。
> 姊妹文件：`01-classical-dsp.md`（经典 DSP 主力）、`04-large-models.md`（生成式修复）。
> 口径来源：`00-taxonomy-and-metrics.md`（作用点 / 控制对象 / 自测口径）。

**一句话定位**：AGC 的神经网络几乎全部落在小型档——但其中**绝大多数只做「降噪掩码」，并不做增益控制**。本档的意义不在于「选一个增益模型」，而在于划清「神经换来了什么、没换来什么」（见 §判决定性点）。唯一的真·联合 SE+AGC 工作是 SE-AGCNet，其参数量未公开于摘要，只在 §3 正文讨论，不进 schema 表（GC 4：查不到参数量就不入表）。

---

## 主表：小型神经网络（< 30M）

| 模型 | 版本/形态 | 参数量(M) | 输入 | 控制对象 | 作用点 | 基准 | 指标 | 许可 | 可得 | edge | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RNNoise | 神经·GRU(3 层，频带增益预测) | 0.085 | 48kHz / 20ms 帧 / 单通道（42 维特征） | 降噪掩码 | 采集后 | DNS4 blind test | DNSMOS OVLMOS 3.38 (DNS4 blind) | BSD-3-Clause | yes | yes: 任意 CPU / MCU（C 定点，< 10 MFLOPS） | https://github.com/xiph/rnnoise（arXiv:1709.08243） |
| DTLN | 神经·双信号变换 LSTM（双阶段） | 0.243 | 16kHz / 32ms 块（512 采样 @ 128 移） | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 3.04 (VoiceBank-DEMAND) | MIT | yes | yes: TF-lite INT8 RPi3B+ RTF 0.28 | https://github.com/breizhn/DTLN（doi:10.21437/Interspeech.2020-2631） |
| GTCRN | 神经·卷积循环 | 0.048 | 16kHz / 10ms 帧 / 单通道 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 2.87 (VoiceBank-DEMAND) | MIT | yes | yes: ONNX Runtime Mobile INT8 | https://github.com/Xiaobin-Rong/gtcrn（论文 23.7K / 39.6 MMACs） |
| DeepFilterNet2 | 神经·ERB + DeepFilter（DF 阶 5） | 2.0 | 48kHz / 20ms 帧 / 50% 重叠 / 40ms 延迟 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 3.04 (VoiceBank-DEMAND) | Apache-2.0 | yes | yes: 任意 CPU（Core i5-8250U RTF 0.04） | https://github.com/Rikorose/DeepFilterNet（arXiv:2205.05474） |
| DeepFilterNet3 | 神经·ERB + DeepFilter（改进） | 2.5 | 48kHz / 20ms 帧 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ ~3.1 (VoiceBank-DEMAND，同架构未单列对比) | Apache-2.0 | yes | yes: 桌面 0.1–0.2 RTF / RPi4 0.5–0.8 RTF | https://github.com/Rikorose/DeepFilterNet |
| NSNet2 | 神经·RNN（频带增益） | 6.17 | 16kHz / 20ms 帧 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 2.47 (VoiceBank-DEMAND) | MIT | yes | yes: 任意 CPU RTF 0.02 | https://github.com/microsoft/DNS-Challenge（NSNet2） |
| PercepNet | 神经·增益 + 后滤波（Valin 2020） | 8.0 | 16kHz / 20ms 帧 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 2.73 (VoiceBank-DEMAND) | BSD | yes | yes: 任意 CPU（0.8 G MACS） | https://github.com/juanmc2005/PercepNet（Interspeech 2020） |
| DCCRN | 神经·复数域 CRN | 3.70 | 16kHz / 帧 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 2.54 (VoiceBank-DEMAND) | 非商用（权重受限） | yes(权重受限) | no（RTF 2.19，非实时） | https://github.com/haoxiangsnr/DCCRN（Interspeech 2020） |
| FRCRN | 神经·频率递归复合网络 | 10.27 | 16kHz | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 3.21 (VoiceBank-DEMAND) | 非商用 | yes(权重受限) | unknown(未找到公开转换案例) | https://github.com/Audio-Westlake/FRCRN（Interspeech 2022） |
| FullSubNet+ | 神经·频带 + 时序子网 | 8.67 | 16kHz / 帧 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 2.88 (VoiceBank-DEMAND) | Apache-2.0 | yes | unknown(未找到公开转换案例) | https://github.com/haoxiangsnr/FullSubNet（Interspeech 2022） |

**表数核对**：本表 1 张、10 行 schema 记录。校验器打印应一致（GC 3）；首列 `模型` 逐字照抄 `00`，不会被 `table_lint` 静默跳过。

---

## §1. 这些模型「是」什么：清一色的降噪掩码

10 条记录里 9 条的控制对象是 `降噪掩码`，只有 SE-AGCNet（§3 正文）标 `联合(SE+AGC)`。
这不是巧合，是结构事实：**增益控制（乘一个标量系数）与降噪（逐频带时频掩码）是两件不同的事**。
RNNoise / DTLN / GTCRN / DeepFilterNet 系列的产出都是「每个频带保留多少能量」的掩码，
它们解决的是「噪声掩住语音」，**不解决「说话人离麦克风远、整体太轻」**。
因此本档严格说是一张「轻量神经语音增强档」，不是「增益控制档」——
与 `01-classical-dsp.md` 里真正做数字增益闭环的 WebRTC AGC2 / SpeexDSP 不能等同对待。

---

## §2. 端侧可得性预览（详表见 `05-edge-deployment.md`）

- **真能常驻跑的**：RNNoise（< 10 MFLOPS，Cortex-A53 单核实时）、DTLN（RPi3B+ TF-lite INT8 RTF 0.28）、
  GTCRN（48K 参数，ONNX INT8）。三者是 MCU / 低端 ARM 档的事实标准。
- **能跑但不实时 / 权重受限**：DCCRN（RTF 2.19，14.36 G MACS，非实时）、FRCRN / FullSubNet+（权重非商用或未见公开端侧转换）。
- **经典 DSP 对照**：WebRTC AGC2 一类的 MCPS 量级是 1–2 MCPS（见 `01`），比 RNNoise 还低两个数量级；
  神经模型的「端侧优势」只在「噪声场景」成立，纯电平调整场景无增益（§3）。

---

## §3. 判决定性点：神经网络在这里换来了什么

### (a) 噪声场景下的增益 —— 有强证据

在有噪声的输入上，神经掩码模型相对「无处理」基线在 PESQ / STOI / DNSMOS 上全面胜出：
DTLN PESQ 3.04、DeepFilterNet2 PESQ 3.04、FRCRN PESQ 3.21（均 VoiceBank-DEMAND，相对 Noisy 的 1.97 提升约 1.1），
RNNoise 在 DNS4 blind 上 OVLMOS 3.38。这部分证据充足，**结论明确：噪声场景该用神经增强**。

### (b) 纯电平调整（无噪声、只是说话声小）—— 没有证据神经优于经典反馈环

**这是本调研的判定锚点，结论写死：没有公开证据。**

理由逐层：
1. 上表 9 条模型的控制对象是 `降噪掩码`，它们**根本不输出增益**，自然谈不上「在纯电平调整上优于 AGC」。
2. 唯一做增益的神经工作是 **SE-AGCNet**（arXiv:2606.25959，Interspeech 2026）：两阶段（MP-SENet SE 骨干 + BiLSTM AGC 模块），
   以 RMS 归一化 + 频域 CNN + 2 层 BiLSTM 做音量归一化，目标响度 -23 LUFS（EBU R128），
   在 LibriAGC / MMCSG / AliMeeting-far 上把 PESQ 从 2.18（MP-SENet 仅 SE）提到 3.00，并降低会议场景 WER。
   **但**：① 它的任务设定是「会议场景音量剧烈不平衡」（突增 / 渐衰 / 随机波动，音量可降到 5%–30%），
   不是 laos 关心的「说话人平稳、只是离得远略轻」；② 它的 AGC 基线只有 `pyagc`（Ellis 的攻击/释放经典实现）和 MP-SENet(AGC)，
   **没有与 WebRTC AGC2 / SpeexDSP 这类工业级反馈环做头对头对比**；③ 参数量未在公开摘要披露（故不入 schema 表）。
3. `00` 的 X-03 原假设「SE+AGC 联合优化无公开 benchmark、无与 ITU-R BS.1770 对齐的评价协议」——
   SE-AGCNet **部分推翻**了该假设（它确实引入了 LUFS / St LUFS / LRA 标准化指标，并与 BS.1770 / EBU R128 对齐），
   但「与经典 DSP 增益在纯电平任务上的优劣」仍无头对头证据。

→ 因此：**「说话声小」这类纯电平问题，证据链只支持经典 DSP 反馈环，不支持换神经网络。**
神经的增量全部发生在「噪声 + 音量不平衡」同时存在的场景。

### (c) 代价

| 项 | 经典 DSP（WebRTC AGC2） | 小型神经（RNNoise / DTLN / DF2） |
| --- | --- | --- |
| 算力 | ~1–2 MCPS（C 定点） | RNNoise < 10 MFLOPS；DF2 0.35 G MACS；DTLN ~0.5 G MACS |
| 模型体积 | 无（代码） | RNNoise ~100 KB；DTLN ~1 MB；DF2 ~2 M 参数 |
| 常驻功耗 | < 1 mW（AP 用户态） | RNNoise 可忽略；DF2 级约数十 mW（CPU 推理） |
| 实时性 | 原生 | RNNoise / DTLN / DF2 实时；DCCRN 非实时（RTF 2.19） |

相对经典 DSP，神经模型在算力上是 **100–1000×** 的量级差，换来的是噪声场景的听感/可懂度提升，
**不是**电平调整能力的提升。这条代价账直接喂给 `05-edge-deployment.md` 与 `07-adoption.md`。

---

## §4. 自检与疑虑

1. **校验器覆盖**：主表首列 `模型`，不会被 `table_lint` 静默跳过；已核表数 = 记录数 = 10。
2. **SE-AGCNet 未入表**：参数量未在公开摘要披露，按 GC 4「查不到参数量不入表」处理，仅在 §3 正文讨论；
   其许可为代码开源（jinming00.github.io/SE-AGCNet）、权重未公开托管。
3. **DCCRN 许可**：原版论文代码 MIT，但训练权重多受非商用约束，已如实标 `非商用（权重受限）`。
4. **未二次核实项**：① DeepFilterNet3 的 VoiceBank-DEMAND PESQ 未在论文单列（仅 DF2 报告 3.04），
   本文按同架构给 `~3.1` 并注明；② FullSubNet+ 的端侧 RTF 未见公开数字，标 `unknown(未找到公开转换案例)`；
   ③ NSNet2 许可按 Microsoft DNS-Challenge 仓库惯例标 MIT（仓库未明示单一 LICENSE 文件，存疑）。
5. **跨任务类型不互比**：所有 PESQ 均标 VoiceBank-DEMAND，DNSMOS 标 DNS4 blind，未跨基准比较。
