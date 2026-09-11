# 端侧硬件与功耗：一直开着，到底多贵

> 调研时间：2026-09-11 ｜ 姊妹篇：[academic-papers.md](academic-papers.md)（学术线）、[../always-on-recording-industry-2026-09.md](../always-on-recording-industry-2026-09.md)（产品与开源线）
> 本文只做两件事：**把"常开"的功耗换算成 laos 能用的预算数字**，以及**钉死真机（Android / proot）上哪些事根本做不到**。每条数字标来源与可信度，查不到的一律写 `未证实`。

---

## 一句话结论

**"常开"不是一种能力，而是一个跨越 4 个数量级的功耗阶梯**：定制 ASIC 上亚微瓦（0.047–1 µW）→ 专用音频 NPU 上百微瓦（140 µW）→ 手机里的传感中枢 / aDSP 上数毫瓦（官方口径 <1 mA）→ **应用处理器上"常醒听"数百毫瓦到数瓦**。laos 声称的 ADSP LPAI <5 mW 处于阶梯第三级，是**通用平台上能做到的最好位置之一**；但它在 laos 当前的 proot Ubuntu + Termux 架构里**根本拿不到**——proot 内的 Python 只能拿到 AP 层的 OpenSL/PulseAudio 流，代价是直接掉到阶梯最底层（数百 mW）。这是本调研对 laos 最重要的一条结论。

---

## 0. 换算基准：把 "%/小时" 读成 mW

后续所有数字统一到 mW。基准取典型手机电池 **5000 mAh × 3.85 V = 19.25 Wh**（标称电压 3.85 V，容量标称值）。

| 功耗 | 折算耗电 | 折算一天 |
|---|---|---|
| 5 mW（laos ADSP 目标） | 0.026 %/h | **0.62 %/天** |
| 25 mW | 0.13 %/h | 3.1 %/天 |
| 100 mW | 0.52 %/h | 12.5 %/天 |
| 200 mW | 1.04 %/h | **25 %/天** |
| 1 W | 5.2 %/h | 不可能（约 19 h 耗尽） |

> 读法：任何"全天候"能力只要进入 100 mW 量级，就意味着**一天吃掉四分之一的电**，用户会立刻关掉它；进入 1 W 量级则根本不成立。laos 的四级能力阶梯里 `mic.always_on` 这一级，工程上的准入线就是 **≤25 mW（≈3%/天）**。

---

## 1. 器件级：麦克风本身不是瓶颈

