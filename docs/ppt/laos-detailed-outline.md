# laos 详细版项目介绍 —— 共享底稿（wave2，供 5 个 PPT skill 各自渲染）

> 版本基准：v0.12.0（2026-10-05）。所有数字均来自仓库真实状态，禁止虚构。
> 详细版定位：上一波 12 页概览的**深潜版**——每一页都下钻到机制层。
> 页数指引：18-24 页（各 skill 版式不同可微调，内容域不得缺）。

## 内容域（18 个，每个 = 一页或一组）

### A. 开场组

**A1 封面**
- 标题：laos —— Linux AgentOS
- 副题：Linux 内核的 Agent 扩展（用户态 · 零内核改动）· 详细技术深潜
- 一句话：Linux AgentOS = Linux kernel + Agent + MCP
- 版本角标：v0.12.0 · 2026-10-05

**A2 命题**
- 不改一行内核代码，把 Linux 变成 Agent 的操作系统
- 复用四件内核遗产：namespace（隔离）/ cgroup（配额）/ seccomp-BPF（系统调用过滤）/ landlock（文件沙箱）
- 映射表：MCP Server = 设备驱动 · tool call = 系统调用 · laosd = 薄内核 · 能力表 = 权限位
- 关键判断：Agent 时代的"内核"不是重写调度器，而是给工具调用装上 syscall 语义

**A3 与"AgentOS 八种含义"的坐标**
- 调研结论：市面上"AgentOS"至少指 8 种不同的东西（docs/research/agentos-landscape-2026-08.md）
- 定位坐标：强制力光谱 L0（约定层）→ L3（libOS 层）；laos 落在 L2——用户态强制层
- 差异化：多数"AgentOS"是框架/壳，laos 是治理内核：能力、预算、审计、判断四件事在派发前完成

### B. 内核组

**B1 总体架构分层**
- 自上而下：Agent（brain/agent）→ laos 内核（kernel.py 调度 + syscall 闸门链）→ 驱动子进程（15 个 drv_*，重依赖隔离）→ Linux/MCP/外设
- 核心承诺：laos/ 目录零第三方依赖（纯 stdlib）——重依赖只活在驱动子进程
- 三棵树：laos 主库 · AlwaysOnRec 隔离区 · Repro 复现区

**B2 syscall 闸门链（本页是全片核心，建议做成 8 环流程图）**
1. 能力表（caps，如 screen.*）
2. task_scope（路径前缀 / pkg: 应用白名单 / time: 时间窗）
3. schema 校验（参数非法即拒，EINVAL 语义）
4. EDQUOT 预算（配额耗尽即拒）
5. FleetLedger 不可逆计价（先扣账后派发，风险分扣减）
6. Jev 预审（opt-in 判断层：值不值得做）
7. 确认横幅（高危操作人审）
8. 派发 + 审计（每笔 tool call 留痕）
- 例：screen.tap 越过 pkg: 白名单 → 第 2 环即拒，不触 adb

**B3 分支与内存模型**
- branch.py 分支树 + cow.py 写时复制上下文
- Agent 可在分支上试错，合并回主线（类似 git 语义的 Agent 上下文管理）
- memory.py MemoryStore + diary/journal 日记层：记忆闸门只记实际发生的交互

**B4 判断层 Jev**
- 四闸门决策模型（三判型：Noul/Choice/Score）
- laos 11 处硬阈值映射 + 端侧实测 median 157.5ms（README 宣称 15.6ms 被实测否证，慢 10×——诚实数字）
- judge 透传：TurnBuffer.commit / memory.remember 都可挂 judge

### C. 驱动生态组

**C1 驱动全景表（15 驱动）**
- 听觉：drv_mic（录音，显式 syscall 触发）/ drv_ear（转写+LUFS）/ drv_rec
- 手机：drv_screen（tap/text/dump/key/longpress/doubletap/devices）/ drv_apps（list/launch/close）/ drv_notify / drv_battery / drv_comms / drv_events
- 系统：drv_fs / drv_proc / drv_sys / drv_npu（QNN 真机）/ drv_audio / drv_genie
- 治理事实：kernel.load_driver() 外挂需过闸；apps.*/screen.* 均受 pkg 作用域闸门

**C2 端侧听觉栈（漏斗图）**
- vad.py 能量+滞回 VAD（10ms 帧，无声即弃零存储）
- loudness.py BS.1770-4 全套：K 计权（48k Annex 精确系数）/门控积分/LRA/True Peak（sinc 重构）/PLR——校准锚点 −23.00 LUFS ±0.1
- binaural.py Goertzel 逐频点 ILD/IPD（250/500/1k/2k/4k Hz）
- micgeom.py 麦克风几何 MPE（与官方 JAX 源码逐行对齐，跨实现 diff 0.0）
- foa.py 一阶 Ambisonics 编解码（SN3D/N3D + ACN）
- ShoNet DOA 复现（Repro 区）：STFT 相位特征 → CNN+BiGRU+MHSA，冒烟 holdout 56.5°

