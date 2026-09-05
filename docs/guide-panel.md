# laosweb 面板使用教程

> 启动：`python bin\laosweb.py` → 浏览器开 `http://127.0.0.1:8800`
> （端口被占换 `set LAOS_WEB_PORT=18800`；高危操作默认弹**确认横幅**等人裁决，
> 想跳过横幅自动放行看计费效果用 `set LAOS_CONFIRM=auto-yes`，或直接在面板的重启控制台里切）

## 这个面板是什么

每次启动，laosweb 会在后台跑一遍**完整的内核演示**（约 0.5 秒）：引导内核 → 加载 3 个驱动 →
建 main 分支 → fork 出 exp-A / exp-B 两个探索分支 → 起 2 个 Agent（一个权限全、一个只有 `sys.*`）
并发跑 ReAct 任务 → 演示内核 IPC 和能力委托 → first-commit-wins 提交。
面板把这整个过程的状态**实时**展示出来，每秒刷新一次。

## 七个面板怎么读

### 1. 顶部状态条
`uptime` 内核存活秒数 · `隔离` Linux 内核隔离是否生效（Windows 上显示 none = 仅能力表，上 Linux 会变 full）·
`驱动 3` 已加载的 MCP 驱动数 · `审计 N 条` 审计日志事件数 · 最右边的圆点：**蓝=demo 运行中，灰=已结束**。

### 2. 进程表（Agent = 进程）
| 列 | 含义 |
|---|---|
| pid / name | 进程号（从 1001 起）和名字 |
| state | ready=可调度 · running=syscall 执行中 · zombie=正常退出 · killed=被终止 |
| caps | 能力表——**它能调哪些 syscall**（`fs.*`=文件读写、`proc.*`=执行命令、`sys.*`=系统信息、`msg.*`=消息） |
| scope | 任务边界——`/exp-A/` 表示只许碰这个路径前缀（意图收窄） |
| branch | 它在哪个分支上工作 |
| sys / deny / risk | 成功调用数 / 被拒次数 / 风险账单 |

**看点**：guest-agent 只有 `sys.*`，它去调 `fs.read` 会被内核当场拒绝（EPERM）——这就是"能力表"在执法。
每行末尾的 **✕ 按钮**可以随时 kill 一个进程（operator 和已死进程没有按钮）；kill 后 state 变 `killed`
并保持不变，调度器随即注销该 pid——它后续的 syscall 会在调度闸门上拿到
`ESRCH: scheduler suspended pid (token/err budget exhausted)`，不再占用 LLM 时间片。
进程表里那个叫 **operator** 的常驻进程就是你自己——human-in-the-loop
是以"人也是一个进程"的方式进场的。

### 3. 分支树
`main [exploring]` 是主干；`exp-A [committed]`（绿）表示探索成功并已合并回主干；
`exp-B [invalidated]`（灰）表示被 first-commit-wins 规则作废——兄弟分支谁先提交谁活，其余全部失效。
这对应论文的 fork → explore → commit 原语：Agent 可以放心在分支里"搞破坏"，提交才生效。

### 4. 风险账本
`spent` 已消耗的不可逆风险点 · `remaining` 剩余 · `budget` 总预算（默认 3）。
不可逆操作（如 `proc.exec` 执行命令）按定价扣分；**被拒绝的调用不计费**；预算耗尽后新的不可逆调用直接被拒。
想看到扣分过程：demo 跑到 `proc.exec` 时点横幅上的 [✓ 允许]（或在重启控制台切"自动放行"再重跑），spent 变 3。

### 5. 调度快照
每个 agent 的 `err=已错/上限` 和 `tokens` 用量。失败（驱动报错等）会消耗错误预算，
耗尽即挂起让出 LLM 时间片（Patient Bytes 思想：老把事办砸的 agent 少占用资源）。

### 6. 审计流（最右在先 = 最新事件在最上面）
每一行是一次内核裁决，格式：`时间 pid [徽标] 工具 → 结果`。
- 绿色 = 成功；红色 = 被拒
- **彩色徽标 = 事件类型**：`stale_broadcast`(橙) 分支提交导致上下文陈旧广播 · `delegate`(黄) 能力委托 ·
  `sys.delegate`(青) 内建委托调用 · `admission`(紫) 准入控制 · `builtin`(青) 内核内建 syscall（不经 MCP 驱动）
- **看点多**：demo 里你能依次看到——guest 调 `fs.read` 被能力表拒（第一层防御）→
  guest 被拒绝时带 `task_scope` 的路径也被拦（第二层）→ ops 的 `proc.exec` 被确认关拦（第三层）→
  ops 给 guest 发消息、委托能力 → 分支提交触发 stale 广播。**这就是"纵深防御"在跑**。

### 7. 系统调用表（底部 chips)
当前内核注册的全部 syscall——Agent 只能看到自己 caps 覆盖的子集，这张表是全量视图。

