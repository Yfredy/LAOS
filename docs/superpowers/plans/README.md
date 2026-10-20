# 计划状态登记（plans/）

> **本仓库约定：计划正文的 checkbox 执行时不勾选——完成度看 commit 与落点，不看 checkbox。**
> 状态三值：`已执行`（交付物在 git 历史可证）/ `部分执行` / `待执行`。本表 52 份（2026-10-09 复盘点 42 + 新增 audio-replay/aor-lifelog/aurase-adoption/evolve-followups + 2026-10-12 auditory-governance-wave + 2026-10-12 audiovisual-innovation + 2026-10-15 brain-reliability-repeat-guard + 2026-10-18 audio-agentos-litreview-survey + 2026-10-18 audio-agentos-survey-v2 + 2026-10-20 campplus-htp-timeout）。
> 排查命令：`git log --oneline --all -- <落点路径>`。

## 计划编写纪律（2026-10-09 制度化，取自 writing-plans 技能查漏补缺）

新计划沿用现行体例（四段头 Goal/Architecture/Tech Stack/Spec + Global Constraints + 每 Task 的 Files/Interfaces/checkbox 步骤，TDD 先红后绿，每任务一 commit）。在此基础上三条增量纪律，即日起生效：

1. **写完三查**（保存前必跑，自查非派发）：
   - **spec 覆盖**——spec 里每个需求都能指到对应 Task；有缺口补 Task，不许带缺口发布；
   - **占位符扫描**——"TBD"/"加适当错误处理"/"处理边界情况"/"为上述写测试"（不带测试代码）/无代码块却描述代码的步骤 = 计划失败，重写；
   - **类型一致性**——跨 Task 消费的签名（函数名/参数返回类型/字段名）逐字符一致；Task 3 的 `clearLayers()` 到 Task 7 变 `clearFullLayers()` 这类漂移就是计划 bug。
2. **Task 尺寸判据**：Task 是携带自己测试周期、值得单独过一道评审门的最小单元——setup/配置/脚手架/文档步骤折进需要它的 Task，只在"评审者可能否决这个而批准相邻那个"处切分。步骤粒度 2-5 分钟一粒，但 Task 不是步骤的机械聚合。
3. **乱序阅读禁令**：执行者可能乱序读 Task（zones 并行执行是常态）——跨 Task 引用一律原文重复（代码块照抄），禁止"类似 Task N，参见其做法"；邻 Task 之间的签名学习只经 Interfaces 的 Produces 块传递。

