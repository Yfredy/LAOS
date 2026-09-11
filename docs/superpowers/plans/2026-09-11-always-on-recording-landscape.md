# 全天候录音（Always-On Recording）业界全景调研 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 系统回答"业界是如何应用全天候录音的"——把商业产品、开源项目、学术论文、端侧硬件/算法栈、隐私合规五条线一次摸清，收敛成一份**带分类学的全景文档**，并直接反向映射到 laos 的听觉链路（四段漏斗），列出"哪些能抄、哪些是坑、哪些是 laos 独有的空档"。

**Architecture:** 先钉死一个共享分类框架（Task 1 定义字段名，后续所有 track 必须按同一 schema 产出，否则无法横向对比），再派 5 条互不重叠的调研线并行跑（商业产品 / 开源项目 / 学术论文 / 硬件与功耗 / 隐私合规），最后由主代理收敛成 Markdown 全景文档 + 一份深色主题 HTML 交付物。分类主轴不是"产品名"，而是**录音数据从麦克风到被消费的完整生命周期**——因为业界所有分歧都发生在这条链的四个环节上（是否常开、留什么、在哪算、给谁用）。

**Tech Stack:** WebSearch + WebFetch（GitHub / arxiv / 产品官网 / 官方文档）；arXiv API 批量取元数据；纯 Python 生成 HTML（无第三方依赖，与 laos 零依赖约束一致）；HTML 深色主题（用户 IDE 为 dark）。

**Spec:** 用户口头需求（"找出全天候录音的文章与开源项目，全方面了解业界是如何应用全天候录音的功能的"）+ 既有资产 `docs/research/2026-09-10-always-on-audio-journal.md`（laos 侧四段漏斗设计）与 `docs/PROJECT_OVERVIEW.md`。

---

## 前置发现（已完成，作为计划的已知前提）

- [x] 已扫描 `docs/research/papers/` 115 篇 PDF，通过 arXiv API 取回全部标题，生成 `docs/research/papers_index.md`（脚本 `scripts/arxiv_index.py`）。
- [x] **结论：115 篇 100% 是 Agent / LLM-OS / Agent 安全方向，音频相关命中为 0**（仅 3 篇因 "conversation/noise/asr" 子串误命中，实际无关）。
  → 因此本调研**不能从现有语料里挖**，必须全新采集；同时也说明"听觉"在 laos 的调研体系里是一块**未被论文覆盖的空白**，正是差异化机会。

## Global Constraints

- 事实准确性优先于覆盖广度：**每一个产品/项目的关键数字（价格、续航、是否开源、是否停售）必须来自官方页面或可信二手源，并在产出里带 URL**；查不到就写 `未证实`，禁止臆造。
- 现状必须标注时效：本调研以 2026-09 为基准，产品状态一律标 `在售 / 停售 / 维护中 / 已归档`，停售的（Humane Ai Pin、Rewind、Rabbit R1 早期形态）**必须记录失败原因**，这比成功案例更有信息量。
- 所有产出用简体中文；专有名词保留英文原名。
- 价格统一折算标注币种（¥ / $），不臆造汇率时并列写原价。
- 不下载、不安装任何代码；纯调研。论文 PDF 是否归档见 Task 7（可选项，需用户确认）。
- 交付物 HTML 用深色主题（背景近 `#0d1117` 系，正文浅色），单文件、无外部 CDN 依赖（图表用纯 CSS/SVG 手写）。

---

## Task 1: 钉死分类框架与统一记录 schema

**Files:**
- Create: `docs/research/always-on-recording/taxonomy.md`
- Create: `docs/research/always-on-recording/tracks/.gitkeep`

**产出内容（后续所有 track 的公共契约，字段名不得改写）：**

1. **主坐标轴 —— 录音数据生命周期四段**（这是全文骨架，来自 laos 已有设计，需验证业界是否普遍如此）：

```
① 常驻检测 (always-on sensing)  麦克风 → 什么条件下算"有事发生"
② 触发捕获 (capture)            留下哪一段音频 / 多大 / 存在哪
③ 蒸馏 (distillation)           转写 / 说话人 / 情感 / 声学事件 / 摘要，在哪算
④ 留存与消费 (retention & use)  原音频留多久、文本怎么用、谁在查
```

