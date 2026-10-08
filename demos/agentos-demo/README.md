# Linux AgentOS demo —— 30 秒讲清 kernel + Agent + MCP 三件套

一个最小可运行模型：**Linux 内核就是 AgentOS 的底座**，Agent 是与进程同类的
新负载。本 demo 不给 Agent"装"操作系统——而是把操作系统已有的治理角色
（进程、监督者、驱动、强制层）逐一指给 Agent 生态里的对应物看。

## 对应表（本 demo 的全部论点）

| Linux 概念 | demo 对应物 | 实现文件 | 什么是真的 |
|---|---|---|---|
| **进程** | Agent（`agent.py`） | `agent.py` | pid / 信号 / 退出码全是真的：`spawn()` 拿到真 pid，`kill()` 发真 SIGTERM，被杀 agent 的退出码是负数（Linux 语义）。Agent 的唯一资源通道是 stdin/stdout 一对管道 |
| **监督者（内核）** | `DemoKernel` | `kernel.py` | 能力表 = per-agent allow-list（不在表内 → EPERM）；审计 = `var/audit.jsonl` 一行一事件（t/pid/agent/op/args/ok/result）；代理 = 放行的 syscall 经 `_dispatch` 转给驱动，内核自己不做 I/O |
| **设备驱动** | MCP 文件服务 | `mcp_fs.py` | stdio = 设备总线（JSON-RPC 2.0 over pipes），`tools/list` = 设备探测，`tools/call` = 一次设备 I/O；工具面窄到只剩 `fs.read`/`fs.write`/`time.now`，且 fs 只在 jail 内（`DEMO_JAIL`，越界路径驱动侧直接拒）——驱动只做设备语义，治理在内核 |
| **强制层（L4）** | seccomp | `seccomp_gate.py` | agent 进程开机自装 BPF 过滤器：execve/execveat/socket 族一律 EPERM。能力表管"许可"，seccomp 管"物理"——即使内核有 bug 放行越权 op，agent 也生不出新进程/网络连接 |

## 五幕剧本（`run_demo.sh`）

1. **设备上线**：MCP 文件服务就位，jail 落盘（懒启动，首次 syscall 才拉起）
2. **Agent 上场**：reader（能读、能 execve 自测，**无** fs.write）与 writer（能写）两个真进程
3. **syscall 循环**：agent 逐条请求 → 内核查能力表 → 放行的代理到驱动，拒绝的直接回 EPERM
4. **验证**：reader 的 `fs.write` 被能力闸拦（DENY，b.txt 不存在）；`selftest.execve` 在 agent 进程内被 seccomp 拦（DENY，result 含 "blocked"）；writer 的 c.txt 真落盘
5. **审计收尾**：打印 `AUDIT N rows -> var/audit.jsonl`

任何一幕断言失败，脚本非零退出。

## 运行

```bash
# WSL / Linux x86_64（seccomp 过滤器仅 x86_64 syscall 号表）
wsl -- bash demos/agentos-demo/run_demo.sh

# 测试（7 tests；非 Linux 下 seccomp 与整链两例 SKIP）
wsl -- python3 demos/agentos-demo/test_demo.py
```

零依赖：`kernel.py`/`agent.py`/`mcp_fs.py`/`seccomp_gate.py` 全部纯 stdlib，
不 import laos，demo 自包含。

## 与 laos 主仓的关系

本目录是 **laos 的认知蒸馏物**，不是 laos 本体：laos 是内核治理在用户态的
延伸（四闸/录音/评测……），体量和责任都远大于此；demo 只保留"治理角色
对应表"这条认知主干，用来 30 秒向旁人讲清架构立场。demo 代码与主仓
`laos/` 包无 import 关系、互不依赖。

## 来源

- seccomp 模式复刻自主仓 `laos/seccomp.py`（prctl + seccomp(2) 直调、经典
  BPF 四元组、每条 JEQ 紧跟自己的 RET 的交错布局、`SECCOMP_RET_ERRNO|EPERM`），
  缩小为 execve/socket 两条规则的 demo 版。
- MCP stdio JSON-RPC 契约参考 `laos/mcp.py` 同型实现。
