# laos 技术评审（2026-10-18）

> **评审对象**：laos / nanoLAOS v0.39.0
> **本文回答**：架构是否成立、关键机制是否正确、风险在哪里、证据够不够。
> **编号约定**：接口契约 `C-01…C-08`、威胁 `T-01…T-12`、技术风险/债务 `R-01…R-10`、架构决策 `ADR-01…ADR-06`；编号冻结。
> **数字口径**：与 [00-review-pack.md](00-review-pack.md) §4 一致；未实测数字一律写「未实测」。

---

## 1. 评审结论摘要

| 维度 | 结论 |
|---|---|
| 架构 | 成立：语义层与强制层职责清晰，Agent 是受治理的负载而非特权主体 |
| 闸门链 | 正确：能力 → 作用域 → 校验 → 预算 → Sentinel → 不可逆账本 → 派发 → 审计，被拒路径也留痕 |
| 关键机制 | 分支/COW、上下文失效、风险账本、IPC/委托、可靠性重试均有测试与明确不变量 |
| 最大技术风险 | 端到端延迟与 7×24 长跑**无实测**；审计无防篡改链；隐私闸门依赖实现纪律 |
| 建议决议 | **有条件通过**：Must 架构面通过；R-01/R-02 作为上线运营的阻塞条件，其余为跟踪债务 |

---

## 2. 架构与职责边界

```
L5 入口层      bin/laosd · bin/laosweb · bin/laosctl · bin/journal · clients/android
L4 运行时      Agent · Brain · ContextManager · SkillStore
L3 语义内核    AgentKernel · BranchContext · MemoryStore · FleetLedger · Scheduler
               Sentinel · Telemetry · AgentProf · 内建 syscall（msg.*/mem.*/rec.replay）
L2 驱动总线    MCPClient/MCPServer（JSON-RPC over stdio） · 17 个 drivers/ · Sandbox/PathJail
L1 强制层      enforcement/linux · seccomp BPF · cgroup v2 · namespace · CoW 写入原语
L0 基座        Linux kernel（调度 / 内存 / 权限 / 文件系统）
```

| 层 | 只做什么 | 明确不做什么 |
|---|---|---|
| L5 | 人机入口与展示 | 不做权限判断，不直接调用驱动 |
| L4 | ReAct、上下文、技能 | 不绕过 `kernel.syscall` 产生副作用 |
| L3 | 裁决、记账、审计、路由 | 不执行具体 I/O |
| L2 | 把设备能力封装成工具 | 不信任调用方，不自行扩权 |
| L1 | 用内核原语兜底强制 | 不解释业务语义 |
| L0 | 调度/内存/权限强制 | 不感知 Agent 语义（laos 不改内核） |

**核心不变量**：Agent 的唯一副作用出口是 `kernel.syscall`；驱动的可见工具表由内核按能力裁剪；被拒调用与成功调用同样进入审计。

---

## 3. syscall 闸门链

实现位置：[kernel.py](../../../laos/kernel.py) `AgentKernel.syscall()`（约 557–800 行）。

| 序 | 闸门 | 失败返回 | 关键实现点 |
|---|---|---|---|
| 1 | 进程存在/状态 | `ESRCH` / `EACCES` | killed 进程不可再调用 |
| 2 | 查表 | `ENOSYS` | 先 MCP 驱动表，再内建表 |
| 3 | 能力（含委托） | `EPERM` | `_effective_allows(consume=True)` 扣减委托 TTL |
| 4 | 意图作用域 | `EACCES: outside task scope` | `normpath` 归一化 + 分隔符收边，防 `..` 与 `/host` 前缀混淆 |
| 5 | 应用作用域 | `EACCES: outside task scope` | `pkg:` 白名单按包名前缀收边（`pkg` 或 `pkg.`） |
| 6 | 参数 schema | 校验错误原文 | 内核派发前强制，堵 Tool Manager 无校验洞 |
| 7 | syscall 预算 | `EDQUOT` | 先于风险闸门，避免注定被拒的调用消耗风险预算 |
| 8 | Sentinel 动作闸 | `EDENIED` / 需确认 | 六级判定；`ask` 先查 scoped grants；读隐私源即置污，污点不因后续动作洗白 |
| 9 | 不可逆账本 | `EACCES` / `EDENIED` | 车队剩余 → agent 帽 → Jev 预审 → 人类确认 → 记账（`risk_spend`） |
| 10 | 派发 | `EIO` | 内建：阻塞型走线程；驱动：同驱动单工锁，不同驱动并行 |
| 11 | 审计 | — | `event:"syscall"` 全量；`mic.*` 额外 `event:"mic"`；`rec.replay` 结果抹除 |
| 12 | 可靠性记账 | — | `scheduler.note_outcome`；内核裁决的 `_deny` 不计入驱动失败 |

