# laos 需求评审（2026-10-18）

> **评审对象**：laos / nanoLAOS v0.39.0
> **本文回答**：为谁做、做什么、不做什么、怎样算做到。
> **编号约定**：需求 `R-01…R-18`、门槛 `G1–G9`、开放问题 `Q-01…Q-08`；编号冻结，新增顺延。
> **数字口径**：与 [00-review-pack.md](00-review-pack.md) §4 一致；测试数取实跑 `Ran N tests`，性能未实测处一律写「未实测」。

---

## 1. 评审结论摘要

| 维度 | 结论 |
|---|---|
| 定位 | 成立：Linux 内核是基座，Agent 是新负载，laos 是内核治理在用户态的延伸 |
| 第一场景 | **开发者自部署的个人常驻 Agent 平台**（桌面/服务器），不是面向消费者的语音助手 |
| 需求覆盖 | Must 10 项全部达标；Should 6 项中 2 项达标、2 项部分、2 项未开始 |
| 最大缺口 | 语音问答完整体验（KWS 未真机实测、TTS 无服务端合成）与移动端常驻（真机功耗未验收） |
| 建议决议 | **有条件通过**：Must 范围通过；Should 按 §6 的 Q-03/Q-04 冻结是否进入本期承诺 |

---

## 2. 定位与边界

### 2.1 一句话定位

> **Linux AgentOS = Linux kernel + Agent + MCP**：不改内核，用 Linux 已有的强制原语（namespace / cgroup / seccomp / landlock）做强制层，用用户态薄内核 `laos` 做语义层，用 MCP Server 做设备驱动，用 MCP tool call 做系统调用。

### 2.2 三类目标形态

| # | 形态 | 内容 | 服务对象 | 本期承诺 |
|---|---|---|---|---|
| 1 | **个人常驻 Agent 平台** | 对话面 + 记忆 + 工具调用 + 审批 + 审计 + 听觉日志 | 开发者本人 | ✅ 承诺 |
| 2 | **Agent 治理语义层** | 能力表 / 意图作用域 / 风险账本 / 分支 / IPC / 审计，可被第三方内嵌 | 引用 laos 内核库的开发者 | ✅ 承诺（0.x API） |
| 3 | **听觉研究平台** | 四段漏斗 + 三通道 ASR + 语料/评测资产 | 语音与语料研究者 | ✅ 承诺（桌面形态） |

### 2.3 明确不做（见 §5 Won't）

- 不提供托管 SaaS、无 SLA、无多租户；
- 不做云端默认上传，ASR 全本地是红线；
- 不修改 Linux 内核；
- 不做跨会话声纹库（说话人分离只在本会话内标注）；
- 不把生成式修复结果写进记忆链路（声学修复只用于回放/听清，不改写事实记忆）。

---

## 3. 用户画像与核心场景

### 3.1 用户画像

| 画像 | 描述 | 最在意 |
|---|---|---|
| **P1 自部署开发者** | 在自己的桌面/服务器上跑 laos 并日常使用 | 装得上、跑得稳、出事能查 |
| **P2 Agent 治理研究者** | 引用能力表/审计/预算/分支语义做多 Agent 实验 | 语义可组合、接口稳定、可复现 |
| **P3 语音/语料研究者** | 消费听觉漏斗、ASR 评测与语料资产 | 精度、隐私、可追溯 |
| **P4 交接/评审者** | 接手项目、做需求/技术/路线评审 | 文档一致、数字有证据、边界清楚 |

### 3.2 核心场景与完成度

| 场景 | 用户动作 → 系统行为 | 完成度 | 说明 |
|---|---|---|---|
| **S1 个人 Agent 对话** | 在 laosweb 输入问题 → agent 调工具/记忆 → 高危操作弹审批 → 全程审计 | ✅ | 对话面、记忆闭环、审批、审计已闭环；LLM 需 opt-in 配置 |
| **S2 常驻录音日记** | 显式触发录音 → VAD 门控 → 捕获有声段 → 本地 ASR → 入记忆 → 原音频 TTL 即焚 | ✅ | 四段漏斗全落地；默认 6 小时即焚 |
| **S3 语音交互** | 按住说话 → ASR → 对话 → 朗读；回放最近 15–60 秒 | ◐ | 按住说话/朗读/回放已落地；唤醒词真机链路未验收，服务端 TTS 缺失 |
| **S4 Agent 治理实验** | 起多 agent → 能力/预算/分支/IPC → laosctl 回放 | ✅ | 审计 + trace + budget + spans 全可用 |
| **S5 二次开发** | 写新驱动 → 注册 syscall → 内嵌内核 | ✅ | 17 个驱动即模板；驱动为独立子进程 |
| **S6 长时无人值守** | 7×24 常驻，慢泄漏/慢劣化可发现 | ◐ | 埋点与审计已就位；缺 7 天 soak 验收与告警面 |

