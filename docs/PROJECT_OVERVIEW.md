# laos —— 运行在真实操作系统上的 AI Agent 操作系统

> **一句话**：laos 是一个给 AI Agent 用的"操作系统"——它站在 Linux/Android 内核之上，给 Agent 提供进程管理、权限控制、资源记账、记忆和感官，让多个 Agent 安全、可审计、越用越聪明地替你干活。
>
> **核心命题**：`Linux AgentOS = Linux kernel + Agent + MCP`。不改内核，用 Linux 已有的强制原语（seccomp/namespace/cgroup）做**强制层**，自己写用户态薄内核做**语义层**，用 MCP 协议做**驱动总线**。纯 Python 标准库实现（核心零第三方依赖），Windows/macOS 上自动降级运行，Linux 上开启真隔离。

---

## 这个项目解决什么问题？

直接跑一个 AI Agent 有四个致命缺陷，laos 逐一补上：

| 裸 Agent 的问题 | laos 的答案 | 实现 |
|---|---|---|
| **无权限模型**——给它 shell 它就能 `rm -rf /` | 三层能力执法：能力表（caps）→ 任务作用域（task_scope：路径前缀 / `pkg:` 应用包名）→ 确认横幅（高危操作人类裁决） | `kernel.syscall` 闸门链 |
| **无资源记账**——一个 Agent 能烧光预算 | 不可逆风险账本（按工具定价 × 电池感知乘数）+ token/错误双预算调度 + spawn 准入控制 | `risk.py` / `scheduler.py` |
| **无记忆**——每次从零开始 | 情景记忆库（中文免分词检索 + 时间衰减）+ 技能库（成功任务沉淀为可复用解法）+ 每日日记 | `memory.py` / `skills.py` / `bin/diary.py` |
| **不可审计**——黑盒干活 | 每一次工具调用 = 一条带 errno 的 syscall 审计 + eBPF 内核真值对照 + 语义 span（OTLP 导出） | `audit` / `profiling.py` / `agentprof.py` |

一句话总结架构：**Agent 是进程，MCP tool call 是系统调用，MCP Server 是设备驱动，能力表是文件权限，审计流是事件查看器**。

---

## 五分钟看懂：一次 Agent 干活时发生了什么

```
你（浏览器面板）→ 下达任务
  Agent（=进程，带 PCB/caps/risk_cap/task_scope）
    → kernel.syscall("fs.write", args)          # 每次 tool call 一次 syscall
        ① ESRCH/状态检查   ② 能力表 EPERM？     ③ task_scope 路径越界？
        ④ 参数 schema 校验 ⑤ syscall 预算 EDQUOT ⑥ 风险账本（不可逆计费+确认）
        ⑦ 派发：内建 syscall（IPC/记忆）或 MCP 驱动子进程（fs/proc/...）
        ⑧ 审计 + AgentProf 记 span + stale-context 观察
  高危操作 → 红色横幅弹出等你点【允许/拒绝】（不点 60 秒自动拒）
  成功任务 → 自动沉淀为技能 → 下次同类任务注入 [skill-hint]
```

启动方式：

```bash
python bin/laosd.py     # 命令行跑完整 demo（七幕：fork分支→ReAct→IPC→委托→提交→报告）
python bin/laosweb.py   # 浏览器开 http://127.0.0.1:8800 实时面板 + 交互操控
python -m unittest discover -s tests   # 253 项回归测试
```

---

## 目录总览（每个文件是干什么的）