**设计要点**：

- **拒绝也是数据**：`_deny()` 统一写审计，并对 `mic.*` / `rec.replay` 补 `event:"mic"`，保证禁录路径可计数。
- **先预算后计费**：`EDQUOT` 在风险闸门之前，attempt-based pricing 不被浪费。
- **两条派发路径同一收口**：内建与 MCP 共享闸门链与可靠性记账，避免语义分叉。
- **审计抹除例外**：`rec.replay` 的转写文本永不进持久化审计，只有元数据。

---

## 4. 强制层与降级

| 原语 | 用途 | 当前状态 | 证据 |
|---|---|---|---|
| namespace（unshare） | 驱动子进程的 pid/mount/net 视图 | Linux full/partial，按 root 与 unshare 可用性分级 | `enforcement/linux.py` `probe()` |
| cgroup v2 | CPU/内存/PID 上限 | 探测 `/sys/fs/cgroup/cgroup.controllers` | `enforcement/linux.py` |
| seccomp BPF | 34 条危险 syscall 黑名单，fail-closed | Linux 注入；未知架构自动关闭并如实报告 | `laos/seccomp.py`、`tests/test_seccomp.py` |
| CoW 写入 | 分支共享 inode，写入时 temp+`os.replace` 断链 | 已落地 | `laos/cow.py`、`tests/test_cow.py` |
| eBPF profiling | 驱动进程真实 syscall 分布 | 可选，需 root+bpftrace，缺席降级 | `laos/profiling.py` |
| Stub 后端 | Windows/macOS 仅能力表 | 自动选择并报告原因 | `enforcement/stub.py`、`tests/test_enforcement.py` |

**边界**：非 Linux 上强制力只剩能力表；laos 明确不把用户态能力表宣称为内核级隔离。

---

## 5. 关键机制审计

### 5.1 分支与写时复制

- `fork()` 只复制目录项，数据块共享；写路径 temp+replace 断链，保护兄弟分支的共享 inode。
- `commit()` 先到先得，兄弟分支失效；`abort()` 只删分支视图。
- 不变量：**分支不产生提权**——能力表与 `task_scope` 随 fork 血统继承，分支只隔离状态，不放宽权限。
- 证据：`tests/test_cow.py`、`tests/test_laos.py`、`tests/test_scope.py`。

### 5.2 上下文与陈旧检测

- `ContextManager`：定长窗口 + 摘要压缩 + swap 落盘；压缩有"不可丢"判断与连续跳过的死循环保护。
- 观察簿：`fs.read` 记录内容摘要；`fs.write/append` 使其他 agent 的观察失效；分支 commit 批量失效。
- 局限：只覆盖 fs 类副作用，非 fs 驱动的外部状态变化不在观察面内（已知债务）。

### 5.3 风险账本与调度

- `FleetLedger`：按工具定价 × 动态乘数；agent 帽与车队预算两级记账；spawn 保留水位。
- 尝试定价：授权即计费、拒绝不计费；高风险走确认横幅，Jev 仅作预审。
- `AgentScheduler`：token/错误双预算，耗尽挂起而非失败；`note_outcome` 统一收口。
- 证据：`tests/test_irreversibility.py`、`test_risk.py`、`test_relbudget.py`、`test_scheduler.py`、`test_jev_gate.py`。

### 5.4 IPC 与能力委托

- `msg.send/recv/list`：信箱有配额、全量审计；消息不持久化到磁盘（进程内）。
- `sys.delegate`：只可授予自身能力子集；TTL 按调用次数；委托者死亡即全部撤销。
- 反提权检查：子集校验 + TTL 扣减 + 死亡撤销，三者缺一不可。
- 证据：`tests/test_ipc.py`。

### 5.5 Brain 可靠性与重复动作治理（v0.39.0）

