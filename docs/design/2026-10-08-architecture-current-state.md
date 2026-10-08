# laos 架构现状（2026-10-08 重新学习快照）

> **生成于 4332b1c 时刻快照**（v0.28.1 · 980 测试基线）：其后 laosweb v3 波（/api/sentinel + 审批卡 scope + mobile-first PWA 前端）与仓库卫生波已推进，§6/§10/§12 中 laosweb 行数、测试计数、计划完成度等以最新 git 状态为准。

> **本文档是"重新学习"后的唯一现状快照**，用于取代一切过期笔记。
> 实测环境：`C:/Users/yaoyue/miniconda3/python.exe`（3.12.4）｜HEAD `4332b1c`｜`laos.__version__ = "0.28.1"`
> 主库测试实跑 `python -m unittest discover -s tests` → **Ran 980 tests · OK (skipped=5)**，耗时 157s。
> 写作方式：文件级逐模块勘察 + 实跑核对，所有数字均来自实测或代码行号，不引用宣称值。

## 0. 作废声明（旧记忆中对不上的部分）

与 2026-09 及更早的工作记忆相比，以下认知**已整体作废**：

| 旧认知 | 现状 |
|---|---|
| laos 是"常驻音频采集 Agent 原型"，四段漏斗是主线 | 四段漏斗只是**听觉链路**；项目主体已是 **Linux AgentOS 语义内核**（九级闸门 + 驱动总线 + 治理面） |
| `bin/laosd.py` 是常驻 daemon | laosd 是**一次性引导器**（无循环、无 socket）；常驻宿主是 `bin/laosweb.py` |
| `laos/` 只有十来个文件 | 50 个模块，8447 行；`kernel.py` 单文件 1035 行 |
| 目录 `AlwaysOnRec-*` 裸奔根层 | 已收进 `zones/`，四棵树 |
| 品牌名 laos | 对外 **nanoLAOS**（副标 laos · Linux AgentOS）；技术名/包名/CLI/`LAOS_*` 全部不变 |
| 主库 ~691 测试 | **980**（conda 3.12.4 实跑） |

---

## 1. 定位与品牌

- **命题**：`Linux AgentOS = Linux kernel + Agent + MCP`。基座是 Linux 内核，Agent 是内核之上的**新负载**（与进程同类）；禁止"给 AI Agent 装操作系统"式主客反转表述。
- **做法**：不改内核。Linux 原语（namespace / cgroup / seccomp）做**强制层**；用户态薄内核做**语义层**（进程表、能力表、驱动路由、审计）；MCP Server 做**设备驱动**；MCP tool call 做**系统调用**。
- **零依赖承诺**：`laos/` 核心纯 stdlib（已 Grep 全量 import 核实）。第三方包只允许出现在 `drivers/` 子进程内，且必须**惰性导入**（函数体内 import），保证裸解释器可 import 并回答 `status`。
- **conda 红线**：只用 `C:/Users/yaoyue/miniconda3/python.exe`；禁止 `pip install` 进该环境。

---

## 2. 运行时拓扑

```
bin/laosweb.py  ← 真正的常驻宿主（ThreadingHTTPServer 127.0.0.1:$LAOS_WEB_PORT，默认 8800）
   │  import laosd，在 daemon 线程里跑 laosd.demo()
   │  HTTP 线程只读状态 / kernel.kill / asyncio.run(内建 syscall)；kernel.confirm = web_confirm 实现人类在环
   ▼
laos/kernel.py  AgentKernel（被动可调用对象，自身无循环）
   │  syscall(pid, tool, args) → 九级闸门链 → 派发
   ├── 内建 syscall（10 条，不经驱动、无 driver 锁）：msg.* / sys.delegate / mem.*
   └── MCP over stdio（JSON-RPC 2.0，PROTOCOL_VERSION "2026-07-28"）
        ▼
   drivers/drv_*.py（16 个驱动子进程）→ sandbox.wrap → enforcement 后端 → seccomp
        ▼
   Linux kernel（强制层）：namespace / cgroup v2 / seccomp / landlock
```

- **驱动拉起点**：`bin/laosd.py:145-171` `boot_kernel()` → `kernel.load_driver(name, argv, env)`。
- **解释器分流**：fs/proc/sys/npu 用 `sys.executable`；audio 仅当 `.venv-audio/Scripts/python.exe` 存在才加载；ear/mic 用 `LAOS_EAR_PYTHON` → conda python → 退回主解释器（仅 status 可用）。
- **跨进程事后审计**：内核状态只在内存，`bin/laosctl.py` 走 `var/audit.jsonl` 日志回放而非 IPC 查询。

