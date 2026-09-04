# AgentOS / AIOS 现状调研与变体分类学

> 调研时间：2026-08-31
> 目的：回答"Linux AgentOS = Linux kernel + Agent + MCP"这个命题在当下坐标系里的位置，
> 以及它有哪些变体、各自解决了什么、没解决什么。

---

## 0. 一句话结论

**"AgentOS"现在至少指 8 种不同的东西**，从"一个 Python 框架"到"一个跑在 seL4 上的可启动微内核系统"。
所有混淆都来自两件事没说清：**抽象做在哪一层**、**强制力从哪来**。

真正有用的分类维度不是"是不是 OS"，而是下面这条**强制力光谱**。

---

## 1. 强制力光谱：理解所有变体的唯一坐标轴

| 层级 | 名称 | 强制力来源 | 能绕过吗 | 代表 |
|---|---|---|---|---|
| **L0** | 约定层 | prompt / tool 描述 / 系统提示词 | 随便绕过 | 绝大多数"给 Agent 一堆工具"的做法 |
| **L1** | 框架层 | 进程内 Python/TS 框架 | 框架外调用即绕过 | 各种 Agent 框架自称"OS" |
| **L2** | 用户态内核层 | 独立守护进程做能力检查 | Agent 不走这条路就绕过 | **AIOS**、**laos（本项目）** |
| **L3** | libOS 层 | 与 Agent 同进程，拦截所有操作 | 需突破运行时 | **Agent libOS** |
| **L4** | 宿主 OS 强制层 | namespace / cgroup / seccomp / landlock | 需提权或内核漏洞 | 阿里云 AgentSecCore、E2B/Daytona、**laos 的目标** |
| **L5** | 微内核 / 能力硬件层 | seL4 capability + 形式化验证 | 需破形式化证明 | **agentOS (seL4)**、Agate |

**关键洞察**：
- L0–L2 的全部问题在于一句话 —— **visibility ≠ permission**（Agent libOS 论文原话）。
  Agent"能看到"某个工具，不等于它"被允许"用。MCP 解决了前者，完全没碰后者。
- 真正不可绕过的是 **L4 及以上**。所以任何"AgentOS"如果不接 L4，安全性都只是**约定**。
- 但 L5 的代价是：整个生态（Linux 驱动、Docker、GPU 栈）全部作废。

**这直接给出 Linux AgentOS 的准确定位：不做 L5，把 L2 语义层写扎实，把 L4 强制层接满。**

---

## 2. 变体全景（按落地层次）

### A. 用户态中间件 —— AIOS（Rutgers / AIOS Foundation）

