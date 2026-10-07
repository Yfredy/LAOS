# 上线前评审与埋点设计（review-instrumentation）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出上线前两份评审文档（需求评审 + 技术评审）与一份埋点设计文档（含"用户上线后各类问题的诊断矩阵"），并吸收 voicenpu 上游 metrics 字段口径进 laos 事件设计——三个新文档域（docs/review/ 与 docs/design/），发版 v0.20.0。

**Architecture:** 三文档递进：需求评审先定义"上线"与用户场景（埋点的需求源头）→ 技术评审盘点现状强项/风险/债务（埋点要覆盖的故障面）→ 埋点设计给出事件分类学+schema+发射点+隐私红线约束+问题→埋点诊断矩阵。文档间交叉引用，事实全部取自仓库既有实测（禁止新编数字）。

**Tech Stack:** 纯 markdown 文档；无代码改动（埋点模块 laos/telemetry.py 是下一波次的自然落地，本波只做设计）。

**Spec:** 用户 2026-10-07 指令"1、写出详细的技术评审和需求评审文档。2、写出埋点设计文档，用户上线之后需要应对不同的问题"；上游 pending 项 = docs/research/2026-10-06-voicenpu-adoption.md §六#4（上游 dialog_metrics.jsonl 字段口径吸收进 laos 审计事件设计）。

## Global Constraints

- **隐私红线（埋点设计的最高约束）**：录音只由显式 syscall 触发；LAOS_REC=0 全局禁录；ASR 全本地；既有审计事件 event:"mic"。**埋点默认不采集音频内容与转写文本明文**——内容类只允许长度/哈希/计数/时长等脱敏字段，且须挂在既有审计流之下（埋点≠新开后门）。
- **零依赖承诺**：本波纯文档；设计中为 telemetry 预留的实现形态必须是纯 stdlib（JSONL 落盘）。
- **来源诚实**：文档中所有性能数字必须引用仓库既有实测（下文"事实基线"节为唯一允许来源），不得引入外部宣称值；无实测的维度写"未实测"。
- **定位叙事红线**：基座是 Linux 内核，Agent 是新负载（与进程同类），laos 是内核治理在用户态的延伸——评审文档的叙述不得主客反转。
- 发版：新文档域 → v0.20.0（release.py --apply 全流程）。

**事实基线（文档引用的唯一数字来源，实测口径）**：
- ASR 三通道：funasr/SenseVoice（en WER 2.7% / zh CER 0.0%，zh 主力）；whistle via needle3（en WER 10.8%，ttft 651ms，~300 tok/s，模型 16.9MB+引擎 1.56MB，多语轻备）；server（HTTP）
- Refiner：AASR-Bench 917 例错误率 0.4571→0.3875（**-15.2%**）；端到端（TTS 口吃语音→funasr→refiner）CER 1.563→0.042；已知局限=子句级替换型
- 对话控制面（v0.17.0 语义复现）：WakeGate 四态（follow-up 12s/会话 120s/6 轮）；generation 版本化打断；投机 prefill 窗 500ms+resume≥96ms×16+commit 延长 200ms；TtsRouter 降级（句中不换声线）；MicrophoneGate guard 400ms
- voicenpu 上游（RK3576 实测，对照用）：端到端首音 1.44s、常驻 1951MB、ASR 端点→终稿 ~88ms、metrics 22 字段口径（dialog_id/route/retrieval_ms/first_text_ms/first_audio_ms/prefill_ms/generate_ms/tokens/memory_mb/total_ms/speculative_cancelled/merged_segments/speculative_tokens_wasted/asr 侧 vad_ms·zipformer_ms·endpoint_to_final_ms 等）
- 判断层：edgejev 端侧实测 median 157.5ms（README 宣称 15.6ms 被否证）
- 测试：主库 691（实跑），页脚总数 1041（含隔离区 279 + 复现区 71）
- 上游故障自愈语义（学习来源）：USB ENODEV 重开、AEC 收敛门槛（100 渲染帧+50 稳定帧）、队列 overrun 自愈、TTS 在线降级

---

### Task 1: 需求评审文档

**Files:**
- Create: `docs/review/2026-10-07-requirements-review.md`

**Interfaces:**
- Produces: 文档 §6"上线后问题域清单"（12+ 类问题）是 Task 3 诊断矩阵的需求源头（Task 3 逐条映射埋点字段）。