| 计划 | 状态 | 落点摘要 |
|---|---|---|
| 2026-08-31-laos-aios-mechanisms.md | 已执行 | AIOS 机制研究 → 调研文档 + 内核语义（v0.1.0 基线期） |
| 2026-09-04-kernel-enforcement-cow-ebpf.md | 已执行 | 内核强制层三件套（seccomp BPF/CoW/eBPF profiler）→ v0.2.0 |
| 2026-09-05-agentprof-spans.md | 已执行 | AgentProf → laos（v0.3.0） |
| 2026-09-05-irreversibility-budget-2.md | 已执行 | 不可逆预算 v2 → kernel 风险账本 |
| 2026-09-05-kernel-ipc.md | 已执行 | 信箱 IPC → v0.3.0 |
| 2026-09-05-mcp-2026-07-28.md | 已执行 | MCP Tasks 接入 → v0.3.0 |
| 2026-09-05-stale-context.md | 已执行 | 上下文过期治理 → laos/context.py |
| 2026-09-06-intent-scope.md | 已执行 | 意图作用域 → kernel task_scope |
| 2026-09-06-laosweb-dashboard.md | 已执行 | laosweb v1 → bin/laosweb.py |
| 2026-09-06-laosweb-v2-console.md | 已执行 | v2 控制台（五 POST + 运维面） |
| 2026-09-06-reliability-budget-scheduler.md | 已执行 | 可靠性预算调度 → v0.2.0 波 |
| 2026-09-10-always-on-audio-journal.md | 已执行 | 全天候音频日记 → diary/journal（v0.4.0） |
| 2026-09-10-ear-memory-diary.md | 已执行 | 听觉记忆日记 → drv_ear/MemoryStore（v0.4.0） |
| 2026-09-10-enforcement-osal.md | 已执行 | 强制层 OSAL 抽象 → laos/seccomp.py 分层 |
| 2026-09-10-smartphone-agent-five-layers.md | 已执行 | 手机五层 → drv_screen/notify/comms/battery/events（v0.5.0） |
| 2026-09-11-always-on-recording-capabilities.md | 已执行 | 全天候能力调研 → docs/research/always-on-recording/ |
| 2026-09-11-always-on-recording-landscape.md | 已执行 | 全天候业界全景 → 同上（收敛版/业界版） |
| 2026-09-11-always-on-recording-research.md | 已执行 | 全天候研究线 → 同上 + 双沙箱 zones/（v0.5.0） |
| 2026-09-11-audio-event-models.md | 已执行 | AED 调研 → audio-events/ 全线（2026-10-08 收尾完成，58 条+landscape+HTML+07 落地） |
| 2026-09-11-auto-gain-models.md | 已执行 | AGC 调研 → auto-gain/ 全线（收尾完成，48 条+分层判定+HTML+07 不加结论） |
| 2026-09-11-speech-emotion-models.md | 已执行 | SER 调研 → speech-emotion/ 全线（收尾完成，46 条+06 落地 HY4 sherpa 通道） |
| 2026-09-13-full-traversal-papers-and-oss.md | 已执行 | 论文全量遍历 → corpus 19,792 篇（v0.6.0） |
| 2026-09-14-audio-ai-agent-oss-landscape.md | 已执行 | 音频/AI/Agent OSS 景观 → corpus 3,724 OSS |
| 2026-09-14-icassp-interspeech-census.md | 已执行 | ICASSP/Interspeech 普查 → 语料基座 |
| 2026-09-18-jev-chat-jarvis-assessment.md | 已执行 | jarvis 评估 → 采集链路整体拒绝 + 校准台/问句方法论采纳 |
| 2026-09-18-jev-system-one-layer.md | 已执行 | Jev 判断层 → 四闸门 + criteria 问句（v0.7.0） |
| 2026-09-19-laos-adoption-capstone.md | 已执行 | 采纳总纲 → capstone + INDEX 导航中枢 |
| 2026-09-21-jev-decision-model-survey.md | 已执行 | Jev 决策模型调研 → 11 处硬阈值映射 + edgejev 实测 |
| 2026-09-28-multivenue-paper-survey.md | 已执行 | 多 venue 普查 → venue_expansion 前身 |
| 2026-09-28-versioning-and-releases.md | 已执行 | 语义化版本 + 发版流程 → release.py/tags/CHANGELOG（v0.7.0 起全链，发版纪律 AGENTS.md） |
| 2026-10-06-venue-expansion-survey.md | 已执行 | venue 扩展普查 → corpus/venue_expansion 123,271 行 |
| 2026-10-07-clef-decision-layer.md | 已执行 | Clef 判断层 → 判断层三路线（rules/edgejev/clef） |
| 2026-10-07-corpus-reuse-upgrade.md | 已执行 | 语料复用升级 → scripts/query_corpus.py |
| 2026-10-07-review-instrumentation.md | 已执行 | 上线前两评审 → docs/review/（P01-P15/R1-R11 冻结编号） |
| 2026-10-07-telemetry-implementation.md | 已执行 | 埋点实现 → laos/telemetry.py + 10 钩子（23 事件/138 字段） |
| 2026-10-08-agentos-demo.md | 已执行 | Linux AgentOS demo → demos/agentos-demo（v0.27.0） |
| 2026-10-08-laosweb-v3.md | 已执行 | laosweb v3 → 四 tab/PWA/治理面（v0.29.0，989 绿） |
| 2026-10-08-repo-hygiene.md | 已执行 | 仓库卫生波 → zones/ 收编 + 目录学约定（v0.29.0） |
| 2026-10-08-sentinel-wave.md | 已执行 | Sentinel 动作闸 → laos/sentinel.py + provenance（v0.28.0/28.1） |
| 2026-10-08-speech-research-closeout.md | 已执行 | 语音三域收尾 → 三线 landscape/HTML/落地 + HY4 sherpa（152 绿） |
| 2026-10-09-onboarding-handover.md | 已执行 | 新人交接 → docs/ONBOARDING.md + scripts/check_onboarding.py 门禁（本表所在波） |
| 2026-10-09-openevolve-trial-and-laos-driver.md | 部分执行 | T1/2/4/5/6/8 已执行：laos/evolve.py（gate/装配面）+ evolve.run 内建 syscall（0462915）+ drivers/drv_evolve.py + openevolve_job.py（558f93d），主套件 **1085 绿**（终审 C1/I2/I3+M4/M7/M8 修复波后实跑；565dec8 已并入 master）；T3/7 按预案收档 BLOCKED（无可用 LLM 后端——七端点全 401/网关 NXDOMAIN/无 ollama，证据 var/rsi/openevolve/OBSERVATIONS.md §后端/§e2e）；解锁补跑入口=2026-10-09-evolve-followups.md |
| 2026-10-09-audio-replay.md | 已执行 | 录音回放 rec.replay：laos/ringbuf.py 环冲（30s=960KB/clamp 120s）+ mic.replay 快照 + 内核跨驱动组装（syscall 审计按 tool 抹除转写+event:mic 成败双路+sentinel 置污）+ laosweb /api/replay 卡片；SDD 六任务+终审修复波（C1 审计封口/I1/M1/M2）；v0.36.0 发版（1121 绿）；摘要模型扩展位 §扩展位 |
| 2026-10-09-aor-lifelog.md | 已执行 | 生活日志双记忆：laos/soundscape.py（Goertzel+LUFS，-inf floor 防护）+ laos/rhythm.py（拾音时刻 [HH:MM] 前缀优先）+ journal --diary（含预存 ear_transcribe 名字 bug 修复）+ diary 第六章（SECTION_TITLES 5→6）；SDD 六任务+终审修复波（C1 拾音时刻/I1 不炸批/I2 锚）；v0.37.0 发版（1140 绿）；§功能版图交付 |
| 2026-10-09-aurase-adoption.md | 已执行 | T1-T3+终审修复波全落地：laos/evolve.py RewardSpec+aggregate（55e787c）+ EvolveResult 可选 reward 字段+审计条件键 reward_version（8a28b82，字节级不变实测钉住）+ drivers/README 立约+AGENTS.md 登记（2fdbb69）+ null/NaN 边界修复（99af75d）；Subagent-Driven 执行（三任务各自评审通过+终审 Clean）；test_evolve 32 例，全量 1121 绿；随 aor-waves 波后下一 MINOR 携带 |
| 2026-10-09-evolve-followups.md | 待执行 | openevolve 终审遗留三件（决策已预决按推荐）：① evolve.run 默认入 sentinel always_ask（③ 级全 mode 生效，② 显式 rule 唯一免问通道）② AuditLog.rotate() 持 _wlock（(epoch,seq) 键全库唯一硬契约，并发压测钉不变式）③ scripts/evolve_e2e.py 解锁 runbook（--check 探测 rc=0/2 口径 + 全链真跑自动留痕 asks/事件循环让出实证/checkpoint 布局钉死，产物只落 var/）+ §8/#9 回写 |
| 2026-10-12-auditory-governance-wave.md | 待执行 | 听觉治理波（四方向 A/B/C/D，内核侧纯 stdlib + 驱动挂钩，8 Task）：A 说话人分离（laos/speaker.py 7 带谱质心到达顺序贪心聚类，不建跨会话声纹库；journal `[S1]` 标签 + diary 第六章聚合）；B 听觉缺页召回（laos/audiodream.py 即焚后 audio_status=burned 软降级，永不复活字节；memory.mark_burned + recall 套壳）；C 声景驱动调度（laos/duty.py 聚合声景反推 VAD 阈值偏移 ±5，drv_rec 下段 rec_start 消费，不改显式 syscall/LAOS_REC=0 红线）；D 即焚销毁回执（laos/burnt.py rec_gc/journal 删除前 sha256 回执、哈希算完即弃，新增 burn.verify 只读核验）。建议优先序 A→D→B→C。**外部模型评估（追加）**：评估一 `FLASepformer-JAEC`＝语音分离非 diarization（不出标签+CC BY-NC 4.0 仅非商用+8k 非流式+重依赖）→不并入 Task A，记驱动侧可选 ASR 前置级；评估二 diarization 家族（NeMo Streaming Sortformer AOSC=到达顺序身份/NVIDIA Open Model License 可商用（原记 CC-BY-4.0 已复核纠正，那只是第三方 CoreML 转换仓许可）、阿里 3D-Speaker CAM++ 7.2M/Apache-2.0、pyannote3.1 gated）＝对口→作驱动侧可选后端，交付 Task A4 `normalize_arrival_labels`（纯 stdlib 归一接缝，模型接入唯一内核入口，主套件不触模型依赖）；Task A1 纯 stdlib 聚类保留为零依赖默认/兜底。**体量红线（2026-10-12 追加）**：内核/手机端常驻链路模型权重上限 ~50MB（含推理内存，报"磁盘 MB+峰值 RAM+CPU/GPU"三项）——据此重排为两档：CAM++（7.2M/fp32 ≈29MB 参数推衍/Apache/CPU）升常驻首选；Sortformer（117M/gguf F32 471MB·F16 237MB·Q8 139MB 实测口径/GPU）禁入常驻，只挂 journal `--diar` 桌面离线后处理档；pyannote（ResNet34 嵌入 6.6M/ONNX 28MB）因 gated 接入摩擦不优先。**复核补全（2026-10-12）**：FLASepformer=arXiv:2508.19528（Libri2Mix-100 SI-SNRi 20.3dB，CC BY-NC 4.0 禁商用），JAEC=10ms 帧/22ms 固定延迟/CPU RTF≤0.0039（许可证转述 Apache-2.0，单一来源待确认）；**两模型早已落地为 drivers/drv_audio.py 的 audio.separate/audio.aec（laosd:161 加载+venv 门控测试，本机 .venv-audio 可跑真实推理）——挂载点已存在，缺默认链路接线+许可证放行，维持 opt-in 现状** |
| 2026-10-12-audiovisual-innovation.md | 待执行（构思+路线图，Wave 1 可执行） | 音视频创新波：§0 勘察坐实三大空白——视觉栈为零（51 模块无一涉视觉）、screen.shot 无人消费、空间音频三件（binaural/foa/micgeom）只被自己测试引用；§1 七方向含 4 条明确否决（视觉常驻 AED/跨会话声纹/唇读/截屏喂多模态）；Wave 1 屏幕语义漏斗（laos/screenlog.py 界面签名丢弃 text/id + bin/screenlog.py LAOS_SCREENLOG 门控 + diary 第七章双模态时间线，XML 字节零落盘），代码已在 var/scratch 试跑并通过（修掉单样本抖动劈断会话的真 bug）；Wave 2 听觉预算/听觉 taint、Wave 3 空间方向（硬门：drv_mic CHANNELS=1 需 LAOS_MIC_CHANNELS=2）接口已冻结待拆独立计划 |
| 2026-10-15-brain-reliability-repeat-guard.md | 待执行 | 第一波（esp32 借鉴 #2，spec: research/2026-10-15-esp32-iphone-agent-borrowing）：修两个现存洞——① `brain.py:211` tool_call 参数非法 JSON 直接崩 think()（一次输出抖动报废整个任务）→ Thought 增 `retryable` 标志 + think 接受 `temperature`，任一坏 call 整轮转可重试（半套调用比没有调用更危险）；② `agent.py:124-159` 死循环仅靠 max_steps=12 硬截断、烧穿 token 预算 → 温度阶梯 0→0.4→0.8（esp32 同款三档，第 3 轮仍坏即 ok=False 放弃）+ 重复 syscall 检测器（同 tool+同参数第 3 次触发 `ctx.notice` 强制换策略，每 key 只通告一次）。四 Task 全 TDD，新增 tests/test_brain.py + tests/test_agent_reliability.py（含 kernel 装配自包含副本，守乱序阅读禁令）；不动 kernel/驱动，核心零依赖 |
| 2026-10-18-audio-agentos-litreview-survey.md | 已执行 | 音频智能体综述（LitReview S0–S8，9 Task）：正文 `2026-10-18-audio-agentos-survey.md` + 证据附录 `-evidence.md` + `scripts/check_survey.py`/`tests/test_check_survey.py`（15 测试，strict 门禁）；覆盖 AgentOS×音频、多模态、全天候录音、SER、AED/AGC（3 档规模 × 端侧/多模态标记，AED 加任务类型、AGC 加经典 DSP 与作用点）；目标 80 篇纳入、每篇六字段卡片 + 条件化矩阵 + 未来方向溯源；本仓语料仅 123,271 条元数据/115 篇 PDF，不声称全量全文精读 |
| 2026-10-18-audio-agentos-survey-v2.md | 已执行 | 综述 v2（9 Task）：**AGC 神经增益定向补检索**——arXiv 5 式/ISCA Interspeech 2026 全目录 767 篇/Crossref 三通道，新增卡片 **S81–S91**（WaveNorm Interspeech 2026 为唯一「纯增益+因果+端侧画像」条目），**推翻 v1「无纯神经增益模型」**（根因是 v1 检索式 `AND abs:audio` 把 46 条切到 1 条）；正文 §6 全章改写 + 新增 §6.6 准入门槛三条、§3.5 多媒体两条主线与成本闸、§3.6 三道闸小结；`auto-gain/00` 追加裁定 3/4/5（纯增益划界 / MACs≠参数量 / 失效仓库），02/03/04/05 域表回填（中型档记"小的有、中的没有"断层）；新增 `scripts/md2html_survey.py` + HTML 阅读版；文献 80→91 篇，strict 门禁 0 违规 |
| 2026-10-20-campplus-htp-timeout.md | 部分执行 | CAM++ W8A16 SM8845/V81 真机超时排障（6 Task）：同 build runner/metadata 门禁、有限 QAIRT+编译配置矩阵、真实中间 tensor 前缀/后缀二分、单 context 语义修复或最多双 context 备用、paired accuracy、1000 次延迟与 30 分钟 soak；10 秒 FastRPC watchdog 始终开启。**提交区间 `80413f6..7bb42f2`（Task 1-6 + 任务评审修复轮 1-3）**；Task 1-5 离线链路（bounded 矩阵/真实 probe 二分/改写与分区门禁/accuracy 证据绑定）已落地，Task 6 交付 `scripts/speaker_qnn/report.py`（确定性渲染 + `--check` 漂移门禁）与报告 `docs/research/2026-10-20-campplus-qnn-sm8845.md`。**blocked 原因**：设备全程不在 adb（`device_unavailable`），真机只留下 2 次 smoke `pass`（16 个有限输出）与 2 次 CAM++ `ssr`（退出码 17、0 输出）；4 个完整图变体全部 `config_warning` 未上机、2.47.0 被元数据门禁拒绝（`socModel=0`），隔离区间停在 `awaiting_device`（待验证 [0,3101]），双 context 分区 `solves_root_cause=unproven`，故 Task 6 的冷/暖延迟、吞吐、30 分钟 soak 与 paired accuracy 均未执行，报告终态 `blocked`。解锁入口=设备恢复后先跑 prefix/suffix probe 验证隔离区间，再跑 30 次首通门禁与 1000 次测速 |