- 论文：[arXiv:2403.16971](https://arxiv.org/abs/2403.16971)，已演进为 [agiresearch/AIOS](https://github.com/agiresearch/AIOS) + [AIOS Foundation](https://app.aios.foundation/)
- 架构：**AIOS Kernel（架在 OS kernel 之上的抽象层）+ Cerebrum SDK**
- Kernel 模块（官方文档目录）：LLM Core(s) / **Scheduler** / **Context** / Memory / Storage / Tools / **Access** / **Syscalls** / Terminal
- 部署模式 4+1 种：Local Kernel、Remote Kernel、Remote Kernel Dev、Personal Remote Kernel、Personal Remote Virtual Kernel
  （ARM = Agent Running Machine，AHM = Agent Hub，ADM = Dev，AUM = UI）

**判断**：这是"用户态薄内核"路线的定义者。它证明了**不修改 Linux 内核也能做出 OS 语义**。
局限：强制力停在 L2 —— 能力检查由 AIOS 自己做，Agent 若绕过 AIOS SDK 直接 syscall，AIOS 看不见。

### B. 发行版级集成 —— 阿里云 Agentic OS

- 2026-03 基于 Alibaba Cloud Linux 发布，[ANOLISA](https://github.com/alibaba/ANOLISA) 开源
- 三板斧：**原生 Skill 封装**（系统管理场景省 token 30%+，CVE 评估场景 60%）、**cosh**（Copilot Shell 取代 bash 作为 Agent 交互入口）、**AgentSecCore**（Skill 签名校验 + bubblewrap/seccomp 进程级沙箱 + 主机标识防泄露 + 安全基线）
- 系统级 **Token 可观测**：按 Agent 拆解 system prompt / Skills 注册表 / history 占比

**判断**：目前**落地最完整**的形态，而且是少数真正做进 L4 的（seccomp + bubblewrap）。
代价是绑死发行版。统信 UOS 2024 年也发过 UOS AIOS，同一思路。

### C. libOS / 运行时基座 —— Agent libOS（清华）

- [arXiv:2606.03895](https://arxiv.org/abs/2606.03895)，Yingqi Zhang，v3（2026-08）
- 针对的核心问题：**self-evolving agent**（跨任务持久化、获取记忆、激活 Skills、合成工具、fork 子进程、挂载远程资源、提交 checkpoint）会导致**部署后权限持续扩张**
- 三平面分离：
  - **Operation admission** = 进程身份 + **Task Authority ceilings** + typed Capabilities + 人类审批 + 预算 + 具体原语
  - **Information-flow admission** = 标签传播 + 不可变来源引用 + Host 注册的 Sink + 高敏出口需**一次性精确人类释放**
  - **Durable causal evidence** = 记录意图/结果/记账/因果链，但**从不授予权限**
- 实现：持久进程、Object Memory、Skills、**syscall 中介的 JIT Tools**、镜像与 checkpoint、typed providers、Human queues、预算、持久恢复
- 外部副作用走 **prepare-dispatch-settle** 协议：暴露歧义、防止盲重放
- 评估：33/33 确定性全运行时任务通过任务与安全 oracle；12 次真实模型运行安全与严格效用 12/12

**论文自己承认的三个不**（这一点非常值得尊重，也划清了边界）：
> 不防 prompt injection、不提供 kernel-grade sandboxing、不回滚不可逆的外部副作用。

**判断**：这是 L3 的最强形态，也是"能力受控"这件事目前最严谨的设计。
它的 **Task Authority ceiling**（权限上限，只能收紧不能放宽）和**信息流标签**是 laos 里完全缺失的东西。

### D. 微内核路线 —— agentOS (seL4)

- [github.com/jordanhubbard/agentos](https://github.com/jordanhubbard/agentos)（Jordan Hubbard = FreeBSD 联合创始人）
- **可启动**，跑在 seL4（唯一形式化验证的能力安全微内核）上，QEMU 下已 boot-proven（含 Linux / FreeBSD 双 guest）
- 能力模型：**ToolCap / ModelCap / MemCap / MsgCap / StoreCap / SpawnCap / NetCap**
  —— **可委派但不可提升（delegatable but never escalatable）**，Agent 只能授予自己所持能力的子集
- Agent 身份 = Ed25519 密钥对，badge 由身份派生，**内核级验证发送者，不可伪造**
- 系统服务：CapStore / MsgBus / MemFS / ToolSvc（**MCP 兼容**）/ ModelSvc / NetStack / BlobSvc / LogSvc
- 最激进的设计：**vibe-coding layer** —— Agent 可以生成新的系统服务（文件系统、消息总线、工具注册表），验证后**热替换**而无需重启

**成熟度必须诚实标注**：README 自己分了 5 级证明（boot-proven / target-tested / host-tested / stubbed / planned），
大部分 agent 服务是 **host-tested scaffolding**，23 stars，alpha。
它的 README 里有一句尖锐的吐槽，值得记下：

> Every other "agent OS" is a Python framework running on Linux. ... **Boot it or it doesn't count.**

**判断**：L5 的唯一真实践。能力不可提升 + 形式化验证是终极答案，
但代价是放弃整个 Linux 生态，且目前离生产极远。同方向的还有 **Agate: Capability Microkernels**（华为 2012，SOSP AgenticOS 2026 lightning talk）。

### E. 新内核原语 —— fork / explore / commit

- [arXiv:2602.08199](https://arxiv.org/abs/2602.08199)，Cong Wang（Multikernel Technologies）+ Yusheng Zheng（UCSC）
- **branch context** 抽象：① COW 状态隔离（独立 fs 视图 + 进程组）② fork / explore / commit|abort 生命周期
  ③ **first-commit-wins**，兄弟分支自动失效 ④ 可嵌套
- 实现：**BranchFS**（FUSE，非 root，创建 < 350μs 且与基础文件系统大小无关）+ 提议中的 **`branch()` 系统调用**
- Python 库 `BranchContext` 已开源

**判断**：这是唯一一个"为 Agent 探索语义量身定做"的 OS 原语，也是最能直接补进 laos 的一块。
laos 目前的 `branch.py` 就是它的语义移植版（用 copytree 模拟 COW）。

### F. 沙箱 / 隔离执行层（不是 OS，但是 L4 强制力的来源）

- 商业/开源：E2B、Daytona、Modal、Firecracker microVM、gVisor
- 云原生：[kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) —— **Sandbox CRD**：单个有状态 Pod + 稳定身份 + 持久存储
- [AgentCube](https://xie.infoq.cn/article/4525c159cfb7895a6bc160a5b)：K8s 上的 Agent 工作负载运行时（Router / Workload Manager / PicoD）

**判断**：这一层是"Agent 执行不可信代码"的事实标准答案，但它只管**隔离**，不管**语义**（没有上下文管理、没有能力模型、没有分支）。
Linux AgentOS 应该把它当**底座**而不是**替代品**。

### G. 内存 / 上下文层次 —— 把 OS 虚拟内存搬进 Agent

- **MemGPT / Letta**：主上下文 = 内存，外存 = 磁盘，自带分页调度；memory blocks；sleeptime 后台学习
- AIOS Context Manager：上下文快照与恢复，支持中断后续跑
- HKU 的 *When Agent Context Goes Stale*：上下文与实际环境不一致的问题

**判断**：这是"上下文是新的内存"这条共识的源头。laos 的 `ContextManager`（窗口 + 摘要 + swap）就是这条线的简化版。

### H. 内核侧适配 —— 系统为 Agent 改 / Agent 管系统

- **SchedCP**（[arXiv:2509.01245](https://arxiv.org/abs/2509.01245)）：首个让 LLM Agent **通过 sched_ext 自主调优 Linux 调度器**的框架，把"优化什么"（AI 语义推理）与"如何观察执行"（系统安全执行）分离
- *Agentic AI is a Kernel Scheduling Problem*：工具调用让内核进入**推理关键路径**，最高杠杆的改动不是把 Agent 提到 RT 优先级
- **AgentProf**（UCSC + 阿里云 + HKUST）：Agent 的语义剖析
- *Preserving GPU Profiling Accuracy under Concurrent GPU-Coding Agent Workloads*（SJTU）

**判断**：SOSP 2026 AgenticOS Workshop 的主战场在这里。这些是"系统为 Agent 让路"的议题，与 Linux AgentOS 互补而非竞争。

---

## 3. 横向对比

| 变体 | 层次 | 强制力 | 上下文管理 | 分支/回滚 | 能力模型 | 生态兼容 | 成熟度 |
|---|---|---|---|---|---|---|---|
| **AIOS** | 用户态中间件 | L2 | ✅ 快照/恢复 | ❌ | Access Manager | ✅ 完全 | 可用 |
| **阿里云 Agentic OS** | 发行版 | L2+L4 | ✅ | ❌ | Skill 签名 | ⚠️ 绑发行版 | 产品化 |
| **Agent libOS** | libOS | L3 | ✅ Object Memory | ✅ checkpoint | ✅ 权威上限+信息流 | ✅ | 研究原型 |
| **agentOS (seL4)** | 微内核 | L5 | ✅ | 部分 | ✅ 不可提升能力 | ❌ 放弃 Linux | alpha |
| **BranchFS / branch()** | 内核原语 | L4/L5 | ❌ | ✅ **核心** | ❌ | ✅ | 研究原型 |
| **E2B / agent-sandbox** | 沙箱 | L4 | ❌ | ❌ | ❌ | ✅ | 生产可用 |
| **MemGPT / Letta** | 内存层 | L0 | ✅ **核心** | ❌ | ❌ | ✅ | 产品化 |
| **laos（本项目）** | 用户态薄内核 | L2（目标 L4） | ✅ 窗口+swap | ✅ first-commit-wins | ✅ 通配能力表 | ✅ | demo |

**没有任何一个变体同时覆盖了「能力模型 + 分支回滚 + 上下文管理 + L4 强制」。这就是空档。**

---

## 4. 对原命题的评估

> `Linux AgentOS = Linux kernel + Agent + MCP`

**成立，但需要补两个限定词才准确：**

```
Linux AgentOS = Linux kernel（L4 强制层）
              + 薄内核语义层（能力模型 + 分支 + 上下文 + 审计）
              + Agent（进程）
              + MCP（驱动总线 / syscall 约定）
```

三个必须补的点：

1. **MCP 只是驱动总线，不是内核。** 它定义了"怎么调"，没定义"能不能调"。
   laosd 这层薄内核存在的唯一理由就是补上 MCP 缺失的权限、审计、配额。
2. **必须显式接 L4。** 否则整个系统的安全性等价于"Agent 会不会听话"，即 L0。
   阿里云的 seccomp+bubblewrap、E2B 的 microVM 都是这个意思。**这是 laos 当前最大的缺口。**
3. **不可逆操作需要单独的预算。** 现有 laos 只有 syscall 次数预算（EDQUOT），
   但 `rm -rf /` 和 `ls` 消耗同样的一次预算显然荒谬。
   MPI-SWS 的 **Irreversibility Budget**（车队级风险记账与准入控制）是这个问题的正解。

---

## 5. laos 相对各变体的差距清单

| # | 缺口 | 现状 | 对标 | 优先级 |
|---|---|---|---|---|
| 1 | **强制隔离** | `sandbox.py` 封装了 unshare/cgroup，但**没接到驱动与 Agent 启动路径** | 阿里云 AgentSecCore、E2B | **P0** |
| 2 | **不可逆操作预算** | 只有 syscall 次数预算 | Irreversibility Budget（MPI-SWS） | **P0** |
| 3 | **权限上限 / 能力委派** | 静态能力表，无委派、无收紧 | Agent libOS 的 Task Authority ceiling | **P0** |
| 4 | **信息流控制** | 无 | Agent libOS 的标签传播 + Sink 注册 | P1 |
| 5 | **分支 O(1) 创建** | copytree（O(n)） | BranchFS（FUSE，<350μs） | P1 |
| 6 | **上下文一致性** | 只看 token 水位 | *When Agent Context Goes Stale*（HKU） | P1 |
| 7 | **语义可观测** | JSONL 审计 | AgentProf | P2 |
| 8 | **多 Agent IPC** | 共享文件系统 | agentOS MsgBus、A2A | P2 |

---

## 6. 参考

**论文**
- [AIOS: LLM Agent Operating System](https://arxiv.org/abs/2403.16971) — Rutgers
- [Agent libOS: A Runtime Substrate for Capability-Controlled Self-Evolving LLM Agents](https://arxiv.org/abs/2606.03895) — 清华
- [Fork, Explore, Commit: OS Primitives for Agentic Exploration](https://arxiv.org/abs/2602.08199) — Multikernel / UCSC
- [Towards Agentic OS: SchedCP](https://arxiv.org/abs/2509.01245) — LLM Agent 调优 Linux 调度器

**项目**
- [agiresearch/AIOS](https://github.com/agiresearch/AIOS) · [AIOS Docs](https://docs.aios.foundation/aios-docs)
- [alibaba/ANOLISA](https://github.com/alibaba/ANOLISA) — 阿里云 Agentic OS
- [jordanhubbard/agentos](https://github.com/jordanhubbard/agentos) — seL4 微内核路线
- [yingqi-z20/Agent-libOS](https://github.com/yingqi-z20/Agent-libOS)
- [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox)

**会议**
- [AgenticOS @ SOSP 2026](https://os-for-agent.github.io/) — 2nd Workshop on OS Design for AI Agents（2026-09-29）
