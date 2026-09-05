# laos —— Linux AgentOS 最小可运行原型

> **命题**：`Linux AgentOS = Linux kernel + Agent + MCP`
> **做法**：不改内核。用 Linux 已有的强制原语（namespace / cgroup / seccomp / landlock）做**强制层**，
> 用一个用户态薄内核 `laosd` 做**语义层**（进程表、能力表、驱动路由、审计），
> 用 MCP Server 做**设备驱动**，用 MCP tool call 做**系统调用**。

零第三方依赖，Python 3.10+，Linux 上可开启真正隔离，macOS / Windows 自动降级为"仅能力表"。

```bash
python bin/laosd.py                    # 跑完整 demo（脚本化大脑，无需 API key）
python bin/laosd.py --real             # 有 OPENAI_API_KEY 时用真 LLM
python -m unittest discover -s tests   # 125 项回归测试
```

---

## 一、调研：AIOS / AgentOS 现在的三条主流路线

### 1. 学术派 —— AIOS：把 LLM 塞进操作系统当"大脑"

 Rutgers 张永锋团队，[arXiv:2403.16971](https://arxiv.org/abs/2403.16971)，已演进到 AIOS Foundation 生态。

- 架构 = **AIOS Kernel（OS kernel 之上的一层抽象）+ SDK**
- Kernel 内含：LLM core、**Scheduler**（多 Agent 请求排队/轮转）、**Context Manager**（上下文快照与恢复，支持中断续跑）、Memory / Storage / Tool / **Access Manager**
- 对上暴露一组 **AIOS syscall**，Agent 通过 SDK 调用

**关键判断**：它是**用户态中间件，不修改 Linux 内核**。这基本确立了后来所有"Agent OS"的默认姿势——
新语义自己实现，强制隔离交给宿主内核。

### 2. 产业派 —— Agentic OS：发行版级集成（2026 年集中爆发）

阿里云 2026-03 基于 Alibaba Cloud Linux 发布 [Agentic OS](https://github.com/alibaba/ANOLISA)（[公告](https://developer.aliyun.com/article/1722846)），是目前落地最完整的产品形态：

| 能力 | 做法 |
|---|---|
| 原生 Skill 封装 | 把运维/调优/部署动作预置为 Skill，避免 Agent 花 token 摸索环境；官方称系统管理场景省 token 30%+，CVE 评估场景 60% |
| Copilot Shell (`cosh`) | 用 AI Shell 替代 bash 作为交互入口，Agent 以 Sub-Agent 方式接入 |
| AgentSecCore | Skill 签名与完整性校验、bubblewrap + seccomp 进程级沙箱、主机标识信息防泄露、LoongShield 安全基线 |
| Token 可观测 | 系统级按 Agent 统计 token，拆解 system prompt / Skills 注册表 / history 占比 |

统信 UOS 也在 2024 年发布过 UOS AIOS。这条路线的价值主张是**开箱即用 + 省 token + 可控**，代价是绑定发行版。

### 3. 研究派 —— 给 Agent 造新的 OS 原语（SOSP 2026 AgenticOS Workshop）

第二届 [AgenticOS Workshop](https://os-for-agent.github.io/)（与 SOSP 2026 同期）的议题，基本就是 Agent OS 的待解清单：

- **隔离与风险**：Isolation in the Age of Agents（UW-Madison）、Agent libOS: Capability-Controlled Self-Evolving Agents（清华）、An AgentOS Needs a Formal Representation of Agents（南大）
- **可观测**：AgentProf: Semantic Profiling for AI Agents（UCSC + 阿里云）、GPU Profiling under Concurrent Agent Workloads（SJTU）
- **调度与预算**：The **Irreversibility Budget** — Fleet-Level Risk Accounting and Admission Control（MPI-SWS）
- **上下文正确性**：When Agent Context Goes Stale: Incoherence in Volatile Agent Context（HKU）
- **OS 结构**：TypeGo（Yale，具身 Agent 运行时）、Agate: Capability Microkernels as Substrate（华为 2012）、**The Abstractions Are Slipping: Four OS Mismatches in the Agent Era**（阿里云）

其中最直接可抄的一篇：**[Fork, Explore, Commit: OS Primitives for Agentic Exploration](https://arxiv.org/abs/2602.08199)**（Cong Wang, Yusheng Zheng）

> 提出 **branch context** 抽象：① COW 状态隔离（独立 fs 视图 + 进程组）② fork / explore / commit|abort 生命周期
> ③ **first-commit-wins**，兄弟分支自动失效 ④ 可嵌套。
> 实现为 **BranchFS**（FUSE，非 root 可用，分支创建 < 350μs，commit 开销与改动量成正比）+ 一个提议中的 `branch()` 系统调用。

### 4. MCP 在这张图里的位置

MCP（Model Context Protocol）已经是事实标准，它的角色非常接近 **"设备驱动接口 + 系统调用约定"**：

- 每个 MCP Server = 一个驱动，把文件/进程/网络/浏览器封装成 tool
- 每条 tool = 一个 syscall
- `tools/call` = `syscall(nr, args)`

**但 MCP 只定义了接口，没有定义内核。** 它天然缺三样东西：权限模型、审计、资源配额。
这就是 `laosd` 要补的空缺。

---

## 二、结论：为什么"Linux kernel + Agent + MCP"是当下最务实的答案

| 路线 | 代表 | 优点 | 代价 |
|---|---|---|---|
| **A. 用户态薄内核** | AIOS、本项目 | 今天就落地、跨发行版、可演进 | 强制力依赖能力表本身写对（可被绕过） |
| **B. 发行版级集成** | 阿里云 Agentic OS | 开箱即用、省 token、有安全兜底 | 绑定发行版，生态割裂 |
| **C. 新内核原语** | `branch()` syscall、capability microkernel | 语义最强、内核强制不可绕过 | 上游周期长，部署门槛高 |

**判断**：A 是当下唯一能立刻跑起来的答案，B 是它的产品化外壳，C 是 3–5 年的研究方向。
而"Linux kernel + Agent + MCP"正是 A 的精确表述——
**复用 Linux 做强制，自己写薄内核做语义，用 MCP 做驱动总线。**

---

## 三、架构映射

| 传统 OS | Linux AgentOS | 本仓库实现 |
|---|---|---|
| 进程 `task_struct` | Agent 进程 | `PCB`（pid / caps / state / budget） + `Agent` |
| 系统调用 | MCP tool call | `kernel.syscall(pid, tool, args)` |
| 设备驱动 | MCP Server | `drivers/drv_fs.py`、`drv_proc.py`、`drv_sys.py` |
| `/dev`、`/proc` | 驱动注册表 | `kernel.syscall_table`（tool → driver） |
| init / udev | 引导器 | `bin/laosd.py` |
| capability / seccomp | 能力表 + Linux 隔离 | `CapabilitySet` + `sandbox.py` |
| 内存管理 / 换页 | 上下文分页与换出 | `ContextManager`（窗口 + 摘要 + swap） |
| 调度器 | LLM 时间片 + 可靠性预算 | `AgentScheduler`（轮转 + token/err 双预算挂起） |
| fork / COW | 探索分支 | `BranchContext`（fork / explore / commit） |
| strace + auditd | 审计 | `AuditLog` + `bin/laosctl.py` |

```
        ┌──────────────────────── Agent 进程 ────────────────────────┐
        │  Brain(LLM)  ←→  Context Manager(窗口/换页)                │
        └──────────────────────────┬────────────────────────────────-┘
                                   │ syscall(pid, tool, args)
        ┌──────────────────────────▼────────────────────────────────-┐
        │  laosd 薄内核（语义层）                                     │
        │   能力检查 → 预算检查 → 驱动路由 → 审计                      │
        └──┬──────────────┬──────────────┬──────────────────────────-┘
           │ stdio/MCP    │ stdio/MCP    │ stdio/MCP
        ┌──▼───┐      ┌───▼──┐      ┌───▼──┐
        │drv_fs│      │drv_pr│      │drv_sy│   ← 设备驱动（独立进程）
        └──┬───┘      └───┬──┘      └───┬──┘
           │              │              │
        ┌──▼──────────────▼──────────────▼──────────────────────────-┐
        │  Linux kernel（强制层）：namespace / cgroup v2 / seccomp /  │
        │  landlock / FUSE —— 真正的隔离与资源上限由它执行             │
        └───────────────────────────────────────────────────────────-┘
```

---

## 四、Demo 记录了什么

`python bin/laosd.py` 一次跑完 7 幕：

1. **内核启动**：加载 3 个驱动，注册 9 条 syscall
2. **fork 探索分支**：`main` → `exp-A` / `exp-B`
3. **起 2 个 Agent 进程**，能力不同，并发执行
4. **ReAct 循环**：每一次 tool call 都是一次带 errno 的 syscall
5. **commit**：diff-based 提交，`first-commit-wins` 使 `exp-B` 失效
6. **运行报告**：syscall 数、拒绝数、token、上下文换页
7. **内核状态**

实际输出节选：

```
  系统调用表 : 9 条 -> fs.append, fs.list, fs.read, fs.stat, fs.write, proc.exec, proc.list, sys.info, sys.load
  pid=1001 name=ops-agent   caps=['fs.*', 'proc.*', 'sys.*']  可见 syscalls: 9 条
  pid=1002 name=guest-agent caps=['sys.*']                    可见 syscalls: ['sys.info', 'sys.load']

  ── pid=1001 ops-agent ──
    step2  fs.read(path='/exp-A/workspace/hosts')      -> 127.0.0.1   localhost ...
    step3  fs.append(path='/exp-A/workspace/hosts', content='127.0.0.1 myapp.local\n') -> OK appended 22 bytes
    step5  proc.exec(cmdline='rm -rf /')               -> [error] EDENIED: dangerous command blocked by driver

  ── pid=1002 guest-agent ──
    step1  fs.read(path='/exp-A/workspace/hosts')      -> [error] EPERM: capability not granted

  exp-A 与 main 的差异: [{'op': 'write', 'path': 'workspace/hosts'}]
  exp-A 提交 1 项变更到 main
  - main [exploring] changes=0
    - exp-A [committed]   changes=1
    - exp-B [invalidated] changes=1     ← first-commit-wins

  被拒绝的 syscall（两层防御都命中了）：
    [内核能力表] pid=1002 fs.read   -> EPERM: capability not granted
    [驱动防护]   pid=1001 proc.exec -> EDENIED: dangerous command blocked by driver: 'rm -rf /'
```

控制面：

```bash
python bin/laosctl.py ps        # 进程表：syscalls / denied / caps
python bin/laosctl.py top       # 按 syscall 聚合耗时
python bin/laosctl.py trace --pid 1001
python bin/laosctl.py denied    # 所有被拒调用
python bin/laosctl.py budget    # 车队风险账本回放
python bin/laosctl.py spans     # AgentProf 语义剖析回放
```

---

## 五、实现过程中撞到的四个真问题

这几条比 demo 本身更值得记下来：

1. **写操作发生在驱动进程里，分支层看不见。**
   第一版 commit 靠 journal 记账，结果 agent 用 MCP 写完文件后 `changes=0`、提交了个空。
   修法是改成 **diff-based commit**（对比 workspace 与 base 快照，语义等同 overlayfs 的 upper/lower 合并）。
   论文的 BranchFS 把 COW 下沉到 FUSE，正是为了让文件系统自己记账——**这是分支语义必须下沉到内核态的根本原因**。

2. **MCP 没有权限模型，能力表必须由内核强制。**
   Agent 的"可见 syscall 表"是内核按 caps 裁剪后才交给 LLM 的。即便 LLM 硬要调没授权的 tool，
   内核也会返回 `EPERM` 而不是让请求到达驱动。靠 prompt 约束 Agent 行为在安全上是无效的。

3. **errno 不能被吞掉。**
   驱动抛 `EDENIED` 时，早期版本统一包成 `EIO`，导致上层分不清"被拒绝"和"驱动崩溃"。
   现在 errno 原样透传，控制面才能按类型做准入控制。

4. **上下文是新的内存，需要分页与换出。**
   `ContextManager` 用定长窗口 + 摘要压缩 + swap 落盘三件套。窗口逼近上限时压缩最老的 1/3，
   被换出的消息写进 `var/swap/*.jsonl`，统计里能看到 `compactions` 与 `swapped_bytes`。

---

## 六、与"真正的 AgentOS"还差什么

按重要性排序，也是下一步的路线图：

| 缺口 | 现状 | 该怎么做 |
|---|---|---|
| **强制隔离** | 驱动 spawn 已接 namespace + cgroup v2（挂真实驱动 pid，子孙继承）+ **seccomp block-dangerous**（`LAOS_SECCOMP`，unshare 后经 bootstrap shim 注入、随 fork/execve 继承到 proc.exec 子进程） | per-agent（而非 per-driver）cgroup；seccomp 白名单模式（按驱动画像） |
| **不可逆操作预算** | ~~只有 syscall 次数预算（EDQUOT）~~ → **Irreversibility Budget 2.0**：按工具定价（`irreversibility_cost`）+ agent 风险帽 + 车队账本（`FleetLedger`）+ spawn 准入控制（保留水位） | 探索期免计费、commit 时结算（Externalization Barriers 式延迟定价） |
| **分支的 O(1) 创建** | **hardlink COW**：fork 只复制目录项、数据块全共享、写路径 temp+replace 断链（`laos/cow.py`）；diff 走 inode 快路径 | FUSE BranchFS（真 O(1) inode 级 + 原子 rename 语义）仍是长期项 |
| **上下文一致性** | ~~只看 token 水位~~ → **Stale Context 检测**：fs.read 观察簿 + fs.write/append 失效他人 + branch commit 批量失效，内核通告注入 agent 窗口 | 跨驱动（非 fs 类）副作用的一致性追踪 |
| **语义 profiling** | ~~bpftrace 集成~~ → **eBPF（内核真值）+ AgentProf（语义层）**：审计流 → per-agent span（重复浪费/拒绝率/单工具依赖启发式）→ OTLP/JSON 导出（`var/traces/`）+ `laosctl spans` | 每步意图建模、工具选择合理性评分（论文全量目标） |
| **多 Agent 通信** | ~~共享文件系统~~ → **内核 IPC**：`msg.send/recv/list` 信箱（配额 + 审计）+ `sys.delegate` 运行时能力委托（TTL、委托者死亡即撤销） | 消息持久化 / 组播 / 委托链路审计可视化 |
| **可观测闭环** | JSONL 审计 | 导出 OpenTelemetry trace，一次任务 = 一条 trace，一次 syscall = 一个 span |

> 驱动总线已升级至 **MCP 2026-07-28 子集：Tasks + Elicitation**（同步路径）：
> 长任务可经 `syscall(..., task=True)` 异步派发并轮询结果（`LAOS_TASK_TIMEOUT`），
> 驱动侧 `elicitation/create` 请求统一路由到内核 `confirm` 人类在环闸门
> （`drv_proc` 的 `LAOS_EXEC_ELICIT=1` 白名单外放行即建于此机制上）。

---

## 七、目录结构

```
laos/
  laos/
    mcp.py        MCP 2026-07-28 子集（Tasks/Elicitation）+ JSON-RPC 2.0 over stdio
    kernel.py     laosd 薄内核：PCB、能力表、syscall 网关、审计、分支表、内建 IPC
    agent.py      Agent 运行时（ReAct 循环）
    brain.py      Brain 接口 + ScriptedBrain（确定性）+ OpenAIChatBrain（真 LLM）
    context.py    Context Manager：窗口 / 摘要压缩 / swap / 观察簿（stale 检测）
    branch.py     BranchContext：fork / explore / commit，first-commit-wins
    sandbox.py    Linux 隔离封装（namespace / cgroup）+ 路径 jail
    risk.py       FleetLedger：车队级不可逆风险账本（加权/两级记账/准入水位）
    scheduler.py  AgentScheduler：token/err 双预算轮转 + 快照
    seccomp.py    seccomp 经典 BPF 组装 + ctypes 安装（block-dangerous 黑名单）
    cow.py        CoW 原语：temp + os.replace 断链写，保护 hardlink 共享 inode
    profiling.py  bpftrace 集成：驱动进程树真实 syscall 分布（可选，缺席降级）
    agentprof.py  AgentProf：审计流 → per-agent 语义 span + 启发式发现 + OTLP/JSON 导出
  drivers/
    drv_fs.py     文件系统驱动：read / write / append / list / stat（jail 内）
    drv_proc.py   进程驱动：list / exec（白名单 + 危险模式拦截）
    drv_sys.py    系统信息驱动：info / load（主机名默认脱敏）
  bin/
    laosd.py      引导器（init）：加载驱动 → fork 分支 → 起 Agent → commit
    laosctl.py    控制面：ps / top / trace / denied / audit
  tests/
    test_*.py     125 项回归测试（laos / ipc / seccomp / cow / profiling / sandbox 等 16 个文件）
  var/            运行期产物：audit.jsonl / branches/ / swap/
```

## 八、环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | — | 设置了则 `laosd --real` 走真 LLM |
| `LAOS_LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容端点 |
| `LAOS_LLM_MODEL` | `gpt-4o-mini` | 模型名 |
| `LAOS_FS_ROOT` | `<var>/branches` | fs 驱动的 jail 根 |
| `LAOS_EXEC_ALLOW` | `echo,hostname,uname,whoami,uptime` | proc.exec 命令白名单 |
| `LAOS_PRIVACY_MASK` | `1` | 主机名等标识信息脱敏 |
| `LAOS_CTX_TOKENS` | `2000` | 上下文窗口上限 |
| `LAOS_BUDGET` / `LAOS_STEPS` | `8` / `8` | syscall 预算 / 最大步数 |
| `LAOS_AGENT_ERR_BUDGET` | `3` | per-agent 可靠性预算：派发后的失败次数（含驱动 EDENIED），耗尽即挂起；`0` = 不限 |
| `LAOS_SECCOMP` | `block-dangerous` | `off` 关闭；`block-dangerous` 给驱动装 seccomp 黑名单过滤器（仅 Linux） |
| `LAOS_PROF` | `1` | `0` 关闭 eBPF profiling；开启需 Linux + root + bpftrace，缺席自动降级 |
| `LAOS_RISK_BUDGET` | `LAOS_IRREV_BUDGET` 或 `3` | 车队级不可逆风险总预算 |
| `LAOS_RISK_RESERVE` | `1` | spawn 准入保留水位（剩余预算须严格高于此值） |
| `LAOS_TASK_TIMEOUT` | `30` | MCP Tasks 路径（`syscall(..., task=True)`）轮询任务结果的总超时（秒） |
| `LAOS_EXEC_ELICIT` | `0` | 置 `1` 时 proc.exec 白名单外命令先经 elicitation 请求人类放行（accept 放行 / decline 拒绝） |
