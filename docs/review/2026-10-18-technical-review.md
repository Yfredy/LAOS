# laos 技术评审（2026-10-18）

> **评审对象**：laos v0.39.0（主库 1180 项测试实跑通过，`unittest discover` = "Ran 1180 tests · OK (skipped=5)"，2026-10-18 当日 collect 实跑核对；laos/ 51 个 .py 模块文件 + enforcement/ 四后端；drivers/ 17 个驱动子进程）。
> **定位重申（叙事红线）**：基座是 Linux 内核，Agent 是内核之上的新负载（与进程同类）；laos 是内核治理在用户态的延伸——laosd 是架在 Linux kernel 之上的薄内核（语义层），所有特权操作最终仍由 Linux 执行，laosd 只负责"允许不允许、记不记"。
> **数字口径**：本文全部数字取自 2026-10-18 当日实跑（测试计数逐项见 §5）或仓库既有实测记录（CHANGELOG 各版段、复现区记录、调研报告）；未实测维度一律明写"未实测"，不引入外部宣称值。
> **测试数 1180 的构成归属**（当日三次对账：静态 `def test_` 计数 1211 = 实跑 1180 + 31 个 pytest-only 盲区见 R9）：v0.39.0 发版时点 **1158** + 1（dated 报告排除回归，d396f37）+ 6（锚点五形态同步回归，本评审批次 tests/test_release.py）+ **15**（综述校验器 check_survey，当日并行的「音频智能体综述」SDD 批次三提交 10a28cd/d594c6f/bbc48c0）。后 22 项为未发版增量——README/PROJECT_OVERVIEW/decks 等介绍文件持**发版时点口径** 1158，ONBOARDING 事实表持**门禁实跑口径** 1180，两档差 +22 项待下次发版由 release.py 统一刷新（口径设计见 ONBOARDING §0）。
> **当日并发事件**（详见 R16）：并行 SDD 会话在 tests/ 落盘测试文件的同时，介绍文档遭外部浮写（1164/1165），本评审数字以回退后实跑为准。
> **本文角色**：对《技术评审 v0.19.0》（docs/review/2026-10-07-technical-review.md）的现行版刷新——该文风险表编号 R1–R11 自其时冻结，本文沿用编号逐条更新状态（已关闭/开放/部分缓解），新增债务顺延 R12+，作为飞书文档评审会议的技术侧依据。

---

## §1 架构盘点（七层表）

> 模块清单实取自 `ls laos/`（机械口径：主包 51 个 .py = 50 个功能模块 + 包 `__init__.py`；`laos/enforcement/` 子包另 5 个 .py = 4 个后端文件 base/linux/android/stub + 子包 `__init__.py`）；驱动清单实取自 `ls drivers/drv_*`（17 个）。完成度口径与《需求评审 2026-10-18》§2 交叉一致。