---

## 3. 内核 syscall 九级闸门链（`laos/kernel.py:514` `syscall()`）

| # | 闸门 | 位置 | 拒绝码 |
|---|---|---|---|
| 0 | 进程存在 / 未 killed | L529 | `ESRCH` / `EACCES: process killed` |
| 1 | 查表（`syscall_table` → `_builtin_specs` → miss 才 ENOSYS） | L537 | `ENOSYS` |
| 2 | 能力检查 `_effective_allows(pcb, tool, consume=True)`（自身 caps ∪ 未过期委托，匹配扣 1 次 TTL） | L546 | `EPERM` |
| 3 | 意图收窄 `pcb.task_scope`（normpath 后分隔符收边前缀匹配） | L553 | `EACCES: outside task scope` |
| 3b | pkg 作用域（`pkg:` 条目约束 `screen.*` / `apps.*`） | L568 | `EACCES` |
| 4 | 参数校验 `validate_args`（含路径穿越 → EACCES） | L576 | `EINVAL` / `EACCES` |
| 5 | syscall 次数预算（**先于风险闸**，避免注定失败的调用消耗车队预算） | L583 | `EDQUOT` |
| 6 | **Sentinel 六级动作闸**（opt-in，未装配则零执行零审计） | L591 | `EDENIED` / `EACCES: sentinel requires confirmation` |
| 7 | **不可逆闸门 2.0**：`spec.reversible=False` → 车队余量 / `pcb.risk_cap`；`risk=="high"` 再经 Jev 预审 + 人类 confirm；通过则 `risk.charge()` | L627 | `EACCES: fleet risk budget exhausted` / `EDENIED: denied by jev prejudge` |
| 8 | 派发 + 审计 + `scheduler.note_outcome(pid, result.ok)` | L658 | — |

**Sentinel 六级有序判定**（`laos/sentinel.py:129`）：① `deny_tools` 硬拒 → ② 显式 `rules`（fnmatch，唯一能放行污点出站/终审的通道）→ ③ `always_allow`/`always_ask` → ④ 风险×模式（auto 全放 / strict 非 low 问 / ask 默认：不可逆或高风险问）→ ⑤ taint 升级（污点 pid + 出站 → ask，auto 也生效、永不回退、仅 once 档）→ ⑥ 终审警告（不可逆∧高风险 → ask，`mode=="auto"` 除外）→ 兜底 allow。
配套：`GrantStore`（scoped grants，`once` 命中即消费）、`TaintTracker`（`mark_private_read/is_tainted/untaint`，**唯一清除通道 = 进程退出**，由 `kernel.kill` 调用）。

**syscall 面**：内建 10 条（`msg.send/recv/list`、`sys.delegate`、`mem.remember/recall/forget/stats/curate/outcome`）；驱动面 fs/proc/sys/npu/audio/ear/mic/screen/apps/comms/rec/llm/battery/events/notify（`lsmod` 可查）。

---

## 4. `laos/` 模块地图（50 模块 · 8447 行）

**治理与内核**
`kernel.py`(1035) 闸门链 · `enforcement/`（linux/android/stub 三后端 + base 契约，OSAL 模式：换平台 = 换一个后端文件）· `caps.py`（esp-claw 风格能力注册表，**尚未接入 kernel**）· `decide.py`（Clef 三判型 noul/choice/score + RuleBackend 插拔）· `sentinel.py` · `confgate.py`（置信三段闸 local/cloud/drop）· `sandbox.py`（薄委托 + PathJail）· `seccomp.py`（ctypes 装经典 BPF，30 条黑名单）· `risk.py`（FleetLedger 车队不可逆账本，**按尝试计费，不退款**）· `locks.py`（UniqueLock）· `validate.py`。

**记忆与认知**
`memory.py`（JSONL 情景记忆，bigram Jaccard 检索）· `jitmem.py`（Curator，read-time 整理；三分量加权 0.7/0.2/0.1，recency 半衰期 14 天；**用户行 `origin=="user"` 神圣**，不参与去重与预算）· `context.py`（窗口+换页+swap+观察簿）· `knowledge.py`（LLM 前置短路）· `brain.py` / `branch.py`（fork/explore/commit，first-commit-wins）· `refiner.py` · `calib.py`（Brier/ECE/reliability）。

**对话与事件**
`dialogflow.py`（装配层）· `dialogsched.py`（GenerationGate / PauseWindow / DialogQueue latest-only）· `evroute.py`（事件防火墙，esp-claw 转译）· `wakegate.py`（四态机）· `turnbuf.py` / `turnpolicy.py` / `speechchunk.py`。

