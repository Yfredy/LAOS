# laos 下一步机会清单 —— 基于 2026-09 最新论文与开源生态的调研

> 调研日期：2026-09-05。基线：laos 已完成语义内核（PCB/能力表/syscall 网关/审计/调度）、
> 参数校验、不可逆闸门 v1、上下文分页、seccomp+unshare+cgroup 强制隔离、hardlink COW 分支、
> eBPF syscall profiling（见 master 分支 28d1a3e）。
> 本文回答：对照最新论文与开源项目，laos 还有什么可做之处，按优先级排序。

## 一、外部世界的三个最新信号

### 1. MCP 2026-07-28 规范 —— 驱动总线的大版本

laos 的 `laos/mcp.py` 实现的是 **2025-06-18** 子集（initialize / tools/list / tools/call）。
最新规范（[spec](https://modelcontextprotocol.io/specification/2026-07-28)、
[官方公告](https://blog.modelcontextprotocol.io/posts/2026-07-28/)）新增：

- **Tasks**：长耗时/异步工作成为可追踪的一等协议对象 —— 直接对应 laos 的两个痛点：
  驱动单工 stdio 串行（`_driver_locks` 互斥）使长 syscall 阻塞同驱动全部调用；
  分支探索/提交等长操作没有协议级任务句柄。
- **Elicitation**：server 执行中经 client 向用户要输入 —— laos 的 `kernel.confirm`
  （CLI input hack）可以规范化为协议内 elicitation。
- **MRTR（多往返请求）**、**stateless-first** 架构、**Sampling 弃用**、扩展机制与直接发现。

### 2. AgenticOS @ SOSP 2026 —— 完整论文名单（[workshop 页](https://os-for-agent.github.io/)）

| 论文 | 对 laos 的含义 |
|---|---|
| **The Irreversibility Budget**（Mohammadi, Bindschaedler, MPI-SWS） | laos 现有闸门只有"每 syscall 计 1"的全局计数；论文要求**按工具加权、按 agent/车队两级记账、spawn 时准入控制**。数据模型（ToolSpec.reversible/risk）已在，是最快见效的一条 |
| **Patient Bytes**（Berkeley/UIUC/USI） | 可靠性预算调度：调度优先级应由错误率/拒绝率动态决定 —— laos 的 `AgentScheduler` 目前只有 token 预算 + 静态优先级 |
| **When Agent Context Goes Stale**（HKU） | 上下文陈旧检测 —— laos 独有优势：branch diff 机制就是"世界变了什么"的权威来源，`fs.read` 进上下文时记 (path, hash)，commit/外部写后即可精确标记 stale 并强制重读 |
| **AgentProf**（UCSC/HKUST/阿里云） | 语义剖析 —— laos 已有系统级真相（eBPF syscall 分布）+ 全量审计，缺语义层：每步意图、工具选择是否合理、重试/拒绝模式的 span 化 + OpenTelemetry 导出 |
| **Externalization Barriers**（MPI-SWS） | "不可信探索"的 OS 抽象 —— laos 的分支 + seccomp 组合正是该思想的实例化；理论支撑可反哺分支语义（探索期免计风险、commit 时结算） |
| Isolation in the Age of Agents（UW-Madison）/ Agent libOS（清华）/ Agate（华为） | 能力控制 libOS / 微内核作为 substrate —— 印证 laos 能力表路线，暂无直接可搬运机制 |
| 意图驱动能力（Oracle Labs lightning） | 能力应随任务意图收窄：spawn 时按任务声明把 `fs.*` 收窄到具体路径前缀 —— laos 能力表是静态声明，可加"任务级收窄" |
| Formal Methods as the Harness / An AgentOS Needs a Formal Representation of Agents | 形式化方向，记录备查，暂不适合 laos 阶段 |

**显著空白**：CFP 列了 *inter-agent communication / agent reliability*，但没有任何被接收论文
正面处理多 Agent 通信 —— laos 的"内核 IPC（msg.* syscalls + 运行时能力委托）"是一条
少有人占的路。

### 3. Memory OS 与沙箱生态

- **MemOS**（[arXiv:2507.03724](https://arxiv.org/abs/2507.03724)，
  [MemTensor/MemOS](https://github.com/MemTensor/MemOS)）：MemCube 统一记忆抽象 +
  MemScheduler 在参数级/激活级/明文记忆间调度。laos 的 `context.py` 只有
  窗口+摘要+swap，对应 MemGPT 的虚拟上下文层；升级路径是加一层
  `mem.*` 驱动（episodic JSONL + 关键词检索，零依赖约束下可做）。
- 沙箱生态（[Northflank 深度](https://northflank.com/blog/how-to-sandbox-ai-agents)、
  [arXiv:2606.08433 安全对比研究](https://arxiv.org/html/2606.08433v1)）：
  gVisor/Firecracker microVM 是主流后端，seccomp/Landlock 定位为纵深防御的堆叠层 ——
  laos 的 `Sandbox` 可以做成可插拔 backend（host → unshare+seccomp → gVisor），
  而不是自建 microVM。

## 二、机会清单（按建议顺序）

| # | 机会 | 来源 | 规模 | 一句话设计 |
|---|---|---|---|---|
| 1 | **Irreversibility Budget 2.0**：加权 + 两级记账 + 准入控制 | SOSP'26 论文 | M | `ToolSpec.irreversibility_cost`；`FleetLedger`（车队账本+保留水位）；spawn 准入；kill 不退款；`laosctl budget`。**已有实施计划** |
| 2 | **Stale context 检测** | HKU 论文 | S | `ContextManager.mark_fresh(path, hash)`；syscall 后对上下文引用过的文件做 diff；stale → 注入 "context stale, re-read" 系统消息 |
| 3 | **AgentProf span 化 + OTel 导出** | SOSP'26 论文 | S/M | audit.jsonl 的 syscall 事件聚合成 step span（意图/thinking、tool、ret、ms、tokens、denied）；OTel JSON 导出器（零依赖手写 OTLP/JSON） |
| 4 | **MCP 2026-07-28 升级** | MCP 规范 | M | `mcp.py` 支持 Tasks（长 syscall 异步化，解 single-driver 串行）+ Elicitation（confirm 规范化）；stateless 模式作为驱动可选 |
| 5 | **内核 IPC**：`msg.send/recv/list` syscalls + 运行时能力委托 | CFP 空白 | M/L | 新驱动 `drv_ipc`（内核内消息表，带能力检查与配额）；委托深化：agent 运行中可把自身 caps 子集授予指定 pid |
| 6 | **可靠性预算调度** | Patient Bytes | S | `AgentScheduler` 增加 per-pid 错误预算：EIO/denial 率高的 agent 降优先级/挂起 |
| 7 | **意图→能力收窄** | Oracle Labs | S | spawn 增 `task_scope`：把 `fs.*` 收窄为具体前缀集合，内核在 jail.resolve 后再对一次 scope |
| 8 | **mem.* 记忆分层** | MemOS/MemCube | L | episodic/semantic 两层 JSONL 记忆驱动 + 检索 syscall；MemScheduler 式选择策略 |
| 9 | **隔离后端可插拔** | 沙箱生态 | L | `Sandbox` backend 抽象：host / unshare+seccomp（现状）/ gVisor（runsc 包装），报告层标注 |
| 10 | **FUSE BranchFS** | arXiv:2602.08199 | L | 仍是长期项；hardlink COW 已覆盖语义，FUSE 换取真 O(1) 与原生 rename 语义 |
| 11 | 形式化 agent 模型 | 南大/CAS | research | 记录 |

## 三、建议路线

**1 → 2 → 3 → 4 → 5**。理由：#1 数据模型与论文都在，计划已成文；
#2/#3 是复用刚落地的 diff/审计/eBPF 的小步快跑；#4 是协议大版本，宜在语义层
稳定后做（Tasks 会改变 syscall 网关的同步语义）；#5 是生态空白，
适合作为有论文潜力的方向压轴。

## 参考来源

- [AgenticOS @ SOSP 2026 workshop（完整名单）](https://os-for-agent.github.io/)
- [MCP 2026-07-28 规范](https://modelcontextprotocol.io/specification/2026-07-28) /
  [官方博客](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [MemOS: arXiv:2507.03724](https://arxiv.org/abs/2507.03724) /
  [MemTensor/MemOS](https://github.com/MemTensor/MemOS) /
  [MemoryOS: arXiv:2506.06326](https://arxiv.org/html/2506.06326v1)
- [How to sandbox AI agents in 2026 (Northflank)](https://northflank.com/blog/how-to-sandbox-ai-agents) /
  [AI Code Sandboxes 安全对比 arXiv:2606.08433](https://arxiv.org/html/2606.08433v1)
- [AIOS（Rutgers, arXiv:2403.16971）](https://arxiv.org/abs/2403.16971) /
  [agiresearch/AIOS](https://github.com/agiresearch/AIOS)
