# AIOS 深度调研与分析

> 调研时间：2026-08-31
> 对象：[AIOS: LLM Agent Operating System](https://arxiv.org/abs/2403.16971)（Rutgers，arXiv:2403.16971v5，2025-08-12）
> + 实现仓库 [agiresearch/AIOS](https://github.com/agiresearch/AIOS)（v0.2.2，859 commits，2025-07 后基本停更功能）
> + 官方文档 [AIOS Docs](https://docs.aios.foundation/aios-docs)
> 目的：把 AIOS 的内部机制拆到能直接对比 laos 的程度，找出"它验证了什么、它缺了什么"。

---

## 1. AIOS 到底是什么

一句话：**AIOS 是"Agent 资源管理器"，不是"管理 Agent 操作的操作系统"。**

它把 LLM / 内存 / 存储 / 工具 / 权限当成**资源**来调度，封装一个叫 AIOS Kernel 的抽象层架在 OS 内核之上，再给一个 SDK（Cerebrum）让 agent 调用。三层：

```
Application Layer  ── AIOS SDK (Cerebrum) ── 原生 agent + ReAct/Reflexion/AutoGen/Open-Interpreter/MetaGPT 适配器
Kernel Layer      ── AIOS Kernel ── LLM Core / Scheduler / Context / Memory / Storage / Tool / Access
Hardware Layer    ── CPU/GPU/内存/磁盘（AIOS 通过 OS syscall 间接访问）
```

**最关键的判断（理解了这点后面全通）**：AIOS 假设 Agent 已经跑在一个**可信的操作系统**里，它只在"Agent 内部资源"这一层做编排。它**完全不管理 Agent 对宿主机的操作**（文件、进程、网络、算力隔离）。这与 laos 恰好相反——laos 管"Agent 怎么安全地操作这个操作系统"，把 LLM 当成黑盒。

=> **AIOS 与 laos 是互补关系，不是竞争关系。** 这个结论是本调研最重要的产出。

---

## 2. AIOS Kernel 七大模块（含真实接口）

| 模块 | 职责 | 关键类 / 方法 | 对 laos 的意义 |
|---|---|---|---|
| **LLM Core** | 把不同部署的 LLM 封装成"核"（类 CPU core），统一推理接口 | `LLMAdapter.execute_llm_syscall / get_model_response / process_response` | laos 的 `Brain` 是同一个抽象，但 laos 不调度它 |
| **Scheduler** | 集中管理所有模块队列，分发 syscall | `BaseScheduler.process_llm_requests / process_memory_requests / start / stop` | laos 当前是全局锁，可借鉴其公平调度 |
| **Context Manager** | LLM 推理中途**抢占**（快照/恢复），实现多任务 | `SimpleContextManager.generate_response_with_interruption / load_context / clear_context` | laos 的 `ContextManager` 是窗口换页，应加抢占快照 |
| **Memory Manager** | 运行时交互历史，RAM 分配，LRU-K 淘汰到磁盘 | `BaseMemoryManager.add/remove/update/retrieve_memory` | laos 无独立 memory，依赖 LLM 上下文 |
| **Storage Manager** | 持久化（文件/知识库/向量库 chromadb），**版本回滚、共享** | `StorageManager.sto_create_file/mount/write/retrieve/rollback/share` | laos 的 branch 是更激进的回滚（先写分支再 commit） |
| **Tool Manager** | 动态加载工具，参数校验（**文档未提**），防并行冲突 | `ToolManager.load_tool_instance / execute_tool_syscall`，`tool_conflict_map`（hashmap 互斥） | **laos 同样缺参数校验，应补** |
| **Access Manager** | 跨 agent 访问控制（特权组）+ 不可逆操作人工确认 | `AccessManager.add_privilege / check_access / ask_permission` | laos 应借鉴，但要做成**强制**而非提示 |

---

## 3. AIOS Syscall 全集（论文 Table 2）

**共 7 类、约 24 条。全部是"调用内核服务的库调用"，没有任何 POSIX 风格的世界操作。**

| 模块 | syscall |
|---|---|
| LLM Core | `execute_llm_syscall`, `get_model_response`, `process_model_response` |
| Scheduler | `execute_syscall`, `start`, `stop` |
| Context Manager | `generate_response_with_interruption`, `load_context`, `clear_context` |
| Memory Manager | `execute_memory_syscall`, `add_memory`, `remove_memory`, `update_memory`, `retrieve_memory` |
| Storage Manager | `execute_storage_syscall`, `sto_create_file`, `sto_create_directory`, `sto_mount`, `sto_write`, `sto_retrieve`, `sto_rollback`, `sto_share` |
| Tool Manager | `execute_tool_syscall`, `load_tool_instance` |
| Access Manager | `add_privilege`, `check_access`, `ask_permission` |

每条 syscall 绑一个 `SysCall` 线程（`__init__(agent_name, query)`），带 `event / pid / aid / status / response / time_limit / priority` 字段。
`Query` 对象带 `target` 路由属性，分发到对应模块队列。

**对比 laos 的 syscall**：

| | AIOS | laos |
|---|---|---|
| 语义 | 调用一个内核服务（高级库调用） | 执行一个受控操作（POSIX 风格） |
| 对象 | LLM / Memory / Storage / Tool 抽象 | `fs.read` / `proc.exec` / `sys.info` 等世界操作 |
| 约束 | 跨 agent 资源读写 | 每条 syscall 经能力表，内核可拒绝（EPERM） |
| 拒绝 | 跨 agent 越权才拒 | 无能力即拒，且驱动可再拦（EDENIED） |

AIOS 的 syscall 集合**证明了"Agent 内部资源需要 OS 化调度"**；laos 的 syscall 集合**证明了"Agent 对世界的操作需要 OS 化约束"**。两边合起来才是完整图景。

---

## 4. 三大机制深入剖析

### 4.1 Scheduler —— 调度的是"LLM 推理请求"，不是 CPU

- 策略：FIFO / RR（时间片轮转）/ 可扩展优先级（论文实验只跑了 FIFO 与 RR）
- 机制：agent 查询拆成多个 `SysCall` 线程，Scheduler 把它们排进各模块队列，按策略分发
- 论文数据（表 6）：FIFO 总执行 74.2s，RR 77.3s，无 AIOS 152.1s —— AIOS 把多 agent 的 LLM 调用**批处理/复用**，吞吐翻倍
- **本质**：这是"LLM 推理调度"（解决"很多 agent 抢一个 LLM"的排队），**不是 OS 进程调度**。它优化的是 token 吞吐与等待延迟，不是 CPU 时间片。

### 4.2 Context Manager —— LLM 解码中途的抢占

- 问题：长生成任务占着 LLM core，其他 agent 饿死
- 解决：在分配的时间片内至少解码一个 token 后捕获状态，时间片到就**挂起**，让给别人；恢复时重载快照继续
- 两种快照：
  - **text-based**（闭源 LLM，无 logits）：保存已解码输出
  - **logits-based**（开源 LLM）：保存中间搜索树（beam search），恢复时重载继续生成
- 论文数据（表 7）：切换前后 BLEU/BERT 相似度 **1.0** —— 抢占零质量损失
- **本质**：这是"LLM 生成的协作式多任务"，类比 OS 的**协程/时间片**，不是进程上下文切换。但它解决的真问题和 OS 上下文切换一模一样：**在多个任务间公平复用稀缺算力（LLM core）**。

### 4.3 Access Manager —— 跨 agent 权限 + 人工确认

- **强制部分**：每个 agent 映射到一个特权组（hashmap `agent_id → group`）。agent 要读写**别的 agent** 的内存/LLM 历史/工具日志，必须同组，`check_access` 查表拦截。文档明确这是**内核强制**。
- **提示部分**：删除 / 覆盖 / 特权变更等**不可逆操作**，触发 `ask_permission` 弹窗让用户确认。这是**防御性提示，不自动拒绝 syscall**。
- **诚实标注**：文档说 "access manager still under development"，静态 ACL / 动态 ACL 都标 **TBD**。

**关键缺陷**：这套权限**只管"agent 之间的资源"**，**完全不管"agent 对宿主机的操作"**。一个 agent 要是能调用 shell 工具，Access Manager 拦不住它 `rm -rf /`。

---

## 5. 安全模型：AIOS 最该被正视的三个洞

### 洞 1：Tool Manager 没有参数校验，也没有任何沙箱

官方 Tools 文档给出的 `address_request` 代码（`docs/aios-docs/aios-kernel/tools`）：

```python
tool_org_and_name, tool_params = (tool_call["name"], tool_call["parameters"])
tool = self.load_tool_instance(tool_org_and_name)
tool_result = tool.run(params=tool_params)   # 原样传入，无校验
```

- 文档**未提及任何参数校验逻辑**（"未提及任何参数校验逻辑"）
- `tool_conflict_map` 只是"同一工具名执行期间互斥"，是**资源调度**约束，**不是安全约束**
- 文档**未定义任何安全/沙箱/权限边界**（"未提及任何安全隔离、沙箱、权限管控或代码执行边界限制"）

### 洞 2：没有 L4 强制隔离

- 全仓库（论文 + 代码 + 文档）**找不到 namespace / cgroup / seccomp / landlock** 的任何一处
- 隔离只存在于"跨 agent 资源"（内存/LLM 历史/工具日志）—— 假设宿主 OS 可信
- MCP Server 只在 computer-use 架构里出现，且是**实验性**沙箱（LiteCUA 论文，2025-05）

### 洞 3：不可逆操作靠"问用户"，不靠强制

`ask_permission` 是提示性的。Agent 在自主循环里运行（ReAct 多步），人类的"确认弹窗"要么打断自主流程，要么被默认放行。**这与 Agent libOS 的"权限上限只能收紧"和"一次性人类释放"形成鲜明对比**——AIOS 没有"权限上限"概念，只有"同组才可见"。

### 一句话总结 AIOS 的安全姿态

> 它对"agent 之间"做了内核强制，对"agent 对宿主机的操作"几乎零防御。
> 它是 **L2 的资源调度器**，不是 **L4 的执行沙箱**。

（详见 `docs/research/agentos-landscape-2026-08.md` 的强制力光谱。）

---

## 6. AIOS vs laos：本质对比与互补

| 维度 | AIOS | laos |
|---|---|---|
| 抽象目标 | Agent 内部资源编排 | Agent 对世界的操作约束 |
| syscall 语义 | 调内核服务（库调用） | 执行受控操作（POSIX 风格） |
| syscall 对象 | LLM/Memory/Storage/Tool | fs/proc/sys 等世界操作 |
| 调度对象 | LLM 推理请求排队 | （laos 目前全局锁轮转） |
| 上下文抢占 | LLM 解码中途快照（BLEU=1.0） | 窗口换页 + swap（无抢占） |
| 权限强制 | 跨 agent 特权组（仅 agent 间） | 每条 syscall 能力表（世界操作） |
| 不可逆操作 | `ask_permission` 人工提示 | `EDENIED` 驱动拦截 + `EDQUOT` 预算 |
| 强制层 | L2（无 L4 隔离） | L2（目标 L4） |
| 隔离 | 无宿主隔离 | 设计上接 namespace/cgroup/seccomp |

**结论**：AIOS 验证了"Agent 内部资源需要 OS 化调度"（Scheduler/Context/Access 三大机制都成立且论文有数据支撑）。
laos 验证了"Agent 对世界的操作需要 OS 化约束"（能力表/驱动/分支/审计）。
**一个补另一个的洞。理想形态 = AIOS 的资源调度层 + laos 的强制执行层。**

---

## 7. 对 laos 的具体启示（要补什么 / 不要重复什么）

**要借鉴 AIOS 已验证的机制（以可强制方式重写）**：

1. **上下文抢占快照**：AIOS 证明"LLM 生成中途挂起零质量损失"可行。laos 的 `ContextManager` 应加 `save(pid)` / `restore(pid)`，让一个 agent 在预算耗尽时被挂起、换个 agent 跑，再恢复。
2. **LLM 推理调度**：laos 当前 `kernel.scheduler_ctx()` 是全局锁 + 轮转。应升级为带**优先级 + 预算轮转**的 Scheduler，让多个 agent 公平复用 Brain。
3. **跨 agent 权限**：AIOS 的特权组是好的起点，但 laos 应做成 **capability**（可委派不可提升），而非"同组即可见"。
4. **不可逆操作准入**：把 AIOS 的 `ask_permission`（提示）升级为 laos 的 **irreversibility budget + 人类一次性释放**（学 Agent libOS），高危操作超预算必须人类确认。

**要补 AIOS 明确缺失的（laos 相对它的最大差异化价值）**：

5. **工具调用参数校验**：AIOS Tool Manager 的洞，laos 也有——driver 只做路径 jail，没做**语义校验**。应加一层 schema + 语义围栏。
6. **强制隔离**：把 `sandbox.py` 真正接到驱动与 `proc.exec`，让 laos 落在 L4，而不是停在 L2。

**不要重复 AIOS**：不要去重写 LLM Core 的推理批处理——那是 AIOS 的主场，laos 用 Brain 黑盒即可。laos 的价值在"强制层"，不在"推理编排层"。

---

## 8. 参考

- 论文：[arXiv:2403.16971v5](https://arxiv.org/abs/2403.16971)（COLM 2025 接收）
- 仓库：[agiresearch/AIOS](https://github.com/agiresearch/AIOS)（v0.2.2）
- SDK：[agiresearch/Cerebrum](https://github.com/agiresearch/Cerebrum)
- 文档：[AIOS Docs](https://docs.aios.foundation/aios-docs)（Syscalls / Tools / Access / Context 各页）
- 实验性 Rust 重写：`aios-rs/`（占位实现，未功能对等）