2. **产品/项目记录 schema**（每个 track 的表格必须逐列产出）：

| 字段 | 取值 | 说明 |
|---|---|---|
| `name` | 字符串 | 官方名 |
| `kind` | `wearable` \| `earbuds` \| `phone-app` \| `desktop` \| `smart-speaker` \| `devkit` \| `library` \| `model` \| `dataset` \| `framework` \| `service` | 形态 |
| `oss` | `否` \| `是(<license>)` \| `部分` | 是否开源 |
| `always_on` | `常开录音` \| `VAD门控` \| `唤醒词` \| `声学事件` \| `手动触发` \| `不适用` | ①段机制 |
| `retention` | `永久云存` \| `短期云存` \| `本地即焚` \| `仅留文本` \| `仅留事件` \| `不适用` | ④段策略 |
| `processing` | `端侧` \| `云` \| `混合(说明哪段在哪)` | ③段位置 |
| `outputs` | 多选：`转写`/`摘要`/`说话人`/`情感`/`声学事件`/`告警`/`检索记忆`/`实时字幕` | 蒸馏产物 |
| `power` | 字符串 | 续航或功耗数字（查不到写 `未证实`） |
| `price` | 字符串 | 价格与商业模式 |
| `status` | `在售` \| `停售` \| `维护中` \| `已归档` \| `研究原型` | 时效标注 |
| `verdict` | 一句话 | **判断**：成败原因 / 可抄点 / 坑 |
| `url` | URL | 来源 |

3. **论文记录 schema**：`title` / `venue+year` / `机构` / `研究问题` / `方法` / `数据集` / `关键数字` / `对 laos 的关系` / `url`。

4. **三条横向判据**（写在 taxonomy 里，收敛时用它给所有对象打分）：
   - **隐私姿势**：原音频是否出设备？是否可一键关闭？是否有可见指示器？是否可撤回？
   - **功耗姿势**：①段是否下放到 DSP/协处理器？是否有真实毫瓦数字？
   - **闭环姿势**：录下来的东西**谁在什么时候查**？（查不到用途 → 就是"存了一堆没人听的 wav"）

- [ ] **Step 1: 写 taxonomy.md 并自检**——四段漏斗 + 两个 schema + 三条判据齐全，字段名全文一致
- [ ] **Step 2: Commit** — `docs(research): always-on recording taxonomy and record schema`

---

## Task 2: Track A —— 商业产品全景（谁在卖、卖给了谁、谁死了）

**Files:**
- Create: `docs/research/always-on-recording/tracks/A-products.md`

**必查清单（不少于 12 个，逐个填 schema）：**

可穿戴吊坠/胸针：`Limitless Pendant`（原 Rewind）、`Omi`（Based Hardware）、`Friend`（Based Hardware，注意其地铁广告争议）、`Bee`（Bee Home）、`Tab`（前 ChatGPT 硬件团队）、`Aviary`?
眼镜/耳机：`Meta Ray-Ban Display/智能眼镜`（录音+LED 指示）、`Humane Ai Pin`（**已停售，必记失败原因**）、`Rabbit R1`、`Brilliant Frame`?
录音卡片/配件：`Plaud Note / Plaud NotePin`、`科大讯飞录音笔`系列、`Sony / Zoom` 专业录音（对比定位）
桌面/本机：`Microsoft Recall`（截图版，**争议必记**）、`Granola`、`Otter.ai`、`Fathom`、`Circleback`、`Superwhisper`、`MacWhisper`
智能家居：`Amazon Alexa`（"Do Not Disturb"/本地处理演进）、`Google Nest`、`Apple HomePod / Siri`（端侧策略）

**必须回答的问题：**
1. 每个产品到底在漏斗的哪一段做了取舍？（例：Limitless 是"常开 + 云端转写 + 长期留存"；laos 是"VAD 门控 + 本地 ASR + 即焚"）
2. **失败案例复盘**（Humane、Rabbit、Rewind 转型、Recall 翻车、Friend 争议）：死于技术、功耗、隐私还是"想不出用途"？——这直接对应 laos 的边界。
3. 定价与商业模式：硬件一次性 vs 订阅（月费区间），转写分钟数限制。
4. 有没有**本地优先**的商业产品？如果没有，为什么（是技术不成熟还是商业模式不允许）？