| 层 | 一句话职责 | 核心模块（laos/） | 驱动/入口载体 | 完成度 |
|---|---|---|---|---|
| **① 内核语义层** | 架在 Linux kernel 之上的用户态薄内核：进程表、九级 syscall 闸门链、驱动路由、审计、上下文配额 | `kernel.py`（闸门链+审计）、`agent.py`（Agent=进程）、`brain.py`（LLM 决策，temperature 阶梯）、`scheduler.py`（多 Agent 公平复用 LLM）、`mcp.py`（MCP over stdio = 驱动总线）、`validate.py`（schema 校验+路径围栏）、`sandbox.py`（PathJail）、`branch.py`/`cow.py`（fork-COW 分支原语）、`context.py`（窗口+换页+swap+观察簿） | `bin/laosd.py`（一次性引导器）、`bin/laosctl.py`（离线审计回放）、`bin/laosweb.py`（常驻宿主）；内建 syscall 11 条（msg.*×3 / sys.delegate / mem.*×6 / rec.replay 跨驱动组装） | **✅ 完整** |
| **② 强制层** | 把 Linux 内核已有强制原语包装成 laos 的"保护环"；OSAL 换平台=换一个文件 | `seccomp.py`（ctypes 经典 BPF，30 条黑名单）、`enforcement/`：`base.py`+`linux.py`（unshare+seccomp+cgroup v2 真隔离）+`android.py`（Termux 矩阵）+`stub.py`（非 Linux 降级） | `scripts/termux_matrix.py`（降级矩阵一键实测） | **✅ 完整** |
| **③ 治理增强层**（opt-in） | Sentinel 动作闸 / 能力注册表 / 判断层 / 置信闸——全部缺省不装配、字节级不变 | `sentinel.py`（六级有序动作闸+GrantStore+TaintTracker）、`caps.py`（四级 caller+四枚权限位+DRAINING）、`decide.py`（Noul/Choice/Score 三判型+后端插拔）、`calib.py`（Brier/ECE/reliability）、`confgate.py`（local/cloud/drop 三段闸）、`judge.py`（Rule/Cloud/Local/Safe 四后端） | `laos/judge.py` 钩子挂 memory/context/skills；drv_clef（wsl 调 clef_infer） | **✅ 完整**（26+21+74 例测试） |
| **④ 记忆与认知** | 情景记忆 + read-time 整理 + LLM 前置短路 + ASR 纠错 | `memory.py`（JSONL+bigram Jaccard）、`jitmem.py`（Curator：三分量加权/近重复去重/字符预算整条取舍/用户行神圣）、`knowledge.py`（bigram 短路阈值 0.58）、`refiner.py`（AgenticSR 规则版） | 入口 `bin/journal.py`/`bin/diary.py`/`bin/mood_report.py` | **✅ 完整**（refiner 覆盖面窄为已知局限，见 R5） |
| **⑤ 对话控制面** | 唤醒会话机 + 调度核 + 话轮路由 + 全双工件 + 事件防火墙 + 管线装配 | `wakegate.py`（四态+附和白名单）、`dialogsched.py`（generation 版本化打断/latest-only/MicrophoneGate/TtsRouter）、`turnpolicy.py`（speak/hold/stop+TimedTurnJudge 限时判断）、`turnbuf.py`（打断即作废+水位 commit）、`speechchunk.py`（LLM 流→TTS 适配）、`dialogflow.py`（管线装配）、`evroute.py`（JSON 规则热载+六动作映射） | `laos/dialogflow.py` DialogPipeline；消费方=语音问答管线 | **◐ 部分**：控制面语义 ✅（ARVIS 三件 27 例）；**laos 侧 TTS 合成后端 ○** |
| **⑥ 听觉栈** | 四段漏斗 + 三通道 ASR + 评测与空间音频研究件 + 生活日志双记忆 | `vad.py`（StreamingVAD，10ms 帧，audioop 优先+3.13 纯 Python 兜底）、`vadmetrics.py`（FA/FR/F1+BG-FAR）、`wer.py`、`loudness.py`（BS.1770-4 纯 stdlib）、`binaural.py`（ILD/IPD）、`foa.py`（一阶 Ambisonics）、`micgeom.py`（MPE）、`duplex.py`（双工时序度量）、`ringbuf.py`（回放环冲）、`soundscape.py`（七分带声景）、`rhythm.py`（时域节律） | 听觉驱动 `drv_mic`/`drv_ear`（ASR 三通道）/`drv_rec`（VAD 触发+6h 即焚）/`drv_audio`（FLASepformer+JAEC，需 .venv-audio）/`drv_npu`（QNN） | **◐ 部分**：VAD/ASR/refiner/回放/生活日志 ✅（实测）；**KWS 真音频触发 ○**；空间音频件为研究资产向组件 |
| **⑦ 可观测与协议** | 审计真源 + 埋点事件 + 语义剖析 + 派生视图（全部只读派生，原始记录永远权威） | `agentprof.py`（语义 span+OTLP 导出）、`telemetry.py`（23 事件注册表、脱敏四级、5s 节流、64MB 轮转、LAOS_REC=0 联动）、`traceviz.py`（audit→mermaid）、`ste.py`（ASD-STE100 五规则 check-only lint）、`profiling.py`（bpftrace，缺席降级） | `bin/laosweb.py`（986 行单文件：四 tab/审批卡/PWA/mobile-first）；`llm.py`+`asr.py`（OpenAI 兼容最小封装，纯 stdlib） | **✅ 完整**（v0.19.0 时 1.5/5 分的可观测性短板已补齐） |

**盘点结论**：七层中 ①②③④⑦ 完整，⑤⑥ 各有一个明确缺口（laos 侧 TTS 合成后端 / KWS 真音频触发）——两个缺口都不在内核语义层内部，而在驱动与外部能力面；这正是"内核语义层零依赖、重依赖只进驱动子进程"分层（ADR-1）的预期代价形态：缺口以"语义已备、引擎待接"的方式存在。

---

## §2 接口契约审计

> 契约实取自源码与测试。稳定性三档：**稳**（有测试钉住+文档化）/ **演化中**（已实现但预期会变）/ **未冻结**（无版本化承诺，下游引用需自担）。

### 2.1 syscall 面契约（laos/kernel.py）

| 契约 | 内容 | 稳定性 |
|---|---|---|
| 九级闸门链 | 0 进程存在 → 1 查表 → 2 能力检查（扣 TTL）→ 3 task_scope → 3b pkg 作用域 → 4 参数校验 → 5 syscall 预算（先于风险闸）→ 6 Sentinel → 7 不可逆闸（FleetLedger+risk_cap+Jev 预审+人类 confirm）→ 8 派发+审计+note_outcome | **稳**（test_laos 31 例覆盖；拒绝码 ESRCH/ENOSYS/EPERM/EACCES/EINVAL/EDQUOT/EDENIED 语义钉住） |
| 内建 syscall 面 | `msg.send/recv/list`、`sys.delegate`、`mem.remember/recall/forget/stats/curate/outcome`、`rec.replay`（跨驱动同步组装，to_thread 阻塞） | **稳**（mem.curate/outcome 为 v0.24.0 JitMem 新增，rec.replay 为 v0.36.0 新增，均有测试） |
| 驱动面 | 17 驱动：fs/proc/sys/npu/audio/ear/mic/rec/genie/screen/apps/notify/comms/battery/events/clef/evolve；`kernel.load_driver(name, argv, env)` 一行外挂任意 MCP 服务器 | **稳**（外挂默认低能力+低预算，审计正常再提权） |
| Sentinel 装配 | `AgentKernel(..., sentinel=None)` 缺省字节级不变；装后每条 syscall 落 `event:"sentinel"`；ask 走 confirm 回调；grants 命中 session/always 免问；污点 pid 出站恒问（仅 once 档） | **稳**（test_default_none_is_byte_compatible 钉死） |
| 审计事件流 | 追加式 JSONL，`(epoch, seq)` 复合键同点盖章；`rotate()` gzip 归档轮转；`mode='a'` 跨 boot 开机检测续代；diary 跨代按数字代序聚合 | **稳**（事件 schema 本体仍**未冻结**：行内字段无版本号，下游解析需"未知字段宽容"） |

