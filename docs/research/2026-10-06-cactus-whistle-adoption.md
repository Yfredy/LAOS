# Cactus Whistle 端侧 ASR：复现、实测与接入（小红书笔记采纳）

> 日期：2026-10-06。
>
> **来源诚实声明**：触发源为小红书笔记《16.9MB跑完端侧语音识别 Cactus Compute 于
> 2026 年 1…》（ID `6ac2a1db000000001802abf9`，分享链 xhslink.cn/o/25DokaNLcnp）。
> 笔记正文被登录墙+滑块拦截（直连壳页 / webReader 均无笔记数据），**笔记原文未能
> 逐字取到**；模型定位经由全网检索交叉确认：Cactus Compute **Whistle**，2026-01-30
> 发布。技术事实取自 [官方文档](https://docs.cactuscompute.com)、
> [HuggingFace 仓库](https://huggingface.co/Cactus-Compute/whistle) 与
> [Communeify 技术解析](https://www.communeify.com/tw/blog/cactus-whistle-speech-recognition-16mb-edge-cpu)
> （均经服务器侧 webReader 全文取回）。

## 一、Whistle 是什么

| 项 | 事实 | 来源 |
|---|---|---|
| 发布 | 2026-01-30，Cactus Compute | Communeify |
| 体积 | **16.9 MB**（`whistle.cact` 实测落盘 16,919,407 B；仓库另有 `checkpoints/whistle.safetensors` 源权重） | HF 仓库（已实抓 config.json） |
| 形态 | **`.cact` 自包含容器**（非 GGUF；v1 用 GGUF，v2 起换私有 .cact 格式）+ config.json + processor_config.json | config.json 实读 |
| 架构 | WhistleForSpeechRecognition：GQA 注意力 + Hadamard MLP + 80ms 编码帧 + cactus-quants (group 128) | config.json 实读 |
| 运行 | 纯 CPU 本地推理；引擎 = cactus-compute/cactus（C++，"self-contained, no dependencies"） | 官方文档 + sdist 源码 |
| 输入 | 16 kHz 单声道，单次 ≤30s | config.json `max_audio_seconds: 30` |
| 语言 | **en/de/fr/es/it/nl/pl——无中文**（config.json `languages` 字段实读，7 语确认） | config.json |
| 宣称 | "多数场景胜 Whisper base，体积 1/9"；首 token 11.1ms | The Neuron / postcutoff（**未验证**） |
| 同门 | 与 Needle（8-29MB 自动化基础模型）同一引擎（needle3） | config.json `engine` 字段 |

### 引擎落地现实（2026-10-06 实查，重要）

- **PyPI `cactus-compute` 2.2.2**：wheel 仅 `macosx_14_0_arm64` 与 `manylinux_2_27/28_aarch64`——
  **无 Windows、无 x86_64**（阿里云镜像 simple 索引全清单实读）；
- **Python SDK 本体**（sdist 2.2.0 拆读）：ctypes FFI 加载 `libcactus_engine.dylib/.so`，
  错误信息自述 "the library is built for **arm64 only**"，代码里连 Windows dll 分支都不存在；
- **GitHub Releases**（23 个 release，v2.2.2 最新）：资产基本是源码包，预编译面向移动/边缘
  ARM 平台，无 Windows x64/WASM 资产；
- **PyPI 冒名警告**：PyPI 上叫 `Cactus` 3.3.3 的包是无关的 2013 年静态网站生成器
  （Koen Bok, BSD），勿装；
- 结论：**Windows 本机无法原生跑 cactus 引擎**——这不是网络问题（模型/源码/索引全部
  实抓到了），是平台支持缺失。可行的评测宿主：**Termux（Android aarch64，可直接装
  manylinux_aarch64 wheel）**或任何 ARM Linux/Mac。

## 二、评测方法（可复现）

- **评测集**：Windows SAPI TTS 合成的已知文本（离线、可控）——`var/asr_eval/`：
  en_a/en_b/en_c（Zira，12 句英文）+ zh_set（Huihui，8 句中文），全部 16kHz/16bit/mono、
  ≤30s；参照文本在 `ground_truth.json`。
- **指标**：`laos/wer.py`（本波次新增，纯 stdlib）——英文词错率 WER、中文字错率 CER，
  归一化统一剥标点/全半角/大小写；编辑距离为教科书 Levenshtein，不做修剪美化。
- **基线**：funasr 通道本机直推 SenseVoiceSmall（laos 现役默认 ASR，234M 参数，
  D:/ldf 本地权重）。注：本机 funasr 1.4.0 的 fsmn-vad 注册损坏（`not registered`），
  评测段 ≤30s 无需 VAD，已去掉。
- **harness**：`scripts/eval_whistle.py`（`--backend whistle|funasr|all`），
 SenseVoice 富标签 `<|en|><|NEUTRAL|>…` 剥除后再计分（格式不是内容）。

## 三、基线实测（2026-10-06，本机）

| 后端 | en WER（3 段均值） | zh CER | 稳态 RTF | 备注 |
|---|---|---|---|---|
| funasr SenseVoiceSmall | **0.027**（0 / 0.028 / 0.054） | **0.000** | 0.014–0.018 | 首次调用含模型加载 ~22s；`three thirty`→`330`、`five PM`→`5 PM` 是主要错源 |
| whistle q4_k | （待网络恢复后回填） | — | — | 网络事件见 §五 |

## 四、laos 接入（本波次已落地）

| 件 | 落点 | 状态 |
|---|---|---|
| WER/CER 评测指标 | `laos/wer.py`（normalize/edit_distance/wer/cer，22 测试） | ✅ |
| 评测 harness（集生成+计分+基线） | `scripts/eval_whistle.py` + `var/asr_eval/` | ✅（基线已跑） |
| **ear 驱动第三通道** | `drivers/drv_ear.py`：`LAOS_ASR_CHANNEL=whistle` → 子进程调 cactus CLI（`LAOS_WHISTLE_CMD` 模板，默认 `cactus transcribe Cactus-Compute/whistle --file {wav} --language {lang}`）；`ear.status` 报 `whistle=available`；zh 请求 EINVAL 直接拒绝（防静默垃圾文本）；引擎缺失 ENOENT、CLI 失败 EIO（9 测试全 mock，不依赖引擎存在） | ✅ |
| 引擎 vendored 方案 | 不动 conda（红线）：HF 拉 GGUF → `var/asr_eval/whistle/`；cactus 引擎走 wheel 解压 + PYTHONPATH（待网络） | ⏳ |

**定位裁决**：Whistle **无中文**，不能取代 funasr 作为 laos 默认 ASR；定位为
**多语轻量备选通道**（16.9MB 常驻、纯 CPU、7 语）。laos 的听觉栈分工：
zh 主力=funasr/SenseVoice（GPU/CPU 本机直推），多语轻备=whistle，HTTP=server。

## 五、网络事件记录（诚实档）

评测当日本机网络间歇中断：DNS 被 TUN 劫持为 fake-IP（198.18.x），huggingface.co /
pypi.org / api.github.com 反复 SSL 断连；**阿里云 PyPI 镜像全程稳定**（模型与 sdist 均经
它或 HF 恢复窗口取得）。GitHub API 403 限流（TUN 出口 IP 共享配额）。全部情报链经
服务器侧 webReader/WebSearch 保持不断。`whistle.cact` + config 已落
`var/asr_eval/whistle/`，cactus sdist 源码在 C:/tmp（未入库）。

## 六、待办（评测宿主落地后）

1. **首选 Termux 路径**（laos 原生架构：手机=设备端、PC=治理端，与 QNN
   InferenceServer 同构）：插上手机开 USB 调试 → adb push 评测集与 whistle.cact →
   Termux `pip install cactus-compute`（aarch64 wheel 现成）→ 手机上跑转写 →
   回传 PC 用 laos/wer 计分 → 回填 §三；
2. 备选：任何 ARM Linux / Mac 宿主跑同一评测；
3. 数字回填后裁决是否给 journal 管线加"英文段走 whistle"分流（confgate 同款思路）；
4. 远期：cactus-android（Maven `com.cactuscompute:cactus-android`）做常驻服务，
   adb forward 暴露给 laos `ear.transcribe` 的 whistle 通道（LAOS_WHISTLE_CMD
   模板已支持指向任意引擎命令）。
