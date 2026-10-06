# Changelog（laos）

所有重要变更记录于此。本项目遵循 [Semantic Versioning](https://semver.org/spec/v2.0.0.html) 与 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)。
0.x 阶段：minor 即功能波次，breaking 不升 major。

## [Unreleased]

## [v0.16.0] - 2026-10-06

### Added
- feat(ear): whistle channel landed end-to-end — the needle3 engine discovery (HF Cactus-Compute/needle3 ships all-platform engine binaries incl. windows-x86_64/needle.exe, 1.56MB single file; whistle's designated engine per its config) unblocked Windows-native inference: `needle --model whistle.cact --audio X.wav --audio-language en` → JSON. Official benchmark (SAPI known-text set, Windows CPU native): **whistle en WER 10.8%** (ttft 651ms, ~300 tok/s decode) vs SenseVoice baseline 2.7%/CER 0.0% — zh audio hallucinated as English transliteration (7 langs, no zh, behavior matches config); systematic defects recorded (today→"to day" tokenization splits, British spellings, digit normalization). drv_ear whistle channel upgraded to needle form (LAOS_WHISTLE_BIN/MODEL envs, JSON parsing with plain-text fallback, zh EINVAL guard, 10 tests + real-engine smoke through ear.transcribe at 597ms latency). Verdict locked: laos three-channel ASR — zh main = funasr/SenseVoice, multilingual light = whistle (value = tiny footprint 16.9MB+1.56MB all-platform incl. WASM/Android, not accuracy), HTTP = server. Full suite 496 green

## [v0.15.1] - 2026-10-06

### Fixed
- fix(laos): refiner self-correction upgraded from take-last-segment to **comma-scope discard** (the corrected fragment is the last clause before the marker; head without internal clause boundaries falls back to take-last; overly short tails fall back to original). Official AASR-Bench full set (ModelScope, 917 cases zh 510 / en 407): error rate 0.4571→0.3875 (**-15.2%**), 17 of 18 scenes improved or neutral (zh/explanation -0.649, voice_search -0.180, navigation -0.128), both passthrough scenes zero-damage; the only two positive deltas (en/daily_chat +0.091, zh/academic +0.014 = whole-predicate-replacement corrections) re-confirm the paper's case for a learned Refiner with laos's own data. Official repo audit recorded: 917 + 6,637 rubrics, LLaMA-Factory full finetune (template cpm4), onnx-int4 variant runnable under local onnxruntime. Tests 25 (+2), full suite 495 green

## [v0.15.0] - 2026-10-06

### Added
- feat(ear): AgenticASR reproduction & adoption — laos/refiner.py rule-based AgenticSR Refiner (filler removal with demonstrative preservation, stutter folding zh≥3/en≥2 with 这/那 double-fold exception, self-correction take-last-segment with predicate-guard for "不对/不是", idempotent cleanup; paper arXiv 2607.28175, XHS note login-walled → honest reconstruction from primary sources); drv_ear ear.refine tool + ear.transcribe(refine=True) — the paper's decoupled ASR→Refiner landed as a laos syscall; text-level 13-case error rate 1.083→0.113 (-90%), end-to-end (SAPI TTS disfluent speech → funasr → refiner) CER 1.563→0.042 (-97%); restatement-style corrections proven robust to ASR noise (errors fall in the discarded pre-correction segment); sub-clause replacement kept as documented limitation for the genie learned-refiner channel; 23 new tests, full suite 493 green

## [v0.14.0] - 2026-10-06

### Added
- docs(research): Transformer 效率演进时间线（小红书视频笔记整理）——视频五路取件全失败（App-only+登录墙），按既有预案从可验证来源重构并作诚实声明；三大脉络 少算（稀疏/近似/MoE）→ 少搬（FlashAttention IO 感知/PagedAttention）→ 少存（MQA→GQA→MLA→DSA、int8→FP8）+ 跳出注意力（Mamba→混合架构→DeltaNet 回流），关键节点全部带 arXiv 编号；与 laos 关系全 ○/◐（PagedAttention=OS 分页反哺模型层的方向论印证；端侧 MoE 对 npu 配额按激活口径计价的远期含义）。纯文档波次，按 README 版本定义"新文档域=MINOR"发版（先例 v0.6.0 调研语料库）

## [v0.13.0] - 2026-10-06

### Added
- feat(laos): confidence gate + paired VAD metrics — laos/confgate.py three-band ConfidenceGate (>= local execute locally / >= cloud second-pass verify with cloud_enabled=False privacy default dropping mid-band, never uploading / rest drop; EdgeAI-KWS edge-cloud split as a miniature of the syscall gate chain); laos/vadmetrics.py evaluate_vad (FA/FR/precision/recall/F1 + BG-FAR over foreground-silent∧background-active frames; bg_far_valid = f1 >= f1_floor anti-play-dead gate, Foreground VAD arXiv 2609.19856 metric-pairing principle); 24 new tests, full suite 439 green
- docs(research): four WeChat articles study (EdgeAI-KWS dual-MCU deploy / Foreground VAD / kernel-internals.org / GitHub 2026-09 trend — adoption ●×2 ◐×2 ○×1) + QNN workspace deep study (22GB Explore survey + five key files: vendor ADSP base untouched, SER registered as a SEE virtual sensor resident on SLPI inferring through AP deep-sleep, InferenceServer.kt on 127.0.0.1:8900 is the device-side counterpart of laos npu.infer; rulings A–F); INDEX 18→20 main reports; README test count 415→439

## [v0.12.0] - 2026-10-05

### Added
- feat(duplex+turnpolicy): speech-AI weekly adoption, timing core — laos/duplex.py event-timeline metrics (response latency / barge-in response / overlap ratio / premature-response count; Duplex-MPE four-capability decomposition, JSON-friendly summarize; unclosed intervals and beyond-horizon pairings dropped); laos/turnpolicy.py speak/hold/stop state machine with min-speech/tail-silence/min-hold gates (LateIntent premature-response guard; already-answered turns don't re-trigger); TurnBuffer.interject() head-of-queue frames for delegate results (SALMONN-duo seamless weaving / Context Spanning raw-text injection)
- feat(binaural+foa): spatial primitives — laos/binaural.py Goertzel per-band ILD/IPD binaural cues (SAIL disentangled spatial stream; exact-DFT final combining X = e^(-iω(N-1))·(s[N-1] − e^(-iω)·s[N-2]) verified against direct sum); laos/foa.py plane-wave FOA encode SN3D/N3D + quad-speaker decode + ACN order (Bin2Ambi / RMS-AQA groundwork; ACN first order is W,Y,Z,X, decode gives source-facing max / opposite zero, not exclusive)
- docs(research): speech-AI weekly digest (8 papers: spatial audio ×4 + full-duplex ×4, XHS login wall → arXiv week+theme reconstruction with honest note) + adoption plan + execution notes; 42 new tests, full suite 415 green

## [v0.11.0] - 2026-10-05

### Added
- feat(phone+micgeom): mobile-mcp borrowed features landed — screen.key/longpress/doubletap/devices + new drv_apps driver (apps.list/launch/close, kernel pkg gate extended to apps.*), laos/micgeom.py pure-stdlib MPE (cross-impl diff 0.0 vs numpy reference); adoption statuses updated

## [v0.10.0] - 2026-10-05

### Added
- feat(turnbuf+locks): Pipecat two lessons + unique_lock semantics into core — TurnBuffer (interrupt drops undelivered; commit records only delivered waterline into mem.* with judge passthrough); UniqueLock util + MCPClient._rpc adopts it with protocol-fact lock-lifetime note (adoption items B/C)
- feat(loudness): BS.1770-4 pure-stdlib adoption — K-weight/gated integrated/M/S/LRA + local-peak sinc true-peak; new ear.lufs driver tool (adoption item A from repro wave; calibration anchors -23.00 LUFS / mono -26.0 held)
- feat(docs): laos intro deck x5 — one outline, five PPT skills (ppt-master editable pptx 12p/320 shapes via quality-gated SVG pipeline; guizang Swiss validated deck; frontend-slides terminal-green 16:9 stage + E-key edit; html-ppt blueprint theme + vendored MIT assets + presenter mode; huashu black-gold ledger + 3-direction board); comparison README

## [v0.9.0] - 2026-10-05

### Added
- feat(repro): unique_lock semantics — RAII + early unlock + defer_lock + try_lock + owns_lock (Python contextmanager port of C++ article patterns)
- feat(repro): Pipecat frame-pipeline architecture — SystemFrame/DataFrame split, InterruptionFrame drains queued data while system frames survive, streaming pass-through, aggregator-after-output, HandoffGuard swallow+inject

## [v0.8.0] - 2026-10-05

### Added
- feat(repro): end-to-end SHO runner (sim→features→train→MAE-by-bin artifact) + per-image directivity in ISM (critical: orientation label needs VDP correlate) + four-module smoke aggregator
- feat(repro): PhaseCoder numpy port — exact MPE (GI-DOAEnet Eq.2-3: phase/freq modulation, alpha*r scaling, centroid spherical), mag+phase STFT layout (256/128), (frame,mic) tokenization, hparams meta; aligned line-by-line to cloned JAX source
- feat(repro): ShoNet — paper Fig.1 exact architecture (3xConv+2xBiGRU+2xMHSA+AdaMaxPool, cos/sin head)
- feat(repro): isotropic diffuse-field noise via sinc-coherence Cholesky mixing (2607.02129 §3.1 noise aug)
- feat(repro): pseudo-speech synth + cardioid VDP substitute + STFT phase sin/cos features (2CxTx128) + circular MAE
- feat(repro): Allen-Berkley ISM room sim + 6-mic r=4.5cm circular array + paper-range room sampler (2607.02129 §3.1)
- feat(repro): FxLMS ANC — engine-order reference synth, single-channel (>20dB tonal), LS secondary-path ID, mismatch robustness, coupled 2x2 multichannel (~15dB both error mics)
- feat(repro): BS.1770-4 loudness — K-weighting (48k Annex + parametric dual-path), gated integrated, M/S, LRA, true peak, PLR; fixed in-place K-weight mutation (double-filtering bug caught by idempotence test)
- feat(corpus): wave B v3 — longest-alias container hint unlocks KDD/WWW/WSDM/RecSys/MMSys/ICMR (8.8k papers, 24 yielding venues); ICLR/ICML/JMLR/CoNLL/ECCV/CHiME honest zeros (no Crossref registration)
- feat(corpus): OpenAlex top-up for Crossref-absent venues — ACL/EMNLP/NAACL/COLING real yields, CoNLL honest zero (topic disjoint), CHiME no source
- feat(corpus): multivenue wave A via Crossref backend — speech-adjacent venues rich (SLT/ASRU/WASPAA/TASLP/EURASIP), NLP confs structurally absent from Crossref (ACL Anthology), TACL/CL journals OK
- feat(scripts): multivenue crawler + venue probe (8 resolved) + fuzzy venue_of + opportunistic harvest
- feat(scripts): release helper — semver derivation from conventional commits, three-tree __version__ sync

### Fixed
- fix(corpus): AAAI unlocked via ISSN exact-filter route (600 papers) — relevance ranking drowns AAAI main proceedings; chime honest-zero restored; survey updated (29 yielding venues / 9,908 records)
- fix(scripts): enforce 75s floor on retry path + self-sufficient anti-hijack test

## [v0.7.0] - 2026-09-28

Jev 判断层四闸门 + selfcheck 加固 + 调研资产总纲收束。

### Added

- 可插拔 System-One 判断后端（judge backends）：rule 后端先行，live E2E 实测全链路（autogate 开启时 `rm -rf` 被拒并落 jev 审计）。
- 高危 syscall jev 预审闸门（opt-in）：高风险调用先过判断层裁决再放行。
- jev 过滤的记忆摄入与压缩（opt-in）：MemoryStore 入口与 compaction 均可挂判断闸（JevGatedMemory）。
- 技能蒸馏 jev 质量闸门：任务轨迹升格为可复用技能前先经判断层把关。
- 判断校准台（scripts/judge）：标注集 + 混淆矩阵 + 置信分桶，量化 judge 成色。
- criteria 问句常量：instructions 与 true/false 判据两套问艺模板（源自 jev-chat-jarvis 评估的采纳项）。
- memory `self_check`：JSONL 完整性 + 归一化 + 召回 sanity 三检（模式取自 jev-chat-jarvis KbSelfCheck，MIT）。
- 调研收束三件：Jev System-One 版图（GitHub 778 仓库普查、8 类分类、端上实测 157.5ms 中位——证伪 README 15.6ms 旧口径）、jev-chat-jarvis 评估（拒绝伪装捕获红线，采纳校准/问艺/自检）、laos 落地总纲 capstone（全部调研资产按"来源→可取之处→落点→状态"映射为 59 份文档的主索引）。

### Changed

- README 测试计数对齐至 288（判断层并入后 253→288），判断层参数口径措辞同步修订。

### Fixed

- JevGatedMemory 的 judge 转发缝隙收敛，live E2E 验证通过（rule 后端 + autogate + rm-rf 拒绝带审计）。
- selfcheck 两轮加固：先显式化 bad-line 丢弃副作用（docstring + stderr 警告）并容忍非标量 id；随后措辞精确化（仅不可解析行被移除）且 `_next_id` 容忍损坏记录（live 发现的 KeyError）。
- 收尾杂修：autogate/rule 后端警告、校准台退出码、版图条目相邻锚点。
- capstone / INDEX 计数与一致性修正：59 份文档总数对账、优先级一致、§G 与 README 对账、三棵树路径前缀、第 4 状态锚点。

## [v0.6.0] - 2026-09-18

调研语料库波次：19,792 篇双会议论文 + 3,724 个 OSS 仓库 + 分域模型地图。

### Added

- 19,792 篇统一论文语料库：ICASSP 2022–2026 五年全量 14,285 篇 + Interspeech 五年全量 5,507 篇（ISCA 档案逐篇枚举，回填 1,069 篇摘要、89.1% 成功率），统一语料带验证器。
- OSS 版图：GitHub 音频/AI/Agent 仓库遍历 3,529 个，去噪 + 回填后 3,724 个清洁仓库（2,153 清洁 + 1,571 回填），14 类分类 + laos_fit 映射。
- 语料工具链：ICASSP Crossref 枚举器（offset 分页 + DOI 前缀过滤）、GitHub 仓库爬虫（引号短语搜索）、研究表格共享 markdown lint。
- 语音情感（SER）分档地图：edge / small（<30M）/ medium（30M–500M）/ large + 语音 LLM / multimodal 五轴，附交叉表、决策树与 HTML 全景；多模态轴裁决"不引入视觉模态"。
- 语音前沿逐篇跟踪：说话人 / 前端 / 编解码-TTS / 副语言 51 篇（2024–2026），映射到 laos 用户可感知功能。
- AlwaysOnRec-ZCode 隔离区语音前沿增量：PCEN VAD 前端、envelope-DTW 唤醒词（含易混淆词）、opt-in 音频归档、ear.assess 发音韵律评估、合规红线章节（279 测试全绿）。
- 研究地图与索引：常开录音"漏斗 × 模型能力"路线图（含合规红线）嵌入 README 第 10 节，附研究索引与 2026-09 修订日志。

### Changed

- 五年遍历报告定稿：主题矩阵改为从源文件重算（ICASSP 的 jsonl 标签已损坏、不可信）。

### Fixed

- SER 档位表补正：SALMONN-7B/13B 遗漏行按裁决 3 记为 A 档。

## [v0.5.0] - 2026-09-11

常开录音内核能力 + 双沙箱并行推进 + 情感/事件模型地图。

### Added

- 麦克风能力阶梯：listen / record / transcribe / always_on 四级内核能力，逐级授权。
- 常开录音模式：环形缓冲 + 回溯（rewind）；drv_rec Opus 编码（带回退链）+ 存储配额。
- 双沙箱并行落地 Apple 基准增量：AlwaysOnRec-Trae 实现能力阶梯 / Opus 编码 / 常开模式三件，AlwaysOnRec-ZCode 隔离区实现 journal 标题 schema 与 mic `time:` 窗口作用域（261 测试全绿）。
- 模型地图两份：SER 边缘-小-中-大-多模态五分类选型映射；音频事件识别（AED）+ AGC/语音增强五分类（以 DCASE'25 冠军 61.5% @122K 参数的蒸馏范式为端侧锚点，README 现有口径）。

### Fixed

- 常开录音调研报告终审修订（final review fixes）。

## [v0.4.0] - 2026-09-11

听觉 + 记忆 + 日记波次，手机五层感官驱动，强制层 OSAL 化。

### Added

- 听觉双驱动：drv_mic 显式录音（每次调用写 `event:mic` 审计）+ drv_ear SenseVoice 双通道转写。
- MemoryStore 情景记忆 + `mem.*` 内建 syscall；每日日记（audit + memory 整合沉淀）与 laosweb 记忆 / 日记面板。
- 手机五层感官驱动波次：drv_screen（adb + uiautomator 屏幕理解与操控，pkg 作用域）、drv_genie 双后端 LLM（QAIRT Genie / OpenAI 兼容）、drv_notify + drv_comms、drv_battery + 电池感知动态电力定价（风险乘数）、drv_events（端上传感写入记忆）。
- 常开音频链路：零依赖流式 VAD（批 / 流一致性）→ drv_rec VAD 门控录音会话 → journal 管线（批量 ASR 分段入记忆、自动 GC）→ 日记"五、今天听到的"段落 + 每周心情报告。
- 技能库：成功任务轨迹蒸馏为可复用技能。
- 强制层 OSAL 化：linux / stub / android 三后端（含 Termux 检测）经 `LAOS_ENFORCEMENT` 运行时选择。
- drv_npu 真机闭环：adb 设备传输层 + runbook；drv_audio 语音分离 / 回声消除（FLASepformer + JAEC AEC）+ RTX 4060 GPU 基准（线性复杂度验证）。
- 调研波次：常开录音全景（产品 / OSS / 论文 / 功耗 / 隐私，21 篇论文归档 + arXiv 工具 + HTML 交付）、垂直应用与 Apple Watch S12 音频智能。

### Changed

- 强制层重构为 OSAL 骨架（linux / stub 后端原样迁移），多平台后端可插拔。

### Fixed

- 记忆与监听加固：MemoryStore 原子重写（temp+replace）、mic 拒绝时补写审计、监听线程加固。
- 架构图重叠修复：容器标签固定置顶，audit / enforcement / adb 连线改走空白边距。

## [v0.3.0] - 2026-09-09

laosweb 交互控制台 + NPU 驱动。

### Added

- laosweb 交互端点：confirm 队列 / restart / kill / operator msg。
- laosweb 控制台：确认横幅、重启、终止、操作员消息四类操作落地。
- drv_npu 驱动：QNN 后端探测 + 计价推理，接入 demo act 4.6。
- 调研：QNN / ADSP 真机集成路线研究（A / B / C 三条路）。

### Fixed

- laosweb confirm 不再读 stdin——面板场景默认拒绝（dashboard-safe default deny）。
- 控制台交互两轮评审加固：fail-safe 重启、killed 状态守卫、调度器锁、double-get 修复。
- laosweb v2 计划文档 fence 配对与接口契约修正。

## [v0.2.0] - 2026-09-05

内核强制层与语义扩展大波次：seccomp / CoW / eBPF / FleetLedger / MCP Tasks / 信箱 / laosweb。

### Added

- seccomp BPF 系统调用强制：纯 Python 零依赖 BPF 汇编器，接入驱动 spawn 全链路（含 cgroup 集成）。
- CoW 文件系统隔离：原子 temp+replace 原语、硬链接 COW fork（零数据拷贝）、inode 快速 diff，覆盖驱动写入 / 追加路径。
- eBPF 系统调用画像：bpftrace 后端（可选，缺依赖时优雅降级），接入 demo 与 `laosctl prof`。
- FleetLedger 不可逆风险账本（Irreversibility Budget 2.0）：加权风险记账、每 Agent 风险上限、带舰队风险储备的 spawn 准入控制、`laosctl budget` 台账回放。
- 陈旧上下文检测：上下文观察簿 + 内核失效接线 + Agent 循环通知注入与提交钩子。
- AgentProf 语义画像：审计流 span 构建与启发式归因、OTLP / JSON 导出契约，接入 demo 与 laosctl。
- 内核语义扩展套件：双向 MCP 请求（elicitation）+ MCP Tasks 异步工具调用（客户端轮询）、信箱 IPC `msg.send/recv/list` 内建 syscall（配额契约）、运行时能力委托（TTL + 可撤销）。
- 调度语义与面板：每 Agent 可靠性预算（Patient Bytes）+ 意图驱动 task_scope 路径收窄 + laosweb 实时仪表盘（状态 API + 面板页）。

### Fixed

- seccomp 两轮修复：勘误 pivot_root / finit_module 的 x86_64 系统调用号；unshare 之后经 bootstrap shim 安装 seccomp（含 shim 测试断言与架构守卫）。
- 驱动 PID 与审计修正：cgroup / 画像取真实驱动 PID、E2E 加固、mount API denylist 收口；固定测试环境旋钮、risk_cap 在 fork_child 传递、EDQUOT 判定先于风险闸。
- 观测与调度修复：span 计时改用审计 t（每调用粒度，R206）、暂停 Agent 的调度等待上界（R307）、task_scope 路径匹配遍历加固。
- laosweb 稳定性：面板原地刷新（消除每 tick 重复渲染）、内核状态无锁快照读（ctx 副本 + audit seq）。

## [v0.1.0] - 2026-09-04

基线：内核 + 强制层骨架 + 研究文档基线。

### Added

- 用户态薄内核 laosd 语义层骨架：进程表、能力表、驱动路由、审计（kernel / agent / brain / scheduler / sandbox / mcp 等 9 个模块）；不改内核，用 namespace / cgroup / seccomp / landlock 做强制层。
- 首批驱动与工具：drv_fs / drv_proc / drv_sys 三驱动 + laosctl 控制台；零第三方依赖，macOS / Windows 自动降级为"仅能力表"。
- 研究与测试基线：AgentOS 版图、AIOS 深读（docs/research）+ 回归测试起步，全仓 149 个文件。