### 2.2 三通道 ASR env 契约（drivers/drv_ear.py）——沿用 v0.19.0 口径，现状不变

| 契约 | 内容 | 稳定性 |
|---|---|---|
| `LAOS_ASR_CHANNEL` | `funasr`（默认，SenseVoiceSmall+fsmn-vad）/ `server`（HTTP）/ `whistle`（needle3 子进程）；未知值 EINVAL | **演化中** |
| 统一出口 | `ear.transcribe` → `{"text","language","emotions","source","latency_ms"}`；`ear.status` → 通道/模型/可达性/加载状态；重依赖全部惰性导入，裸解释器必须能 import 并回答 status | **稳** |
| `LAOS_EAR_PYTHON` | 听觉双驱动解释器；未设置自动探测 conda python，再退回主解释器（仅 server/status 可用） | **稳**（探测失败静默降级为已知风险，见 R11） |

### 2.3 Brain 决策契约（laos/brain.py——v0.39.0 新立）

| 契约 | 内容 | 稳定性 |
|---|---|---|
| `Brain.think(messages, tools, temperature=0)` | 三实现（Brain 抽象 / ScriptedBrain / OpenAIChatBrain）同签名；OpenAIChatBrain 把 temperature 透传进请求体（默认 0——首轮从"服务器默认 1.0"变为显式确定性） | **稳**（3+3 例测试钉住；全仓签名回归抓出过旧 test double） |
| `Thought.retryable` | 默认 False；tool_call 参数非法 JSON 时整轮作废返回 retryable=True 的 Thought（不执行半套调用、不抛异常、不吞成 finish） | **稳**（2 例测试） |
| Agent 侧重试策略 | 连续 retryable 轮依次以 0→0.4→0.8 调 think；超过 2 次仍不可用以 ok=False 中止；非 retryable 轮重置计数 | **稳**（3 例测试） |

### 2.4 laosweb HTTP 契约（bin/laosweb.py，常驻宿主）

| 端点 | 内容 | 稳定性 |
|---|---|---|
| `/api/state` | 全局状态投影（chat/audit/memory/gov 四视图数据源） | **演化中**（v2→v3 波次重写过投影键；前端 1s 轮询+tick 容错） |
| `/api/sentinel`（GET/POST） | GET 投影 sentinel 状态；POST 三动作 grant/revoke/set_mode；未知 action→400；未装配优雅降级 | **稳** |
| `/api/confirm` | 审批 POST 扩 {cid,approved,scope,tool}：approved 且 scope∈{session,always} 先落 grant 再放行 | **稳**（旧 id/allow 键回退无双破） |
| `/api/chat` `/api/voice` `/api/replay` | 对话 / 按住说话（音频只转写不落盘）/ 录音回放（含摘要开关） | **演化中**（三者为 v0.31.0–v0.38.0 渐次新增） |
| XSS 地基 | 动态内容全 createElement/textContent，全页无 innerHTML，静态断言钉死 | **稳** |

---

## §3 强项（带证据）

### 3.1 测试密度与增长曲线

- **1180 项实跑全绿**（2026-10-18，当日多次全套运行 255–291s 负载敏感；skipped=5；构成归属见页眉口径段）；另有隔离区 279 / 复现区 94 / 对照树 276，四树合计 1829 项。
- **增长曲线**（CHANGELOG 各版段实跑数）：501（v0.17.0）→ 573 → 634 → 691（v0.19.0）→ 697 → 753（v0.21.0 埋点核心）→ 766 → 840（v0.22.0 Clef）→ 861 → 884（v0.24.0 JitMem）→ 911 → 942 → 946 → 973（v0.28.0 Sentinel）→ 974 → 989（v0.29.0 laosweb v3）→ 1016（v0.30.0 ARVIS，**破千**）→ 1033 → 1037 → 1051（v0.33.0 语音桥）→ 1054（v0.35.1 锚点千位修复）→ 1146（v0.38.0）→ 1158（v0.39.0 发版时点）→ 1159（+1 dated 排除回归 d396f37）→ 1165（+6 锚点同步回归，Task #116 批次）→ **1180**（+15 综述校验器，当日并行 SDD 三提交，现行实跑）。另实测确认静态 1211 与实跑 1180 的 31 例差 = 4 个 pytest-only 模块盲区（R9；该 31 例 pytest 单独跑全过）。
- **结构前提**：全部时间语义经可注入时钟测试，无 sleep 依赖——测试秒级跑完。