---

## 4. 功能需求（MoSCoW）

### 4.1 Must（本期必须成立）

| ID | 需求 | 验收标准 | 现状 | 证据 |
|---|---|---|---|---|
| **R-01** | 能力表与意图作用域 | 未授权 syscall 返回 `EPERM`；路径越界返回 `EACCES: outside task scope`；`pkg:` 白名单管住 screen/apps | ✅ | [kernel.py](../../../laos/kernel.py) `syscall()` 能力/作用域段；`tests/test_caps.py`、`test_scope.py` |
| **R-02** | syscall 闸门链与 errno 审计 | 每次调用（含被拒）一条审计，errno 原样透传，不被包成 EIO | ✅ | `_deny()` 写 `event:"syscall"`；`tests/test_laos.py`、`test_capability.py` |
| **R-03** | MCP 驱动总线 | 驱动为独立子进程；工具 schema 由内核校验；17 个驱动可加载 | ✅ | `laos/mcp.py`、`drivers/drv_*.py`（17 个）；`tests/test_mcp2.py`、`test_validate.py` |
| **R-04** | 风险账本与预算调度 | 不可逆操作按工具定价；agent 帽 + 车队账本；预算耗尽挂起而非崩溃 | ✅ | `laos/risk.py`、`laos/scheduler.py`；`tests/test_irreversibility.py`、`test_scheduler.py`、`test_relbudget.py` |
| **R-05** | 分支与写时复制 | fork 零拷贝；commit 先到先得；abort 不污染主线 | ✅ | `laos/branch.py`、`laos/cow.py`；`tests/test_cow.py`、`test_laos.py` |
| **R-06** | 记忆与技能 | `mem.*` 可增删查；技能从成功任务沉淀并注入提示 | ✅ | `laos/memory.py`、`laos/skills.py`；`tests/test_memory.py`、`test_skills.py` |
| **R-07** | 控制面 | `laosctl ps/top/trace/denied/budget/spans` 可回放；laosweb 可实时看板与操控 | ✅ | `bin/laosctl.py`、`bin/laosweb.py`；`tests/test_laosweb.py` |
| **R-08** | 平台降级 | Windows/macOS 无 namespace/cgroup 时仍可跑能力表与审计 | ✅ | `laos/enforcement/stub.py`；`tests/test_enforcement.py`、`test_sandbox.py` |
| **R-09** | 隐私四件套 | 显式 syscall 才录音；`LAOS_REC=0` 返回 `EACCES`；ASR 本地；成功与被拒都写 `event:"mic"`；原音频 TTL 即焚 | ✅ | [kernel.py](../../../laos/kernel.py) `_deny()` 的 mic 补账；`tests/test_rec.py`、`test_replay.py`、`test_telemetry.py` |
| **R-10** | 可观测性 | 审计为追加式 JSONL；23 类埋点事件带字段级脱敏；禁止字段永不出现在事件里 | ✅ | `laos/telemetry.py`（23 事件 / 138 字段）；`tests/test_telemetry.py`、`test_telemetry_hooks.py` |

### 4.2 Should（本期应补，未达不阻塞 Must 范围）

| ID | 需求 | 验收标准 | 现状 | 证据/缺口 |
|---|---|---|---|---|
| **R-11** | 个人对话面 | 未配置 LLM 时降级为模板回复；配置后可多轮；用户话轮入记忆并在下一轮召回 | ✅ | `laos/llm.py`、`bin/laosweb.py`；`tests/test_llm.py`、`test_laosweb.py`；LLM 全 opt-in |
| **R-12** | 四段漏斗与回放 | 静音不落盘；有声段可转写；最近 N 秒可回放；回放转写不进审计 | ✅ | `laos/vad.py`、`laos/ringbuf.py`、`rec.replay`；`tests/test_vad.py`、`test_ringbuf.py`、`test_replay.py` |
| **R-13** | 唤醒会话与打断 | 四态唤醒机全迁移可测；文本永不唤醒；打断用 generation 代数，过期回答不播 | ◐ | 模块级通过（`wakegate.py` / `dialogsched.py`）；**KWS 真机触发未实测**，与 turnpolicy 未组合 |
| **R-14** | 说话人分离 | 本会话内区分 S1/S2；不建跨会话声纹库；默认关闭或明确 opt-in | ○ | 计划 `2026-10-12-auditory-governance-wave.md` Task A（纯 stdlib 到达顺序聚类）+ A4 驱动侧可选后端 |
| **R-15** | TTS 完整体验 | 对话回答可朗读；失败可降级；音频不出本机（或显式 opt-in 云端） | ◐ | 浏览器 `speechSynthesis` 已有；无服务端合成后端，`drv_comms` TTS 通道未做端到端验收 |
| **R-16** | 移动端常驻 | 前台服务 + 用户可见开关 + 真机功耗验收（目标 <25 mW 量级） | ○ | Android 壳为 WebView 薄壳；ADSP/LPAI 路线在调研中，未进主线计划 |