**音频与度量**
`vad.py`（StreamingVAD，10ms 帧，audioop 优先 + 3.13 纯 Python 兜底）· `vadmetrics.py`（含 BG-FAR 防装死闸）· `loudness.py`（ITU-R BS.1770-4 纯 stdlib）· `micgeom.py`（MPE 位置编码）· `binaural.py`（ILD/IPD）· `duplex.py` · `foa.py`（AmbiX/SN3D）· `wer.py`。

**协议与可观测**
`mcp.py`(487)（JSON-RPC 2.0 over stdio，Tasks + Elicitation）· `skills.py` · `judge.py`（四后端 Rule/Cloud/Local/SafeJudge；**HTTP 一律走 curl 子进程**；无 OnnxBackend）· `agent.py` / `agentprof.py`（语义 span + OTLP 导出）· `scheduler.py` · `telemetry.py`(551)（23 事件注册表，脱敏四级，5s 节流，`LAOS_REC=0` 时 `a.*` 静默）· `traceviz.py`（audit → mermaid）· `ste.py`（ASD-STE100 五规则 check-only lint）· `profiling.py`（bpftrace，缺席降级）· `cow.py`。

---

## 5. `drivers/` —— 16 个驱动子进程（2671 行）

`drv_fs`(PathJail=chroot) · `drv_proc`（白名单非黑名单）· `drv_sys`（默认脱敏）· `drv_npu`（QNN ctypes / stub）· `drv_audio`（分离+AEC，需 .venv-audio）· `drv_ear`(352，ASR 三通道) · `drv_mic`（`LAOS_REC=0` 全局 EACCES）· `drv_rec`（VAD 触发，6h 即焚）· `drv_genie`（端侧 LLM）· `drv_screen`(209，adb+uiautomator) · `drv_apps` · `drv_notify` · `drv_comms`（sms_send 不可逆）· `drv_battery` · `drv_events` · `drv_clef`（非 MCP Server，wsl chroot 调 clef_infer）。底座 `screen_adb.py`。**无 `drv_adb.py`**（adb 能力收口在 drv_screen + screen_adb）。
分层红线：驱动**不持审计句柄**，只把脱敏字段放进返回 JSON，由内核在派发尾部转写事件。

---

## 6. `bin/` 入口

| 文件 | 行 | 角色 |
|---|---|---|
| `laosweb.py` | 986 | **常驻宿主**：单文件内联 HTML/CSS/JS，无模板引擎；路由 `/`、`/api/state`、`/api/sentinel`(GET/POST)、`/api/confirm`、`/api/kill`、`/api/msg`、`/api/recv`、`/api/diary`、`/api/restart`；前端 1s 轮询；审批超时 60s 按拒绝 |
| `laosd.py` | 448 | 一次性引导器：boot_kernel → seed_main_branch → wire_judge → demo 7 幕 → shutdown |
| `laosctl.py` | 229 | 离线审计回放：`audit/trace/denied/top/ps/prof/budget/spans/selfcheck/traceviz` |
| `diary.py` | 332 | 审计+记忆 → `var/diary/<date>.md` 五章；跨代聚合（活文件 + gzip 归档按代序拼接） |
| `journal.py` / `mood_report.py` | 96 / 84 | 录音蒸馏入记忆 + 即焚；情绪堆积图 |

---

## 7. `zones/` 四棵树（全部是 fork 快照，不 import 主库）

| 树 | 角色 | 测试（`def test_`） | `__version__` | git |
|---|---|---|---|---|
| `AlwaysOnRec-Trae` | 同工作负载在另一 IDE 的对照实现 | 276 | 0.28.1 | 主仓跟踪 |
| `AlwaysOnRec-ZCode` | 全天候录音前沿增量孵化区（验完再合主干） | 279 | 0.28.1 | 主仓跟踪 |
| `AlwaysOnRec-DB` | 数据库沙箱 | 304 | **0.1.0（不同步）** | **整树 gitignore + 自带 .git** |
| `Repro-ZCode` | 论文数字过手复现（零主代码耦合） | 71 | 无 | 主仓跟踪 |

三棵树（主 + ZCode + Trae）由 `scripts/release.py` 同步 `__version__`；DB 树**永久游离**。

---

## 8. 数据与可观测