### 3.2 零依赖纯度

`laos/` 51 个模块文件纯 stdlib（全量 import 核实）；重依赖（funasr/torch/soundfile/needle/numpy）只进驱动子进程且惰性导入，裸解释器必须能 import 并回答 status。laosweb v3 同样零 npm/构建链/CDN 外链（单文件内嵌原生前端）——"抄设计不抄栈"（nanoMuse GPL 红线纪律）。

### 3.3 治理红线的工程化落地（不是口号，是代码）

- `event:"mic"` 放行+被拒双路径写审计；`LAOS_REC=0` 返回 EACCES 且留痕、`f.rec.bypass` 哨兵事件永不静默；
- 审计 `seq` 单调盖章 + `(epoch, seq)` 复合键轮转安全 + `rotate()` 中途异常保底不断流；
- sentinel 放行后按 `assessment.reads_private` 统一置污，fail-closed（dispatch 失败也置污）；
- 记忆 provenance：用户行 `origin=="user"` 神圣——不参与去重与预算，人写一行胜模型任何行；
- telemetry 禁止级字段（明文文本/音频字节/唤醒词）拒发整条并落 `telemetry.reject`。

### 3.4 复现文化（Repro-ZCode：71→94 项）

论文不是引用，是复现：BS.1770-4 响度计量（R128 校准点 −23.00 LUFS ±0.1，已合入主库 `laos/loudness.py`）、FxLMS 主动降噪（>20dB）、ShoNet DOA 全管线（冒烟 holdout 56.5°）、PhaseCoder 麦位编码（与官方 JAX 源码逐行对齐，跨实现 diff 0.0）、Pipecat 帧管道、unique_lock 语义、AuraSE-IPO 规则版（+23 例）。方法论：论文数字不作断言，自己跑的才记；跑不动的等比缩距并写明偏差。

### 3.5 调研资产规模

- 双会议全量语料：Interspeech 5,507 + ICASSP 14,285 = **19,792 篇**（100% 全量）；OSS 普查 3,724 仓库（去噪后 core 132 / ref 2,864 / unrelated 728）；38 venue 扩展语料 120,234 行 + 934 行强命中工作集；
- 调研文档 **116 份**，capstone 采纳总账每条落「已落地/推荐/不做」三态记账。

### 3.6 来源诚实案例（项目气质样本）

- Jev 判断层：官方 README 宣称端侧 15.6ms，本地实测 median 157.5ms——**慢约 10×，README 数字被实测否证并写入文档**；rule 后端校准 accuracy 0.519、高置信桶错误率 33%——"越自信越离谱"如实记录，AUTOGATE 禁配 rule 后端；
- clef-flash 延迟：引用上游 38.8ms@edgeGPU 与本地 WSL 实测（noul 33.8s/choice 32.8s/score 62.9s）**分列不混写**；
- release.py 测试计数千位 bug（README 被写成 12 层 "1" 套娃）实录进 CHANGELOG 并以回归测试钉死。

---

## §4 风险与债务表（R1–R11 冻结编号状态更新 + R12–R16 新增）

> R1–R11 编号自 v0.19.0 技术评审冻结，不得复用；"状态"列为 2026-10-18 核对。新增条目顺延 R12+。与《需求评审 2026-10-18》§6 问题域（P01–P15）的关联在"影响面"列标注。