**起始搜索词：** `Limitless Pendant privacy local transcription`、`Humane Ai Pin failure postmortem`、`Rewind AI shut down Limitless acquisition`、`always-on AI wearable 2026 comparison`、`Microsoft Recall privacy backlash 2026`、`Plaud Note review privacy`

- [ ] **Step 1: 逐个查证并填表（≥12 条，每条带 URL）**
- [ ] **Step 2: 写"失败案例复盘"小节（≥4 个案例，每个给出死因一句话）**
- [ ] **Step 3: 写"本地优先商业产品是否存在"结论**
- [ ] **Step 4: Commit** — `docs(research): always-on recording commercial products track`

---

## Task 3: Track B —— 开源项目全景（能直接抄的都在这）

**Files:**
- Create: `docs/research/always-on-recording/tracks/B-open-source.md`

**必查清单（分层，每层都要有结论"该选哪个、为什么"）：**

| 层 | 必查项目 |
|---|---|
| 可穿戴整机开源 | `BasedHardware/omi`（固件+App+服务端全开源）、`BasedHardware/OpenGlass`、`Bee` 是否开源、`soniox`? |
| ASR 引擎 | `whisper.cpp`、`faster-whisper`、`whisperX`（对齐）、`insanely-fast-whisper`、`sherpa-onnx`（新一代 Kaldi，流式+唤醒词一体）、`FunASR` / `SenseVoice`（laos 在用的）、`WeNet`、`NVIDIA NeMo`、`Vosk`、Kaldi |
| 流式 / 实时 | `whisper-streaming`（UFAL，SimulWhisper 策略）、`WhisperLiveKit`、`LiveKit`、`kyutai/moshi`（全双工）、`Kyutai STT`（流式） |
| 端侧 / MCU | `Edge Impulse`、`SensiML`、`TensorFlow Lite Micro`（micro_speech）、`microWakeWord`（Home Assistant）、`openWakeWord`、`Willow`（ESP32-S3） |
| VAD | `Silero VAD`、`TEN VAD`（TEN Framework，低延迟）、`WebRTC VAD`、`fsmn-vad`（FunASR）、`pyannote/segmentation` |
| 说话人 | `pyannote.audio 3.x`、`3D-Speaker`、`WeSpeaker`、`Sortformer`（流式 diarization）、`nemo diarization` |
| 情感 / 声学事件 | `SenseVoice`（情感 token）、`emo2vec`、`PANNs` / `AST` / `BEATs` / `CLAP`、`DCASE` 挑战赛基线、`AudioSet` |
| 语音助手框架 | `Rhasspy`、`OpenVoiceOS (OVOS)`、`Home Assistant Wyoming` 协议、`Willow`、`Mycroft`（已停，记教训）、`Almond/Genie`（Stanford） |
| 桌面转写应用 | `Buzz`、`aTrain`、`noScribe`、`Whisper Diarization`、`MacWhisper`（非开源，对比） |

**必须回答的问题：**
1. **"自建一条全天候录音管线"的最小可拼装栈是什么**？给出一套推荐组合（含理由），标明每一环的 license 与中文能力（这对 laos 很关键——SenseVoice vs Whisper 的中文表现）。
2. 哪些项目是**维护中**、哪些**已归档**（star 数与最近提交时间必须查，不查就说"未证实"）。
3. 有没有现成的 **"常驻检测 + 触发捕获 + 即焚"端到端开源实现**？如果没有——这就是 laos 的独特位置，必须明确指出。

**起始搜索词：** `open source always-on audio recording wearable github`、`sherpa-onnx streaming keyword spotting`、`whisper streaming real-time transcription github 2026`、`pyannote speaker diarization open source 2026`、`local voice assistant open source Rhasspy OVOS 2026`

- [ ] **Step 1: 分层查证并填表（≥25 个项目，每条带 URL + star/维护状态）**
- [ ] **Step 2: 产出"最小可拼装栈"推荐组合（一张图 + 为什么选它 + 中文能力对比）**
- [ ] **Step 3: 回答"是否存在端到端开源实现"**
- [ ] **Step 4: Commit** — `docs(research): always-on recording open source track`