- `Thought.retryable`：工具参数非法 JSON 不再抛异常，整轮作废为可重试。
- 温度阶梯：连续可重试轮依次 `0 → 0.4 → 0.8`，超过 2 次重试仍不可用则 `ok=False` 中止。
- 重复 syscall 检测：同 tool + 同规范化参数跨步累计，第 3 次注入"必须更换策略"提示，每 key 仅一次。
- 证据：`tests/test_brain.py`、`tests/test_agent_reliability.py`。
- 局限：检测的是**完全重复**，对"参数微调但语义重复"无覆盖（后续可做参数相似度）。

### 5.6 可观测性

- 审计：追加式 JSONL，每次 syscall 带 errno、耗时、结果截断；`laosctl` 可回放。
- 埋点：`telemetry.py` 23 事件 / 138 字段，四级脱敏（plain/count/redacted/forbidden），禁止字段整条拒发；同键 5s 节流，红线事件永不节流。
- AgentProf：审计流 → per-agent span → OTLP/JSON 导出。
- 局限：审计是追加文件，无哈希链/签名，**防篡改能力有限**（R-06）。

### 5.7 听觉链路与隐私

- 四段漏斗：VAD（静音不落盘）→ 触发捕获 → 本地 ASR 蒸馏 → TTL 即焚。
- 回放：内存环形缓冲（默认 30s≈960KB，clamp 5–120s），ADSP 为权威时域存储，AP 环冲只是镜像。
- 隐私封口：`mic.*` 成败双路 `event:"mic"`；`rec.replay` 转写结果从 syscall 审计抹除；上行音频只转写不落盘。
- 证据：`tests/test_vad.py`、`test_rec.py`、`test_ringbuf.py`、`test_replay.py`、`test_telemetry.py`。

---

## 6. 接口契约审计

| ID | 契约 | 当前定义 | 稳定性 | 风险 |
|---|---|---|---|---|
| **C-01** | 内核 ↔ 运行时 | `syscall(pid, tool, args, task=False)`；返回 `CallResult` | 冻结（0.x 内保持） | 低 |
| **C-02** | 内核 ↔ 驱动 | MCP JSON-RPC over stdio；`tools/list`、`tools/call`、Tasks 子集 | 跟随 MCP 2026-07-28 子集 | 中：上游演进 |
| **C-03** | 驱动 ↔ OS | 独立子进程 + jail 根 + 环境继承 | 稳定 | 中：新驱动可绕过隐私闸门（R-07） |
| **C-04** | 审计 schema | `event`/`pid`/`tool`/`args`/`ok`/`ms`/`result`；`mic` 专项 | 稳定 | 中：无版本字段 |
| **C-05** | 埋点 schema | 23 事件、字段级脱敏、禁止字段拒发 | 稳定 | 低 |
| **C-06** | 环境变量 | `LAOS_*` 全表（README §九） | 公开契约 | 低 |
| **C-07** | 版本 | `__version__` + SemVer 0.x 规则 | 公开契约 | 中：第三方内嵌需明确冻结面（Q-07） |
| **C-08** | 隐私 | 显式触发 / `LAOS_REC=0` / 本地 ASR / TTL / 审计脱敏 | 红线 | 低（有测试），但依赖新驱动遵守 |

**契约缺口**：

1. 审计记录无 schema 版本号，跨版本回放依赖字段兼容；
2. 驱动工具名未标注 experimental，第三方可能误当稳定 API；
3. 隐私闸门是"每个驱动自己遵守 + 内核补审计"，缺一个**新驱动注册时的红线断言**（R-07）。

---

## 7. 威胁模型