| 编号 | 风险 | 状态 | 证据指针 | 影响面 |
|---|---|---|---|---|
| **R1** | turnpolicy 与 GenerationGate 未组合 | **✅ 已关闭** | v0.26.0 dialogflow 管线装配 + v0.30.0 ARVIS 三件：DialogPipeline(turn_judge=) 接线，turnpolicy 15 例 + dialogflow 11 例 + e2e 组合面均落 | P05 |
| **R2** | KWS 未实测（模型+词表已拿到，驱动子进程模式未跑） | **开放** | docs/research/2026-10-06-voicenpu-adoption.md §六#1；test_wakegate 12 例全走注入 wake() | P01/P02 |
| **R3** | laos 侧 TTS 合成后端缺失 | **开放（部分缓解）** | 前端 speechSynthesis 朗读开关（v0.33.0，本地不出网）+ TtsRouter 降级语义已备；laos 侧合成仍未接 | S2 闭环/P07 |
| **R4** | AEC 未接入对话链路致半双工 | **开放** | dialogsched.py `post_tts_guard_ms=400.0`；drv_audio JAEC 组件级存在但独立于对话调度（ARVIS 报告 R5 参照留档） | P05 |
| **R5** | refiner 子句级替换局限 | **开放** | docs/research/2026-10-06-agenticasr-adoption.md（论文自认局限）；LLM 版 refiner 后置（无常驻 LLM 通道时不可用，现 llm.py 已备=前提渐熟） | P03 |
| **R6** | QNN 真机链路未复测（2026-09 曾闭环，此后无回归） | **开放** | drivers/drv_npu.py 路线 A 语义；test_npu_driver 10 例仅本地 HTTP 桩；docs/research/qnn-real-device-runbook.md | P08 |
| **R7** | 采集外源依赖（Anthology/Crossref 可用性） | **开放**（研究资产面，非运行时） | docs/research/2026-10-06-venue-expansion-survey.md 数据源结构性结论节；corpus 带源+时间戳版本化入档 | 语料增量 |
| **R8** | 三棵树同步漂移 | **✅ 已收口** | release.py --apply 硬闸（不绿拒绝发版）+ sync_docs 五类锚点 + **2026-10-18 dated 报告排除**（_DATED_REPORT_RE + 透明报告行 + 回归测试） | 全仓口径 |
| **R9** | 测试口径双轨（4 个 pytest 风格文件在 unittest 口径不可见） | **开放** | tests/test_locks.py(7)/test_loudness.py(10)/test_micgeom.py(6)/test_turnbuf.py(8) = 31 函数 pytest-only；只跑 unittest 的 CI 静默漏跑 | 测试资产错账 |
| **R10** | 长时运行无界增长（memory.jsonl 无 TTL/水位；无 RSS 采样） | **部分缓解** | telemetry 64MB 轮转+写前归档已封埋点侧；AuditLog rotate() + epoch/seq 续代已封审计侧；**memory.jsonl 与 RSS 采样仍未治理** | P10/P11 |
| **R11** | 听觉重依赖解释器探测链脆弱（conda 迁移即能力悄悄变窄） | **开放** | drv_ear.py LAOS_EAR_PYTHON 探测指引；探测失败静默降级 | P08 |
| **R12** | laosweb 前端契约随波漂移快（新增） | 管理项 | v2→v3 两次前迁实录：tick 容错（故障只吞一轮不杀轮询）、epoch\|seq\|t\|tool 复合键去重恢复；XSS 地基靠静态断言 | 面板可用性 |
| **R13** | PPT/deck 正文旧锚点待重建（新增） | 管理项 | 2026-10-18-ppt-audit.md §6：底稿三份已刷新，19 个 html deck 正文锚点（驱动数/天数叙述）待下次重建——按纪律不在 deck 上手改 | 介绍面口径 |
| **R14** | LocalBackend 与端侧判断层接口不匹配（新增） | 开放 | judge.py 四后端中 LocalBackend 走 OpenAI 兼容 HTTP chat completions；edgejev 是进程内 ONNX int8（358.9MB）直推接口——HTTP 解析路径拿不到 157.5ms，需新增 OnnxBackend 才真正端侧化 | 判断层端侧落点 |
| **R15** | zones/AlwaysOnRec-DB 树永久游离（新增） | 开放（设计上接受） | __version__ 0.1.0 不同步、整树 gitignore + 自带 .git——release.py 管不到，靠文档明示"不纳入三树口径" | 三树口径 |
| **R16** | 并发写入窗口期：介绍文档被外部浮写 + discover 收集数瞬时抖动（新增） | **部分缓解**（已回退，防再发机制缺位） | 2026-10-18 实录：17:55/18:00 两次写入把 README/ONBOARDING/PROJECT_OVERVIEW/19 处 deck 的测试锚点刷成动态收集数 1164→1165（介绍文件正确口径=发版时点 1158）；数值对账证实写入值随当时正落盘的 +6 回归测试同步增长。写入源未最终定位（本会话审计日志无对应命令，疑似并发 SDD 会话/外部工具在验证发版管线时对真实仓库执行了 sync）。同窗口 tests/ 非原子写入令 17:27 的 discover 瞬时漏收 6 例（实测 1159 vs 18:11 真值 1165）。已全部回退+门禁转绿；缺防再发：sync_docs 无"仅发版时点"守卫、discover 与并发写无互斥 | 介绍面口径/测试资产错账 |

**风险表小结**：R1/R8 已关闭，R10 部分缓解、R16 部分缓解（已回退待防再发），R2–R7/R9/R11/R14 开放，R12/R13/R15 为管理项。开放项与新增债务全部指向三个域：**驱动真机链路**（R2/R3/R4/R6）、**长时运行治理**（R10/R11）、**端侧判断层接口**（R14）——均不阻塞内核语义层的引用方使用，但决定"上线后运营"质量。

---

## §5 测试覆盖评估

### 5.1 主库逐模块测试数（2026-10-18 discover -v 实跑聚合）