| 器件 | 模式 / 电流 | 折算功耗（按 1.8 V） | 可信度 | 来源 |
|---|---|---|---|---|
| TDK T5838/T5848（带 AAD 声学活动检测） | 休眠待唤醒 **20 µA**；数字滤波模式 **137 µA** | 0.036 mW / 0.25 mW | 厂商官方 | [TDK InvenSense](https://invensense.tdk.com/news-media/blog/high-performance-mems-microphones-enable-user-friendly-ai) |
| TDK ICS-43434（I²S） | AlwaysOn 模式 **230 µA**；Sleep **12 µA**；唤醒 10–14 ms | 0.41 mW / 0.02 mW | 经销商规格页（二手） | [Digi Electronics](https://www.digi-electronics.ca/ca/products/detail/invensense/ICS43434/6631513.html) |
| Infineon IM68D128B（PDM） | 正常 **580 µA**；低功耗 **190 µA**；SNR 67.5 dB(A) | 1.04 mW / 0.34 mW | 官方 datasheet | [Infineon PDF](https://www.infineon.com/assets/row/public/documents/24/49/infineon-im68d128b-datasheet-en.pdf) |
| TDK T3902 | 低功耗模式 **185 µA** | 0.33 mW | 厂商访谈 | [Yole 访谈](https://www.yolegroup.com/strategy-insights/mems-microphones-are-still-improving-and-continue-to-enhance-the-human-device-communication-an-interview-with-tdk-invensense/) |
| TDK ICS-40310（模拟） | 最低功耗模拟麦 **16 µA** | 0.026 mW | 厂商访谈 | 同上 |
| ST MP23DB02MM | Sleep **2 µA** / 低功耗 **285 µA** / 正常 **800 µA** | 0.004 / 0.51 / 1.44 mW | 行业汇编（二手） | [SISTC 选型指南](https://sistc.com/zh/low-power-mems-microphone-selection-guide) |

**对 laos 的关系**：麦克风整链（含 AAD 待唤醒）在最差情况下也只有 **~1 mW**，在最好的 AAD 休眠模式下是 **0.036 mW**。这意味着 ①常驻检测的功耗**几乎全部花在"谁来处理麦克风数据"上，而不是麦克风本身**。laos 的 `<5 mW` 预算里，麦克风最多占 1 mW，其余 4 mW 全是处理开销——这个分配关系应当在 laos 的技术文档里写明，否则"<5 mW"会被误读成"麦克风很省电"。

---

## 2. 常驻检测级（漏斗①）：从 140 µW 到数 mW

| 平台 | 关键数字 | 可信度 | 对 laos 的关系 | 来源 |
|---|---|---|---|---|
| **Syntiant NDP120**（专用音频 NPU） | always-on voice 全程推理 **140 µW**；MLPerf Tiny v0.7：**35.29 µJ/推理** @0.9 V/30 MHz（4.3 ms）/ 49.59 µJ @1.1 V/98 MHz（1.8 ms）；同期 MCU 方案 **>7300 µJ/推理（差 120×）** | 厂商官方 + MLCommons 公开榜 | 换算成每 100 ms 推一次 = **0.35 mW**、每秒一次 = **35 µW**。这是"①常驻检测"的现实地板，也是 laos 对标 `<5 mW` 时最该引用的对手数字 | [Syntiant 博客](https://www.syntiant.com/?p=7959/)、[MLPerf 结果](https://www.syntiant.com/news/syntiant-ndp120-achieves-outstanding-results-in-latest-mlperf-tiny-v07-benchmark-suite) |
| **Syntiant NDP250** | 30 GOPS，always-on **<1 mW**，多模态（语音+视觉+IMU） | 厂商 + 汇编 | 说明"常驻 <1 mW"已经是货架商品，不是实验室指标 | [Electronics-Lab](https://www.electronics-lab.com/syntiant-unveils-ndp250-a-breakthrough-in-microwatt-ai-processing-for-always-on-applications/) |
| **Qualcomm Sensing Hub（二代，骁龙 888）** | 官方原话：Sensing Hub 上的**全部处理 < 1 mA**；可卸载 Hexagon 常规负载的 **80%** | **高通官方 PDF** | laos 走 ADSP/LPAI 路线最硬的一条外部锚点：手机厂商自己给的常驻预算是"亚毫安"级。laos 的 <5 mW 与之一致（1 mA @ 传感域电压 ≈ 数 mW） | [Qualcomm 888 AI 博客 PDF](https://www.qualcomm.com/media/documents/files/snapdragon-888-ai-blog-post-by-jeff-gehlhaar-vp-of-technology-hsin-i-hsu-senior-product-manager.pdf) |
| **Snapdragon 8 Elite Gen 5 Sensing Hub** | 升级为**双 Micro NPU**（"Dual always-sensing"），专司语音/运动等连续感知 | 官方规格（镜像/媒体转载） | 架构上确认了"常驻感知独立供电域"已是旗舰标配；**官方未给功耗数字 → 功耗 未证实** | [规格汇编](https://radargit.com/2026/03/03/qualcomm-snapdragon-8-elite-gen-5-review-and-specs)、[发布会报道](https://it.sohu.com/a/938579003_120157221) |
| **Hexagon aDSP** | aDSP 在主 ARM 核心睡眠时处理音频流（QuRT + Elite 框架）；同算法在 DSP 上功耗约为 ARM/NEON 的 **1/3** | 官方 + 合作方技术博客 | 官方只给比例不给绝对值，**"<2 mW" 的说法只见于中文二手博客，标注为存疑，不引用** | [Lantronix 技术博客](https://www.lantronix.com/blog/using-the-hexagon-dsp/) |
| **ESP32-S3 + esp-sr**（对照：便宜方案） | 持续监听 **<50 mW**；唤醒待机 **8 mA（≈26 mW @3.3 V）**；唤醒延迟 80–120 ms | 开发者实测（二手） | 给 laos 一个"如果只在通用 MCU/AP 上做"的对照：**比专用 NPU 贵 100 倍以上** | [ESP-SR 实测](https://blog.csdn.net/gitblog_01166/article/details/163533732) |

**学术侧的同级对照**（详见 [academic-papers.md](academic-papers.md) §3）：定制 ASIC 的 VAD 可低至 **47 nW**、AAD 门控 KWS **0.36–0.8 µW**、含 MEMS 麦克风与能量采集的整机 **63 µW**。与本节对照可得出一句可对外讲的话：**"软件跑在通用核上 vs 跑在专用检测核上，差 3–4 个数量级"**。

---

## 3. 记录与落盘级（漏斗②）：AudioMoth 给出的权威拆解

AudioMoth（Open Acoustic Devices）是唯一把"长期录音的每一毫瓦花在哪"公开测过的开源平台，同行评审数据可直接引用（Hill et al., *Methods in Ecology and Evolution* 2018 / *HardwareX* 2019）：

| 项目 | 数值 | 来源 |
|---|---|---|
| **microSD 写入（最耗能环节）** | **17–70 mW**（48 kHz 平均 23 mW；8 kHz 17 mW；384 kHz 达 70 mW） | [Hill et al. 2018](https://besjournals.onlinelibrary.wiley.com/doi/abs/10.1111/2041-210X.12955) |
| 端上实时分类（不落盘） | **≤25 mW** | 同上 |
| 睡眠 / 待机 | **80 µW**（三节 AA 锂电可维持计时约 6 年） | 同上 |
| 对照组：跑 Linux 的模块化设备（RPi / Solo） | **空闲 400–1000 mW**；AudioMoth 录 48 kHz 比最省电的同类高效 **15×**，空闲态高效 **4000×** | 同上 |

**占空比调度的实测收益**（官方 Table 8，3×AA 锂电 ≈ 13.5 Wh）：

| 配置 | 调度 | 续航 | 数据量 | 推导平均功耗 |
|---|---|---|---|---|
| Soundscape 48 kHz | 全天连续录 | **9 天** | 64 GB（4 天换卡） | ≈62 mW（录音态） |
| Bird 32 kHz | 06:00–09:00 连续 | **75 天** | 49 GB | ≈60 mW（录音态） |
| Chainsaw 8 kHz | 录 30 s / 睡 300 s（占空 9.1%） | **115 天** | 14 GB | **≈4.9 mW（整机平均）** |
| 实测社区配置（32 kHz，录 1 min / 睡 9 min） | 占空 10% | **~30 天** | ~1.34 GB/天 | ≈19 mW（整机平均，含 SD 型号差异） |

来源：[HardwareX 2019 Table 8](https://www.sciencedirect.com/science/article/pii/S2468067219300306)、[Guardian Connector 部署指南](http://docs.guardianconnector.net/pt/guides/guide-audiomoth/step-2-programming-audiomoth)、[WILDLABS 社区测量](https://www.wildlabs.net/comment/10412)。

**三条对 laos 直接可用的推论：**

1. **落盘比"听"贵 1–2 个数量级**：听（端上分类）≤25 mW，写 SD 17–70 mW。laos 的"只存有声段"（`laos/vad.py` → `drivers/drv_rec.py`）因此不只是隐私设计，**它本身就是最大的省电措施**——与 TinyChirp 的结论（少写 90%、续航 ×4）同构。
2. **占空比是第二有效的手段**：同样电池，9% 占空比把 9 天拉到 115 天（12.8×）。laos 的常开模式（`mic.always_on_start`）若要省电，应提供"周期性抽样监听"档位，而不是只有"全程听"。
3. **跑通用 Linux 的机器空闲就 400–1000 mW**——这句是 laos 真机路线最该记住的数字：proot Ubuntu 里的任何 Python 进程，只要它醒着，就已经在 400 mW 量级，**比整个 AudioMoth 录音态还贵一个数量级**。

---

## 4. 蒸馏级（漏斗③）：AP 与 NPU 的真实价位

| 场景 | 数字 | 可信度 | 来源 |
|---|---|---|---|
| Hexagon HTP 持续功耗包络 | **~1–4 W**（INT8 峰值 ~45 TOPS） | 技术汇编（二手，量级可信） | [Hexagon 架构笔记](https://jvoltci.github.io/mosaic/edge-ai/npu/hexagon) |
| **真机实测**：OnePlus 12 用 NPU 解码 Qwen 1.5B / 3B | 整机功耗 **<5 W**（3B 稳定在 **~4.3 W**），sysfs 实测 | **同行评审论文** | [arXiv:2509.23324](https://arxiv.org/abs/2509.23324) |
| MobileNetV3 三后端（第三代骁龙 8） | CPU **1200 mW** / GPU **900 mW** / Hexagon NPU **300 mW** | 开发者实测（二手） | [CSDN 实测](https://tencentcloud.csdn.net/69eaf28f54b52172bc6facbb.html) |
| 手机常驻听觉（Pixel Now Playing） | 24 小时额外耗电 **2–3%**（≈**24 mW** 折算） | 媒体博客（**未证实**，仅作量级参考） | [分析文章](https://jinguli.connectquest.co.in/technology/04-03-2026/analysis-pixels-now-playing---revolutionizing-media-tracking.php) |

**结论**：ASR / 情感识别（漏斗③）在手机上**无论跑在哪个核上都是"百毫瓦到瓦"级**，只能"触发后短时运行"，绝不能常驻。这与 [industry 报告 §9.1](../always-on-recording-industry-2026-09.md) 的结论完全一致，也解释了为什么所有活下来的产品都是 **buffer-and-burst（本地低码率存着，充电/Wi-Fi 时批量转写）**。laos 的 `bin/journal.py` 批量转写管线方向正确。

---

## 5. 平台与 OS 约束：真机上哪些事根本做不到

> laos 的主战场是 **Android（proot Ubuntu + Termux）**，桌面 Linux/Windows 为辅。这一节直接决定"能力阶梯"里哪些级能在手机上落地。

| 约束 | 内容 | 对 laos 的影响 | 来源 |
|---|---|---|---|
| **Android 9（API 28）起** | 后台应用**无法访问麦克风**（拿到的是静音），必须前台服务 | 常驻录音必须是常驻前台服务 + 常驻通知 | [Android 后台录音综述](http://www.wmrh.cn/news/1151231)（二手，与官方行为一致） |
| **Android 10（API 29）** | 必须声明 `android:foregroundServiceType` | 录音服务需声明 `microphone` | [官方 FGS 文档](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start) |
| **Android 12（API 31）** | 后台**启动**前台服务受限（除豁免外抛 `ForegroundServiceStartNotAllowedException`） | 不能靠"定时/广播"偷偷拉起录音 | 同上 |
| **Android 14（API 34）** | 创建 `microphone` 类型 FGS 时系统**即时校验** `RECORD_AUDIO`；而它是 while-in-use 权限 → **App 在后台时创建直接 `SecurityException`**；且**不能从 `BOOT_COMPLETED` 启动** | **开机自启的常驻录音在标准 Android 上不合法**。正确姿势：在 Activity 可见时（用户点"开始听"）就启动服务，之后才允许退到后台 | [官方 FGS 限制](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start)、[实践复盘](https://widget-chat.com/blog/flutter-microphone-foreground-service-securityexception-android-14) |
| **常驻通知 / 通知权限** | Android 13+ 需 `POST_NOTIFICATIONS`；无可见通知的后台录音会被判定为可疑行为（社区实测：锁屏后约 3 分钟被杀） | laos 真机上的"录音状态指示"不是可选项，而是**保活前提**。与学术侧 MeMic 结论（可见指示灯显著提升接受度）方向一致 | [Android 后台录音实践](https://blog.csdn.net/qq_42551618/article/details/163703754)（二手） |
| **麦克风抢占** | 同一时刻只有一个 App 持有麦克风；来电/语音助手会打断。Android 无统一中断通知，需 `AudioManager.AudioRecordingCallback` 自检测 | laos 的录音段必须能容错"中断 → 分段"，`rec.start/rec.stop` 的段式设计正好契合 | [Sansan 工程博客](https://buildersbox.corp-sansan.com/entry/2026/05/15/150000) |
| **国产 ROM** | 小米"神隐模式"、华为"耗电保护/启动管理"、各家自启动与电池优化白名单 | 一次性授权不够，需要 **runbook 里的逐机型白名单步骤** | 同上（二手） |
| **Termux / proot（laos 现状）** | ① Android **没有内核 ALSA**，ALSA 不可用且需 root；② 录音要靠 **PulseAudio 的 `module-sles-source`**（OpenSL ES）+ TCP 转发给 proot 里的 Ubuntu；③ `termux-microphone-record` **只能整段启停、拿不到流**；④ 关屏后进程被休眠，需 `termux-wake-lock`（Android 14 上关屏即休眠，实测） | **laos 目前在真机上拿不到 aDSP/LPAI**：proot 里的 Python 只能消费 AP 层音频流，功耗落在 §3 的"Linux 设备空闲 400–1000 mW"档。要拿到 §2 的 mW 级常驻，必须走出 proot，做成原生 App（JNI/HAL/FastRPC） | [termux-app issue #2871](https://github.com/termux/termux-app/issues/2871)（维护者原话）、[PulseAudio + proot 实操](https://mikhail-yudin.ru/notes/termux-proot-distro-two-way-sound/)、[Android 14 关屏休眠实测](https://blog.lilydjwg.me/tag/android) |
| **iOS** | 后台常驻录音基本不允许（中断后不保证恢复），非 laos 目标平台 | 一句话带过：laos 的听觉链路在 iOS 上不成立 | [BlackBox 兼容性说明](https://blackboxrecorder.in/tools/phone-compatibility-checker)（二手） |

---

## 6. 功耗阶梯总表（对照 laos 四段漏斗）

| 漏斗段 | 定制 ASIC | 专用音频 NPU | 手机传感中枢 / aDSP | 通用 MCU/AP（软件） | laos 现状（proot/Termux） |
|---|---|---|---|---|---|
| ① 常驻检测 | 47 nW – 1 µW | **140 µW**（NDP120） | **<1 mA**（Sensing Hub 官方） | 26–50 mW（ESP32-S3） | **400–1000 mW 空闲**（跑 Linux 的机器） |
| ② 触发捕获（编码+落盘） | — | — | 未证实 | **17–70 mW 写 SD**；占空 9% 时整机均值 **≈5 mW** | 同左（AP 上更贵） |
| ③ 蒸馏（ASR/情感） | 8.62 µW（端到端 SLU SoC） | 未证实 | NPU 持续包络 **1–4 W**；实测整机 4.3–5 W | CPU 1.2 W / GPU 0.9 W（MobileNetV3） | 同左（批量、充电时跑） |
| ④ 留存 | 存储成本见 industry 报告：Opus 16 kbps = **7.2 MB/h**；AAC 32 kbps = 14.4 MB/h | | | | laos：Opus + 6 h 即焚 + 配额 FIFO |

---

## 7. 对 laos 的启示（可执行）

1. **把"<5 mW"讲成"占每天的百分之几"**：按 §0 的换算，5 mW = 0.62%/天，100 mW = 12.5%/天。对外文档应直接给这个换算，避免"5 mW 听起来很小但没人有概念"。
2. **①环节的功耗账要拆开写**：麦克风 ≤1 mW（`drivers/drv_mic.py` 现为 16 kHz / 100 ms 块 / PCM16），处理开销才是大头。写成"麦克风 x mW + 检测 y mW"而不是一个笼统的 5 mW。
3. **给常开模式加"占空比档位"**（AudioMoth 证据：9% 占空 → 续航 12.8×）。`mic.always_on_start(ring_seconds=...)` 之外再提供 `duty_on_ms/duty_off_ms`，默认可设为"听 10 s / 歇 50 s"，安静场景省一个数量级。
4. **"只存有声段"是省电措施，不只是隐私措施**：落盘（17–70 mW）比端上判断（≤25 mW）贵，laos 应把这条写进 README 的"为什么 VAD 门控"一节，与 MeMic/TinyChirp 的实证并列。
5. **真机路线必须做一次架构选择**：继续 proot → 常驻成本是数百 mW，`mic.always_on` 这一级在手机上**不成立**（掉电 25%/天以上）；要做成原生 App（JNI/HAL 走 aDSP 或 Sensing Hub）→ 才能进 mW 档。建议 README 明确写"proot 版仅支持 `mic.listen`/`mic.record`（显式触发），`mic.always_on` 需原生 App"。
6. **Android 上"开机自启 + 无声常驻"是禁区**：Android 14 后台创建 mic FGS 直接 SecurityException，且不能从 BOOT_COMPLETED 起。laos 的 `mic.always_on` 语义应设计为"用户在前台显式开启后保持"，并在内核审计里记录开启时点（与 `MIC_SESSION_TOOLS`/`mic_state` 设计一致）。
7. **录音状态指示是保活 + 接受度双必要**：常驻通知（Android 保活）+ 可见指示（MeMic 实证）指向同一件事，`laosctl mic` 的控制面应当在真机上映射到通知栏状态。

---

## 8. 参考来源

**厂商 / 官方**
- Qualcomm Snapdragon 888 AI 博客（Sensing Hub <1 mA、卸载 80% Hexagon 负载）：https://www.qualcomm.com/media/documents/files/snapdragon-888-ai-blog-post-by-jeff-gehlhaar-vp-of-technology-hsin-i-hsu-senior-product-manager.pdf
- Infineon IM68D128B datasheet：https://www.infineon.com/assets/row/public/documents/24/49/infineon-im68d128b-datasheet-en.pdf
- TDK InvenSense AAD 麦克风（20/137 µA）：https://invensense.tdk.com/news-media/blog/high-performance-mems-microphones-enable-user-friendly-ai
- Yole × TDK 访谈（T3902 185 µA、ICS-40310 16 µA）：https://www.yolegroup.com/strategy-insights/mems-microphones-are-still-improving-and-continue-to-enhance-the-human-device-communication-an-interview-with-tdk-invensense/
- Syntiant NDP120 功耗说明与 MLPerf Tiny v0.7 结果：https://www.syntiant.com/?p=7959/ 、https://www.syntiant.com/news/syntiant-ndp120-achieves-outstanding-results-in-latest-mlperf-tiny-v07-benchmark-suite
- Android 前台服务限制（官方）：https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start

**同行评审 / 学术**
- Hill et al., AudioMoth 评估（SD 写入 17–70 mW、睡眠 80 µW、Linux 设备空闲 400–1000 mW）：https://besjournals.onlinelibrary.wiley.com/doi/abs/10.1111/2041-210X.12955
- AudioMoth: A low-cost acoustic device（Table 8 配置与续航）：https://www.sciencedirect.com/science/article/pii/S2468067219300306
- Mobile NPU 上 LLM 解码功耗实测（OnePlus 12，<5 W）：https://arxiv.org/abs/2509.23324

**社区 / 二手（已标注可信度）**
- Termux 麦克风支持讨论（ALSA 不可用、PulseAudio module-sles-source）：https://github.com/termux/termux-app/issues/2871
- Termux + proot 双向音频实操：https://mikhail-yudin.ru/notes/termux-proot-distro-two-way-sound/
- Android 14 关屏即休眠实测：https://blog.lilydjwg.me/tag/android
- Android 14 mic FGS SecurityException 复盘：https://widget-chat.com/blog/flutter-microphone-foreground-service-securityexception-android-14
- Android 后台录音与国产 ROM 设置实践：https://blog.csdn.net/qq_42551618/article/details/163703754
- ESP32-S3 esp-sr 持续监听功耗：https://blog.csdn.net/gitblog_01166/article/details/163533732
- Hexagon HTP 架构与功耗包络：https://jvoltci.github.io/mosaic/edge-ai/npu/hexagon
- Snapdragon 8 Elite Gen 5 双 Micro NPU（官方未给功耗）：https://radargit.com/2026/03/03/qualcomm-snapdragon-8-elite-gen-5-review-and-specs