### 4.3 Could（增强项，不承诺本期）

| ID | 需求 | 说明 |
|---|---|---|
| **R-17** | 屏幕语义漏斗 | 界面签名去文本/去 id，XML 字节零落盘；计划 `2026-10-12-audiovisual-innovation.md` Wave 1 |
| **R-18** | 架构级隔离增强 | FUSE BranchFS（真 O(1) 分支）、gVisor 第四后端；属 3–5 年方向 |

### 4.4 Won't（明确不做）

| ID | 不做 | 理由 |
|---|---|---|
| **W-01** | 云端默认上传 | 隐私红线；任何上云只能显式 opt-in |
| **W-02** | 多租户 / SaaS | 无托管承诺，治理模型面向单机/单用户 |
| **W-03** | 修改 Linux 内核 | 定位红线；强制力复用既有内核原语 |
| **W-04** | 跨会话声纹库 | 生物特征长期留存与隐私红线冲突 |
| **W-05** | 生成式修复写入记忆 | 修复文本是衍生内容，不得改写事实记忆；只服务回放/听清 |

---

## 5. 非功能需求

| ID | 维度 | 要求 | 现状 | 证据 |
|---|---|---|---|---|
| **NFR-01** | 依赖 | `laos/` 核心纯标准库；重依赖只进驱动子进程 | ✅ | 0 第三方依赖；`.venv-audio` 门控 `drv_audio` |
| **NFR-02** | 可移植 | Python 3.10+；Linux 全隔离，Windows/macOS 自动降级 | ✅ | `enforcement/` 三后端；CI 与本地 Windows 实测 |
| **NFR-03** | 隐私 | 录音显式触发、全局禁录、本地 ASR、原音频 TTL、审计脱敏 | ✅ | `tests/test_rec.py`、`test_replay.py`、`test_telemetry.py` |
| **NFR-04** | 延迟 | 关键链路有分段实测；端到端可归因 | ◐ | 片段实测：whistle ttft 651ms、edgejev median 157.5ms；**端到端首音未实测** |
| **NFR-05** | 功耗 | 桌面常开为研究形态；移动常开需原生 App + ADSP | ◐ | 桌面空闲 400–1000 mW 量级（调研口径）；移动目标 <25 mW 未验收 |
| **NFR-06** | 长时稳定 | 7×24 运行无慢泄漏；崩溃后可恢复 | ○ | 无 7 天 soak；`AuditLog.rotate()` 与 evolve 后台任务 GC 在待办中 |
| **NFR-07** | 可观测 | 每步可追、每类降级有事件、红线路径有自证 | ✅ | 审计 + 23 事件埋点；缺长跑告警面 |
| **NFR-08** | 兼容契约 | 0.x 阶段 minor 可加能力、breaking 需在 CHANGELOG 明示 | ✅ | CHANGELOG + SemVer 纪律；`LAOS_*` 环境变量为公开契约 |

---

## 6. 开放问题（评审现场需冻结）

| ID | 问题 | 选项 | 建议 |
|---|---|---|---|
| **Q-01** | 本期对外承诺的形态？ | A 桌面研究平台；B 含语音问答完整体验；C 移动常驻 | **A**。B/C 依赖未验收的 KWS/TTS/真机功耗 |
| **Q-02** | 主库测试口径冲突（1158 vs 1159）如何处理？ | A 以实跑为准并同步全介绍面；B 保留 README 口径 | **已闭合（当日两次收敛）**：先实跑 **1159** 确认 CHANGELOG v0.39.0 的 1158 少计 1（README 正确）；同日后 22 项未发版回归落盘后实跑 **1180**（OK skipped=5，构成见 00-pack §4），确立「介绍面发版时点口径 1158 / ONBOARDING 门禁实跑口径 1180」两档口径，差 +22 待下次发版统一刷新 |
| **Q-03** | 说话人分离是否本期进入主线？ | A 不进入；B 只做纯 stdlib 会话内聚类；C 接模型后端 | **B**（默认关闭，不建声纹库）；C 仅作驱动侧 opt-in |
| **Q-04** | KWS 与 TTS 是否本期承诺？ | A 都不承诺；B 只承诺 TTS 降级朗读；C 两者都承诺 | **A**；B 已有浏览器朗读，不构成服务端能力承诺 |
| **Q-05** | 屏幕语义的隐私边界？ | A 不采集；B 只存界面签名（去文本/id）；C 存截图 | **B**，且明确 XML 字节零落盘；C 否决 |
| **Q-06** | 模型体量红线是否沿用 ~50MB？ | A 沿用；B 放宽到 200MB；C 不设限 | **A**（常驻链路）；离线后处理可另档 |
| **Q-07** | 0.x API 是否给第三方稳定承诺？ | A 不给，仅文档化；B 冻结内核公开类；C 冻结全部驱动工具名 | **B**：`AgentKernel`/`PCB`/`CapabilitySet`/`ToolSpec` 冻结；驱动工具名标注 experimental |
| **Q-08** | 长跑验收谁负责、何时做？ | A 本波；B 下一波；C 真机波一起 | **B**：下一波做 7 天 soak（桌面），指标含 RSS/审计体积/句柄数/失败率 |

