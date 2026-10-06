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

**打通方式（终局）**：whistle 的指定引擎是 **needle3**（config.json `engine` 字段）——
HF `Cactus-Compute/needle3` 仓库分发**全平台引擎二进制**（windows-x86_64/needle.exe
1.56MB 单文件、linux-arm64/android-arm64/ios/wasm/win-arm64 全有，另有 cactus_needle
Python wheel 含 win_amd64）。命令：`needle --model whistle.cact --audio X.wav
--audio-language en`，输出单行 JSON（text/language/ttft_ms/decode_tps）。
**Windows 本机原生可跑**——前述"Windows 无路"仅指 cactus-compute 通用引擎（arm-only
wheel + 转换器缺 whistle 适配，官方 download 路径实测 "No prebuilt bundle found +
Unknown model type whistle" 双确认）；needle3 路线绕开全部死结。

| 后端 | en WER（3 段均值） | zh CER | 首字延迟 | 解码吞吐 | 常驻体积 |
|---|---|---|---|---|---|
| funasr SenseVoiceSmall（234M） | **0.027**（0/0.028/0.054） | **0.000** | （GPU/CPU 本机直推） | 稳态 RTF 0.014-0.018 | ~900MB 模型 |
| **whistle（16.9MB）via needle.exe** | **0.108**（0.105/0.139/0.081） | **不可用**¹ | ttft 651ms 均值 | ~300 tok/s | **16.9MB 模型 + 1.56MB 引擎** |

¹ 中文音频实测被当英语幻觉输出（音译乱串）；强制 zh 则拒识——7 语言（en/de/fr/
es/it/nl/pl）无中文，config 声明与行为一致。

**质量观察**：SAPI 清晰语音下仍有系统性分词裂痕（"today"→"to day"、
"tomorrow"→"to morrow"，tokenizer 后处理缺陷）；英式拼写（summarise）、数字化
（three thirty→330）造成计分口径差。真实嘈杂语音预计更差。

**裁决**：laos 听觉栈三通道分工定局——**zh 主力 = funasr/SenseVoice（WER 2.7%/CER 0%
碾压）；whistle = 多语轻量备选**（体积 1/50、零依赖单文件、全平台含 WASM/Android，
英文 10.8% 够用档）；server = HTTP 外部服务。whistle 的真正价值面是**极小足迹部署**
（手表/MCU/浏览器），不是精度。

## 四、laos 接入（本波次已落地）

| 件 | 落点 | 状态 |
|---|---|---|
| WER/CER 评测指标 | `laos/wer.py`（normalize/edit_distance/wer/cer，22 测试） | ✅ |
| 评测 harness（集生成+计分+基线） | `scripts/eval_whistle.py` + `var/asr_eval/` | ✅ |
| **ear 驱动第三通道（needle 形态）** | `drivers/drv_ear.py`：`LAOS_ASR_CHANNEL=whistle` → 子进程 needle 引擎（`LAOS_WHISTLE_BIN`/`LAOS_WHISTLE_MODEL` env，默认 var/asr_eval/needle/）；输出解析 JSON 取 text/ttft_ms/decode_tps；zh EINVAL 拒绝；引擎缺失 ENOENT、CLI 失败 EIO；纯文本回退（10 测试 + 真机全链冒烟 latency 597ms） | ✅ |
| 引擎与模型入库位 | `var/asr_eval/needle/needle.exe`（1.56MB）+ `whistle.cact`（16.9MB）——gitignore 内运行期资产，重取路径在 §五 | ✅ |

**定位裁决（终局）**：Whistle **无中文**，不能取代 funasr 作为 laos 默认 ASR；定位为
**多语轻量备选通道**（16.9MB 常驻、纯 CPU、7 语、全平台单文件引擎含 WASM/Android/
Windows）。laos 的听觉栈分工：zh 主力=funasr/SenseVoice（GPU/CPU 本机直推），多语
轻备=whistle（needle 引擎），HTTP=server。

## 五、网络事件记录（诚实档）

评测当日本机网络间歇中断：DNS 被 TUN 劫持为 fake-IP（198.18.x），huggingface.co /
pypi.org / api.github.com 反复 SSL 断连；**阿里云 PyPI 镜像全程稳定**（模型与 sdist 均经
它或 HF 恢复窗口取得）。GitHub API 403 限流（TUN 出口 IP 共享配额）。全部情报链经
服务器侧 webReader/WebSearch 保持不断。`whistle.cact` + config 已落
`var/asr_eval/whistle/`，cactus sdist 源码在 C:/tmp（未入库）。

### 虚拟端侧评测环境（2026-10-06 下午，用户提议虚拟手机思路后建成）

- **宿主**：WSL2 Ubuntu-22.04（x86_64）+ qemu-user-static 6.2 + ubuntu-base 22.04.5
  arm64 rootfs chroot（/mnt/armroot）——与安卓手机同指令集（aarch64）的"虚拟手机"，
  官方 manylinux_aarch64 wheel 直接原生安装；
- **已就位**：cactus-compute 2.2.2（arm64 wheel，`libcactus_engine.so` import OK）、
  torch 2.14.1+cu130、transformers 5.18.0（tuna 源）、评测集与 ground_truth；
- **引擎事实（实测+源码双重确认）**：裸 `whistle.cact` 不是可运行 bundle——引擎要
  `config.txt + tokenizer_config.txt + components/manifest.json`（或 runtime_plan.json），
  这些由 `cactus convert --model <本地路径> --bits 4` 从 HF 源权重
  （checkpoints/whistle.safetensors）离线转换生成；convert CLI 收本地路径
  （`local_files_only` 分支），转换全程可离线；
- **剩余卡点**：whistle.safetensors 源权重在 HF（无国内镜像，ModelScope/Gitee 均无），
  后台轮询等窗口拉取后即可全链离线完成（脚本已备好：whistle_full_chain.sh）。

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
