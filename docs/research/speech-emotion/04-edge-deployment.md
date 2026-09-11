# 端侧部署轴：真端侧 vs proot 内可行

> 口径来源：[`00-taxonomy-and-metrics.md`](00-taxonomy-and-metrics.md)（`edge` 列三值定义、12 列 schema、三条红线）。
> 姊妹篇：[`01-small-models.md`](01-small-models.md) / [`02-medium-models.md`](02-medium-models.md) / [`03-large-models.md`](03-large-models.md)（规模轴）、
> [`../always-on-recording/hardware-power.md`](../always-on-recording/hardware-power.md)（功耗阶梯，**本文只引用、不重算**）。
> 本文回答一个问题：**「端侧可部署」在 laos（Android + proot Ubuntu + Termux）语境下到底是什么意思，哪些情感模型真的落得进去。**
> 表格 schema 由 `scripts/check_ser_table.py` 机器校验，本文的非 12 列表格不归它管。

---

## 一句话结论

**「端侧可行」在 laos 语境下不是一个布尔值，而是两个互斥的档位：**

- **A 档 · 真端侧（原生 App / aDSP / Sensing Hub）**：mW 级常驻。但普通第三方 App **拿不到 aDSP 的低功耗岛**——内核 `fastrpc` 驱动对未授信进程 attach 音频 PD 直接返回 `-EACCES`；第三方 App 能自由使用的是 **HTP（NPU）**，而 HTP 在**瓦级**。
- **B 档 · proot 内可行（CPU 推理）**：当下 `pip install` 就能跑（ORT / sherpa-onnx / torch 都有官方 aarch64 wheel），但功耗按「通用 Linux 设备空闲 **400–1000 mW**」计，**只适合触发后短时运行与批量处理，绝不能常驻**。

支撑这个结论的三条最硬证据：

1. **功耗找不到一条反例。** 连 Edge TPU 上 **1.8 MB** 的 INT8 情绪模型连续推理都是 **2.5 W**（arXiv 2510.18036）；手机 CPU 上 7.6 MB 的 INT8 情绪模型单次 38.2–52.6 mJ ≈ **212–224 mW**（ACI 2025，同行评审）。**未检索到任何一条「端侧声学情感识别做到 <100 mW 常驻」的实测。**
2. **中型档的门槛不是时延，而是内存。** WavLM-base+（95M）在骁龙 8 Gen 3 的 NPU 上跑完 20 s 音频只要 251 ms（RTF 1.26×10⁻²），但**峰值内存报到 1–1413 MB**（Qualcomm AI Hub 官方 profile）。「95M 参数 ≈ 几百 MB 内存」的直觉是错的。
3. **wav2vec2 / HuBERT / WavLM 家族没有公开的端侧转换案例。** TFLite 与 CoreML 的官方导出器把它们列在**已知不支持清单**里；AI Hub 上只有 WavLM-Base-Plus 一个条目，且**只有 float 档，没有 w8a8 / w8a16**——而同一站点上的 YAMNet（纯 CNN）w8a8 / w8a16 档齐全。

---

## 读法（三条，适用于本文所有表格）