- [ ] **Step 1: 读底料**（实现者必读）：README.md（版本与发布节+能力总览）、docs/research/2026-10-06-voicenpu-adoption.md（§二 上游系统全景+§六 后续建议）、事实基线（本计划）。
- [ ] **Step 2: 写文档**，章节骨架（每节内容要求）：
  1. §评审范围与"上线"定义——laos 的三类目标形态（端侧常开录音研究平台 / Agent 治理语义层 / 对话控制面组件库），明确本评审以"开发者自部署上线"为第一场景（laos 无对外 SaaS 承诺）
  2. §用户画像与核心场景——场景表：常开录音日记、语音问答（唤醒→识别→知识库/LLM→TTS）、Agent 治理审计、语料研究；每场景一行"用户动作→系统行为→当前完成度（✅完整/◐部分/○缺）"
  3. §功能需求清单（MoSCoW）——Must：三通道 ASR/唤醒会话/打断/审计/禁录开关；Should：KWS 实测落地（◐，模型与词表已拿到）/TTS 能力面（○，laos 尚无）/知识库检索；Could：AEC 全双工/NPU SER 真机；Won't：云端默认上传/多租户
  4. §非功能需求——延迟预算表（对照 voicenpu 1.44s 首音/88ms 端点终稿，laos 各段未实测处如实标"未实测"）、功耗预算（引用 always-on-recording 调研的功耗阶梯）、隐私合规（红线逐条）
  5. §上线门槛（Go/No-Go 清单）——每条一行判定：现状态+差距
  6. §上线后问题域清单（12+ 条，喂给 Task 3）——唤醒不灵/误唤醒、ASR 误识别劣化、端到端延迟劣化、打断失效（过期代播放）、会话异常（超时/轮数）、TTS 降级频繁、模型加载失败、音频设备断连、内存增长、崩溃后恢复、审计缺失、LAOS_REC=0 旁路
  7. §需求评审结论——TOP5 风险+TOP3 放大器（埋点=放大器之一）
- [ ] **Step 3: 自查**——所有数字可溯源到事实基线/引用文档；无 SaaS 化越权承诺
- [ ] **Step 4: Commit** `docs(review): requirements review — scenarios, MoSCoW, go/no-go, post-launch problem taxonomy`

### Task 2: 技术评审文档

**Files:**
- Create: `docs/review/2026-10-07-technical-review.md`

**Interfaces:**
- Consumes: Task 1 §2 场景完成度（交叉一致）。
- Produces: §风险与债务表是 Task 3 埋点覆盖面的技术源头。

- [ ] **Step 1: 读底料**：laos/ 目录模块清单（`ls laos/`+各模块 docstring 首行）、tests/ 计数（691 实跑）、事实基线、Task 1 成品。
- [ ] **Step 2: 写文档**，章节骨架：
  1. §架构盘点（五层表：内核语义层/强制层/听觉栈/对话控制面/研究资产层——每层：模块清单+一句话职责+完成度）
  2. §接口契约审计——三通道 ASR 的 env 契约（LAOS_ASR_CHANNEL/LAOS_WHISTLE_BIN 等）、dialogsched 可注入时钟/GenerationGate 回调、audit 事件流；每个契约一行"稳定性（稳/演化中/未冻结）"
  3. §强项（带证据）——控制面语义复现的测试密度（573→691 曲线）、refiner -15.2%、三通道 footprint 梯度、语料资产规模
  4. §风险与债务表（每条：风险/证据/影响面/缓解建议）——至少覆盖：turnpolicy 与 GenerationGate 未组合、KWS 未实测（词表已拿到）、TTS 能力面缺失、AEC 缺失致半双工、refiner 子句级替换局限、QNN 真机链路未复测、Crossref/DBLP 外源依赖、三棵树同步的漂移风险
  5. §测试覆盖评估——按模块的测试数表+盲区清单（drivers 真机链路、并发路径、长时运行）
  6. §性能数据汇总——事实基线数字表+未实测维度清单
  7. §技术决策记录（ADR 式 5 条：为什么零依赖/为什么规则版 refiner 先行/为什么语义复现不拷贝/为什么三通道/为什么 KWS 延后）
  8. §评审结论——上线就绪度分维度打分（对话控制面/听觉栈/治理层/可观测性——可观测性应最低，引出 Task 3）
- [ ] **Step 3: 自查**——风险表每条有仓库内证据指针（文件/报告路径）；无凭空断言
- [ ] **Step 4: Commit** `docs(review): technical review — five-layer inventory, contract audit, risk/debt table, ADRs`

### Task 3: 埋点设计文档

**Files:**
- Create: `docs/design/2026-10-07-instrumentation-design.md`

**Interfaces:**
- Consumes: Task 1 §6 问题域清单（逐条映射）、Task 2 §4 风险表（覆盖面）、voicenpu metrics 22 字段口径（吸收进对话事件）。
- Produces: 事件 schema 与发射点清单 = 下一波 laos/telemetry.py 的实现规格。