---

## Task 4: Track C —— 学术论文线（别人怎么研究"一直听着"这件事）

**Files:**
- Create: `docs/research/always-on-recording/tracks/C-papers.md`

**必查方向（每个方向至少 3 篇，填论文 schema）：**

1. **可穿戴长期录音的真实世界研究**：长时间佩戴音频采集的经验研究（UbiComp/IMWUT 系）、`Ego4D` / `Ego-Exo4D` 的音频与情景记忆任务、lifelogging、egocentric audio。
2. **声学事件与场景理解**：`AudioSet`、`ESC-50`、`FSD50K`、`DCASE` 历年挑战（尤其 domestic / elderly care 相关）、音频事件检测在 MCU 上的落地。
3. **低功耗 always-on**：keyword spotting 综述、TinyML 音频、亚毫瓦级语音前端（ISSCC/JSSC 系）、模拟域特征提取、"always-on audio" 的功耗预算论文。**这一条直接对标 laos 的 ADSP LPAI 路线**。
4. **真实场景说话人日志**：`DIHARD`、`VoxConverse`、`AVA-AVD`、`AliMeeting`、`AISHELL-4`（中文多人会议）、流式 diarization。
5. **语音情感与健康**：语音生物标记物（vocal biomarkers）、抑郁/焦虑的语音检测、`emo2vec`、`SenseVoice` 情感、长期情绪追踪的纵向研究。**对标 laos 的情绪周报**。
6. **隐私与接受度**："always-on sensing" 的 consent 研究、旁观者（bystander）隐私、CHI/CSCW 上关于持续录音社会接受度的实证研究。**对标 laos 的隐私四件套**。

**必须回答的问题：**
1. 学术界对"全天候录音"的**共识与分歧**分别是什么？
2. 有没有论文给出**定量证据**证明"常驻检测 + 触发捕获"比"全量录音"在功耗/存储上差多少量级？（laos 的漏斗需要数字背书）
3. 长期录音研究的**纵向样本规模**与主要发现（人一天说多少话、能提炼出什么）？

**起始搜索词：** `always-on audio wearable study UbiComp`、`egocentric audio Ego4D episodic memory`、`keyword spotting ultra-low power always-on survey`、`speaker diarization in the wild DIHARD AISHELL-4`、`vocal biomarkers depression speech longitudinal`、`always-on sensing bystander privacy CHI consent`

- [ ] **Step 1: 六个方向各查 ≥3 篇并填论文表（带 arXiv/DOI 链接）**
- [ ] **Step 2: 写"学术共识与分歧"小节**
- [ ] **Step 3: 找出并引用定量功耗/存储数字（至少 2 组）**
- [ ] **Step 4: Commit** — `docs(research): always-on recording academic papers track`

---

## Task 5: Track D —— 端侧硬件与功耗（"一直开着"到底多贵）

**Files:**
- Create: `docs/research/always-on-recording/tracks/D-hardware.md`

**必查清单：**

- 麦克风前端：MEMS 麦克风的低功耗/唤醒模式（Vesper 零功耗 wake-on-sound、Knowles、Infineon XENSIV PDM）
- 协处理器 / MCU：Qualcomm **ADSP / LPAI**（laos 在用）、Ambiq Apollo 系列（亚毫瓦）、Syntiant NDP、Alif Ensemble、GreenWaves GAP9、Analog Devices MAX78000、ESP32-S3、nRF 系列、XMOS、QuickLogic
- 操作系统约束：**Android 前台服务录音**（通知、麦克风指示器、后台限制、Android 14+ 限制）、**iOS 后台录音**（基本不允许常驻，Apple 的硬件/软件指示）、Termux 的限制（laos 已知：Termux:API 只支持启停不支持流）
- 功耗数字：给出量级对比表（AP 常醒 vs DSP 常驻 vs 专用 NPU vs MCU），**每个数字带出处**

**必须回答的问题：**
1. 一条"全天开着"的听觉管线，功耗预算的**行业量级**是多少？（mW 级 / 十 mW 级 / 百 mW 级分别对应什么能力）
2. laos 声称的 "ADSP LPAI <5mW" 在行业里处于什么位置？（需要外部数字做锚点）
3. Android/iOS 的**系统级硬约束**到底卡在哪——哪些能力在手机上根本做不到，必须在 App 层或 DSP 层做？

