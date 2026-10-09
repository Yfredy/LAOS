# 计划状态登记（plans/）

> **本仓库约定：计划正文的 checkbox 执行时不勾选——完成度看 commit 与落点，不看 checkbox。**
> 状态三值：`已执行`（交付物在 git 历史可证）/ `部分执行` / `待执行`。本表 41 份（2026-10-09 盘点）。
> 排查命令：`git log --oneline --all -- <落点路径>`。

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
