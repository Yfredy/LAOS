# AgenticASR 复现与运用（小红书笔记：基于智能体方法优化现实场景下的语音识别）

> 日期：2026-10-06。
>
> **来源诚实声明**：触发源为小红书笔记《AgenticASR：基于智能体方法优化现实场景下…》
> （ID `6ac3015f0000000018005d9f`，分享链 xhslink.cn/o/1I3tCwxbZxe）。笔记正文被登录墙
> 拦截（壳页无数据），按既有预案全网定位真身并从一手来源学习：
> **arXiv 2607.28175**《AgenticASR: Refining Speech Recognition in Real-World
> Scenarios via an Agentic Approach》（全文经 ar5iv/arXiv 摘要页服务器侧取回）；
> 官方 GitHub（论文 demo 页指向，克隆因 GitHub 间歇断连暂未完成，后台重试中）。

## 一、论文核心（一手来源摘录）

- **任务重构 AgenticSR**：ASR 的智能体中心重构——输入含填充词/口吃/自我纠正/
  代码切换/转写错误的真实口语，输出"说话者最终意图"的干净书面文本（给人也给
  Agent 用）。ASR 是智能体应用的输入接口，脏转写直接劣化下游任务。
- **系统 AgenticASR**：解耦的 **ASR → Refiner** 两段（在线友好）；Refiner =
  **Qwen3-4B-Instruct + LoRA（rank 16 / α 32）** 微调。
- **训练对构造**（LLM-assisted pipeline）：LLM 分饰**学生/考官**多轮对话，把
  原始 ASR 输出精炼成任务特定训练对。
- **基准 AASR-Bench**：真实语音数据集策展（英文 SA-EN 558 句 / 中文 SA-ZH 480 句）。
- **主结果**：英文 Whisper large-v3 **WER 43.5→19.7**；中文 FunASR Paraformer
  **CER 21.3→17.9**。**Qwen3-560B 零样本 25.8（英文）——4B 微调打赢 560B 提示词**。
- **消融**：2B Refiner 22.4 vs 7B 19.7；prompt-only（不微调）28.9；去掉自我纠正
  增强对中文伤害最大（-1.8 CER）。

## 二、laos 复现（规则版 AgenticSR，纯 stdlib）

论文 Refiner 是学习出来的；laos 核心层能给出的是**确定性子集**——
[laos/refiner.py](../../laos/refiner.py)：

1. 填充词去除（呃/嗯/啊/唉/哦 与 uh/um/er/ah/hmm；"那个/这个"是指示词不删）；
2. 口吃折叠（中文同字 ≥3 折 1，双叠合法保留；这/那双叠例外必折；英文同词 ≥2 折 1）；
3. 自我纠正解析（"不对/不是"须后随停顿或引导字防谓语误触发；按标记分段**取末段**
   ——"最终意图=最后一次说出口的内容"）；
4. 清理重复标点/空白。幂等。

**已知局限（即论文卖点）**：子句级替换型纠正（"发邮件给张三，不对，我是说李四"）
需要语义对齐，规则版只能给末段——学习型 Refiner（genie 端侧 LLM 通道）的存在理由。

## 三、实测（2026-10-06，本机）

### 官方 AASR-Bench 全集（权威数字，var/asr_eval/aasr_bench/）

ModelScope 镜像拉取官方 benchmark.jsonl（**917 例**：zh 510 / en 407，11 场景，
oral/clean 成对）。laos.refiner（逗号域版）对 clean 计错（zh=CER / en=WER）：

| 维度 | oral（不精炼） | refined | Δ |
|---|---|---|---|
| **微平均（917 例）** | 0.4571 | **0.3875** | **-0.0696（-15.2%）** |

场景分解（Δ，负=改善）：zh/explanation **-0.649**、zh/voice_search -0.180、
zh/navigation -0.128、zh/meeting -0.115、zh/dictation_memo -0.074、
zh/vibe_coding -0.077、zh/daily_chat -0.058、en/customer_service -0.059、
en/voice_search -0.030、en/dictation_memo -0.023、en/tech -0.012、
en/meeting -0.008、en/academic -0.005、双 passthrough 0.000（干净语音零误伤）。
仅 en/daily_chat +0.091 与 zh/academic +0.014 为正——后者即"整句谓语被替换"
型纠正（旗舰例：'…换成 Cross Entropy，啊不对，应该是 Focal Loss'），规则版
逗号域仍不可解，**用 laos 自己的数据复证了论文"学习型 Refiner 必要性"的论点**。

> 注：官方基准的 clean 还含数字归一（"百分之二十二点五"→"22.5%"）与书面化
> 改写，这些规则版不做——上面的 -15.2% 是纯"去不流利"维度的收益。

### 文字级自构集（var/asr_eval/refiner_cases.json，13 例：zh 8 + en 5）

| 类别 | n | raw 错误率 | refined | Δ |
|---|---|---|---|---|
| filler（纯填充词） | 3 | 0.264 | **0.000** | -0.264 |
| filler_partial（"那个"指示词，规则版不删） | 1 | 0.200 | 0.000* | -0.200 |
| stutter（口吃） | 3 | 0.356 | **0.000** | -0.356 |
| restate（完整重述型纠正） | 4 | 2.562 | **0.000** | -2.562 |
| replace（子句级替换，已知局限） | 2 | 0.883 | 0.733 | -0.150 |
| **TOTAL** | 13 | 1.083 | **0.113** | **-0.970（-90%）** |