**起始搜索词：** `always-on microphone low power MEMS wake-on-sound`、`Ambiq Apollo sub-milliwatt audio`、`Qualcomm ADSP low power always-on audio LPAI`、`Android foreground service microphone restriction 2026`、`iOS background audio recording limitations`、`Syntiant NDP120 always-on power consumption`

- [ ] **Step 1: 硬件清单查证 + 功耗量级表（带出处）**
- [ ] **Step 2: 平台约束小节（Android / iOS / Termux 三列对照）**
- [ ] **Step 3: 给 laos 的 ADSP 路线定位（外部数字锚点）**
- [ ] **Step 4: Commit** — `docs(research): always-on recording hardware and power track`

---

## Task 6: Track E —— 隐私、合规与社会接受度（这决定了能不能上线）

**Files:**
- Create: `docs/research/always-on-recording/tracks/E-privacy.md`

**必查清单：**

- 法律：欧盟 GDPR（录音属生物/个人数据的处理与告知同意）、美国**两方同意州**（California / Illinois BIPA 等）与单方同意州差异、HIPAA（健康场景）、**中国大陆**（民法典第 1033 条隐私权、《个人信息保护法》对敏感个人信息与单独同意的要求、《治安管理处罚法》相关）——**中国部分必须写准确，这是 laos 的主战场**
- 平台规则：Apple App Store 录音/隐私清单政策、Google Play 麦克风权限与健康应用政策、Meta 智能眼镜的 LED 强制指示
- 产品设计层面的共识做法：可见指示器、一键禁录、本地优先、即焚、审计日志、被录者的可见性与撤回权
- 社会接受度实证：旁观者对被持续录音的态度、职场/会议录音的规范、"consent-by-design" 研究

**必须回答的问题：**
1. 做一个"全天候录音"产品，**最低合规集合**是什么？（一页 checklist）
2. laos 现有的隐私四件套（显式 syscall 触发 / `LAOS_REC=0` 总开关 / 每次录音写审计 / 本地 ASR / 6 小时即焚）对照业界，缺什么？
3. 哪些场景**本质是高风险**应当主动放弃（如秘密录音、看护中的被看护人同意问题）？

**起始搜索词：** `always-on recording consent law two-party consent states 2026`、`GDPR audio recording personal data`、`个人信息保护法 录音 单独同意`、`中国 民法典 1033条 录音`、`Microsoft Recall privacy regulation response`、`wearable recording bystander consent study CHI`

- [ ] **Step 1: 法律与平台规则查证（中国部分单独成节，须准确）**
- [ ] **Step 2: 产出一页"最低合规 checklist"**
- [ ] **Step 3: laos 隐私四件套差距分析表**
- [ ] **Step 4: 明确"主动放弃的场景"清单**
- [ ] **Step 5: Commit** — `docs(research): always-on recording privacy and compliance track`

---

## Task 7: 收敛 —— Markdown 全景文档

**Files:**
- Create: `docs/research/always-on-recording/2026-09-landscape.md`

**文档结构（必须包含，顺序固定）：**

1. **一句话结论**：业界对全天候录音的共识是什么、分歧在哪、laos 的位置在哪。
2. **分类学**：四段漏斗 + 三条横向判据（引用 taxonomy.md，不重复定义）。
3. **全景表一：商业产品**（按 `kind` 分组，schema 全列，≥12 条）
4. **全景表二：开源项目**（按层分组，≥25 条）
5. **全景表三：关键论文**（按六个方向分组，≥18 篇）
6. **硬件与功耗量级表**
7. **隐私合规 checklist + 风险场景黑名单**
8. **失败案例复盘**（Humane / Rabbit / Rewind / Recall / Friend）
9. **对 laos 的反向映射**：
   - 已做对且业界稀缺的（明确列出，作为差异化卖点）
   - 可以抄的（具体到模块：`vad.py` / `drv_rec` / `drv_ear` / `journal.py` / 隐私四件套）
   - 现有缺口（对照业界：**说话人分离**是不是真缺口、情感标签粒度、长时记忆检索、是不是该做声学事件 detection 上 ADSP 作为第二个小模型）
   - 一条建议路线（3 个月内能落地的 3 件事）
