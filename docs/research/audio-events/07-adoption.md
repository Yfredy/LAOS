# AED 落地 · 接回 AlwaysOnRec-HY4

> 收尾计划 Task 8。消费：`audio-events/2026-09-landscape.md`（Task 7 决策）、`05-edge-deployment.md`（A/B 档结论）、`06-multimodal.md`，以及 HY4 捕获链路代码（`aor/drivers/rec.py` / `aor/drivers/ear.py`）。
> 产出：一份「暂不引入」的论证 + 触发条件；**HY4 不改代码**（结论为「不加」，按 plan Task 8 Step 3 条件执行规则）。
> 本文不动 HY4 任何源码，147 项 unittest 保持全绿（Step 4 验证）。

---

## §1. 先读 HY4 现状（plan Step 1 三件事）

### 1.1 第一段常驻检测当前实现位置与判据（VAD 能量门）

`aor/drivers/rec.py` 的捕获回路：

- `rec_start(threshold_dbfs=-35.0, encoding="auto")` 创建 `StreamingVAD(SAMPLE_RATE, threshold_dbfs=threshold_dbfs)`（`rec.py:233`）。
- `_capture_loop()` 对每个 `vad.feed(data)` 返回的**有声段**才 `_save_segment()`（`rec.py:181-199`）。静音帧零存储、零后续算力。
- 这是 laos 四段漏斗的**第一段（常驻检测）**，且**零模型推理成本**——只做能量门，没有任何神经网络常驻运行。

> 关键事实：laos 当前的「常驻检测」= **VAD 能量门**，不是事件级检测。这与 `2026-09-landscape.md` §3 的「漏斗第一段从 VAD 能量门升级为事件级检测」问题直接对应。

### 1.2 AED 若接入：替换能量门，还是在其后作二次确认

- **推荐后者（二次确认）**：AED 只处理被 VAD 能量门放行的「可疑片段」，不替换能量门。理由（landscape §3）：能量门零成本、零常驻功耗；若用 AED 替换它，则 AED 必须**常驻**运行，功耗回到「模型持续推理」档，直接踩 landscape §3 的否决项。
- 二次确认路径下，AED 的运行形态是**触发后短时**（VAD 放行一段 → 跑一次 AED 前向），功耗回到「近实时」档而非「常驻」档。

### 1.3 `AOR_ASR_CHANNEL` 三值与新增分支命名

- `ear.py` 的 `channel()` 三值为 `stub` / `funasr` / `server`（`ear.py:71-73`），由 `AOR_ASR_CHANNEL` / `LAOS_ASR_CHANNEL` 环境变量决定。`DEFAULT_CHANNEL="stub"`。
- AED 是**独立的声学能力**，不属于 `ear.py` 的 ASR 通道（ASR 通道产出文本/语种/情感；AED 产出事件标签）。二者在架构上正交。
- 本结论为「暂不引入」，故**不命名新分支、不写新通道**；命名留给未来触发条件满足时再定（届时按 plan GC 11「落地点不得凭空命名」，由届时选型决定）。

---

## §2. 落地建议（plan Step 2 三件事）

### 2.1 在 proot Ubuntu 现状下（B 档）哪几款模型当下真能跑

B 档 = proot 内 CPU 推理，通用 Linux 空闲 **400–1000 mW**，拿不到 aDSP（fastrpc `-EACCES`）。据此：

| 模型 | 端侧可得（B 档含义） | 在 B 档 proot CPU 上 | 结论 |
|---|---|---|---|
| **YAMNet**（3.7M） | `yes: TFLite Micro INT8`（官方导出路径，Cortex-M / 手机 NPU） | TFLite Micro 主要面向 MCU/NPU；在 proot CPU 上走 TFLite CPU 后端也可跑，**RTF ≪ 1**，技术上可行 | 唯一当下能跑的候选，但落在 B 档 CPU，不是真端侧 aDSP |
| **EfficientAT** 系列（mn10 等） | `unknown(未找到公开转换案例)` | 仅 PyTorch 权重，无公开 INT8 转换产物 | 不可直接落地 |
| DCASE Low-Complexity 获奖系统（CP-Mobile / Karasin_JKU） | `unknown(未找到公开转换案例)` | 同上，只有 PyTorch | 端侧档的真实缺口 |

> 诚实结论：**B 档下 YAMNet 作为事件驱动二次确认，在 CPU 上技术可行**；但其余小型档全部 `unknown`，中型/大型档全不可端侧部署（见 `01`/`02`/`03` 的 `edge` 列）。

### 2.2 AED 输出与既有「粗粒度唤醒度」标签的职责边界

