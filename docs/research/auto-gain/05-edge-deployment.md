# AGC 跨切轴一 · 端侧部署

> 本文件是 `docs/research/auto-gain/` 的**端侧轴**（Task 13）。
> 消费：Task 9/10 表格、`01` 的二次增益结论、`docs/research/speech-emotion/04-edge-deployment.md`
> 已建立的功耗阶梯（**引用，不重算**）、`docs/research/always-on-recording/hardware-power.md` 的量级阶梯。
> 产出：端侧结论，供 Task 15（landscape）与 Task 16（落地）使用。

---

## §1. 三处作用点的端侧可得性（AGC 独有）

| 作用点 | 第三方 App 能否实现 | 功耗档 | 备注 |
|---|---|---|---|
| 采集前（aDSP / TX-path 固件） | **通常不能**。`01` Part 0 已论证：普通第三方 App 能用 Hexagon HTP 跑推理，但**用不了 aDSP 的 SEE/LPAI**；内核 fastrpc 对未授信进程 attach audioPD 返回 `-EACCES`。Android `AutomaticGainControl` API 也只能开关，参数在 HAL/厂商固件侧，App 读不到 | mW 档（理想位，但拿不到） | 物理上最省，工程上不可达 |
| 采集后（AP 用户态 / proot） | **能** | 常驻跑模型数十至数百 mW；跑经典 DSP < 5 MCPS | **唯一可选层**（laos 现状落在这一层） |
| 离线（开环归一） | 能 | 一次性 | 与即焚架构兼容性见 §4 |

沿用 `04-edge-deployment.md` 的 A/B 两档：

- **A 档 · 真端侧**：aDSP / Sensing Hub / 专用音频 NPU，功耗在 mW 级（Sensing Hub 官方口径 < 1 mA；专用 NPU 如 Syntiant NDP120 常驻 < 1 mW）。
- **B 档 · proot 内**：通用 Linux CPU 推理，空闲 **400–1000 mW**（`hardware-power.md` §3 实测：跑 Linux 的机器空闲即此量级）。laos 当前 proot Ubuntu + Termux 架构**全部落在 B 档**，拿不到 A 档的 mW 级常驻。

> 关键推论：**AGC 的"省电层"（采集前 aDSP）与 laos 完全错位**。laos 能做的增益控制只能放在采集后（B 档），而这恰好是二次增益风险最高的层（见 `01` Part 0）。

---

## §2. runtime 与量化证据

AGC 领域的端侧分支极窄：**真正有大量公开端侧实测的只有超小神经增强模型（RNNoise 类）**；经典 DSP 是纯 C 实现，不需要"部署框架"，但它要跑在 AP 上才对 laos 有效。

### 2.1 神经分支的端侧 runtime 对照