**C3 全双工轮转三件套（时序图）**
- duplex.py：事件时间线 → 响应延迟 / 打断响应 / 重叠率 / 抢话计数（Duplex-MPE 四能力分解）
- turnpolicy.py：speak/hold/stop 三态（min-speech 200ms / tail-silence 500ms / min-hold 250ms 三闸，防过早响应）
- turnbuf.py：打断即作废（未送达丢弃）/ 只记已送达（记忆不写想象）/ interject 插队帧（慢系统结果无缝织入）
- 来源论文标注：Duplex-MPE / SALMONN-duo / Context Spanning（2026-09 周报波）

**C4 AlwaysOnRec 双沙箱**
- 隔离区 279 测试：环形缓冲 + 端侧蒸馏 + 7 天即焚（Apple Watch S12 范式对照）
- 四段漏斗：VAD 常开 → 段落成段 → 本地转写 → 事件入记忆
- 隐私红线（一条都不能破）：录音只由显式 syscall 触发 · LAOS_REC=0 全局禁录 · 每次调用审计 event:"mic" · ASR 全本地

### D. 质量与文化组

**D1 测试与质量**
- 765 测试全绿：主库 415 + AlwaysOnRec 279 + Repro 71
- TDD 纪律：先红后绿，每任务一 commit
- 版本纪律：SemVer + conventional commits；30 天 12 个 MINOR 版本（v0.1.0 → v0.21.0）

**D2 版本史时间线（12 段，每段一句话）**
- v0.1.0 (09-04) baseline 149 文件 / v0.2.0 (09-05) 强制层 seccomp+CoW+eBPF+FleetLedger / v0.3.0 (09-09) AgentProf+MCP Tasks+信箱+laosweb+drv_npu / v0.4.0 (09-11) 听觉+记忆+日记 / v0.5.0 (09-11) 五层手机能力+双沙箱 / v0.6.0 (09-18) 语料库 19,792 论文+3,724 OSS / v0.7.0 (09-28) Jev 四闸门 / v0.8.0-v0.10.0 (10-05) 复现采纳三连（SHO/PhaseCoder/ANC/LUFS/Pipecat/unique_lock→loudness/turnbuf/locks+五套 PPT）/ v0.11.0 (10-05) 手机操控四件套+drv_apps+micgeom / v0.12.0 (10-05) 双工时序+轮转策略+双耳线索+FOA

**D3 复现文化（Repro-ZCode）**
- 71 测试隔离区：能复现的论文全部复现（BS.1770 响度 / FxLMS ANC >20dB / ShoNet DOA / PhaseCoder MPE 逐行对齐）
- 诚实清单：跑不动的等比缩距并写明偏差（40,295 样本→百样本冒烟）
- 采纳漏斗：复现 → 裁决（●执行/◐基础件/○不做）→ 主库落地 → 文档执行注记

**D4 调研语料库**
- 47 份调研文档 + capstone 采纳总账（每条：来源/可取之处/落点/状态）
- 19,792 篇双会议论文（ICASSP 2022-2026 14,285 + Interspeech 2021-2025 5,507，全量 100%）
- 3,724 个 OSS 星标仓库（去噪后：core 132 / ref 2,864 / unrelated 728）

### E. 收尾组

**E1 安全与合规红线**
- 拒绝清单实证：jarvis 七文件一行不碰（伪装配置/聊天截获/屏幕捕获/常驻保活）
- 法条跟踪：EU AI Act（职场/教育情绪识别禁令）/ PIPL（声纹=敏感个人信息，单独同意）
- 原则：能力可以有，红线内的能力永远不做

**E2 路线图**
- 近期（v0.13+）：FDGym 式模拟用户回归 / Bin2Ambi 驱动 / FOA 评测钩子接 RMS-AQA
- 中期（v1.0）：多 Agent 并发调度 / 驱动市场（第三方 MCP 治理接入）
- 远期：端侧完整语音 Agent 参考机（laosd + 听觉栈 + 全双工闭环）

**E3 收尾页**
- 一句话：Agent 需要的不是更强的模型，是一个会说"不"的内核
- 仓库：github.com/Yfredy/LAOS · v0.12.0 · 765 测试

## 版式注意
- 每页信息密度可以高（这是详细版），但必须有清晰层级（kicker/标题/正文/角标）
- 数字角标统一：版本 v0.12.0 · 测试 765 · 驱动 15 · 版本 12 个
- 论文/机制引用标注来源（arXiv 号或 docs/research/ 路径）