```
laos/
├── laos/                    ★ 内核（语义层）——纯标准库，零第三方依赖
│   ├── kernel.py            内核主体：syscall 闸门链（能力→作用域→校验→预算→风险→派发）、
│   │                          PCB 进程表、spawn 准入、审计、内建 syscall 注册（msg.*/mem.*）
│   ├── mcp.py               MCP 协议最小实现（JSON-RPC over stdio）= 驱动总线；
│   │                          含 2026-07-28 规范的 Tasks（异步工具）与 Elicitation（人类在环）
│   ├── memory.py            记忆库：JSONL 存储 + 字符 bigram Jaccard + tags + 时间衰减检索
│   ├── skills.py            技能库：成功任务序列 → 指纹签名 → 检索注入 [skill-hint]
│   ├── risk.py              FleetLedger 风险账本：按工具定价×乘数、agent/车队两级记账、准入水位
│   ├── scheduler.py         LLM 时间片调度器：优先级轮转 + token/错误双预算（耗尽挂起）
│   ├── agent.py             Agent 运行时：ReAct 循环、调度 acquire、技能学习/提示注入
│   ├── brain.py             大脑接口：ScriptedBrain（确定性演示）/ OpenAIChatBrain（真 LLM）
│   ├── context.py           上下文管理（=虚拟内存）：滑窗/摘要压缩/swap + stale 观察簿
│   ├── branch.py            分支原语：fork(硬链接COW零拷贝)/explore/commit(先到先得)/abort
│   ├── cow.py               写时复制原语：temp+os.replace 原子断链，保护共享 inode
│   ├── seccomp.py           seccomp BPF 组装器（纯 Python 手搓经典 BPF，34 条危险 syscall 黑名单）
│   ├── sandbox.py           Sandbox/PathJail：驱动子进程的路径监狱 + 隔离报告
│   ├── enforcement/         强制层后端（CherryUSB OSAL 模式：换平台=换一个文件）
│   │   ├── linux.py           Linux 真隔离：unshare+seccomp shim+cgroup v2
│   │   ├── android.py         Android/Termux 后端（限制矩阵文档化）
│   │   └── stub.py            非 Linux 降级
│   ├── vad.py               语音活动检测：批式/流式一致（能量+滞回+补边），零依赖
│   ├── agentprof.py         语义剖析：审计流→per-agent span→OTLP/JSON 导出
│   ├── profiling.py         eBPF profiling：bpftrace 采集驱动进程真实 syscall（内核真值）
│   └── validate.py          参数 schema 校验（堵"工具管理器无校验"的洞）
│
├── drivers/                 ★ 设备驱动（每个=一个 MCP Server 子进程，14 个）
│   ├── drv_fs.py            文件系统：read/write/append/list/stat（jail 内）
│   ├── drv_proc.py          进程：exec（白名单+危险模式拦截）/list
│   ├── drv_sys.py           系统信息：info（主机名脱敏）/load
│   ├── drv_npu.py           NPU 推理：QNN 后端探测 + 真机 device 传输（功耗定价）
│   ├── drv_audio.py         语音增强：FLASepformer 双说话人分离 + JAEC 回声消除
│   ├── drv_ear.py           语音转文字：SenseVoice GPU / HTTP server 双通道（含情感标签）
│   ├── drv_mic.py           麦克风：显式录音 + VAD 分段（录音必审计）
│   ├── drv_rec.py           听觉日志：VAD 触发式录音会话（只有有声段落盘+即焚）
│   ├── drv_genie.py         端侧 LLM：QAIRT Genie / OpenAI 兼容（ollama）双后端
│   ├── drv_screen.py        屏幕操控：dump/tap/swipe/text（adb 通道，pkg 白名单双重校验）
│   ├── drv_notify.py        通知读取（Termux / App 双传输）
│   ├── drv_comms.py         短信收发 + TTS（发短信=不可逆操作，走确认横幅）
│   ├── drv_battery.py       电池状态（喂给动态功耗定价：低电量风险成本×3）
│   ├── drv_events.py        全天候感知：真机情感事件流拉取
│   └── screen_adb.py        adb 传输类 + uiautomator XML 解析（drv_screen 的底座）
│
├── bin/                     ★ 用户入口
│   ├── laosd.py             引导器（=init）：加载驱动→建分支→起 Agent→跑 demo 七幕
│   ├── laosweb.py           Web 面板：实时看板（进程/分支/风险/审计）+ 交互操控
│   │                          （确认横幅/重跑/kill/发消息/生成日记）
│   ├── laosctl.py           控制面 CLI：ps/top/trace/denied/budget/spans/prof
│   ├── diary.py             每日日记：审计+记忆聚合→四章节 markdown（LLM 可选/模板兜底）
│   ├── journal.py           听觉日志管线：录音段批量转写→入记忆→原音频即焚
│   └── mood_report.py       情绪周报：journal 记忆按日聚合→字符堆叠图
│
├── scripts/                 辅助脚本
│   ├── termux_matrix.py     Android/Termux 强制层降级矩阵一键实测（7 项检查）
│   └── flasep_gpu_bench.py  FLASepformer GPU/CPU 基准（RTX 4060 实测 9.3x 加速）
│
├── tests/                   253 项回归测试（21 个文件；真录音/真 ASR 用例在本机实测通过）
├── docs/                    研究与文档：论文调研、真机 runbook、面板教程、实施计划
├── var/                     运行期产物：audit.jsonl / branches/ / swap/ / memory.jsonl / diary/
└── outputs/                 模型产物：分离音轨 / 基准 JSON
```