*filler_partial 单例的 intended 取"那个…"口径；若按删除口径则规则版输——诚实备注。

### 端到端（复刻论文 ASR→Refiner 主实验，SAPI TTS 口吃语音 ×6）

链路：合成口吃/纠正语音 → funasr SenseVoice 转写 → laos.refiner → CER 对 intended：

| 例 | ASR 转写 | refined | CER 前→后 |
|---|---|---|---|
| dz1 | 呃今天天气怎么样 | 今天天气怎么样 | 0.143→0 |
| dz2 | 文帮我打开爱厨房的灯 | （不变） | 0.250→0.250 |
| dz3 | 我我我想要喝水 | 我想要喝水 | 0.400→0 |
| dz4 | 明天九点不对我是说十点开会 | 十点开会 | 2.250→0 |
| dz5 | 我叫小王**二**不对是老王 | 是老王 | 2.333→0 |
| dz6 | 订大桌不对我是说小桌 | 小桌 | 4.000→0 |
| **MEAN** | | | **1.563→0.042（-97%）** |

两个结构性发现：
- **重述型纠错天然容错 ASR 噪声**：dz5 的 ASR 把"哦"误听成"二"，但错误落在被丢弃的
  纠正前段里，取末段语义顺带清掉了它；
- dz2 平局是**同音字级 ASR 错误**（"嗯"→"文"），规则版无法修——正是论文留给学习型
  Refiner 的 transcription errors 类。

## 四、laos 运用（本波次已落地）

| 件 | 落点 | 状态 |
|---|---|---|
| 规则版 Refiner | `laos/refiner.py`（19 测试） | ✅ |
| 驱动工具 `ear.refine` | `drivers/drv_ear.py`：ASR 后精炼独立 syscall 工具 | ✅ |
| `ear.transcribe(refine=True)` | 同上：转写即精炼一步到位 | ✅ |
| 评测资产 | `var/asr_eval/refiner_cases.json` + `disfluent_e2e.json` + 结果 JSON | ✅ |
| 学习型 Refiner 通道 | genie 端侧 LLM prompt 版（复用官方 prompts.json），远期 onnx-int4 | ◐ 远期 |
| 官方代码/AASR-Bench | SSH 克隆到手（§六核对）+ ModelScope 全集 917 例实测（§三权威数字） | ✅ |

**架构对照**：论文的"4B 微调打赢 560B 零样本"= laos 一直的立场——端侧小模型 +
治理与管道编排胜过裸大模型；Refiner 作为 ASR 之后的独立负载，与 laos "Agent 是
新负载，与进程同类"完全同构。journal/diary 管线（ASR→memory）是下一个接 refiner
的天然客户（转写入库前先精炼，后续检索质量受益）。

## 五、与既有波次的合流

- whistle 波次（同日）：drv_ear 三通道 + wer.py——本波次的 CER/WER 指标直接复用；
- 本波次新增 `laos/refiner.py`（核心层第 3 个 AgenticSR 件，与 confgate/vadmetrics
  同族：小而纯、零依赖、可独立进驱动子进程）。

## 六、官方仓库核对（2026-10-06 SSH 克隆到手，订正与补充）

- **仓库**：github.com/AnXMuy/AgenticASR（研究代码 + 可复现核心；另有产品化桌面应用
  VibeXASR、项目页 anxmuy.github.io）；
- **AASR-Bench 规模订正**：**917 样本 + 6,637 条原子评分规则**（Content/Format/
  Filter/Rephrase 四维；本档前述"SA-EN 558/SA-ZH 480"是论文正文口径，仓库 README
  以 917 为准——已用 917 例全集实测）；
- **训练配方**（refiner.yaml 实读）：LLaMA-Factory，**全参微调**（非 LoRA——论文
  提及的 LoRA 是另一配置）、template=cpm4、lr 2e-5、5 epochs、packing、bf16；
- **Refiner 发布物**：HF Andrew0425/AgenticASR-Refiner + ModelScope MuyuanJ/
  AgenticASR-Refiner，含社区 **mlx-int4 / onnx-int4 变体**——onnx-int4 与本机
  onnxruntime 1.27 兼容，学习型通道有现成宿主；
- **在线模式**："continually replace a bounded active span as speech arrives"
  ——有界活动窗的流式精炼（Context Spanning 同族），远期进 laos 流式管道；
- pipeline/configs/prompts*.json：官方 prompt 资产，genie 学习型通道的直接素材。

## 七、待办

1. genie 通道加 `refine` prompt 模式（复用官方 prompts.json），与规则版同
   AASR-Bench 对比，复刻论文 prompt-only vs fine-tuned 消融；
2. onnx-int4 Refiner 经 onnxruntime 落地评估（模型 ~4B int4 ≈ 2-3GB，需评估
   本机内存/时延）；
3. journal.py 转写入库前接 refine=True（一次 syscall 级改动）。