| ID | 威胁 | 攻击路径 | 现有控制 | 残余风险 |
|---|---|---|---|---|
| **T-01** | 提示注入诱导越权 | 模型输出未授权工具名 | 能力表裁剪 + `EPERM`；schema 校验 | 低：内核拒绝而非提示约束 |
| **T-02** | 路径穿越 | `../` 或前缀混淆逃出 `task_scope` | normpath + 分隔符收边 | 低 |
| **T-03** | 应用作用域逃逸 | 包名前缀伪造（`com.a.evil`） | `pkg` 相等或 `pkg.` 收边 | 低 |
| **T-04** | 委托提权 | 委托超出自身能力 / 永久有效 | 子集校验 + TTL 次数 + 委托者死亡撤销 | 低 |
| **T-05** | 陈旧上下文误判 | 读过期文件继续推理 | 观察簿 + 写失效 + commit 批量失效 | 中：只覆盖 fs |
| **T-06** | 分支提交竞争 | 两分支同时 commit | first-commit-wins，兄弟失效 | 低 |
| **T-07** | 恶意驱动返回 | 驱动输出被当可信指令 | 驱动结果只作为工具结果回灌；审计截断 | 中：缺结果 schema 校验 |
| **T-08** | 审计缺失/篡改 | 删改 JSONL / 异常吞审计 | 追加式写入；被拒路径也记；异常路径补 `event:"mic"` | 中：无哈希链（R-06） |
| **T-09** | 禁录旁路 | 新驱动自行开麦 / 子进程未继承环境 | `LAOS_REC=0` 闸门 + 驱动侧遵守 + 审计 | 中：无注册时断言（R-07） |
| **T-10** | 敏感内容入日志 | 转写文本/音频进审计或埋点 | `rec.replay` 结果抹除；埋点禁止字段；`sha8` 脱敏 | 低（有测试钉死） |
| **T-11** | 资源耗尽 | 无限 syscall / 大输出 / 长任务 | EDQUOT + 风险帽 + cgroup + driver 锁 | 中：长跑未验收（R-02） |
| **T-12** | 审批疲劳 | 用户长期无脑点允许 | scoped grants 减少重复询问；高危恒走确认；污点不洗白 | 中：产品层无"审批质量"指标 |

---

## 8. 测试与证据

### 8.1 套件结构

| 套件 | 规模 | 作用 |
|---|---|---|
| 主库 `tests/` | 评审当日实跑（见 §12） | 内核/驱动/入口/协议全量回归 |
| 隔离区 `zones/AlwaysOnRec-ZCode` | 279 | 全天候录音前沿实现，独立可跑 |
| 复现区 `zones/Repro-ZCode` | 94 | 六来源 71 + AuraSE 规则版 23 |

主库测试文件共 89 个（`tests/test_*.py`），覆盖：

- 内核：`test_laos` / `test_capability` / `test_caps` / `test_scope` / `test_seccomp` / `test_sandbox` / `test_enforcement` / `test_cow` / `test_risk` / `test_irreversibility` / `test_relbudget` / `test_scheduler` / `test_sentinel`；
- 上下文与分支：`test_context` / `test_stale` / `test_laos`；
- IPC 与委托：`test_ipc` / `test_scope`；
- 记忆与技能：`test_memory` / `test_skills` / `test_jitmem` / `test_curate_strong_hits` / `test_jev_mem_ctx` / `test_jev_skills`；
- 听觉：`test_vad` / `test_vadmetrics` / `test_rec` / `test_replay` / `test_ringbuf` / `test_ear_*` / `test_wakegate` / `test_dialogsched` / `test_dialog_e2e` / `test_turnpolicy`；
- 可靠性：`test_brain` / `test_agent_reliability` / `test_llm`；
- 可观测：`test_agentprof` / `test_telemetry` / `test_telemetry_hooks` / `test_release` / `test_ste`。

### 8.2 已实测数字

| 指标 | 值 | 口径 |
|---|---|---|
| edgejev 判断延迟 | median **157.5ms** | 本机实测（README 宣称 15.6ms 已被实测否证） |
| whistle ASR | en WER **10.8%**，ttft **651ms**，~300 tok/s | 本机实测 |
| funasr / SenseVoice | en WER **2.7%**，zh CER **0.0%** | 既有评测口径 |
| Refiner | 错误率 0.4571→0.3875（**-15.2%**）；端到端 CER 1.563→0.042 | AASR-Bench 917 例 |
| GPU 分离 | RTX 4060 上 CPU→GPU **9.3x**（30s 音频） | `scripts/flasep_gpu_bench.py` |

### 8.3 未实测数字（评审必须承认）

| 指标 | 状态 | 影响 |
|---|---|---|
| 端到端首音延迟 | **未实测** | 无法回答"为什么慢"（R-01） |
| 常驻内存 / 7 天 RSS 曲线 | **未实测** | 无法证明无慢泄漏（R-02） |
| KWS 真机触发率/误唤醒率 | **未实测** | 语音问答第一环未闭环（R-03） |
| TTS 首音 | **无此段** | 服务端合成未落地（R-04） |
| 移动端常驻功耗 | **未实测** | 移动形态不承诺（R-05） |

