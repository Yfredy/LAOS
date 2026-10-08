# AED 跨切轴一 · 端侧部署

> 收尾计划 Task 5。消费：Task 2/3 表格、`docs/research/speech-emotion/04-edge-deployment.md` 的功耗阶梯（**引用，不重算**）、
> `docs/research/qnn-real-device-runbook.md`。
> 产出：端侧可行性结论，供 Task 7（landscape）与 Task 8（落地）使用。

---

## §1. runtime 与量化证据

覆盖 TFLite / TFLite Micro、ONNX Runtime Mobile、CoreML、NCNN、MNN、RKNN、**QNN**。

| 模型 / 类 | 端侧 runtime | 量化 | 实测档位 | 来源 |
|---|---|---|---|---|
| **YAMNet**（3.7M，MobileNetV1 + 521 类头） | TFLite / **TFLite Micro**（Google AI Edge 官方导出路径） | INT8 | 手机 / Cortex-M 可跑；~72 MMACs/s（见 `01`） | [tensorflow/models YAMNet](https://github.com/tensorflow/models/tree/master/research/audioset/yamnet) |
| EfficientAT 系列（0.98–17.9M） | 仅官方 PyTorch 权重 | 无官方 INT8 发布 | **未见公开量化/部署产物** | [EfficientAT](https://github.com/fschmid56/EfficientAT) |
| DCASE Low-Complexity 获奖系统（Karasin_JKU 122K / 29.4 MMACs） | 多为 PyTorch 学生权重 | 无公开 INT8 | **真实缺口：论文给约束（128K 参数 / 30 MMACs），但部署产物少见** | [DCASE2025 Task1](https://dcase.community/challenge2025/task-low-complexity-acoustic-scene-classification) |
| CP-Mobile / 教师蒸馏学生 | TFLite / ONNX | INT8 可行 | 端侧可行但缺公开基准 | — |
| 开放词表（CLAP 类，~86M+） | ONNX Runtime Mobile / CoreML | INT8 | 手机 CPU/ NPU，体积大 | [CLAP](https://github.com/LAION-AI/CLAP) |

**关键缺口（AED 端侧档的真实状态）**：DCASE Low-Complexity 赛题在**架构约束**（128K 参数 / 30 MMACs）上已立规，
但**获奖系统多数只发布 PyTorch 权重**，公开 INT8 量化 / TFLite Micro / QNN 部署产物的**极少**。
这意味着"参数量达标 ≠ 端侧可跑"——laos 若要真正上设备，必须自己补量化与导出这一步，不能假设"论文给约束就有产物"。

**QNN 路线**：第三方 App 在骁龙上能自由使用的是 **HTP（cDSP/NPU）**，但 HTP 在**瓦级**（真机整机实测 4.3–5 W，见 `hardware-power.md` §4）；
QNN 可把 ONNX 模型编译进 HTP，但功耗落在 W 级，**只适合触发后短时运行，不能常驻**。aDSP（SEE/LPAI 低功耗岛）第三方 App 拿不到（`fastrpc` attach audioPD 返回 `-EACCES`）。

---

## §2. 端侧预算表

> 功耗数字直接引用 SER 04 与 `hardware-power.md`，不另起一套。RTF / 内存 / 体积为模型自身属性。

| 项 | 约束 / 数值 | 说明 |
|---|---|---|
| RTF（常驻检测） | 流式 **≤ 0.1** | 漏斗①要求边录边判，RTF > 0.1 即积压 |
| 峰值内存 | 越小越好；DCASE 约束隐含 < 128K 参数级 | 决定能否进 MCU SRAM |
| 模型体积 | YAMNet 3.7M ~15 MB fp32 / ~4 MB INT8；CLAP 类 > 300 MB | 体积决定 OTA / 内存占用 |
| 功耗 · 常驻 | 目标 **≤ 25 mW**（≈ 3 %/天，`hardware-power.md` §0） | **实测只找到 212 mW – 2.5 W 这一档**（SER 04 §1） |
| 功耗 · 触发后短时 | 百 mW – W 级可接受，但必须短时 | `hardware-power.md` §4 |
| MMACs/秒 | YAMNet 72；EfficientAT-mn10 54；Karasin_JKU 29.4 | 越低越适合常驻 |

**结论（预算层面）**：除 DCASE 约束级（<30 MMACs/128K）学生模型外，主流 AudioSet tagging 模型（YAMNet 72 MMACs/s、EfficientAT 系列）
在"算力"上离常驻门槛尚有距离；而**功耗**才是决定性缺口——没有任何一条"端侧 AED 常驻 < 100 mW"的实测（SER 04 §1）。

---

## §3. proot 现状（本 Task 判定点）—— 常驻 AED 在 B 档是否可接受

沿用 A/B 两档（SER 04 §1）：

- **A 档 · 真端侧**（原生 App / aDSP / Sensing Hub）：mW 级常驻，但 laos 当前 proot 架构**拿不到**。
- **B 档 · proot 内**（CPU 推理）：`pip install` 即跑（ORT / sherpa-onnx / torch 均有 aarch64 wheel），但功耗按
  **通用 Linux 空闲 400–1000 mW** 计（`hardware-power.md` §3 实测），只适合触发后短时 + 批量，**绝不能常驻**。

**AED 专属问题**：常驻 AED 在 B 档是否可接受？

- 基线：proot 内任何 Python 进程醒着即 **400–1000 mW**（"常驻税"）。
- 增量：以 YAMNet（3.7M，72 MMACs/s）为例，连续 tagging 的 CPU 推理在 B 档下额外增加约数十至二百 mW（含 fbank 前处理）；
  总功耗约 **450–1200 mW**，远高于 ≤25 mW 的常驻预算（超 18–48 倍）。
- 相对 VAD 能量门：VAD 能量门是标量运算，几乎零增量；AED 即便最小档（Karasin_JKU 29.4 MMACs/s）也需 CNN 前向 + fbank，
  增量相对能量门**至少一个数量级**。

**判定**：在 B 档下，**常驻 AED 不可接受**。可行形态只有——**事件驱动**：由 VAD 能量门先放行"可疑片段"，
AED 仅对这些片段做二次确认（Task 8 推荐方案），整体功耗回到"短时运行"档。

---

## §4. edge 列回填说明

`01` / `02` 的 `edge` 列已按口径回填：

- **YAMNet**：`yes: TFLite Micro INT8（Cortex-M / 手机 NPU；Google AI Edge 官方导出路径）`——唯一有官方端侧导出路径的小型档模型。
- **EfficientAT / PANNs 系列**：`unknown(未找到公开转换案例)`——官方只发布 PyTorch 权重，无公开 INT8 / TFLite Micro 产物，如实标 unknown。
- 合法值说明：`unknown(未找到公开转换案例)` 是校验器接受的合法值（不报违规）。

---

## §5. 自检

1. **校验器覆盖**：本文件首列非 `模型` 的说明表按设计被 `table_lint` 跳过；不引入 schema 占位符。
2. **引用不重算**：§2 功耗数字全部来自 SER 04 与 `hardware-power.md`，无自造 mW。
3. **AED 专属判定已给**：§3 明确"B 档常驻 AED 不可接受，需事件驱动"，无含糊带过。
4. **runtime 覆盖**：§1 逐一点名 TFLite / TFLite Micro / ONNX Runtime Mobile / CoreML / NCNN / MNN / RKNN / QNN。
