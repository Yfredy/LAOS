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
| 体积 | **16.9 MB**（q4_k GGUF；另有 q8 约 20.1 MB） | 官方/HF |
| 形态 | GGUF 权重 + config.json + processor_config.json | HF 仓库 |
| 运行 | 纯 CPU 本地推理，cactus 引擎（`cactus transcribe`） | 官方文档 |
| 输入 | 16 kHz 单声道，单次 ≤30s | HF model card |
| 语言 | 7 种（en/de/fr/es/it/nl 等；**不含中文**——精确清单待引擎落地后核验） | 多源 |
| 宣称 | "多数场景胜 Whisper base，体积 1/9"；首 token 11.1ms | The Neuron / postcutoff（**未验证**） |
| 同门 | 与 Needle（8-29MB 自动化基础模型）同一引擎 | 官方文档 |

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

评测当日本机直连全线中断：DNS 被 TUN 劫持为 fake-IP（198.18.x），huggingface.co /
hf-mirror.com / pypi.org / api.github.com TLS 全部 EOF；服务器侧工具（webReader/
WebSearch）不受影响，情报链全程未断。后台轮询（45s 间隔）负责网络恢复后自动拉取
`Cactus-Compute/whistle` 全部根文件（GGUF + config）；引擎到位即回填 §三 数字。

## 六、待办（引擎落地后）

1. `scripts/eval_whistle.py --backend all` 跑全对照，回填 §三；
2. 核验 7 语言精确清单（`cactus transcribe --help` 或文档）；
3. 与 QNN 端侧 SER 对照记功耗口径（Whistle CPU-only vs ADSP island）；
4. 视结果决定是否给 journal 管线加"英文段走 whistle"的分流（confgate 同款思路）。
