# AIOS / AgentOS 格局 · Linux 原生路线 · 全天候录音 —— 三轨全景调研

> 2026-10-08 · 三路并行调研（每路独立溯源核实：官方文档/论文/源码一手优先，媒体二手标注，未证实项明示）
> 基线：[aios-deep-dive-2026-08.md](aios-deep-dive-2026-08.md)（AIOS 内部机制拆解）+ [always-on-recording-industry-2026-09.md](always-on-recording-industry-2026-09.md)（全天候行业图谱）——本轮为两者之后的增量与扩展
> 产出物：本报告（认知）+ [plans 实施计划](../superpowers/plans/2026-10-08-agentos-demo.md)（demo，kernel+Agent+MCP）

## 1. 三轨各一句话

1. **AIOS/AgentOS**：名号泛滥但实质收敛——所有叫 "Agent OS" 的知名项目都在用户态模拟 OS 概念，商用大厂没有一家用 OS 隐喻（他们叫 containment / orchestration）；MCP 已成事实上的 agent syscall 层。
2. **Linux 原生路线**：真内核碎片全部就绪（sched_ext / eBPF 观测 / Landlock / seccomp-bwrap / systemd-MCP / 规范背书的 unix socket transport）但**无人拼装**；"几百行讲清 agent-OS"的教学 demo 是空白——恰是 laos demo 的位置。
3. **全天候录音**：技术已不是瓶颈（端侧 ASR/摘要/声纹过滤全部就绪），瓶颈是**社会许可+价值密度**；2026-09 苹果入场（不留音频+Secure Exclave 隔离）把 ambient listening 从创业赌局变成 OS 标配赛道——范式与 laos 的"显式 syscall+全本地"红线同频。

## 2. 轨道一：AIOS / AgentOS 主流方式

### 2.1 学术线