- **真源**：`var/audit.jsonl`（`AuditLog` 盖 `(epoch, seq)` 复合键，gzip 轮转 `audit-<UTC日期>-<代>.jsonl.gz`）+ `var/memory.jsonl`。一切派生物（diary / traceviz / OTLP / web 面板）必须能回到原始记录。
- **23 事件注册表**（L4/A4/S2/D5/P3/F5）：内容类字段只许 `len` / `sha256 前 8 位` / 时长 / 语言码；禁止级字段命中**拒发整条**并落 `telemetry.reject`。
- **隐私四件套**：录音只由显式 syscall 触发；`LAOS_REC=0` 全局禁录（`a.*` 静默、`f.rec.bypass` 永不静默）；每次录音成功**与被拒**都写 `event:"mic"`；ASR 全本地。

---

## 9. 关键环境变量（节选）

`LAOS_WORKDIR` · `LAOS_WEB_PORT`(8800) · `LAOS_FS_ROOT` · `LAOS_REC` · `LAOS_PRIVACY_MASK`(1) · `LAOS_SECCOMP`(block-dangerous) · `LAOS_ENFORCEMENT` · `LAOS_RISK_BUDGET`/`LAOS_IRREV_BUDGET`(3) · `LAOS_RISK_RESERVE`(1) · `LAOS_AGENT_ERR_BUDGET`(3) · `LAOS_TASK_TIMEOUT`(30) · `LAOS_JEV_BACKEND`(none)/`_AUTOGATE`/`_AUTOGATE_MIN`(0.95)/`_MEM`/`_SKILL`/`_COMPACT`/`_PREVIEW` · `LAOS_EAR_PYTHON` · `LAOS_ASR_CHANNEL`(funasr|server) · `LAOS_WAKE_*` · `LAOS_DIALOG_OBS_MS`/`RESUME_MS` · `LAOS_STE_LINT` · `LAOS_PROF`。

---

## 10. 测试与发版口径

- **命令**：`C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests` → **980 OK（skipped=5）**。
- **解释器必须锁 conda 3.12.4**：`bin/laosd.py:395` 用了 PEP 701 嵌套同型引号 f-string，3.11.9 直接 SyntaxError → 主库掉到 947 且 6 个 error。
- **发版 SOP**（AGENTS.md 最高优先级）：`release.py --dry-run` 核对 → `release.py --apply`（真跑套件 → 三棵树 `__version__` 同步 → `sync_docs()` 改五类锚点）→ 人工誊 CHANGELOG → annotated tag → push master+tag → GitHub Release。**漏一步算发版事故**。
- 版本轴：0.x 阶段 minor = 功能波次，breaking 也升 minor；纯 docs 波在 subject **尾部**标 `+new-domain` 才按 MINOR。

---

## 11. 已知硬伤（2026-10-08 实测，均未修）

1. **解释器锁定未成文**：PEP 701 断裂点见上，`release.py --apply` 用 `sys.executable` 起子进程，用错解释器会被门禁当场拒发版。
2. **31 个幽灵测试**：`tests/test_locks.py`(7) / `test_loudness.py`(10) / `test_turnbuf.py`(8) 是 pytest 风格，`unittest discover` 收集不到（静态 1011 − 实跑 980 = 31）。另 `scripts/test_crawl_*.py` 也不在 discover 范围。
3. **文档计数漂移**：README/CHANGELOG 仍写 974，实跑 980；页脚总数应为 980+279+71 = **1330**（现写 1324）。
4. **`zones/AlwaysOnRec-DB` 的 `__version__`(0.1.0) 与 304 测试永久游离**。
5. **`scripts/table_lint.py` 首列硬编码 `"模型"`**（L17/30/44/110）：首列不是"模型"的表被**静默跳过**，等于没校验（Jev 表首列是"项目"即如此）。
6. **跨仓库：`AlwaysOnRec-HY4` 当前 147 tests 中 1 个失败** —— `test_status_reports_encoding_and_quota`（`tests/test_rec.py:167`）断言 `encoding=wav`，实际返回 `encoding=opus`。这是 AED/AGC/SER 三条调研线落地任务的**共同前置门禁**。

---

## 12. 调研资产与计划台账

- `docs/research/`：44 篇主报告 + 9 个子目录（按日期前缀平铺，**不迁移**，INDEX.md 是导航中枢）；入场口 `2026-09-19-laos-adoption-capstone.md`。
- `docs/superpowers/plans/`：39 份计划，**38 份已执行完**，未完成 1 份 —— `2026-10-08-laosweb-v3.md`（后端 `/api/sentinel` 与审批卡已合，前端治理面板 + mobile-first + PWA 未落地）。
- 语料：`docs/research/corpus/papers_unified.jsonl` 19,792 条；`corpus/venue_expansion/` 38 venue 123,271 行，强命中 934 行（audio-speech 771 / agent-os 49 / spatial-privacy 114），检索入口 `python scripts/query_corpus.py --topic audio-speech --strong-only --limit N`（实测返回 771 条）。