- [ ] **Step 1: 读底料**：Task 1/2 成品、voicenpu 报告 §二 metrics 字段清单、laos/audit 现有事件形态（读 laos 源码审计模块）。
- [ ] **Step 2: 写文档**，章节骨架：
  1. §设计原则（五条）——本地优先（默认 JSONL 落盘无云端）、计数优先于内容（隐私红线落法：内容字段只允许 len/sha256 前 8 位/时长/语言码）、挂审计流（埋点事件复用 audit 通道与 event:"mic" 联动语义，不新开后门）、节流必设（同类事件 5s 节流，防风暴——学上游日志节流）、LAOS_REC=0 联动（禁录时音频内容类埋点同步静默）
  2. §事件分类学（六类）——L 生命周期（sys.init/driver.load/crash.recover）、A 音频链路（mic.frame_overrun/device.reopen[学上游 ENODEV]/vad.endpoint）、S 语音服务（asr.result[通道/WER 侧车字段/cer 本地无法算则记 duration+lang]/refine.delta）、D 对话调度（dialog.turn[吸收 voicenpu 22 字段口径：route/first_audio_ms/interrupted/speculative_cancelled/merged_segments…]/wake.state_change/barge_in/mic.guard）、P 性能（rtf/memory/rss 采样）、F 降级与故障（tts.fallback/asr.channel_fail/model.load_fail）
  3. §事件 schema——统一 JSONL 行：`{"ts": <monotonic_ms>, "event": "<class.name>", "level": "info|warn|error", "module": "<laos 模块>", "session": "<会话 id>", "fields": {...}}`；每类事件一张字段表（字段名/类型/脱敏要求/来源函数）
  4. §发射点清单——映射表：事件 ↔ laos 模块函数（如 wake.state_change ↔ laos/wakegate.py state 变更处、dialog.turn ↔ dialogsched commit/cancel 路径、device.reopen ↔ 未来音频前端自愈位）；未落地模块标"预留（对应风险表 #N）"
  5. §问题→埋点诊断矩阵（核心交付）——Task 1 §6 的 12+ 问题逐条：症状→看哪个事件哪些字段→判定逻辑（如"打断失效"→dialog.turn.interrupted==false 且 generation 未递增→调度旁路；"ASR 劣化"→asr.result.duration 上升/lang 误判率[若有 ref 比对]→通道切换审查）
  6. §保留与采样——滚动保留（默认 7 天/容量上限）、性能事件采样率、崩溃时 flush 语义
  7. §与 voicenpu 口径对照表——22 字段哪些直接采纳/哪些改名/哪些不适用（无 NPU 场景）
- [ ] **Step 3: 自查**——诊断矩阵 12+ 问题全覆盖；每个字段表标脱敏级别；无一处违反隐私红线
- [ ] **Step 4: Commit** `docs(design): instrumentation design — event taxonomy, schema, emission map, diagnosis matrix`

### Task 4: 交叉一致性 + 登记

**Files:**
- Modify: `docs/research/INDEX.md`（主报告 +3 行——docs/review/ 与 docs/design/ 若不在 INDEX 体系则加"评审与设计"新节；头部计数机械对齐，**只按机械数改，避免重蹈 28 vs 33 错账**）
- Modify: `README.md`（一句话：上线前评审两份+埋点设计一份，引相对路径；不碰锚点）

- [ ] **Step 1: 三文档交叉核对**——T1 §6 问题数 == T3 矩阵行数；T2 §4 风险表条目在 T3 发射点/预留位有呼应；voicenpu 22 字段对照表与事实基线一致
- [ ] **Step 2: INDEX/README 登记**（机械计数：先数行再写数字）
- [ ] **Step 3: 测试不受影响**（-m unittest discover -s tests -q 仍 691 OK skipped=5）
- [ ] **Step 4: Commit** `docs: cross-consistency check + index/readme registration for review & design docs`

### Task 5: 发版 v0.20.0

- [ ] **Step 1**: 全套测试 691 OK；`python scripts/release.py --apply`（三树+14 文档同步）→ CHANGELOG v0.20.0 段（一句话：上线前评审×2+埋点设计=新文档域 docs/review+docs/design；关键数：12+ 问题诊断矩阵/六类事件/voicenpu 22 字段对照）→ commit → tag → push + Release 页（body 走临时 json 文件，TUN 断窗 var/ 脚本后台重试）
- [ ] **Step 2**: 交付说明（三文档路径+矩阵要点+下一步=laos/telemetry.py 实现波次）

## Self-Review

- 用户指令覆盖：技术评审 ✅（T2）需求评审 ✅（T1）埋点设计+上线后问题 ✅（T3 §5 矩阵，源头=T1 §6）。
- 占位符：文档型任务给章节骨架+内容要求+事实基线（数字唯一来源），评审按"章节齐全+数字可溯源+矩阵全覆盖"验收。✅
- 冲突检查：T4 INDEX 计数明确"机械数优先"（吸取 T5 错账教训）；三文档接口（§6→矩阵、§4→发射点、22 字段→对照表）闭环；隐私红线为 T3 最高约束且自查条目覆盖。✅
- 纯文档波次发版先例：v0.14.0（新文档域=MINOR）。✅