| 模块 | 例数 | 模块 | 例数 |
|---|---|---|---|
| agent_reliability | 6 | journal | 7 |
| agentprof | 6 | judge | 17 |
| apps | 7 | knowledge | 11 |
| asr | 9 | laos | 31 |
| audio_driver | 5 | laosweb | 64 |
| battery | 5 | llm | 10 |
| binaural | 8 | mcp2 | 7 |
| brain | 6 | memory | 20 |
| calib | 29 | mood | 3 |
| calibrate_judge | 16 | multivenue | 30 |
| capability | 2 | notify | 4 |
| caps | 21 | npu_driver | 10 |
| check_survey | 15 | profiling | 5 |
| confgate | 12 | query_corpus | 20 |
| context | 2 | rec | 4 |
| cow | 5 | refiner | 21 |
| curate_strong_hits | 37 | relbudget | 5 |
| decide | 22 | release | 32 |
| dialog_e2e | 9 | replay | 17 |
| dialogflow | 24 | rhythm | 6 |
| dialogsched | 23 | ringbuf | 6 |
| diary | 11 | risk | 16 |
| drv_clef | 23 | sandbox | 3 |
| drv_evolve | 13 | scheduler | 3 |
| duplex | 11 | scope | 8 |
| ear_mic | 18 | screen | 18 |
| ear_refine | 4 | seccomp | 9 |
| ear_whistle | 10 | sentinel | 27 |
| enforcement | 6 | skills | 6 |
| events | 2 | soundscape | 7 |
| evolve | 32 | speechchunk | 17 |
| evroute | 16 | stale | 10 |
| fetch_anthology | 14 | ste | 17 |
| fetch_crossref | 25 | telemetry | 29 |
| filter_laos_relevant | 16 | telemetry_hooks | 32 |
| foa | 9 | traceviz | 10 |
| genie | 5 | turnpolicy | 25 |
| ipc | 13 | vad | 7 |
| irreversibility | 3 | vadmetrics | 12 |
| jev_gate | 5 | validate | 6 |
| jev_mem_ctx | 6 | venue_registry | 6 |
| jev_skills | 8 | wakegate | 18 |
| jitmem | 23 | wer | 22 |
| **合计** | **1180** | 零收集 pytest-only 4 模块 | **31**（R9） |
> 计数方法：`unittest` loader discover -v 展平按模块聚合（2026-10-18 18:45 实跑）。另有 4 个 pytest 风格文件（locks 7 / loudness 10 / micgeom 6 / turnbuf 8 = 31 函数）在本口径零收集（R9），静态 `def test_` 口径合计 1211。

### 5.2 四棵树口径（2026-10-18 实跑）

| 树 | 命令 | 结果 | 说明 |
|---|---|---|---|
| laos 主库 | `python -m unittest discover -s tests` | **Ran 1180 · OK (skipped=5)** | 正口径；与 ONBOARDING 门禁实跑对账一致（README/decks 为发版时点口径 1158/1159，两档差 +22 项未发版回归） |
| AlwaysOnRec-ZCode（隔离区） | 同左（zones/AlwaysOnRec-ZCode） | **Ran 279 · OK (skipped=8)** | 前沿增量独立可跑 |
| Repro-ZCode（复现区） | `python -m pytest`（collect 94） | 94 例收集 | 论文复现，pytest-only |
| AlwaysOnRec-Trae（对照树） | 同左 | **Ran 276 · OK (skipped=8)** | 同负载在另一 IDE 的对照实现 |
| AlwaysOnRec-DB（沙箱） | 不跑 | — | **永久游离**：__version__ 0.1.0、整树 gitignore，不纳入口径（R15） |

### 5.3 盲区清单（按"测不到的路径"归类）

| 盲区 | 现状 | 关联 |
|---|---|---|
| **drivers 真机链路** | KWS 音频触发未跑（R2）；QNN 真机设备位只有本地 HTTP 桩（R6）；ALSA/USB 自愈语义仅入档未实现；drv_audio 分离/AEC 无对话链路级用例（R4） | P01/P08/P09 |
| **并发路径** | dialogsched/wakegate 是可注入时钟的单线程决策核（设计选择）——调用方并发驱动决策核的竞态无测试；多 Agent 并发 syscall 派发靠 asyncio.Lock，压力路径无测试 | P10/P15 |
| **长时运行** | 无 soak/耐久测试：memory.jsonl 增长、AuditLog.records 全量驻留内存、时钟漂移对窗口判定的影响——全部零覆盖；laos 常驻内存未实测 | P10/P11 |
| **跨模块组合** | turnpolicy×GenerationGate 已组合（R1 关闭）；refiner×whistle 组合（whistle 无中文）仍未测；TTSRouter×前端 speechSynthesis 无组合用例 | P03/P07 |
| **测试口径双轨** | 31 个 pytest 函数在 unittest 口径不可见（R9） | R9 |

### 5.4 覆盖评估结论

主库覆盖呈"**内核与治理语义密、驱动真机与运行时稀**"的形态——与分层设计一致（语义层零依赖可测、重依赖在驱动子进程难测）。对照 v0.19.0 评审：盲区清单条目数未减（真机链路一类未动），但**可观测性维度的盲区已被 telemetry 23 事件部分照亮**——每个盲区现在至少有事件观测位，缺的是真机与长时运行的真实数据。

---

## §6 性能数据汇总

### 6.1 已实测数字（全部可溯源）