- **Rutgers AIOS**（[arXiv:2403.16971](https://arxiv.org/abs/2403.16971)，COLM 2025 全文）：仓库 6.5k★、最后提交 2026-07-20（近两月做 Mem0 记忆隔离）；发版止于 v0.3.0，**无 v1/v2**；部署形态五档（Local → Personal Remote **Virtual** Kernel 一机多个人内核）。
- **"AgentOS" 名号 2026 年已被论文圈挤爆**：UFO²（微软桌面 AgentOS，arXiv:2504.14603）、Liu et al. AgentOS（2603.08938）、Architecting AgentOS（2602.20934）、ABot-AgentOS（2607.10350，机器人）、HoloAgent-0（2606.23565，具身）——同名不同义，无一是内核级。
- **IBM 系统性论述**：Steinder & Franke《Towards an Agent Operating System – Lessons from Classical and Cloud OS》（arXiv:2607.25076，ICWS 2026）——大厂对"agent 需要什么 OS 抽象"的论文层回答。
- 记忆侧：MemOS（arXiv:2507.03724，记忆当一等 OS 资源）；综述 OS Agents（arXiv:2508.04482）。
- **内核侧语义缺口有人指出没人填**：Towards Agentic OS（arXiv:2509.01245）指调度器与 agent 存在 semantic gap；Understanding and Controlling OS Resources of AI Agents（arXiv:2602.09345）。

### 2.2 开源线（2026-10-08 快照，逐仓核实）

| 项目 | 数据 | 现状判定 |
|---|---|---|
| agiresearch/AIOS | 6.5k★ | 用户态 "kernel" 库；活跃但慢 |
| builde rmethods/agent-os | 5.5k★ | **已转型 spec-driven 开发工具**，不再讲 kernel/syscalls |
| letta-ai/letta（原 MemGPT） | 25.1k★ | README 已弃用 OS 隐喻，主力迁 letta-code |
| microsoft/UFO | 10.0k★ | Windows 桌面 AgentOS（UIA/Win32 深绑） |
| openclaw/openclaw | 现象级 | 自托管常驻个人 agent（IM 为 UI）；个人侧真正聚集人群处 |
| topics/agentos | 65 仓 | 头部仅 2.2k★——**赛道碎片化，无事实标准** |

### 2.3 商用线

- **OpenAI**：AgentKit（2025-10 DevDay，Connector Registry 支持 MCP）；运行时收敛为统一桌面 App（Atlas 独立浏览器 2026-08 停更并入）。
- **Anthropic（最有信息量的一手）**：2026-05 工程博客《How we contain Claude》——三级 containment：claude.ai 代码执行=gVisor+seccomp 容器；Claude Code=Seatbelt/bubblewrap 进程沙箱（网络默认全禁）；**Claude Cowork=本地独立内核 VM**（工作区挂载+egress allowlist）。实测数据：权限弹窗用户批准率 93%；钓鱼演练 25 次重试 24 次外泄成功，靠 egress+文件系统边界拦住。开源 sandbox-runtime（srt，~5.5k★，当天仍在提交）。**结论：Anthropic 在做操作系统的隔离原语选型，只是拒绝叫 OS。**
- **Google**：ADK+Agents CLI；Gemini CLI 107.3k★ 内建 MCP client+server；Mariner 2026-05 停更并入 AI Mode。
- **微软**：SK+AutoGen 合并为 Agent Framework（2026-04 GA，14.0k★）。
- **国内**：Coze Studio 21.7k★ / Dify 158.1k★——**全部"平台/工作流"叙事，无 OS 隐喻**。

### 2.4 MCP 生态

- 最新 spec **2026-07-28**：协议改无状态、每请求能力协商；新增 Tasks/Skills/Apps 扩展；**unix socket 传输被规范原文背书**（"SHOULD reuse the stdio framing"）。
- 官方 registry 上线；规模二手口径 2026-04 约 9,652 个 latest server 记录；awesome-mcp-servers 95.9k★。
- **OS 厂商入场**：RHEL 10 官方 `linux-mcp-server`（Developer Preview，默认只读，暴露 systemd/journald/存储诊断）；openSUSE `systemd-mcp`（直链 systemd C API，polkit 授权）。
- 四个官方 SDK（Python 24.5k★/TS 13.5k★/Go 5.2k★/Rust 4k★）全部活跃；姊妹协议 A2A（agent 间 IPC）2026-03 v1.0，转入 Agentic AI Foundation。

### 2.5 四派判定（2026 年"给 Agent 做操作系统"的路径）

| 派 | 代表 | 与内核的距离 |
|---|---|---|
| (a) Framework/SDK 派（最主流） | LangGraph 42.9k★、MS Agent Framework、ADK、AgentKit、Coze/Dify | 纯用户态编排，**刻意回避 OS 隐喻** |
| (b) 沙箱/VM 派 | Anthropic 三级 containment、E2B（Firecracker microVM 快照恢复）、microsandbox | 隐性 OS 化——做的是隔离原语选型；**"隔离 Agent"而非"以内核治理 Agent"** |
| (c) **OS 内核派（空位）** | 学术（AIOS 模拟、UFO²、两篇 semantic-gap 论文）+ 厂商工具化（RHEL/openSUSE 的 OS-MCP） | **无主流内核为 agent 改动；位置空着** |
| (d) 端侧/常驻派 | OpenClaw、Claude Cowork、ChatGPT 桌面 App、Gemini CLI | 形态在端侧，治理沿用 (b) |

底座共识：MCP=syscall/ABI 层，A2A=IPC 层——**没有派别再自造工具协议**。

## 3. 轨道二：Linux 原生路线（demo 可行性）

### 3.1 源码级铁证：AIOS 是模拟

读取 [aios/scheduler/base.py](https://raw.githubusercontent.com/agiresearch/AIOS/main/aios/scheduler/base.py)：`from threading import Thread`、`self.processing_threads: Dict[str, Thread]`——FCFS/Round-Robin 都在**线程间**轮转 agent 上下文；全文无 multiprocessing/os.fork/cgroup/systemd。**"Agent OS"的调度器离内核隔着一整个用户态。**

### 3.2 真内核碎片清单（全部有活跃先例）

| 碎片 | 做法 | 关键事实 |
|---|---|---|
| **sched_ext** | BPF 可扩展调度器（内核 6.12 合并） | scx 调度器集合；**SchedCP**（eunomia-bpf，NeurIPS 2025，arXiv:2509.01245）：LLM agent 经 MCP server `list/run/stop_scheduler` 甚至**合成 sched_ext 调度器**，失败自动回退 CFS——与"Linux AgentOS"愿景直接同构的最强先例 |
| **eBPF 观测** | AgentSight（arXiv:2508.02736） | TLS 边界拦截 LLM 流量+进程树关联，开销 <3% CPU，支持 Claude Code/Codex/Cursor |
| **Landlock 强制** | nono（nolabs-ai，Sigstore 系） | **每次工具调用**一个临时微沙箱+凭据幻影化+Merkle 审计链 |
| **seccomp/bwrap** | Anthropic sandbox-runtime | bwrap+netns+seccomp-BPF 封 unix socket（只放行到代理 socket）；官方数据：沙箱使权限弹窗减少 84% |
| **systemd↔MCP** | openSUSE/systemd-mcp、RHEL linux-mcp-server | systemd C API 直链 polkit 授权；RHEL 开发者预览 |
| **unix socket transport** | MCP 2026-07-28 spec | 规范背书 custom transport 复用 stdio framing → **socket-activated MCP 服务在协议层合法且无人做** |

### 3.3 三个空白点（demo 的差异化依据）

1. **"几百行讲清 agent-OS"的教学 demo 不存在**——检索只命中 agent loop 教程（REPL+工具调用），无一把 loop 接到真实 Linux 原语（HN 亦有"缺严肃 internals 教程"抱怨）。
2. **socket-activated MCP 服务（systemd `ListenStream=`+fd 继承）无公开案例**。
3. **cgroup v3 专用于 agent 计账/治理无开源项目**（只有 microVM 内资源限制和 systemd slice 常规用法）。

### 3.4 竞品离内核距离分层

L0 内核原语直用（SchedCP/AgentSight/nono/srt）→ L1 microVM（E2B/Firecracker/microsandbox）→ L2 用户态内核（gVisor）→ L3 推理编排"OS"（NVIDIA Dynamo——调度 GPU 推理请求，"inference OS for AI factories"）。**真正住在内核里的只有 eBPF 系与 Landlock 系；商业竞品是"隔离 Agent"不是"治理 Agent"。**（io_uring 在沙箱语境是著名逃逸面，普遍被 seccomp 封禁——demo 叙事素材。）

## 4. 轨道三：全天候录音（2026-09→10 增量深调研）

### 4.1 最大变量：苹果入场（2026-09-14 Newsroom + 隐私白皮书）

Apple Watch **Audio Intelligence**：Live Rewind（回看 15 秒逐字转写，触发强制提示音）+ **Siri Recap（ambient listening 生成高层次笔记）** + Sound Recognition（听障辅助）。隐私架构=**不留任何音频**：原始音频在 S11 Secure Exclave 硬件隔离区内处理完即删，文本 E2E 加密；按场景开关；刻意排除财务/证件号。限制：仅新表、年末英语 beta、EU/中国初期不可用。舆论分裂（PCMag "间谍设备" vs TechCrunch "新常态"）+ **法律真空**（只存文字不存音频，法庭无先例）。判定：**苹果定义了"可接受的 ambient"范式——2027 全行业合规基准线。**

### 4.2 硬件层存亡（相对 2026-09 基线的更新）

| 玩家 | 状态 | 关键数字 |
|---|---|---|
| Limitless→Meta | 2025-12 收购，Pendant 停售 | Meta 自研 pendant 计划曝光（2026-05 路透） |
| Friend 2 | 活着，转 AI 陪伴 | $249+OpenAI 实时语音；热度营销>规模化 |
| Amazon Bee | 巨头低价试探 | $49.99+免订阅；**默认非 always-on**（按键+绿灯） |
| **Plaud** | **唯一做出彩** | **100 万台**（2025-07）、年营收 $1-2.5 亿口径——公式=按钮显式记录+会议场景+企业付费 |
| Taya | 新形态 | $5M 种子；**注册声纹只录自己**（single-player） |
| Omi | 开源 | 13.7k★；可自托管 |
| Ray-Ban Meta Audio | 2026-09 发布 | $349 纯音频眼镜；现款 Live AI 仅 ~30 分钟续航 |

### 4.3 技术已非瓶颈的证据链

- 端侧 ASR：Moonshine（27M/61M）树莓派 5 RTF<1.0 纯 CPU；whisper.cpp 中端安卓 RTF 40-70%。
- 端侧摘要：旗舰 NPU prefill 1k-11k tok/s——30 分钟会议转写摘要秒级（mllm-NPU ASPLOS'25）。
- **TSE（目标说话人提取）学术已热**：NeurIPS 2025、REAL-TSE Challenge（SLT 2026）、Interspeech 2025 低延迟单通道——产品化边缘（Taya 卖点/苹果反其道不区分说话人）。
- 开源侧**没有主流 always-on 项目**——收敛在显式触发侧，印证"障碍不在代码在默认值"。

### 4.4 为什么没人做出彩（七因，按证据强度）

① 社会许可>技术（Recall 延期两年/Friend 被涂鸦/苹果也要提示音+白皮书先行）；② 形态因子错配（挂件要求换搭，眼镜/手表是既存习惯）；③ 价值密度低+killer workflow 缺位（会议纪要已商品化）；④ always-on 三杀（电池/误触发/他人在场）；⑤ 法律碎片化（13 个全方同意州+可穿戴录音刑法推进中）；⑥ 创业公司教育市场、巨头收获（Limitless→Meta/Bee→Amazon/io→OpenAI）；⑦ **可信中立性缺失**（用户数据归大厂引发反弹——本地优先/开源的空位）。

### 4.5 破局信号 × laos 对位

laos 既有红线（录音只由显式 syscall 触发/LAOS_REC=0 全局禁录/ASR 全本地）与 2026 前沿**完全同频**：苹果范式=不留音频+硬件隔离+提示音；Taya 范式=只录自己（声纹过滤）；Plaud 公式=显式按钮+窄场景。**空缺位恰是"数据不进大厂"的本地优先方案**——与 laos 听觉栈（wakegate 只认 KWS、KWS 实测 7.56ms、AlwaysOnRec 双沙箱）逐条对上。

## 5. laos 定位综合判定（三轨交叉）

1. **叙事被独立印证**：Karpathy 的"Agent=进程"论、IBM 的 OS 抽象论文、Anthropic 的 containment 工程、SchedCP 的 MCP→内核闭环——四条独立线索都指向"agent 需要内核级治理"，但**没有人在做整体**（AIOS 是 threading 模拟；厂商只做隔离或只做工具暴露）。
2. **"给 AI Agent 装操作系统"的主客反转没人做也做不成**（大厂已用脚投票：全部 platform/framework 叙事）——laos 的"内核治理在用户态延伸"叙事恰在空位 (c) 派上，且已有 RHEL Developer Preview 作为同路人。
3. **demo 的差异化**：不是又一个 agent framework，而是**把真内核碎片按治理的本来位置拼回去的最小教学演示**——每个部件都有已验证先例（SchedCP/systemd-mcp/nono/srt），整体无人做过。
4. **全天候录音**：laos 红线设计与苹果 2026-09 范式同频；差异化=本地优先+声纹过滤+syscall 显式触发——三者 2026 都被验证为正确方向。

## 6. demo 设计（实施计划的 spec）

**命题**：Linux AgentOS = Linux kernel + Agent + MCP 服务。三角色映射（demo 的全部认知载荷）：

| Linux 概念 | demo 实现 | 先例对齐 |
|---|---|---|
| **进程**（fork/exec/信号/退出码） | Agent=真实 Linux 进程（subprocess 起，pid/kill -TERM/exit code 全真） | srt 把 agent 当任意进程；Karpathy "Agent=进程" |
| **内核**（syscall 表+权限位+日志） | DemoKernel 监督者：per-agent 能力表（allow-list）→审计 JSONL | AIOS 只有函数命名风格的 "syscall"；laos caps.py 同构 |
| **设备驱动**（设备总线+探测+I/O） | MCP server（stdio JSON-RPC）：fs.read/fs.write（jail 内）+time.now | MCP stdio transport=客户端拉起子进程——天生进程模型 |
| **强制层**（L4，能力之外的物理边界） | agent 进程自装 seccomp-BPF：execve/socket 族 EPERM | Anthropic srt 同款思路（封 unix socket） |

**边界**：demo 是认知演示物（自包含、零依赖、~500 行、WSL 运行），不进 laos 核心、不进主测试套件；它是 laos 命题的蒸馏展示，不是 laos 本体。**实施细节见 [2026-10-08-agentos-demo.md](../superpowers/plans/2026-10-08-agentos-demo.md)**（writing-plans 格式，四任务 TDD）。

**升级路径**（demo 之后的可选项，不在本计划内）：systemd-run --slice 起真 unit（cgroup 计账）；MCP server 改 unix socket+socket activation（规范背书的空白点）；bpftrace 一次 execve 观测；SchedCP 式 sched_ext 演示（需 kernel 6.12+）。

## 7. 来源与口径

三路调研共 ~160 次检索/抓取，关键一手源：AIOS 源码（scheduler/base.py 直读）、Anthropic containment 博客、MCP 2026-07-28 spec transports 页、RHEL 10 官方文档、Apple Newsroom+隐私白皮书、各 GitHub 仓库页（2026-10-08 快照；匿名 API 限流，star 数取页面实时值）。二手/付费墙转述（Bloomberg/Reuters）与未证实项（OpenAI 耳机出货预测、Ray-Ban Gen3 续航、Sacra ARR 估算等）已在正文标注。凡"推"标均为推断。完整来源清单随三路简报存档于本报告引用的链接内。