- HY4 `ear.py` 的 `classify_mood(dbfs, dur_ms)` 产出**唤醒度**标签（高唤醒 / 平稳 / 低唤醒 / 短促），来自 raw pcm 的 `dbfs`，零成本启发式（`ear.py:114-125`）。
- AED 事件标签（alarm / cry / doorbell / music …）是**正交维度**：一个是「这段多响/多短」，一个是「这段是什么事件」。
- 边界：**事件标签只进记忆的「事件」维度，且只改变「是否蒸馏」，不改变「是否留存原始音频」**（与即焚架构的咬合见 `2026-09-landscape.md` §5）。

### 2.3 不做什么（三条，逐条给理由）

1. **不做全 521 类常驻输出。** AudioSet 固定词表 521 类若常驻输出，长期事件序列聚合可推断**家庭结构与作息**（几点有人声/电视/水流/出门），属超范围画像；laos 的隐私红线只授权「自己的声音」，不授权「家庭行为画像」。
2. **不引入视觉模态。** A+V 在 AED 下的增量是「事件定位」而非「事件分类」（见 `06-multimodal.md` §3）；且视觉模态触发个保法 §26 / §28–30 + 799 号令第 17 条（视频保存 ≥30 日），与「原数据即焚」架构**根本互斥**。
3. **不让 AED 结果单独触发留存。** 事件标签只能改变「是否蒸馏」（是否把这段文本/事件写进记忆），**不能**改变「是否留存原始音频」——否则即焚被绕过，隐私设计失效。

---

## §3. 落地结论（plan Step 3 条件执行）

**结论：暂不引入常驻 AED 通道，也不在当前 B 档引入事件驱动 AED 二次确认通道；维持 VAD 能量门为唯一第一道常驻检测；HY4 不改代码。**

> 口径说明（与 landscape 的衔接）：landscape §4 决策树在「B 档 · 非常驻」分支曾给出「VAD 能量门 + 事件驱动 AED（YAMNet TFLite Micro，触发后短时）」的推荐；但 landscape §3 阈值的三个条件（① 走出 proot 拿 A 档；② 事件类别固定；③ 接受事件标签只改蒸馏不改留存）与 §2 中文场景空白，使该推荐在**当前 B 档 + 中文环境**下站不住——YAMNet 的 527 类英文词表对中文特定事件（电动车报警器 / 麻将 / 广场舞 / 燃气灶报警器）召回低、误报高，而 VAD 能量门已零成本覆盖「有无声学活动」这个真正需要的判据。**落地取「暂不引入」，并记录该推翻。**

### 触发条件（满足任一档组合后重新评估）

| 条件 | 说明 |
|---|---|
| ① 走出 proot 拿 A 档 | 原生 App / aDSP / Sensing Hub（mW 档），而非 proot CPU（400–1000 mW） |
| ② 事件类别固定或自采中文微调 | 目标事件固定（小型 tagging 模型可覆盖），或针对中文特定事件自采百级样本微调 YAMNet/EfficientAT 分类头（缓解 §2 中文空白） |
| ③ 接受事件标签只改蒸馏不改留存 | 事件标签永远不能触发原始音频留存，否则即焚被绕过 |

**只要 ① 不成立（当前 B 档）且 ② 未做中文微调，结论维持「暂不引入」。**

---

## §4. HY4 测试门禁（plan Step 4）

无源码改动，147 项 unittest 保持全绿。执行（收尾末步统一验证）：

```
cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4
C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t .
```

预期：`Ran 147 tests ... OK`。

---

## §5. 速览版指针（plan Step 5）

`docs/research/2026-09-11-aed-agc-model-landscape.md` 头部已含 AED / AGC 双指针（Task 16  consolid 时写入），AED 部分指向 `docs/research/audio-events/`，本文为落地论证。原文 §8 文献跟踪保留不动。

---

## §6. 自检

1. **结论明确**：§3 给「暂不引入」单一结论，未骑墙；并显式记录与 landscape §4 推荐分支的推翻关系。
2. **HY4 现状已读**：§1 三件事（VAD 能量门位置/判据、二次确认而非替换、AOR_ASR_CHANNEL 不受影响）均落到具体代码行。
3. **不做什么三条齐全**：§2.3 每条带理由（超范围画像 / 合规与即焚互斥 / 不绕过即焚）。
4. **中文场景空白已承接**：§3 触发条件 ② 直接承接 `2026-09-landscape.md` §2。
5. **无代码改动**：本文为纯论证，HY4 147 测试不受影响（Step 4）。