---

## 9. 技术风险与债务

| ID | 风险 | 等级 | 证据 | 缓解 | 时间盒建议 |
|---|---|---|---|---|---|
| **R-01** | 端到端延迟全线未实测 | 高 | §8.3 | 下一波接分段埋点并做基准场景（唤醒→ASR→LLM→TTS） | 2 周 |
| **R-02** | 7×24 长跑无 soak，慢泄漏不可见 | 高 | 无 RSS/句柄/审计体积采样 | 7 天桌面 soak + 指标入库 + 阈值告警 | 2 周 |
| **R-03** | KWS 真机链路未闭环 | 中 | 模型/词表已备，未跑真音频 | 驱动子进程跑 KWS，记录漏唤醒/误唤醒 | 下一波 |
| **R-04** | 无服务端 TTS | 中 | 仅浏览器 `speechSynthesis` | 明确降级形态；TTS 路由/降级语义已有 | 下一波 |
| **R-05** | 移动常驻功耗未验收 | 中 | ADSP 路线在调研 | 原生 App + 前台服务 + 功耗实测 | 中期 |
| **R-06** | 审计无防篡改链 | 中 | JSONL 追加，无哈希链 | 增加逐条链式哈希或定期锚点 | 中期 |
| **R-07** | 新驱动可绕过隐私闸门 | 中 | 闸门依赖驱动遵守 + 内核补审计 | 驱动注册时断言 `LAOS_REC` 检查；隐私驱动清单 | 下一波 |
| **R-08** | 上下文压缩质量依赖摘要器 | 低-中 | 默认摘要 + 可选 judge | 建立压缩前后任务成功率对照 | 中期 |
| **R-09** | 同驱动单工锁限制吞吐 | 低 | 单 stdio 会话按 driver 加锁 | 需要时按工具分片或驱动多实例 | 观察 |
| **R-10** | 0.x API/工具名漂移 | 中 | 无冻结标注 | Q-07 冻结内核公开类；驱动工具名标 experimental | 本场决议 |

---

## 10. 架构决策记录（ADR）

| ID | 决策 | 理由 | 代价 | 复议条件 |
|---|---|---|---|---|
| **ADR-01** | 用户态语义层 + Linux 强制层 | 今天可落地、跨发行版；强制力复用内核原语 | 用户态能力表可被绕过（需配合强制层） | 上游出现可用的 Agent 内核原语 |
| **ADR-02** | 核心零第三方依赖 | 可审计、可移植、无供应链风险 | 手写 HTTP/MCP/OTLP/检索 | 出现无法用 stdlib 满足的硬需求 |
| **ADR-03** | MCP 作为驱动总线 | 事实标准、工具即 syscall、生态可复用 | 受上游协议演进影响 | MCP 出现破坏性变更 |
| **ADR-04** | hardlink CoW 而非 FUSE | 非 root 可用、零依赖、实现简单 | 语义不如 FUSE 完整；跨设备受限 | 需要真 O(1) inode 级分支 |
| **ADR-05** | JSONL 追加审计/记忆 | 简单、可回放、崩溃后易恢复 | 无索引、无事务、体积增长 | 需要复杂查询或强一致 |
| **ADR-06** | 本地 ASR + 显式录音 | 隐私红线、离线可用 | 模型体积与算力成本 | 用户显式 opt-in 云端 |

---

## 11. 技术评审清单

- [ ] 确认闸门链顺序与"拒绝也审计"不变量无异议
- [ ] 确认非 Linux 降级边界表述（仅能力表，不宣称内核隔离）
- [ ] 确认 R-01（端到端延迟）与 R-02（长跑）为阻塞条件并指定责任人
- [ ] 确认 R-06（审计防篡改）是否本期处理
- [ ] 确认 R-07（新驱动隐私断言）的落点
- [ ] 确认 Q-07 的 API 冻结面
- [ ] 逐条复核 §8.3 未实测项没有被文档写成已实测
- [ ] 记录本场结论：通过 / 有条件通过 / 不通过

---

## 12. 本场结论（现场填写）

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
- 说明：README 的 1159 为 10-18 早前实跑值；当日 +22 未发版回归落盘后全量为 1180（构成见 00-pack §4）。CHANGELOG v0.39.0 的 1158 为发版时点正确值，介绍文件不随手改，待下次发版统一刷新