| 模型 | 端侧 runtime | 量化 | 实测档位 | 来源 |
|---|---|---|---|---|
| **RNNoise**（0.085M，GRU 频带增益） | 纯 C（`rnnoise.h`），**无框架依赖**；可跑 Cortex-M | 浮点权重 ~100 KB 内嵌 | **Raspberry Pi Pico 2（Cortex-M33）实时**；STM32H743@480 MHz 单帧（480 样本 / 16 kHz）约 **2.7 ms** | [Raspberry Pi 官方博客](https://www.raspberrypi.com/news/real-time-ml-audio-noise-suppression-on-raspberry-pi-pico-2/) + [ArmDeveloperEcosystem/rnnoise-examples-for-pico-2](https://github.com/ArmDeveloperEcosystem/rnnoise-examples-for-pico-2)；[STM32 移植](https://www.eeworld.com.cn/mcu/eic650130.html) |
| DTLN（0.243M） | TF-lite / TF-lite Micro | INT8 | RPi3B+ RTF **0.28**（见 `02`） | [breizhn/DTLN](https://github.com/breizhn/DTLN) |
| GTCRN（0.048M） | ONNX Runtime Mobile | INT8 | 48K 参数、可 ONNX INT8（见 `02`） | [Xiaobin-Rong/gtcrn](https://github.com/Xiaobin-Rong/gtcrn) |
| DeepFilterNet2（2.0M） | 原生 Rust / ONNX | INT8 | Core i5-8250U RTF 0.04（桌面） | [Rikorose/DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) |

**runtime 覆盖**（按计划要求逐一点名）：

- **TFLite Micro**：DTLN 的 MCU 路径即走此；微控制器端量化推理的事实标准。
- **ONNX Runtime Mobile**：GTCRN / DeepFilterNet2 的 INT8 路径。
- **CoreML**：iOS 侧可用，但 iOS 不在 laos 路径（见 `hardware-power.md` §5）。
- **NCNN / MNN / RKNN / QNN**：均为 ARM/端侧推理后端；RNNoise 因纯 C 实现可直接编译进任意后端，**无需这些框架**；DTLN/GTCRN 可经 ONNX 导入 QNN（骁龙）或 RKNN（瑞芯微）。
- **CMSIS-NN / Ethos-U（MCU 侧）**：RNNoise 在 STM32 上可通过 **NNoM 的 CMSIS-NN 后端**加速（`eeworld` 移植示例），这是 AGC/增强领域**唯一有 MCU NPU（Ethos-U）可行路径**的模型。

### 2.2 经典 DSP 分支（无"部署"概念，但有"能跑在哪"问题）

WebRTC AGC2 / SpeexDSP / FFmpeg loudnorm 都是 C/C++，**没有权重、没有量化**，直接编译即可。
但"能编译" ≠ "能在 laos 跑到省电档"：

- 在 **A 档（aDSP）**：WebRTC AGC2 的原始目标就是 aDSP/TX-path，~1–2 MCPS（见 `02` §3 代价表），本应最省；**但 laos 拿不到 aDSP**（§1）。
- 在 **B 档（proot AP）**：任何常驻进程先被 Linux 空闲功耗钉在 400–1000 mW，`01` Part 2 推导的 ~2 KB 状态、~10 ms 延迟在此档下**完全被掩盖**——增益环本身便宜，但"让它常驻跑"贵。

---

## §3. 常驻增益控制的功耗账

> 所有量程数字来自 `hardware-power.md` 与 `04-edge-deployment.md`，**此处只引用不重算**。

把"什么都不做"作为基线，逐项叠加增量：

| 方案 | 落点 | 常驻增量（相对基线） | 说明 |
|---|---|---|---|
| 什么都不做 | — | 0 | laos 现状：麦克风数据进 AP（B 档），空闲即 400–1000 mW |
| 经典 DSP 增益环（WebRTC AGC2） | 采集后（B 档） | 环本身 < 5 MCPS（可忽略）；**但常驻进程 400–1000 mW** | 增益环算力可忽略，贵的永远是"进程醒着" |
| RNNoise 降噪掩码 | 采集后（B 档） | < 10 MFLOPS，单帧 ms 级；**仍受 B 档 400–1000 mW 笼罩** | MCU 上 < 1 mW 的优势在 proot 内**完全丧失** |
| 理想 AGC（aDSP/TX-path） | 采集前（A 档） | mW 级（Sensing Hub < 1 mA） | **物理可达，laos 工程不可达** |

**核心账**：在 laos 当前的 B 档架构下，**任何增益/增强处理都先支付 400–1000 mW 的"常驻税"**，模型自身的 MCPS/mW 优势（RNNoise 比 AGC2 还便宜两个数量级）在此档下**没有任何省电意义**——因为税比货贵一个数量级。

→ 这再次把结论指向 `01` Part 0 与 `hardware-power.md` §7：**要拿到 AGC 的省电收益，必须走出 proot 做成原生 App 走 aDSP/Sensing Hub**，否则在采集后做增益控制只是把"电平被归一化"的副作用（见 `07-adoption.md`）换一个更贵的实现方式。

---

## §4. 与即焚架构的兼容性

- 增益只作用于**送入推理的那份副本**，不作用于留存副本（`rec.gc` 删的是原始音频，增益参数可随原始音频一并焚毁，不污染记忆）。
- **生成式修复（Task 12 的幻觉风险）不得用于会产生记忆的链路**：它会补出输入中不存在的内容，污染转写与情绪记忆。
- 离线响度归一（loudnorm / pyloudnorm / laos.loudness）是**开环、一次性**，不与固件环互相追逐，是 `07-adoption.md` 唯一被放行形态的前提（详见该文件）。

---

## §5. 本轴结论（供 Task 15/16）

1. **端侧可得性**：采集前（A 档）物理可达但 laos 工程不可达；采集后（B 档）是 laos 唯一能落的点，但被 400–1000 mW 常驻税笼罩。
2. **唯一有公开 MCU 实测的分支是 RNNoise 类超小神经增强**（Pico 2 / STM32 / Ethos-U 路径），但它做的是**降噪掩码不是增益控制**（见 `02` §1）。
3. **功耗账结论**：在 B 档下，增益控制"加不加"对总功耗影响极小（都被常驻税主导），真正的杠杆是"走不走原生 App 拿 A 档"——这是架构层决策，不是模型选型。
4. `edge` 列已在 `01`（经典 DSP）与 `02`（小型神经）回填完毕，本轴不再改表。

---

## §6. 自检

1. **校验器覆盖**：本文件主表首列均非 `模型`，按设计被 `table_lint` 跳过，不误报；不引入 schema 占位符。
2. **引用不重算**：§3 量程数字全部来自 `hardware-power.md` 与 `04-edge-deployment.md`，无自造 MCPS/mW。
3. **RNNoise MCU 证据**：Raspberry Pi Pico 2 为官方博客 + Arm 官方 GitHub 仓；STM32 为社区移植（标为二手但可核验）。
4. **未二次核实项**：① QNN/RKNN 对 DTLN/GTCRN 的具体 INT8 实测数字未见公开基准，仅按 ONNX 可导入推断；② CoreML 路径未展开（iOS 不在 laos 路径）。