### 8. 消息面板（operator 信箱）
**人也是系统里的一个进程**：boot 时内核会 spawn 一个常驻的 `operator`（pid 就在进程表里）。
- **发送**：选目标 agent 的 pid、写一句话、点 [发送] —— 面板以 operator 的身份跑 `msg.send`，
  消息落进目标 agent 的内核信箱（它下一步 `msg.recv` 就能读到）。
- **收取**：每个活进程一粒 [收取] 按钮，以该 pid 自己的身份跑 `msg.recv` 并把信箱内容显示在面板上——
  你可以替任何 agent"拆信"，看它收到了什么。
发送/收取都是**内核内建 syscall**（不经 MCP 驱动），所以从 HTTP 线程直接发起也是安全的。

## 交互功能

laosweb 不只可看，还可操控——全部交互走 `POST /api/*`，不引入任何依赖。

### 确认横幅（human-in-the-loop 的主入口）
demo 里的 agent 一旦发起**高危 syscall**（如 `proc.exec`），内核的确认关会把整条请求挂进待裁决队列，
demo 冻结等你裁决；面板顶部弹出红色横幅（闪烁边框）：`⚠ 内核等待裁决：… [✓ 允许] [✗ 拒绝]`。
- **点 [✓ 允许]**：syscall 放行执行——审计流里该行变绿，风险账本 spent +3（`proc.exec` 定价 3）。
- **点 [✗ 拒绝]**：syscall 被拒（EACCES）——审计流红行，**不计费**。
- **60 秒不点**：超时自动按拒绝处理，队列项清除。
- 想跳过横幅：重启控制台切"自动放行"（或启动前 `set LAOS_CONFIRM=auto-yes`）——高危操作秒答放行、照常计费。

### 重启控制台（换参数重跑 demo）
面板顶部的小面板：选 confirm 模式（横幅裁决 / 自动放行）+ 填风险预算（默认 3），点 [↻ 重跑]——
面板按新参数重新 boot，新内核完全就绪后才退役旧内核（boot 半途失败时旧内核照常服务，面板不会 503），
demo 从头跑一遍。预算必须 **> 保留水位 reserve=1**（输入框已限 min=2，低于会被 400 拒绝——预算 1
连 operator 都 spawn 不进）。适合做实验：预算调成 2 就能看到 `proc.exec` 被"车队风险预算耗尽"拒绝；
切自动放行就能完整看一遍计费流。
重启后审计流从头滚动（客户端去重账本会自动清空）。

### kill 按钮
进程表每行末尾的 ✕：随时终止一个越权/失控的 agent（同步 `kernel.kill`，HTTP 线程安全；operator 是
你自己，直接 POST /api/kill 也会被 400 `cannot kill operator` 拒绝）。
被 kill 的进程 state 变 `killed` 并保持不变（不会在运行收尾时被改写回 zombie/ready）；调度器随即注销
它——agent 后续的 syscall 会在调度闸门上拿到 `ESRCH: scheduler suspended pid (token/err budget
exhausted)`（有界等待约 2s 后返回），不再分配 LLM 时间片；它授出的能力委托也会被内核即时撤销。

### 实验
1. **横幅裁决**：默认启动 → demo 到 `proc.exec` 时横幅弹出 → 点 [✗ 拒绝] → 审计红行、spent 仍 0；
   再点 [↻ 重跑] → 这次点 [✓ 允许] → 审计绿行、spent=3。
2. **给 agent 递纸条**：消息面板选 ops-agent 的 pid，发送"请先 fs.stat 再 read"，再点它的 [收取] 看信箱。
3. **处决**：点 guest-agent 行的 ✕ → state 变 killed 并保持不变 → 它被移出调度器，
   后续 syscall 全部 `ESRCH: scheduler suspended pid`。

## 动手实验

1. **看拒绝计费**：横幅弹出时点 [✗ 拒绝] → 审计流 proc.exec 红、spent=0；重启控制台切"自动放行"再重跑
   （或启动前 `set LAOS_CONFIRM=auto-yes`）→ 审计流里 proc.exec 变绿、风险账本 spent=3。
2. **调预算**：`set LAOS_RISK_BUDGET=2` → 一条 proc.exec（价 3）直接被车队预算拒（`fleet risk budget exhausted`）。
   （预算必须 > reserve=1：设 1 会在 boot 时连 operator 都 spawn 不进。）
3. **换端口**：`set LAOS_WEB_PORT=9000`。
4. **事后回放**（不用面板）：`python bin\laosctl.py ps`（进程表）/ `top`（耗时）/ `budget`（风险账本）/
   `spans`（语义剖析）/ `trace --pid 1001`（单 agent 回放）/ `denied`（全部被拒调用）。
5. **跑真 LLM**：`set OPENAI_API_KEY=... && python bin\laosd.py --real --task "你的任务"`——ScriptedBrain 换成真模型，面板照常可看（用 laosweb 跑真 LLM 同理）。

## 它和传统 OS 的对应关系（一句话版）

进程表 = 任务管理器 · 能力表 = 文件权限 · 审计流 = 事件查看器/auditd · 风险账本 = 配额管理 ·
分支树 = git · 调度快照 = 任务管理器的"已挂起"列 · 驱动 = 设备管理器里的设备。