---

## 7. Go/No-Go 门槛

| # | 门槛 | 现状态 | 判定 | 差距 |
|---|---|---|---|---|
| **G1** | 主库测试全绿 | 评审当日实跑 **1180**，OK（skipped=5） | GO | CHANGELOG v0.39.0 的 1158 少计 1（文档勘误，历史记录）；+22 未发版回归待发版刷新（见 Q-02） |
| **G2** | 零依赖承诺 | `laos/` 纯 stdlib；重依赖只在驱动子进程 | GO | — |
| **G3** | 三通道 ASR | funasr / whistle / server 均有实现与测试 | GO | whistle 精度低于 funasr，定位为轻量备 |
| **G4** | 唤醒与打断语义 | WakeGate 四态 + dialogsched generation 语义有测试 | GO（模块级） | KWS 真机触发未验收（Q-04） |
| **G5** | 隐私红线 | 四件套逐条有测试；被拒路径也审计 | GO | — |
| **G6** | 语音问答完整体验 | 按住说话 → 对话 → 朗读可用；唤醒词与服务端 TTS 缺失 | **NO-GO**（仅对该完整体验） | 按降级形态上线（文字 + 浏览器朗读） |
| **G7** | 可观测性 | 审计 + 23 类埋点事件 + 字段级脱敏 | GO | 长跑告警面未验收（Q-08） |
| **G8** | 移动端常驻 | Android 壳可连接；无前台常驻服务与功耗验收 | **NO-GO**（移动常驻形态） | 定位为桌面研究平台（Q-01） |
| **G9** | 发版与文档 | `release.py --apply` 真跑门禁 + 锚点同步 + 发版归档 | GO | 测试数口径需一次全量同步 |

**综合判定**：以**桌面个人常驻 Agent 平台**形态，Must 10 项全部 GO；Should 中的语音完整体验与移动常驻不进入本期承诺。评审建议为**有条件通过**，条件即 Q-01/Q-03/Q-04 的冻结与记录（Q-02 已由实跑闭合）。

---

## 8. 评审清单

- [ ] 确认第一场景 = 桌面/服务器自部署（Q-01）
- [x] 主库测试口径已闭合：实跑 1180（OK skipped=5），两档口径确立（Q-02）；CHANGELOG 的 1158 为发版时点正确值 |
- [ ] 确认说话人分离本期范围（Q-03）
- [ ] 确认 KWS/TTS 不作为本期承诺（Q-04）
- [ ] 确认屏幕语义隐私边界（Q-05）
- [ ] 确认常驻模型体量红线（Q-06）
- [ ] 确认 0.x API 冻结面（Q-07）
- [ ] 指定长跑验收责任人与时间盒（Q-08）
- [ ] 逐条确认 Must 10 项验收证据可复现
- [ ] 记录本场结论：通过 / 有条件通过 / 不通过

---

## 9. 本场结论（现场填写）

| 项 | 内容 |
|---|---|
| 结论 | 待填 |
| 阻塞项（现象 + 证据 + 验收标准 + 责任人 + 时间盒） | 待填 |
| 条件项 | 待填 |
| 下次复核时间 | 待填 |

---

## 附：主库测试实跑记录

- 命令：`C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests`
- 结果：**Ran 1180 tests — OK (skipped=5)**（同日多轮 255–291s，负载敏感）
- 口径：只认 `Ran N tests`，不认静态 `def test_` 计数；实跑 1180 = 全量 discover，31 个 pytest-only 盲区另由 pytest 单独验证
- 勘误沿革：CHANGELOG v0.39.0 写「1146 → 1158」为该版发版时点实跑值（正确）；其后 +22 未发版回归致门禁实跑 1180，README 等介绍文件保持 1158 至下次发版由 release.py 统一刷新