---

## 五大能力版图（全部已实现）

**① 安全与强制**：能力表三级粒度（`fs.*` → `fs.read`）｜路径作用域（`task_scope`，防 `..` 穿越）｜应用作用域（`pkg:` 白名单——Agent 只能操控指定 App）｜seccomp BPF（34 条危险 syscall，fail-closed）｜确认横幅（人类在环，60 秒超时自动拒）｜fork 委托不可提权（TTL+死亡撤销）

**② 资源记账**：不可逆风险账本（SOSP'26 论文机制：按工具定价、agent 帽+车队预算、spawn 准入、**电池感知动态乘数**）｜LLM 时间片调度（token/错误双预算，耗尽挂起让出）｜尝试定价语义（授权即计费，拒绝不计费）

**③ 记忆与学习**：情景记忆（`mem.remember/recall/forget`，中文免分词）｜技能库（成功任务→签名→`[skill-hint]` 注入）｜每日日记（LLM 可选模板兜底）｜情绪周报

**④ 感官与执行**：麦克风（VAD 触发录音）｜ASR（SenseVoice 双通道，GPU RTF≈0.01，带情感标签）｜语音增强（分离/回声消除，GPU 实测 9.3x 加速）｜屏幕操控（adb，pkg 白名单）｜通信（短信/TTS/通知）｜端侧 LLM（Genie/ollama）｜NPU（QNN 真机传输）

**⑤ 可观测**：全量审计（每次 syscall 带 errno）｜eBPF 内核真值对照｜OTLP span 导出｜Web 面板实时看板+操控

---

## 已验证的真机与实测亮点

- **真机闭环**：真机 App 内嵌 HTTP 推理服务（127.0.0.1:8900），laos 的 `npu.infer` 经 adb forward 直达骁龙 **ADSP 上的 QNN LPAI** 硬件推理——审计流记录真实延迟、风险账本扣功耗费
- **GPU 实测**：FLASepformer 在 RTX 4060 上 CPU vs GPU 加速比随音频长度 6.4x→9.3x（30s 音频 1.99s，验证论文线性复杂度主张）
- **真录音+真 ASR**：对着麦克风说话 → SenseVoice 返回文本+情感标签（`今天天气怎么样？ 😔 SAD`）全链路实测通过
- **多平台**：Windows（降级模式开发）/ Linux（全隔离）/ Android+Termux（强制层 OSAL，附一键实测矩阵脚本）

---

## 快速上手

```bash
git clone https://github.com/Yfredy/LAOS.git && cd LAOS
python bin/laosweb.py              # 打开 http://127.0.0.1:8800
# 面板上：看审计流滚动 → 点【重跑】触发确认横幅 → 允许/拒绝高危操作
#        → 生成日记 → 翻记忆面板

# 真机（可选）：装 App + adb forward 后
set LAOS_NPU_ENDPOINT=http://127.0.0.1:8900
python bin/laosd.py                # demo 第 4.6 幕 = 真 DSP 推理
```

进阶文档：`docs/guide-panel.md`（面板教程）｜`docs/research/qnn-real-device-runbook.md`（真机手册）｜`README.md`（环境变量全表）

---

## 定位与边界（诚实说明）

- **是什么**：研究原型 + 个人常驻系统的骨架——253 项测试守护的可运行语义内核，覆盖 SOSP'26 AgenticOS Workshop 上的核心机制（Irreversibility Budget / Stale Context / AgentProf / 可靠性预算调度 / 运行时委托）
- **不是什么**：不是 Linux 发行版，不修改内核；不替代你的操作系统——它是**架在操作系统之上、专为 Agent 服务的那一层**
- **已知边界**：Termux 上 namespace/cgroup 受限（降级矩阵已文档化）；全天候低功耗常驻拾音依赖真机前台服务（runbook 提供）；多人场景的说话人分离待做