| 维度 | 数字 | 来源 |
|---|---|---|
| ASR funasr 精度 | en WER 2.7% / zh CER 0.0%（zh 主力） | 事实基线（计划文档）+ 耳-记忆波次实测 |
| ASR whistle 精度/流式 | en WER 10.8%；ttft 651ms，~300 tok/s；模型 16.9MB+引擎 1.56MB | docs/research/2026-10-06-cactus-whistle-adoption.md |
| Refiner 精度 | AASR-Bench 917 例错误率 0.4571→0.3875（-15.2%）；e2e CER 1.563→0.042 | docs/research/2026-10-06-agenticasr-adoption.md |
| 判断层 edgejev | 端侧 median **157.5ms**；峰值 RSS 494.8MB；模型 358.9MB；首载 2144ms | scripts/bench_jev_local.py 实测（否证 README 15.6ms 宣称） |
| 判断层 clef-flash | WSL x86 实测：noul 33.8s / choice 32.8s / score 62.9s（18.1GB 权重 CPU 推理）；上游引用 38.8ms@edgeGPU 分列 | v0.22.0 CHANGELOG 段（三判型×20 全量） |
| 语音增强 GPU | FLASepformer RTX 4060 CPU vs GPU 6.4x→9.3x（30s 音频 1.99s） | scripts/flasep_gpu_bench.py |
| 测试吞吐 | 主库全套 1180 例（discover 实跑 OK skipped=5，2026-10-18 当日多次 255–291s） | 本评审 §5 实跑 |
| 上游对照锚点（非 laos 数字） | voicenpu RK3576：端到端首音 1.44s / 常驻 1951MB / ASR 端点→终稿 ~88ms | docs/research/2026-10-06-voicenpu-adoption.md §二 |

### 6.2 未实测维度清单（如实声明，禁止引用宣称值充数）

- 端到端首音（对照上游 1.44s）——laos 侧全线未实测；
- ASR 端点→终稿延迟（对照上游 ~88ms）；funasr 通道 ttft（非流式）；
- KWS 唤醒触发延迟与漏/误唤醒率（R2：链路本身未跑）；
- refiner 修正延迟；知识库检索 retrieval_ms；LLM 首 token（llm.py 非流式）；
- TTS 首音（laos 侧能力面缺失 R3）；
- laos 进程常驻内存（对照上游 1951MB）；长时运行 RSS 曲线（R10）；
- laos 侧功耗（仅有业界阶梯定性结论：通用 Linux 设备空闲即 400–1000 mW）。

**结论**：实测集中在**精度与离线基准**，在线分段延迟与资源占用几乎全空——每一行对应一个待埋点/待运行积累的字段族。这是 v0.21.0 telemetry 设计的直接动因，也是"上线后数据自然产生"的期待项。

---

## §7 技术决策记录（ADR ×8）

**ADR-1 零依赖：laos/ 核心纯 stdlib**（v0.19.0 沿用，有效）
- 决策/动因/代价见前版；状态：AGENTS.md 红线级纪律，零 npm 前端（v0.29.0）是同纪律的延伸。

**ADR-2 规则版 refiner 先行**（沿用，有效）
- 子句级替换型，AASR-Bench 917 例可量化（-15.2%）；LLM 版后置——llm.py 落地后前提渐熟，但规则版的可解释性仍是保留理由。

**ADR-3 语义复现不拷贝**（沿用，有效）
- AGPL/GPL 上游（voicenpu/nanoMuse）一律"读源码理解语义后纯 Python 重写"；已扩展为对全部外部来源的默认纪律（jev/ARVIS/esp-claw 等波次沿用）。

**ADR-4 三通道 ASR**（沿用，有效）
- funasr/server/whistle 三通道 + 统一 JSON 出口；footprint 梯度保证单一环境故障不打死三条通道。

**ADR-5 KWS 延后**（沿用，有效但已到期未兑现）
- v0.17.0 只复现 WakeGate 语义；KWS 引擎延后驱动波次——**Should 项 S1 已挂到 v0.39.0 仍未兑现，是路线图上最老的逾期项**（见《路线评审 2026-10-18》§6）。

**ADR-6 Sentinel opt-in 装配**（v0.28.0 新立，有效）
- 决策：`sentinel=None` 缺省字节级不变，治理增强全部 opt-in。
- 动因：①治理内核自身不能变成强制依赖——引用方最小面集成；②与 telemetry 钩子（默认 None 零行为变化）同一哲学；③测试可分离（默认面与装配面各自钉住）。
- 代价：两套行为面（装/不装）都要维护文档与测试；装配面的组合语义（grants×taint×mode）是组合爆炸区——目前靠六级有序判定 + 测试枚举控制。

**ADR-7 laosweb 纯 stdlib 单文件前端**（v0.29.0 新立，有效）
- 决策：常驻宿主 = http.server + 单文件内嵌 HTML/CSS/JS；零 npm/构建链/CDN 外链。
- 动因：①零依赖红线的延伸——治理内核的UI面同样不引入供应链；②nanoMuse 设计可借鉴而 GPL 技术栈不抄（抄设计语言不抄 React）；③单文件可审计（XSS 静态断言可写）。
- 代价：手写 DOM 契约，波次间前端契约漂移需前迁管理（R12）；功能密度受限（复杂图表类视图走 laosctl/traceviz 派生）。