1. **跨平台不可比。** 每张表都带「平台 / 计算单元」列。**不同行的数字不许相减、不许算倍数**——骁龙 8 Elite Gen 5 的 NPU 与 Raspberry Pi 4B 的 Cortex-A72 之间差的不是软件优化，是硬件类别。同一张表内也只有**同一平台、同一运行时、不同精度**的行可以直接比。
2. **Qualcomm AI Hub 的 profile 不测功耗**，且它报的时延是「多次迭代里的最小观测值」，输入数据只生成一次并循环复用，**不含前处理（log-mel / fbank）与 VAD 开销**（[官方工作原理](https://app.aihub.qualcomm.com/docs/zh_TW/hub/howitworks.html)）。把它当**模型前向的下界**读，不要当端到端延迟。
3. **可信度分级**：`官方` = 厂商/平台方自己跑的 profile 或官方文档 ｜ `同行评审` = 期刊/会议/MLCommons 审核 ｜ `二手实测` = 可核验的第三方记录 ｜ `未证实` = 孤证或推论 ｜ `本仓库内部` = laos 既有文档里的记录，**不是公开证据**。

---

## §1 端侧预算：先把目标值立出来

预算目标分两类：**外部引用**（功耗，直接取自 `hardware-power.md` 已建立的阶梯）与**本项目自定**（RTF / 内存 / 体积，无外部标准可用，已标注）。

| 维度 | 预算目标 | 目标口径来源 | 实测现状（出处见 §4） | 判定 |
|---|---|---|---|---|
| **RTF**（流式，16 kHz） | **≤ 0.1** | 本项目自定（计划 Task 5 Step 2） | 小型纯 CNN（YAMNet 级）：NPU **1.0×10⁻⁴**、中端 CPU **6.4×10⁻⁴**；中型 WavLM-base+：NPU **1.3×10⁻²**、CPU **7.1×10⁻²–2.85×10⁻¹** | 小型 ✅；中型 **看跑在哪个核** |
| **峰值内存** | 常驻进程 **≤ 100 MB** | 本项目自定 | YAMNet **0–37 MB**；DistilHuBERT int8 **23 MB（体积）**；WavLM-base+ **1057–1597 MB** | 小型 ✅；中型 ❌ |
| **模型体积** | MCU 档 ≤ 几百 KB；手机常驻 ≤ 50 MB | 本项目自定（对照 laos 已跑通的 TIM-Net int8 **0.4 MB** / 蒸馏版 **~174 KB**） | YAMNet int8 ≈ **4 MB**；SenseVoice-Small int8 **229–254 MB** | 小型 ✅；中型 ❌（仅触发式可接受） |
| **功耗 · 常驻** | **≤ 25 mW**（≈ 3 %/天） | `hardware-power.md` §0（5000 mAh × 3.85 V 折算） | 实测只找到 **212 mW – 2.5 W** 这一档 | ❌ **全档不达标** |
| **功耗 · 触发后短时** | 百 mW – W 级可接受，**但必须短时** | `hardware-power.md` §4 | 同上 | ✅ |
| **量化精度** | INT8 相对 fp32 无明显掉点 | 本文 §4.4 | 同行评审证据 **0.88 → 0.88**（CMAF-Net）；INT4 崩（Conformer WER **15.94 → 38.49**） | INT8 ✅；**INT4 ❌** |

### 1.1 功耗阶梯（直接引用，不另起一套）

来源：[`hardware-power.md` §6 总表](../always-on-recording/hardware-power.md)。

| 级 | 功耗 | 对应什么 | 与本文的关系 |
|---|---|---|---|
| ① 定制 ASIC | 0.047–1 µW | 学术 VAD / AAD | 非货架，不参与选型 |
| ② 专用音频 NPU | **140 µW** | Syntiant NDP120 | 常驻检测的地板 |
| ③ 手机传感中枢 / aDSP | 官方口径 **<1 mA** | **laos `<5 mW` 目标所在** | **第三方 App 拿不到**（§2.3） |
| ④ 通用 MCU / AP | **26–50 mW** | ESP32-S3 持续监听 | 走出 proot 后的现实档 |
| ⑤ 通用 Linux 空闲 | **400–1000 mW** | **proot Ubuntu 现状** | 本文 B 档 |
| ⑥ 手机 NPU 持续推理 | **1–4 W**（真机整机实测 4.3–5 W） | 第三方 App 能拿到的 HTP | 本文 A 档的实际上限 |
| ⑦ SD 卡落盘 | **17–70 mW** | 漏斗② | 比"听"贵 1–2 个数量级 |

**情感识别的实测功耗落在 ④⑤⑥ 之间**，具体位置由「跑什么核」和「跑多频繁」共同决定，**与模型大小弱相关**——这是本文 §4.3 的核心发现。

---

## §2 proot 现状：「端侧可行」必须拆成两档

> 调研时间：2026-09-12 ｜ 上游结论：[`../always-on-recording/hardware-power.md`](../always-on-recording/hardware-power.md)
> 本文不重新论证功耗阶梯，只做一件事：**把"端侧可行"这句话拆成两档，并为每一档找出现实中真能跑的组合**。所有功耗数字直接引用 hardware-power.md 并标注出处。
> 可信度标记：**官方** = 厂商/上游项目文档；**可核验实测** = 有原始数据或复现步骤；**社区传闻** = 论坛/博客/二手汇编；**未证实** = 只有孤证或推论。

---

### 2.0 一句话结论

「端侧可行」在 laos 语境下不是一个布尔值，而是**两个互斥的档位**：

- **真端侧（原生 App / aDSP / Sensing Hub）**：mW 级常驻，但必须走出 proot 做成原生 App；而普通第三方 App 能拿到的只有 **HTP（cDSP/NPU）**，拿不到 **aDSP 的 SEE/LPAI 低功耗岛**——这是内核 `fastrpc` 驱动的硬性权限隔离，不是工程技巧能绕过的。
- **proot 内可行（CPU 推理）**：当下就能跑，runtime 生态比预想的完整（ORT / sherpa-onnx / torch 都有官方 aarch64 wheel），但功耗按 hardware-power.md §3 的"通用 Linux 设备空闲 **400–1000 mW**"计（[来源](https://besjournals.onlinelibrary.wiley.com/doi/abs/10.1111/2041-210X.12955)，引自 hardware-power.md §3），只适合"触发后短时运行 + 批量处理"，**绝不能常驻**。

---

### 2.1 先对齐：QNN 在 laos 既有真机资料里的真实状态

先厘清既有资料到底证明了什么，避免后面的推理建立在空中楼阁上。

#### 2.1.1 状态表（全部来自本仓库既有文件）

| 项目 | 既有资料的说法 | 真实状态判定 | 可信度 | 来源 |
|---|---|---|---|---|
| QNN/QAIRT 版本与位置 | QAIRT **2.47.0.260601**，`lib/aarch64-android/`（Android 上 QNN 运行时：libQairtHtp.so + hexagon v68…v81 stub） | 已在本地工作区，AP 侧用户态库就绪 | 本仓库内部记录 | [2026-09-09-qnn-real-os-integration.md §二.4](../2026-09-09-qnn-real-os-integration.md) |
| 目标硬件 | 骁龙 **8 Elite（SM8735 "Bonito"，Hexagon v73M）** 的 **Audio DSP** | 目标是 aDSP，不是 HTP | 本仓库内部记录 | 同上 §一 |
| 模型 | TIM-Net **34,671 参数 / 0.4 MB**；LIGHT-SERNET ~460K；蒸馏学生版 ~**174 KB .eaix**；输入 `[1,1,479,26]`（MFCC 479 帧 × 26 维） | 极小模型，7 分类 | 本仓库内部记录 | 同上 §一 |
| 转换链路 | Keras → 4D SavedModel → ONNX → **QNN int8**（QAIRT 2.47）→ `timnet.cpp/.bin/.json` 或 `.eaix` → SCons 编入 SEE 镜像 | **转换成功**，但踩了 **7 个算子兼容坑**（reverse→gather、Lambda→标准算子、causal→ZeroPadding2D、1D→4D、SpatialDropout 移除、expand_dims→Reshape、环境隔离） | 本仓库内部记录（过程可复现） | 同上 §一.4 |
| 精度 | EMO-DB **70.28%**（5 折） | 有 | 本仓库内部记录 | 同上 §一 |
| 推理耗时 | **QNN CPU 推理 ≈ 6 ms** | ⚠️ 这是**转换期在 CPU 后端上测的数**，不是真机 aDSP/LPAI 实测 | 本仓库内部记录（口径需澄清） | 同上 §一 |
| 真机闭环 | 已跑通：laos 面板 → `npu.infer` → adb forward 8900 → `TimnetLpaiApp`（Kotlin）→ `EmotionClassifier` JNI → QNN LPAI/ADSP → 7 类概率 + 真实延迟回传；APK 构建成功于 **2026-09-09** | **链路跑通 = 真**，形态是 **原生 App + adb 调试桥** | 本仓库内部记录（有 runbook 与端点清单） | [qnn-real-device-runbook.md](../qnn-real-device-runbook.md) |
| 实测数字（latency / 内存 / 功耗 / 转换成功率） | 两份文件**均未记录** | **未检索到**：没有 on-device 的延迟、常驻内存、功耗、转换成功率的实测值 | — | 同上（全篇无数字） |

#### 2.1.2 与 hardware-power.md 的冲突点（明确指出，不和稀泥）

**冲突 A（表面冲突，实际一致，但表述会误导）：**
`qnn-real-device-runbook.md` 宣称"真实硬件闭环"跑通了 ADSP/LPAI 情感识别，而 hardware-power.md §5 说"laos 目前在真机上**拿不到** aDSP/LPAI"。
→ **判定：不矛盾，反而互为印证。** runbook 的闭环里，推理发生在 **原生 Android App（`com.timnet.lpai`）的 JNI 层**，proot 里的 Python 全程只扮演"发 HTTP 请求的客户端"。也就是说，这条链路**已经走出了 proot**——它正是 hardware-power.md §7.5 建议的那条路的一次实现。真正的限定是：它是一个 **adb forward + PC 侧 laos 面板** 的调试形态，不是可独立常驻的手机 App。

**冲突 B（真冲突，必须点破）：两份文件把两条不同的硬件通路混写成了一个东西。**
- `qnn-real-device-runbook.md` 写的是 "**QNN LPAI / ADSP**"；
- `2026-09-09-qnn-real-os-integration.md` 里，aDSP 侧的运行时其实是 **SEE + eAI（`eai_init / eai_execute`，`EAI_PROHIBITED_LPI_REQUEST`）**，而 **QNN/QAIRT 的 `libQnnHtp.so` 走的是 FastRPC 到 HTP（cDSP/NPU）**。
→ 这是**两个不同的处理器、两套不同的运行时、两种完全不同的权限模型**。§2.3 会证明：这个区分不是咬文嚼字，它直接决定"普通 App 能拿到哪一档"。

**冲突 C（口径冲突）："QNN CPU 推理 ≈ 6 ms" 被当成了性能证据。**
这是转换流程中 QNN **CPU 后端**的数（且大概率在 PC 上），既不是 aDSP/LPAI 实测，也不是 HTP 实测。按输入 3 秒音频折算 RTF ≈ 0.002 只是**推算量级**，不能作为真机指标。→ **结论：QNN 在 laos 的真实状态是"链路跑通、性能未测"**，不是"性能达标"。

---

### 2.2 proot 内到底能跑什么：runtime 可用性表

**前提**：proot Ubuntu（proot-distro）是完整 glibc rootfs，aarch64 原生存取，**不走虚拟化**（ptrace 拦截系统调用 + 路径翻译，[来源](https://termuxtools.com/proot-distro-linux-termux)、[来源](https://sinapti.ca/post/es/linux-en-tu-android-sin-root-proot-distro-debian-y-la-termin-qhfxy31v)）→ **manylinux aarch64 官方 wheel 直接可装**。而**裸 Termux 是 Bionic libc，不是 glibc**，两者不能混为一谈——这是社区里最常见的踩坑点。

#### 表 ① proot / Termux 各 runtime 可用性对照

| Runtime | aarch64 官方 wheel | 裸 Termux（Bionic） | proot Ubuntu（glibc aarch64） | 实测性能（RTF / 速度） | 可信度 | 来源 |
|---|---|---|---|---|---|---|
| **ONNX Runtime**（CPU） | ✅ **官方发布** `manylinux_2_27_aarch64` / `manylinux_2_28_aarch64`，cp311–cp314，1.26.0 起（最新 1.27.0，2026-06-16） | 未检索到官方 Bionic 构建 | ✅ `pip install onnxruntime` 直接命中 aarch64 wheel | 未检索到手机端统一基准 | **官方** | [PyPI files](https://pypi.org/project/onnxruntime/1.26.0/#files) |
| **ONNX Runtime + QNN EP**（HTP） | ❌ **官方不为 aarch64 Linux 发布带 AI Engine Direct 的 wheel**；需下载第三方预编译 `onnxruntime_qnn-1.23.0-cp312-cp312-linux_aarch64.whl` 或自编译 | 未检索到 | 仅 aarch64 **Linux**（Dragonwing 等嵌入式板）可行；**Android/proot 形态未检索到可行案例** | 未检索到 | **官方**（高通文档） | [Qualcomm Dragonwing ONNX Runtime](https://dragonwingdocs.qualcomm.com/Ubuntu/ai-workflows/onnxruntime) |
| **TensorFlow Lite / tflite-runtime** | ⚠️ 有 aarch64 wheel（cp37–cp310，`manylinux_2_34_aarch64`），但**最后发布 2023-10-03（2.14.0），已停更** | 社区教程称 `pip install tflite-runtime` 可用 | ✅ 可装，但版本冻结在 2023 | 未检索到 | **官方**（PyPI）+ **社区传闻** | [PyPI tflite-runtime](https://pypi.org/project/tflite-runtime/2.8.0/)、[SkillFed 归档](https://skillfed.io/packages/tflite-runtime) |
| **LiteRT（ai-edge-litert）**——TFLite 的继任者 | ✅ Google 已把 TFLite 改名 LiteRT（2024-09-04），Python 包为 `ai-edge-litert`，2.2.0 提供 cp310–cp314 | 未检索到 | 未检索到（aarch64 wheel 存在性未证实） | 未检索到 | **官方**（Google）+ **社区汇编** | [LiteRT vs TFLite 迁移对照](https://www.bestblogs.dev/en/article/a7ce684a43) |
| **PyTorch** | ✅ **官方** linux aarch64 CPU wheel（`torch-2.3.1-cp39-cp39-manylinux_2_17_aarch64.manylinux2014_aarch64.whl` 等），通道 `https://download.pytorch.org/whl/cpu`；2.14 RC 明确列出 "Linux x86 **and aarch64**" | ❌ `import torch` 失败：`OSError: dlopen failed: library "libgomp.so.1" not found`（Termux 缺 OpenMP 运行时） | ✅ 可装可用（有完整 BLAS/LAPACK） | 未检索到手机端基准 | **官方** + **可核验实测**（Termux issue） | [PyTorch aarch64 wheel 清单](https://mirrors.aliyun.com/pytorch-wheels/cpu/)、[Arm 安装指引](https://learn.arm.com/install-guides/pytorch/)、[termux-app #2219](https://github.com/termux/termux-app/issues/2219) |
| **funasr（SenseVoice 官方推理框架）** | 纯 Python 包（`pip install -U funasr`），依赖 `torch>=1.13` + `torchaudio`；SenseVoiceSmall **330M 参数** | ❌ 同上，卡在 torch | ⚠️ **技术上可行**（torch aarch64 wheel 官方有），但 **laos 未做过 proot 实测**；唯一的 RTF≈0.01 是 **PC conda（torch 2.6.0+cu124）** 上的数，不是手机 | RTF≈0.01（**PC 端**，非手机） | **官方**（FunASR）+ 本仓库记录 | [FunASR](https://github.com/modelscope/FunASR)、[SenseVoice 模型卡](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)、本仓库 `docs/superpowers/plans/2026-09-10-ear-memory-diary.md` |
| **sherpa-onnx**（SenseVoice 端侧主路径） | ✅ **官方**发布 `manylinux2014_aarch64` / `manylinux_2_17_aarch64`（cp38–cp314，2026-09-10 的 1.13.8），**同时**发布 `android_24_arm64_v8a` wheel | 可用 android wheel | ✅ **aarch64 wheel 直接命中，无需编译** | SenseVoice int8（**8 MB**）社区口径 **RTF≈0.1**；RPi4B 实测 **RTF 0.28**；AX650 NPU 上 RTF **0.015**（NPU，非 CPU） | **官方**（wheel 存在）+ **社区传闻**（RTF） | [PyPI sherpa-onnx files](https://pypi.org/project/sherpa-onnx/#files)、[sherpa-onnx README](https://github.com/k2-fsa/sherpa-onnx)、[RTF 汇编](https://adg.csdn.net/6952387e5b9f5f31781b36ca.html)、[RPi4B 实测](https://agent.csdn.net/6a4e65b0662f9a54cb8bf451.html)、[AX650 实测](https://docs.m5stack.com/en/guide/ai_accelerator/llm-8850/m5_llm_8850_sherpa-onnx) |
| **llama.cpp / GGUF** | 无 wheel，需源码编译 | ✅ Termux 可编译（clang + cmake，可选 NDK / OpenCL+CLBlast） | ✅ 可编译 | 小米平板 5（Termux，Qwen2.5-0.5B Q4_K_M）**14 tokens/s**，首 token 3.4 s；8 GB 手机（Qwen2.5-3B Q2_K）**~5 tokens/s**；SD 8 Gen 2（llama-2-7B Q4_0，4 线程）**3.67 t/s** | **社区传闻**（有命令与日志，但无统一基准） | [Termux 编译教程与实测](https://github.com/MrDoe/llama.cpp-android-tutorial)、[Termux 部署实测](https://blog.csdn.net/weixin_35433448/article/details/156493366)、[8GB 手机长跑记录](https://www.hotmolts.com/post/running-an-ai-agent-on-a-phone-8gb-ram-termux-no-r-70dfad35-ab4a-4be4-a39e-6b952c1dafb2) |

#### 2.2.1 从表 ① 读出的三条硬事实

1. **proot 里的 CPU 推理栈是"开箱可用"的，不是"要自己造轮子"。** ORT、sherpa-onnx、PyTorch 三家都有**官方 aarch64 manylinux wheel**；proot Ubuntu 是 glibc 环境，`pip install` 直接命中。所以"`AOR_ASR_CHANNEL=funasr` 能不能在 proot 里跑起来"这个问题的答案是：**能装、大概率能跑，但代价是 GB 级内存（torch + SenseVoiceSmall 330M 参数）与数秒级模型加载**，且唯一的 RTF 证据来自 PC。
2. **同一件事用 sherpa-onnx 做，代价低一个数量级**：SenseVoice int8 只有 **8 MB**，不依赖 torch，aarch64 wheel 官方发布，且**一次前向同时吐出文本 + 语种 + 情感 + 事件标签**（`<|zh|> <|HAPPY|> <|Speech|>`，[来源](https://docs.m5stack.com/en/guide/ai_accelerator/llm-8850/m5_llm_8850_sherpa-onnx)）——对 laos 的漏斗③（即时蒸馏出文本与情绪）是**天然合拍的一个前向**。**这是 proot 档的首选组合。**
3. **proot 里拿不到 NPU，且不是"再编一下就行"。** ORT 的 QNN EP 在 aarch64 Linux 上要靠第三方预编译 wheel（高通自己的文档说官方不发），且面向的是 Dragonwing 这类嵌入式 Linux 板，**Android/proot 形态未检索到可行案例**；即便拿到 `libQnnHtp.so`，proot 里的进程仍是普通 App 权限（见 §2.3）。→ proot 档 = **纯 CPU**。

---

### 2.3 真端侧路径：最大障碍不是"能不能用 NPU"，而是"能用 NPU ≠ 能用低功耗岛"

#### 2.3.1 核心问题：普通第三方 App 到底能不能用 Hexagon NPU？

**答案要劈成两半，这是本节最重要的一条：**

| 目标 | 普通非 root 第三方 App 能否使用 | 证据 | 可信度 | 来源 |
|---|---|---|---|---|
| **Hexagon HTP（cDSP / NPU）** | ✅ **能**。无需 root、无需签名、无需白名单；条件是 SoC 在支持列表内（8 Gen 1+ / 8 Gen 2 / 8 Gen 3 / 8 Elite / X Elite 等）+ 模型为 **INT8 / INT16**（v69+ 可用 FP16） | 高通自家 **AI Hub Apps 就是普通 Android App**（要求 Android 11 / API 30+），明确列出 "CPU, GPU, **NPU (includes hexagon HTP)**" | **官方** | [qualcomm/ai-hub-apps](https://github.com/qualcomm/ai-hub-apps)、[AI Hub Models 硬件矩阵](https://github.com/qualcomm/ai-hub-models) |
| 同上，另一条路 | ✅ **能**。GenieX / llama.cpp 提供 **Android SDK（Kotlin, Maven Central）**，`llama_cpp` runtime 默认 pin 到 **HTP0** | 官方平台文档 | **官方** | [GenieX Platforms & runtimes](https://geniex.aihub.qualcomm.com/en/get-started/platforms/) |
| **aDSP 的 SEE / LPAI / 音频 PD**（laos `<5 mW` 目标所在） | ❌ **不能**。 | ① 内核 `fastrpc` 驱动：**"Third-party apps don't have permission to open the fastrpc device, so it is opened on their behalf by DSP HAL"**；未授信进程请求 signed PD 时 `is_session_rejected()` 直接拒绝并打印 *"Untrusted application trying to offload to signed PD"*；attach 到 rootPD / sensorsPD / **audioPD** 时返回 **`-EACCES`**（*"untrusted app trying to attach to privileged DSP PD"*）<br>② LKML 讨论明确：**"For all the available platforms, ADSP supports only signed modules. Unsigned modules (as well as signed) are supported by CDSP and GDSP subsystems."** | **官方**（内核邮件列表 / 补丁原文） | [LKML: misc: fastrpc: Restrict untrusted apk to spawn](https://lwn.net/ml/linux-kernel/20240508054250.2922-4-quic_ekangupt@quicinc.com/)、[LKML: ADSP 只支持 signed 模块](https://ns1.openwall.net/linux-kernel/2025/11/27/251) |
| **Sensing Hub（QSH）定制 sensor** | ❌ **不能**（无高通授权）。 | 高通原话：**"Source code of the low-power application digital signal processor (aDSP), including the QSH framework, is available only to licensed users with authorized access."** | **官方** | [Qualcomm sensing hub architecture](https://docs.qualcomm.com/doc/80-70029-7/topic/architecture.html) |

**因此，真端侧路径的最大障碍是：**

> **普通 App 能用的 NPU 是 HTP，而 HTP 不在 mW 档。**
> laos 的 `<5 mW`（Active <50 mW / LPI <5 mW）预算位置在 **aDSP 的 LPAI 低功耗岛**，而 aDSP **只接受 signed 模块**、第三方 App attach 音频 PD 直接 `-EACCES`；要进这个岛，必须走高通授权 + 厂商签名 + 编进 SEE 镜像这条路（`2026-09-09-qnn-real-os-integration.md` 里的 `sns_ai_timnet_sensor_instance_island.c` 正是这条路，它需要完整的 Hexagon SDK 与 SCons 专有工具链）。
> 而第三方 App 能自由使用的 **HTP**，功耗落在 hardware-power.md §4 的"持续包络 **1–4 W**、真机 NPU 解码实测整机 **4.3–5 W**"（[来源](https://arxiv.org/abs/2509.23324)，引自 hardware-power.md §4）——**比 mW 档高三个数量级**。

这与 hardware-power.md §2 的官方锚点（Sensing Hub 全部处理 **<1 mA**，[来源](https://www.qualcomm.com/media/documents/files/snapdragon-888-ai-blog-post-by-jeff-gehlhaar-vp-of-technology-hsin-i-hsu-senior-product-manager.pdf)）形成完整闭环：**mW 档的钥匙在 Sensing Hub / aDSP 手里，而这把钥匙不发给第三方 App。**

#### 2.3.2 QNN / AI Engine Direct 走 HTP 后端的实际条件

| 条件 | 具体要求 | 是否需要 root / 签名 | 来源 |
|---|---|---|---|
| SDK | Qualcomm AI Engine Direct（QAIRT）SDK；Android 侧 `aarch64-android/`（`libQnnHtp.so` + `libQnnHtpPrepare.so` + `libQnnHtpVxxStub.so` / `libQnnHtpVxxSkel.so`） | 否（需注册高通开发者账号下载） | [Qualcomm LiteRT 架构 / QNN delegate](https://docs.qualcomm.com/doc/80-70018-54SC/topic/arch.html) |
| Skel 版本匹配 | skel 库必须与 SoC 的 Hexagon 架构版本严格对应（V68 / V73 / V75 / V79 / V81…） | 否，但**不匹配直接失败** | [SECO NPU 文档](https://developer.seco.com/clea-os/scarthgap_2-05-00/npu/qcom-npu)、[llama.cpp snapdragon README](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/README.md) |
| 精度 | HTP **只接受量化模型**（INT8 / INT16；v69+ 支持 FP16）；不支持的层会自动回退 CPU | 否 | [AI Hub Models 精度矩阵](https://github.com/qualcomm/ai-hub-models) |
| 性能模式 | `htp_performance_mode`：`burst` / `balanced` / `power_saver` / `sustained_high_performance` | 否 | [ONNX Runtime GenAI QNN EP](https://mintlify.wiki/microsoft/onnxruntime-genai/acceleration/qnn) |
| 普通 App 部署 | 高通官方示例 App 要求 **Android 11 / API 30+**；无 root / 无签名要求 | **否** | [qualcomm/ai-hub-apps](https://github.com/qualcomm/ai-hub-apps) |

> 对照 laos 现状：laos 工作区里已有 **QAIRT 2.47.0.260601** 与 `aarch64-android` 运行时（[来源](../2026-09-09-qnn-real-os-integration.md)），所以"走 HTP"的物料是齐的；**缺的是把 HTP 换成 aDSP/LPAI 的那张授权门票**。

#### 2.3.3 NNAPI 现状：已被弃用，官方转向 LiteRT

| 事项 | 状态 | 来源 |
|---|---|---|
| NNAPI（NDK API） | **Android 15 起弃用**。Google 原话：*"Starting in Android 15, the Neural Networks API (NNAPI NDK API) is deprecated. The Neural Networks HAL interface continues to be supported and NNAPI drivers aren't affected by this deprecation."* Google 同时警告未来多数设备会回落到 CPU 后端，建议迁移 | [Android 15 变更说明（NNAPI deprecation 原文摘录）](https://ima.qq.com/wiki/?shareId=af6c9590711e61afdab250988af14ae1bf8386ed9c90151745006d5dfeeb0e10&action=openDetailDrawer)、[NNAPI 弃用与迁移解读](https://meetonfriday.com/posts/666bbf67/) |
| 官方替代 | **LiteRT**（= TensorFlow Lite 改名，2024-09-04）；新版 `CompiledModel` API 用 `Accelerator.NPU / GPU / CPU` 选择加速器，取代手写 delegate；NPU 页列出 Google Tensor、Qualcomm、MediaTek、Samsung、Intel | [LiteRT vs TFLite 迁移对照](https://www.bestblogs.dev/en/article/a7ce684a43)、[NNAPI→LiteRT 迁移实践](https://www.cnblogs.com/vincentson/p/20524700) |
| ONNX 侧的替代 | ONNX Runtime Mobile + **QNN Execution Provider**（骁龙） | [On-Device AI on Android 2026](https://www.forasoft.com/blog/article/neural-networks-on-android-369) |

→ **对 laos 的含义**：今天新写端侧推理代码，**不要走 NNAPI**；原生 App 路线的现实组合是 **LiteRT `Accelerator.NPU`（= QNN delegate）** 或 **ORT + QNN EP**，两者都只到 HTP。

#### 2.3.4 麦克风常开：Android 的 OS 约束（确认 hardware-power.md §5 并补最新状态）

| 约束 | 内容 | 状态 | 来源 |
|---|---|---|---|
| Android 14（API 34）+ | 创建 `microphone` 类型前台服务时**即时校验** `RECORD_AUDIO`；它是 while-in-use 权限 → **App 在后台时创建直接抛 `SecurityException`**。`PermissionChecker.checkSelfPermission()` **无法**规避（后台也返回 `PERMISSION_GRANTED`） | **确认有效，且 Android 15/16 未见放宽** | [官方：从后台启动前台服务的限制](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start) |
| 启动时机 | 必须在**有可见 Activity 时**调 `Context.startForegroundService()` / `bindService()`；`BOOT_COMPLETED` 属于"后台启动限制"的豁免项，但**不属于** while-in-use 权限限制的豁免项 → **开机自启的常驻录音不合法** | 确认 | 同上 |
| Android 12（API 31）+ | 后台启动 FGS 抛 `ForegroundServiceStartNotAllowedException` | 确认 | 同上 |
| Android 15+ 附加 | 依赖 `SYSTEM_ALERT_WINDOW` 豁免时，还必须有**可见悬浮窗** | 收紧 | 同上 |
| 补充路径（非 proot） | Android 16 内置 **Linux Terminal**（AVF/pKVM 上的 Debian VM）；但 VM 与主机隔离，**外设（摄像头/麦克风）需额外直通层或可能被禁止**；Terminal 自身 manifest 含 `RECORD_AUDIO` 但**麦克风直通可用性未证实** | **未证实** | [AVF 隔离性分析](https://ivonblog.com/en-us/posts/termux-vs-android-linux-terminal)、[Android 16 Linux Terminal 评测](https://www.makeuseof.com/used-new-linux-terminal-on-android-impressed/)、[Terminal APK manifest 摘要](https://appteka.store/apps/246r287845) |

---

### 2.4 表 ②：真端侧 vs proot 内，两档对照

| 维度 | **A 档：真端侧**（原生 App / aDSP / Sensing Hub） | **B 档：proot 内**（CPU 推理） |
|---|---|---|
| **功耗档位** | Sensing Hub 官方 **<1 mA**（≈mW 级）；laos 目标 Active <50 mW / LPI <5 mW。**但第三方 App 只能到 HTP**：持续包络 1–4 W，整机实测 4.3–5 W | **400–1000 mW**（通用 Linux 设备空闲档） |
| 折算耗电 | mW 档 ≈ **0.62 %/天**（5 mW）｜HTP 档 ≈ 不可能常驻 | **25 %/天**（200 mW）起 |
| 功耗来源 | [hardware-power.md §2](https://besjournals.onlinelibrary.wiley.com/doi/abs/10.1111/2041-210X.12955) 的 Sensing Hub 锚点、[hardware-power.md §4](https://arxiv.org/abs/2509.23324) 的 HTP 实测 | **同上，§3**（AudioMoth 论文：跑 Linux 的模块化设备空闲 400–1000 mW） |
| 谁能用 | aDSP/LPAI **需高通授权 + 厂商签名**；HTP **普通 App 可用（无 root / 无签名）** | 任何人，`pip install` 即可 |
| 工程形态 | 原生 Android App + JNI/HAL/FastRPC（laos 已有 `TimnetLpaiApp` 原型） | proot Ubuntu + Python，现状即可 |
| 麦克风合法性 | 必须是常驻前台服务 + 常驻通知；**必须在前台可见时启动**，不能 BOOT_COMPLETED 自启 | 同左（Termux 也受同一套 FGS 约束）+ 关屏即休眠，需 `termux-wake-lock`（[hardware-power.md §5](../always-on-recording/hardware-power.md)） |
| **当下真能跑的组合** | **TIM-Net int8（34,671 参数 / 蒸馏版 ~174 KB .eaix）→ 骁龙 8 Elite aDSP/SEE LPAI → 原生 App `TimnetLpaiApp` + JNI**。laos 已跑通 HTTP→JNI→QNN LPAI 闭环并回传 7 类概率与真实延迟（2026-09-09 APK）；**无 on-device RTF / 功耗实测**（唯一耗时数 ≈6 ms 是 CPU 后端推算） | **sherpa-onnx 1.13.8（官方 `manylinux2014_aarch64` wheel）+ SenseVoice-small int8（8 MB）→ proot Ubuntu aarch64 CPU**。一次前向同时给出文本/语种/情感/事件；社区 RTF **0.1–0.3**（8 MB int8 口径 0.1，RPi4B 实测 0.28） |
| 同上，第二条可选路径 | **llama.cpp Hexagon/HTP 后端**：Llama-3.2-1B Q4_0 在骁龙 8 Elite（Hexagon v79）上 **pp128 = 169.42 ± 1.75 t/s，tg64 = 51.54 ± 1.13 t/s**（官方 bench 输出）；注意官方走的是 **adb + `/data/local/tmp`**，普通 App 形态请走 GenieX/lama.cpp Android SDK | **llama.cpp 在 Termux 上纯 CPU**：Qwen2.5-0.5B Q4_K_M **14 t/s**；Qwen2.5-3B Q2_K **~5 t/s**（社区实测） |
| 适用场景 | 漏斗①常驻检测（**只有拿到 aDSP/Sensing Hub 授权才成立**）；漏斗③的加速推理 | 漏斗③（触发后短时运行）+ 漏斗④批量转写（充电 / Wi-Fi 时） |
| **绝不能用于** | — | **①常驻检测**。任何醒着的 proot 进程都在 400 mW 量级，比 aDSP 方案贵 2–3 个数量级 |

---

### 2.5 落地判定（可直接写进结论章）

1. **`mic.always_on` 这一级在 proot 版里不成立**，与 hardware-power.md §7.5 的建议一致：proot 版只应支持 `mic.listen` / `mic.record`（显式触发），常驻需原生 App。
2. **`AOR_ASR_CHANNEL=funasr` 在 proot 里"能跑"，但不是最优解**：torch aarch64 官方 wheel 存在，proot Ubuntu 是 glibc 环境，缺的只是实测；代价是 GB 级内存与数秒加载。**改用 `sherpa-onnx` 通道（8 MB int8 SenseVoice，无 torch 依赖，官方 aarch64 wheel）可把常驻内存与启动时间压掉一个数量级，且一个前向同时产出文本与情绪**——这是漏斗③"即时蒸馏"最贴合的形态。
3. **"上 NPU"不等于"进 mW 档"**：第三方 App 的 NPU 上限是 HTP（瓦级），mW 档的 aDSP/LPAI 需要高通授权。laos 目前握有前者（QAIRT 2.47 + `TimnetLpaiApp`），后者是**授权问题，不是技术问题**。
4. **不要再投 NNAPI**：Android 15 起已弃用，新代码走 LiteRT `Accelerator.NPU` 或 ORT + QNN EP。
5. **两档都要遵守同一条 OS 红线**：常驻麦克风必须是"用户在前台显式开启后保持"的常驻前台服务 + 常驻通知，不能开机自启。

---

---

## §3 端侧推理 runtime 与量化路径

> 调研时间：2026-09-12 ｜ 上游结论：[`00-taxonomy-and-metrics.md`](00-taxonomy-and-metrics.md)（`edge` 列口径）、本文档 §2「proot 现状」、[`../2026-09-09-qnn-real-os-integration.md`](../2026-09-09-qnn-real-os-integration.md)
> 本文回答一个问题：**一个声音情感模型（尤指 wav2vec2 / HuBERT / WavLM 这类"卷积 + Transformer"编码器）从 PyTorch/HF 出发，能落进哪些端侧 runtime，量化路径走不走得通，落进去之后有多慢。**
> 可信度标记：**官方** = 厂商/上游项目文档或官方页面数字；**同行评审** = 期刊/会议论文；**二手实测** = 博客/社区/CSDN 等有步骤但无复现门槛的记录；**未证实** = 孤证或推论。
> 查不到的一律写"未检索到"，不留占位符。

---

### 3.0 一句话结论

> **没有任何一个 runtime 有公开的"wav2vec2/HuBERT 系情感模型 → 该 runtime"完整转换案例**；唯一与 SER 直接沾边的公开转换案例是 **emotion2vec 的 ONNX 导出**（FunASR PR #2359，导出的是帧级特征不是情感标签，[来源](https://github.co.uk/modelscope/FunASR/discussions/2151)）。
> 但**相邻音频编码器有硬数字**：高通 AI Hub 上 **WavLM-Base-Plus（95.1M，卷积+注意力音频编码器，与 wav2vec2/HuBERT 同构）** 在骁龙 8 Elite Gen 5 上 QNN_DLC **129.22 ms / 峰值内存 0–1144 MB（float）**、SD8Gen3 **227.39 ms**、QCS8275 **844.66 ms**（[来源](https://huggingface.co/qualcomm/HuggingFace-WavLM-Base-Plus/blame/main/README.md)）——**这是目前能拿到的、最接近"wav2vec2 家族能否跑在 Hexagon HTP 上"的实测证据，且全部是 float，w8a8/w8a16 行未检索到。**
> 对照 YAMNet（3.73M 纯 CNN）在同一批设备上 **96 μs – 0.7 ms**（[来源](https://aihub.qualcomm.com/models/yamnet)）：**卷积注意力量级 ~100 ms，纯 CNN 量级 ~0.1 ms，差三个数量级。**

---

### 3.1 表 ①：八个 runtime 横向对比

| Runtime | 主要平台 | 官方导出工具链（步数） | 精度支持 | Transformer/注意力编码器友好度 | 与 laos 的相关性 | 来源 |
|---|---|---|---|---|---|---|
| **TensorFlow Lite / LiteRT** | Android / iOS | Keras→SavedModel→`TFLite Converter`（2 步）；torch 侧需 `optimum-cli export tflite` 或 `onnx2tf`（3–4 步） | fp16 / int8 动态 / int8 全整 / int4（实验） | **差**：wav2vec2/HuBERT 官方导出器明确不支持（GroupNorm + 广播） | 中：Android 原生 App 默认栈，但 SER 模型进不去 | [optimum](https://github.com/huggingface/optimum)、[exporters 不支持清单](https://github.com/aidyai/exporters)、[onnx2tf 坑](https://github.com/PINTO0309/onnx2tf) |
| **TFLite Micro / LiteRT for Micro** | MCU（Cortex-M / ESP32） | 同上 + `xxd` 转 C 数组 + 固定 `tensor_arena`（3–4 步） | int8 为主，fp32 少数 | **极差**：算子子集极小，无动态分配 | 低（但给出"模型体积下限"的硬参照） | [官方概览](https://developers.google.cn/edge/litert/microcontrollers/overview) |
| **ONNX Runtime Mobile** | Android / iOS / 嵌入式 Linux | torch→ONNX→`convert_onnx_models_to_ort.py`（ORT format + minimal build）（3–4 步） | fp32/fp16/int8 动态/静态/int4(RTN) | **中**：算子最全，是注意力模型唯一"基本能跑通"的通用栈 | **高**：proot 档首选；也是 QNN EP 的宿主 | [ORT custom build](https://onnxruntime.ai/docs/build/custom.html)、[reduced-operator 配置](http://onnxruntime.ai/docs/reference/operators/reduced-operator-config-file.html) |
| **CoreML** | Apple（ANE / GPU / CPU） | torch→`coremltools.convert`（2 步）+ `palettize_weights` / `linear_quantize_weights` | fp16 / int8 线性 / 4–8 bit palettization / 混合 | **差**：Wav2Vec2 / HuBERT / SEW / WavLM / Data2VecAudio / UniSpeech 全部在已知不支持清单里 | 低（laos 目标是 Android） | [coremltools 工作流](https://apple.github.io/coremltools/docs-guides/source/opt-workflow.html)、[exporters](https://github.com/aidyai/exporters) |
| **NCNN** | ARM CPU / Vulkan GPU（含 RK3588） | torch→**pnnx**→ncnn（2 步）或 onnx→`onnx2ncnn`；量化 `ncnnoptimize`→`ncnn2table`→`ncnn2int8`（+3 步） | fp32 / fp16 / int8（KL / ACIQ / EQ），逐层混合 | **中偏低**：`F.layer_norm` 有支持，但 `LayerNormalization` 在 onnx2ncnn 路径报 not supported | 中：无 NPU 时的 ARM CPU 高性价比选择 | [ncnn int8 文档](https://github.com/Tencent/ncnn)、[pnnx 算子表](https://github.com/Tencent/ncnn/pull/3262) |
| **MNN** | ARM CPU / Vulkan / OpenCL；可挂 QNN、CoreML、NNAPI、HIAI | `MNNConvert -f ONNX --quantize INT8`（1–2 步）+ `quantized.out` | fp32 / fp16 / int8（KL / ADMM / EMA）/ int4（MNN-Transformer） | **中**：有专门的 MNN-Transformer 量化通道（int4/int8 per-channel/per-block） | 中：若走国产 NPU 或需要"一个 runtime 多后端" | [MNN 量化](https://juejin.cn/post/7598021081987268659)、[MNN-Transformer](https://www.besthub.dev/articles/mnn-transformer-efficient-on-device-large-language-and-diffusion-model-deployment-75815f40d39d) |
| **RKNN** | Rockchip NPU（RK3566/3576/3588） | `rknn.config()`→`load_onnx()`→`build(do_quantization)`→`export_rknn()`（4 步）；混合量化再 +2 步 | int8（asymmetric_quantized-8 / w8a8 / w8a16）/ fp16 / 混合量化 | **中**：官方点名"Transformer Attention"是混合量化里应保持 fp16 的敏感层 | 低（非骁龙）；但 sherpa-onnx 支持它，可作交叉验证 | [RKNN-Toolkit2 用法](https://blog.gitcode.com/13304c713ad67dddd45b949b681e382a.html) |
| **QNN / Qualcomm AI Engine Direct（QAIRT）** | **骁龙 HTP（cDSP/NPU）/ aDSP LPAI / GPU / CPU** | torch→ONNX→`qnn-onnx-converter`→`qnn-quantization-checker`→`qnn-context-binary-generator` / `qnn-model-lib-generator`（4–5 步）；或 ORT + QNN EP（3 步） | fp32 / fp16 / **int8（w8a8、w8a16）** / int4 权重 / 混合精度 | **中偏低，且"列出支持 ≠ 真的跑得通"**：Gelu/LayerNorm 在支持列表里，但 HTP 图形准备阶段会挂（见 §3.2.8.1）；**不支持动态 shape、不支持 Loop/If** | **最高**：laos 现状就是它（QAIRT 2.47 + 骁龙 8 Elite） | [QNN 后端库](https://docs.qualcomm.com/bundle/publicresource/topics/80-63442-10/backend.html)、[ORT QNN EP](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html)、[Ultralytics QNN](https://docs.ultralytics.com/zh/integrations/qnn) |

---

### 3.2 逐个 runtime

#### 3.2.1 TensorFlow Lite / LiteRT

| 项 | 内容 | 来源 / 可信度 |
|---|---|---|
| **算子覆盖** | **wav2vec2 / HuBERT / SEW 明确不支持**：官方导出器已知问题原文 *"Unsupported op for nn.GroupNorm (should be possible to solve), invalid broadcasting operations (will be harder to solve), and most likely additional issues"*；**WavLM**：*"Missing ops for _weight_norm, add_, full_like"*；**Data2VecAudio / UniSpeech / Speech2Text** 同样在不支持清单 | **官方**（[aidyai/exporters 已知限制](https://github.com/aidyai/exporters)） |
| 同上（实测报错） | `optimum-cli export tflite -m <wav2vec2>` 直接报 `KeyError: "wav2vec2 (tf_wav2_vec2_for_sequence_classification) is not supported yet with the tflite backend. Only ['onnx'] are supported."` | **二手实测**（[devhide](https://devhide.com/convert-hugging-face-audio-classifier-to-tflite-format-77892732)） |
| 转换旁路的坑 | `onnx2tf` 走 ONNX 中转的典型失败：① `ERROR: Unsupported ops: Counter({'OP_NAME': X})`；② `ValueError: Cannot take the length of shape with unknown rank`（**动态维度**，需 `-b`/`-ois` 固定）；③ NHWC/NCHW 不匹配（`-kt`/`-kat`/`-prf`）；④ int8 量化必须显式给 `--calibration_data_path`；⑤ 要求 Python ≥3.12 | **官方**（[onnx2tf README](https://github.com/PINTO0309/onnx2tf)） |
| **量化路径** | PTQ：`TFLite Converter` + `representative_dataset`（全整 int8）或 `optimizations=[DEFAULT]`（动态范围 int8，仅权重）；fp16 直接 `target_spec.supported_types=[tf.float16]`。**QAT**：`tensorflow_model_optimization` 的 `quantize_model` + `QuantizeAwareTraining`。**Optimum 侧**：`optimum-cli export tflite -m <m> --sequence_length N --quantize int8-dynamic` | **官方**（[optimum README](https://github.com/huggingface/optimum)） |
| Optimum 能力矩阵（TFLite） | PTQ 动态 ✔ ｜ PTQ 静态 ✔ ｜ **QAT N/A** ｜ FP16 ✔ | **官方**（同上） |
| **SER 转换案例** | **未检索到** wav2vec2/HuBERT 系 → TFLite 的公开 SER 案例。相邻案例见 §3.3 | — |
| **导出工具链** | Keras 原生：SavedModel → `tf.lite.TFLiteConverter`（**2 步**）。PyTorch/HF：`optimum-cli export tflite`（**2 步**，但音频编码器大概率失败）或 `torch→onnx→onnx2tf`（**3 步**） | **官方** |

#### 3.2.2 TFLite Micro / LiteRT for Microcontrollers（内存现实）

| 项 | 内容 | 来源 / 可信度 |
|---|---|---|
| **运行时体积** | 核心运行时 **在 Arm Cortex-M3 上刚好装进 16 KB**；**无 OS、无动态内存分配、无文件系统**；仅支持 **TensorFlow 算子的一个有限子集** | **官方**（[LiteRT for Microcontrollers 概览](https://developers.google.cn/edge/litert/microcontrollers/overview)） |
| **张量竞技场** | 必须**预先静态分配**一块 `tensor_arena`（`MicroInterpreter` 构造时传入），大小不够直接 `AllocateTensors() failed`，且**没有运行时扩容机制** | **官方**（同上） |
| **典型可用 SRAM 量级** | 官方未给统一数字，只给"16 KB 核心运行时"这一个锚点。二手口径：ESP32 上 arena **80–120 KB**、运行时 **10–20 KB**，KWS 模型占用 arena **30–50 KB**，总计 **50–200 KB**，约支持 **60–80 个算子** | **二手实测**（[ESP32 TFLite 指南](https://www.foresthub.ai/resources/guides/how-to-run-tensorflow-lite-on-esp32)） |
| **大一点的例子** | Arm Ethos-U + Vela 的部署示例：Total SRAM _used = **146.31 KiB**（外加 ≥2 KiB 的 TFLM 开销），`ACTIVATION_BUF_SZ` 从 **0x00200000（2 MiB）** 调到 **0x00400000（4 MiB）** | **二手实测**（[Alif ML 评估套件 wiki](https://deepwiki.com/alifsemi/alif_ml-embedded-evaluation-kit/8.2-model-integration-and-deployment)） |
| **→ 能装多大的模型** | 量级判断：MCU 档现实上限约 **几百 KB 级权重 + 百 KB 级激活**。对照 laos 现有 **TIM-Net 34,671 参数 / 0.4 MB int8、蒸馏版 ~174 KB .eaix**，正好落在这个档内；而 **wav2vec2-base（~95M）int8 约 95 MB**，**差 2–3 个数量级，物理上不可能** | **本仓库内部**（[2026-09-09-qnn-real-os-integration.md](../2026-09-09-qnn-real-os-integration.md)）+ 本文推算 |
| **量化路径** | **只有 int8（训练后全整量化）现实可用**；fp32 在 MCU 上基本不可接受（体积 ×4 + 无硬浮点）。QAT 可用但需 TF 侧训练改造 | **官方**（同上） |
| **SER 转换案例** | 有（极小模型）：LSTM SER（RAVDESS/TESS/SAVEE）1.5 MB → TFLite 515 KB → **int8 150 KB**，准确率 **72.88% → 73.06%**，100 样本推理 **4.391 s → 0.299 s** | **未证实**（[GitHub 项目](https://github.kazgu.com/Kashish0212/Speech-Emotion-Recognition-TinyML)） |
| **导出工具链** | Keras → TFLite → `xxd -i` 生成 C 数组 → 编进固件（**3–4 步**） | **官方** |

#### 3.2.3 ONNX Runtime Mobile

| 项 | 内容 | 来源 / 可信度 |
|---|---|---|
| **算子覆盖** | ONNX 标准算子覆盖**最全**，是注意力类模型唯一"基本能跑通"的通用栈（这也是 FunASR 把 emotion2vec 导出成 ONNX 而非 TFLite 的原因）。代价是**默认包体大** | 本文判断（基于 [FunASR PR #2359](https://github.com/modelscope/FunASR/commit/3530688e0a1b1dfbb22dcd3324db97be5bbc0d9b)） |
| **体积** | ORT Mobile **默认约 10–15 MB**，用 minimal build 可压到 **约 4–5 MB** | **二手实测**（[HF 博客](https://www.huggingface.co/blog/tugrulkaya/running-large-transformer-models-on-mobile)） |
| **Minimal build 流程（官方）** | ① `convert_onnx_models_to_ort.py <dir>` 生成 `.ort` 与 **`required_operators.config`**（加 `--enable_type_reduction` 则生成 `required_operators_and_types.config`）；② 构建时 `--minimal_build --include_ops_by_config <config> --enable_reduced_operator_type_support --disable_ml_ops --disable_exceptions --android_cpp_shared --config MinSizeRel` | **官方**（[ORT custom build](https://onnxruntime.ai/docs/build/custom.html)、[reduced-operator 配置文件](http://onnxruntime.ai/docs/reference/operators/reduced-operator-config-file.html)） |
| **量化路径（PTQ）** | `optimum-cli onnxruntime quantize --avx512 --onnx_model X -o Y`；动态量化 / 静态量化（需校准集）均支持 | **官方**（[optimum](https://github.com/huggingface/optimum)） |
| **int4（RTN）** | 支持 RTN int4，并用 `int4_accuracy_level` 权衡：**1 = 偏精度，4 = 偏性能** | **官方**（同上） |
| **QAT** | Optimum 能力矩阵里 ONNX Runtime 的 QAT 项为 **N/A**（不支持）；FP16 ✔ | **官方**（同上） |
| **端侧实测（官方）** | Phi-3-mini 经 int4 量化后跑在 **Galaxy S21** 上 | **官方**（[ORT blog: Accelerating Phi-3](http://onnxruntime.ai/blogs/accelerating-phi-3)） |
| **Optimum 对 wav2vec2/HuBERT** | `optimum-cli export onnx -m <model> --optimize O2 <out>` **可用**（ONNX 是 wav2vec2 家族唯一被支持的后端）；`--optimize O2` 会做算子融合（含 attention 融合） | **官方**（同上） |
| **SER 转换案例** | **未检索到**纯 SER 案例。**相邻**：emotion2vec ONNX（见 §3.3）；whisper 的 ONNX 导出仅支持 `feature-extraction` / `ASR` 任务，**不支持 `audio-classification`** | **官方**（[optimum](https://github.com/huggingface/optimum)）+ **二手实测**（[devhide](https://devhide.com/convert-hugging-face-audio-classifier-to-tflite-format-77892732)） |
| **导出工具链** | torch/HF → `optimum-cli export onnx` → `.ort` + minimal build（**3–4 步**） | **官方** |

#### 3.2.4 CoreML（Apple）

| 项 | 内容 | 来源 / 可信度 |
|---|---|---|
| **算子覆盖** | 与 TFLite 同病：**Wav2Vec2 / HuBERT / SEW / WavLM / Data2VecAudio / UniSpeech / Speech2Text** 全在已知不支持清单，原因同为 GroupNorm + 广播 + `_weight_norm` | **官方**（[aidyai/exporters](https://github.com/aidyai/exporters)） |
| **量化路径（官方三类工作流）** | ① **data-free**：palettization（8/6-bit；4-bit 支持 grouped-channel，`group_size` 32/16/8）、linear 8-bit；② **calibration-based**：128 个校准样本，激活 8-bit（官方称可改善 ANE 延迟）；③ **fine-tuning-based（=QAT）** | **官方**（[coremltools 优化工作流](https://apple.github.io/coremltools/docs-guides/source/opt-workflow.html)） |
| 关键 API | `cto.coreml.OpPalettizerConfig` / `OpLinearQuantizerConfig` / `OpMagnitudePrunerConfig`，作用函数 `palettize_weights` / `linear_quantize_weights` / `prune_weights`；4-bit 权重另有 `per_block`（64/32/16）模式 | **官方**（同上） |
| 精度上限的官方旁证 | Apple 自研端侧基础模型用 **2-bit 与 4-bit palettization 混合**，平均 **3.7 bits/weight** | **二手**（[aiwiki](https://aiwiki.ai/wiki/core_ml)） |
| **ANE 阻塞算子** | 动态 shape、**TopK、Scatter、GatherND**、自定义层、超大空间维度（>4096）、**奇数通道数**（建议取 8/16 的倍数）→ 会回退 GPU/CPU | **二手**（[coreml-optimizer 汇编](https://lobehub.com/it/skills/ckorhonen-claude-skills-coreml-optimizer)） |
| **SER 转换案例** | **未检索到** | — |
| **导出工具链** | torch → `coremltools.convert()` → 量化 API（**2–3 步**） | **官方** |

#### 3.2.5 NCNN（腾讯）

| 项 | 内容 | 来源 / 可信度 |
|---|---|---|
| **算子覆盖** | **pnnx** 路径（PyTorch 推荐）算子状态表显示 **`F.layer_norm` 与 `F.instance_norm` 已支持**；但 **onnx2ncnn 路径报 `LayerNormalization not supported yet`**（有具体踩坑案例：自定义 `LayerNorm2d_Sc`） | **官方**（[pnnx 算子表](https://github.com/Tencent/ncnn/pull/3262/commits/7679005a265ed4dd07733eb4c803ebb4d02b4cc0)）+ **二手实测**（[gitcode 博客](https://blog.gitcode.com/69a0f0a0680eca9b48585a3fa685cceb.html)） |
| 结论 | 走 NCNN **不要用 onnx2ncnn，用 pnnx**（从 torch 直转，避开 ONNX 算子翻译层的缺失） | 本文判断 |
| **量化路径（PTQ）** | 三步：`ncnnoptimize`（图优化 + fp16 存储）→ `ncnn2table`（校准，方法 **KL / ACIQ / EQ**）→ `ncnn2int8`（生成 int8 模型）。**不支持量化的层自动存 fp16** | **官方**（[ncnn quantized int8 inference](https://github.com/Tencent/ncnn/blob/master/docs/how-to-use-and-FAQ/quantized-int8-inference.md)、[deepwiki 汇编](https://www.deepwiki.com/Tencent/ncnn/8.2-post-training-quantization-tools)） |
| **混合精度** | 在 `.table` 里**把某一层的 weight-scale 行注释掉**，该层即保持非量化 | **官方**（同上） |
| **QAT** | **未检索到**官方 QAT 通道 | — |
| **实测** | RK3588 上 ResNet50 + Vulkan：**FP16 43.46 ms / INT8 24.80 ms** | **二手实测**（[CSDN](https://blog.csdn.net/m0_61864577/article/details/148031677)） |
| **SER 转换案例** | **未检索到** | — |
| **导出工具链** | torch → **pnnx** → ncnn（**2 步**），量化再 **+3 步** | **官方** |

#### 3.2.6 MNN（阿里）

| 项 | 内容 | 来源 / 可信度 |
|---|---|---|
| **量化路径（PTQ）** | ① 转换期：`MNNConvert -f ONNX --modelFile X --MNNModel Y --bizCode MNN [--quantize INT8 --calibrateDataset ... --calibrateType naive]`；② 转换后离线量化：`./quantized.out origin.mnn quan.mnn imageInputConfig.json`。校准方法 **KL / ADMM / EMA** | **二手实测**（[掘金](https://juejin.cn/post/7598021081987268659)、[CSDN](https://blog.csdn.net/gitblog_00639/article/details/152109018)） |
| 量化效果（官方口径） | EMA 量化 MobileNet V2：**精度损失 <1%，提速 1.5×** | **二手实测**（同上） |
| **Transformer 专用通道（MNN-Transformer）** | 支持 **int4 / int8** 权重、**channel-wise / block-wise** 量化、可导入 **GPTQ** 模型、支持**动态量化**与 **KV cache 量化**；已在 Qwen2-1.5B 等模型上验证 | **二手**（[besthub 汇编](https://www.besthub.dev/articles/mnn-transformer-efficient-on-device-large-language-and-diffusion-model-deployment-75815f40d39d)） |
| **后端** | CPU / Vulkan / OpenCL，并可挂 **QNN（高通）、CoreML、NNAPI、HIAI**——即"一个 runtime 覆盖多 NPU" | **二手**（[CSDN](https://blog.csdn.net/gitblog_00639/article/details/152109018)） |
| 实测（NPU 收益） | 骁龙 8 Gen 3 上 ResNet-50：CPU **550 ms** → NPU **379 ms** | **二手实测**（同上） |
| **算子覆盖** | **未检索到**官方的"Transformer 音频编码器算子支持矩阵"；MNN-Transformer 的存在说明注意力算子有解，但 wav2vec2 特有的 `GroupNorm` / `_weight_norm` 支持情况**未检索到** | — |
| **SER 转换案例** | **未检索到** | — |
| **导出工具链** | torch/onnx → `MNNConvert`（**1–2 步**），量化再 **+1 步** | **官方** |

#### 3.2.7 RKNN（Rockchip）

| 项 | 内容 | 来源 / 可信度 |
|---|---|---|
| **工具链（官方四步）** | `rknn.config(target_platform=..., mean_values=..., std_values=..., quantized_dtype='asymmetric_quantized-8'/'w8a8'/'asymmetric_quantized-16', quantized_algorithm='normal'/'mmse'/'kl_divergence', quantized_method='layer'/'channel', optimization_level=3)` → `rknn.load_onnx()` → `rknn.build(do_quantization=True, dataset=...)` → `rknn.export_rknn()` | **二手实测**（[gitcode 教程](https://blog.gitcode.com/13304c713ad67dddd45b949b681e382a.html)） |
| **QAT** | 走 QAT 时 `rknn.build(do_quantization=False)`（即板端不再做 PTQ） | **二手实测**（同上） |
| **混合量化** | `hybrid_quantization_step1` / `step2` + `model.quantization.cfg`，把**敏感层保持 fp16**。官方/教程点名的典型敏感层：**YOLO 检测头、Transformer Attention、第一层与最后一层** | **二手实测**（同上） |
| → **对本文的意义** | **"Transformer Attention 是量化敏感层"这条判断，是跨厂商共识（RKNN 文档与 QNN 实践都这么说）**，不是某一家的问题 | 本文判断 |
| **硬件** | RK3588 NPU **6 TOPS@INT8**；FP16 回退约 **1.5 TOPS**；算子支持清单见 `doc/05_RKNN_Compiler_Support_Operator_List_v1.6.0.pdf` | **二手实测**（同上） |
| **算子覆盖** | **未检索到** wav2vec2/HuBERT 系在 RKNN 上的算子支持实测 | — |
| **SER 转换案例** | **未检索到**。相邻：sherpa-onnx 的 SenseVoice 有 RKNN 路径，但存在**版本地雷**（RKNN **2.1.0** 报 *"Meet unsupported input dtype for gather"*；**2.2.0** 可用；**2.3.2** 段错误） | **二手实测**（[CSDN](https://blog.csdn.net/gitblog_00492/article/details/160735355)） |
| **导出工具链** | torch → ONNX → RKNN（**3 步** + 校准集） | **官方** |

#### 3.2.8 QNN / Qualcomm AI Engine Direct（QAIRT）—— 重点

##### 3.2.8.1 算子覆盖与真实的坑

**先说结论：QNN 的"支持列表"和"真跑得通"之间存在明显落差，落差集中在 `Gather` / `GELU` / `LayerNorm` / 动态 shape 这四处——而这四处恰好是 Transformer 的全部要害。**

| 算子 / 特性 | 官方状态 | 实际坑（有出处） | 来源 / 可信度 |
|---|---|---|---|
| `ai.onnx:Gelu` | ORT QNN EP 支持列表里**明确列出**（HTP） | 高通支持论坛：`qairt-accuracy-debugger --offline_prepare` 在 HTP 图准备阶段报 **`no properties registered for q::QNN_Gelu`**。根因被描述为 **HTP 后端比 CPU / 旧 SNPE DSP 严格**，当 HTP 的 memory tiler 无法处理该 shape/dtype 组合（例如某些 FP16 或动态 shape 配置）时 Gelu 直接失败 | **官方**（[ORT QNN EP 算子表](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html)）+ **二手实测**（[Qualcomm 支持论坛](https://mysupport.qualcomm.com/supportforums/s/question/0D5dK00000I4PnDSAV/)） |
| `ai.onnx:Gather` | 支持，但**"仅支持正索引"** | 同一帖里 HTP 图准备报 **`could not create op: q::Gather`** | **官方**（同上）+ **二手实测**（同上） |
| `ai.onnx:LayerNormalization` | 支持列表里有（HTP） | ExecuTorch QNN 后端 PR #18990 专门修 LayerNorm：原本的 `LayerNormVisitor` 只匹配 `aten.layer_norm.default`，但 **PyTorch 会分解（decompose）成 `aten.native_layer_norm.default`**；且 `elementwise_affine=False`（weight/bias 为 None）时 QNN x86_64 运行时崩 `AttributeError: 'NoneType' object has no attribute 'name'`（fixes #18989） | **官方**（[ORT QNN EP](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html)）+ **官方代码**（[pytorch/executorch commit 0e8c146](https://github.com/pytorch/executorch)） |
| `ai.onnx:MatMul` | 支持；HTP 接受 **uint8/uint8、uint8/uint16、uint16/uint8** | 即 **w8a8 与 w8a16** 两种量化组合都落在这几个 dtype 对上 | **官方**（同上） |
| `ai.onnx:LpNormalization` | 仅 **p == 2** | — | **官方**（同上） |
| **动态 shape** | **不支持**。QNN EP 的模型要求写明：动态 shape 必须固定成静态 | 对 SER 是硬伤：音频天然变长，必须做**固定窗口 + 固定帧数** | **官方**（同上） |
| **控制流** | **不支持 Loop / If**，仅支持 ONNX 算子子集 | Whisper 这类自回归 decode 循环要靠外部展开 | **官方**（同上） |
| 完整算子矩阵 | 官方有**逐算子 × 逐后端（CPU/GPU/HTA/LPAI/HTP/DSP）× 逐精度（fp32/int8/BF16/FP16/INT16）** 的支持表（Rev AL，`80-63442-10`） | ⚠️ 该页面为 JS 门禁，本次抓取返回 "You do not have any projects yet"，**逐行矩阵未能直接核验**，本表其余行以 ORT QNN EP 文档 + 论坛根因帖替代 | **官方（页面存在，内容未核验）**（[QNN Supported Ops](https://docs.qualcomm.com/bundle/publicresource/topics/80-63442-10/SupportedOps.html)） |

##### 3.2.8.2 量化路径

| 项 | 内容 | 来源 / 可信度 |
|---|---|---|
| **工具** | `qnn-quantization-checker`（先看哪些层可量化）→ `qnn-onnx-converter`（转换 + 量化编码）→ `qnn-context-binary-generator`（生成可直接加载的 context binary）/ `qnn-model-lib-generator`（生成 .so）；配套 `qnn-accuracy-debugger`、`qnn-net-run`、`qnn-profile-viewer`、`qnn-netron`、`qnn-platform-validator` | **二手实测**（[CSDN 教程](https://blog.csdn.net/weixin_51031772/article/details/141331531)、[Microsoft edgeai-for-beginners 中文版](https://github.com/microsoft/edgeai-for-beginners/blob/main/translations/zh-CN/Module04/07.QualcommQNN.md)） |
| **PTQ（命令行原文）** | `--act_bw 8 --weight_bw 8 --algorithms cle adaround --param_quantizer enhanced --act_quantizer enhanced --use_per_channel_quantization`（CLE + Adaround + per-channel） | **二手实测**（同上） |
| **量化覆盖（override）** | `quantization_overrides` JSON：`activation_encodings` / `param_encodings` / `activation_bitwidth` / `param_bitwidth` / `bias_bitwidth` | **二手实测**（同上） |
| **int4** | 支持：encoding 里写 `"dtype": "int4"`，配 `group_size 128`（per-group）。AI Hub 侧 `build_deployable_asset.py` 负责把 QDQ 折叠成整数权重，并用 `convert_initializers_int8_to_int4` 打包（因为 onnx-graphsurgeon 原生不支持 INT4） | **二手实测**（[ai-hub-apps 部署教程](https://deepwiki.com/qualcomm/ai-hub-apps/4.3-onnx-deployment-tutorial)） |
| **HTP 首选精度** | **INT8 权重 + 16-bit 激活（W8A16）** 被点名为 Hexagon 上的最佳平衡点（Ultralytics 的 QNN 导出即默认这个组合） | **二手实测**（[Ultralytics QNN 集成文档](https://docs.ultralytics.com/zh/integrations/qnn)） |
| **AI Hub 一键量化** | `python qai_hub_models/models/<m>/export.py --target-runtime onnx --quantize`；AI Hub 的量化形态以 **w8a8 / w8a16** 为主 | **官方**（同上 + [HF qualcomm/YamNet](https://huggingface.co/qualcomm/YamNet)） |
| **QAT** | **未检索到** QNN 官方 QAT 通道（QNN 侧是 PTQ 为主；QAT 需在上游框架做完后带 QDQ 图导入） | — |
| **混合精度 / 权重共享** | ORT QNN EP 支持权重共享与混合精度 | **官方**（[ORT QNN EP](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html)） |

##### 3.2.8.3 HTP 架构与后端库

| HTP arch | 对应 SoC | 来源 |
|---|---|---|
| v68 | 骁龙 888 | **二手实测**（[Ultralytics](https://docs.ultralytics.com/zh/integrations/qnn)） |
| v69 | 骁龙 8 Gen 1 | 同上 |
| v73 | 骁龙 8 Gen 2 / X Elite | 同上 |
| v75 | 骁龙 8 Gen 3 | 同上 |
| v79 | 骁龙 8 Elite | 同上 |
| v81 | 骁龙 8 Elite Gen 5 | 同上 |

后端库（[官方 backend 文档](https://docs.qualcomm.com/bundle/publicresource/topics/80-63442-10/backend.html)）：CPU `libQnnCpu.so` ｜ DSP `libQnnDspV##.so` ｜ GPU `libQnnGpu.so` ｜ HTP `libQnnHtp.so` / `libQnnHtpV##Skel.so` ｜ HTA `libQnnHta.so` ｜ **LPAI `libQnnLpai.so` / `libQnnLpaiSkel.so` / `libQnnLpaiIsland.so`（v5 起才支持执行）**。

> **LPAI 是 laos 唯一的目标档**（Active <50 mW / LPI <5 mW）。硬约束：LPAI 要求 **QNN 量化模型必须是 context binary 格式**，且需 **eNPU v5+**（[MathWorks 文档](https://ww2.mathworks.cn/help/ecoder/qualcommhexagon/ug/deploy-deep-neural-networks-qualcomm-qnn-example.html)）。结合本文档 §2.3 的结论——aDSP/LPAI 需高通授权 + 厂商签名——**这一档对 laos 是授权问题不是技术问题。**

##### 3.2.8.4 AI Hub 上的实测数字（本节最有价值的部分）

**① YAMNet（3.73M 参数 / 14.2 MB float，输入 1×1×96×64，MobileNet_v1 深度可分离，AudioSet 分类）——纯 CNN 基准**

| 设备 / 运行时 | 精度 | 延迟 | 峰值内存 | NPU 层数 | 来源 |
|---|---|---|---|---|---|
| Samsung Galaxy S26 / 骁龙 8 Elite Gen 5（TFLite） | float | **96.0 μs**（吞吐 10,417 次/s） | 0–21 MB | 32 | **官方**（[AI Hub YAMNet](https://aihub.qualcomm.com/models/yamnet)） |
| Dragonwing RB3 Gen 2（QCS6490），LiteRT 1.4.5 + QAIRT v2.45.0，QNN delegate HTP fp16 burst O3 | fp16 | **525 μs** | 0–6 MB | 32 | **官方**（job `jpyxdxq05`，[AI Hub](https://aihub.qualcomm.com/jobs/jpyxdxq05)；⚠️ 复核时该页返回 404，数字取自检索快照，标注为**官方（页面已失效）**） |

YAMNet 逐芯片（float，[HF qualcomm/YamNet](https://huggingface.co/qualcomm/YamNet)）：

| 设备 | TFLITE | QNN | ONNX |
|---|---|---|---|
| Galaxy S23 / SD8Gen2 | 0.213 ms | 0.211 ms | 0.294 ms |
| Galaxy S24 / SD8Gen3 | 0.176 ms | 0.178 ms | — |
| SD8 Elite QRD | 0.174 ms | 0.169 ms | 0.249 ms |
| SA8775P ADP（车规） | — | 0.355 ms | — |
| Snapdragon X Elite CRD | — | 0.266 ms | — |

YAMNet 量化档（**官方**：QNN_DLC 与 ONNX 有 **w8a8 / w8a16**，TFLITE 只有 **w8a8**）：

| 设备 | 精度 | 延迟 |
|---|---|---|
| SD8 Elite Mobile | QNN_DLC w8a8 **0.099 ms** ／ TFLITE w8a8 **0.097 ms** ／ ONNX w8a8 **0.096 ms** |
| SD8 Elite Gen 5 | QNN_DLC w8a8 **0.098 ms** ／ TFLITE w8a8 **0.096 ms** ／ ONNX w8a16 **0.1 ms** |
| QCS6490（IoT） | TFLITE w8a8 **0.516 ms** ／ QNN_DLC w8a8 **0.561 ms** ／ ONNX w8a8 **0.699 ms** |

> 读法：纯 CNN 音频分类器在骁龙旗舰上 **float ≈ 0.17–0.27 ms，int8 ≈ 0.1 ms**，量化收益约 **1.7×**；IoT 档（QCS6490）慢 **5 倍**。

**② Whisper-Tiny decoder（自回归解码器，相邻案例）**

| 设备 / 运行时 | 延迟 | 内存 | NPU 层数 | 来源 |
|---|---|---|---|---|
| Snapdragon X2 Elite CRD，ORT float | **1.35 ms** | 10 MB | 509 | **官方**（[AI Hub Whisper-Tiny](https://aihub.qualcomm.com/models/whisper_tiny)） |
| Samsung Galaxy S25 / SD8 Elite for Galaxy（SM8750-AC），QAIRT v2.45.0，fp16 KV-cache | **1.56 ms** | 0–13 MB | 509 | **官方**（job `jgk431kvp`，同上） |
| （HF commit 附带）SD8Gen2：TFLite **encoder 68.47 ms / decoder 3.853 ms**；QNN Model Library **encoder 286.944 ms / decoder 3.672 ms** | — | — | — | **官方**（同上页面 HF commit 引用） |

**③ HuggingFace-WavLM-Base-Plus —— 与 wav2vec2/HuBERT 同构的"卷积 + 注意力"音频编码器，95.1M 参数 / 363 MB float / 输入 1×320000（20 s @16 kHz）**

> **这是本调研里最重要的一个数：它直接回答"wav2vec2 家族上 HTP 到底多慢"。**

| 运行时 / 精度 | SD8 Elite Gen 5 | SD8 Elite For Galaxy | SD8Gen3 | X Elite | X2 Elite | QCS9075 | QCS8550 / 8450 / 8275 | SA8775P | SA8295P |
|---|---|---|---|---|---|---|---|---|---|
| **ONNX float** | **140.019 ms**（1–1177 MB） | 177.21 ms | 251.325 ms（1–1413 MB） | 311.924 ms | 137.668 ms | 387.221 ms | 328.759 ms（8550） | — | — |
| **QNN_DLC float** | **129.22 ms**（0–1144 MB） | — | 227.388 ms | — | 125.695 ms | — | 573.586 ms（8450）／844.659 ms（8275/SA7255P） | 337.247 ms | — |
| **TFLITE float** | 166.44 ms | — | 309.3 ms | — | — | — | 939.668 ms（8275） | — | 527.024 ms |

来源：
- 主表：[HF `qualcomm/HuggingFace-WavLM-Base-Plus` README（blame 视图，含完整表格）](https://huggingface.co/qualcomm/HuggingFace-WavLM-Base-Plus/blame/main/README.md)——**官方**
- 单次 profile job：SD8Gen2，ONNX Runtime 1.20.1 + QAIRT v2.32，**228 ms**，内存 **3–422 MB**，NPU **686 ops**，job `j5627y00g`——**官方**（[AI Hub](https://aihub.qualcomm.com/jobs/j5627y00g)）

**关键读法（三条）：**
1. **全部是 float。该模型在 AI Hub 上未检索到 w8a8 / w8a16 行。** → 与 YAMNet（有完整 w8a8/w8a16 行）形成鲜明对比：**纯 CNN 能量化，卷积注意力编码器在 AI Hub 上没有公开的量化档。** 这本身就是一条强信号。
2. **峰值内存 1.1–1.4 GB**（20 s 输入）。即便量化到 int8，激活内存不会同比例下降，且 laos 的常驻预算在 mW/memory 两侧都不允许。
3. **最快的 QNN_DLC 也要 125–130 ms（旗舰）/ 227 ms（8Gen3）/ 844 ms（IoT 8275）**——对 20 s 输入意味着 RTF ≈ 0.006–0.04，看着很好，但**这是一次 20 s 大块前向的摊销结果**；若按 laos 的"滑动窗口常驻检测"切片（例如 3 s 窗口 + 1 s hop），实际是**每秒一次百毫秒级 HTP 唤醒**，与 mW 档完全冲突（见 §2.3 的 HTP 瓦级功耗）。

##### 3.2.8.5 SER 转换案例（QNN）

- **公开的 SER → QNN 案例：未检索到。**
- **本仓库内部已有真机链路**（这是 laos 唯一的"已跑通"证据，必须显式标注为内部记录而非公开案例）：TIM-Net（34,671 参数 / 0.4 MB）与 LIGHT-SERNET（~460K）→ Keras → 4D SavedModel → ONNX → **QNN int8（QAIRT 2.47）** → `.eaix` → SCons 编入 SEE 镜像 → 骁龙 8 Elite（SM8735 "Bonito"，Hexagon v73M）**aDSP**；7 分类，EMO-DB **70.28%**（5 折）；QNN **CPU** 推理 ≈6 ms；转换期踩了 **7 个算子兼容坑**（reverse→gather、Lambda→标准算子、causal→ZeroPadding2D、1D→4D、SpatialDropout 移除、expand_dims→Reshape、环境隔离）。来源：[`../2026-09-09-qnn-real-os-integration.md`](../2026-09-09-qnn-real-os-integration.md)（**本仓库内部**）
- 相邻案例（量化收益的量级参照，非音频）：小米 17（SD8 Elite Gen 5，HTP v81）上 YOLO26n：**NPU Hexagon QNN W8A16 = 11.3 ms** vs **CPU INT8 TFLite = 53.3 ms**（**二手实测**，[Ultralytics](https://docs.ultralytics.com/zh/integrations/qnn)）

##### 3.2.8.6 导出工具链步数

| 路线 | 步骤 |
|---|---|
| **ORT + QNN EP（推荐，最省事）** | torch/HF → `optimum-cli export onnx` → ORT（Android aar + QNN EP）→ 运行（**3 步**，量化用 `onnxruntime.quantization` 加一步） |
| **原生 QNN** | torch → ONNX → `qnn-onnx-converter`（+ `qnn-quantization-checker` 预检）→ `qnn-context-binary-generator` / `qnn-model-lib-generator` → Android 集成（**4–5 步**） |
| **AI Hub（最省事，但要联网上传模型）** | `qai_hub.submit_profile_job()` / `submit_compile_job()` 或 `export.py --target-runtime ... --quantize`（**1–2 步**，直接拿官方 profile 数字） |

---

### 3.3 表 ②：SER / 相邻音频模型的公开端侧转换案例

> 口径：**"纯 SER"** = 模型本身做情感分类；**"相邻"** = 音频编码器 / 语音模型，非情感任务，只能作为算子与性能的代理证据。

| # | 模型 | 任务 | 目标 runtime | 设备 / 硬件 | 精度 | 体积 | 延迟 / 内存 | 可信度 | 来源 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **emotion2vec_plus_large** | **纯 SER（导出的是帧级特征，非标签）** | **ONNX**（opset 14） | — | fp32 | **648,972,628 bytes** | 与 PyTorch 最大绝对误差 **6.20e-6**；输入 `input[1, samples]` → 输出 `[1, T, 1024]`，支持动态长度 | **官方**（PR + 讨论区核验） | [FunASR PR #2359](https://github.com/modelscope/FunASR/commit/3530688e0a1b1dfbb22dcd3324db97be5bbc0d9b)、[讨论 #2151](https://github.co.uk/modelscope/FunASR/discussions/2151) |
| 2 | **TIM-Net / LIGHT-SERNET** | **纯 SER（7 分类）** | **QNN int8 → aDSP/LPAI** | 骁龙 8 Elite（SM8735，v73M） | **int8** | 34,671 参数 / **0.4 MB**；蒸馏版 **~174 KB .eaix** | QNN **CPU** ≈6 ms（非真机 aDSP）；EMO-DB **70.28%** | **本仓库内部**（无实测数字） | [`../2026-09-09-qnn-real-os-integration.md`](../2026-09-09-qnn-real-os-integration.md) |
| 3 | **WavLM-Base-Plus**（相邻，与 wav2vec2/HuBERT 同构） | 音频编码器 | ONNX / **QNN_DLC** / TFLite | SD8 Elite Gen 5 等 9 款 | **float**（w8a8/w8a16 **未检索到**） | 95.1M / 363 MB | **129.22 ms**（QNN_DLC，8EG5）／227.39 ms（8Gen3）／844.66 ms（QCS8275）；峰值内存 **0–1144 MB** | **官方** | [HF README](https://huggingface.co/qualcomm/HuggingFace-WavLM-Base-Plus/blame/main/README.md) |
| 4 | **YAMNet**（相邻） | AudioSet 分类 | TFLite / QNN / ONNX | SD8 Elite Gen 5 等 | float **+ w8a8 + w8a16**（齐全） | 3.73M / 14.2 MB | float **96.0 μs**（Galaxy S26）／0.174 ms（8 Elite）；**w8a8 ≈0.096–0.099 ms**；QCS6490 w8a8 **0.561 ms**；峰值内存 0–21 MB | **官方** | [AI Hub YAMNet](https://aihub.qualcomm.com/models/yamnet)、[HF YamNet](https://huggingface.co/qualcomm/YamNet) |
| 5 | **Whisper-Tiny**（相邻） | ASR decoder | ONNX Runtime | SD8 Elite for Galaxy / X2 Elite | float（fp16 KV-cache） | — | **1.35–1.56 ms**，10–13 MB，NPU 509 层 | **官方** | [AI Hub Whisper-Tiny](https://aihub.qualcomm.com/models/whisper_tiny) |
| 6 | **SenseVoice**（相邻，但**自带 SER/AED/LID 能力**） | ASR + 情感 + 事件 | ONNX（sherpa-onnx） | CPU（RKNN/AXERA/QNN 等 NPU 可选） | fp32 / **int8 动态量化** | **895 MB → 229 MB**（**−75%**） | 未检索到统一基准 | **官方** | [sherpa-onnx SenseVoice 导出](https://k2-fsa.github.io/sherpa/onnx/sense-voice/export.html) |
| 7 | **SER（LSTM）**（纯 SER，极小） | 情感分类 | TFLite → **int8** | MCU / TinyML | **int8** | 1.5 MB → 515 KB → **150 KB** | 100 样本 **4.391 s → 0.299 s**；准确率 **72.88% → 73.06%** | **未证实** | [GitHub 项目](https://github.kazgu.com/Kashish0212/Speech-Emotion-Recognition-TinyML) |
| 8 | **SER（多种）**（纯 SER） | 情感分类 | **TFLite 量化** | 边缘设备 | 量化（未指明位宽） | 体积最多压缩 **94.5%** | 推理延迟低至 **3.4 ms**；最佳模型 **74.15% acc / macro-F1 0.73** | **同行评审**（Expert Systems 2026，DOI 10.1111/exsy.70322） | [DOI](https://doi.org/10.1111/exsy.70322) |
| 9 | **Transformer 晚期融合**（相邻，含 YAMNet 部署验证） | 音频-文本融合 | **Edge TPU（Coral Dev Board Micro）** | Coral Dev Board Micro | — | **1.8 MB 内存预算** | **21–23 ms**；恒定 **2.5 W** | **同行评审**（arXiv 2510.18036） | [arXiv](https://arxiv.org/abs/2510.18036) |
| 10 | **轻量 SER（深度可分离 CNN + 注意力）**（纯 SER） | 情感分类 | 端侧（未指明 runtime） | Raspberry Pi 4 + 中端 Android | — | — | 推理 **<150 ms**，端到端 **<500 ms**；EMO-DB/RAVDESS/TESS **>90% acc / >88% UAR** | **同行评审**（会议论文，未获取 DOI） | 检索命中，链接未固化 |
| 11 | **wav2vec2 / HuBERT → TFLite 或 CoreML** | — | — | — | — | — | **未检索到任何成功案例**；官方导出器把它们列在"已知不支持"清单 | **官方** | [aidyai/exporters](https://github.com/aidyai/exporters) |
| 12 | **wav2vec2 / HuBERT → QNN / AI Hub** | — | — | — | — | — | **未检索到**（AI Hub 上未检索到 wav2vec2 或 HuBERT 条目；只检索到 WavLM-Base-Plus） | — | — |

**第 9 行要单独拎出来看**（对 laos 的算子选型有直接指导）：arXiv 2510.18036 在 Coral Dev Board Micro 上实测，**Edge TPU 不支持 3D 张量上的 MHSA**，作者被迫把多头自注意力换成**单头注意力 + 1×1 卷积**；同时全连接层也不接受 2D/3D 张量输入。→ **"注意力在极边缘硬件上必须降维/替换"是同行评审级的结论，不只是一家 runtime 的毛病。**

---

### 3.4 对 laos 的直接含义

1. **别指望 wav2vec2/HuBERT/WavLM 系能进 mW 档。** 最硬的证据是 WavLM-Base-Plus 在 SD8 Elite Gen 5 上 QNN_DLC **129 ms / 峰值 1.1 GB**，且 **AI Hub 上连 w8a8 档都没有**（对比 YAMNet 的 w8a8 档齐全）。量级上差了 TIM-Net（0.4 MB int8）**三个数量级**。
2. **如果一定要用大模型，ONNX 是唯一有出路的中间表示。** emotion2vec 的 ONNX 导出已经官方支持（#1，误差 6.2e-6），而 wav2vec2 家族的 TFLite / CoreML 导出是**官方声明不支持**的。
3. **QNN 路线的真实风险不在"能不能转"，在"转完跑不跑得动"。** 已知坑集中在 `Gather`（正索引限制）、`QNN_Gelu`（HTP tiler 对 shape/dtype 敏感）、`LayerNorm`（`native_layer_norm` 分解 + 无 affine 时崩）、**动态 shape 不支持**——laos 在 TIM-Net 上已经踩过 7 个同类坑，说明**模型越小、算子越规整，成功率越高**。
4. **音频变长与 QNN 静态 shape 是直接冲突的**，必须设计成固定窗口（对照 TIM-Net 的固定 `479 帧 × 26 维` MFCC 输入）。
5. **sherpa-onnx 值得单列**：它底层是 ONNX Runtime，通过 CMake 开关支持 `SHERPA_ONNX_ENABLE_QNN`（高通）、`_RKNN`、`_AXERA`、`_AXCL`、`_ASCEND_NPU`、`_SPACEMIT`；SenseVoice 官方导出 `model.onnx`（895 MB）与 `model.int8.onnx`（**229 MB，动态量化 −75%**）。**SenseVoice 一个前向同时吐文本/语种/情感/事件**，是"情感"这条需求上**唯一有官方量化产物的相邻模型**。（[CMakeLists](https://github.com/k2-fsa/sherpa-onnx/blob/master/CMakeLists.txt)、[导出文档](https://k2-fsa.github.io/sherpa/onnx/sense-voice/export.html)）
6. **Optimum 的结论要写清楚**：`optimum-cli export onnx` 对 wav2vec2/HuBERT **可用**；`optimum-cli export tflite` **不可用**（报 "Only ['onnx'] are supported"）；`optimum-cli export executorch` 存在但**未检索到 wav2vec2/HuBERT 的成功案例**。

---

---

## §4 实测数字：速度 / 内存 / 体积 / 功耗 / 量化

### 4.1 推理速度

#### 4.1.1 小型档（< 30M）

| 模型 | 平台 / 计算单元 | 运行时·精度 | 输入时长 | 实测时延 | RTF（=时延/输入时长，推算） | 峰值内存 | 可信度 | 来源 |
|---|---|---|---|---|---|---|---|---|
| YAMNet (3.73M) | Snapdragon 8 Elite Gen 5（Galaxy S26 / Android 16）· **NPU** | LiteRT + QNN HTP，fp16 | 0.96 s（96 帧 ×10 ms） | **98.0 µs**（吞吐 10,204 次/s） | 1.0×10⁻⁴ | 0–23 MB | 官方 | [AI Hub 模型页](https://aihub.qualcomm.com/models/yamnet)、[profile job jpvdwdezp](https://aihub.qualcomm.com/jobs/jpvdwdezp) |
| YAMNet | Snapdragon 8 Elite Gen 5 · NPU | ONNX，float | 0.96 s | 0.153 ms | 1.6×10⁻⁴ | 0–25 MB | 官方 | [qualcomm/YamNet](https://huggingface.co/qualcomm/YamNet) |
| YAMNet | Snapdragon 8 Elite Gen 5 · NPU | ONNX，w8a8 | 0.96 s | 0.099 ms | 1.0×10⁻⁴ | 0–26 MB | 官方 | 同上 |
| YAMNet | Snapdragon 8 Gen 3 · NPU | ONNX，float | 0.96 s | 0.186 ms | 1.9×10⁻⁴ | 0–37 MB | 官方 | 同上 |
| YAMNet | Snapdragon 8 Gen 3 · NPU | ONNX，w8a8 | 0.96 s | 0.117 ms | 1.2×10⁻⁴ | 0–37 MB | 官方 | 同上 |
| YAMNet | Snapdragon 7 Gen 4 · **CPU** | ONNX，w8a8 | 0.96 s | 0.615 ms | 6.4×10⁻⁴ | 0–7 MB | 官方 | 同上 |
| YAMNet | QCM6690 · **CPU** | ONNX，w8a8 | 0.96 s | 0.878 ms | 9.1×10⁻⁴ | 0–7 MB | 官方 | 同上 |
| YAMNet | QCS6490 · **CPU** | ONNX，w8a8 | 0.96 s | 1.637 ms | 1.7×10⁻³ | 0–6 MB | 官方 | 同上 |
| YAMNet（INT8，mel-patch 输入） | **ESP32-S3 @240 MHz + ESP-NN** | TFLite Micro，全整数 INT8 | 0.96 s | **≈500 ms / patch** | ≈0.52 | arena ≈1.2 MB | 二手实测 | [chayuto/yamnet-mel-int8-tflm 模型卡](https://huggingface.co/chayuto/yamnet-mel-int8-tflm) |
| FRILL (10.1M) | Pixel 1 | TFLite（fp32 38.5 MB / QAT INT8） | 未标注 | **8.5 ms / 次** | — | — | 同行评审 | arXiv 2011.04609（已录入 `01-small-models.md`） |
| DistilHuBERT INT8 (23.49M) | — | ONNX INT8，23 MB | — | **未检索到**（该文只报精度与体积，未报时延/RTF） | — | — | — | [arXiv 2512.23435](https://arxiv.org/abs/2512.23435) |
| openSMILE ComParE_2016（非神经） | — | 原生 C++ | — | **未检索到**官方或同行评审的提取耗时/RTF | — | — | — | — |

**小型档读法**：YAMNet 这类 3.7M 卷积在**旗舰 NPU 上比实时快 4 个数量级**，即便退到中端 CPU（骁龙 7 Gen 4）也还有 RTF 6.4×10⁻⁴ 的余量——也就是说**纯时延根本不是小型档的瓶颈**。真正的分水岭在 MCU：同一模型搬到 ESP32-S3 上 RTF 掉到 ≈0.52，**只剩约 2 倍余量**，且要吃掉 1.2 MB arena（nRF52840 的 256 KB SRAM 装不下）。

#### 4.1.2 中型档（30M–500M）

| 模型 | 平台 / 计算单元 | 运行时·精度 | 输入时长 | 实测时延 | RTF（推算） | 峰值内存 | 可信度 | 来源 |
|---|---|---|---|---|---|---|---|---|
| **WavLM-base+ (95.1M)** | Snapdragon 8 Elite Gen 5 · NPU | QNN_DLC，float | 20 s（1×320000 @16 kHz） | 129.22 ms | 6.5×10⁻³ | 0–1144 MB | 官方 | [qualcomm/HuggingFace-WavLM-Base-Plus](https://huggingface.co/qualcomm/HuggingFace-WavLM-Base-Plus) |
| WavLM-base+ | Snapdragon 8 Elite Gen 5 · NPU | ONNX，float | 20 s | 154.394 ms | 7.7×10⁻³ | 1–1057 MB | 官方 | 同上 |
| WavLM-base+ | Snapdragon 8 Elite For Galaxy · NPU | ONNX，float | 20 s | 188.641 ms | 9.4×10⁻³ | 1–1006 MB | 官方 | 同上 |
| WavLM-base+ | Snapdragon 8 Gen 3 · NPU | ONNX，float | 20 s | 251.325 ms | 1.26×10⁻² | **1–1413 MB** | 官方 | 同上 |
| WavLM-base+ | Snapdragon 8 Gen 3 · **CPU** | TFLite，float | 20 s | 1421.172 ms | 7.1×10⁻² | 117–1306 MB | 官方 | 同上 |
| WavLM-base+ | Snapdragon 8 Gen 2（Galaxy S23）· NPU | ONNX RT + QNN，fp16 | 5 s（1×80000） | 228 ms | 4.6×10⁻² | 3–422 MB | 官方 | [job j5627y00g](https://aihub.qualcomm.com/jobs/j5627y00g) |
| WavLM-base+ | QCS8275 · **CPU** | TFLite，float | 20 s | 2905.625 ms | 1.45×10⁻¹ | 125–1049 MB | 官方 | [qualcomm/HuggingFace-WavLM-Base-Plus](https://huggingface.co/qualcomm/HuggingFace-WavLM-Base-Plus) |
| WavLM-base+ | SA7255P ADP · **CPU** | TFLite，float | 10 s（1×160000） | **2.85 s** | 2.85×10⁻¹ | 125–908 MB | 官方 | [job jp2lqemrg](https://aihub.qualcomm.com/jobs/jp2lqemrg) |
| **wav2vec2-base (93M)** | **Raspberry Pi 4B**（4×Cortex-A72 @1.5 GHz）4 核 · CPU | PyTorch 动态量化 | — | — | **RTF 0.98** | 未报 | 二手实测（预印本） | [arXiv 2202.05993](https://arxiv.org/abs/2202.05993) |
| wav2vec2-base | Raspberry Pi 4B 1 核 · CPU | PyTorch 动态量化 | — | — | RTF 2.30 | 未报 | 二手实测 | 同上 |
| wav2vec2-base | Raspberry Pi 4B 4 核 · CPU | 未量化 | — | — | RTF 1.36 | 未报 | 二手实测 | 同上 |
| **SenseVoice-Small (234M)** | 未标注（官方 benchmark 图） | 非自回归端到端 | 10 s | **≈70 ms** | ≈7×10⁻³ | 未报 | 官方（**未标设备**） | [FunAudioLLM/SenseVoice README](https://github.com/FunAudioLLM/SenseVoice/blob/main/README_zh.md) |
| SenseVoice-Small | NVIDIA H100 | FunASR | — | — | RTFx 169.6（RTF 5.9×10⁻³） | 未报 | 官方 | [FunASR vs Whisper 基准](https://funasr.com/en/blog/funasr-vs-whisper-benchmark.html) |
| SenseVoice-Small | CPU（**型号未标注**） | FunASR | 184 条中文音频 / 11,539 s | — | RTFx 17.2（RTF ≈5.8×10⁻²） | 未报 | 官方（未标设备） | 同上 |
| SenseVoice-Small | CPU 8 线程 | GGUF q8_0（llama.cpp runtime） | — | — | ≈20× 实时（RTF ≈5×10⁻²） | 未报 | 二手实测 | [cangmeng/SenseVoiceSmall-GGUF](https://huggingface.co/cangmeng/SenseVoiceSmall-GGUF) |
| Whisper-Tiny (37.8M，**ASR 参照**) | Snapdragon 8 Elite Gen 5（Galaxy S26）· NPU | Voice AI，float | 30 s 输入 / 200 token | decoder 1.49 ms/步（吞吐 673 次/s） | — | 0–9 MB | 官方 | [AI Hub whisper_tiny](https://aihub.qualcomm.com/mobile/models/whisper_tiny) |
| Whisper-Tiny | Snapdragon 8 Gen 3 · NPU | PRECOMPILED_QNN_ONNX，float | 同上 | decoder 1.908 ms/步 | — | 13–20 MB | 官方 | [qualcomm/Whisper-Tiny](https://huggingface.co/qualcomm/Whisper-Tiny) |

**中型档读法（两条，都会影响选型）**

1. **时延不是中型档的门槛，内存才是。** WavLM-base+ 在骁龙 8 Gen 3 的 NPU 上 251 ms 就跑完 20 s 音频（RTF 1.26×10⁻²，比实时快 80 倍），但**峰值内存上限报到 1413 MB**；同一模型在 8 Elite Gen 5 上是 1057–1144 MB。**"95M 参数 = 363 MB 权重"这个直觉是错的**：AI Hub 报的是 OS 视角的进程内存区间，实际能上到 1 GB 量级。laos 若按"中型档 = 几百 MB 内存"做预算，会踩空。
2. **掉到 CPU 就立刻不是实时。** 同一 WavLM-base+ 在 8 Gen 3 上从 NPU 换到 TFLite/CPU，时延从 251 ms 涨到 1421 ms（5.7×）；在车规 SA7255P（CPU）上 10 s 音频要 2.85 s（RTF 0.285）。**这在 laos 的 proot 现状里就是默认路径**（proot 里拿不到 NPU）。

#### 4.1.3 大型档（> 500M，作对照）

| 模型 | 平台 / 计算单元 | 运行时·精度 | 输入 | 实测时延 | RTF / 吞吐（推算） | 峰值内存 | 可信度 | 来源 |
|---|---|---|---|---|---|---|---|---|
| **Whisper-Large-V3-Turbo (809M)** | Snapdragon 8 Elite Gen 5 · NPU | PRECOMPILED_QNN_ONNX，float（**encoder**） | 30 s（128×3000） | 378.435 ms | 1.26×10⁻²（仅 encoder） | 59–68 MB | 官方 | [qualcomm/Whisper-Large-V3-Turbo](https://huggingface.co/qualcomm/Whisper-Large-V3-Turbo) |
| Whisper-Large-V3-Turbo | Snapdragon 8 Gen 3 · NPU | 同上（encoder） | 30 s | 471.256 ms | 1.57×10⁻² | 未报 | 官方 | 同上 |
| Whisper-Large-V3-Turbo | Snapdragon X Elite · NPU | 同上（encoder） | 30 s | 626.749 ms | 2.09×10⁻² | **1395–1395 MB** | 官方 | 同上 |
| Whisper-Large-V3-Turbo | Snapdragon 8 Elite Gen 5 · NPU | 同上（**decoder**） | 200 token | 6.297 ms/token | ≈159 token/s | 42–53 MB | 官方 | 同上 |
| Whisper-Large-V3-Turbo | Snapdragon 8 Gen 3 · NPU | 同上（decoder） | 200 token | 8.093 ms/token | ≈124 token/s | 未报 | 官方 | 同上 |
| Whisper-Large-V3-Turbo-**Quantized** | Snapdragon 8 Elite Gen 5 · NPU | w8a16（decoder） | 200 token | 3.29 ms/token | ≈304 token/s | 17–25 MB | 官方 | [qualcomm/Whisper-Large-V3-Turbo-Quantized](https://huggingface.co/qualcomm/Whisper-Large-V3-Turbo-Quantized) |
| 7B 级语音大模型（Qwen2-Audio / SALMONN / GAMA 一类） | **端侧** | — | — | **未检索到**端侧实测 | — | — | — | — |

> 关于 7B 级：arXiv 2409.06223 的 Table 5 给过一个 7B 级 LALM 在 fp16 / 8-bit / 4-bit 下的 7.35 / 13.16 / 19.64 TPS 与 12.55 / 6.67 / 3.56 GiB 体积（[来源](https://arxiv.org/html/2409.06223v3)），**但文中未标明设备，疑为桌面 GPU，不作端侧数字引用**。

---

### 4.2 内存与体积

| 模型（参数量） | fp32 | fp16 | INT8 | INT4 | 峰值内存 / arena | 可信度 | 来源 |
|---|---|---|---|---|---|---|---|
| YAMNet (3.73M) | **14.2 MB** | — | ≈4.0 MB（TFLM 全整数） | 未检索到 | 0–37 MB（8 Gen 3 NPU）；arena ≈1.2 MB（ESP32-S3） | 官方 / 二手实测 | [AI Hub](https://aihub.qualcomm.com/models/yamnet)、[TFLM 模型卡](https://huggingface.co/chayuto/yamnet-mel-int8-tflm) |
| DistilHuBERT (23.49M) | 未检索到 | 未检索到 | **23 MB** | 未检索到 | 未检索到 | 二手实测（预印本） | [arXiv 2512.23435](https://arxiv.org/abs/2512.23435) |
| wav2vec2-base (93M) | **377 MB**（TorchScript） | — | **207 MB**（量化 TorchScript） | 未检索到 | 未报 RSS；量化 LM 比无 LM 多约 25% 内存 | 二手实测（预印本） | [arXiv 2202.05993](https://arxiv.org/abs/2202.05993) |
| WavLM-base+ (95.1M) | **363 MB** | — | 未检索到 | 未检索到 | **最高 1597 MB**（TFLite / 8 Gen 3）；1057–1144 MB（8 Elite Gen 5） | 官方 | [qualcomm/HuggingFace-WavLM-Base-Plus](https://huggingface.co/qualcomm/HuggingFace-WavLM-Base-Plus) |
| Whisper-Tiny (37.8M) | **encoder 35.9 MB + decoder 109 MB** | — | 未检索到 | 未检索到 | 13–20 MB（decoder / 8 Gen 3）；0–9 MB（8 Elite Gen 5） | 官方 | [qualcomm/Whisper-Tiny](https://huggingface.co/qualcomm/Whisper-Tiny) |
| Whisper-Large-V3-Turbo (809M) | 未检索到总体积 | — | decoder w8a16 峰值仅 17–25 MB（体积未单列） | 未检索到 | encoder 59–68 MB（8 Elite Gen 5）；X Elite 上 1395 MB | 官方 | [模型页](https://huggingface.co/qualcomm/Whisper-Large-V3-Turbo)、[量化版](https://huggingface.co/qualcomm/Whisper-Large-V3-Turbo-Quantized) |
| **SenseVoice-Small (234M)** | ONNX **895 MB**；GGUF f32 936 MB；GGUF f16 **470 MB** | 470 MB | ONNX INT8 **228–229 MB**；GGUF Q8_0 **254 MB**（254,211,200 B） | 未检索到 | 未检索到 RSS | 官方 + 二手实测 | [官方 README（q8 约 254 MB）](https://github.com/FunAudioLLM/SenseVoice/blob/main/README_zh.md)、[sherpa-onnx 导出卡（228 MB / fp32 895 MB）](https://huggingface.co/omote-ai/sensevoice-asr)、[GGUF q8_0 精确字节数](https://huggingface.co/yoyolaiyy3062/SenseVoiceSmall-GGUF-audiocpp)、[GGUF f16/f32](https://huggingface.co/cangmeng/SenseVoiceSmall-GGUF) |
| Edge TPU 情绪分类模型 (0.734M) | — | — | **1.8 MB** | — | **运行时 1.4 MB** | 同行评审（arXiv） | [arXiv 2510.18036](https://arxiv.org/html/2510.18036v1) |
| 手机压力/情绪模型 CMAF-Net | **18.2 MB** | — | **7.6 MB**（TFLite 动态量化，−58%） | — | 未报 | 同行评审 | [ACI 2025](http://ftp.nowpublishers.com/aci/article/doi/10.1108/ACI-08-2025-0346/1327676/Knowledge-guided-cross-modality-attention-for) |

**对两个既有锚点的核对结论**

- 「DistilHuBERT INT8 约 23 MB」→ **核实通过**。arXiv 2512.23435 原文：*"a quantized model footprint of only 23 MB"*。
- 「SenseVoice-Small ONNX INT8 约 228 MB / GGUF Q8_0 约 254 MB」→ **两个都核实通过**，且 254 MB 是精确字节数（254,211,200 B，官方 exporter `--wtype q8_0` 产出）。补一条：fp32 ONNX 是 **895 MB**，f16 GGUF 是 **470 MB**——即 Q8_0 相对 fp32 只压到 **28%**，远低于"INT8 = fp32 的 1/4"的直觉，因为 SenseVoice 的 234M 里 CTC 头（25,055 词表）占了不少。

---

### 4.3 功耗：情感/语音推理落在阶梯哪一级

**先给结论**：现有全部实测证据**支持**（没有任何一条反证）`hardware-power.md` §4 的那句话——*「ASR / 情感识别在手机上无论跑在哪个核上都是百毫瓦到瓦级，只能触发后短时运行，绝不能常驻」*。而且实测把它钉得比原话更死：**连专用 Edge TPU 上的 1.8 MB 情绪模型，连续推理都是 2.5 W**。

#### 4.3.1 直接实测（情感 / 语音推理）

| 场景 | 硬件 | 模型 | 实测功耗 | 折算 | 落在阶梯哪一级 | 可信度 | 来源 |
|---|---|---|---|---|---|---|---|
| **连续（continuous）端侧情绪识别** | **Coral Dev Board Micro**（Edge TPU，板载 64 MB RAM、PDM 麦） | 自研 late-fusion 情绪模型，0.734M 参数，**INT8**，5 s 窗口流式推理，时延 21–23 ms | **2.5 W（5 V / 0.5 A）恒定**；TPU 温度 32.5 ℃ | 500 mAh 电池**仅撑约 44 分钟** | **「手机 NPU 持续推理 1–4 W」级**（一个 MCU 上的 1.8 MB 模型，功耗与旗舰手机 NPU 同档） | 同行评审（arXiv） | [arXiv 2510.18036](https://arxiv.org/html/2510.18036v1) |
| 手机端情绪/压力推理（TFLite，CPU-only，batch=1，1,000 次均值） | Snapdragon 720G（6 GB，中端） | CMAF-Net 三分类，INT8 7.6 MB，180 ms/次 | **38.2 mJ / 次** | 38.2 mJ ÷ 0.18 s ≈ **212 mW**（推理期间均值） | **「通用 MCU/AP 26–50 mW」与「手机 NPU 1–4 W」之间**，即**百毫瓦级** | 同行评审（Trepn Profiler + Android battery stats） | [ACI 2025](http://ftp.nowpublishers.com/aci/article/doi/10.1108/ACI-08-2025-0346/1327676/Knowledge-guided-cross-modality-attention-for) |
| 同上（低端机） | Snapdragon 665（4 GB） | 同上，235 ms/次 | **52.6 mJ / 次** | 52.6 mJ ÷ 0.235 s ≈ **224 mW** | 同上（**越差的芯片反而越费电**） | 同行评审 | 同上 |
| wav2vec2-base ASR 推理（USB 功率计实测） | Raspberry Pi 4B | wav2vec2-base 量化，4 核 | 空闲 3.1 W；**推理增量 +2.9 W**（总量约 6 W） | 10 s 语音 **8.0 mWh**（量化）／**11 mWh**（未量化）；省 27% | **「手机 NPU 持续推理 1–4 W」上沿并超出** | 二手实测（预印本，带真实功率计） | [arXiv 2202.05993](https://arxiv.org/abs/2202.05993) |
| wav2vec2-base，1 核 | Raspberry Pi 4B | 同上，1 核 | 推理增量 **+1.1 W** | — | 同上（**降核是唯一有效节能手段**：1 核比 4 核省约 20% 能耗，代价是 RTF 从 0.98 劣化到 2.3） | 二手实测 | 同上 |

#### 4.3.2 MLPerf 里的音频类能耗数字

| 项目 | 数值 | 说明 | 可信度 | 来源 |
|---|---|---|---|---|
| MLPerf Tiny **keyword spotting**（唯一音频任务）· Syntiant NDP120 (v0.7) | **35.29 µJ/次 @4.3 ms**（0.9 V / 30 MHz）；**49.59 µJ/次 @1.8 ms**（1.1 V / 98 MHz） | 换 1 Hz = 35–50 µW；10 Hz = 0.35–0.50 mW | 同行评审（MLCommons 收录）+ 厂商 | [Syntiant v0.7](https://www.syntiant.com/news/syntiant-ndp120-achieves-outstanding-results-in-latest-mlperf-tiny-v07-benchmark-suite) |
| MLPerf Tiny KWS · Syntiant Core 2（v1.1 / v1.2） | **31.5 µJ/次 @4.4 ms**（0.9 V / 30.7 MHz）；**43.8 µJ/次 @1.5 ms**（1.1 V / 98.7 MHz） | 比同期其他提交低 **25–30×** | 同行评审 | [v1.1](https://syntiant.com/news/syntiant-core-2-achieves-outstanding-results-in-latest-mlperf-tiny-v1-1-benchmark-suite)、[v1.2](https://syntiant.com/news/syntiant-core-2-achieves-lowest-power-results-in-mlperf-tiny-v12-benchmark-suite) |
| MLPerf Tiny 同期 MCU 方案（对照） | **>7,300 µJ/次**（比 NDP120 差约 120×） | 即 1 Hz ≈ 7.3 mW | 二手（已在 `hardware-power.md` §2 引用） | 同上 |
| MLPerf Tiny 其他两个任务（**视觉**，非音频，供量级参照） | 视觉唤醒词 71.7–97.2 µJ/次；图像分类 101.8–139.4 µJ/次 | — | 同行评审 | 同上 |

**两条必须写进正文的判据**

- **MLPerf Tiny 没有 SER 任务**，它的唯一音频任务是 keyword spotting（DS-CNN / Speech Commands）。**MLPerf Mobile 连音频任务都没有**（只有图像分类、目标检测、分割、超分、MobileBERT NLP，见 [MLPerf Mobile v4.0 说明](https://mlcommons.org/?p=323)）。所以「MLPerf 里有没有情感识别的 µJ 数字」的标准答案是：**没有，且短期内不会有**。
- 因此「情感识别这一档的能耗」只能用 A.1/C.1 里的非 MLPerf 实测来定——它们一致地落在**百毫瓦到瓦**。

#### 4.3.3 可穿戴连续感知的参照（非声学情感，仅作同场景量级对照）

| 系统 | 场景 | 功耗 | 可信度 | 来源 |
|---|---|---|---|---|
| EarIO | 耳机内声学感知，连续追踪面部表情，86 Hz 采样 | **154 mW** | 同行评审（IMWUT / PACM） | [DOI 10.1145/3534621](https://dl.acm.org/doi/10.1145/3534621)（经 [arXiv 2506.05720 表 10](https://arxiv.org/html/2506.05720v2) 汇编） |
| IMUFace | 耳机 IMU 连续 3D 面部重建，30 Hz | **58 mW** | 同行评审 | [arXiv 2501.02177](https://arxiv.org/html/2501.02177v2) |

> 这两条是**模态对照**：同样"在可穿戴上连续推断情绪/表情"，非声学路线能做到 58–154 mW，而 §4.3.1 里**声学**路线（Coral Micro）是 2.5 W——差 16–43 倍。这不是说声学不行，而是说**"声学情感"的功耗量级由 transformer/CNN 前向决定，不由传感器决定**。

#### 4.3.4 结论（可直接抄进 04 的正文）

1. **情感识别的推理功耗落在阶梯第 4–5 级**，即"通用 MCU/AP（26–50 mW）"到"手机 NPU 持续推理（1–4 W）"之间，**具体位置由"跑什么核"和"跑多频繁"共同决定**，与模型大小弱相关。
2. **反例不存在**：本轮检索**未找到任何一条**"端侧声学情感识别做到 <100 mW 常驻"的实测。最强的低功耗证据（Syntiant 31.5 µJ/次）对应的是 keyword spotting，不是情感。
3. **唯一的现实路径是"降频 + 触发"**：CMAF-Net 的作者自己给的部署建议是 **2–4 次 / 小时**（而不是连续）；Coral Micro 那篇的 future work 第一条就是"加轻量声音检测前端，只在有声音时触发完整模型"。**这两条与 laos 的 `VAD 门控 + 批量转写` 设计同构，可作为外部佐证写进 README。**
4. **降核是唯一被量化的节能旋钮**：wav2vec2 在 RPi 上从 4 核降到 1 核，功耗增量 2.9 W → 1.1 W（省 62%），代价 RTF 0.98 → 2.30。laos 若在 proot 里跑批量转写，**限制线程数比换模型更能省电**。

---

### 4.4 量化对情感识别精度的影响

#### 4.4.1 同模型 / 同基准的 fp32 vs INT8（或 INT4）

| 主体 | 基准 / 指标 | fp32 | INT8 | 差 | 可信度 | 来源 |
|---|---|---|---|---|---|---|
| DistilHuBERT（**蒸馏 + 8-bit 量化合并**）vs 全量 Wav2Vec2.0 Base | IEMOCAP 5-fold LOSO，UA(UAR) | 67.2（**全量 wav2vec2 base，约 318 MB**；Pepino et al., Interspeech 2021） | **61.4（INT8，23 MB）** | **−5.8 点（=全量的 91%）** | 二手实测（预印本，**未经同行评审**） | [arXiv 2512.23435](https://arxiv.org/abs/2512.23435) §IV-B |
| CMAF-Net（手机三分类压力/情绪） | 自建 87 人 2,200 样本测试集，Accuracy / macro-F1 | 0.88 / 0.89 | **0.88 / 0.89** | **无可测量损失**（ECE < 0.02，阈值可直接沿用） | 同行评审 | [ACI 2025](http://ftp.nowpublishers.com/aci/article/doi/10.1108/ACI-08-2025-0346/1327676/Knowledge-guided-cross-modality-attention-for) §5.4 |
| wav2vec2-base（ASR，非情感） | LibriSpeech test-clean（960 h，No LM），WER↓ | 3.7 | **4.0** | **+0.3** | 二手实测（预印本） | [arXiv 2202.05993](https://arxiv.org/abs/2202.05993) 表 2 |
| wav2vec2-base | LibriSpeech test-other（960 h，No LM），WER↓ | 9.0 | **10.0** | **+1.0** | 二手实测 | 同上 |
| AST（音频分类 / Speech Commands V2，ESC 校准） | Accuracy↑ | 98.13 | **98.15（INT8）** | **+0.02（无损）** | 二手实测（预印本） | [arXiv 2603.08173](https://arxiv-vanity.com/papers/2603.08173) 表 1 |
| AST | 同上，Accuracy↑ | 98.13 | **96.41（INT4）** | **−1.72（相对 −1.75%）** | 二手实测 | 同上 |
| Conformer（ASR / LibriSpeech，ESC 校准） | WER↓ | 15.94 | **16.01（INT8）** / **38.49（INT4）** | INT8 +0.07｜**INT4 +22.55（崩）** | 二手实测 | 同上 |
| ECAPA（说话人，仅供参照） | VoxCeleb EER↓ | 0.97 | 0.94（INT8）/ **11.28（INT4）** | INT4 崩 | 二手实测 | 同上 |

> **DistilHuBERT 那一行必须带一句限定**：论文**没有做"同一模型 fp32 vs INT8"的消融**。61.4 vs 67.2 是**"蒸馏到 23.49M + 8-bit 量化"相对"全量 95M wav2vec2 base"的合计差**，其中蒸馏贡献多少、量化贡献多少，该文没有拆。**不能把它读成"INT8 量化让 SER 掉了 5.8 点"。**

#### 4.4.2 「INT8 在 SER 上掉点是否比在 ASR 上更严重？」

**直接答案：未检索到。** 没有找到任何一篇在同一批实验里**同时**报告 SER 与 ASR 的 fp32→INT8 掉点的论文，因此无法给出"SER 比 ASR 多掉 X 点"这种数字。

能拿到的**间接证据**（三条，方向不一致，都要带限定引用）：

1. **机制上，音频模型确实比视觉/NLP 更怕量化——但怕的是激活量化，尤其是 INT4。** arXiv 2603.08173 用 Conformer（音频）/ ResNet（视觉）/ BERT（NLP）对照证明：三者做 **4-bit 权重量化**都几乎不掉，但做 **4-bit 激活量化**时**只有 Conformer 严重退化**。原文结论：*"unlike in vision or NLP, audio models are particularly sensitive to activation quantization"*；原因是音频激活的校准范围极大，Max/Percentile 这类标准校准会把绝大多数值压到同一个整数级。→ 这条是**"音频量化更难"的最硬证据**，但它测的是 Conformer/ASR，**不含 SER**。
2. **在"粗粒度分类"这一档，INT8 实测基本无损。** CMAF-Net（三分类压力/情绪，同行评审）量化后 acc/macro-F1 完全不变；AST 在 INT8 下 +0.02。而 wav2vec2 ASR 在 INT8 下 WER +0.3~1.0。**把这三条放一起看：INT8 在 SER 上的掉点没有比 ASR 更严重，反而因为在分类任务上（而非序列生成）显得更不敏感。**
3. **真正会掉点的是 INT4，且情感任务没有 INT4 数据。** INT4 下 Conformer WER 从 15.94 崩到 38.49、ECAPA EER 从 0.97 崩到 11.28，而 AST（分类任务）只掉 1.75% 相对值。**SER 在 INT4 下会怎样——未检索到。**

**给 04 的写法建议**：现有证据**不支持**"INT8 在 SER 上掉点明显比 ASR 严重"这一说法；可引用的结论是「**INT8 在 SER 上基本无损（同行评审证据：0.88→0.88），真正危险的是 INT4 的激活量化，而音频比视觉/NLP 对激活量化更敏感（arXiv 2603.08173）**」。laos 若走量化，**停在 INT8 / w8a8 是安全的，往下压到 INT4 没有证据支撑**。

---

### 4.5 对 laos 的三条可直接执行的推论

1. **proot 现状 = §4.1.2 的 CPU 行，不是 NPU 行。** 在 proot Ubuntu 里，WavLM-base+ 一类的中型模型只能走 CPU，实测参考值是 **RTF 7.1×10⁻²（8 Gen 3 TFLite/CPU）到 2.85×10⁻¹（SA7255P CPU）**，峰值内存 **>1 GB**。这意味着"在 proot 里常驻中型情感模型"**既过不了功耗关（§4.3），也过不了内存关（§4.2）**——内存这条是本次调研新发现的、比功耗更硬的约束。
2. **若一定要在 proot 里跑，小型档 YAMNet 级别是唯一有余量的一档**（NPU 上 RTF ~10⁻⁴，中端 CPU 上 6.4×10⁻⁴），但它在情感任务上的精度不成立（SERAB 跨库 Acc 55.1，见 `01-small-models.md`）。**工程余量与任务精度在小型档上是直接冲突的**，选型时要显式做这个取舍，不要两头都要。
3. **量化停在 INT8，别下 INT4。** INT8 在 SER 上有同行评审的"无损"证据（0.88→0.88）；INT4 在音频任务上有"崩"的证据（Conformer WER 15.94→38.49），且 SER 的 INT4 数据完全空白。SenseVoice-Small 的 Q8_0（254 MB）也是官方明确背书"精度保持一致"的档位，可直接采用。

---

## §5 回填：`edge` 列的档位判定

### 5.1 判定规则（在 00 号文件三值之上加一层档位）

`00-taxonomy-and-metrics.md` 定义了 `edge` 的三个合法值（`yes: <runtime>` / `no` / `unknown(...)`）。本文在其上**再加一层档位标注**，因为在本项目里「能跑」和「能常驻」差三个数量级：

| 档位 | 含义 | 判据 |
|---|---|---|
| **A · 真端侧** | 能在原生 App / aDSP / Sensing Hub 或手机 NPU 上跑 | 有该 runtime 的**官方或实测**转换/运行证据 |
| **B · proot 内** | 能在 proot Ubuntu（glibc aarch64）里用 CPU 跑 | runtime 有官方 aarch64 wheel 或可编译，且内存/时延可接受 |
| **—** | 两端都无证据 | 记为 `unknown(...)` |

**`yes` 仍按 00 号文件的规矩：必须带 runtime 名。** 只报了量化体积、没有 runtime 的，一律降为 `unknown(...)` 并写明原因——这一条在本轮回填里实际生效了一次（DistilHuBERT）。

### 5.2 小型档回填（`01-small-models.md`，16 条）

| 模型 | 表中 `edge`（回填后） | A 档 | B 档 | 依据 / 本轮变更 |
|---|---|---|---|---|
| YAMNet (3.7M) | `yes: TFLite / ONNX / QNN，w8a8 + w8a16 档齐全（AI Hub 实测 0.096–0.699 ms）` | ✅ | ✅ | **已变更**：原只写"AI Hub 已给出部署档"，本轮补齐逐芯片与逐精度实测数字（§3.2.8.4、§4.1.1） |
| openSMILE ComParE_2016 | `yes: 原生 C++ 库，无需量化，MCU 可直接运行` | ✅ | ✅ | 不变。B 档补充：proot 内 `apt install` 或源码编译即可，是**唯一非神经、无依赖**的选项 |
| FRILL (10.1M) | `yes: TFLite fp32 38.5 MB / QAT INT8，Pixel 1 单次 8.5 ms` | ✅ | ⚠️ | 不变。A 档有真机实测（Pixel 1）；B 档受限于 `tflite-runtime` 停更在 2023、LiteRT 的 aarch64 wheel **未证实** |
| DistilHuBERT (23.49M) | `unknown(INT8 体积 23 MB 已核实，未检索到 runtime 与实测时延)` | — | — | **已变更（降级）**：原文只报 "quantized footprint 23 MB"，**未点名 runtime**，且时延与 fp32 体积完全空白。按"yes 必须带 runtime"的规矩降级，**不是否定它，是没有证据**（见 §7 空白清单） |
| Moonshine-tiny (27M) | `yes: GGUF Q8_0 34 MB / ONNX，CPU 约 11.2x 实时` | — | ✅ | 不变。llama.cpp 在 Termux/proot 可编译（§2.2） |
| TRILL / TRILLsson 1·2·3 / modified CPC / APC / PASE+ / NPC / TERA / BYOL-A / ECAPA-TDNN | `unknown(未找到公开转换案例)` | — | — | 不变。本轮**未检索到**任何一条的端侧转换案例；ECAPA-TDNN 另按红线 1 标注 `speaker-capable`、不参与选型 |

### 5.3 中型档回填（`02-medium-models.md`，14 条）

| 模型 | 表中 `edge`（回填后） | A 档 | B 档 | 依据 / 本轮变更 |
|---|---|---|---|---|
| wav2vec2-base / HuBERT-base / WavLM-base+ / UniSpeech-SAT-base / data2vec-base（95M 档，5 条） | `yes: ONNX Runtime INT8` | ❌ | ⚠️ | 不变，但**加两条硬限定**（见 §5.4）：① 同构的 WavLM-Base-Plus 在 AI Hub 上**只有 float 档，无 w8a8/w8a16**；② 峰值内存 **1057–1597 MB**。ONNX 是官方唯一支持的后端，ORT 的 INT8 PTQ 是通用工具，故 `yes` 成立 |
| wav2vec2-Large / HuBERT-Large / WavLM-Large / UniSpeech-SAT-Large（316M 档，4 条） | `unknown(未找到公开转换案例)` | — | — | 不变。AI Hub 上**未检索到** wav2vec2 或 HuBERT 的条目（只有 WavLM-Base-Plus） |
| **emotion2vec_plus_large (164M)** | `yes: ONNX（FunASR 官方导出，648,972,628 B，误差 6.20e-6；导出的是帧级特征，非情感标签）` | — | ⚠️ | **已变更（升级）**：FunASR PR #2359 提供了官方 ONNX 导出（648,972,628 bytes），是**唯一与 SER 直接相关的公开转换案例**（§3.3 表② 第 1 行）。注：导出后仍需自接分类头 |
| emotion2vec_base / emotion2vec_plus_base | `unknown(未找到公开转换案例)` | — | — | 不变。官方 ONNX 导出目前只见于 plus_large |
| Chinese-HuBERT (95M) | `unknown(未找到公开转换案例)` | — | — | 不变 |
| SenseVoice-Small (234M) | `yes: ONNX Runtime INT8（sherpa-onnx 导出 ~229 MB）/ GGUF Q8_0（llama.cpp ~254 MB）` | — | ✅ **首选** | 不变，补强证据：sherpa-onnx 有**官方** `manylinux_aarch64` 与 `android_arm64-v8a` wheel，无需编译；**一个前向同时吐文本/语种/情感/事件**，与漏斗③形态天然合拍（§2.2 表①） |

### 5.4 中型档「`yes` 不等于能进端侧」——必须一起读的两条限定

中型档 5 条 95M 模型的 `edge = yes: ONNX Runtime INT8` **不能读成"可以端侧部署"**。两条限定：

1. **同构模型在 AI Hub 上没有量化档。** WavLM-Base-Plus（95.1M，与 wav2vec2/HuBERT 完全同构）在 AI Hub 上只有 float 行；**w8a8 / w8a16 未检索到**。对照同一站点上的 YAMNet（纯 CNN）三档量化齐全。**这条对比本身就是信号：卷积+注意力编码器的量化路径在高通官方pipeline 里没打通。**
2. **峰值内存 1.0–1.6 GB。** 8 Gen 3 NPU 上最高 **1413 MB**、TFLite/CPU 上最高 **1597 MB**（20 s 输入）。laos 的常驻预算在内存这一侧先崩，比功耗更早崩。

因此中型档的准确定位是：**B 档（proot 内 CPU）触发式可用，A 档不成立**。

### 5.5 本轮发现的一处口径冲突（记录，不单方面采信）

| 项 | 说法 A | 说法 B | 处理 |
|---|---|---|---|
| SenseVoice-Small int8 体积 | **229 MB**（sherpa-onnx 官方导出卡：`model.onnx` 895 MB → `model.int8.onnx` 229 MB） | **8 MB**（社区汇编口径，同时报 RTF≈0.1） | 采信 **229 MB**（官方导出卡，且 §4.2 有 Q8_0 精确字节数 254,211,200 B 佐证）。8 MB 疑为早期精简版或笔误，**不作为预算依据** |

---

## §6 红线自检

1. **不存声纹。** 本文涉及的全部工程数字（时延/内存/体积/功耗）都不涉及说话人向量。`01` 里的 ECAPA-TDNN 已标 `speaker-capable` 且**不出现在任何档位推荐中**；`02` 里的 WavLM / UniSpeech-SAT 同此。**本文的 B 档首选（SenseVoice-Small）不产出说话人嵌入。**
2. **情绪标签非临床。** 本文只谈工程可行性，不涉及任何健康声称。已知最大规模的语音抑郁检测研究敏感度与特异度均仅 **71%**（见 [`../always-on-recording/academic-papers.md`](../always-on-recording/academic-papers.md)），任何临床用途都必须标注"非诊断"。
3. **中文场景已覆盖。** 本文 B 档首选 SenseVoice-Small 在 **CASIA (zh) WA 70 / MER2023 (zh) WA 68** 上有公开数字（见 `02-medium-models.md` §4.3），满足"至少覆盖 2 个中文基准"的红线。
4. **不许编造。** 所有查不到的项集中在 §7 空白清单；三份来源里"未检索到"均原文保留，未用二手数字填充。

---

## §7 空白清单（合并自三份调研，按对选型的影响排序）

| 缺口 | 状态 | 对选型的影响 |
|---|---|---|
| emotion2vec（base / plus_large）在手机或 RPi 上的**官方**时延与内存 | **未检索到官方来源**；仅有多篇二手实测且**互相矛盾**（同为 RPi 4B 跑 10 s 音频，分别报 1.6 s / 2.5–3.5 s / 4.2 s），按红线不引用 | **最大**：中文 SER 主力模型缺可信工程数字 |
| Qualcomm AI Hub 的功耗 / 能耗数字 | **平台不提供**（只报时延、吞吐、峰值内存、计算单元） | 高通体系（laos 主战场）的功率只能靠非高通实测外推 |
| 手机 NPU（Hexagon HTP）上跑**情感模型**的实测功耗 | **未检索到** | Hexagon 1–4 W 包络目前是从"LLM 解码"和"MobileNetV3"两处外推的，不是 SER 实测 |
| QNN 在 laos 真机上的 on-device 延迟 / 内存 / 功耗 / 转换成功率 | **未记录**（既有 runbook 只有"链路跑通"） | laos 唯一的真端侧原型**性能未测**，A 档无法定量 |
| DistilHuBERT 的 fp32 体积、任何平台上的时延、以及 fp32 vs INT8 的**单独消融** | **未检索到**（61.4 vs 67.2 是"蒸馏 + 量化"合计） | 小型档最优候选缺工程数字，"量化掉多少点"在小型档没有干净数字 |
| SER 在 **INT4** 下的精度 | **未检索到** | 无法评估"再压一半体积"的可行性 |
| openSMILE（ComParE / eGeMAPS）特征提取的耗时或 RTF | **未检索到**官方或同行评审数字 | 非神经基线只有精度、没有工程数字，无法进预算表 |
| TRILLsson / FRILL 在 TFLite / QNN 上的时延与内存 | **未检索到**（FRILL 只有 Pixel 1 的 8.5 ms） | 小型档三条主力里两条缺工程数字 |
| 耳机 / 手表上做**声学**情感识别的整机功耗 | **未检索到**（只有非声学的 EarIO 154 mW / IMUFace 58 mW 作参照） | "常开情感"在可穿戴上的预算无法直接定 |
| MLPerf Tiny / Mobile 中 SER 任务的 µJ 数字 | **不存在**（Tiny 唯一音频任务是 KWS；Mobile 无音频任务） | 拿不到权威的 SER 能耗横比基准 |
| 7B 级语音大模型的端侧时延 | **未检索到** | 大型档对照只能靠 Whisper-Large-V3-Turbo |
| QNN 逐算子 × 后端 × 精度支持矩阵 | 页面存在（Rev AL, 80-63442-10），但**JS 门禁未取到逐行内容** | 算子兼容性只能靠论坛根因帖与 ORT 文档推断 |

---

## §8 对 laos 的四条可执行结论

1. **漏斗①（常驻检测）在 proot 里不成立，且这不是优化能解决的。** 任何醒着的 proot 进程都在 400 mW 量级，比 aDSP 方案贵 2–3 个数量级。`mic.always_on` 这一级必须走出 proot——与 [`hardware-power.md` §7.5](../always-on-recording/hardware-power.md) 的建议一致。
2. **漏斗③（触发后蒸馏）的当下最优解是 sherpa-onnx + SenseVoice-Small int8**，不是 funasr。理由：sherpa-onnx 有官方 aarch64 wheel、不依赖 torch、**一个前向同时产出文本/语种/情感/事件**；而 funasr 路径要装 torch（GB 级内存、数秒加载），且唯一 RTF 证据来自 PC。
3. **"上 NPU"不等于"进 mW 档"。** 第三方 App 能用的 NPU 是 HTP（瓦级）；mW 档的 aDSP/LPAI 需要高通授权 + 厂商签名。laos 目前握有前者（QAIRT 2.47 + `TimnetLpaiApp` 已跑通闭环），后者是**授权问题，不是技术问题**。
4. **量化停在 INT8，别下 INT4。** INT8 在 SER 上有同行评审的"无损"证据（0.88 → 0.88）；INT4 在音频任务上有"崩"的证据（Conformer WER 15.94 → 38.49），且 SER 的 INT4 数据完全空白。

---

## §9 参考来源

### 9.1 端侧 runtime 与量化（§3）

**官方（Qualcomm / AI Hub）**
- QNN 后端库（含 LPAI `libQnnLpaiIsland.so`，v5 起可执行）：https://docs.qualcomm.com/bundle/publicresource/topics/80-63442-10/backend.html
- QNN 逐算子 × 后端 × 精度支持表（Rev AL，80-63442-10；本次 JS 门禁未取到逐行内容）：https://docs.qualcomm.com/bundle/publicresource/topics/80-63442-10/SupportedOps.html
- AI Hub — YAMNet 模型页（Galaxy S26 / SD8 Elite Gen 5，96.0 μs）：https://aihub.qualcomm.com/models/yamnet
- AI Hub — YAMNet profile job `jpyxdxq05`（QCS6490，525 μs；⚠️ 复核 404）：https://aihub.qualcomm.com/jobs/jpyxdxq05
- AI Hub — Whisper-Tiny 模型页（X2 Elite 1.35 ms；Galaxy S25 1.56 ms）：https://aihub.qualcomm.com/models/whisper_tiny
- AI Hub — WavLM-Base-Plus profile job `j5627y00g`（SD8Gen2，228 ms，3–422 MB，686 NPU ops）：https://aihub.qualcomm.com/jobs/j5627y00g
- HF `qualcomm/YamNet`（逐芯片 + w8a8/w8a16 完整表格）：https://huggingface.co/qualcomm/YamNet
- HF `qualcomm/HuggingFace-WavLM-Base-Plus` README（完整性能表）：https://huggingface.co/qualcomm/HuggingFace-WavLM-Base-Plus/blame/main/README.md
- MathWorks：LPAI 要求 context binary + eNPU v5+：https://ww2.mathworks.cn/help/ecoder/qualcommhexagon/ug/deploy-deep-neural-networks-qualcomm-qnn-example.html

**官方（ONNX Runtime / Optimum / 上游项目）**
- ORT QNN Execution Provider（支持算子表、Gelu/LayerNorm/Gather 正索引/无动态 shape/无 Loop-If）：https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html
- ORT 自定义 / minimal build：https://onnxruntime.ai/docs/build/custom.html 、reduced-operator 配置：http://onnxruntime.ai/docs/reference/operators/reduced-operator-config-file.html
- Optimum 导出与量化能力矩阵：https://github.com/huggingface/optimum
- ORT 官方博客：Phi-3-mini int4 跑 Galaxy S21：http://onnxruntime.ai/blogs/accelerating-phi-3
- pytorch/executorch QNN LayerNorm 修复（PR #18990 / fixes #18989，commit 0e8c146）：https://github.com/pytorch/executorch
- LiteRT for Microcontrollers 概览（16 KB / 无动态分配 / 算子子集）：https://developers.google.cn/edge/litert/microcontrollers/overview
- coremltools 优化工作流（palettization / linear quantization / QAT）：https://apple.github.io/coremltools/docs-guides/source/opt-workflow.html
- 导出器已知不支持清单（Wav2Vec2 / HuBERT / SEW / WavLM / Data2VecAudio / UniSpeech）：https://github.com/aidyai/exporters
- onnx2tf 已知坑（动态 rank、NHWC/NCHW、Python ≥3.12、校准集）：https://github.com/PINTO0309/onnx2tf
- ncnn 量化 int8 推理文档：https://github.com/Tencent/ncnn/blob/master/docs/how-to-use-and-FAQ/quantized-int8-inference.md
- ncnn pnnx 算子状态表（`F.layer_norm` 支持）：https://github.com/Tencent/ncnn/pull/3262/commits/7679005a265ed4dd07733eb4c803ebb4d02b4cc0
- FunASR emotion2vec ONNX 导出（PR #2359）：https://github.com/modelscope/FunASR/commit/3530688e0a1b1dfbb22dcd3324db97be5bbc0d9b ；核验讨论 https://github.co.uk/modelscope/FunASR/discussions/2151
- sherpa-onnx CMakeLists（NPU 后端开关）：https://github.com/k2-fsa/sherpa-onnx/blob/master/CMakeLists.txt
- sherpa-onnx SenseVoice 导出（model.onnx 895 MB / model.int8.onnx 229 MB）：https://k2-fsa.github.io/sherpa/onnx/sense-voice/export.html

**同行评审**
- arXiv 2510.18036（Coral Dev Board Micro；1.8 MB / 21–23 ms / 2.5 W；MHSA over 3D 不被支持）：https://arxiv.org/abs/2510.18036 、全文 http://ar5iv.labs.arxiv.org/html/2510.18036
- "Emotion AI on the Edge"，Expert Systems 2026，DOI 10.1111/exsy.70322（TFLite 量化 −94.5%，延迟低至 3.4 ms，74.15% acc）：https://doi.org/10.1111/exsy.70322

**二手实测（已逐条标注）**
- Qualcomm 支持论坛：HTP 图准备失败 `could not create op: q::Gather` / `no properties registered for q::QNN_Gelu`：https://mysupport.qualcomm.com/supportforums/s/question/0D5dK00000I4PnDSAV/
- QNN Linux 工具链清单：https://blog.csdn.net/weixin_51031772/article/details/141331531 、https://github.com/microsoft/edgeai-for-beginners/blob/main/translations/zh-CN/Module04/07.QualcommQNN.md
- QNN 量化命令行（CLE / Adaround / per-channel / quantization_overrides / int4）：同上
- ai-hub-apps ONNX 部署教程（QDQ 折叠、INT4 打包）：https://deepwiki.com/qualcomm/ai-hub-apps/4.3-onnx-deployment-tutorial
- Ultralytics QNN 集成（W8A16 为 HTP 首选、HTP arch 映射 v68–v81、小米 17 实测 11.3 ms vs 53.3 ms）：https://docs.ultralytics.com/zh/integrations/qnn
- RKNN-Toolkit2 用法与混合量化（Transformer Attention 为敏感层、RK3588 6 TOPS@INT8）：https://blog.gitcode.com/13304c713ad67dddd45b949b681e382a.html
- sherpa-onnx 的 RKNN 版本地雷（2.1.0 失败 / 2.2.0 可用 / 2.3.2 段错误）：https://blog.csdn.net/gitblog_00492/article/details/160735355
- MNN 量化（KL/ADMM/EMA、EMA <1% 损失 1.5× 提速、SD8Gen3 ResNet-50 550 ms→379 ms）：https://juejin.cn/post/7598021081987268659 、https://blog.csdn.net/gitblog_00639/article/details/152109018
- MNN-Transformer（int4/int8、channel/block-wise、GPTQ、KV 量化）：https://www.besthub.dev/articles/mnn-transformer-efficient-on-device-large-language-and-diffusion-model-deployment-75815f40d39d
- ncnn onnx2ncnn `LayerNormalization not supported yet`：https://blog.gitcode.com/69a0f0a0680eca9b48585a3fa685cceb.html
- ncnn RK3588 ResNet50 FP16 43.46 ms / INT8 24.80 ms：https://blog.csdn.net/m0_61864577/article/details/148031677
- ESP32 上 TFLite Micro 内存口径（arena 80–120 KB，总 50–200 KB，60–80 算子）：https://www.foresthub.ai/resources/guides/how-to-run-tensorflow-lite-on-esp32
- Arm Ethos-U / Vela 部署（SRAM 146.31 KiB，ACTIVATION_BUF_SZ 2–4 MiB）：https://deepwiki.com/alifsemi/alif_ml-embedded-evaluation-kit/8.2-model-integration-and-deployment
- ORT Mobile 体积 10–15 MB → minimal build 4–5 MB：https://www.huggingface.co/blog/tugrulkaya/running-large-transformer-models-on-mobile
- CoreML ANE 阻塞算子汇编：https://lobehub.com/it/skills/ckorhonen-claude-skills-coreml-optimizer
- wav2vec2 → TFLite 报错 `Only ['onnx'] are supported`：https://devhide.com/convert-hugging-face-audio-classifier-to-tflite-format-77892732
- TinyML SER（1.5 MB → 150 KB int8，4.391 s → 0.299 s）：https://github.kazgu.com/Kashish0212/Speech-Emotion-Recognition-TinyML

**本仓库内部**
- [`../2026-09-09-qnn-real-os-integration.md`](../2026-09-09-qnn-real-os-integration.md)（QAIRT 2.47、TIM-Net/LIGHT-SERNET、7 个算子坑、QNN CPU ≈6 ms）
- [`00-taxonomy-and-metrics.md`](00-taxonomy-and-metrics.md)（`edge` 列口径与"查不到就删"规则）

### 9.2 proot 与真机权限（§2）

**官方（厂商 / 上游项目）**
- ONNX Runtime 1.26.0 aarch64 wheel 清单：https://pypi.org/project/onnxruntime/1.26.0/#files
- Android 从后台启动前台服务的限制（mic FGS / SecurityException）：https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
- Qualcomm sensing hub 架构（aDSP/QSH 仅限授权用户）：https://docs.qualcomm.com/doc/80-70029-7/topic/architecture.html
- Qualcomm LiteRT 架构与 QNN delegate / HTP 后端库：https://docs.qualcomm.com/doc/80-70018-54SC/topic/arch.html
- Qualcomm AI Hub Apps（普通 Android App 用 NPU，API 30+，chipset 列表）：https://github.com/qualcomm/ai-hub-apps
- Qualcomm AI Hub Models（CPU/GPU/NPU 精度矩阵与 chipset 列表）：https://github.com/qualcomm/ai-hub-models
- GenieX 平台与运行时（Android SDK + llama_cpp 默认 pin HTP0）：https://geniex.aihub.qualcomm.com/en/get-started/platforms/
- Qualcomm Dragonwing：aarch64 Linux 上 ORT 无官方 QNN wheel：https://dragonwingdocs.qualcomm.com/Ubuntu/ai-workflows/onnxruntime
- FunASR / SenseVoiceSmall（330M 参数，`pip install -U funasr`）：https://github.com/modelscope/FunASR 、https://huggingface.co/FunAudioLLM/SenseVoiceSmall
- sherpa-onnx 1.13.8 wheel 清单（含 manylinux aarch64 与 android arm64-v8a）：https://pypi.org/project/sherpa-onnx/#files 、https://github.com/k2-fsa/sherpa-onnx
- llama.cpp Snapdragon / Hexagon 后端官方 README（adb 部署、HTP v73/v75/v79/v81、bench 数字）：https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/README.md
- PyTorch aarch64 CPU wheel 索引：https://download.pytorch.org/whl/cpu 、清单镜像 https://mirrors.aliyun.com/pytorch-wheels/cpu/ 、Arm 官方安装指引 https://learn.arm.com/install-guides/pytorch/
- PyTorch 2.14 RC（明确 "Linux x86 and aarch64"）：https://dev-discuss.pytorch.org/t/pytorch-2-14-final-rc-available/3429

**内核 / 权威邮件列表（第三方 App 权限边界的关键证据）**
- misc: fastrpc: Restrict untrusted apk to spawn（第三方 App 不能 open fastrpc 设备；signed PD / audio PD → `-EACCES`）：https://lwn.net/ml/linux-kernel/20240508054250.2922-4-quic_ekangupt@quicinc.com/
- LKML：ADSP 只支持 signed 模块，CDSP/GDSP 支持 unsigned：https://ns1.openwall.net/linux-kernel/2025/11/27/251

**可核验实测**
- M5Stack 文档：sherpa-onnx-offline SenseVoice 在 AX650 上 RTF = 0.015（NPU）：https://docs.m5stack.com/en/guide/ai_accelerator/llm-8850/m5_llm_8850_sherpa-onnx
- termux-app issue #2219（裸 Termux `import torch` 失败 `libgomp.so.1 not found`）：https://github.com/termux/termux-app/issues/2219

**社区 / 二手（已标注可信度）**
- llama.cpp Termux 编译与实测（SD 8 Gen 2，llama-2-7B Q4_0 3.67 t/s）：https://github.com/MrDoe/llama.cpp-android-tutorial
- Termux 上 Qwen2.5-0.5B Q4_K_M 14 t/s / 首 token 3.4 s：https://blog.csdn.net/weixin_35433448/article/details/156493366
- 8 GB 手机 Termux 长跑（Qwen2.5-3B Q2_K ~5 t/s）：https://www.hotmolts.com/post/running-an-ai-agent-on-a-phone-8gb-ram-termux-no-r-70dfad35-ab4a-4be4-a39e-6b952c1dafb2
- sherpa-onnx SenseVoice int8 8 MB / RTF≈0.1 汇编：https://adg.csdn.net/6952387e5b9f5f31781b36ca.html
- RPi4B 上 SenseVoice RTF 0.28 实测记录：https://agent.csdn.net/6a4e65b0662f9a54cb8bf451.html
- LiteRT 取代 TFLite / NNAPI 弃用后的迁移对照：https://www.bestblogs.dev/en/article/a7ce684a43
- NNAPI 弃用与 LiteRT 迁移实践：https://www.cnblogs.com/vincentson/p/20524700 、https://meetonfriday.com/posts/666bbf67/ 、https://www.forasoft.com/blog/article/neural-networks-on-android-369
- proot-distro 机制（ptrace，非虚拟化，完整 rootfs）：https://termuxtools.com/proot-distro-linux-termux 、https://sinapti.ca/post/es/linux-en-tu-android-sin-root-proot-distro-debian-y-la-termin-qhfxy31v
- Android 16 Linux Terminal（AVF/pKVM，外设隔离）：https://ivonblog.com/en-us/posts/termux-vs-android-linux-terminal 、https://www.makeuseof.com/used-new-linux-terminal-on-android-impressed/

**本仓库内部（口径已在 §2.1 声明）**
- [`../always-on-recording/hardware-power.md`](../always-on-recording/hardware-power.md)（功耗阶梯，本文只引用不重算）
- [`../qnn-real-device-runbook.md`](../qnn-real-device-runbook.md)（真机闭环、端点清单、无实测数字）
- [`../2026-09-09-qnn-real-os-integration.md`](../2026-09-09-qnn-real-os-integration.md)（QAIRT 2.47、TIM-Net/LIGHT-SERNET、SEE/eAI、QNN CPU ≈6 ms）

### 9.3 实测预算（§4）

- Qualcomm AI Hub 工作原理（profile 只报时延/吞吐/峰值内存，不报功耗；时延为多次迭代最小观测值）：https://app.aihub.qualcomm.com/docs/zh_TW/hub/howitworks.html
- arXiv 2510.18036（Coral Dev Board Micro 上 1.8 MB INT8 情绪模型连续推理 2.5 W）：https://arxiv.org/abs/2510.18036
- ACI 2025（CMAF-Net，手机 TFLite CPU 情绪推理 38.2 / 52.6 mJ 每次，INT8 精度无损）：http://ftp.nowpublishers.com/aci/article/doi/10.1108/ACI-08-2025-0346/1327676/Knowledge-guided-cross-modality-attention-for
- arXiv 2202.05993（RPi 4B 上 wav2vec2-base 的 RTF 与 USB 功率计实测）：https://arxiv.org/abs/2202.05993
- arXiv 2603.08173（音频模型对**激活量化**比视觉/NLP 更敏感；Conformer INT4 崩）：https://arxiv-vanity.com/papers/2603.08173
- arXiv 2512.23435（DistilHuBERT INT8 体积 23 MB）：https://arxiv.org/abs/2512.23435
- MLPerf Tiny v0.7 / v1.1 / v1.2（Syntiant KWS 31.5–49.6 µJ/次，唯一音频任务）：https://www.syntiant.com/news/syntiant-ndp120-achieves-outstanding-results-in-latest-mlperf-tiny-v07-benchmark-suite
- MLPerf Mobile v4.0（无音频任务）：https://mlcommons.org/?p=323
- EarIO 154 mW（耳机声学连续感知）DOI 10.1145/3534621 ｜ IMUFace 58 mW arXiv 2501.02177