10. **参考来源总表**（URL 汇总，去重）

- [ ] **Step 1: 汇总五个 track 文件，交叉校验事实冲突（冲突时以官方源为准并标注）**
- [ ] **Step 2: 按上述 10 节结构撰写**
- [ ] **Step 3: 自查——每条 schema 记录的 `url` 非空、数字均有出处、无 `TBD`/`待补`**
- [ ] **Step 4: Commit** — `docs(research): always-on recording landscape synthesis`

---

## Task 8: 交付 —— 深色主题 HTML 全景文档

**Files:**
- Create: `docs/always-on-recording.html`

**要求：**
- 单文件、零外部依赖（不引 CDN）；图表用内联 SVG / 纯 CSS 手写
- 深色主题（背景 `#0d1117` 系、卡片 `#161b22`、正文 `#e6edf3`、强调色用青绿 `#39d0d8` 与暖橙 `#f0883e`；红色 `#f85149` 表示风险/停售，绿色 `#3fb950` 表示在售/可行）
- 必须包含的可视化：
  1. **四段漏斗图**（SVG）：标注每段"保留什么/丢弃什么"与数据量级变化
  2. **产品定位散点/矩阵**：X 轴 = 端侧 ←→ 云端，Y 轴 = 仅事件 ←→ 全量留存（把 Task 2 的产品摆上去）
  3. **开源栈分层图**：从麦克风到记忆，每层标注候选项目与 license
  4. **功耗量级柱状图**（对数刻度更有说服力）
  5. **风险矩阵**：场景 × 合规风险
- 侧边导航（sticky）+ 顶部锚点目录
- 表格支持横向滚动，不截断内容

- [ ] **Step 1: 生成 HTML（脚本或直接写文件）**
- [ ] **Step 2: 冒烟检查（文件可打开、锚点齐全、无未闭合标签）**
- [ ] **Step 3: `present_files` 打开预览**
- [ ] **Step 4: Commit** — `docs(research): always-on recording landscape HTML deliverable`

---

## Task 9: 收尾 —— 回写项目文档与记忆

**Files:**
- Modify: `README.md`（"重点能力：全天候录音"一节补上业界对标引用与本文链接）
- Modify: `docs/PROJECT_OVERVIEW.md`（如存在听觉链路章节，补链接）
- Modify: `.workbuddy/memory/2026-09-11.md`（追加本次调研记录）

- [ ] **Step 1: 在 README 全天候录音节加入"业界对标"一句话 + 文档链接**
- [ ] **Step 2: 追加当日工作记忆**
- [ ] **Step 3: Commit** — `docs(research): link always-on recording landscape from README`

---

## （可选）Task 10: 关键论文归档

> 需用户确认后再执行。沿用 `docs/research/papers/` 现有惯例（`<arxiv-id>v<n>.pdf`）。
> 目标：把 Track C 中最有价值的 15–25 篇下载到本地，并用 `scripts/arxiv_index.py` 重新生成索引。

- [ ] **Step 1: 确认用户是否需要**
- [ ] **Step 2: 批量下载 + 重建 `papers_index.md`**
- [ ] **Step 3: Commit** — `docs(research): archive always-on recording papers`

---

## 自检结果（写完后逐条核对）

- **覆盖度**：商业产品 ≥12、开源项目 ≥25、论文 ≥18、硬件平台 ≥8、法律辖区 ≥3（含中国大陆）——每个数字在对应 Task 里已写明。
- **Schema 一致性**：Task 1 定义的字段名在 Task 2/3/4/5 中逐字使用，未出现 `retention` vs `keep_policy` 之类的漂移。
- **无占位符**：全文无 `TBD`、`待补`、`类似 Task N`；查不到的事实统一写 `未证实`。
- **Spec 覆盖**：用户要"文章"（Track C + Task 10）、"开源项目"（Track B）、"全方面了解如何应用"（Task 2/5/6 三条应用侧 track）、"参考我找了很多"（前置发现已确认现有语料性质），全部有对应 Task。
- **可独立验收**：每个 Task 产出一个文件并单独 commit，任一 track 失败不影响其他 track 交付。