**ADR-8 release.py 硬闸 + 锚点同步 + dated 排除**（2026-10-18 新立，有效）
- 决策：发版 = conventional commits 推导 semver → --apply 真跑测试绿闸 → 三树 __version__ 同步 → sync_docs 改写五类锚点（含"项测试全绿"/递归 glob/ISO 日期文件名排除）。
- 动因：①文档宣称与实际行为不符会放大一切问题报告的不可信（R8 教训）；②腐化要会失败——锚点由工具同步而非人记；③dated 现场记录（审计/取证）是历史快照，不随后续发版漂移（PPT 审计报告被误刷的教训）。
- 代价：每条新锚点形态都是同步面欠账（"项测试全绿"盲区从 10-10 挂到 10-18 才结构性关闭）；读文档的人需要理解"实跑值 vs 发版时点值"两档口径。

---

## §8 评审结论（分维度就绪度）

> 就绪度评分（5 分制，判据=语义完备度×测试证据×实测覆盖×线上观测面四要素）；与《需求评审 2026-10-18》§5 Go/No-Go 交叉一致。括号内为 v0.19.0 时点评分。

| 维度 | 评分 | 判据摘要 |
|---|---|---|
| **内核治理层** | **4.5 / 5**（4.0） | 九级闸门 + Sentinel 六级 + grants + taint + caps + 不可逆账本齐备，1180 项中治理语义测试密；扣分：审计事件 schema 未冻结、memory.jsonl 无界增长（R10） |
| **对话控制面** | **4.0 / 5**（4.0） | 五件+ARVIS 三件+LLM 通道全落地（turnpolicy 已组合，R1 关闭）；扣分：laos 侧 TTS 合成 ○（R3）、无真音频端到端 |
| **听觉栈** | **3.5 / 5**（3.5） | 三通道+VAD+refiner+回放+生活日志均实测；扣分：KWS 未实测（R2）、AEC 未接对话链路（R4）、refiner 覆盖面窄（R5） |
| **可观测性** | **3.5 / 5**（**1.5**） | telemetry 23 事件 + 面板 + traceviz + OTLP span 落地（v0.21.0–v0.29.0 补齐 v0.19.0 时的唯一系统性 NO-GO）；扣分：无 RSS 采样、无真实运行数据、overrun 类事件缺位 |
| **工程纪律面** | **4.5 / 5**（新设维度） | TDD+每任务一 commit+43 tag 全归档+发版硬闸+交接门禁实跑对账+dated 排除；扣分：测试口径双轨未决（R9）、deck 正文锚点待重建（R13） |

**结论**：

1. **治理内核形态技术面就绪**：①②③④⑦ 层完整，1180 项测试+四树 1829 项资产，"语义已备、引擎待接"的缺口全部在驱动与外部能力面（R2/R3/R4/R6），不阻塞引用方集成。
2. **对照 v0.19.0 评审的结构性变化**：可观测性 1.5→3.5（telemetry 落地）、R1 关闭（turnpolicy 组合）、R8 收口（发版硬闸+dated 排除）——剩余开放风险与新增债务（R2–R7/R9/R11/R14/R16）集中于四个域：**驱动真机链路、长时运行治理、端侧判断层接口、并发写入纪律**。
3. **给下一波的四个工程动作项**（不阻塞当前引用方使用）：R9 测试口径统一（31 例并入 unittest 口径或显式声明双 runner）、R14 OnnxBackend（端侧判断层真落地）、R2 KWS 驱动子进程实测（最老逾期 Should 项）、R16 防再发（sync_docs 增加版时点守卫 + 发版同步仅在 --apply 发版主流程可达）。

---

### 附：本文引用来源

- 前版评审（编号冻结源）：docs/review/2026-10-07-technical-review.md（R1–R11 冻结、ADR-1..5、契约审计口径）
- 2026-10-18 实跑记录：主库 discover "Ran 1180 tests · OK (skipped=5)"（当日多次 255–291s）；`ls laos/*.py`（51 文件）与 `ls drivers/drv_*`（17 驱动）机械计数；ZCode 279 / Trae 276（discover）/ Repro-ZCode 94（pytest collect）
- CHANGELOG.md v0.19.0–v0.39.0 各版段（能力落地、测试增量、实施裁决实录）
- docs/design/2026-10-08-architecture-current-state.md（架构现状快照）+ 本次源码实取（kernel.py 内建 11 条、laosweb 端点、telemetry 23 事件）
- docs/research/2026-10-06-voicenpu-adoption.md（上游对照锚点）；docs/research/2026-10-07-cloudflare-clef.md + jev/06-clef-mapping.md（clef 实测）；docs/research/2026-10-08-arvis.md §7 裁决（ARVIS 三件）
- docs/ppt/2026-10-18-ppt-audit.md（介绍面锚点审计）；AGENTS.md（发版/零依赖/conda/测试口径纪律）
- README.md / docs/PROJECT_OVERVIEW.md / docs/ONBOARDING.md（数据面板、交接门禁）
